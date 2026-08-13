"""Korelasyon olcum aleti (app/services/correlation.py) — Faz A, salt rapor."""
from __future__ import annotations

from app.services.challengers import RETIRED, SAMPLING_REGIME
from app.services.correlation import (build_report, correlation_matrix,
                                      direction_overlap, effective_bets,
                                      pair_days, pearson)
from app.services.database import Database


# ------------------------------------------------------------- saf fonksiyonlar
def test_pearson_basics():
    assert abs(pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9
    assert abs(pearson([1, 2, 3], [3, 2, 1]) + 1.0) < 1e-9
    assert pearson([1, 1, 1], [1, 2, 3]) is None      # sifir varyans
    assert pearson([1], [2]) is None                  # n<2


def test_pair_days_union_zero_fill():
    a = {"d1": 1.0, "d2": 2.0}
    b = {"d2": -1.0, "d3": 0.5}
    xs, ys = pair_days(a, b)
    assert xs == [1.0, 2.0, 0.0] and ys == [0.0, -1.0, 0.5]


def test_correlation_matrix_min_days_gate():
    s = {"A": {f"d{i}": float(i) for i in range(12)},
         "B": {f"d{i}": float(i) * 2 for i in range(12)},
         "C": {"d0": 1.0}}                            # 12 ortak gunle esik alti degil
    m = correlation_matrix(s, min_days=10)
    assert m["A|B"]["corr"] == 1.0 and m["A|B"]["days"] == 12
    # C ile ciftler esik alti -> corr None ama gun sayisi raporlanir
    assert m["A|C"]["corr"] is None and m["A|C"]["days"] == 12


def test_effective_bets_formula():
    # ort korelasyon 1 -> tek bagimsiz bahis; 0 -> N bahis
    m1 = {"A|B": {"corr": 1.0, "days": 20}}
    assert effective_bets(m1, 2)["effective_bets"] == 1.0
    m0 = {"A|B": {"corr": 0.0, "days": 20}}
    assert effective_bets(m0, 2)["effective_bets"] == 2.0
    assert effective_bets({}, 1)["effective_bets"] is None


def test_direction_overlap_rate():
    opens = {"A": {"d1": {"LONG"}, "d2": {"SHORT"}, "d3": {"LONG"}},
             "B": {"d1": {"LONG"}, "d2": {"LONG"}, "d9": {"SHORT"}}}
    ov = direction_overlap(opens)["A|B"]
    assert ov["both_open_days"] == 2          # d1, d2
    assert ov["same_dir_days"] == 1           # yalniz d1
    assert ov["rate"] == 0.5


# ------------------------------------------------------------------ DB raporu
def _db(tmp_path):
    from app.services.challengers import ChallengerEngine
    from app.services.signal_tracker import SignalTracker
    db = Database(str(tmp_path / "k.db"))
    SignalTracker(db, "15")
    ChallengerEngine(db, "15")
    return db


def test_build_report_reads_champion_and_challengers(tmp_path):
    db = _db(tmp_path)
    # sampiyon: 2 kapanmis islem, ayni gun
    for i, r in enumerate((2.0, -1.0)):
        db.execute(
            "INSERT INTO signals(pair,direction,created_utc,closed_utc,"
            "status,outcome,r_multiple,blocked) "
            "VALUES('BTCUSDT','LONG','2026-08-10T01:00:00Z',"
            "'2026-08-10T09:00:00Z','CLOSED','WIN',?,0)", (r,))
    # aday: S1, kapanis gunu entry_ts+hold ile hesaplanir
    t0 = 1_755_000_000_000                     # sabit ms
    db.execute(
        "INSERT INTO challenger_signals(strategy,pair,direction,created_utc,"
        "entry_ts,entry,stop,tp,timeout_bars,cluster_id,status,outcome,"
        "r_multiple,hold_bars,ambiguous,regime) "
        "VALUES('S1_TSMOM','ETHUSDT','SHORT','2026-08-10T02:00:00Z',?,"
        "100,102,96,192,'c1','CLOSED','WIN',1.5,4,0,?)",
        (t0, SAMPLING_REGIME))
    # eski rejim kaydi HESABA GIRMEZ
    db.execute(
        "INSERT INTO challenger_signals(strategy,pair,direction,created_utc,"
        "entry_ts,entry,stop,tp,timeout_bars,cluster_id,status,outcome,"
        "r_multiple,hold_bars,ambiguous) "
        "VALUES('S1_TSMOM','XUSDT','LONG','2026-08-01T02:00:00Z',?,"
        "100,98,104,192,'c0','CLOSED','LOSS',-1.0,4,1)", (t0,))
    rep = build_report(db, SAMPLING_REGIME, RETIRED)
    assert rep["strategies"]["CHAMPION"]["active_days"] == 1
    assert rep["strategies"]["S1_TSMOM"]["active_days"] == 1
    # gunluk toplam: sampiyon 2-1=+1 (seri toplami dogru kurulmus olmali)
    assert "CHAMPION|S1_TSMOM" in rep["daily_corr"]
    ov = rep["same_day_same_dir"]["CHAMPION|S1_TSMOM"]
    assert ov["both_open_days"] == 1 and ov["same_dir_days"] == 0


def test_report_is_measurement_only():
    """Rapor SALT olcumdur: karar/esik alani eklenirse bu test kirilir."""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        db = _db(Path(td))
        rep = build_report(db, SAMPLING_REGIME, RETIRED)
    assert set(rep) == {"note", "min_days", "basis", "strategies",
                        "daily_corr", "independence", "same_day_same_dir"}
    assert set(rep["independence"]) == {"n_strategies", "avg_pairwise_corr",
                                        "effective_bets", "pairs_measured"}
