"""Cikis laboratuvari testleri (on-kayit ideas.md 2026-08-17).

Kanit yuku: (1) V0 sadakati — yeniden oynatma, motorun defterdeki
sonucunu BIREBIR uretmeli; (2) mekanizma farki — ayni fiyat serisinde
V0 zarar yazarken V1 kar kilitleyebilmeli; (3) muhafazakar sira — ayni
mumdaki yeni tepe o mumun stopunu kurtaramaz; (4) alet SALT-OKUR;
(5) hukum kurali onceden ilan edilen esiklerle calisir.
"""
from __future__ import annotations

import numpy as np

from app.services import exit_lab
from app.services.challengers import ChallengerEngine, SAMPLING_REGIME
from app.services.database import Database
from tests import fixtures as fx
from tests.test_challengers import _put_candles


def _eng(tmp_path):
    db = Database(str(tmp_path / "x.db"))
    return ChallengerEngine(db, "15"), db


def _insert_signal(db, pair="AUSDT", direction="LONG", entry=100.0,
                   stop=98.0, tp=106.0, timeout=96, cid="S2:L1"):
    db.execute(
        "INSERT INTO challenger_signals(strategy,pair,direction,created_utc,"
        "entry_ts,entry,stop,tp,timeout_bars,cluster_id,regime) "
        "VALUES('S2_DONCHIAN',?,?,'2026-08-17T00:00:00Z',1000000,?,?,?,?,?,?)",
        (pair, direction, entry, stop, tp, timeout, cid, SAMPLING_REGIME))


def test_v0_replay_reproduces_ledger_outcome(tmp_path):
    """SADAKAT SARTI: V0 yeniden-oynatmasi, motorun kapattigi kaydin
    sonucunu birebir uretmeli; uyumsuzluk sayaci sifir kalmali."""
    eng, db = _eng(tmp_path)
    _insert_signal(db)                       # LONG 100, stop 98, tp 106
    # 3. mum V1'in de sonuclanmasi icin: V1 hedefsizdir, V0'dan uzun
    # yasar; iz stop 104.5 (=106.5-2) mum 3'te vurulur
    _put_candles(db, "AUSDT",
                 [(101.0, 99.0, 100.5), (106.5, 100.0, 106.0),
                  (105.0, 104.0, 104.5)],
                 start_ts=1_900_000)
    eng.evaluate_open("AUSDT")
    row = db.query_one("SELECT * FROM challenger_signals")
    assert row["outcome"] == "WIN"
    rep = exit_lab.build_report(db, SAMPLING_REGIME)
    assert rep["replayed"] == 1
    assert rep["v0_fidelity_mismatch"] == 0
    s = rep["strategies"]["S2_DONCHIAN"]
    assert s["n"] == 1
    # V0 net, brut 3R'den kucuk (maliyet dusuldu) ama pozitif
    assert 0 < s["V0_SABIT"]["net_r"] < 3.0


def test_v1_locks_profit_where_v0_takes_full_loss(tmp_path):
    """MEKANIZMA FARKI KANITI: fiyat once kosar (hedefe degmeden), sonra
    coker. V0 sabit kural -1R zarar yazar; V1 iz suren stop kari kilitler."""
    eng, db = _eng(tmp_path)
    _insert_signal(db)                       # LONG 100, stop 98, tp 106
    # mum 1: 105.5'e kosar (tp 106'ya DEGMEZ), mum 2: 97'ye coker
    _put_candles(db, "AUSDT",
                 [(105.5, 100.0, 105.0), (105.0, 97.0, 97.5)],
                 start_ts=1_900_000)
    eng.evaluate_open("AUSDT")
    row = db.query_one("SELECT * FROM challenger_signals")
    assert row["outcome"] == "LOSS" and row["r_multiple"] == -1.0
    rep = exit_lab.build_report(db, SAMPLING_REGIME)
    s = rep["strategies"]["S2_DONCHIAN"]
    assert rep["v0_fidelity_mismatch"] == 0
    assert s["V0_SABIT"]["net_r"] < -1.0     # zarar + maliyet
    # V1: mum 1 sonrasi stop = 105.5 - 2 = 103.5; mum 2 stoptan cikar:
    # brut R = (103.5-100)/2 = +1.75
    assert s["V1_IZ"]["net_r"] > 1.5
    assert s["fark_v1_eksi_v0"]["e"] > 2.5   # fark ~ +2.8R


def test_v1_conservative_same_bar_order():
    """Ayni mumda once STOP kontrolu, sonra yukseltme: mumun yeni tepesi
    o mumun stopunu kurtaramaz (bakis-oncesi yasaginin V1 hali)."""
    candles = [
        {"ts": 1, "high": 104.0, "low": 99.5, "close": 103.0},
        # bu mum hem 106 tepesi yapar hem 102'ye sarkar: MEVCUT stop 102
        # (=104-2) vurulur; tepe 106'nin stopu 104'e cekmesi SAYILMAZ
        {"ts": 2, "high": 106.0, "low": 101.0, "close": 105.0},
    ]
    v1 = exit_lab.replay_v1("LONG", 100.0, 98.0, 96, candles)
    assert v1["outcome"] == "TRAIL_STOP"
    assert abs(v1["r"] - 1.0) < 1e-9         # cikis 102'den, 104'ten degil


