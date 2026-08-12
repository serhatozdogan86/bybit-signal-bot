"""Kayit-arsiv denetim araci (tools/audit_replay.py) - salt sayim testleri."""
from __future__ import annotations

import csv
import os

from app.services.challengers import ChallengerEngine
from app.services.database import Database
from app.services.signal_tracker import SignalTracker
from tools.audit_replay import backup_live, run

STEP = 900_000
T0 = 1_000_000 * STEP          # arsivin ilk mumu


def _write_csv(dirpath, pair, candles):
    with open(os.path.join(dirpath, f"{pair}_15.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close", "volume"])
        for ts, o, h, lo, c in candles:
            w.writerow([ts, o, h, lo, c, 1.0])


def _mk_db(path):
    db = Database(path)
    SignalTracker(db, "15")        # sema goc adimlari (ambiguous vb.)
    ChallengerEngine(db, "15")
    return db


def _champ(db, pair, outcome, r_mult, entry_ts, amb=0):
    db.execute(
        "INSERT INTO signals(pair,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,status,outcome,r_multiple,"
        "blocked,ambiguous,fill_ts) "
        "VALUES(?,?,?,?,100.0,101.0,99.0,104.0,'CLOSED',?,?,0,?,NULL)",
        (pair, "LONG", "2026-08-01T00:00:00Z", entry_ts, outcome,
         r_mult, amb))


def _chal(db, pair, strategy, outcome, r_mult, entry_ts, timeout=192, amb=0):
    db.execute(
        "INSERT INTO challenger_signals(strategy,pair,direction,created_utc,"
        "entry_ts,entry,stop,tp,timeout_bars,cluster_id,status,outcome,"
        "r_multiple,hold_bars,ambiguous,regime) "
        "VALUES(?,?,?,?,?,100.0,98.0,106.0,?,?,'CLOSED',?,?,1,?,2)",
        (strategy, pair, "LONG", "2026-08-01T00:00:00Z", entry_ts,
         timeout, f"{strategy}:X", outcome, r_mult, amb))


def _fixture(tmp_path):
    data = tmp_path / "arsiv"
    data.mkdir()
    # TESTUSDT: dolus mumu (low 100.5 <= entry 101), sonra TP (high 105)
    _write_csv(data, "TESTUSDT", [
        (T0, 102, 103, 100.5, 102.5),
        (T0 + STEP, 102.5, 105.0, 102.0, 104.5),
        (T0 + 2 * STEP, 104.5, 104.8, 104.0, 104.2),
    ])
    # DOWNUSDT: dolus, sonra STOP (low 98.5 <= stop 99)
    _write_csv(data, "DOWNUSDT", [
        (T0, 102, 103, 100.5, 102.5),
        (T0 + STEP, 102.5, 102.8, 98.5, 99.5),
    ])
    # CHALUSDT: giris mumu SONRASI ilk mumda TP 106 (aday kurali ts>entry_ts)
    _write_csv(data, "CHALUSDT", [
        (T0, 100, 100.5, 99.5, 100.0),
        (T0 + STEP, 100.5, 107.0, 100.0, 106.5),
    ])
    db_path = str(tmp_path / "kopya.db")
    db = _mk_db(db_path)
    return data, db_path, db


# ------------------------------------------------------------------ sampiyon
def test_champion_match_and_mismatch(tmp_path):
    data, db_path, db = _fixture(tmp_path)
    # dogru kayit: WIN r=1.5 ((104-101)/(101-99))
    _champ(db, "TESTUSDT", "WIN", 1.5, T0)
    # yanlis kayit: arsive gore STOP (LOSS) olmasi gerekirken WIN yazilmis
    _champ(db, "DOWNUSDT", "WIN", 1.5, T0)
    rep = run(db_path, str(data))
    c = rep["champion"]
    assert c["closed"] == 2 and c["checked"] == 2
    assert c["match"] == 1 and c["mismatch"] == 1
    assert c["mismatch_details"][0]["pair"] == "DOWNUSDT"


def test_champion_out_of_window_and_missing_archive_skipped(tmp_path):
    data, db_path, db = _fixture(tmp_path)
    _champ(db, "TESTUSDT", "WIN", 1.5, T0 - 10 * STEP)   # arsivden eski
    _champ(db, "YOKUSDT", "WIN", 1.5, T0)                # arsivde CSV yok
    rep = run(db_path, str(data))
    c = rep["champion"]
    assert c["checked"] == 0 and c["mismatch"] == 0
    assert c["skipped"]["pencere_disi"] == 1
    assert c["skipped"]["arsiv_yok"] == 1


