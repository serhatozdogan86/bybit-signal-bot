"""IKIZ DEPO KONTROLU (16 Agu 2026): midas v4.32 'zombi PENDING' kusurunun
bybit karsiligi var mi?

Midas vakasi (DAL/UAL): dolum penceresi sayaci MUM LISTESI INDEKSI oldugu
icin mum akisi kesilince NOT_FILLED asla yazilmadi; iki kayit time-stop'tan
9 gun sonra bile portfoy tavanindan slot yedi.

Bybit'te ayni sekil: signal_tracker._evaluate_signal icinde
    if i + 1 >= self._fill_window:
gecisi yine dongu indeksine bagli. Bu testler kusuru KANITLAR.
"""
from __future__ import annotations

import numpy as np

from app.models.decision import (Decision, DecisionType, Direction, EntryZone,
                                 Targets, TimeFrames)
from app.services.database import Database
from app.services.signal_tracker import SignalTracker
from tests import fixtures as fx

FILL_WINDOW = 24


def _make_tracker(tmp_path, fill_window=FILL_WINDOW, max_track=192):
    db = Database(str(tmp_path / "ikiz.db"))
    return SignalTracker(db, ltf_interval="15",
                         fill_window_bars=fill_window,
                         max_track_bars=max_track), db


def _signal(pair="TESTUSDT", direction=Direction.LONG,
            entry=(100.0, 101.0), stop=98.0, tp1=106.0, tp2=110.0) -> Decision:
    return Decision(
        pair=pair, timestamp_utc="2026-07-27T00:00:00Z",
        timeframes=TimeFrames(htf="240", ltf="15"),
        decision=DecisionType.SIGNAL, direction=direction,
        entry_zone=EntryZone(min=entry[0], max=entry[1]),
        stop_loss=stop, targets=Targets(tp1=tp1, tp2=tp2), rr=2.5)


def _feed(tracker, closes, start_ts=1_000_000, lows=None, highs=None,
          symbol="TESTUSDT"):
    n = len(closes)
    lows = lows if lows is not None else [c - 0.3 for c in closes]
    highs = highs if highs is not None else [c + 0.3 for c in closes]
    series = fx.make_series(np.array(closes + [closes[-1]]), symbol=symbol)
    for i, c in enumerate(series.candles[:-1]):
        c.ts = start_ts + i * 900_000
        c.low, c.high, c.close = float(lows[i]), float(highs[i]), float(closes[i])
    tracker.record_candles(series)


def _track(tracker, d=None):
    d = d or _signal()
    ltf = fx.make_series(np.full(70, 105.0))
    ltf.candles[-1].ts = 1_000_000
    assert tracker.maybe_track(d, ltf) is True
    return d


def _status(tracker):
    return tracker.recent_signals(1)[0]["status"]


# --------------------------------------------------------------- KUSUR A
def test_kusur_a_eksik_mum_pencereyi_asla_kapatmaz(tmp_path):
    """Pencereden AZ mum gelirse (parite evrenden dustu / veri kesildi)
    fiyat giris bolgesine hic girmese bile NOT_FILLED yazilmaz.

    DAL/UAL'in tam sekli: 9 mum vardi, pencere 14'tu -> sonsuz PENDING.
    """
    tracker, _ = _make_tracker(tmp_path)
    _track(tracker)

    # 9 mum, hepsi giris bolgesinin USTUNDE (low 104 > entry_max 101):
    # dolum yok. Pencere 24 -> sayac 9'da kalir.
    kapanis = [105.0] * 9
    _feed(tracker, closes=kapanis, lows=[104.0] * 9, highs=[106.0] * 9)
    tracker.evaluate_open("TESTUSDT")

    assert _status(tracker) == "PENDING", (
        "beklenen kusur: az mumla pencere kapanmiyor")


# --------------------------------------------------------------- KUSUR B
def test_kusur_b_hic_mum_yoksa_degerlendirme_hic_calismaz(tmp_path):
    """Arsivde hic mum yoksa evaluate_open 'if candles:' ile sessizce
    atlar - kayit sonsuza dek PENDING kalir. Mumsuz supurge YOK."""
    tracker, _ = _make_tracker(tmp_path)
    _track(tracker)

    tracker.evaluate_open("TESTUSDT")   # arsiv bos

    assert _status(tracker) == "PENDING", (
        "beklenen kusur: mumsuz kayit hic degerlendirilmiyor")


# --------------------------------------------------------------- KUSUR C
def test_kusur_c_sikisan_kayit_portfoy_tavanindan_slot_yer(tmp_path):
    """Asil zarar: sikisan PENDING heat_check'te sayiliyor. Ayni kumede
    HEAT_CLUSTER=2 tavani var -> iki sikisik kayit o kumeyi KALICI kapatir.
    """
    tracker, db = _make_tracker(tmp_path)
    _track(tracker)

    # mum akisi kesik -> kayit sikisti
    tracker.evaluate_open("TESTUSDT")
    assert _status(tracker) == "PENDING"

    acik = db.query_one("SELECT COUNT(*) n FROM signals "
                        "WHERE status!='CLOSED' AND blocked=0")["n"]
    assert acik == 1, "sikisan kayit acik sayiliyor"

    kume = db.query_one("SELECT cluster_id FROM signals "
                        "WHERE status!='CLOSED'")["cluster_id"]
    # ayni kumeden 1 tane daha eklenirse tavan (2) dolar
    db.execute("INSERT INTO signals(pair,direction,created_utc,"
               "entry_candle_ts,entry_min,entry_max,stop_loss,tp1,tp2,rr,"
               "status,blocked,cluster_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               ("OTHERUSDT", "LONG", "2026-07-27T00:00:00Z", 1_000_000,
                100.0, 101.0, 98.0, 106.0, 110.0, 2.5, "PENDING", 0, kume))

    sebep = tracker.heat_check("LONG", kume)
    assert sebep is not None and "cluster" in sebep, (
        f"sikisan kayit kume tavanini kapatmali, donen: {sebep}")


# --------------------------------------------------------------- KONTROL
def test_kontrol_mum_akarsa_pencere_dogru_kapanir(tmp_path):
    """Kusurun kapsamini sinirla: mum akisi SAGLAMKEN mantik dogru.
    Yani sorun 'pencere mantigi' degil, 'mum yoksa hic calismamasi'."""
    tracker, _ = _make_tracker(tmp_path)
    _track(tracker)

    n = FILL_WINDOW + 2            # pencereden FAZLA mum
    _feed(tracker, closes=[105.0] * n, lows=[104.0] * n, highs=[106.0] * n)
    tracker.evaluate_open("TESTUSDT")

    sig = tracker.recent_signals(1)[0]
    assert sig["status"] == "CLOSED" and sig["outcome"] == "NOT_FILLED", (
        f"mum akarken dogru kapanmali, gelen: {sig['status']}/{sig['outcome']}")
