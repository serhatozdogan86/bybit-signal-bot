"""P4 (OI-onayli kirilim kohortu) ve 52w-HIGH backtest araclari."""
from __future__ import annotations

import csv
import os
from datetime import datetime, timezone

from tools.backtest_52w import DAY, _is_monday
from tools.backtest_52w import run_backtest as run_52w
from tools.backtest_oi_breakout import run_pair as p4_run_pair
from tools.download_backtest_data import _MS

M15 = 900_000
H4 = 14_400_000
H1 = 3_600_000
T0 = 1_000_000 * H4                      # 4H hizali baslangic


# ------------------------------------------------------------------ altyapi
def test_downloader_supports_daily_interval():
    assert _MS.get("D") == 86_400_000    # 52w on-kaydinin veri kanali


def test_monday_detection():
    monday = datetime(2026, 8, 10, tzinfo=timezone.utc)   # bilinen Pazartesi
    ts = int(monday.timestamp() * 1000)
    assert _is_monday(ts)
    assert not _is_monday(ts + DAY)      # Sali
    assert _is_monday(ts + 7 * DAY)


# ---------------------------------------------------------------------- P4
def _p4_scenario(oi_rise=0.10, rally=True):
    """Duz kanal -> yukari kirilim; OI tetik gununde oi_rise kadar artar."""
    bars4h = [(T0 + i * H4, 100.0, 100.5, 99.5, 100.0) for i in range(40)]
    n_flat = 40 * 16                      # 4H penceresini kapsayan 15m sayisi
    bars15 = [(T0 + i * M15, 100.0, 100.2, 99.8, 100.0)
              for i in range(n_flat)]
    # kirilim mumu: onceki kapanis kanal ici (<=100.5), simdiki ustunde
    t_break = T0 + n_flat * M15
    bars15.append((t_break, 100.4, 101.2, 100.3, 101.0))
    p = 101.0
    for i in range(1, 260):
        p = p + (0.05 if rally else -0.02)
        t = t_break + i * M15
        bars15.append((t, p, p + 0.1, p - 0.1, p))
    oi = {}
    for hh in range(-30, (len(bars15) * M15) // H1 + 5):
        t = T0 + hh * H1
        boundary = (n_flat * M15) // H1
        oi[t] = 1000.0 * (1 + oi_rise) if hh >= boundary - 1 else 1000.0
    return bars15, bars4h, oi


def test_p4_cohort_assignment_rising_oi():
    bars15, bars4h, oi = _p4_scenario(oi_rise=0.10)
    trades, skipped = p4_run_pair(bars15, bars4h, oi)
    assert skipped == 0 and len(trades) >= 1
    assert trades[0]["cohort"] == "OI_ARTISLI"
    assert trades[0]["outcome"] in ("WIN", "EXPIRED")


def test_p4_cohort_assignment_flat_oi():
    bars15, bars4h, oi = _p4_scenario(oi_rise=0.0)
    trades, _ = p4_run_pair(bars15, bars4h, oi)
    assert len(trades) >= 1
    assert trades[0]["cohort"] == "OI_ARTISSIZ"


def test_p4_missing_oi_skips_and_counts():
    bars15, bars4h, _ = _p4_scenario()
    trades, skipped = p4_run_pair(bars15, bars4h, {})
    assert trades == [] and skipped >= 1


# --------------------------------------------------------------------- 52w
def _write_daily(dirpath, pair, closes, t0):
    with open(os.path.join(dirpath, f"{pair}_D.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close", "volume"])
        for i, c in enumerate(closes):
            w.writerow([t0 + i * DAY, c, c * 1.005, c * 0.995, c, 1.0])


def _monday_t0(n_days_before):
    monday = int(datetime(2026, 8, 10, tzinfo=timezone.utc)
                 .timestamp() * 1000)
    return monday - n_days_before * DAY


def test_52w_selects_near_high_and_wins(tmp_path):
    n = 130                               # 90 gun gecmis + test haftalari
    t0 = _monday_t0(n - 14)               # son 2 hafta islem penceresi
    # ZIRVE: surekli yukselen -> yakinlik 1.0, secilir, hafta boyu yukselir
    _write_daily(tmp_path, "TOPUSDT", [100 + i * 0.5 for i in range(n)], t0)
    # DIP: zirvesinden %50 asagida -> yakinlik ~0.5, secilMEZ
    dip = [200.0] * 10 + [100.0] * (n - 10)
    _write_daily(tmp_path, "DIPUSDT", dip, t0)
    for j in range(10):                   # kesit dolgusu: yakinlik ~0.77 <0.90
        _write_daily(tmp_path, f"MID{j}USDT",
                     [130.0] * 5 + [100.0] * (n - 5), t0)
    rep = run_52w(str(tmp_path))
    assert rep["trades"] >= 1
    assert rep["losses"] == 0             # yukselen seride stop yenmez
    assert rep["net_sum"] > 0
    assert rep["clusters"] == rep["weeks_with_entry"]   # hafta = kume


def test_52w_proximity_floor_blocks_low_cross_section(tmp_path):
    n = 130
    t0 = _monday_t0(n - 14)
    # herkes zirvesinin %70'inde -> yakinlik tabani 0.90 gecilemez
    for j in range(12):
        closes = [140.0] * 10 + [100.0] * (n - 10)
        _write_daily(tmp_path, f"P{j}USDT", closes, t0)
    rep = run_52w(str(tmp_path))
    assert rep["trades"] == 0 and rep["weeks_with_entry"] == 0


def test_52w_stop_hit_is_loss(tmp_path):
    n = 130
    t0 = _monday_t0(n - 14)
    # zirveye yakin ama karar sonrasi coker -> stop LOSS -1
    closes = [100 + i * 0.5 for i in range(n - 6)] + \
             [40.0] * 6                   # son hafta cokus
    _write_daily(tmp_path, "CRASHUSDT", closes, t0)
    for j in range(10):                   # kesit dolgusu: yakinlik ~0.77 <0.90
        _write_daily(tmp_path, f"MID{j}USDT",
                     [130.0] * 5 + [100.0] * (n - 5), t0)
    rep = run_52w(str(tmp_path))
    # cokus haftasinin girisi stop yer; onceki yukselen haftalar kazanir
    assert rep["losses"] >= 1
    assert rep["wins"] >= 1


def test_52w_short_history_skipped(tmp_path):
    n = 40                                # 90 gun altinda
    t0 = _monday_t0(n - 14)
    _write_daily(tmp_path, "NEWUSDT", [100 + i for i in range(n)], t0)
    rep = run_52w(str(tmp_path))
    assert rep["trades"] == 0
    assert rep["skipped_short_history"] >= 1
