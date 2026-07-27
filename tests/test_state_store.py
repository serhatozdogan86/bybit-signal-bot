"""InMemoryStateStore - cooldown ve sonuc saklama davranisi."""
from __future__ import annotations

from app.services.state_store import InMemoryStateStore


def test_cooldown_lifecycle():
    store = InMemoryStateStore()
    assert store.cooldown_active("BTCUSDT", "LONG", cooldown_sec=100, now=1000.0) is False
    store.mark_signal_sent("BTCUSDT", "LONG", now=1000.0)
    assert store.cooldown_active("BTCUSDT", "LONG", cooldown_sec=100, now=1050.0) is True
    assert store.cooldown_active("BTCUSDT", "LONG", cooldown_sec=100, now=1101.0) is False
    # yon bagimsizligi: SHORT icin cooldown yok
    assert store.cooldown_active("BTCUSDT", "SHORT", cooldown_sec=100, now=1050.0) is False


def test_results_and_meta():
    store = InMemoryStateStore()
    store.save_result("BTCUSDT", {"decision": "NO_TRADE"})
    store.record_scan("2026-07-27T00:00:00Z")
    assert store.get_results()["BTCUSDT"]["decision"] == "NO_TRADE"
    meta = store.get_meta()
    assert meta["scan_count"] == 1
    assert meta["last_scan_utc"] == "2026-07-27T00:00:00Z"
