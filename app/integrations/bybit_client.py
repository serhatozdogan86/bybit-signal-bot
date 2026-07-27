"""
Bybit v5 REST client (public market data - API key GEREKMEZ, emir gonderilmez).
Retry politikasi: network hatasi / HTTP 429 / 5xx -> exponential backoff (1s, 2s, 4s).
API-seviyesi hata (retCode != 0) retry edilmez -> loglanir, None doner.
Hata durumunda None doner; ust katman DATA_MISSING uretir - tahmin yok.
"""
from __future__ import annotations

import logging
import time

import requests

from app.logging_setup import kv

log = logging.getLogger("bybit")

_CATEGORY = "linear"
_KLINE_LIMIT = 200
_MAX_ATTEMPTS = 3
_TIMEOUT = (10, 15)  # (connect, read) saniye


class BybitClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def _get(self, path: str, params: dict) -> dict | None:
        url = f"{self._base_url}{path}"
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                resp = self._session.get(url, params=params, timeout=_TIMEOUT)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                data: dict = resp.json()
                if data.get("retCode") != 0:
                    log.error(kv(event="bybit_api_error", path=path,
                                 ret_code=data.get("retCode"), msg=data.get("retMsg")))
                    return None
                return data
            except (requests.RequestException, ValueError) as exc:
                wait = 2 ** (attempt - 1)
                log.warning(kv(event="bybit_retry", path=path, attempt=attempt,
                               max=_MAX_ATTEMPTS, error=str(exc), wait_s=wait))
                if attempt == _MAX_ATTEMPTS:
                    log.error(kv(event="bybit_failed", path=path, error=str(exc)))
                    return None
                time.sleep(wait)
        return None

    def get_kline_rows(self, symbol: str, interval: str,
                       limit: int = _KLINE_LIMIT) -> list[list[str]] | None:
        """Ham kline satirlari (Bybit sirasi: yeniden eskiye). Hata -> None."""
        data = self._get("/v5/market/kline", {
            "category": _CATEGORY, "symbol": symbol,
            "interval": interval, "limit": limit,
        })
        if data is None:
            return None
        rows: list[list[str]] = data.get("result", {}).get("list", [])
        return rows or None

    def get_last_price(self, symbol: str) -> float | None:
        data = self._get("/v5/market/tickers", {"category": _CATEGORY, "symbol": symbol})
        if data is None:
            return None
        try:
            return float(data["result"]["list"][0]["lastPrice"])
        except (KeyError, IndexError, ValueError):
            log.error(kv(event="bybit_ticker_parse_error", symbol=symbol))
            return None

    def get_all_tickers(self) -> list[dict] | None:
        """Tum linear pariteler icin ticker listesi (evren secimi icin)."""
        data = self._get("/v5/market/tickers", {"category": _CATEGORY})
        if data is None:
            return None
        return data.get("result", {}).get("list") or None

    def get_orderbook(self, symbol: str, depth: int = 50) -> dict | None:
        """Orderbook snapshot (Phase 2). result: {"b": [[p,s],...], "a": [...]}."""
        data = self._get("/v5/market/orderbook",
                         {"category": _CATEGORY, "symbol": symbol, "limit": depth})
        return data.get("result") if data else None
