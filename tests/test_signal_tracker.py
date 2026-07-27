"""SignalTracker - golge takip sonuclandirma ve istatistik testleri."""
from __future__ import annotations

import numpy as np

from app.config.settings import StrategyParams
from app.models.decision import (Decision, DecisionType, Direction, EntryZone,
                                 Targets, TimeFrames)
from app.services.database import Database
from app.services.signal_tracker import SignalTracker
from tests import fixtures as fx


def _make_tracker(tmp_path, fill_window=24, max_track=192):
    db = Database(str(tmp_path / "test.db"))
    return SignalTracker(db, ltf_interval="15",
                         fill_window_bars=fill_window, max_track_bars=max_track), db


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
    """Sentetik kapanmis mumlari arsive yaz (record_candles yolunu kullanir)."""
    n = len(closes)
    lows = lows if lows is not None else [c - 0.3 for c in closes]
    highs = highs if highs is not None else [c + 0.3 for c in closes]
    series = fx.make_series(np.array(closes + [closes[-1]]), symbol=symbol)
    # deterministik high/low icin dogrudan yaz
    for i, c in enumerate(series.candles[:-1]):
        c.ts = start_ts + i * 900_000
        c.low, c.high, c.close = float(lows[i]), float(highs[i]), float(closes[i])
    tracker.record_candles(series)


def test_win_path(tmp_path):
    tracker, _ = _make_tracker(tmp_path)
    d = _signal()
    ltf = fx.make_series(np.full(70, 101.5))
    ltf.candles[-1].ts = 1_000_000
    assert tracker.maybe_track(d, ltf) is True
    # bar1: entry bolgesine iner (low 100.5 <= entry_max 101) -> FILLED @101
    # bar3: high 106.5 >= tp1 106 -> WIN, r = (106-101)/(101-98) = 1.67
    _feed(tracker, closes=[100.8, 102.0, 105.0, 106.2],
          lows=[100.5, 101.6, 104.0, 105.5],
          highs=[101.2, 102.5, 105.5, 106.5], start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")
    sig = tracker.recent_signals(1)[0]
    assert sig["status"] == "CLOSED" and sig["outcome"] == "WIN"
    assert abs(sig["r_multiple"] - 1.67) < 0.01
    stats = tracker.stats()
    assert stats["win_rate"] == 1.0 and stats["decided_trades"] == 1


def test_loss_path(tmp_path):
    tracker, _ = _make_tracker(tmp_path)
    d = _signal()
    ltf = fx.make_series(np.full(70, 101.5))
    ltf.candles[-1].ts = 1_000_000
    tracker.maybe_track(d, ltf)
    # fill sonra stop 98'e deger -> LOSS -1R
    _feed(tracker, closes=[100.8, 99.5, 97.9],
          lows=[100.5, 99.0, 97.5], highs=[101.2, 100.2, 99.0])
    tracker.evaluate_open("TESTUSDT")
    sig = tracker.recent_signals(1)[0]
    assert sig["outcome"] == "LOSS" and sig["r_multiple"] == -1.0
    assert tracker.stats()["win_rate"] == 0.0


def test_not_filled(tmp_path):
    tracker, _ = _make_tracker(tmp_path, fill_window=3)
    d = _signal()
    ltf = fx.make_series(np.full(70, 103.0))
    ltf.candles[-1].ts = 1_000_000
    tracker.maybe_track(d, ltf)
    # fiyat hic entry bolgesine (<=101) inmiyor, 3 bar sonra NOT_FILLED
    _feed(tracker, closes=[103.0, 104.0, 105.0, 106.0],
          lows=[102.5, 103.5, 104.5, 105.5], highs=[103.5, 104.5, 105.5, 106.5])
    tracker.evaluate_open("TESTUSDT")
    sig = tracker.recent_signals(1)[0]
    assert sig["outcome"] == "NOT_FILLED"
    # NOT_FILLED win_rate'e dahil edilmez
    assert tracker.stats()["decided_trades"] == 0


def test_short_win_and_dedupe(tmp_path):
    tracker, _ = _make_tracker(tmp_path)
    d = _signal(direction=Direction.SHORT, entry=(99.0, 100.0),
                stop=102.0, tp1=94.0)
    ltf = fx.make_series(np.full(70, 98.5))
    ltf.candles[-1].ts = 1_000_000
    assert tracker.maybe_track(d, ltf) is True
    assert tracker.maybe_track(d, ltf) is False  # acik kayit varken tekrar izlenmez
    # bar1 high 99.5 >= entry_min 99 -> FILLED @99; bar3 low 93.8 <= tp1 94 -> WIN
    _feed(tracker, closes=[99.2, 96.0, 94.2],
          lows=[98.5, 95.5, 93.8], highs=[99.5, 97.0, 95.0])
    tracker.evaluate_open("TESTUSDT")
    sig = tracker.recent_signals(1)[0]
    assert sig["outcome"] == "WIN"
    assert abs(sig["r_multiple"] - (99.0 - 94.0) / (102.0 - 99.0)) < 0.01


def test_dataset_accumulation(tmp_path):
    tracker, db = _make_tracker(tmp_path)
    d = _signal()
    tracker.record_decision(d)
    _feed(tracker, closes=[100.0, 101.0, 102.0])
    stats = tracker.stats()
    assert stats["dataset"]["decisions_recorded"] == 1
    assert stats["dataset"]["candles_archived"] == 3
    # ayni mumlar tekrar yazilirsa cogaltilmaz (INSERT OR IGNORE)
    _feed(tracker, closes=[100.0, 101.0, 102.0])
    assert tracker.stats()["dataset"]["candles_archived"] == 3
