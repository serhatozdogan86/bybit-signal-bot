"""52w-HIGH ZIRVE YAKINLIGI — gecmis veri budamasi (ON-KAYIT: docs/ideas.md
2026-08-16).

KURALLAR (donmus):
  Karar her Pazartesi 00:00 UTC, son KAPANMIS gunluk mumla (Pazar kapanisi).
  Yakinlik = o kapanis / son 365 gunun (parite yeniyse listing'den beri,
  EN AZ 90 gun) en yuksek GUNLUK kapanisi. Secim: yakinlik >= 0.90 VE o
  haftanin kesitinde en ust %10 (iki kosul birden). Yalniz LONG.
  Giris karar anindaki kapanis; stop = giris - 2xATR(14,gunluk); cikis
  7 gun sonra kapanis (zaman) veya stop (once gelen). Hedef YOK.
  Kume = formasyon haftasi (haftanin tum girisleri TEK kume).
  Maliyet canli model. TEK ATIS — tarama yok.

VERI: --data klasorunde PAIR_D.csv (tools/download_backtest_data.py
  --intervals D --days 750 ciktisi).

KULLANIM (VM):
  cd ~/bybit-signal-bot-audit && git pull
  .venv/bin/python tools/backtest_52w.py --data /home/ubuntu/daily-data
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import measurement                          # noqa: E402
from app.services.signal_tracker import (FUNDING_8H, STOP_SLIP,  # noqa: E402
                                         TAKER_FEE)
from tools.backtest_oi_flush import _atr_series, _read_bars   # noqa: E402

DAY = 86_400_000
ANCHOR_DAYS = 365        # zirve penceresi
MIN_HISTORY = 90         # yeni paritede asgari gecmis (gun)
PROXIMITY = 0.90         # yakinlik tabani
DECILE = 0.10            # kesit ust dilimi
STOP_ATR = 2.0           # ATR(14, gunluk) kati
HOLD_DAYS = 7
ATR_N = 14


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d")


def _is_monday(ts: int) -> bool:
    return (ts // DAY + 3) % 7 == 0        # 1970-01-01 Persembe


def run_backtest(data_dir: str) -> dict:
    pairs: dict[str, list[tuple]] = {}
    for fn in sorted(os.listdir(data_dir)):
        if fn.endswith("_D.csv"):
            bars = _read_bars(os.path.join(data_dir, fn))
            if bars:
                pairs[fn[:-len("_D.csv")]] = bars
    if not pairs:
        return {"error": "gunluk arsiv bos (PAIR_D.csv yok)"}

    idx = {p: {b[0]: i for i, b in enumerate(bars)}
           for p, bars in pairs.items()}
    atrs = {p: _atr_series(bars) for p, bars in pairs.items()}
    all_ts = sorted({t for bars in pairs.values() for (t, *_ ) in bars})
    mondays = [t for t in all_ts
               if _is_monday(t) and t + (HOLD_DAYS - 1) * DAY <= all_ts[-1]]

    clusters: dict[str, list[float]] = {}
    stats = {"weeks": 0, "weeks_with_entry": 0, "trades": 0, "wins": 0,
             "losses": 0, "time_exits": 0, "gross_sum": 0.0, "net_sum": 0.0,
             "skipped_short_history": 0}
    for m in mondays:
        # kesit: her paritenin Pazar-kapanisli yakinligi
        cross: list[tuple[float, str, int]] = []
        for p, bars in pairs.items():
            i_sun = idx[p].get(m - DAY)
            if i_sun is None:
                continue
            if i_sun + 1 < MIN_HISTORY:
                stats["skipped_short_history"] += 1
                continue
            lo = max(0, i_sun + 1 - ANCHOR_DAYS)
            high_anchor = max(b[4] for b in bars[lo: i_sun + 1])
            if high_anchor <= 0:
                continue
            cross.append((bars[i_sun][4] / high_anchor, p, i_sun))
        if not cross:
            continue
        stats["weeks"] += 1
        cross.sort(reverse=True)
        k = max(1, round(DECILE * len(cross)))
        selected = [(prox, p, i) for prox, p, i in cross[:k]
                    if prox >= PROXIMITY]
        if not selected:
            continue
        stats["weeks_with_entry"] += 1
        for prox, p, i_sun in selected:
            bars = pairs[p]
            entry = bars[i_sun][4]
            atr = atrs[p][i_sun]
            if atr is None or atr <= 0:
                continue
            stop = entry - STOP_ATR * atr
            risk = entry - stop
            if risk <= 0 or i_sun + HOLD_DAYS >= len(bars):
                continue
            outcome, r, hold_d = None, None, 0
            for d in range(1, HOLD_DAYS + 1):
                b = bars[i_sun + d]
                hold_d = d
                if b[3] <= stop:
                    outcome, r = "LOSS", -1.0
                    break
                if d == HOLD_DAYS:
                    outcome, r = "TIME", round((b[4] - entry) / risk, 2)
            if outcome is None:
                continue
            stop_frac = risk / entry
            fee = 2 * TAKER_FEE / stop_frac
            slip = (STOP_SLIP / stop_frac) if outcome == "LOSS" else 0.0
            funding = FUNDING_8H * (hold_d * 24 / 8.0) / stop_frac
            net = r - fee - slip - funding
            stats["trades"] += 1
            # wins: pozitif zaman-cikisi; losses: stop; time_exits: <=0 zaman
            stats["wins" if (outcome == "TIME" and r > 0) else
                  ("losses" if outcome == "LOSS" else "time_exits")] += 1
            stats["gross_sum"] += r
            stats["net_sum"] += net
            clusters.setdefault(f"W{m // DAY}", []).append(net)

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
        "params": {"anchor_days": ANCHOR_DAYS, "min_history": MIN_HISTORY,
                   "proximity": PROXIMITY, "decile": DECILE,
                   "stop_atr": STOP_ATR, "hold_days": HOLD_DAYS},
        "pairs_loaded": len(pairs),
        "data_range": [_iso(all_ts[0]), _iso(all_ts[-1])],
        **{k: (round(v, 2) if isinstance(v, float) else v)
           for k, v in stats.items()},
        "clusters": n_cl, "ci": ci,
        "e_net": (boot["e_net"] if boot else None),
        "verdict": verdict,
        "note": ("Tek atis budama, HUKUM DEGIL. Gunluk cozunurluk: stop "
                 "kontrolu gun dusugunden (yol bilinmez, muhafazakar). "
                 "Akademik evren binlerce coin; 150 likit perp'te kenar "
                 "incelmis olabilir."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, help="gunluk kline klasoru")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    rep = run_backtest(args.data)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=2)
    print("\n=== 52w-HIGH BACKTEST RAPORU (tek atis budama) ===")
    if rep.get("error"):
        print("HATA:", rep["error"])
        return 2
    print(f"parite: {rep['pairs_loaded']} | veri: {rep['data_range'][0]} -> "
          f"{rep['data_range'][1]}")
    print(f"hafta: {rep['weeks']} (girisli: {rep['weeks_with_entry']}) | "
          f"islem: {rep['trades']} ({rep['wins']}W/{rep['losses']}L) | "
          f"kisa-gecmis atlanan: {rep['skipped_short_history']}")
    print(f"brut R: {rep['gross_sum']} | net R: {rep['net_sum']} | "
          f"kume: {rep['clusters']}")
    print(f"kume-CI: {rep['ci']} | E_net: {rep['e_net']}")
    print(f"HUKUM: {rep['verdict']}")
    print(f"NOT: {rep['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