def test_champion_ambiguous_loss_equivalence(tmp_path):
    """Kilitli kural: ayni mumda TP+STOP defterde LOSS(ambiguous=1) yazilir;
    denetci AMBIGUOUS der - AYNI karar, uyusmazlik sayilmaz."""
    data, db_path, db = _fixture(tmp_path)
    _write_csv(data, "AMBUSDT", [
        (T0, 102, 103, 100.5, 102.5),          # dolus
        (T0 + STEP, 102, 105.0, 98.0, 100.0),  # ayni mumda tp+stop
    ])
    _champ(db, "AMBUSDT", "LOSS", -1.0, T0, amb=1)
    rep = run(db_path, str(data))
    assert rep["champion"]["mismatch"] == 0
    assert rep["champion"]["match"] == 1


# ---------------------------------------------------------------------- aday
def test_challenger_match_mismatch_and_breakdown(tmp_path):
    data, db_path, db = _fixture(tmp_path)
    # dogru: WIN r=3.0 ((106-100)/(100-98))
    _chal(db, "CHALUSDT", "S1_TSMOM", "WIN", 3.0, T0)
    # yanlis R: ayni olay, kayitta r=1.0
    _chal(db, "CHALUSDT", "S2_DONCHIAN", "WIN", 1.0, T0)
    rep = run(db_path, str(data))
    ch = rep["challengers"]
    assert ch["checked"] == 2 and ch["match"] == 1 and ch["mismatch"] == 1
    assert ch["per_strategy"]["S1_TSMOM"] == {"checked": 1, "mismatch": 0}
    assert ch["per_strategy"]["S2_DONCHIAN"]["mismatch"] == 1
    assert ch["mismatch_details"][0]["problems"][0].startswith("R:")


def test_challenger_timeout_and_insufficient_data(tmp_path):
    data, db_path, db = _fixture(tmp_path)
    # timeout=1: giris sonrasi ilk mumda TP var -> WIN; ama timeout senaryosu
    # icin dokunmayan mum dizisi kullan
    _write_csv(data, "FLATUSDT", [
        (T0, 100, 100.5, 99.5, 100.0),
        (T0 + STEP, 100.2, 100.9, 99.8, 100.6),
    ])
    # EXPIRED r=(100.6-100)/2=0.3
    _chal(db, "FLATUSDT", "S4_CARRY", "EXPIRED", 0.3, T0, timeout=1)
    # veri yetersiz: giris son mumda, sonrasi arsivde yok
    _chal(db, "FLATUSDT", "S4_CARRY", "WIN", 3.0, T0 + STEP)
    rep = run(db_path, str(data))
    ch = rep["challengers"]
    assert ch["match"] == 1 and ch["mismatch"] == 0
    assert ch["skipped"]["veri_yetersiz"] == 1


# ------------------------------------------------------------------ guvenlik
def test_backup_live_copies_without_writing(tmp_path):
    src = str(tmp_path / "canli.db")
    db = _mk_db(src)
    _champ(db, "TESTUSDT", "WIN", 1.5, T0)
    before = os.path.getmtime(src)
    dst = str(tmp_path / "kopya2.db")
    backup_live(src, dst)
    assert os.path.exists(dst)
    rep_rows = Database(dst).query("SELECT COUNT(*) n FROM signals")
    assert rep_rows[0]["n"] == 1
    assert os.path.getmtime(src) == before      # kaynaga yazilmadi


def test_report_is_count_only():
    """ON-KAYIT kurali: rapor yalniz sayim/karsilastirma alanlari tasir;
    istatistik alani eklenirse bu test bilerek kirilir."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "bos.db")
        _mk_db(db_path)
        os.makedirs(os.path.join(td, "arsiv"), exist_ok=True)
        rep = run(db_path, os.path.join(td, "arsiv"))
    assert set(rep) == {"generated_utc", "note", "champion", "challengers"}
    assert set(rep["champion"]) == {"closed", "checked", "match", "mismatch",
                                    "mismatch_details", "skipped"}
    assert set(rep["challengers"]) == {"closed", "checked", "match",
                                       "mismatch", "mismatch_details",
                                       "per_strategy", "skipped"}
