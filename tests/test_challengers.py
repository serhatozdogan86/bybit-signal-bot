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
    """S6 emekli (2026-08-12) ama uretim MEKANIZMASI arsiv dogrulugu icin
    test edilmeye devam eder: _generate adayi hala dogru kurar; on_scan
    emeklilik filtresiyle deftere YAZMAZ."""
    eng, db = _eng(tmp_path)
    closes = np.full(120, 100.0)
    ltf = fx.make_series(closes, volumes=np.full(120, 1000.0))
    # elle supurme mumu: swing high uzerine igne, kapanis geride, hacim 2x
    c = ltf.candles[-1]
    sw = max(x.high for x in ltf.candles[-98:-2])
    c.high = sw * 1.01
    c.close = sw * 0.998
    c.volume = 2000.0
    cands = dict(eng._generate("BUSDT", None, ltf, None))
    assert "S6_SWEEP" in cands
    direction, stop, tp, timeout = cands["S6_SWEEP"]
    assert direction == "SHORT"
    assert stop > c.high  # stop ekstremum otesinde
    # emeklilik filtresi: deftere kayit dusmez
    assert eng.on_scan("BUSDT", None, ltf, None) == 0
    assert db.query_one("SELECT COUNT(*) n FROM challenger_signals")["n"] == 0


def test_s4_carry_sign_mapping(tmp_path):
    """S4 emekli (2026-08-18, CHALLENGER_DEAD) ama uretim MEKANIZMASI
    arsiv dogrulugu icin test edilir; on_scan deftere YAZMAZ (S6 emsali)."""
    eng, db = _eng(tmp_path)
    htf = fx.make_series(np.full(60, 100.0), interval="240")
    ltf = fx.make_series(np.full(60, 100.0))
    a = dict(eng._generate("CUSDT", htf, ltf, +0.002))   # yillik ~%219
    b = dict(eng._generate("DUSDT", htf, ltf, -0.002))
    assert a["S4_CARRY"][0] == "SHORT" and b["S4_CARRY"][0] == "LONG"
    # notr funding sinyal uretmez
    assert "S4_CARRY" not in dict(eng._generate("EUSDT", htf, ltf, 0.00001))
    # emeklilik filtresi: deftere kayit dusmez
    assert eng.on_scan("CUSDT", htf, ltf, funding=+0.002) == 0
    assert db.query_one("SELECT COUNT(*) n FROM challenger_signals")["n"] == 0


def _s8_ltf(last):
    """Son 15dk kapanisi 'last', oncesi duz 100 -> fiyat teyit yonu."""
    closes = np.full(60, 100.0)
    closes[-1] = last
    return fx.make_series(closes)


def test_s8_fundsqueeze_price_confirmed_long_and_short(tmp_path):
    eng, _ = _eng(tmp_path)
    htf = fx.make_series(np.full(60, 100.0), interval="240")
    # derin NEGATIF funding + fiyat YUKARI donuyor -> LONG
    c = dict(eng._generate("AUSDT", htf, _s8_ltf(100.5), funding=-0.001))
    assert "S8_FUNDSQUEEZE" in c
    d, stop, tp, _ = c["S8_FUNDSQUEEZE"]
    assert d == "LONG" and stop < 100.5 < tp
    # derin POZITIF funding + fiyat ASAGI donuyor -> SHORT
    c = dict(eng._generate("BUSDT", htf, _s8_ltf(99.5), funding=+0.001))
    assert "S8_FUNDSQUEEZE" in c and c["S8_FUNDSQUEEZE"][0] == "SHORT"


def test_s8_requires_price_confirmation(tmp_path):
    """S4'ten AYRISMA 1: fiyat teyidi. Derin funding ama fiyat ters yonde
    teyit vermezse S8 fire ETMEZ; S4 (teyit istemez) yine firlar."""
    eng, _ = _eng(tmp_path)
    htf = fx.make_series(np.full(60, 100.0), interval="240")
    # derin negatif funding AMA fiyat ASAGI (LONG teyidi yok)
    c = dict(eng._generate("AUSDT", htf, _s8_ltf(99.5), funding=-0.001))
    assert "S8_FUNDSQUEEZE" not in c
    assert "S4_CARRY" in c and c["S4_CARRY"][0] == "LONG"


