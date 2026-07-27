"""
UniverseProvider - takip edilecek parite evreninin secimi.

Iki mod (SYMBOLS_MODE):
- static : SYMBOLS env listesi aynen kullanilir (eski davranis).
- top    : Bybit linear USDT perp'leri 24s ciroya (turnover24h) gore siralanir,
           ilk SYMBOLS_TOP_N tanesi secilir. Liste UNIVERSE_REFRESH_SEC'te bir
           (default gunluk) yenilenir -> delist olan duser, yukselen likit
           coinler kendiliginden girer.

Dayaniklilik: ticker cekimi basarisiz olursa son basarili liste kullanilir;
o da yoksa static SYMBOLS'a dusulur. Evren secimi hicbir zaman taramayi durdurmaz.
"""
from __future__ import annotations

import logging
import threading
import time

from app.config.settings import Settings
from app.integrations.bybit_client import BybitClient
from app.logging_setup import kv

log = logging.getLogger("universe")


class UniverseProvider:
    def __init__(self, client: BybitClient, settings: Settings) -> None:
        self._client = client
        self._mode = settings.SYMBOLS_MODE.lower()
        self._top_n = settings.SYMBOLS_TOP_N
        self._exclude = {s.strip().upper()
                         for s in settings.SYMBOLS_EXCLUDE.split(",") if s.strip()}
        self._refresh_sec = settings.UNIVERSE_REFRESH_SEC
        self._static = settings.symbols
        self._cached: list[str] = []
        self._last_refresh = 0.0
        self._lock = threading.Lock()

    @property
    def mode(self) -> str:
        return self._mode

    def describe(self) -> dict:
        symbols = self.get_symbols()
        return {"mode": self._mode, "count": len(symbols),
                "top_n": self._top_n if self._mode == "top" else None,
                "exclude": sorted(self._exclude), "symbols": symbols}

    def get_symbols(self) -> list[str]:
        if self._mode != "top":
            return self._static
        with self._lock:
            if self._cached and (time.time() - self._last_refresh) < self._refresh_sec:
                return list(self._cached)
            refreshed = self._fetch_top()
            if refreshed:
                self._cached = refreshed
                self._last_refresh = time.time()
                log.info(kv(event="universe_refresh", count=len(refreshed),
                            first=refreshed[0], last=refreshed[-1]))
            elif not self._cached:
                log.warning(kv(event="universe_fallback_static"))
                return self._static
            return list(self._cached)

    def _fetch_top(self) -> list[str]:
        tickers = self._client.get_all_tickers()
        if not tickers:
            return []
        rows: list[tuple[str, float]] = []
        for t in tickers:
            symbol = str(t.get("symbol", "")).upper()
            if not symbol.endswith("USDT") or symbol in self._exclude:
                continue
            try:
                turnover = float(t.get("turnover24h", 0))
            except (TypeError, ValueError):
                continue
            rows.append((symbol, turnover))
        rows.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in rows[: self._top_n]]
