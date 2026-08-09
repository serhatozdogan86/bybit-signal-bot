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
               "status,outcome,r_multiple,hold_bars,regime) VALUES("
               "'S1_TSMOM','AUSDT','LONG','2026-08-04T00:00:00Z',1000000,"
               "100,98,106,192,'S1:L1','CLOSED','WIN',3.0,20,2)")
    s = eng.stats()["strategies"]["S1_TSMOM"]
    assert s["decided"] == 1 and s["win_rate"] == 1.0
    assert s["net_r"] < s["gross_r"]                # maliyet dusuldu


def test_challenger_stats_in_gist_backup_payload(tmp_path):
    """IZLEME BOSLUGU KAPALI KALSIN: aday verisi yedege girmezse uzaktan
    denetlenemez (bugun yasandi). build_files 0_challengers.json icermeli."""
    from unittest.mock import MagicMock
    from app.services.gist_backup import GistBackup
    tracker, db = _make_tracker(tmp_path)
    eng = ChallengerEngine(db, "15")
    gb = GistBackup(MagicMock(), tracker, symbols=["TESTUSDT"],
                    intervals=["15"])
    gb.set_challengers(eng)
    files = gb.build_files()
    assert "0_challengers.json" in files
    payload = json.loads(files["0_challengers.json"])
    assert "strategies" in payload and "S6_SWEEP" in payload["strategies"]
    # motor baglanmadan da yedek COKMEmeli
    gb2 = GistBackup(MagicMock(), tracker, symbols=["TESTUSDT"],
                     intervals=["15"])
    assert "0_challengers.json" in gb2.build_files()


def test_per_strategy_open_caps(tmp_path):
    """Tavan stratejiye gore: uzun tutan adaylar slot kitliligi yuzunden
    veri toplayamaz hale gelmemeli (rejim-2 duzeltmesi)."""
    from app.services.challengers import MAX_OPEN, MAX_OPEN_DEFAULT
    eng, db = _eng(tmp_path)
    assert MAX_OPEN["S1_TSMOM"] > MAX_OPEN["S3_MEANREV"]
    for i in range(MAX_OPEN["S3_MEANREV"]):
        db.execute("INSERT INTO challenger_signals(strategy,pair,direction,"
                   "created_utc,entry_ts,entry,stop,tp,timeout_bars,"
                   "cluster_id,regime) VALUES('S3_MEANREV',?,'LONG','x',1,"
                   "100,98,104,96,?,2)", (f"P{i}USDT", f"S3:L{i}"))
    assert eng._crowded("S3_MEANREV") is True
    assert eng._crowded("S1_TSMOM") is False      # ayri tavan, ayri sayac
    assert MAX_OPEN.get("BILINMEYEN", MAX_OPEN_DEFAULT) == MAX_OPEN_DEFAULT


def test_old_regime_rows_excluded_from_stats(tmp_path):
    """Ornekleme rejimi degisince eski kohort BIRLESTIRILMEZ: farkli
    kisitla toplandi. Tabloda kalir, hesaba girmez, sayisi raporlanir."""
    from app.services.challengers import SAMPLING_REGIME
    eng, db = _eng(tmp_path)
    ins = ("INSERT INTO challenger_signals(strategy,pair,direction,"
           "created_utc,entry_ts,entry,stop,tp,timeout_bars,cluster_id,"
           "status,outcome,r_multiple,hold_bars,regime) VALUES('S1_TSMOM',"
           "?,'LONG','x',1,100,98,106,192,'S1:L1','CLOSED','WIN',3.0,20,?)")
    db.execute(ins, ("ESKIUSDT", 1))              # tavan oncesi
    db.execute(ins, ("YENIUSDT", SAMPLING_REGIME))
    s = eng.stats()
    assert s["sampling_regime"] == SAMPLING_REGIME
    assert s["retired_rows"] == 1
    assert s["strategies"]["S1_TSMOM"]["decided"] == 1   # yalniz yeni kohort


def test_new_signals_stamped_with_current_regime(tmp_path):
    from app.services.challengers import SAMPLING_REGIME
    eng, db = _eng(tmp_path)
    htf = fx.make_series(np.full(60, 100.0), interval="240")
    closes = np.concatenate([np.full(98, 100.0), [100.0, 106.0]])
    eng.on_scan("AUSDT", htf, fx.make_series(closes), None)
    r = db.query_one("SELECT regime FROM challenger_signals")
    assert r["regime"] == SAMPLING_REGIME


