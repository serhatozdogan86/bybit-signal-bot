"""P4 OI-ONAYLI KIRILIM FILTRESI — eslesmis kohort backtesti (ON-KAYIT:
docs/ideas.md 2026-08-16).

Hipotez: kirilim aninda OI artiyorsa hareket "yeni para" (devam olasi);
artmiyorsa sahte kirilima yatkin. Yeni motor DEGIL — S2-Donchian kuralinin
birebir kopyasi uretilir, tek fark tetik anindaki dOI(24s) kohort etiketi:
  >= +%5 -> OI-ARTISLI | < +%5 -> OI-ARTISSIZ | OI yok -> atla (sayilir)
Iki kohort ayni kural, ayni maliyet, ayni kume tanimiyla YAN YANA olculur;
bulgu iki kohortun FARKIDIR.

Hukum kurali (onceden ilan): UMUT = artisli E_net > artissiz E_net VE
artisli kume-CI alt >= 0. ELENDI = artisli E_net <= artissiz E_net VEYA
artisli kume-CI ust < 0. Arasi: BELIRSIZ. TEK ATIS — tarama yok.

KULLANIM (VM):
  cd ~/bybit-signal-bot-audit && git pull
  .venv/bin/python tools/backtest_oi_breakout.py \\
      --data /home/ubuntu/backtest-data --oi /home/ubuntu/oi-data
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import measurement                          # noqa: E402
from app.services.signal_tracker import (FUNDING_8H, STOP_SLIP,  # noqa: E402
                                         TAKER_FEE)
from tools.backtest_oi_flush import (_atr_series, _read_bars,  # noqa: E402
                                     _read_oi)

M15 = 900_000
H4 = 14_400_000
DAY = 86_400_000
DONCHIAN_N = 20          # S2 ile ayni (challengers.DONCHIAN_N)
STOP_ATR = 2.0           # S2 ile ayni (TREND_STOP_ATR)
TP_ATR = 6.0             # S2 ile ayni (TREND_TP_ATR)
TIMEOUT_BARS = 192       # S2 ile ayni (TREND_TIMEOUT)
OI_RISE = 0.05           # kohort esigi: dOI(24s) >= +%5
ATR_N = 14


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def run_pair(bars15: list[tuple], bars4h: list[tuple],
             oi: dict[int, float]) -> tuple[list[dict], int]:
    """S2-kurali kirilimlar + kohort etiketi. Doner: (islemler, oi_yok)."""
    if len(bars15) < 2 or len(bars4h) < DONCHIAN_N + ATR_N + 2:
        return [], 0
    atr4 = _atr_series(bars4h)
    ts4 = [b[0] for b in bars4h]
    n = len(bars15)
    trades: list[dict] = []
    used: set[str] = set()
    open_until = -1
    skipped_no_oi = 0
    for i in range(1, n - 1):
        if i <= open_until:
            continue
        t, _, _, _, c = bars15[i]
        c_prev = bars15[i - 1][4]
        # t aninda KAPANMIS son 4H bar: kanal + ATR oradan
        j = bisect.bisect_right(ts4, t - H4) - 1
        if j < DONCHIAN_N:
            continue
        window = bars4h[j - DONCHIAN_N + 1: j + 1]
        dh = max(b[2] for b in window)
        dl = min(b[3] for b in window)
        a4 = atr4[j]
        if a4 is None or a4 <= 0:
            continue
        if c_prev <= dh < c:
            direction = "LONG"
            stop, tp = c - STOP_ATR * a4, c + TP_ATR * a4
        elif c_prev >= dl > c:
            direction = "SHORT"
            stop, tp = c + STOP_ATR * a4, c - TP_ATR * a4
        else:
            continue
        cluster = f"{direction[0]}{t // H4}"
        if cluster in used:
            continue
        oi_now = oi.get((t // 3_600_000) * 3_600_000)
        oi_prev = oi.get((t // 3_600_000) * 3_600_000 - DAY)
        if not oi_now or not oi_prev:
            skipped_no_oi += 1
            continue
        cohort = ("OI_ARTISLI" if oi_now / oi_prev - 1.0 >= OI_RISE
                  else "OI_ARTISSIZ")
        entry = c
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        outcome, r, hold = None, None, 0
        is_long = direction == "LONG"
        for k in range(i + 1, n):
            _, _, h, lo, cl = bars15[k]
            hold = k - i
            hit_stop = (lo <= stop) if is_long else (h >= stop)
            hit_tp = (h >= tp) if is_long else (lo <= tp)
            if hit_stop and hit_tp:
                outcome, r = "LOSS", -1.0
                break
            if hit_stop:
                outcome, r = "LOSS", -1.0
                break
            if hit_tp:
                outcome, r = "WIN", round(abs(tp - entry) / risk, 2)
                break
            if hold >= TIMEOUT_BARS:
                pnl = (cl - entry) if is_long else (entry - cl)
                outcome, r = "EXPIRED", round(pnl / risk, 2)
                break
        if outcome is None:
            continue
        stop_frac = risk / entry
        fee = 2 * TAKER_FEE / stop_frac
        slip = (STOP_SLIP / stop_frac) if outcome == "LOSS" else 0.0
        funding = FUNDING_8H * (hold * 0.25 / 8.0) / stop_frac
        trades.append({"cohort": cohort, "cluster": cluster,
                       "outcome": outcome, "gross": r,
                       "net": r - fee - slip - funding, "hold": hold})
        used.add(cluster)
        open_until = i + hold
    return trades, skipped_no_oi


def run_backtest(data_dir: str, oi_dir: str) -> dict:
    pairs = sorted({fn[:-len("_15.csv")] for fn in os.listdir(data_dir)
                    if fn.endswith("_15.csv")})
    if not pairs:
        return {"error": "kline arsivi bos"}
    cohorts: dict[str, dict] = {
        k: {"clusters": {}, "trades": 0, "wins": 0, "losses": 0,
            "expired": 0, "gross": 0.0, "net": 0.0}
        for k in ("OI_ARTISLI", "OI_ARTISSIZ")}
    meta = {"pairs_done": 0, "pairs_no_oi": 0, "skipped_no_oi_at_trigger": 0}
    span = [None, None]
    for pair in pairs:
        b15 = _read_bars(os.path.join(data_dir, f"{pair}_15.csv"))
        b4 = _read_bars(os.path.join(data_dir, f"{pair}_240.csv"))
        oi = _read_oi(os.path.join(oi_dir, f"{pair}_oi_1h.csv"))
        if b15 is None or b4 is None or oi is None or not oi:
            meta["pairs_no_oi"] += 1
            continue
        meta["pairs_done"] += 1
        if span[0] is None or b15[0][0] < span[0]:
            span[0] = b15[0][0]
        if span[1] is None or b15[-1][0] > span[1]:
            span[1] = b15[-1][0]
        trades, skipped = run_pair(b15, b4, oi)
        meta["skipped_no_oi_at_trigger"] += skipped
        for tr in trades:
            co = cohorts[tr["cohort"]]
            co["trades"] += 1
            co[{"WIN": "wins", "LOSS": "losses",
                "EXPIRED": "expired"}[tr["outcome"]]] += 1
            co["gross"] += tr["gross"]
            co["net"] += tr["net"]
            co["clusters"].setdefault(tr["cluster"], []).append(tr["net"])

    out_cohorts = {}
    for name, co in cohorts.items():
        boot = measurement.cluster_bootstrap(co["clusters"])
        out_cohorts[name] = {
            "trades": co["trades"], "wins": co["wins"],
            "losses": co["losses"], "expired": co["expired"],
            "gross_r": round(co["gross"], 2), "net_r": round(co["net"], 2),
            "clusters": len(co["clusters"]),
            "ci": ([boot["ci_low"], boot["ci_high"]]
                   if boot and boot.get("ci_low") is not None else None),
            "e_net": (boot["e_net"] if boot else None),
        }
    a, b = out_cohorts["OI_ARTISLI"], out_cohorts["OI_ARTISSIZ"]
    if a["e_net"] is None or b["e_net"] is None:
        verdict = "YETERSIZ VERI (bir kohortta CI hesaplanamadi)"
    elif a["e_net"] <= b["e_net"] or (a["ci"] and a["ci"][1] < 0):
        verdict = "FILTRE ELENDI (OI teyidi katki vermiyor veya CI ust < 0)"
    elif a["ci"] and a["ci"][0] >= 0:
        verdict = "FILTRE UMUT VAAT EDIYOR (artisli E_net ustun VE CI alt >= 0)"
    else:
        verdict = "BELIRSIZ (arasi)"
    return {
        "params": {"donchian_n": DONCHIAN_N, "stop_atr": STOP_ATR,
                   "tp_atr": TP_ATR, "timeout_bars": TIMEOUT_BARS,
                   "oi_rise": OI_RISE},
        "data_range": ([_iso(span[0]), _iso(span[1])] if span[0] else None),
        **meta, "cohorts": out_cohorts, "verdict": verdict,
        "note": ("Eslesmis kohort karsilastirmasi; bulgu iki kohortun "
                 "FARKIDIR. Tek atis budama, HUKUM DEGIL."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True)
    ap.add_argument("--oi", required=True)
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    rep = run_backtest(args.data, args.oi)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=2)
    print("\n=== P4 OI-ONAYLI KIRILIM RAPORU (eslesmis kohort) ===")
    if rep.get("error"):
        print("HATA:", rep["error"])
        return 2
    print(f"parite: {rep['pairs_done']} islendi | verisiz: "
          f"{rep['pairs_no_oi']} | tetikte-OI-yok: "
          f"{rep['skipped_no_oi_at_trigger']}")
    print(f"veri: {rep['data_range']}")
    for name, co in rep["cohorts"].items():
        print(f"{name}: islem {co['trades']} ({co['wins']}W/{co['losses']}L/"
              f"{co['expired']}E) | kume {co['clusters']} | net R "
              f"{co['net_r']} | E_net {co['e_net']} | CI {co['ci']}")
    print(f"HUKUM: {rep['verdict']}")
    print(f"NOT: {rep['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
