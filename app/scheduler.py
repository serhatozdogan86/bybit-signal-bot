"""
Scheduler - REST polling dongusu (MVP).
- Her SCAN_INTERVAL'de tum semboller taranir.
- Per-symbol hata izolasyonu: bir sembol patlarsa digerleri etkilenmez.
- SIGNAL -> cooldown kontrolu -> Telegram.
- NO_TRADE / DATA_MISSING -> ilgili flag aciksa Telegram, degilse sadece log + store.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from app.config.settings import Settings
from app.formatting import telegram_formatter
from app.integrations.telegram_notifier import TelegramNotifier
from app.logging_setup import kv
from app.models.decision import Decision, DecisionType
from app.services.market_data_service import MarketDataService
from app.services.state_store import StateStore
from app.strategies import signal_engine

log = logging.getLogger("scheduler")

_SYMBOL_PAUSE_SEC = 1.0  # Bybit rate-limit nezaketi


class Scheduler:
    def __init__(self, settings: Settings, market_data: MarketDataService,
                 store: StateStore, notifier: TelegramNotifier) -> None:
        self._settings = settings
        self._md = market_data
        self._store = store
        self._notifier = notifier
        self._params = settings.strategy_params

    # ------------------------------------------------------------- tarama
    def scan_symbol(self, symbol: str) -> Decision:
        htf = self._md.get_series(symbol, self._settings.HTF)
        ltf = self._md.get_series(symbol, self._settings.LTF)
        decision = signal_engine.evaluate(symbol, htf, ltf, self._params)
        log.info(kv(event="scan", symbol=symbol, decision=decision.decision.value,
                    direction=decision.direction.value,
                    reason=decision.reject_reason or decision.setup_type.value))
        return decision

    def scan_all(self, send_telegram: bool = True) -> list[Decision]:
        results: list[Decision] = []
        for symbol in self._settings.symbols:
            try:
                decision = self.scan_symbol(symbol)
            except Exception:
                log.exception(kv(event="scan_error", symbol=symbol))
                continue
            results.append(decision)
            self._store.save_result(symbol, decision.contract_dict())
            if send_telegram:
                self._dispatch(decision)
            time.sleep(_SYMBOL_PAUSE_SEC)

        self._store.record_scan(
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        return results

    # ------------------------------------------------------------ dispatch
    def _dispatch(self, d: Decision) -> None:
        if d.decision is DecisionType.SIGNAL:
            if self._store.cooldown_active(d.pair, d.direction.value,
                                           self._settings.SIGNAL_COOLDOWN_SEC):
                log.info(kv(event="cooldown_skip", symbol=d.pair,
                            direction=d.direction.value))
                return
            if self._notifier.send(telegram_formatter.render(d)):
                self._store.mark_signal_sent(d.pair, d.direction.value)
        elif d.decision is DecisionType.DATA_MISSING:
            if self._settings.SEND_DATA_MISSING:
                self._notifier.send(telegram_formatter.render(d))
        else:  # NO_TRADE
            if self._settings.SEND_NO_TRADE:
                self._notifier.send(telegram_formatter.render(d))

    # ---------------------------------------------------------------- loop
    def start_background(self) -> None:
        thread = threading.Thread(target=self._loop, daemon=True, name="scan-loop")
        thread.start()

    def _loop(self) -> None:
        s = self._settings
        log.info(kv(event="scheduler_start", symbols=",".join(s.symbols),
                    htf=s.HTF, ltf=s.LTF, interval_s=s.SCAN_INTERVAL))
        self._notifier.send(
            "Signal engine online.\n"
            f"Pairs: {', '.join(s.symbols)}\n"
            f"TF: {s.HTF}/{s.LTF} | Scan: {s.SCAN_INTERVAL}s\n"
            f"Mode: conservative swing | Min RR: {s.RISK_REWARD_MIN}"
        )
        while True:
            try:
                self.scan_all(send_telegram=True)
            except Exception:
                log.exception(kv(event="loop_error"))
            time.sleep(s.SCAN_INTERVAL)
