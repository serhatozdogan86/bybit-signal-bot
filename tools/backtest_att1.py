"""S-ATT1 WIKIPEDIA DIKKAT SOKU - tek atis backtest (ON-KAYIT:
docs/ideas.md 2026-08-16 + uygulama eki 2026-08-17).

KURALLAR (dondurulmus - burada DEGISTIRILEMEZ):
  - Sinyal (gun D): z-skoru >= 2 - x = log(1+goruntuleme), taban onceki
    90 takvim gunu (en az 81 gun veri; populasyon sapmasi; sapma 0 ->
    sinyal yok) VE 24s getiri (D son 4H kapanisi / D-1 son 4H kapanisi
    - 1) 0 ile +0.25 arasi -> LONG.
  - T+1: giris D+1 gununun ILK 4H mumunun ACILISI (gun verisi ancak gun
    bitince tamdir).
  - Stop: giris - 2 x ATR(14, 4H; giristen onceki son kapanmis mum).
    Zaman-stopu 18 x 4H bar (3 gun), kapanistan. Hedef yok.
  - Yeniden-giris yasagi: sembol basina giris gununden 7 takvim gunu.
  - Kume = SINYAL takvim gunu (ayni gun tum semboller TEK kume).
  - Maliyet v0: 2xtaker + stop cikisinda slip + funding x tutus;
    R paydasi stop mesafesi. Hukum merdiveni S5 ile ayni (tek atis).

KULLANIM (VM):
  cd ~/bybit-signal-bot-audit && git pull
  .venv/bin/python tools/backtest_att1.py --data /home/ubuntu/backtest-data
  (once tools/download_backtest_data.py 4H CSV'leri ve
   tools/download_wiki_views.py wiki_views.csv uretmis olmali)
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import measurement                          # noqa: E402
from app.services.signal_tracker import (                     # noqa: E402
    FUNDING_8H, STOP_SLIP, TAKER_FEE)

STEP_MS = 4 * 60 * 60 * 1000
DAY_MS = 86_400_000
ATR_N = 14
Z_MIN = 2.0
BASE_DAYS = 90
MIN_BASE = 81
R24_MAX = 0.25
STOP_ATR = 2.0
HOLD_BARS = 18                 # 3 gun x 6 mum
BAN_DAYS = 7
_EPOCH_ORD = date(1970, 1, 1).toordinal()


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def day_to_ms(day_ord: int) -> int:
    return (day_ord - _EPOCH_ORD) * DAY_MS


def load_pairs(data_dir: str, interval: str = "240") -> dict[str, dict]:
    out: dict[str, dict] = {}
    suffix = f"_{interval}.csv"
    for fn in sorted(os.listdir(data_dir)):
        if not fn.endswith(suffix):
            continue
        pair = fn[: -len(suffix)]
        bars: dict[int, tuple] = {}
        with open(os.path.join(data_dir, fn), newline="") as f:
            for row in csv.DictReader(f):
                bars[int(row["ts"])] = (float(row["open"]), float(row["high"]),
                                        float(row["low"]), float(row["close"]))
        if bars:
            out[pair] = bars
    return out


def load_views(path: str) -> dict[str, dict[int, int]]:
    """wiki_views.csv -> {sembol: {gun_ordinali: goruntuleme}}."""
    out: dict[str, dict[int, int]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                d = datetime.strptime(row["date"], "%Y%m%d").date().toordinal()
                out.setdefault(row["symbol"], {})[d] = int(row["views"])
            except (KeyError, ValueError):
                continue
    return out


def zscore_day(views: dict[int, int], day_ord: int,
               base_days: int = BASE_DAYS, min_base: int = MIN_BASE
               ) -> float | None:
    """log(1+v) z-skoru: taban = onceki base_days takvim gunu."""
    if day_ord not in views:
        return None
    xs = [math.log1p(views[d])
          for d in range(day_ord - base_days, day_ord) if d in views]
    if len(xs) < min_base:
        return None
    mu = sum(xs) / len(xs)
    var = sum((x - mu) ** 2 for x in xs) / len(xs)
    sd = var ** 0.5
    # sifir-sapma muhafizi: birebir sabit seride kayan-nokta artigi
    # (~1e-14) sd'yi "sifirdan buyuk" gosterip cop z uretir; log-goruntuleme
    # olceginde (O(10)) 1e-9 alti sapma fiilen sifirdir -> sinyal yok
    if sd < 1e-9:
        return None
    return (math.log1p(views[day_ord]) - mu) / sd


def atr_abs(bars: dict[int, tuple], t: int, n: int = ATR_N) -> float | None:
    """ATR(n) mutlak - t dahil geriye n+1 KESINTISIZ 4H mum ister."""
    seq = []
    for k in range(n + 1):
        b = bars.get(t - (n - k) * STEP_MS)
        if b is None:
            return None
        seq.append(b)
    trs = []
    for i in range(1, len(seq)):
        _, h, lo, _c = seq[i]
        prev_c = seq[i - 1][3]
        trs.append(max(h - lo, abs(h - prev_c), abs(lo - prev_c)))
    return (sum(trs) / len(trs)) if trs else None


def r24(bars: dict[int, tuple], day_ord: int) -> float | None:
    """Gun D son 4H kapanisi / (D-1) son 4H kapanisi - 1."""
    last_d = bars.get(day_to_ms(day_ord) + 5 * STEP_MS)
    last_p = bars.get(day_to_ms(day_ord - 1) + 5 * STEP_MS)
    if last_d is None or last_p is None or last_p[3] <= 0:
        return None
    return last_d[3] / last_p[3] - 1.0


def run_backtest(pairs: dict[str, dict], views: dict[str, dict[int, int]]
                 ) -> dict:
    """Saf cekirdek - dosya I/O yok (test edilebilirlik)."""
    syms = sorted(set(pairs) & set(views))
    if not syms:
        return {"error": "kesisen sembol yok", "pairs": len(pairs),
                "wiki": len(views)}
    clusters: dict[str, list[float]] = {}
    gross_sum = net_sum = 0.0
    signals = entries = wins = losses = expired = 0
    skipped_ban = skipped_data = 0
    per_sym: dict[str, int] = {}
    ban_until: dict[str, int] = {}
    t_min = min(t for b in pairs.values() for t in b)
    t_max = max(t for b in pairs.values() for t in b)

    for sym in syms:
        bars = pairs[sym]
        v = views[sym]
        for day_ord in sorted(v):
            z = zscore_day(v, day_ord)
            if z is None or z < Z_MIN:
                continue
            ret = r24(bars, day_ord)
            if ret is None or not (0.0 < ret <= R24_MAX):
                continue
            signals += 1
            if day_ord + 1 < ban_until.get(sym, 0):
                skipped_ban += 1
                continue
            entry_ts = day_to_ms(day_ord + 1)
            eb = bars.get(entry_ts)
            a = atr_abs(bars, entry_ts - STEP_MS)
            if eb is None or a is None or a <= 0:
                skipped_data += 1
                continue
            entry = eb[0]                      # D+1 ilk mumun ACILISI
            stop = entry - STOP_ATR * a
            risk = entry - stop
            if risk <= 0 or entry <= 0:
                skipped_data += 1
                continue
            # degerlendirme: giris mumu DAHIL (giris acilista) 18 bar
            outcome = None
            for k in range(HOLD_BARS):
                b = bars.get(entry_ts + k * STEP_MS)
                if b is None:
                    break                      # veri boslugu
                if b[2] <= stop:
                    outcome = ("LOSS", -1.0, k + 1, True)
                    break
                if k == HOLD_BARS - 1:
                    outcome = ("EXPIRED",
                               round((b[3] - entry) / risk, 4), k + 1, False)
            if outcome is None:
                skipped_data += 1
                continue
            kind, gross, hold, stop_exit = outcome
            stop_frac = risk / entry
            cost = (2 * TAKER_FEE + (STOP_SLIP if stop_exit else 0.0)
                    + FUNDING_8H * (hold * 4 / 8.0)) / stop_frac
            net = gross - cost
            entries += 1
            per_sym[sym] = per_sym.get(sym, 0) + 1
            wins += 1 if kind == "EXPIRED" and gross > 0 else 0
            losses += 1 if kind == "LOSS" else 0
            expired += 1 if kind == "EXPIRED" else 0
            gross_sum += gross
            net_sum += net
            clusters.setdefault(f"L{day_ord}", []).append(net)
            ban_until[sym] = (day_ord + 1) + BAN_DAYS

    boot = measurement.cluster_bootstrap(clusters)
    ci = ([boot["ci_low"], boot["ci_high"]]
          if boot and boot.get("ci_low") is not None else None)
    n_cl = len(clusters)
    if ci and ci[1] < 0:
        verdict = "ELENDI (kume-CI ust siniri < 0)"
    elif ci and ci[0] >= 0 and net_sum > 0 and n_cl >= 50:
        verdict = "ADAY (kume-CI alt >= 0, net R > 0, kume >= 50)"
    elif n_cl < 50:
        verdict = f"YETERSIZ VERI (kume {n_cl} < 50) - budama zayif"
    else:
        verdict = "BELIRSIZ (arasi) - canliya aday, 'umut vaat etti' DENMEZ"

    top = sorted(per_sym.items(), key=lambda kv: -kv[1])[:10]
    return {
        "symbols": len(syms),
        "data_range": [_iso(t_min), _iso(t_max)],
        "signals": signals, "entries": entries,
        "skipped_ban": skipped_ban, "skipped_data": skipped_data,
        "losses": losses, "time_exits": expired, "time_exit_wins": wins,
        "clusters": n_cl,
        "gross_r_sum": round(gross_sum, 2), "net_r_sum": round(net_sum, 2),
        "ci": ci, "e_net": (boot["e_net"] if boot else None),
        "top_symbols": top,
        "verdict": verdict,
        "note": ("Tek atis budama - HUKUM DEGIL. Bilinen riskler (on-kayit): "
                 "ters nedensellik, T+1 gecikme (giris D+1 acilisi), "
                 "buyuk-coin yanliligi, 90 gun tek rejim olabilir."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True,
                    help="4H CSV + wiki_views.csv klasoru")
    ap.add_argument("--wiki", default="",
                    help="wiki_views.csv yolu (varsayilan: --data icinde)")
    ap.add_argument("--json", default="", help="raporu bu dosyaya da yaz")
    args = ap.parse_args()

    wiki_path = args.wiki or os.path.join(args.data, "wiki_views.csv")
    if not os.path.exists(wiki_path):
        print("HATA: wiki_views.csv yok:", wiki_path)
        return 2
    rep = run_backtest(load_pairs(args.data), load_views(wiki_path))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)

    print("\n=== S-ATT1 BACKTEST RAPORU (tek atis budama) ===")
    if rep.get("error"):
        print("HATA:", rep["error"], "| parite:", rep.get("pairs"),
              "| wiki:", rep.get("wiki"))
        return 2
    print(f"sembol: {rep['symbols']} | veri: {rep['data_range'][0]} -> "
          f"{rep['data_range'][1]}")
    print(f"sinyal: {rep['signals']} | giris: {rep['entries']} "
          f"(yasak atlanan: {rep['skipped_ban']}, veri eksik: "
          f"{rep['skipped_data']})")
    print(f"stop: {rep['losses']} | zaman-cikisi: {rep['time_exits']} "
          f"(karda: {rep['time_exit_wins']})")
    print(f"kume: {rep['clusters']} | brut R: {rep['gross_r_sum']} | "
          f"net R: {rep['net_r_sum']}")
    print(f"kume-CI: {rep['ci']} | E_net: {rep['e_net']}")
    print(f"en cok giris: {rep['top_symbols']}")
    print(f"HUKUM: {rep['verdict']}")
    print(f"NOT: {rep['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
