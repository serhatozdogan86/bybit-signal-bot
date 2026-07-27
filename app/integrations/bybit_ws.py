"""
Bybit v5 public WebSocket adapter (Phase 2, USE_WEBSOCKET=true ile aktif).

Tasarim:
- KlineCache: SAF, test edilebilir mum onbellegi. REST'le seed edilir,
  WS mesajlariyla guncellenir (olusan bar upsert, confirm=true'da yeni bar acilir).
- BybitWSClient: ince soket sarmalayicisi (websocket-client), otomatik reconnect
  (exponential backoff, max 60s). Soket koptugunda sistem REST fallback ile
  calismaya DEVAM EDER - WS bir optimizasyondur, bagimlilik degildir.

Guvenlik: cache tazeligi get_series'te kontrol edilir; bayat cache yerine None
donulur ve MarketDataService REST'e duser.
"""
from __future__ import annotations

import json
import logging
import threading
import time

from app.logging_setup import kv
from app.models.candle import Candle, KlineSeries

log = logging.getLogger("bybit_ws")

_WS_URL = "wss://stream.bybit.com/v5/public/linear"
_MAX_CACHE = 300


class KlineCache:
    """Thread-safe mum onbellegi. Saf mantik - soket bilgisi yok."""

    def __init__(self, max_bars: int = _MAX_CACHE) -> None:
        self._lock = threading.Lock()
        self._data: dict[tuple[str, str], list[Candle]] = {}
        self._last_update: dict[tuple[str, str], float] = {}
        self._max = max_bars

    def seed(self, series: KlineSeries) -> None:
        key = (series.symbol, series.interval)
        with self._lock:
            self._data[key] = list(series.candles)[-self._max:]
            self._last_update[key] = time.time()

    def update(self, symbol: str, interval: str, bar: Candle, confirmed: bool) -> None:
        key = (symbol, interval)
        with self._lock:
            bars = self._data.get(key)
            if bars is None:
                return  # seed edilmemis sembol - REST bootstrap bekleniyor
            if bars and bars[-1].ts == bar.ts:
                bars[-1] = bar          # olusan barin guncellemesi
            elif not bars or bar.ts > bars[-1].ts:
                bars.append(bar)        # yeni bar (onceki bar confirm edilmis demektir)
                if len(bars) > self._max:
                    del bars[0]
            self._last_update[key] = time.time()

    def get_series(self, symbol: str, interval: str, min_bars: int,
                   max_age_sec: float) -> KlineSeries | None:
        key = (symbol, interval)
        with self._lock:
            bars = self._data.get(key)
            fresh = (time.time() - self._last_update.get(key, 0)) <= max_age_sec
            if not bars or len(bars) < min_bars or not fresh:
                return None
            return KlineSeries(symbol=symbol, interval=interval, candles=list(bars))


def parse_kline_message(raw: str) -> tuple[str, str, Candle, bool] | None:
    """WS mesajini (symbol, interval, candle, confirmed) olarak cozer; degilse None."""
    try:
        msg = json.loads(raw)
        topic: str = msg.get("topic", "")
        if not topic.startswith("kline."):
            return None
        _, interval, symbol = topic.split(".", 2)
        d = msg["data"][0]
        candle = Candle(
            ts=int(d["start"]), open=float(d["open"]), high=float(d["high"]),
            low=float(d["low"]), close=float(d["close"]),
            volume=float(d["volume"]), turnover=float(d.get("turnover", 0)))
        return symbol, interval, candle, bool(d.get("confirm", False))
    except (KeyError, ValueError, IndexError, json.JSONDecodeError):
        return None


class BybitWSClient(threading.Thread):
    """Arka plan WS thread'i. Hata durumunda backoff ile yeniden baglanir."""

    def __init__(self, cache: KlineCache, symbols: list[str],
                 intervals: list[str], url: str = _WS_URL) -> None:
        super().__init__(daemon=True, name="bybit-ws")
        self._cache = cache
        self._topics = [f"kline.{i}.{s}" for s in symbols for i in intervals]
        self._url = url

    def run(self) -> None:
        try:
            import websocket  # websocket-client
        except ImportError:
            log.error(kv(event="ws_disabled", reason="websocket-client not installed"))
            return

        backoff = 1
        while True:
            try:
                ws = websocket.create_connection(self._url, timeout=30)
                ws.send(json.dumps({"op": "subscribe", "args": self._topics}))
                log.info(kv(event="ws_connected", topics=len(self._topics)))
                backoff = 1
                while True:
                    parsed = parse_kline_message(ws.recv())
                    if parsed:
                        self._cache.update(*parsed[:2], parsed[2], parsed[3])
            except Exception as exc:
                log.warning(kv(event="ws_reconnect", error=str(exc)[:120], wait_s=backoff))
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
