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
from app.services.challengers import ChallengerEngine
from app.services.signal_tracker import SignalTracker, _cluster_id
from app.services.state_store import StateStore
from app.services.universe import UniverseProvider
from app.strategies import signal_engine
from app.strategies.liquidity_mapper import orderbook_note

log = logging.getLogger("scheduler")


class ScanBusy(RuntimeError):
    """Bir tarama zaten calisiyorken ikinci tarama istendi.

    Arka plan dongusu ile HTTP /scan ayni Scheduler nesnesini paylasir.
    Es zamanli iki tarama: ayni sinyali iki kez izlemeye alabilir, kararlari
    mukerrer yazabilir ve rejim durumunu ortada degistirebilir - yani olcum
    verisini bozar. Kilit bunu engeller; ikinci cagri kuyruga GIRMEZ, reddedilir.
    """




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
        self._scan_lock = threading.Lock()   # es zamanli tarama koruma
        self._funding_map: dict[str, float] = {}
        # Aday motoru (Faz B): sampiyondan tamamen izole golge yarisci.
        # Kurulum hatasi taramayi ASLA engellemez.
        self.challengers = None
        if tracker is not None:
            try:
                self.challengers = ChallengerEngine(tracker.db, settings.LTF)
                if gist_backup is not None:
                    gist_backup.set_challengers(self.challengers)
            except Exception:
                log.exception(kv(event="challenger_init_error"))

    def symbols(self) -> list[str]:
        if self._universe is not None:
            return self._universe.get_symbols()
        return self._settings.symbols

    # ------------------------------------------------------------- tarama
    def _refresh_funding_map(self) -> None:
        """Tarama basina 1 toplu tickers cagrisi (S4 funding girdisi).
        Hata -> eski harita kalir; bos harita S4'u sessizce susturur."""
        if self.challengers is None:
            return
        try:
            tickers = self._md.get_all_tickers() or []
            fresh = {}
            for t in tickers:
                try:
                    fresh[t.get("symbol")] = float(t.get("fundingRate"))
                except (TypeError, ValueError):
                    continue
            if fresh:
                self._funding_map = fresh
        except Exception:
            log.exception(kv(event="funding_map_error"))

    def scan_symbol(self, symbol: str) -> Decision:
        htf = self._md.get_series(symbol, self._settings.HTF)
        ltf = self._md.get_series(symbol, self._settings.LTF)
        decision = signal_engine.evaluate(symbol, htf, ltf, self._params,
                                          market_bias=self._market_bias)

        if decision.decision is DecisionType.SIGNAL and self._settings.ORDERBOOK_ENRICH:
            self._enrich_with_orderbook(decision)

        if self._tracker is not None:
            self._shadow_track(decision, htf, ltf)
        if self.challengers is not None:
            try:
                self.challengers.on_scan(symbol, htf, ltf,
                                         self._funding_map.get(symbol))
                self.challengers.evaluate_open(symbol)
            except Exception:
                log.exception(kv(event="challenger_scan_error", symbol=symbol))

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
                heat = self._tracker.heat_check(
                    decision.direction.value, _cluster_id(decision, ltf))
                if heat is None:
                    self._tracker.maybe_track(decision, ltf)
                else:
                    self._tracker.track_portfolio_blocked(decision, ltf, heat)
            elif ("MARKET_GATE" in (decision.failed_filters or [])
                  and "counter-regime" in (decision.reject_reason or "")
                  and ltf is not None):
                self._tracker.track_blocked(decision, ltf)  # v3.4 karsi-olgu
            self._tracker.evaluate_open(decision.pair)
        except Exception:
            log.exception(kv(event="shadow_error", symbol=decision.pair))

    def scan_all(self, send_telegram: bool = True) -> list[Decision]:
        """Tam evren taramasi. Ayni anda YALNIZ BIR tarama calisabilir.

        Mesgulse ScanBusy firlatir (beklemez): manuel tetik ile arka plan
        dongusunun ust uste binmesi veri bozar, kuyruk ise gecikmeyi buyutur.
        """
        if not self._scan_lock.acquire(blocking=False):
            log.warning(kv(event="scan_busy", note="es zamanli tarama reddedildi"))
            raise ScanBusy("scan already in progress")
        try:
            return self._scan_all_locked(send_telegram)
        finally:
            self._scan_lock.release()

    def scan_in_progress(self) -> bool:
        return self._scan_lock.locked()

    def _scan_all_locked(self, send_telegram: bool) -> list[Decision]:
        self._market_bias = self._compute_market_bias()
        self._refresh_funding_map()
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
            try:
                # v3.6-P1: gercek funding yakalama (tarama basina <=2 cagri)
                self._tracker.backfill_funding(self._md)
            except Exception:
                log.exception(kv(event="funding_backfill_loop_error"))
            try:
                # v3.6: periyodik BAGIMSIZ sonuc denetimi (~6 saatte bir).
                # Amac: muhasebe hatasini insanin fark etmesini BEKLEMEMEK.
                self._audit_tick = getattr(self, "_audit_tick", 0) + 1
                if self._audit_tick % 24 == 1:
                    rep = self._tracker.verify_outcomes()
                    log.info(kv(event="outcome_audit", checked=rep["checked"],
                                mismatches=rep["mismatches"]))
                    if rep["mismatches"]:
                        self._tracker.log_gate_event(
                            "audit_mismatch",
                            f"{rep['mismatches']} kayit mum arsiviyle celisiyor")
            except Exception:
                log.exception(kv(event="outcome_audit_error"))
        self._store.record_scan(
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return results

    # ---------------------------------------------------- v3.0 yardimcilar
    def _compute_market_bias(self) -> str:
        """BTC 4H rejimi -> bull / bear / neutral / halt  (v3.5).

        Konsey revizyonlari:
        - HISTEREZIS: rejim degisimi icin son 2 KAPANMIS 4H mumun da esigin
          otesinde olmasi gerekir (esik +-%0.5). Kosul saglanmazsa onceki
          rejim korunur -> EMA cevresi testere kapiyi titretmez.
        - FAIL-CLOSED + TTL: BTC verisi alinamazsa son bilinen rejim 2 saat
          (TTL) daha kullanilir; TTL de asilirsa "halt" doner ve kapi HER
          IKI yonu de keser. Kor ucus yok.
        """
        now = time.time()
        try:
            series = self._md.get_series("BTCUSDT", self._settings.HTF)
            if series is None or len(series) < 120:
                raise ValueError("insufficient BTC data")
            close = series.to_dataframe()["close"]
            ema = close.ewm(span=200, adjust=False).mean()
            band = 0.005
            votes = []
            for i in (-2, -1):          # son iki kapanmis 4H mum
                diff = close.iloc[i] / ema.iloc[i] - 1
                votes.append("bull" if diff > band
                             else "bear" if diff < -band else "neutral")
            prev = getattr(self, "_bias_state", "neutral")
            if votes[0] == votes[1] and votes[1] != "neutral":
                bias = votes[1]                      # 2 mumluk teyitli gecis
            elif votes[1] == "neutral" and prev != "neutral":
                bias = prev                          # banda geri sarkti: koru
            elif prev == "neutral" and votes[1] != "neutral":
                bias = prev                          # tek mum yetmez: bekle
            else:
                bias = prev
            self._bias_state = bias
            self._bias_ts = now
            log.info(kv(event="market_bias", bias=bias,
                        votes="/".join(votes)))
            # v3.6-P1: histerezis gecikmesini olcmek icin kalici gunluk
            self._log_gate(prev, bias, votes)
            return bias
        except Exception:
            log.exception(kv(event="market_bias_error"))
            last_ts = getattr(self, "_bias_ts", 0.0)
            if now - last_ts <= 7200 and hasattr(self, "_bias_state"):
                log.warning(kv(event="market_bias_stale",
                               bias=self._bias_state,
                               age_s=int(now - last_ts)))
                self._log_gate_event("ttl_stale",
                                     f"bias={self._bias_state} "
                                     f"age_s={int(now - last_ts)}")
                return self._bias_state              # TTL icinde: son rejim
            self._log_gate_event("halt", "fail-closed: veri yok, TTL asildi")
            return "halt"                            # fail-closed

    def _log_gate(self, prev: str, bias: str, votes: list[str]) -> None:
        """Gecis ve bekleyen-gecis olaylarini tracker gunlugune yaz."""
        if prev != bias:
            self._log_gate_event("transition",
                                 f"{prev}->{bias} votes={'/'.join(votes)}")
        elif votes[-1] not in ("neutral", bias):
            # son mum karsi oy verdi ama histerezis teyit bekliyor:
            # bu kayitlarin suresi = histerezisin urettigi gecikme
            self._log_gate_event("pending_flip",
                                 f"state={bias} votes={'/'.join(votes)}")

    def _log_gate_event(self, kind: str, detail: str) -> None:
        tracker = getattr(self, "_tracker", None)
        if tracker is None:
            return
        try:
            tracker.log_gate_event(kind, detail)
        except Exception:
            log.exception(kv(event="gate_log_write_error"))

    def _evaluate_orphans(self, scanned: set[str]) -> None:
        """Evren disina dusen paritelerin acik sinyallerini yasat (v3.0).

        IONQ vakasi: parite top-N listesinden cikinca taranmiyor, acik
        sinyali sonsuza dek PENDING kaliyordu. Artik her tur sonunda,
        taranmamis acik-sinyalli pariteler icin mum cekilir ve
        degerlendirme calistirilir.
        """
        try:
            pairs = set(self._tracker.open_pairs())
            if self.challengers is not None:
                pairs |= set(self.challengers.open_pairs())
            pairs = [p for p in pairs if p not in scanned]
        except Exception:
            log.exception(kv(event="orphan_list_error"))
            return
        for pair in pairs:
            try:
                ltf = self._md.get_series(pair, self._settings.LTF)
                if ltf is not None and len(ltf):
                    self._tracker.record_candles(ltf)
                self._tracker.evaluate_open(pair)
                if self.challengers is not None:
                    self.challengers.evaluate_open(pair)
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
                try:
                    self.scan_all(send_telegram=True)
                except ScanBusy:
                    # manuel tarama suruyor: bu turu atla (15 dk sonra tekrar)
                    log.warning(kv(event="loop_skip_busy"))
                if self._commentary is not None:
                    self._commentary.maybe_generate()
                if self._gist is not None:
                    self._gist.maybe_sync()
            except Exception:
                log.exception(kv(event="loop_error"))
            time.sleep(s.SCAN_INTERVAL)
