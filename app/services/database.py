"""
SQLite veritabani katmani - gölge takip, backtest verisi ve kalici state icin.

ONEMLI - Render free plan notu:
Free web servislerinde disk EPHEMERAL'dir: her redeploy/restart'ta dosya silinir.
Veri kaybini azaltmak icin:
  1) /export/* endpoint'leriyle periyodik yedek indir (ucretsiz cozum), veya
  2) Render'da paid instance + Persistent Disk ekle ve DB_PATH'i disk mount
     yoluna ver (orn. /data/bot.db) - o zaman veriler kalici olur.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candles(
  symbol TEXT NOT NULL, interval TEXT NOT NULL, ts INTEGER NOT NULL,
  open REAL, high REAL, low REAL, close REAL, volume REAL,
  PRIMARY KEY(symbol, interval, ts)
);
CREATE TABLE IF NOT EXISTS decisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT, pair TEXT, decision TEXT, direction TEXT,
  regime TEXT, htf_bias TEXT, setup_type TEXT, reject_reason TEXT,
  contract_json TEXT
);
CREATE TABLE IF NOT EXISTS signals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pair TEXT, direction TEXT, created_utc TEXT, entry_candle_ts INTEGER,
  entry_min REAL, entry_max REAL, stop_loss REAL, tp1 REAL, tp2 REAL, rr REAL,
  status TEXT NOT NULL DEFAULT 'PENDING',
  outcome TEXT, fill_price REAL, exit_price REAL, r_multiple REAL,
  closed_utc TEXT, contract_json TEXT
);
CREATE TABLE IF NOT EXISTS cooldowns(key TEXT PRIMARY KEY, ts REAL);
CREATE TABLE IF NOT EXISTS results(pair TEXT PRIMARY KEY, json TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS idx_candles_lookup ON candles(symbol, interval, ts);
CREATE INDEX IF NOT EXISTS idx_signals_open ON signals(pair, status);
"""


class Database:
    """Tek baglanti + Lock. Bu is yuku icin (dakikada birkac yazma) yeterli."""

    def __init__(self, path: str) -> None:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        if not rows:
            return
        with self._lock:
            self._conn.executemany(sql, rows)
            self._conn.commit()

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def query_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None
