"""Aday motoru testleri: uretim, degerlendirme, izolasyon, bakis-oncesi yasagi."""
from __future__ import annotations

import json

import numpy as np

from app.services.challengers import ChallengerEngine
from app.services.database import Database
from tests import fixtures as fx
from tests.test_signal_tracker import _feed, _make_tracker, _signal


def _eng(tmp_path):
    db = Database(str(tmp_path / "c.db"))
    return ChallengerEngine(db, "15"), db


def _put_candles(db, pair, rows, start_ts):
    db.executemany(
        "INSERT OR IGNORE INTO candles(symbol,interval,ts,open,high,low,"
        "close,volume) VALUES(?, '15', ?, ?, ?, ?, ?, 1000)",
        [(pair, start_ts + i * 900_000, c, h, l, c)
         for i, (h, l, c) in enumerate(rows)])


# ------------------------------------------------------------ uretim
def test_s2_donchian_edge_trigger_and_win_evaluation(tmp_path):
    eng, db = _eng(tmp_path)
    htf = fx.make_series(np.full(60, 100.0), interval="240")
    # ltf: onceki kapanis kanal ici (<=htf max high), son kapanis kirilim ustu
    closes = np.concatenate([np.full(98, 100.0), [100.0, 106.0]])
    ltf = fx.make_series(closes)
    assert eng.on_scan("AUSDT", htf, ltf, None) >= 1
    row = db.query_one("SELECT * FROM challenger_signals WHERE strategy="
                       "'S2_DONCHIAN'")
    assert row["direction"] == "LONG" and row["entry"] == 106.0
    # ayni kova ikinci tarama: tekrar uretmemeli (dedup)
    assert eng.on_scan("AUSDT", htf, ltf, None) == 0
    # degerlendirme: sonraki mumlar hedefe kosar -> WIN, R dogru
    risk = row["entry"] - row["stop"]
    _put_candles(db, "AUSDT",
                 [(row["entry"] + 0.4 * risk, row["entry"] - 0.2 * risk,
                   row["entry"] + 0.3 * risk),
                  (row["tp"] + 0.1, row["entry"], row["tp"])],
                 start_ts=row["entry_ts"] + 900_000)
    eng.evaluate_open("AUSDT")
    row = db.query_one("SELECT * FROM challenger_signals")
    assert row["outcome"] == "WIN" and abs(row["r_multiple"] - 3.0) < 0.05


def test_s6_sweep_short_generation(tmp_path):
    eng, db = _eng(tmp_path)
    closes = np.full(120, 100.0)
    ltf = fx.make_series(closes, volumes=np.full(120, 1000.0))
    # elle supurme mumu: swing high uzerine igne, kapanis geride, hacim 2x
    c = ltf.candles[-1]
    sw = max(x.high for x in ltf.candles[-98:-2])
    c.high = sw * 1.01
    c.close = sw * 0.998
    c.volume = 2000.0
    assert eng.on_scan("BUSDT", None, ltf, None) == 1
    row = db.query_one("SELECT * FROM challenger_signals")
    assert row["strategy"] == "S6_SWEEP" and row["direction"] == "SHORT"
    assert row["stop"] > c.high  # stop ekstremum otesinde


def test_s4_carry_sign_mapping(tmp_path):
    eng, db = _eng(tmp_path)
    htf = fx.make_series(np.full(60, 100.0), interval="240")
    ltf = fx.make_series(np.full(60, 100.0))
    eng.on_scan("CUSDT", htf, ltf, funding=+0.002)   # yillik ~%219 pozitif
    eng.on_scan("DUSDT", htf, ltf, funding=-0.002)
    a = db.query_one("SELECT direction FROM challenger_signals WHERE pair='CUSDT'")
    b = db.query_one("SELECT direction FROM challenger_signals WHERE pair='DUSDT'")
    assert a["direction"] == "SHORT" and b["direction"] == "LONG"
    # notr funding sinyal uretmez
    assert eng.on_scan("EUSDT", htf, ltf, funding=0.00001) == 0


def test_same_candle_stop_and_tp_is_conservative_loss(tmp_path):
    eng, db = _eng(tmp_path)
    db.execute("INSERT INTO challenger_signals(strategy,pair,direction,"
               "created_utc,entry_ts,entry,stop,tp,timeout_bars,cluster_id) "
               "VALUES('S2_DONCHIAN','XUSDT','LONG','2026-08-04T00:00:00Z',"
               "1000000,100,98,104,96,'S2:L1')")
    _put_candles(db, "XUSDT", [(105.0, 97.0, 100.0)], start_ts=1_900_000)
    eng.evaluate_open("XUSDT")
    row = db.query_one("SELECT * FROM challenger_signals")
    assert row["outcome"] == "LOSS" and row["ambiguous"] == 1


