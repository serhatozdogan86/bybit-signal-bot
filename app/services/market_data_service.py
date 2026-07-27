"""
Market data erisim katmani.
Engine bu servis uzerinden veri alir; alttaki kaynak (REST bugun, WebSocket Phase 2)
degistiginde engine ve scheduler degismez. Orderbook stub'i Phase 2 icin rezerve.
"""
from __future__ import annotations

import logging

from app.integrations.bybit_client import BybitClient
from app.logging_setup import kv
from app.models.candle import KlineSeries

log = logging.getLogger("market_data")

MIN_BARS = 60


class MarketDataService:
    def __init__(self, client: BybitClient, min_bars: int = MIN_BARS) -> None:
        self._client = client
        self._min_bars = min_bars

    def get_series(self, symbol: str, interval: str) -> KlineSeries | None:
        """
        Kline serisi (eski -> yeni). Veri yoksa / yetersizse None.
        None donusu ust katmanda DATA_MISSING karari uretir - tahmin yapilmaz.
        """
        rows = self._client.get_kline_rows(symbol, interval)
        if rows is None:
            return None
        if len(rows) < self._min_bars:
            log.warning(kv(event="insufficient_bars", symbol=symbol,
                           interval=interval, bars=len(rows), min=self._min_bars))
            return None
        return KlineSeries.from_bybit_rows(symbol, interval, rows)

    def get_last_price(self, symbol: str) -> float | None:
        return self._client.get_last_price(symbol)

    def get_orderbook(self, symbol: str, depth: int = 50) -> None:
        """Phase 2: /v5/market/orderbook. MVP'de bilincli olarak yok."""
        raise NotImplementedError("Orderbook Phase 2 kapsamindadir")
