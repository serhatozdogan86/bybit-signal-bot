"""
Entrypoint - bagimlilik kablolamasi (composition root).
Calistirma: python -m app.main

Phase 2 kablolamasi:
- STATE_BACKEND=sqlite  -> cooldown/sonuclar DB'de (restart'a dayanikli*)
- SHADOW_TRACKING=true  -> SignalTracker sessiz performans takibi + veri arsivi
- USE_WEBSOCKET=true    -> WS kline cache (REST fallback her zaman aktif)
(*) Render free plan'da disk ephemeral'dir - README'deki kalicilik notuna bakin.
"""
from __future__ import annotations

import logging
import os

from app.config.settings import get_settings
from app.integrations.bybit_client import BybitClient
from app.integrations.telegram_notifier import TelegramNotifier
from app.logging_setup import kv, setup_logging
from app.scheduler import Scheduler
from app.server import create_app
from app.services.database import Database
from app.services.commentary import CommentaryService
from app.services.gist_backup import GistBackup
from app.services.market_info import MarketInfoService
from app.services.market_data_service import MarketDataService
from app.services.signal_tracker import SignalTracker
from app.services.sqlite_state_store import SQLiteStateStore
from app.services.state_store import InMemoryStateStore
from app.services.universe import UniverseProvider

log = logging.getLogger("main")


def main() -> None:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        log.warning(kv(event="telegram_env_missing",
                       note="bot calisir ama mesaj gonderemez (/scan/dry kullanilabilir)"))

    # --- kalicilik ---
    db = Database(settings.DB_PATH)
    if settings.STATE_BACKEND.lower() == "sqlite":
        store = SQLiteStateStore(db)
    else:
        store = InMemoryStateStore()

    # --- golge takip (sessiz) ---
    tracker = None
    if settings.SHADOW_TRACKING:
        tracker = SignalTracker(db, settings.LTF,
                                settings.SHADOW_FILL_WINDOW_BARS,
                                settings.SHADOW_MAX_TRACK_BARS)

    # --- market data (opsiyonel WS cache) ---
    cache = None
    ws_client = None
    if settings.USE_WEBSOCKET:
        # Not: WS deneyseldir ve static SYMBOLS listesiyle sinirlidir;
        # top-N dinamik evrende REST kullanilir (zaten yeterli).
        from app.integrations.bybit_ws import BybitWSClient, KlineCache
        cache = KlineCache()
        ws_client = BybitWSClient(cache, settings.symbols,
                                  [settings.HTF, settings.LTF])
    bybit = BybitClient(settings.BYBIT_BASE_URL)
    market_data = MarketDataService(bybit, kline_cache=cache)
    universe = UniverseProvider(bybit, settings)

    # --- v2.5: saatlik degerlendirme + market/haber servisi ---
    commentary = None
    if tracker is not None:
        commentary = CommentaryService(db, tracker,
                                       settings.COMMENT_INTERVAL_SEC)
    market_info = MarketInfoService(bybit, settings)

    # --- gist yedekleme: botun kendi kayit tutma mekanizmasi ---
    gist_backup = None
    if settings.GIST_SYNC and settings.GITHUB_TOKEN and tracker is not None:
        from app.integrations.gist_client import GistClient
        gist_backup = GistBackup(GistClient(settings.GITHUB_TOKEN), tracker,
                                 lambda: universe.get_symbols(),
                                 [settings.HTF, settings.LTF],
                                 settings.GIST_SYNC_INTERVAL_SEC, settings.GIST_ID,
                                 settings.GIST_CANDLE_MODE,
                                 settings.GIST_CANDLE_MAX_ROWS,
                                 commentary=commentary)
        try:
            gist_backup.restore_if_empty()  # redeploy sonrasi self-healing
        except Exception:
            log.exception(kv(event="gist_restore_error"))

    notifier = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN,
                                settings.TELEGRAM_CHAT_ID,
                                settings.TELEGRAM_PARSE_MODE)
    scheduler = Scheduler(settings, market_data, store, notifier, tracker,
                          gist_backup, universe, commentary=commentary)
    app = create_app(store, scheduler, tracker, gist_backup, universe,
                     market_info=market_info, commentary=commentary)

    if ws_client is not None:
        ws_client.start()
    scheduler.start_background()
    port = int(os.getenv("PORT", "10000"))
    log.info(kv(event="server_start", port=port,
                state_backend=settings.STATE_BACKEND,
                shadow=settings.SHADOW_TRACKING, ws=settings.USE_WEBSOCKET,
                gist=gist_backup is not None))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