# --------------- S7 Wyckoff Spring+Test (tasarim: 8eecb5a, BIREBIR) --------
def _s7_series(spring_vol=2000.0, test_vol=500.0, test_low=99.05,
               mid_low=99.5, spring_low=98.8, n=110):
    """Spring+Test senaryosu: sw_low=99.0 (idx -30), spring idx -3,
    ara mum idx -2, aday test mumu = son mum (giris onun kapanisinda)."""
    ltf = fx.make_series(np.full(n, 100.0), volumes=np.full(n, 1000.0))
    ltf.candles[-30].low = 99.0                  # 96-bar penceresinin dibi
    sp = ltf.candles[-3]                         # SPRING: dibi kir + don
    sp.low, sp.close, sp.volume = spring_low, 100.0, spring_vol
    ltf.candles[-2].low = mid_low                # ara mum (gecersizlik yok)
    t = ltf.candles[-1]                          # TEST adayi (son mum)
    t.low, t.close, t.volume = test_low, 100.0, test_vol
    return ltf


def test_s7_spring_then_low_volume_test_generates_long(tmp_path):
    """Tasarim: spring (yuksek hacim + geri donus) -> 1-6 bar icinde dusuk
    hacimli test -> giris test kapanisinda, stop spring dibinin altinda."""
    eng, db = _eng(tmp_path)
    assert eng.on_scan("W1USDT", None, _s7_series(), None) == 1
    row = db.query_one(
        "SELECT * FROM challenger_signals WHERE strategy='S7_WYCKOFF'")
    assert row is not None and row["direction"] == "LONG"
    assert row["entry"] == 100.0                 # test mumunun kapanisi
    assert row["stop"] < 98.8                    # spring_low - 0.25xATR
    risk = row["entry"] - row["stop"]
    assert abs(row["tp"] - (row["entry"] + 2 * risk)) < 1e-6   # TP 2R
    assert row["timeout_bars"] == 96


def test_s7_high_volume_test_rejected(tmp_path):
    """TERS HACIM FILTRESI - S7'nin varlik nedeni: test mumunda hacim
    kurumamissa (>0.7xSMA20) kurulum YOK. (S6 tam tersini ister.)"""
    eng, _ = _eng(tmp_path)
    assert eng.on_scan("W2USDT", None, _s7_series(test_vol=2000.0), None) == 0


def test_s7_break_below_spring_low_invalidates(tmp_path):
    """Gecersizlik: spring ile test arasinda low <= spring_low -> iptal."""
    eng, _ = _eng(tmp_path)
    assert eng.on_scan("W3USDT", None, _s7_series(mid_low=98.7), None) == 0
    # test mumunun kendisi spring dibinin ALTINA sarkarsa da kurulum yok
    eng2, _ = _eng(tmp_path / "b")
    assert eng2.on_scan("W3BUSDT", None, _s7_series(test_low=98.7), None) == 0


def test_s7_test_window_is_six_bars(tmp_path):
    """Tasarim: test, spring'den sonraki 1-6 bar icinde gelmeli; 7. barda
    gelen test kurulumu tetiklemez."""
    eng, _ = _eng(tmp_path)
    ltf = fx.make_series(np.full(110, 100.0), volumes=np.full(110, 1000.0))
    ltf.candles[-40].low = 99.0
    sp = ltf.candles[-8]                          # spring 7 bar once (>6)
    sp.low, sp.close, sp.volume = 98.8, 100.0, 2000.0
    t = ltf.candles[-1]
    t.low, t.close, t.volume = 99.05, 100.0, 500.0
    assert eng.on_scan("W4USDT", None, ltf, None) == 0


