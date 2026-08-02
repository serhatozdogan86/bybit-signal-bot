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


def test_open_pairs_lists_unclosed(tmp_path):
    from app.services.database import Database as _DB
    tracker = SignalTracker(_DB(str(tmp_path / "op.db")), ltf_interval="15")
    tracker.import_signals([
        {"pair": "AAAUSDT", "direction": "LONG", "created_utc": "x",
         "entry_candle_ts": 1, "entry_min": 1, "entry_max": 1.1,
         "stop_loss": .9, "tp1": 2, "tp2": 3, "rr": 2.0,
         "status": "PENDING", "outcome": None, "fill_price": None,
         "exit_price": None, "r_multiple": None, "closed_utc": None,
         "contract_json": "{}"},
        {"pair": "BBBUSDT", "direction": "SHORT", "created_utc": "x",
         "entry_candle_ts": 1, "entry_min": 1, "entry_max": 1.1,
         "stop_loss": 1.2, "tp1": .8, "tp2": .7, "rr": 2.0,
         "status": "CLOSED", "outcome": "WIN", "fill_price": 1,
         "exit_price": .8, "r_multiple": 2.0, "closed_utc": "y",
         "contract_json": "{}"},
    ])
    assert tracker.open_pairs() == ["AAAUSDT"]


def test_confidence_and_setup_persisted(tmp_path):
    """v3.3: sinyal kaydinda guven ve setup tipi kalici olmali."""
    from app.services.database import Database as _DB
    from app.strategies import signal_engine
    from tests import fixtures as fx

    db = _DB(str(tmp_path / "cs.db"))
    tracker = SignalTracker(db, ltf_interval="15")
    from app.config.settings import StrategyParams
    htf = fx.make_series(fx.bullish_htf_closes(), interval="240", seed=3)
    ltf = fx.make_series(fx.bullish_ltf_closes(), interval="15",
                         volumes=fx.breakout_volumes(), seed=4)
    d = signal_engine.evaluate("CONFUSDT", htf, ltf, StrategyParams())
    assert d.decision.value == "SIGNAL"
    tracker.maybe_track(d, ltf)
    row = tracker.recent_signals(1)[0]
    assert row["confidence"] in ("HIGH", "MEDIUM", "LOW")
    assert row["setup_type"] in ("breakout_retest", "sweep_reclaim")
    # eski yedek geri uyumu: alanlar olmadan import calismali
    n = tracker.import_signals([{"pair": "OLDUSDT", "direction": "LONG",
                                 "created_utc": "z", "entry_candle_ts": 1,
                                 "entry_min": 1, "entry_max": 1.1,
                                 "stop_loss": .9, "tp1": 2, "tp2": 3,
                                 "rr": 2.0, "status": "CLOSED",
                                 "outcome": "WIN", "fill_price": 1,
                                 "exit_price": 2, "r_multiple": 2.0,
                                 "closed_utc": "z", "contract_json": "{}"}])
    assert n == 1
    old = [r for r in tracker.recent_signals(5) if r["pair"] == "OLDUSDT"][0]
    assert old["confidence"] is None and old["setup_type"] is None


def test_blocked_cohort_isolated(tmp_path):
    """v3.4: bloklanan sinyal ayri kohorttadir; skor tablosuna karismaz."""
    from app.services.database import Database as _DB
    from app.config.settings import StrategyParams
    from app.strategies import signal_engine
    from tests import fixtures as fx

    db = _DB(str(tmp_path / "blk.db"))
    tracker = SignalTracker(db, ltf_interval="15")
    htf = fx.make_series(fx.bullish_htf_closes(), interval="240", seed=3)
    ltf = fx.make_series(fx.bullish_ltf_closes(), interval="15",
                         volumes=fx.breakout_volumes(), seed=4)
    d = signal_engine.evaluate("BLKUSDT", htf, ltf, StrategyParams(),
                               market_bias="bear")   # LONG bloklanir
    assert tracker.track_blocked(d, ltf) is True
    assert tracker.track_blocked(d, ltf) is False    # tekrarsizlik
    assert tracker.recent_signals(10) == []          # gercek kohort bos
    blk = tracker.blocked_signals(10)
    assert len(blk) == 1 and blk[0]["blocked"] == 1
    assert blk[0]["rr"] is not None and blk[0]["confidence"] in (
        "HIGH", "MEDIUM", "LOW")
    assert tracker.stats()["open_signals"] == 0      # skor etkilenmez
    # ayni pair icin GERCEK sinyal takibi hala mumkun (kohortlar bagimsiz)
    d2 = signal_engine.evaluate("BLKUSDT", htf, ltf, StrategyParams())
    assert tracker.maybe_track(d2, ltf) is True
    assert tracker.stats()["open_signals"] == 1