def test_timeout_closes_expired_with_close_based_r(tmp_path):
    eng, db = _eng(tmp_path)
    db.execute("INSERT INTO challenger_signals(strategy,pair,direction,"
               "created_utc,entry_ts,entry,stop,tp,timeout_bars,cluster_id) "
               "VALUES('S1_TSMOM','YUSDT','LONG','2026-08-04T00:00:00Z',"
               "1000000,100,98,112,3,'S1:L1')")
    _put_candles(db, "YUSDT", [(101, 99.5, 100.5)] * 3, start_ts=1_900_000)
    eng.evaluate_open("YUSDT")
    row = db.query_one("SELECT * FROM challenger_signals")
    assert row["outcome"] == "EXPIRED"
    assert abs(row["r_multiple"] - 0.25) < 0.01     # (100.5-100)/2


def test_evaluation_never_reads_entry_candle_or_before(tmp_path):
    """Bakis-oncesi yasagi: giris mumu ve oncesi karara giremez (sampiyonda
    dort kez tekrarlanan hata sinifinin aday motorunda dogmamis hali)."""
    eng, db = _eng(tmp_path)
    db.execute("INSERT INTO challenger_signals(strategy,pair,direction,"
               "created_utc,entry_ts,entry,stop,tp,timeout_bars,cluster_id) "
               "VALUES('S6_SWEEP','ZUSDT','SHORT','2026-08-04T00:00:00Z',"
               "1000000,100,103,94,96,'S6:S1')")
    # giris mumu (ts=entry_ts) devasa: hem stop hem tp gorur - SAYILMAMALI
    _put_candles(db, "ZUSDT", [(110.0, 90.0, 100.0)], start_ts=1_000_000)
    eng.evaluate_open("ZUSDT")
    assert db.query_one("SELECT status FROM challenger_signals")["status"] == "OPEN"
    _put_candles(db, "ZUSDT", [(101.0, 93.5, 95.0)], start_ts=1_900_000)
    eng.evaluate_open("ZUSDT")
    row = db.query_one("SELECT * FROM challenger_signals")
    assert row["outcome"] == "WIN"                  # tp 94'e degdi, stop'a degmedi


def test_champion_stats_byte_identical_with_challengers_active(tmp_path):
    """IZOLASYON GARANTISI: adaylar ayni DB'de yazarken sampiyonun
    muhasebesi bayt-bayt degismemeli."""
    tracker, db = _make_tracker(tmp_path)
    ltf = fx.make_series(np.full(70, 101.5))
    ltf.candles[-1].ts = 1_000_000
    tracker.maybe_track(_signal(), ltf)
    _feed(tracker, closes=[100.8, 106.2], lows=[100.5, 105.5],
          highs=[101.2, 106.5], start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")
    once = json.dumps(tracker.stats(), sort_keys=True)
    eng = ChallengerEngine(db, "15")
    htf = fx.make_series(np.full(60, 100.0), interval="240")
    closes = np.concatenate([np.full(98, 100.0), [100.0, 106.0]])
    eng.on_scan("AUSDT", htf, fx.make_series(closes), +0.002)
    eng.evaluate_open("AUSDT")
    sonra = json.dumps(tracker.stats(), sort_keys=True)
    assert once == sonra, "aday motoru sampiyon muhasebesine sizdi"
    st = eng.stats()
    assert st["strategies"]["S2_DONCHIAN"]["open"] >= 1


def test_stats_shape_and_net_below_gross(tmp_path):
    eng, db = _eng(tmp_path)
    db.execute("INSERT INTO challenger_signals(strategy,pair,direction,"
               "created_utc,entry_ts,entry,stop,tp,timeout_bars,cluster_id,"
               "status,outcome,r_multiple,hold_bars) VALUES('S1_TSMOM',"
               "'AUSDT','LONG','2026-08-04T00:00:00Z',1000000,100,98,106,"
               "192,'S1:L1','CLOSED','WIN',3.0,20)")
    s = eng.stats()["strategies"]["S1_TSMOM"]
    assert s["decided"] == 1 and s["win_rate"] == 1.0
    assert s["net_r"] < s["gross_r"]                # maliyet dusuldu
