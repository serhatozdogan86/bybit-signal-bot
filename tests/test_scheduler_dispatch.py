"""
Scheduler dispatch testleri - kalite kontrol regresyonlari:
1. scan_all(send_telegram=False) HICBIR kosulda notifier'i cagirmaz (/scan/dry garantisi).
2. SIGNAL'de notifier bir kez cagrilir; cooldown penceresinde tekrar cagrilmaz.
3. SEND_NO_TRADE/SEND_DATA_MISSING=false iken bu kararlar gonderilmez.
"""
from __future__ import annotations

from app.config.settings import Settings
from app.models.candle import KlineSeries
from app.scheduler import Scheduler
from app.services.state_store import InMemoryStateStore
from tests import fixtures as fx


class SpyNotifier:
    """Gonderimleri kaydeden sahte notifier."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    @property
    def configured(self) -> bool:
        return True

    def send(self, text: str) -> bool:
        self.sent.append(text)
        return True


class StubMarketData:
    """Sabit fixture serileri dondurur; symbol'e gore SIGNAL ya da DATA_MISSING."""

    def __init__(self, produce_signal: bool = True) -> None:
        self._signal = produce_signal

    def get_series(self, symbol: str, interval: str) -> KlineSeries | None:
        if not self._signal:
            return None
        if interval == "240":
            return fx.make_series(fx.bullish_htf_closes(), symbol, "240", seed=3)
        return fx.make_series(fx.bullish_ltf_closes(), symbol, "15",
                              volumes=fx.breakout_volumes(), seed=4)


def _make(settings: Settings, produce_signal: bool = True) -> tuple[Scheduler, SpyNotifier]:
    notifier = SpyNotifier()
    sched = Scheduler(settings, StubMarketData(produce_signal),
                      InMemoryStateStore(), notifier)  # type: ignore[arg-type]
    return sched, notifier


def test_dry_scan_never_sends_telegram():
    settings = Settings(SYMBOLS="TESTUSDT")
    sched, notifier = _make(settings, produce_signal=True)
    results = sched.scan_all(send_telegram=False)
    assert results[0].decision.value == "SIGNAL"   # sinyal uretildi...
    assert notifier.sent == []                     # ...ama Telegram'a gitmedi


def test_signal_sent_once_then_cooldown():
    settings = Settings(SYMBOLS="TESTUSDT", SIGNAL_COOLDOWN_SEC=3600)
    sched, notifier = _make(settings, produce_signal=True)
    sched.scan_all(send_telegram=True)
    sched.scan_all(send_telegram=True)             # ayni sinyal, cooldown icinde
    assert len(notifier.sent) == 1
    assert "SIGNAL | TESTUSDT | LONG" in notifier.sent[0]


def test_data_missing_not_sent_by_default():
    settings = Settings(SYMBOLS="TESTUSDT", SEND_DATA_MISSING=False)
    sched, notifier = _make(settings, produce_signal=False)
    results = sched.scan_all(send_telegram=True)
    assert results[0].decision.value == "DATA_MISSING"
    assert notifier.sent == []


def test_telegram_disabled_mutes_everything():
    """TELEGRAM_ENABLED=false: SIGNAL uretilir, izlenir ama mesaj GITMEZ."""
    settings = Settings(SYMBOLS="TESTUSDT", TELEGRAM_ENABLED=False)
    sched, notifier = _make(settings, produce_signal=True)
    results = sched.scan_all(send_telegram=True)
    assert results[0].decision.value == "SIGNAL"
    assert notifier.sent == []
