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
                 universe: UniverseProvider | None = None,
                 commentary=None) -> None:
        self._settings = settings
        self._md = market_data
        self._store = store
        self._notifier = notifier
        self._tracker = tracker      # None -> golge takip kapali
        self._gist = gist_backup     # None -> gist sync kapali
        self._commentary = commentary  # None -> saatlik yorum kapali
        self._market_bias = "neutral"   # v3.0: her tam taramada guncellenir
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
        decision = signal_engine.evaluate(symbol, htf, ltf, self._params,
                                          market_bias=self._market_bias)

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
            elif ("MARKET_GATE" in (decision.failed_filters or [])
                  and ltf is not None):
                self._tracker.track_blocked(decision, ltf)  # v3.4 karsi-olgu
            self._tracker.evaluate_open(decision.pair)
        except Exception:
            log.exception(kv(event="shadow_error", symbol=decision.pair))

    def scan_all(self, send_telegram: bool = True) -> list[Decision]:
        self._market_bias = self._compute_market_bias()
        if self._commentary is not None:
            self._commentary.market_bias = self._market_bias
        results: list[Decision] = []
        scanned: set[str] = set()
        for symbol in self.symbols():
            try:
                decision = self.scan_symbol(symbol)
            except Exception:
                log.exception(kv(event="scan_error", symbol=symbol))
                continue
            results.append(decision)
            scanned.add(symbol)
            self._store.save_result(symbol, decision.contract_dict())
            if send_telegram:
                self._dispatch(decision)
            time.sleep(self._settings.SYMBOL_PAUSE_SEC)

        if self._tracker is not None:
            self._evaluate_orphans(scanned)
        self._store.record_scan(
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return results

    # ---------------------------------------------------- v3.0 yardimcilar
    def _compute_market_bias(self) -> str:
        """BTC 4H kapanisinin EMA200'e konumu -> bull / bear / neutral.

        Motorun yon kapisi (market gate) icin tek referans. Veri yoksa veya
        yetersizse "neutral" doner (fail-open: kapi kimseyi bloklamaz).
        Notr bant +-%0.25: EMA uzerinde surtunen fiyatta kapi titremesin.
        """
        try:
            series = self._md.get_series("BTCUSDT", self._settings.HTF)
            if series is None or len(series) < 120:
                return "neutral"
            close = series.to_dataframe()["close"]
            ema = close.ewm(span=200, adjust=False).mean().iloc[-1]
            diff = close.iloc[-1] / ema - 1
            bias = "bull" if diff > 0.0025 else "bear" if diff < -0.0025 else "neutral"
            log.info(kv(event="market_bias", bias=bias, diff=f"{diff:+.4f}"))
            return bias
        except Exception:
            log.exception(kv(event="market_bias_error"))
            return "neutral"

    def _evaluate_orphans(self, scanned: set[str]) -> None:
        """Evren disina dusen paritelerin acik sinyallerini yasat (v3.0).

        IONQ vakasi: parite top-N listesinden cikinca taranmiyor, acik
        sinyali sonsuza dek PENDING kaliyordu. Artik her tur sonunda,
        taranmamis acik-sinyalli pariteler icin mum cekilir ve
        degerlendirme calistirilir.
        """
        try:
            pairs = [p for p in self._tracker.open_pairs() if p not in scanned]
        except Exception:
            log.exception(kv(event="orphan_list_error"))
            return
        for pair in pairs:
            try:
                ltf = self._md.get_series(pair, self._settings.LTF)
                if ltf is not None and len(ltf):
                    self._tracker.record_candles(ltf)
                self._tracker.evaluate_open(pair)
                log.info(kv(event="orphan_eval", pair=pair))
            except Exception:
                log.exception(kv(event="orphan_eval_error", pair=pair))

    # ------------------------------------------------------------ dispatch
    def _render(self, d: Decision) -> str:
        return telegram_formatter.render(d, self._settings.TELEGRAM_PARSE_MODE)

    def _dispatch(self, d: Decision) -> None:
        if not self._settings.TELEGRAM_ENABLED:
            return  # sessiz mod: uretim/golge takip surer, mesaj gitmez
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
        if not s.TELEGRAM_ENABLED:
            log.info(kv(event="telegram_muted",
                        note="signals tracked silently; view at dashboard /"))
            startup_send = lambda _msg: None  # noqa: E731
        else:
            startup_send = self._notifier.send
        startup_send(
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
                if self._commentary is not None:
                    self._commentary.maybe_generate()
                if self._gist is not None:
                    self._gist.maybe_sync()
            except Exception:
                log.exception(kv(event="loop_error"))
            time.sleep(s.SCAN_INTERVAL)
