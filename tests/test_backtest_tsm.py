"""TSM backtest aracinin dogrulamasi (tools/backtest_tsm.py).

Sentetik: parite i'nin bar-basi buyumesi g=1+(i-10)*0.002. Mutlak isaret
kurali herkese uygulanir: g>1 (i>10) yukselir -> LONG kar; g<1 (i<10)
duser -> SHORT kar; g=1 (i=10) duz -> isaret 0 -> atlanir. Motor bu
trend kenarini geri bulmali (net R>0, kume-CI alt>0). Decile YOK: her
uygun parite pozisyonlanir.
"""
from __future__ import annotations

import csv
import os

from tools.backtest_s5 import STEP_MS
from tools.backtest_tsm import run_backtest

LB, HOLD, ATRN = 6, 2, 3


def _write(dirpath, pair, bars):
    with open(os.path.join(dirpath, f"{pair}_240.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close", "volume"])
        for ts, o, h, lo, c in bars:
            w.writerow([ts, o, h, lo, c, 1.0])


def _universe(dirpath, n_pairs=20, n_bars=18, t0=1_000_000 * STEP_MS):
    for i in range(n_pairs):
        g = 1.0 + (i - 10) * 0.002
        bars = []
        for k in range(n_bars):
            c = 100.0 * (g ** k)
            bars.append((t0 + k * STEP_MS, c, c * 1.001, c * 0.999, c))
        _write(dirpath, f"P{i:02d}USDT", bars)


def test_trend_edge_recovered(tmp_path):
    _universe(str(tmp_path))
    rep = run_backtest(str(tmp_path), lookback=LB, hold=HOLD, atr_n=ATRN)
    assert rep["pairs_loaded"] == 20
    assert rep["rebalances"] == 5                 # t=6,8,10,12,14
    # i=10 duz (isaret 0) atlanir; i>10 -> 9 long, i<10 -> 10 short
    assert rep["longs"] == 9 * 5 and rep["shorts"] == 10 * 5
    assert rep["clusters"] == 10                  # yon x denge
    assert rep["gross_r_sum"] > 0
    assert 0 < rep["net_r_sum"] < rep["gross_r_sum"]
    assert rep["ci"] is not None and rep["ci"][0] > 0


def test_flat_pair_skipped(tmp_path):
    # tek duz parite: isaret 0 -> hic pozisyon yok -> yetersiz
    t0 = 1_000_000 * STEP_MS
    _write(str(tmp_path), "FLATUSDT",
           [(t0 + k * STEP_MS, 100.0, 100.1, 99.9, 100.0) for k in range(18)])
    rep = run_backtest(str(tmp_path), lookback=LB, hold=HOLD, atr_n=ATRN)
    assert rep["positions"] == 0 and rep["rebalances"] == 0


def test_cost_field_and_no_decile(tmp_path):
    _universe(str(tmp_path))
    rep = run_backtest(str(tmp_path), lookback=LB, hold=HOLD, atr_n=ATRN)
    # decile yok: denge basina ~19 pozisyon (20 parite - 1 duz)
    assert rep["avg_positions_per_rebalance"] == 19.0
    assert abs(rep["params"]["cost_pct_roundtrip"] - 0.0012) < 1e-9


def test_insufficient_history(tmp_path):
    _universe(str(tmp_path), n_bars=5)
    rep = run_backtest(str(tmp_path), lookback=LB, hold=HOLD, atr_n=ATRN)
    assert rep["rebalances"] == 0 and rep["clusters"] == 0
    assert rep["ci"] is None and "YETERSIZ" in rep["verdict"]


def test_empty_data(tmp_path):
    assert run_backtest(str(tmp_path)).get("error") == "veri yok"
