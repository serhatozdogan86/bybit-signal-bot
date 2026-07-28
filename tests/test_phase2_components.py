"""Phase 2 bilesen testleri: SQLiteStateStore, KlineCache, rich formatter, liquidity."""
from __future__ import annotations

import numpy as np

from app.config.settings import StrategyParams
from app.formatting import telegram_formatter as tf
from app.integrations.bybit_ws import KlineCache, parse_kline_message
from app.models.candle import Candle
from app.services.database import Database
from app.services.signal_tracker import SignalTracker
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


# ------------------------------------------------------- v2.5: commentary
def test_commentary_generates_and_deltas(tmp_path):
    from app.services.commentary import CommentaryService

    db = Database(str(tmp_path / "c.db"))
    tracker = SignalTracker(db, ltf_interval="15")
    tracker.import_signals([
        {"pair": "AAAUSDT", "direction": "SHORT", "created_utc": "2026-07-28T01:00:00Z",
         "entry_candle_ts": 1, "entry_min": 10, "entry_max": 11, "stop_loss": 12,
         "tp1": 8, "tp2": 7, "rr": 2.0, "status": "CLOSED", "outcome": "WIN",
         "fill_price": 10, "exit_price": 8, "r_multiple": 2.0,
         "closed_utc": "2026-07-28T03:00:00Z", "contract_json": "{}"},
        {"pair": "BBBUSDT", "direction": "LONG", "created_utc": "2026-07-28T01:10:00Z",
         "entry_candle_ts": 2, "entry_min": 5, "entry_max": 5.1, "stop_loss": 4.99,
         "tp1": 9, "tp2": 10, "rr": 8.5, "status": "CLOSED", "outcome": "LOSS",
         "fill_price": 5.1, "exit_price": 4.99, "r_multiple": -1.0,
         "closed_utc": "2026-07-28T04:00:00Z", "contract_json": "{}"},
    ])
    svc = CommentaryService(db, tracker, interval_sec=3600)
    row = svc.generate()
    assert "golge muhasebe" in row["text"]
    assert "WIN" in row["text"] and "LOSS" in row["text"]
    assert "RR 8.5" in row["text"]          # yuksek-RR kaybi uyarisi
    # ikinci uretim: delta cumlesi olusmali
    row2 = svc.generate()
    assert "Onceki degerlendirmeden bu yana" in row2["text"]
    assert len(svc.recent(10)) == 2


# ------------------------------------------------------ v2.5: market info
def test_market_metrics_and_feed_parse():
    from app.config.settings import Settings
    from app.services.market_info import MarketInfoService, parse_feed

    class FakeBybit:
        def get_all_tickers(self):
            return [
                {"symbol": "BTCUSDT", "lastPrice": "64000", "price24hPcnt": "-0.012",
                 "fundingRate": "0.0001", "turnover24h": "9e9"},
                {"symbol": "ETHUSDT", "lastPrice": "1800", "price24hPcnt": "0.02",
                 "fundingRate": "0.0001", "turnover24h": "5e9"},
                {"symbol": "PUMPUSDT", "lastPrice": "1", "price24hPcnt": "0.4",
                 "fundingRate": "0", "turnover24h": "30000000"},
                {"symbol": "ILLIQUSDT", "lastPrice": "1", "price24hPcnt": "4.0",
                 "fundingRate": "0", "turnover24h": "1000"},  # elenmeli
            ]

    svc = MarketInfoService(FakeBybit(), Settings(SYMBOLS="BTCUSDT"))
    m = svc.metrics()
    assert [x["symbol"] for x in m["majors"]] == ["BTCUSDT", "ETHUSDT"]
    assert m["gainers"][0]["symbol"] == "PUMPUSDT"          # likit lider
    assert all(x["symbol"] != "ILLIQUSDT" for x in m["gainers"])
    assert m["majors"][0]["pct24h"] == -1.2

    rss = """<rss><channel><item><title>T1</title><link>http://a/1</link>
      <pubDate>Tue, 28 Jul 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <title>T2</title><link href="http://b/2"/>
      <updated>2026-07-28T09:00:00Z</updated></entry></feed>"""
    assert parse_feed(rss, "a")[0]["title"] == "T1"
    assert parse_feed(atom, "b")[0]["url"] == "http://b/2"
    assert parse_feed("<broken", "x") == []


# ------------------------------------------------- v2.5: yeni endpoint'ler
def test_new_endpoints_serve(tmp_path):
    from app.server import create_app
    from app.services.sqlite_state_store import SQLiteStateStore

    class StubSched:
        def scan_all(self, send_telegram=True): return []

    class StubMarket:
        def metrics(self): return {"majors": []}
        def news(self): return {"items": []}

    class StubComment:
        def recent(self, limit=5): return [{"ts_utc": "x", "text": "y"}]

    app = create_app(SQLiteStateStore(Database(str(tmp_path / "e.db"))),
                     StubSched(), market_info=StubMarket(),
                     commentary=StubComment())
    c = app.test_client()
    assert c.get("/market").status_code == 200
    assert c.get("/news").status_code == 200
    assert b"y" in c.get("/commentary").data
    body = c.get("/").data.decode()
    for marker in ("hourly_review", "kripto haber", "canlı metrikler",
                   "Nasıl okunur?", "signal-engine // dashboard"):
        assert marker in body, marker
