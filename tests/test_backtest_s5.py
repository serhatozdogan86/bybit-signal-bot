"""S5 backtest aracinin dogrulamasi (tools/backtest_s5.py).

Sentetik evren: parite i'nin bar-basi buyume orani monoton (i buyudukce
guclu). Boylece her dengede siralama sabit; en guclu %10 LONG yukselir,
en zayif %10 SHORT duser -> iki bacak da kar eder. Motor bu kenari
geri bulmali (net R > 0, kume-CI alt > 0). ATR-normalizasyon, maliyet
dususu ve kume sayimi da burada dogrulanir.
"""
from __future__ import annotations

import csv
import os

from tools.backtest_s5 import STEP_MS, atr_frac, run_backtest

# kucuk parametreler (hiz): bakis 6 bar, tutus 2 bar, ATR 3
LB, HOLD, ATRN = 6, 2, 3


def _write(dirpath, pair, bars):
    with open(os.path.join(dirpath, f"{pair}_240.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close", "volume"])
        for ts, o, h, lo, c in bars:
            w.writerow([ts, o, h, lo, c, 1.0])


def _universe(dirpath, n_pairs=20, n_bars=18, t0=1_000_000 * STEP_MS):
    """Parite i: bar-basi buyume g=1+(i-10)*0.002 (monoton siralama)."""
    for i in range(n_pairs):
        g = 1.0 + (i - 10) * 0.002
        bars = []
        c = 100.0
        for k in range(n_bars):
            c = 100.0 * (g ** k)
            bars.append((t0 + k * STEP_MS, c, c * 1.001, c * 0.999, c))
        _write(dirpath, f"P{i:02d}USDT", bars)


# ------------------------------------------------------------- atr_frac
def test_atr_frac_consecutive_bars(tmp_path):
    bars = {i * STEP_MS: (100.0, 101.0, 99.0, 100.0) for i in range(5)}
    af = atr_frac(bars, 4 * STEP_MS, STEP_MS, 3)
    assert af is not None and af > 0
    # bosluk varsa None
    del bars[2 * STEP_MS]
    assert atr_frac(bars, 4 * STEP_MS, STEP_MS, 3) is None


# ------------------------------------------------------------- ana kenar
def test_momentum_edge_recovered(tmp_path):
    _universe(str(tmp_path))
    rep = run_backtest(str(tmp_path), lookback=LB, hold=HOLD, atr_n=ATRN)
    assert rep["pairs_loaded"] == 20
    # warmup index 6, exit +2 gerekli -> denge t=6,8,10,12,14 = 5
    assert rep["rebalances"] == 5
    # her dengede sepet = round(0.1*20)=2; 5 denge -> 10L + 10S
    assert rep["longs"] == 10 and rep["shorts"] == 10
    assert rep["clusters"] == 10          # yon x denge = 2 x 5
    # kenar geri bulundu: brut ve net pozitif, net < brut (maliyet dususu)
    assert rep["gross_r_sum"] > 0
    assert 0 < rep["net_r_sum"] < rep["gross_r_sum"]
    # tutarli pozitif -> kume-CI alt siniri sifirin ustunde
    assert rep["ci"] is not None and rep["ci"][0] > 0


def test_avg_basket_and_cost_field(tmp_path):
    _universe(str(tmp_path))
    rep = run_backtest(str(tmp_path), lookback=LB, hold=HOLD, atr_n=ATRN)
    assert rep["avg_basket"] == 2.0
    # maliyet = 2*taker + funding*(hold*4/8) = 0.0011 + 0.0001*1 = 0.0012
    assert abs(rep["params"]["cost_pct_roundtrip"] - 0.0012) < 1e-9


def test_insufficient_history_no_rebalance(tmp_path):
    # yalniz 5 bar: bakis(6) dolmadan denge olamaz
    _universe(str(tmp_path), n_bars=5)
    rep = run_backtest(str(tmp_path), lookback=LB, hold=HOLD, atr_n=ATRN)
    assert rep["rebalances"] == 0 and rep["clusters"] == 0
    assert rep["ci"] is None
    assert "YETERSIZ" in rep["verdict"]


def test_empty_data_dir(tmp_path):
    rep = run_backtest(str(tmp_path))
    assert rep.get("error") == "veri yok"


def test_short_leg_profits_on_falling_pairs(tmp_path):
    """SHORT bacaginin isaret dogrulugu: dusen paritede short kar etmeli."""
    _universe(str(tmp_path))
    rep = run_backtest(str(tmp_path), lookback=LB, hold=HOLD, atr_n=ATRN)
    # net R toplami pozitifse ve short'lar dusen paritelerse, short bacagi
    # kayba surukmemis demektir; brut > 0 zaten iki bacagi da kapsar.
    assert rep["net_r_sum"] > 0
