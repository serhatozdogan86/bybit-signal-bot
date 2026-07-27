"""Phase 2 bilesen testleri: SQLiteStateStore, KlineCache, rich formatter, liquidity."""
from __future__ import annotations

import numpy as np

from app.config.settings import StrategyParams
from app.formatting import telegram_formatter as tf
from app.integrations.bybit_ws import KlineCache, parse_kline_message
from app.models.candle import Candle
from app.services.database import Database
from app.services.sqlite_state_store import SQLiteStateStore
from app.strategies import signal_engine
from app.strategies.liquidity_mapper import orderbook_note
from tests import fixtures as fx


# ---------------------------------------------------------- SQLiteStateStore
def test_sqlite_store_persists_across_instances(tmp_path):
    path = str(tmp_path / "state.db")
    s1 = SQLiteStateStore(Database(path))
    s1.mark_signal_sent("BTCUSDT", "LONG", now=1000.0)
    s1.save_result("BTCUSDT", {"decision": "SIGNAL"})
    s1.record_scan("2026-07-27T00:00:00Z")
    # yeni instance (restart simulasyonu) ayni dosyayi okur
    s2 = SQLiteStateStore(Database(path))
    assert s2.cooldown_active("BTCUSDT", "LONG", cooldown_sec=100, now=1050.0) is True
    assert s2.cooldown_active("BTCUSDT", "LONG", cooldown_sec=100, now=1200.0) is False
    assert s2.get_results()["BTCUSDT"]["decision"] == "SIGNAL"
    assert s2.get_meta()["scan_count"] == 1


# --------------------------------------------------------------- KlineCache
def _bar(ts, close):
    return Candle(ts=ts, open=close, high=close + 1, low=close - 1,
                  close=close, volume=100, turnover=0)


def test_kline_cache_seed_update_and_staleness():
    cache = KlineCache(max_bars=5)
    series = fx.make_series(np.linspace(100, 110, 70), symbol="BTCUSDT", interval="15")
    cache.seed(series)
    got = cache.get_series("BTCUSDT", "15", min_bars=5, max_age_sec=60)
    assert got is not None and len(got) == 5  # max_bars'a kirpildi

    last_ts = got.candles[-1].ts
    cache.update("BTCUSDT", "15", _bar(last_ts, 111.0), confirmed=False)  # upsert
    cache.update("BTCUSDT", "15", _bar(last_ts + 900_000, 112.0), confirmed=False)  # yeni bar
    got2 = cache.get_series("BTCUSDT", "15", min_bars=5, max_age_sec=60)
    assert got2.candles[-1].close == 112.0
    assert got2.candles[-2].close == 111.0
    # bayatlik: max_age 0 -> None (REST fallback tetiklenir)
    assert cache.get_series("BTCUSDT", "15", min_bars=5, max_age_sec=0) is None
    # seed edilmemis sembol -> None
    assert cache.get_series("ETHUSDT", "15", min_bars=5, max_age_sec=60) is None


def test_parse_kline_message():
    raw = ('{"topic":"kline.15.BTCUSDT","data":[{"start":1700000000000,'
           '"open":"100","high":"101","low":"99","close":"100.5",'
           '"volume":"12.3","turnover":"1234","confirm":true}]}')
    parsed = parse_kline_message(raw)
    assert parsed is not None
    symbol, interval, candle, confirmed = parsed
    assert (symbol, interval, confirmed) == ("BTCUSDT", "15", True)
    assert candle.close == 100.5
    assert parse_kline_message('{"op":"subscribe"}') is None
    assert parse_kline_message("not json") is None


# ------------------------------------------------------------ rich formatter
def test_markdownv2_render_escapes_specials():
    htf = fx.make_series(fx.bullish_htf_closes(), interval="240", seed=3)
    ltf = fx.make_series(fx.bullish_ltf_closes(), interval="15",
                         volumes=fx.breakout_volumes(), seed=4)
    d = signal_engine.evaluate("TRENDUSDT", htf, ltf, StrategyParams())
    text = tf.render(d, parse_mode="MarkdownV2")
    assert text.startswith("*SIGNAL")
    assert "\\." in text  # noktalar kacirilmis
    assert "`" in text    # seviyeler monospace
    # plain mod hala varsayilan
    assert tf.render(d).startswith("SIGNAL | TRENDUSDT")


# --------------------------------------------------------- liquidity mapper
def test_orderbook_note_detects_walls():
    ob = {"b": [["100.0", "10"], ["99.9", "10"], ["99.8", "80"], ["99.7", "10"]],
          "a": [["100.1", "9"], ["100.2", "9"], ["100.3", "9"], ["100.4", "9"]]}
    note = orderbook_note(ob)
    assert "bid wall 80 @ 99.8" in note
    assert "ask wall" not in note  # ask tarafinda duvar yok
    assert orderbook_note({"b": [], "a": []}) == ""
    assert orderbook_note({}) == ""


# ---------------------------------------------------------------- dashboard
def test_dashboard_served_at_root(tmp_path):
    from app.server import create_app
    from app.services.sqlite_state_store import SQLiteStateStore

    class Stub:
        def scan_all(self, send_telegram=True):
            return []

    app = create_app(SQLiteStateStore(Database(str(tmp_path / "d.db"))), Stub())
    r = app.test_client().get("/")
    assert r.status_code == 200
    assert b"signal-engine // dashboard" in r.data
    assert b"/performance" in r.data  # kendi endpoint'lerine baglaniyor