def test_s8_threshold_deeper_than_s4(tmp_path):
    """S4'ten AYRISMA 2: daha uc esik. ann ~%44: S4 (%30) firlar ama
    S8 (%60) firlamaz — fiyat teyidi dogru yonde olsa bile."""
    eng, _ = _eng(tmp_path)
    htf = fx.make_series(np.full(60, 100.0), interval="240")
    # ann = 0.0004*1095 ~ +0.438; pozitif -> S4 SHORT; fiyat asagi (S8 short teyidi)
    c = dict(eng._generate("AUSDT", htf, _s8_ltf(99.5), funding=+0.0004))
    assert "S4_CARRY" in c and c["S4_CARRY"][0] == "SHORT"
    assert "S8_FUNDSQUEEZE" not in c        # esik altinda -> S8 yok


def test_s8_no_funding_no_signal(tmp_path):
    eng, _ = _eng(tmp_path)
    htf = fx.make_series(np.full(60, 100.0), interval="240")
    c = dict(eng._generate("AUSDT", htf, _s8_ltf(100.5), funding=None))
    assert "S8_FUNDSQUEEZE" not in c


def _s9_ltf(hour_utc):
    """Son mumu verilen UTC saatine damgalanmis duz seri."""
    ltf = fx.make_series(np.full(60, 100.0))
    # gun 1000, istenen saat: ts = (1000*24 + saat) * 3600 * 1000
    ltf.candles[-1].ts = (1000 * 24 + hour_utc) * 3_600_000
    return ltf


def test_s9_gece_only_btc_only_window(tmp_path):
    eng, _ = _eng(tmp_path)
    # 21:xx penceresi + BTCUSDT -> LONG, zaman-cikisli kurgu
    c = dict(eng._generate("BTCUSDT", None, _s9_ltf(21), None))
    assert "S9_GECE" in c
    d, stop, tp, timeout = c["S9_GECE"]
    assert d == "LONG" and timeout == 8
    assert stop < 100.0 < tp
    assert tp > 100.0 * 1.5          # sentetik hedef gercekten erisilemez
    # ayni saat baska parite -> YOK (v1 yalniz BTC)
    assert "S9_GECE" not in dict(eng._generate("ETHUSDT", None, _s9_ltf(21), None))
    # BTC ama pencere disi saatler -> YOK
    for h in (20, 22, 3):
        assert "S9_GECE" not in dict(eng._generate("BTCUSDT", None, _s9_ltf(h), None))


def test_s9_gece_one_entry_per_evening_and_time_exit(tmp_path):
    eng, db = _eng(tmp_path)
    ltf = _s9_ltf(21)
    assert eng.on_scan("BTCUSDT", None, ltf, None) == 1
    # ayni aksam ikinci tarama (15dk sonra, ayni 4H kovasi) -> dedup
    ltf2 = _s9_ltf(21)
    ltf2.candles[-1].ts += 900_000              # 21:15
    assert eng.on_scan("BTCUSDT", None, ltf2, None) == 0
    # zaman-cikisi: 8 duz mum -> EXPIRED, R = pnl/risk
    row = db.query_one("SELECT * FROM challenger_signals WHERE strategy='S9_GECE'")
    risk = row["entry"] - row["stop"]
    final_close = row["entry"] + 0.5 * risk     # 2 saatte +0.5R suruklendi
    _put_candles(db, "BTCUSDT",
                 [(row["entry"] * 1.001, row["entry"] * 0.999, row["entry"])] * 7
                 + [(final_close * 1.001, final_close * 0.999, final_close)],
                 start_ts=row["entry_ts"] + 900_000)
    eng.evaluate_open("BTCUSDT")
    row = db.query_one("SELECT * FROM challenger_signals WHERE strategy='S9_GECE'")
    assert row["outcome"] == "EXPIRED" and row["hold_bars"] == 8
    assert abs(row["r_multiple"] - 0.5) < 0.05


