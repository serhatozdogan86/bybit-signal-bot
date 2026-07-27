"""
StateStore - soyut arayuz + in-memory MVP implementasyonu.

Sorumluluklar:
- Sinyal cooldown/dedup (symbol+direction bazli son sinyal zamani)
- Son analiz sonuclari (/status endpoint'i icin)
- Tarama metadata'si (health/monitoring)

Redis/SQLite'a gecis: StateStore'u implemente eden yeni bir sinif yaz
(orn. RedisStateStore), app/main.py'de tek satir degistir. Arayuz sabittir.
"""
from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod


class StateStore(ABC):
    """Kalicilik arayuzu. Tum implementasyonlar thread-safe olmalidir."""

    # --- cooldown / dedup ---
    @abstractmethod
    def get_last_signal_ts(self, key: str) -> float | None:
        """key = 'SYMBOL:DIRECTION'. Son gonderim unix ts'i veya None."""

    @abstractmethod
    def set_last_signal_ts(self, key: str, ts: float) -> None: ...

    # --- son sonuclar ---
    @abstractmethod
    def save_result(self, pair: str, result: dict) -> None:
        """Sabit contract dict (Decision.contract_dict())."""

    @abstractmethod
    def get_results(self) -> dict[str, dict]: ...

    # --- metadata ---
    @abstractmethod
    def record_scan(self, ts_iso: str) -> None: ...

    @abstractmethod
    def get_meta(self) -> dict: ...

    # --- ortak yardimci (implementasyondan bagimsiz) ---
    def cooldown_active(self, symbol: str, direction: str,
                        cooldown_sec: int, now: float | None = None) -> bool:
        last = self.get_last_signal_ts(f"{symbol}:{direction}")
        if last is None:
            return False
        return ((now or time.time()) - last) < cooldown_sec

    def mark_signal_sent(self, symbol: str, direction: str,
                         now: float | None = None) -> None:
        self.set_last_signal_ts(f"{symbol}:{direction}", now or time.time())


class InMemoryStateStore(StateStore):
    """MVP: process ici, Lock ile thread-safe. Restart'ta state sifirlanir."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._signals: dict[str, float] = {}
        self._results: dict[str, dict] = {}
        self._meta: dict = {"last_scan_utc": None, "scan_count": 0}

    def get_last_signal_ts(self, key: str) -> float | None:
        with self._lock:
            return self._signals.get(key)

    def set_last_signal_ts(self, key: str, ts: float) -> None:
        with self._lock:
            self._signals[key] = ts

    def save_result(self, pair: str, result: dict) -> None:
        with self._lock:
            self._results[pair] = result

    def get_results(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._results)

    def record_scan(self, ts_iso: str) -> None:
        with self._lock:
            self._meta["last_scan_utc"] = ts_iso
            self._meta["scan_count"] += 1

    def get_meta(self) -> dict:
        with self._lock:
            return dict(self._meta)