def test_s7_short_mirror_upthrust(tmp_path):
    """Ayna kurgu: upthrust (tepeyi kir + geri don, yuksek hacim) ->
    dusuk hacimli test -> SHORT; stop upthrust tepesinin ustunde."""
    eng, db = _eng(tmp_path)
    ltf = fx.make_series(np.full(110, 100.0), volumes=np.full(110, 1000.0))
    ltf.candles[-30].high = 101.0                 # pencerenin tepesi
    up = ltf.candles[-3]                          # UPTHRUST
    up.high, up.close, up.volume = 101.2, 100.0, 2000.0
    ltf.candles[-2].high = 100.5
    t = ltf.candles[-1]
    t.high, t.close, t.volume = 100.96, 100.0, 500.0
    assert eng.on_scan("W5USDT", None, ltf, None) == 1
    row = db.query_one(
        "SELECT * FROM challenger_signals WHERE strategy='S7_WYCKOFF'")
    assert row["direction"] == "SHORT"
    assert row["stop"] > 101.2                    # upthrust tepesi + tampon
    risk = row["stop"] - row["entry"]
    assert abs(row["tp"] - (row["entry"] - 2 * risk)) < 1e-6


def test_s7_no_spring_no_signal(tmp_path):
    """Duz seri (spring yok) hicbir S7 sinyali uretmez."""
    eng, _ = _eng(tmp_path)
    ltf = fx.make_series(np.full(110, 100.0), volumes=np.full(110, 1000.0))
    assert eng.on_scan("W6USDT", None, ltf, None) == 0


# ---------------- v1.2: detay penceresi tek-kaynak sozlugu ----------------
def test_strategy_info_covers_all_active_strategies():
    """SURUKLENME YASAGI: her aktif stratejinin (S1-S6, beklemedekiler
    haric) STRATEGY_INFO'da tam kaydi olmali. UI metni elle yazmaz."""
    from app.services import challengers as ch
    for strat in ch.STRATEGIES:
        info = ch.STRATEGY_INFO.get(strat)
        assert info, f"{strat} icin STRATEGY_INFO kaydi yok"
        assert len(info["name"]) >= 3
        assert len(info["how"]) >= 80, f"{strat}.how cok kisa (2-4 cumle olmali)"
        for key in ("giris", "stop", "hedef", "zaman_asimi", "tavan",
                    "filtreler"):
            assert info["params"].get(key), f"{strat}.params.{key} bos"
        assert info["honesty"], f"{strat}.honesty bos"
        assert any("yatırım tavsiyesi değildir" in n for n in info["honesty"])
        assert any(str(ch.SAMPLING_REGIME) in n for n in info["honesty"])


def test_strategy_info_numbers_derived_from_constants():
    """Sayisal parametreler GERCEK sabitlerden turetilmeli - sabit degisince
    aciklama otomatik degisir, eski kalamaz."""
    from app.services import challengers as ch
    for strat in ch.STRATEGIES:
        cap = ch.MAX_OPEN.get(strat, ch.MAX_OPEN_DEFAULT)
        assert str(cap) in ch.STRATEGY_INFO[strat]["params"]["tavan"]
    p1 = ch.STRATEGY_INFO["S1_TSMOM"]["params"]
    assert f"{ch.TREND_STOP_ATR:g}" in p1["stop"]
    assert f"{ch.TREND_TP_ATR:g}" in p1["hedef"]
    assert str(ch.TREND_TIMEOUT) in p1["zaman_asimi"]
    assert f"EMA{ch.TSMOM_EMA_N}" in p1["giris"]
    p3 = ch.STRATEGY_INFO["S3_MEANREV"]["params"]
    assert str(ch.FAST_TIMEOUT) in p3["zaman_asimi"]
    assert f"{ch.S3_ADX_MAX:g}" in p3["giris"]
    p4 = ch.STRATEGY_INFO["S4_CARRY"]["params"]
    assert f"%{ch.S4_ANN_FUNDING * 100:g}" in p4["giris"]
    p6 = ch.STRATEGY_INFO["S6_SWEEP"]["params"]
    assert str(ch.S6_SWING_N) in p6["giris"]
    assert f"{ch.S6_VOL_MULT:g}" in p6["giris"]
    p7 = ch.STRATEGY_INFO["S7_WYCKOFF"]["params"]
    assert str(ch.S7_SWING_N) in p7["giris"]
    assert f"{ch.S7_VOL_SPRING:g}" in p7["giris"]
    assert f"{ch.S7_VOL_TEST:g}" in p7["giris"]
    assert str(ch.S7_TEST_WINDOW) in p7["giris"]
    assert f"{ch.S7_ATR_PROX:g}" in p7["stop"]
    assert str(ch.FAST_TIMEOUT) in p7["zaman_asimi"]


