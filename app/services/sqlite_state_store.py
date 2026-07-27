"""
SQLiteStateStore - StateStore arayuzunun kalici implementasyonu.
Cooldown ve son sonuclar restart'lar arasinda korunur (disk kaliciysa).
Secim app/main.py'de STATE_BACKEND env ile yapilir: sqlite (default) | memory.
"""
from __future__ import annotations

import json

from app.services.database import Database
from app.services.state_store import StateStore


class SQLiteStateStore(StateStore):
    def __init__(self, db: Database) -> None:
        self._db = db

    # --- cooldown ---
    def get_last_signal_ts(self, key: str) -> float | None:
        row = self._db.query_one("SELECT ts FROM cooldowns WHERE key=?", (key,))
        return float(row["ts"]) if row else None

    def set_last_signal_ts(self, key: str, ts: float) -> None:
        self._db.execute(
            "INSERT INTO cooldowns(key, ts) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET ts=excluded.ts", (key, ts))

    # --- sonuclar ---
    def save_result(self, pair: str, result: dict) -> None:
        self._db.execute(
            "INSERT INTO results(pair, json) VALUES(?, ?) "
            "ON CONFLICT(pair) DO UPDATE SET json=excluded.json",
            (pair, json.dumps(result)))

    def get_results(self) -> dict[str, dict]:
        return {r["pair"]: json.loads(r["json"])
                for r in self._db.query("SELECT pair, json FROM results")}

    # --- meta ---
    def record_scan(self, ts_iso: str) -> None:
        self._db.execute(
            "INSERT INTO meta(key, value) VALUES('last_scan_utc', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (ts_iso,))
        self._db.execute(
            "INSERT INTO meta(key, value) VALUES('scan_count', '1') "
            "ON CONFLICT(key) DO UPDATE SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT)")

    def get_meta(self) -> dict:
        rows = {r["key"]: r["value"] for r in self._db.query("SELECT key, value FROM meta")}
        return {"last_scan_utc": rows.get("last_scan_utc"),
                "scan_count": int(rows.get("scan_count", "0"))}
