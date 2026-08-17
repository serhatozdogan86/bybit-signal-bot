"""
Market data erisim katmani.
Engine bu servis uzerinden veri alir; kaynak sirasi:
  1) WS KlineCache (aktifse ve taze/yeterliyse)  - Phase 2
  2) REST (her zaman calisan fallback)
REST'ten gelen seri cache'i seed eder, sonraki WS guncellemeleri uzerine yazar.
"""
from __future__ import annotations

import logging
import time

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

    def get_oi_change_24h(self, symbol: str) -> float | None:
        """dOI(24s)/OI - kontrat adedi (P4 golge-kohort etiketi).

        25 x 1saatlik nokta ceker (tek istek); en yeni / 24s onceki - 1.
        Veri eksik/bozuksa None (etiket bos kalir - eksik veri eksik kalir)."""
        rows = self._client.get_open_interest_rows(symbol, limit=25)
        if not rows or len(rows) < 25:
            return None
        try:
            newest = float(rows[0]["openInterest"])
            oldest = float(rows[-1]["openInterest"])
        except (KeyError, TypeError, ValueError):
            return None
        if oldest <= 0:
            return None
        return newest / oldest - 1.0

    def get_daily_closed_bars(self, symbol: str,
                              limit: int = 380) -> list[list[float]] | None:
        """KAPANMIS gunluk mumlar, artan sirada (S10 52w-HIGH verisi).

        Olusmakta olan bugunku mum ATILIR (kapanis-bazli karar kurali).
        Donen: [[ts,o,h,l,c], ...]. Hata/yetersiz -> None."""
        rows = self._client.get_kline_rows(symbol, "D", limit)
        if not rows:
            return None
        try:
            bars = sorted(
                ([int(r[0]), float(r[1]), float(r[2]), float(r[3]),
                  float(r[4])] for r in rows), key=lambda b: b[0])
        except (IndexError, TypeError, ValueError):
            return None
        # yalniz KAPANMIS gunler: ts + 24s <= simdi (kosulsuz son-bar atmak
        # yanlis - gecikmis/duraklamis paritede kapanmis gunu de atardi)
        now_ms = int(time.time() * 1000)
        closed = [b for b in bars if b[0] + 86_400_000 <= now_ms]
        return closed or None

    def get_funding_history(self, symbol: str, start_ms: int | None = None,
                            end_ms: int | None = None) -> list[dict] | None:
        """Gercek funding oranlari (v3.6 maliyet-v1 veri toplama)."""
        return self._client.get_funding_history(symbol, start_ms, end_ms)
