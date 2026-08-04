"""
Market data erisim katmani.
Engine bu servis uzerinden veri alir; kaynak sirasi:
  1) WS KlineCache (aktifse ve taze/yeterliyse)  - Phase 2
  2) REST (her zaman calisan fallback)
REST'ten gelen seri cache'i seed eder, sonraki WS guncellemeleri uzerine yazar.
"""
from __future__ import annotations

import logging

from app.integrations.bybit_client import BybitClient
from app.logging_setup import kv
from app.models.candle import KlineSeries

log = logging.getLogger("market_data")

MIN_BARS = 60
_CACHE_MAX_AGE_SEC = 120.0  # WS cache bu sureden eskiyse bayat sayilir -> REST


class MarketDataService:
    def __init__(self, client: BybitClient, min_bars: int = MIN_BARS,
                 kline_cache=None) -> None:
        self._client = client
        self._min_bars = min_bars
        self._cache = kline_cache  # KlineCache | None (USE_WEBSOCKET=true ise)

    def get_series(self, symbol: str, interval: str) -> KlineSeries | None:
        """
        Kline serisi (eski -> yeni). Veri yoksa/yetersizse None.
        None donusu ust katmanda DATA_MISSING karari uretir - tahmin yapilmaz.
        """
        if self._cache is not None:
            cached = self._cache.get_series(symbol, interval,
                                            self._min_bars, _CACHE_MAX_AGE_SEC)
            if cached is not None:
                return cached

        rows = self._client.get_kline_rows(symbol, interval)
        if rows is None:
            return None
        if len(rows) < self._min_bars:
            log.warning(kv(event="insufficient_bars", symbol=symbol,
                           interval=interval, bars=len(rows), min=self._min_bars))
            return None
        series = KlineSeries.from_bybit_rows(symbol, interval, rows)
        if self._cache is not None:
            self._cache.seed(series)
        return series

    def get_last_price(self, symbol: str) -> float | None:
        return self._client.get_last_price(symbol)

    def get_orderbook(self, symbol: str, depth: int = 50) -> dict | None:
        """Orderbook snapshot (Phase 2 - ORDERBOOK_ENRICH icin)."""
        return self._client.get_orderbook(symbol, depth)

    def get_all_tickers(self) -> list[dict] | None:
        """Tum semboller tek istekte (funding dahil) - aday S4 icin."""
        return self._client.get_all_tickers()

    def get_funding_history(self, symbol: str, start_ms: int | None = None,
                            end_ms: int | None = None) -> list[dict] | None:
        """Gercek funding oranlari (v3.6 maliyet-v1 veri toplama)."""
        return self._client.get_funding_history(symbol, start_ms, end_ms)
