"""UniverseProvider - dinamik evren secimi testleri."""
from __future__ import annotations

from app.config.settings import Settings
from app.services.universe import UniverseProvider


class FakeClient:
    def __init__(self, tickers):
        self.tickers = tickers
        self.calls = 0

    def get_all_tickers(self):
        self.calls += 1
        return self.tickers


def _tickers():
    return [
        {"symbol": "BTCUSDT", "turnover24h": "9000000"},
        {"symbol": "DOGEUSDT", "turnover24h": "3000000"},
        {"symbol": "ETHUSDT", "turnover24h": "8000000"},
        {"symbol": "USDCUSDT", "turnover24h": "7000000"},   # exclude listesinde
        {"symbol": "BTCUSD", "turnover24h": "5000000"},     # USDT degil -> elenir
        {"symbol": "PEPEUSDT", "turnover24h": "bozuk"},     # parse edilemez -> elenir
        {"symbol": "SOLUSDT", "turnover24h": "4000000"},
    ]


def test_top_mode_sorts_filters_and_caps():
    settings = Settings(SYMBOLS_MODE="top", SYMBOLS_TOP_N=3)
    provider = UniverseProvider(FakeClient(_tickers()), settings)
    assert provider.get_symbols() == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    d = provider.describe()
    assert d["mode"] == "top" and d["count"] == 3


def test_top_mode_caches_until_refresh():
    client = FakeClient(_tickers())
    settings = Settings(SYMBOLS_MODE="top", SYMBOLS_TOP_N=2, UNIVERSE_REFRESH_SEC=9999)
    provider = UniverseProvider(client, settings)
    provider.get_symbols()
    provider.get_symbols()
    assert client.calls == 1  # cache'ten okundu


def test_fetch_failure_falls_back():
    settings = Settings(SYMBOLS_MODE="top", SYMBOLS="BTCUSDT,ETHUSDT")
    provider = UniverseProvider(FakeClient(None), settings)
    assert provider.get_symbols() == ["BTCUSDT", "ETHUSDT"]  # static fallback


def test_static_mode_ignores_tickers():
    client = FakeClient(_tickers())
    settings = Settings(SYMBOLS_MODE="static", SYMBOLS="XRPUSDT")
    provider = UniverseProvider(client, settings)
    assert provider.get_symbols() == ["XRPUSDT"]
    assert client.calls == 0
