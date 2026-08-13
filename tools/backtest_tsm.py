"""TSM ZAMAN-SERİSİ MOMENTUM — geçmiş veri budaması (ÖN-KAYIT: docs/ideas.md 2026-08-13).

S5'in TEMİZ KONTROL KOLU: S5 ile birebir aynı boru hattı (14g bakış,
48s tutuş, ATR-normalize R, aynı maliyet, küme=yön+denge), TEK fark
sinyalde — S5 evreni KIYASLAR (kesitsel sıralama); TSM her pariteye
KENDİ geçmişine göre bakar (mutlak işaret). Uygun evrendeki HER parite
işaretine göre pozisyonlanır (decile yok).

load_pairs/atr_frac S5 aracından yeniden kullanılır (tek kaynak).
Parametre taraması YOK — CLI sabit parametrelerle çalışır.

KULLANIM (VM):
  cd ~/bybit-signal-bot-audit && git pull
  .venv/bin/python tools/backtest_tsm.py --data /home/ubuntu/backtest-data
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import measurement                          # noqa: E402
from app.services.signal_tracker import FUNDING_8H, TAKER_FEE  # noqa: E402
from tools.backtest_s5 import (LOOKBACK, HOLD, ATR_N, STEP_MS,  # noqa: E402
                               atr_frac, load_pairs, _iso)


def run_backtest(data_dir: str, lookback: int = LOOKBACK, hold: int = HOLD,
                 atr_n: int = ATR_N, step: int = STEP_MS) -> dict:
    pairs = load_pairs(data_dir)
    if not pairs:
        return {"error": "veri yok", "pairs": 0}
    all_ts = sorted({t for bars in pairs.values() for t in bars})
    funding_periods = hold * (step / 1000 / 3600) / 8.0
    cost_pct = 2 * TAKER_FEE + FUNDING_8H * funding_periods

    clusters: dict[str, list[float]] = {}
    gross_sum = net_sum = 0.0
    n_long = n_short = 0
    rebalances = 0
    sizes: list[int] = []

    start_i = 0
    while start_i < len(all_ts) and all_ts[start_i] < all_ts[0] + lookback * step:
        start_i += 1

    i = start_i
    while i < len(all_ts):
        t = all_ts[i]
        lb_ts, ex_ts = t - lookback * step, t + hold * step
        placed = 0
        for pair, bars in pairs.items():
            b_t, b_lb, b_ex = bars.get(t), bars.get(lb_ts), bars.get(ex_ts)
            if b_t is None or b_lb is None or b_ex is None or b_lb[3] <= 0:
                continue
            af = atr_frac(bars, t, step, atr_n)
            if af is None or af <= 0:
                continue
            ret = b_t[3] / b_lb[3] - 1.0
            if ret == 0:
                continue
            entry, exitp = b_t[3], b_ex[3]
            if ret > 0:                                       # MUTLAK isaret
                rp = exitp / entry - 1.0
                key, n_long = f"LONG:{t}", n_long + 1
            else:
                rp = (entry - exitp) / entry
                key, n_short = f"SHORT:{t}", n_short + 1
            net = (rp - cost_pct) / af
            clusters.setdefault(key, []).append(net)
            gross_sum += rp / af
            net_sum += net
            placed += 1
        if placed:
            rebalances += 1
            sizes.append(placed)
        i += hold

    boot = measurement.cluster_bootstrap(clusters)
    ci = ([boot["ci_low"], boot["ci_high"]]
          if boot and boot.get("ci_low") is not None else None)
    n_clusters = len(clusters)
    if ci and ci[1] < 0:
        verdict = "ELENDI (kume-CI ust siniri < 0)"
    elif ci and ci[0] >= 0 and net_sum > 0 and n_clusters >= 50:
        verdict = "ADAY (kume-CI alt >= 0, net R > 0, kume >= 50)"
    elif n_clusters < 50:
        verdict = f"YETERSIZ VERI (kume {n_clusters} < 50) - budama zayif"
    else:
        verdict = "BELIRSIZ (arasi) - canliya aday, 'umut vaat etti' DENMEZ"

    return {
        "generated_utc": _iso(all_ts[-1]),
        "params": {"lookback_bars": lookback, "hold_bars": hold,
                   "atr_n": atr_n, "cost_pct_roundtrip": round(cost_pct, 6)},
        "pairs_loaded": len(pairs),
        "data_range": [_iso(all_ts[0]), _iso(all_ts[-1])],
        "rebalances": rebalances,
        "avg_positions_per_rebalance": (round(sum(sizes) / len(sizes), 1)
                                        if sizes else 0),
        "positions": n_long + n_short, "longs": n_long, "shorts": n_short,
        "clusters": n_clusters,
        "gross_r_sum": round(gross_sum, 2), "net_r_sum": round(net_sum, 2),
        "ci": ci, "e_net": (boot["e_net"] if boot else None),
        "verdict": verdict,
        "note": ("Tek atis budama; S5 ile ayni olcum, sinyal mutlak (isaret) "
                 "vs S5 goreli (siralama). HUKUM DEGIL - kesin soz canli "
                 "golge yaristan. ATR-normalize R bir vekildir; 90 gun tek "
                 "rejim olabilir."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, help="backtest-data klasoru")
    ap.add_argument("--json", default="", help="raporu bu dosyaya da yaz")
    args = ap.parse_args()

    rep = run_backtest(args.data)     # SABIT parametreler - tarama yok
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=2)

    print("\n=== TSM BACKTEST RAPORU (tek atis budama) ===")
    if rep.get("error"):
        print("HATA:", rep["error"])
        return 2
    print(f"parite: {rep['pairs_loaded']} | veri: {rep['data_range'][0]} "
          f"-> {rep['data_range'][1]}")
    print(f"denge: {rep['rebalances']} | ort pozisyon/denge: "
          f"{rep['avg_positions_per_rebalance']} | toplam pozisyon: "
          f"{rep['positions']} ({rep['longs']}L/{rep['shorts']}S)")
    print(f"kume: {rep['clusters']} | brut R: {rep['gross_r_sum']} | "
          f"net R: {rep['net_r_sum']}")
    print(f"kume-CI: {rep['ci']} | E_net: {rep['e_net']}")
    print(f"HUKUM: {rep['verdict']}")
    print(f"NOT: {rep['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