def test_challengers_endpoint_returns_strategy_info(tmp_path):
    """/challengers arayuzun okudugu tek kapidir - strategy_info donmeli."""
    from unittest.mock import MagicMock
    from app.server import create_app
    from app.services.database import Database
    from app.services.sqlite_state_store import SQLiteStateStore
    db = Database(str(tmp_path / "ep.db"))
    eng = ChallengerEngine(db, "15")
    sch = MagicMock()
    sch.challengers = eng
    app = create_app(SQLiteStateStore(db), sch, None)
    data = app.test_client().get("/challengers").get_json()
    assert "strategy_info" in data and "recent" in data
    for strat in data["strategies"]:
        info = data["strategy_info"].get(strat)
        assert info and info["how"] and info["params"] and info["honesty"]


def test_stats_carry_ambiguous_and_hold_median(tmp_path):
    """Detay penceresi 1. bolum girdileri: belirsiz sayisi + tutus medyani."""
    eng, db = _eng(tmp_path)
    ins = ("INSERT INTO challenger_signals(strategy,pair,direction,"
           "created_utc,entry_ts,entry,stop,tp,timeout_bars,cluster_id,"
           "status,outcome,r_multiple,hold_bars,ambiguous,regime) VALUES("
           "'S1_TSMOM',?,'LONG','x',1,100,98,106,192,?,'CLOSED',?,?,?,?,2)")
    db.execute(ins, ("AUSDT", "S1:L1", "WIN", 3.0, 20, 0))
    db.execute(ins, ("BUSDT", "S1:L2", "LOSS", -1.0, 10, 1))
    s = eng.stats()["strategies"]["S1_TSMOM"]
    assert s["ambiguous"] == 1
    assert s["hold_bars_median"] == 15.0            # medyan(20, 10)


def test_recent_rows_carry_net_r(tmp_path):
    """Son-15 tablosunun net R'si SUNUCUDA hesaplanir (tek kaynak _net_r;
    JS'te maliyet modeli kopyasi tutulmaz)."""
    eng, db = _eng(tmp_path)
    db.execute("INSERT INTO challenger_signals(strategy,pair,direction,"
               "created_utc,entry_ts,entry,stop,tp,timeout_bars,cluster_id,"
               "status,outcome,r_multiple,hold_bars,regime) VALUES("
               "'S2_DONCHIAN','AUSDT','LONG','x',1,100,98,106,192,'S2:L1',"
               "'CLOSED','WIN',3.0,20,2)")
    db.execute("INSERT INTO challenger_signals(strategy,pair,direction,"
               "created_utc,entry_ts,entry,stop,tp,timeout_bars,cluster_id) "
               "VALUES('S2_DONCHIAN','BUSDT','LONG','x',1,100,98,106,192,"
               "'S2:L2')")
    rows = {r["pair"]: r for r in eng.recent(10)}
    assert rows["AUSDT"]["net_r"] is not None
    assert rows["AUSDT"]["net_r"] < 3.0             # maliyet dusuldu
    assert rows["BUSDT"]["net_r"] is None           # acik kayit: hesap yok


def test_strategy_info_texts_have_ru_entries():
    """Kural: yeni UI metinlerinin TAMAMI RU sozlugune girer. Turkce
    karakter iceren her STRATEGY_INFO metni panoda birebir anahtar olmali.
    (tavan/zaman_asimi kalip cevirisiyle donusur - RU_PAT; burada haric.)"""
    import re
    from app.dashboard import DASHBOARD_HTML
    from app.services import challengers as ch
    missing = []
    for strat in ch.STRATEGIES:
        info = ch.STRATEGY_INFO[strat]
        p = info["params"]
        for txt in (info["how"], p["giris"], p["stop"], p["hedef"],
                    p["filtreler"], *info["honesty"]):
            if not re.search(r"[çğıöşüÇĞİÖŞÜâîû]", txt):
                continue                    # dil-notru metin: ceviri gerekmez
            if f'"{txt}"' not in DASHBOARD_HTML:
                missing.append(f"{strat}: {txt[:50]}…")
    assert not missing, f"RU sozlugunde eksik metin: {missing}"