def test_cost_r_and_cluster(tmp_path):
    """v3.5: maliyet motoru mantikli deger uretir; cluster_id yazilir."""
    from app.services.signal_tracker import cost_r
    row = {"outcome": "LOSS", "direction": "SHORT", "fill_price": 100.0,
           "entry_min": 100.0, "entry_max": 101.0, "stop_loss": 102.0,
           "r_multiple": -1.0, "created_utc": "2026-07-29T00:00:00Z",
           "closed_utc": "2026-07-29T16:00:00Z"}
    c = cost_r(row)                     # stop %2; fee+slip=%0.16; funding SHORT alir
    assert c is not None and 0.0 < c < 0.10
    win = dict(row, outcome="WIN", r_multiple=2.5)
    cw = cost_r(win)
    assert cw is not None and cw < c    # kayma yalniz stop cikisinda


def test_portfolio_heat_and_ambiguous(tmp_path):
    """v3.5-P1: isi limitleri blocked=2 uretir; ayni-mum LOSS sayilir."""
    from app.services.database import Database as _DB
    from app.config.settings import StrategyParams
    from app.strategies import signal_engine
    from app.services.signal_tracker import _cluster_id
    from tests import fixtures as fx

    db = _DB(str(tmp_path / "heat.db"))
    tracker = SignalTracker(db, ltf_interval="15")
    htf = fx.make_series(fx.bullish_htf_closes(), interval="240", seed=3)
    ltf = fx.make_series(fx.bullish_ltf_closes(), interval="15",
                         volumes=fx.breakout_volumes(), seed=4)
    params = StrategyParams()
    # 4 farkli paritede ayni yon/kume gercek sinyal doldur
    for i in range(4):
        d = signal_engine.evaluate(f"H{i}USDT", htf, ltf, params)
        assert d.decision.value == "SIGNAL"
        if i < 2:
            assert tracker.heat_check(d.direction.value,
                                      _cluster_id(d, ltf)) is None
            tracker.maybe_track(d, ltf)
        else:
            # kume tavani (2) yon tavanindan once devreye girer
            reason = tracker.heat_check(d.direction.value, _cluster_id(d, ltf))
            assert reason is not None and "cluster cap" in reason
            tracker.track_portfolio_blocked(d, ltf, reason)
    assert tracker.stats()["open_signals"] == 2          # skor izole
    assert tracker.stats()["cohorts"]["heat_blocked"] == 2
    blk = [b for b in tracker.blocked_signals(10) if b["blocked"] == 2]
    assert len(blk) == 2 and "cluster cap" in blk[0]["block_reason"]


def test_fill_ts_recorded(tmp_path):
    """Dolus ani (fill_ts) kaydedilir; grafik tahmine muhtac kalmaz."""
    from app.services.database import Database as _DB
    from app.config.settings import StrategyParams
    from app.strategies import signal_engine
    from tests import fixtures as fx

    db = _DB(str(tmp_path / "fts.db"))
    tracker = SignalTracker(db, ltf_interval="15")
    htf = fx.make_series(fx.bullish_htf_closes(), interval="240", seed=3)
    ltf = fx.make_series(fx.bullish_ltf_closes(), interval="15",
                         volumes=fx.breakout_volumes(), seed=4)
    d = signal_engine.evaluate("FTSUSDT", htf, ltf, StrategyParams())
    assert d.decision.value == "SIGNAL"
    tracker.maybe_track(d, ltf)
    tracker.record_candles(ltf)
    tracker.evaluate_open("FTSUSDT")
    row = tracker.recent_signals(1)[0]
    if row["status"] != "PENDING":           # doldu ise zaman damgali olmali
        assert row["fill_ts"] is not None
        assert row["fill_ts"] >= row["entry_candle_ts"]
