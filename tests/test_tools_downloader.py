"""Backtest veri indiricisinin butunluk sayaclari (tools/, salt sayim)."""
from __future__ import annotations

from tools.download_backtest_data import integrity


def test_integrity_reports_gaps_and_stays_count_only():
    step = 900_000
    ts = [0, step, 2 * step, 6 * step]        # 2*step sonrasi 3 mum eksik
    rep = integrity(ts, step)
    assert rep["rows"] == 4
    assert rep["gaps"] == 1
    assert rep["gap_details"][0]["missing"] == 3
    assert rep["monotonic"] is True
    # ON-KAYIT kurali: rapor YALNIZ sayim alanlari icerir; istatistik/analiz
    # alani eklenirse bu test bilerek kirilir.
    assert set(rep) == {"rows", "range", "gaps", "gap_details", "monotonic"}


def test_integrity_empty_and_clean_series():
    step = 900_000
    assert integrity([], step)["rows"] == 0
    clean = integrity([i * step for i in range(10)], step)
    assert clean["gaps"] == 0 and clean["monotonic"] is True
    assert clean["range"][0].endswith("Z")
