"""
Scheduler - REST polling dongusu.
- Her SCAN_INTERVAL'de tum semboller taranir; per-symbol hata izolasyonu.
- SIGNAL -> cooldown kontrolu -> Telegram (opsiyonel MarkdownV2).
- Phase 2: SignalTracker ile SESSIZ golge takip:
    * her karar + kapanmis mumlar DB'ye arsivlenir (backtest verisi)
    * SIGNAL'ler izlenir, sonraki mumlarla WIN/LOSS/NOT_FILLED/EXPIRED sonuclanir
    * Telegram'a EK MESAJ ATILMAZ - sonuclar /performance endpoint'inden okunur
- Phase 2: ORDERBOOK_ENRICH=true ise SIGNAL'in liquidity_note'una duvar bilgisi eklenir.
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
from app.services.signal_tracker import SignalTracker
from app.services.state_store import StateStore
from app.services.universe import UniverseProvider
from app.strategies import signal_engine
from app.strategies.liquidity_mapper import orderbook_note

log = logging.getLogger("scheduler")




class Scheduler:
    def __init__(self, settings: Settings, market_data: MarketDataService,
                 store: StateStore, notifier: TelegramNotifier,
                 tracker: SignalTracker | None = None,
                 gist_backup=None,
                 universe: UniverseProvider | None = None) -> None:
        self._settings = settings
        self._md = market_data
        self._store = store
        self._notifier = notifier
        self._tracker = tracker      # None -> golge takip kapali
        self._gist = gist_backup     # None -> gist sync kapali
        self._universe = universe    # None -> static SYMBOLS
        self._params = settings.strategy_params

    def symbols(self) -> list[str]:
        if self._universe is not None:
            return self._universe.get_symbols()
        return self._settings.symbols

    # ------------------------------------------------------------- tarama
    def scan_symbol(self, symbol: str) -> Decision:
        htf = self._md.get_series(symbol, self._settings.HTF)
        ltf = self._md.get_series(symbol, self._settings.LTF)
        decision = signal_engine.evaluate(symbol, htf, ltf, self._params)

        if decision.decision is DecisionType.SIGNAL and self._settings.ORDERBOOK_ENRICH:
            self._enrich_with_orderbook(decision)

        if self._tracker is not None:
            self._shadow_track(decision, htf, ltf)

        log.info(kv(event="scan", symbol=symbol, decision=decision.decision.value,
                    direction=decision.direction.value,
                    reason=decision.reject_reason or decision.setup_type.value))
        return decision

    def _enrich_with_orderbook(self, d: Decision) -> None:
        try:
            ob = self._md.get_orderbook(d.pair)
            note = orderbook_note(ob) if ob else ""
            if note:
                d.liquidity_note = f"{d.liquidity_note} | {note}"
        except Exception:
            log.exception(kv(event="orderbook_enrich_error", symbol=d.pair))

    def _shadow_track(self, decision: Decision, htf, ltf) -> None:
        """Sessiz takip - hatasi taramayi asla durdurmaz."""
        try:
            if htf is not None:
                self._tracker.record_candles(htf)
            if ltf is not None:
                self._tracker.record_candles(ltf)
            self._tracker.record_decision(decision)
            if decision.decision is DecisionType.SIGNAL and ltf is not None:
                self._tracker.maybe_track(decision, ltf)
            self._tracker.evaluate_open(decision.pair)
        except Exception:
            log.exception(kv(event="shadow_error", symbol=decision.pair))

    def scan_all(self, send_telegram: bool = True) -> list[Decision]:
        results: list[Decision] = []
        for symbol in self.symbols():
            try:
                decision = self.scan_symbol(symbol)
            except Exception:
                log.exception(kv(event="scan_error", symbol=symbol))
                continue
            results.append(decision)
            self._store.save_result(symbol, decision.contract_dict())
            if send_telegram:
                self._dispatch(decision)
            time.sleep(self._settings.SYMBOL_PAUSE_SEC)

        self._store.record_scan(
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return results

    # ------------------------------------------------------------ dispatch
    def _render(self, d: Decision) -> str:
        return telegram_formatter.render(d, self._settings.TELEGRAM_PARSE_MODE)

    def _dispatch(self, d: Decision) -> None:
        if d.decision is DecisionType.SIGNAL:
            if self._store.cooldown_active(d.pair, d.direction.value,
                                           self._settings.SIGNAL_COOLDOWN_SEC):
                log.info(kv(event="cooldown_skip", symbol=d.pair,
                            direction=d.direction.value))
                return
            if self._notifier.send(self._render(d)):
                self._store.mark_signal_sent(d.pair, d.direction.value)
        elif d.decision is DecisionType.DATA_MISSING:
            if self._settings.SEND_DATA_MISSING:
                self._notifier.send(self._render(d))
        else:  # NO_TRADE
            if self._settings.SEND_NO_TRADE:
                self._notifier.send(self._render(d))

    # ---------------------------------------------------------------- loop
    def start_background(self) -> None:
        thread = threading.Thread(target=self._loop, daemon=True, name="scan-loop")
        thread.start()

    def _loop(self) -> None:
        s = self._settings
        symbols = self.symbols()
        pairs_txt = (", ".join(symbols) if len(symbols) <= 8
                     else f"{len(symbols)} pairs (top-volume dynamic)")
        log.info(kv(event="scheduler_start", symbol_count=len(symbols),
                    mode=self._universe.mode if self._universe else "static",
                    htf=s.HTF, ltf=s.LTF, interval_s=s.SCAN_INTERVAL,
                    shadow=self._tracker is not None))
        self._notifier.send(
            "Signal engine online.\n"
            f"Pairs: {pairs_txt}\n"
            f"TF: {s.HTF}/{s.LTF} | Scan: {s.SCAN_INTERVAL}s\n"
            f"Mode: conservative swing | Min RR: {s.RISK_REWARD_MIN}\n"
            f"Shadow tracking: {'on' if self._tracker else 'off'} | "
            f"Gist backup: {'on' if self._gist else 'off'}"
        )
        while True:
            try:
                self.scan_all(send_telegram=True)
                if self._gist is not None:
                    self._gist.maybe_sync()
            except Exception:
                log.exception(kv(event="loop_error"))
            time.sleep(s.SCAN_INTERVAL)