def test_v1_short_mirror_and_timeout():
    """SHORT ayna: stop asagi cekilir (min, low + iz). Stop hic vurulmazsa
    kayitli timeout'ta kapanistan EXPIRED."""
    candles = [{"ts": i, "high": 100.5 - i, "low": 99.5 - i,
                "close": 100.0 - i} for i in range(1, 4)]
    v1 = exit_lab.replay_v1("SHORT", 100.0, 102.0, 96, candles)
    assert v1 is None                        # timeout'a gelmedi, hala acik
    v1 = exit_lab.replay_v1("SHORT", 100.0, 102.0, 3, candles)
    assert v1["outcome"] == "EXPIRED" and v1["hold_bars"] == 3
    assert v1["r"] > 0                       # dusen fiyat SHORT'a kar
    # ayna iz: dip 96.5 sonrasi stop 98.5'e inmis olmali -> yukselis vurur
    candles2 = candles + [{"ts": 9, "high": 99.0, "low": 97.0,
                           "close": 98.9}]
    v2 = exit_lab.replay_v1("SHORT", 100.0, 102.0, 96, candles2)
    assert v2["outcome"] == "TRAIL_STOP"
    assert abs(v2["r"] - ((100.0 - 98.5) / 2.0)) < 1e-9


def test_report_is_read_only(tmp_path):
    """Alet SALT-OKUR: rapor uretimi hicbir tabloya yazamaz."""
    eng, db = _eng(tmp_path)
    _insert_signal(db)
    _put_candles(db, "AUSDT", [(106.5, 99.0, 106.0)], start_ts=1_900_000)
    eng.evaluate_open("AUSDT")
    before = (db.query_one("SELECT COUNT(*) n FROM challenger_signals")["n"],
              db.query_one("SELECT COUNT(*) n FROM candles")["n"],
              db.query_one("SELECT * FROM challenger_signals"))
    exit_lab.build_report(db, SAMPLING_REGIME)
    after = (db.query_one("SELECT COUNT(*) n FROM challenger_signals")["n"],
             db.query_one("SELECT COUNT(*) n FROM candles")["n"],
             db.query_one("SELECT * FROM challenger_signals"))
    assert before == after


def test_incomplete_candles_counted_honestly(tmp_path):
    """Mum arsivi eksikse (yeniden oynatma bitirilemiyorsa) sinyal sessizce
    atilmaz: incomplete_candles sayacinda gorunur."""
    eng, db = _eng(tmp_path)
    _insert_signal(db, timeout=96)
    # kayit CLOSED ama arsivde yalniz 1 notr mum var (96 bar'a yetmez)
    db.execute("UPDATE challenger_signals SET status='CLOSED', "
               "outcome='EXPIRED', r_multiple=0.1, hold_bars=96")
    _put_candles(db, "AUSDT", [(100.5, 99.5, 100.2)], start_ts=1_900_000)
    rep = exit_lab.build_report(db, SAMPLING_REGIME)
    assert rep["replayed"] == 0 and rep["incomplete_candles"] == 1


def test_verdict_rule_preregistered():
    """Hukum esikleri onceden ilan: >=50 kume + fark CI alt > 0 -> V1;
    ust < 0 -> V0; az kume -> veri birikiyor; arada -> belirsiz."""
    assert exit_lab.verdict(49, 0.5, 1.0) == "VERI_BIRIKIYOR"
    assert exit_lab.verdict(50, None, None) == "VERI_BIRIKIYOR"
    assert exit_lab.verdict(50, 0.01, 0.5) == "V1_USTUN"
    assert exit_lab.verdict(50, -0.5, -0.01) == "V0_USTUN"
    assert exit_lab.verdict(50, -0.1, 0.1) == "BELIRSIZ"


def test_old_regime_rows_excluded(tmp_path):
    """Rejim disiplini korunur: eski rejim kayitlari yeniden oynatilmaz."""
    eng, db = _eng(tmp_path)
    db.execute(
        "INSERT INTO challenger_signals(strategy,pair,direction,created_utc,"
        "entry_ts,entry,stop,tp,timeout_bars,cluster_id,status,outcome,"
        "r_multiple,hold_bars,regime) VALUES('S2_DONCHIAN','AUSDT','LONG',"
        "'x',1000000,100,98,106,96,'S2:L1','CLOSED','WIN',3.0,2,1)")
    _put_candles(db, "AUSDT", [(106.5, 99.0, 106.0)], start_ts=1_900_000)
    rep = exit_lab.build_report(db, SAMPLING_REGIME)
    assert rep["replayed"] == 0 and rep["strategies"] == {}


def test_exitlab_endpoint(tmp_path):
    """/exitlab rotasi raporu dondurur (DASHBOARD_TOKEN kapisi genel
    before_request ile ayni)."""
    from unittest.mock import MagicMock
    from app.server import create_app
    from app.services.sqlite_state_store import SQLiteStateStore
    db = Database(str(tmp_path / "ep.db"))
    eng = ChallengerEngine(db, "15")
    sch = MagicMock()
    sch.challengers = eng
    app = create_app(SQLiteStateStore(db), sch, None)
    data = app.test_client().get("/exitlab").get_json()
    assert data["variants"] == ["V0_SABIT", "V1_IZ"]
    assert "v0_fidelity_mismatch" in data and "strategies" in data
