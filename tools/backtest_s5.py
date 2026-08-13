"""S5 KESİTSEL MOMENTUM — geçmiş veri budaması (ÖN-KAYIT: docs/ideas.md 2026-08-13).

NE YAPAR:
  İndirilen 4H CSV arşivinden (tools/download_backtest_data.py çıktısı) S5
  kesitsel momentum stratejisini TEK atış test eder ve ölçüm çerçevemizin
  diliyle (risk-birimli R + küme-blok bootstrap CI) raporlar.

KURALLAR (docs/ideas.md'de dondurulmuş — burada DEĞİŞTİRİLEMEZ):
  - 4H; bakış 84 bar (14 gün); denge 12 bar (48 saat).
  - Her denge: uygun evreni son 14 günlük HAM getiriye göre sırala;
    en güçlü %10 LONG, en zayıf %10 SHORT; sepet = max(1, round(0.10×N)).
  - Giriş close[t], çıkış close[t+12] (sabit 48s; stop/hedef yok).
  - R paydası = ATR(14,4H)/close (atr_frac). net R = (getiri − maliyet)/atr_frac.
    Maliyet = 2×taker + funding×(denge/2 periyot). Stop kayması YOK (stop yok).
  - Küme = yön + denge zaman damgası. Faz-1: ≥50 küme + küme-CI alt > 0.

NE YAPMAZ: parametre taraması YOK (tek atış). CLI sabit parametrelerle çalışır;
  parametreler yalnız birim testinden geçirilebilir (tarama değil, doğrulama).

KULLANIM (VM):
  cd ~/bybit-signal-bot-audit && git pull
  .venv/bin/python tools/backtest_s5.py --data /home/ubuntu/backtest-data
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import measurement                          # noqa: E402
from app.services.signal_tracker import FUNDING_8H, TAKER_FEE  # noqa: E402

STEP_MS = 4 * 60 * 60 * 1000       # 4H
LOOKBACK = 84                      # 14 gün
HOLD = 12                          # 48 saat
ATR_N = 14
DECILE = 0.10


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def load_pairs(data_dir: str, interval: str = "240") -> dict[str, dict]:
    """PAIR_240.csv dosyalarini {pair: {ts:(o,h,l,c)}} olarak yukle."""
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


def atr_frac(bars: dict[int, tuple], t: int, step: int, n: int) -> float | None:
    """ATR(n)/close[t]: t-n*step .. t araligindaki n+1 mum kesintisiz olmali."""
    seq = []
    for k in range(n + 1):
        b = bars.get(t - (n - k) * step)
        if b is None:
            return None
        seq.append(b)
    trs = []
    for i in range(1, len(seq)):
        _, h, lo, c = seq[i]
        prev_c = seq[i - 1][3]
        trs.append(max(h - lo, abs(h - prev_c), abs(lo - prev_c)))
    close_t = seq[-1][3]
    if close_t <= 0 or not trs:
        return None
    return (sum(trs) / len(trs)) / close_t


def run_backtest(data_dir: str, lookback: int = LOOKBACK, hold: int = HOLD,
                 atr_n: int = ATR_N, decile: float = DECILE,
                 step: int = STEP_MS) -> dict:
    pairs = load_pairs(data_dir)
    if not pairs:
        return {"error": "veri yok", "pairs": 0}
    all_ts = sorted({t for bars in pairs.values() for t in bars})
    # denge zaman izgarasi: en erken uygun andan itibaren her 'hold' adim
    grid = all_ts
    # maliyet (R paydasina bolunecek): round-trip taker + funding
    funding_periods = hold * (step / 1000 / 3600) / 8.0      # saat/8
    cost_pct = 2 * TAKER_FEE + FUNDING_8H * funding_periods

    clusters: dict[str, list[float]] = {}
    gross_sum = net_sum = 0.0
    n_long = n_short = 0
    basket_sizes: list[int] = []
    rebalances = 0

    start_i = 0
    # ilk denge: en az 'lookback' bar geçmişi ve 'hold' bar geleceği olacak an
    while start_i < len(grid) and grid[start_i] < all_ts[0] + lookback * step:
        start_i += 1

    i = start_i
    while i < len(grid):
        t = grid[i]
        lb_ts, ex_ts = t - lookback * step, t + hold * step
        ranked = []
        for pair, bars in pairs.items():
            b_t, b_lb, b_ex = bars.get(t), bars.get(lb_ts), bars.get(ex_ts)
            if b_t is None or b_lb is None or b_ex is None:
                continue
            if b_lb[3] <= 0:
                continue
            af = atr_frac(bars, t, step, atr_n)
            if af is None or af <= 0:
                continue
            ret = b_t[3] / b_lb[3] - 1.0                    # 14g ham getiri
            ranked.append((ret, pair, b_t[3], b_ex[3], af))
        n = len(ranked)
        if n >= 10:                                          # anlamli sepet icin
            rebalances += 1
            ranked.sort(key=lambda x: x[0])
            k = max(1, round(decile * n))
            longs = ranked[-k:]
            shorts = ranked[:k]
            basket_sizes.append(k)
            for _, _, entry, exitp, af in longs:
                rp = exitp / entry - 1.0
                net = (rp - cost_pct) / af
                clusters.setdefault(f"LONG:{t}", []).append(net)
                gross_sum += rp / af
                net_sum += net
                n_long += 1
            for _, _, entry, exitp, af in shorts:
                rp = (entry - exitp) / entry
                net = (rp - cost_pct) / af
                clusters.setdefault(f"SHORT:{t}", []).append(net)
                gross_sum += rp / af
                net_sum += net
                n_short += 1
        i += hold

    boot = measurement.cluster_bootstrap(clusters)
    ci = ([boot["ci_low"], boot["ci_high"]]
          if boot and boot.get("ci_low") is not None else None)
    n_clusters = len(clusters)
    # onceden ilan edilmis basari olcutu
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
                   "atr_n": atr_n, "decile": decile,
                   "cost_pct_roundtrip": round(cost_pct, 6)},
        "pairs_loaded": len(pairs),
        "data_range": [_iso(all_ts[0]), _iso(all_ts[-1])],
        "rebalances": rebalances,
        "avg_basket": (round(sum(basket_sizes) / len(basket_sizes), 1)
                       if basket_sizes else 0),
        "positions": n_long + n_short, "longs": n_long, "shorts": n_short,
        "clusters": n_clusters,
        "gross_r_sum": round(gross_sum, 2),
        "net_r_sum": round(net_sum, 2),
        "ci": ci, "e_net": (boot["e_net"] if boot else None),
        "verdict": verdict,
        "note": ("Tek atis budama. HUKUM DEGIL - kesin soz canli golge "
                 "yarisin 50 kumesi + walk-forward'dan cikar. ATR-normalize R "
                 "bir vekildir. 90 gun tek rejim olabilir."),
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

    print("\n=== S5 BACKTEST RAPORU (tek atis budama) ===")
    if rep.get("error"):
        print("HATA:", rep["error"])
        return 2
    print(f"parite: {rep['pairs_loaded']} | veri: {rep['data_range'][0]} "
          f"-> {rep['data_range'][1]}")
    print(f"denge sayisi: {rep['rebalances']} | ort sepet: {rep['avg_basket']} "
          f"| pozisyon: {rep['positions']} ({rep['longs']}L/{rep['shorts']}S)")
    print(f"kume: {rep['clusters']} | brut R: {rep['gross_r_sum']} | "
          f"net R: {rep['net_r_sum']}")
    print(f"kume-CI: {rep['ci']} | E_net: {rep['e_net']}")
    print(f"HUKUM: {rep['verdict']}")
    print(f"NOT: {rep['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
