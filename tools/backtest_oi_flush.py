"""P1 OI-FLUSH DONUSU — gecmis veri budamasi (ON-KAYIT: docs/ideas.md 2026-08-14).

KURALLAR (donmus — burada degistirilemez):
  Her 15m kapanista: dOI(24s)/OI <= -%10 (kontrat adedi) VE fiyat ayni 24s'de
  >= 2xATR(14,4H) dusmus (kapanis-kapanis) VE son 15m kapanis oncekinin
  USTUNDE (stabilizasyon) -> LONG (girise 15m kapanis).
  Stop: 24s penceresinin dibi - 1xATR(14,15m). Hedef 2R. Zaman asimi 96 bar
  (24s) -> EXPIRED r=pnl/risk. Ayni mumda stop+hedef -> LOSS(ambiguous).
  Kume = yon + 4H penceresi (pariteler arasi ORTAK). Parite basina tek acik
  pozisyon; ayni kume ayni paritede tekrar islem acmaz.
  Maliyet canli modelle ayni (2xtaker + LOSS kaymasi + funding x tutus).

VERI: --data (kline arsivi: PAIR_15.csv + PAIR_240.csv) ve --oi
  (PAIR_oi_1h.csv; tools/download_oi_data.py ciktisi). Parite parite islenir
  (bellek dostu). OI'si veya mumu olmayan parite atlanir ve sayilir.

TEK ATIS — parametre taramasi yok.

KULLANIM (VM):
  cd ~/bybit-signal-bot-audit && git pull
  .venv/bin/python tools/backtest_oi_flush.py \\
      --data /home/ubuntu/backtest-data --oi /home/ubuntu/oi-data
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import measurement                          # noqa: E402
from app.services.signal_tracker import (FUNDING_8H, STOP_SLIP,  # noqa: E402
                                         TAKER_FEE)

M15 = 900_000
H4 = 14_400_000
DAY = 86_400_000
OI_DROP = -0.10          # dOI(24s)/OI esigi
PRICE_DROP_ATR = 2.0     # 24s dusus esigi (ATR-4H kati)
STOP_PAD_ATR = 1.0       # stop: pencere dibi - 1xATR(15m)
TP_RISK = 2.0
TIMEOUT_BARS = 96        # 24 saat
ATR_N = 14
WINDOW = 96              # 24s = 96 x 15m


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _read_bars(path: str) -> list[tuple] | None:
    if not os.path.exists(path):
        return None
    out = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out.append((int(row["ts"]), float(row["open"]),
                        float(row["high"]), float(row["low"]),
                        float(row["close"])))
    out.sort(key=lambda b: b[0])
    return out


def _read_oi(path: str) -> dict[int, float] | None:
    if not os.path.exists(path):
        return None
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out[int(row["ts"])] = float(row["open_interest"])
    return out


def _atr_series(bars: list[tuple], n: int = ATR_N) -> list[float | None]:
    """Bar-kapanisi itibariyla basit-ortalama TR(n); yetersizse None."""
    trs: list[float] = []
    out: list[float | None] = []
    for i, (_, _, h, lo, c) in enumerate(bars):
        if i == 0:
            trs.append(h - lo)
        else:
            pc = bars[i - 1][4]
            trs.append(max(h - lo, abs(h - pc), abs(lo - pc)))
        out.append(sum(trs[-n:]) / n if len(trs) >= n else None)
    return out


def run_pair(bars15: list[tuple], bars4h: list[tuple],
             oi: dict[int, float]) -> list[dict]:
    """Tek paritenin donmus-kural taramasi -> islem listesi."""
    if len(bars15) < WINDOW + 2 or len(bars4h) < ATR_N + 1:
        return []
    ts15 = [b[0] for b in bars15]
    idx15 = {t: i for i, t in enumerate(ts15)}
    atr15 = _atr_series(bars15)
    atr4 = _atr_series(bars4h)
    ts4 = [b[0] for b in bars4h]

    def atr4_at(t: int) -> float | None:
        # t aninda KAPANMIS son 4H barin ATR'si (bar kapanisi ts+4H)
        j = bisect.bisect_right(ts4, t - H4) - 1
        return atr4[j] if j >= 0 else None

    trades: list[dict] = []
    used_clusters: set[str] = set()
    open_until = -1                      # acik pozisyon varken tarama yok
    n = len(bars15)
    for i in range(WINDOW, n - 1):
        if i <= open_until:
            continue
        t, _, _, _, c = bars15[i]
        prev_i = idx15.get(t - DAY)
        if prev_i is None:
            continue
        oi_now = oi.get((t // 3_600_000) * 3_600_000)
        oi_prev = oi.get((t // 3_600_000) * 3_600_000 - DAY)
        if not oi_now or not oi_prev:
            continue
        if oi_now / oi_prev - 1.0 > OI_DROP:
            continue
        a4 = atr4_at(t)
        if a4 is None or a4 <= 0:
            continue
        if c > bars15[prev_i][4] - PRICE_DROP_ATR * a4:
            continue                                       # dusus yetersiz
        if c <= bars15[i - 1][4]:
            continue                                       # stabilizasyon yok
        cluster = f"L{t // H4}"
        if cluster in used_clusters:
            continue
        a15 = atr15[i]
        if a15 is None or a15 <= 0:
            continue
        window_low = min(b[3] for b in bars15[i - WINDOW + 1: i + 1])
        stop = window_low - STOP_PAD_ATR * a15
        entry = c
        risk = entry - stop
        if risk <= 0:
            continue
        tp = entry + TP_RISK * risk
        # ---- ileri simulasyon (challengers._evaluate_one kurali) ----
        outcome, r, hold = None, None, 0
        for j in range(i + 1, n):
            _, _, h, lo, cl = bars15[j]
            hold = j - i
            hit_stop, hit_tp = lo <= stop, h >= tp
            if hit_stop and hit_tp:
                outcome, r = "LOSS", -1.0
                break
            if hit_stop:
                outcome, r = "LOSS", -1.0
                break
            if hit_tp:
                outcome, r = "WIN", round((tp - entry) / risk, 2)
                break
            if hold >= TIMEOUT_BARS:
                outcome, r = "EXPIRED", round((cl - entry) / risk, 2)
                break
        if outcome is None:
            continue                                       # arsiv bitti
        stop_frac = risk / entry
        fee = 2 * TAKER_FEE / stop_frac
        slip = (STOP_SLIP / stop_frac) if outcome == "LOSS" else 0.0
        funding = FUNDING_8H * (hold * 0.25 / 8.0) / stop_frac
        trades.append({"cluster": cluster, "outcome": outcome,
                       "gross": r, "net": r - fee - slip - funding,
                       "hold": hold})
        used_clusters.add(cluster)
        open_until = i + hold
    return trades


def run_backtest(data_dir: str, oi_dir: str) -> dict:
    pairs = sorted({fn[:-len("_15.csv")] for fn in os.listdir(data_dir)
                    if fn.endswith("_15.csv")})
    if not pairs:
        return {"error": "kline arsivi bos"}
    clusters: dict[str, list[float]] = {}
    stats = {"pairs_done": 0, "pairs_no_oi": 0, "pairs_no_kline": 0,
             "trades": 0, "wins": 0, "losses": 0, "expired": 0,
             "gross_sum": 0.0, "net_sum": 0.0}
    span = [None, None]
    for pair in pairs:
        b15 = _read_bars(os.path.join(data_dir, f"{pair}_15.csv"))
        b4 = _read_bars(os.path.join(data_dir, f"{pair}_240.csv"))
        oi = _read_oi(os.path.join(oi_dir, f"{pair}_oi_1h.csv"))
        if b15 is None or b4 is None:
            stats["pairs_no_kline"] += 1
            continue
        if oi is None or not oi:
            stats["pairs_no_oi"] += 1
            continue
        stats["pairs_done"] += 1
        if span[0] is None or b15[0][0] < span[0]:
            span[0] = b15[0][0]
        if span[1] is None or b15[-1][0] > span[1]:
            span[1] = b15[-1][0]
        for tr in run_pair(b15, b4, oi):
            stats["trades"] += 1
            key = {"WIN": "wins", "LOSS": "losses",
                   "EXPIRED": "expired"}[tr["outcome"]]
            stats[key] += 1
            stats["gross_sum"] += tr["gross"]
            stats["net_sum"] += tr["net"]
            clusters.setdefault(tr["cluster"], []).append(tr["net"])

    boot = measurement.cluster_bootstrap(clusters)
    ci = ([boot["ci_low"], boot["ci_high"]]
          if boot and boot.get("ci_low") is not None else None)
    n_cl = len(clusters)
    net = round(stats["net_sum"], 2)
    if ci and ci[1] < 0:
        verdict = "ELENDI (kume-CI ust siniri < 0)"
    elif ci and ci[0] >= 0 and net > 0 and n_cl >= 50:
        verdict = "ADAY (kume-CI alt >= 0, net R > 0, kume >= 50)"
    elif n_cl < 50:
        verdict = f"YETERSIZ VERI (kume {n_cl} < 50) - budama zayif"
    else:
        verdict = "BELIRSIZ (arasi) - canliya aday, 'umut vaat etti' DENMEZ"
    return {
        "params": {"oi_drop": OI_DROP, "price_drop_atr": PRICE_DROP_ATR,
                   "stop_pad_atr": STOP_PAD_ATR, "tp_risk": TP_RISK,
                   "timeout_bars": TIMEOUT_BARS, "window_bars": WINDOW},
        "data_range": ([_iso(span[0]), _iso(span[1])] if span[0] else None),
        **{k: (round(v, 2) if isinstance(v, float) else v)
           for k, v in stats.items()},
        "clusters": n_cl, "ci": ci,
        "e_net": (boot["e_net"] if boot else None),
        "verdict": verdict,
        "note": ("Tek atis budama. HUKUM DEGIL - kesin soz canli golge "
                 "yaristan. Kaskad ortaminda kagit-dolus iyimser olabilir; "
                 "OI arsiv derinligi API kisitina tabi."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, help="kline arsivi")
    ap.add_argument("--oi", required=True, help="OI arsivi")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    rep = run_backtest(args.data, args.oi)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=2)
    print("\n=== P1 OI-FLUSH BACKTEST RAPORU (tek atis budama) ===")
    if rep.get("error"):
        print("HATA:", rep["error"])
        return 2
    print(f"parite: {rep['pairs_done']} islendi | OI'siz: "
          f"{rep['pairs_no_oi']} | mumsuz: {rep['pairs_no_kline']}")
    print(f"veri: {rep['data_range']}")
    print(f"islem: {rep['trades']} ({rep['wins']}W/{rep['losses']}L/"
          f"{rep['expired']}E) | kume: {rep['clusters']}")
    print(f"brut R: {rep['gross_sum']} | net R: {rep['net_sum']}")
    print(f"kume-CI: {rep['ci']} | E_net: {rep['e_net']}")
    print(f"HUKUM: {rep['verdict']}")
    print(f"NOT: {rep['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