def test_s9_no_reentry_same_evening_after_early_stop(tmp_path):
    """Inceleme 2026-08-13: 'gunde tek kayit' on-kaydinin kritik yolu.
    Ilk sinyal ayni aksam STOP olsa bile (status CLOSED), cluster_id dedup'u
    ayni 4H kovasinda yeniden girisi ENGELLEMELI."""
    eng, db = _eng(tmp_path)
    ltf = _s9_ltf(21)
    assert eng.on_scan("BTCUSDT", None, ltf, None) == 1
    row = db.query_one("SELECT * FROM challenger_signals WHERE strategy='S9_GECE'")
    # hemen stop: ilk mumda stop seviyesinin altina in
    _put_candles(db, "BTCUSDT",
                 [(row["entry"], row["stop"] - 1.0, row["stop"] - 0.5)],
                 start_ts=row["entry_ts"] + 900_000)
    eng.evaluate_open("BTCUSDT")
    assert db.query_one("SELECT outcome o FROM challenger_signals WHERE "
                        "strategy='S9_GECE'")["o"] == "LOSS"
    # ayni aksam 21:30 taramasi: yeniden giris YOK
    ltf2 = _s9_ltf(21)
    ltf2.candles[-1].ts += 2 * 900_000          # 21:30
    assert eng.on_scan("BTCUSDT", None, ltf2, None) == 0
    n = db.query_one("SELECT COUNT(*) n FROM challenger_signals WHERE "
                     "strategy='S9_GECE'")["n"]
    assert n == 1


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
    hacimli test -> giris test kapanisinda, stop spring dibinin altinda.
    S7 emekli (2026-08-18): mekanizma _generate ile arsiv dogrulugu icin
    test edilir; on_scan deftere YAZMAZ (S6 emsali)."""
    eng, db = _eng(tmp_path)
    c = dict(eng._generate("W1USDT", None, _s7_series(), None))
    assert "S7_WYCKOFF" in c
    d, stop, tp, timeout = c["S7_WYCKOFF"]
    assert d == "LONG"
    assert stop < 98.8                           # spring_low - 0.25xATR
    risk = 100.0 - stop                          # giris = test kapanisi 100
    assert abs(tp - (100.0 + 2 * risk)) < 1e-6   # TP 2R
    assert timeout == 96
    # emeklilik filtresi: deftere kayit dusmez
    assert eng.on_scan("W1USDT", None, _s7_series(), None) == 0
    assert db.query_one("SELECT COUNT(*) n FROM challenger_signals")["n"] == 0


def test_s7_high_volume_test_rejected(tmp_path):
    """TERS HACIM FILTRESI - S7'nin varlik nedeni: test mumunda hacim
    kurumamissa (>0.7xSMA20) kurulum YOK. (S6 tam tersini ister.)"""
    eng, _ = _eng(tmp_path)
    c = dict(eng._generate("W2USDT", None, _s7_series(test_vol=2000.0), None))
    assert "S7_WYCKOFF" not in c


def test_s7_break_below_spring_low_invalidates(tmp_path):
    """Gecersizlik: spring ile test arasinda low <= spring_low -> iptal."""
    eng, _ = _eng(tmp_path)
    assert "S7_WYCKOFF" not in dict(
        eng._generate("W3USDT", None, _s7_series(mid_low=98.7), None))
    # test mumunun kendisi spring dibinin ALTINA sarkarsa da kurulum yok
    assert "S7_WYCKOFF" not in dict(
        eng._generate("W3BUSDT", None, _s7_series(test_low=98.7), None))


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
    assert "S7_WYCKOFF" not in dict(eng._generate("W4USDT", None, ltf, None))


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
    c = dict(eng._generate("W5USDT", None, ltf, None))
    assert "S7_WYCKOFF" in c
    d, stop, tp, _ = c["S7_WYCKOFF"]
    assert d == "SHORT"
    assert stop > 101.2                           # upthrust tepesi + tampon
    risk = stop - 100.0                           # giris = test kapanisi 100
    assert abs(tp - (100.0 - 2 * risk)) < 1e-6


def test_s7_no_spring_no_signal(tmp_path):
    """Duz seri (spring yok) hicbir S7 sinyali uretmez."""
    eng, _ = _eng(tmp_path)
    ltf = fx.make_series(np.full(110, 100.0), volumes=np.full(110, 1000.0))
    assert "S7_WYCKOFF" not in dict(eng._generate("W6USDT", None, ltf, None))


# -------- S11 Sikisma Kirilimi (on-kayit ideas.md 2026-08-17, BIREBIR) -------
def _s11_htf(fire_close=110.0, n=60):
    """>=6 bar sikisma (duz 100, TR=2, sigma=0 -> ACIK) + son kapanmis 4H
    barda genisleme (kapanis sicramasi sigma'yi buyutur -> KAPALI)."""
    htf = fx.make_series(np.full(n, 100.0), interval="240")
    for c in htf.candles:
        c.high, c.low = 101.0, 99.0
    f = htf.candles[-2]                  # son KAPANMIS 4H mum (drop_last)
    f.close = fire_close
    f.high, f.low = fire_close + 0.5, fire_close - 0.5
    return htf


def test_s11_squeeze_release_long(tmp_path):
    """Sikisma cozulup 4H kapanis aralik USTUNDE + momentum pozitif -> LONG;
    stop = sikisma araliginin ALT ucu (dogal stop), hedef 2R."""
    eng, db = _eng(tmp_path)
    ltf = fx.make_series(np.full(60, 110.0))
    assert eng.on_scan("SQUSDT", _s11_htf(110.0), ltf, None) == 1
    row = db.query_one(
        "SELECT * FROM challenger_signals WHERE strategy='S11_SQUEEZE'")
    assert row["direction"] == "LONG"
    assert abs(row["stop"] - 99.0) < 1e-9          # aralik alt ucu
    risk = row["entry"] - row["stop"]
    assert abs(row["tp"] - (row["entry"] + 2 * risk)) < 1e-6
    assert row["timeout_bars"] == 192


def test_s11_squeeze_release_short_mirror(tmp_path):
    """Ayna kurgu: kapanis aralik ALTINDA + momentum negatif -> SHORT;
    stop = aralik UST ucu."""
    eng, _ = _eng(tmp_path)
    ltf = fx.make_series(np.full(60, 90.0))
    c = dict(eng._generate("SQ2USDT", _s11_htf(90.0), ltf, None))
    assert "S11_SQUEEZE" in c
    d, stop, tp, timeout = c["S11_SQUEEZE"]
    assert d == "SHORT" and abs(stop - 101.0) < 1e-9
    assert tp < 90.0                                # hedef girisin altinda


def test_s11_no_release_no_signal(tmp_path):
    """Sikisma COZULMEDEN (duz seri) sinyal yok - S2'den ayrisan onkosul."""
    eng, _ = _eng(tmp_path)
    htf = fx.make_series(np.full(60, 100.0), interval="240")
    for c in htf.candles:
        c.high, c.low = 101.0, 99.0
    ltf = fx.make_series(np.full(60, 100.0))
    assert "S11_SQUEEZE" not in dict(eng._generate("SQ3USDT", htf, ltf, None))


def test_s11_breakout_without_squeeze_precondition_silent(tmp_path):
    """SIKISMA ONKOSULU olmadan kirilim S11'i tetiklemez (S2 tetikleyebilir;
    ayrisma tam olarak budur): trendli seri her barda KAPALI durumdadir."""
    eng, _ = _eng(tmp_path)
    htf = fx.make_series(np.linspace(100.0, 160.0, 60), interval="240")
    ltf = fx.make_series(np.full(60, 161.0))
    assert "S11_SQUEEZE" not in dict(eng._generate("SQ4USDT", htf, ltf, None))


def test_s11_squeeze_run_needs_min_bars():
    """squeeze_run kisa seride None doner (guard)."""
    from app.services.challengers import squeeze_run
    xs = [100.0] * 30
    assert squeeze_run(xs, xs, xs) is None


# ------ S12 Hacim Kapili Seans Kirilimi (on-kayit 2026-08-17, BIREBIR) ------
def _s12_htf(open_vol=3000.0, n_bars=158):
    """Gun basina 6x4H mum, ts gercek gun hizasinda. n_bars=158 ->
    son kapanmis mum (idx 156) = 26. gunun 00:00 acilis mumu."""
    htf = fx.make_series(np.full(n_bars, 100.0), interval="240",
                         volumes=np.full(n_bars, 1000.0))
    for i, c in enumerate(htf.candles):
        c.ts = i * 14_400_000
    # Donchian tavanini (son 20 kapanmis 4H bar penceresi) uzakta tut ki
    # kirilim S2'yi degil yalniz S12'yi tetiklesin
    htf.candles[150].high = 106.0
    if n_bars > 156:
        op = htf.candles[156]
        op.high, op.low, op.volume = 101.0, 99.0, open_vol
    return htf


def _s12_ltf(prev_close=100.5, last_close=102.0, hour=5.0):
    """Son 15dk mumu 26. gunde 'hour' saatine damgali; kenar-tetik kirilimi."""
    closes = np.full(60, 100.0)
    closes[-2], closes[-1] = prev_close, last_close
    ltf = fx.make_series(closes)
    base = 156 * 14_400_000              # 26. gun 00:00 UTC
    for i, c in enumerate(ltf.candles):
        c.ts = base + int(hour * 3_600_000) - (59 - i) * 900_000
    return ltf


def test_s12_relvol_long_with_day_end_timeout(tmp_path):
    """Hacim kapisi acik (3000 >= 2x1000) + 15dk kapanis aralik ustune ->
    LONG; stop aralik alti; zaman asimi = gun sonuna kalan bar sayisi."""
    eng, db = _eng(tmp_path)
    assert eng.on_scan("RVUSDT", _s12_htf(), _s12_ltf(hour=5.0), None) == 1
    row = db.query_one(
        "SELECT * FROM challenger_signals WHERE strategy='S12_RELVOL'")
    assert row["direction"] == "LONG" and row["entry"] == 102.0
    assert abs(row["stop"] - 99.0) < 1e-9
    # 05:00 girisi -> son cikis mumu 00:00'da kapanir: (24-5)*4 - 1 = 75
    assert row["timeout_bars"] == 75
    assert row["tp"] > row["entry"] * 3           # sentetik hedef erisilemez
    assert row["cluster_id"] == "S12_RELVOL:LD26"  # kume = takvim gunu


def test_s12_volume_gate_blocks_ordinary_open(tmp_path):
    """AYRISTIRAN OGE - hacim kapisi: acilis hacmi 2x esigin altindaysa
    ayni kirilim sinyal URETMEZ (Zarattini bulgusunun ozu)."""
    eng, _ = _eng(tmp_path)
    c = dict(eng._generate("RV2USDT", _s12_htf(open_vol=1500.0),
                           _s12_ltf(hour=5.0), None))
    assert "S12_RELVOL" not in c


def test_s12_waits_for_opening_bar_close(tmp_path):
    """00:00-04:00 arasi (acilis mumu daha kapanmadan) islem yok."""
    eng, _ = _eng(tmp_path)
    c = dict(eng._generate("RV3USDT", _s12_htf(n_bars=157),
                           _s12_ltf(hour=2.0), None))
    assert "S12_RELVOL" not in c


def test_s12_edge_trigger_and_day_end_guard(tmp_path):
    """Kenar tetik: onceki kapanis zaten disaridaysa sinyal yok; gun sonuna
    <1 bar kala da sinyal yok (cikis mumu kalmadi)."""
    eng, _ = _eng(tmp_path)
    c = dict(eng._generate("RV4USDT", _s12_htf(),
                           _s12_ltf(prev_close=103.0, last_close=103.5), None))
    assert "S12_RELVOL" not in c
    c = dict(eng._generate("RV5USDT", _s12_htf(),
                           _s12_ltf(hour=23.75), None))
    assert "S12_RELVOL" not in c


def test_s12_one_entry_per_day_per_direction(tmp_path):
    """On-kayit: gunde yon basina TEK giris. Ilk giris ayni gun stopla
    kapansa bile, gunun sonraki 4H kovasindaki yeni kirilim REDDEDILIR
    (kume+dedup takvim gunudur, 4H kovasi degil)."""
    eng, db = _eng(tmp_path)
    assert eng.on_scan("RVUSDT", _s12_htf(), _s12_ltf(hour=5.0), None) == 1
    row = db.query_one(
        "SELECT * FROM challenger_signals WHERE strategy='S12_RELVOL'")
    _put_candles(db, "RVUSDT", [(row["entry"], row["stop"] - 0.5,
                                 row["stop"] - 0.2)],
                 start_ts=row["entry_ts"] + 900_000)
    eng.evaluate_open("RVUSDT")
    assert db.query_one("SELECT outcome o FROM challenger_signals WHERE "
                        "strategy='S12_RELVOL'")["o"] == "LOSS"
    # ayni gun 09:00: farkli 4H kovasi, ayni takvim gunu -> yeniden giris YOK
    assert eng.on_scan("RVUSDT", _s12_htf(), _s12_ltf(hour=9.0), None) == 0
    n = db.query_one("SELECT COUNT(*) n FROM challenger_signals WHERE "
                     "strategy='S12_RELVOL'")["n"]
    assert n == 1


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
    p11 = ch.STRATEGY_INFO["S11_SQUEEZE"]["params"]
    assert str(ch.S11_MIN_SQUEEZE) in p11["giris"]
    assert f"{ch.S11_KC_MULT:g}" in p11["giris"]
    assert f"{ch.S11_TP_RISK:g}" in p11["hedef"]
    assert str(ch.TREND_TIMEOUT) in p11["zaman_asimi"]
    p12 = ch.STRATEGY_INFO["S12_RELVOL"]["params"]
    assert f"{ch.S12_RELVOL_MIN:g}" in p12["giris"]
    assert str(ch.S12_LOOKBACK_D) in p12["giris"]
    assert f"{ch.S12_TP_RISK:g}" in p12["hedef"]


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


def test_retired_strategies_stop_generating_keep_evaluating(tmp_path):
    """KARAR (2026-08-12, Madde 4): kenar olumu ILAN EDILMIS kosulla
    kanitlanan adaylar (S3, S6 - CHALLENGER_DEAD: kume-CI ust siniri < 0,
    >=20 kume) emekliye ayrilir. Yeni sinyal uretimi DURUR; acik
    pozisyonlar normal degerlendirilir; kapanmis kohort arsivde kalir.
    Bosalan slot butcesi (15+15) tavana bogulan S1'e devredilir: toplam
    efektif butce SABIT kalir (turetme, icat degil)."""
    from app.services.challengers import RETIRED, MAX_OPEN
    assert set(RETIRED) == {"S3_MEANREV", "S6_SWEEP",
                            "S4_CARRY", "S7_WYCKOFF"}
    assert RETIRED["S4_CARRY"] == "2026-08-18"      # ilan kosulu tarihli
    assert RETIRED["S7_WYCKOFF"] == "2026-08-18"
    # 2026-08-12 butce devri (S3/S6 -> S1: 40+30=70) KORUNUR; 2026-08-18
    # emekliliklerinde (S4/S7) slot DEVRI YOK - S1 dogrulama penceresi
    # "ayni kurallar" sozuyle acildi, tavanlar OYNAMAZ. Efektif butce
    # bilerek kuculdu.
    assert MAX_OPEN["S1_TSMOM"] == 70
    assert MAX_OPEN["S2_DONCHIAN"] == 40
    assert MAX_OPEN["S4_CARRY"] == 40               # arsiv kaydi, kullanilmaz
    # S6'nin kusursuz uretim senaryosu artik SIFIR sinyal uretmeli
    eng, db = _eng(tmp_path)
    closes = np.full(120, 100.0)
    ltf = fx.make_series(closes, volumes=np.full(120, 1000.0))
    c = ltf.candles[-1]
    sw = max(x.high for x in ltf.candles[-98:-2])
    c.high, c.close, c.volume = sw * 1.01, sw * 0.998, 2000.0
    assert eng.on_scan("RETUSDT", None, ltf, None) == 0
    assert db.query_one("SELECT COUNT(*) n FROM challenger_signals")["n"] == 0
    # ama ONCEDEN acilmis S6 pozisyonu hala degerlendirilir ve kapanir
    db.execute("INSERT INTO challenger_signals(strategy,pair,direction,"
               "created_utc,entry_ts,entry,stop,tp,timeout_bars,cluster_id,"
               "regime) VALUES('S6_SWEEP','OPNUSDT','LONG',"
               "'2026-08-10T00:00:00Z',1000000,100,98,104,96,'S6:L1',2)")
    _put_candles(db, "OPNUSDT", [(104.5, 99.5, 104.0)], start_ts=1_900_000)
    eng.evaluate_open("OPNUSDT")
    row = db.query_one("SELECT outcome FROM challenger_signals")
    assert row["outcome"] == "WIN"
    # stats emekliligi acikca raporlar (sessiz kaybolma yok)
    s = eng.stats()["strategies"]
    assert s["S6_SWEEP"].get("retired_utc")
    assert s["S3_MEANREV"].get("retired_utc")
    assert "retired_utc" not in s["S1_TSMOM"]


def test_alarms_skip_retired_challengers():
    """Emekli aday icin CHALLENGER_CAPPED/DEAD alarmi URETILMEZ - hukmu
    verilmis stratejinin alarmi kalici gurultuye doner."""
    from app.services import alarms
    ch = {"max_open": {"S3_MEANREV": 15, "S1_TSMOM": 70},
          "strategies": {
              "S3_MEANREV": {"open": 15, "clusters": 83,
                             "ci": [-0.3, -0.07], "retired_utc": "2026-08-12"},
              "S1_TSMOM": {"open": 70, "clusters": 10, "ci": None}}}
    rep = alarms.evaluate({}, None, ch)
    codes = [a["code"] for a in rep["alarms"]]
    assert "CHALLENGER_DEAD" not in codes      # emekli: hukum zaten verildi
    # emekli OLMAYAN tavandaki aday hala uyarilir
    assert "CHALLENGER_CAPPED" in codes


def test_s1_validation_window_measured_separately(tmp_path):
    """ON-KAYIT (2026-08-12): S1 secim penceresini 50 kumede doldurdu,
    kume-CI alt siniri -0.053 ile sinavi KIL PAYI GECEMEDI. Coklu
    karsilastirma kurali geregi hukum, ilan ANINDAN SONRA dogan yeni
    kohorttan verilir. Bu test pencere muhasebesini zorlar: ilan oncesi
    kayitlar dogrulama istatistigine KARISAMAZ."""
    from app.services.challengers import VALIDATION_WINDOWS
    assert "S1_TSMOM" in VALIDATION_WINDOWS      # pencere ilan edilmis olmali
    start = VALIDATION_WINDOWS["S1_TSMOM"]
    eng, db = _eng(tmp_path)
    ins = ("INSERT INTO challenger_signals(strategy,pair,direction,"
           "created_utc,entry_ts,entry,stop,tp,timeout_bars,cluster_id,"
           "status,outcome,r_multiple,hold_bars,regime) VALUES("
           "'S1_TSMOM',?,?,?,1,100,98,106,192,?,'CLOSED',?,?,20,2)")
    # ilan ONCESI kayit (secim penceresi) - dogrulamaya girmemeli
    db.execute(ins, ("ESKIUSDT", "LONG", "2026-08-01T00:00:00Z",
                     "S1:Lold", "WIN", 3.0))
    # ilan SONRASI iki kayit (dogrulama kohortu)
    db.execute(ins, ("YENIUSDT", "LONG", "2026-09-01T00:00:00Z",
                     "S1:Lnew1", "WIN", 3.0))
    db.execute(ins, ("YENI2USDT", "LONG", "2026-09-01T05:00:00Z",
                     "S1:Lnew2", "LOSS", -1.0))
    s = eng.stats()["strategies"]["S1_TSMOM"]
    assert s["decided"] == 3                     # genel sayac hepsini gorur
    v = s["validation"]
    assert v["start_utc"] == start
    assert v["decided"] == 2                     # yalniz ilan sonrasi
    assert v["clusters"] == 2
    assert v["target_clusters"] == 50
    # pencere ilani olmayan stratejide validation alani yok
    assert "validation" not in eng.stats()["strategies"]["S2_DONCHIAN"]


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
