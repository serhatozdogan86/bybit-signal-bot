"""
Entrypoint - bagimlilik kablolamasi (composition root).
Calistirma: python -m app.main
StateStore degisimi (Redis/SQLite) yalnizca buradaki tek satirla yapilir.
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
from app.services.market_data_service import MarketDataService
from app.services.state_store import InMemoryStateStore

log = logging.getLogger("main")


def main() -> None:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        log.warning(kv(event="telegram_env_missing",
                       note="bot calisir ama mesaj gonderemez (/scan/dry kullanilabilir)"))

    store = InMemoryStateStore()  # <- Redis/SQLite'a gecis: bu satiri degistir
    market_data = MarketDataService(BybitClient(settings.BYBIT_BASE_URL))
    notifier = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)
    scheduler = Scheduler(settings, market_data, store, notifier)
    app = create_app(store, scheduler)

    scheduler.start_background()
    port = int(os.getenv("PORT", "10000"))
    log.info(kv(event="server_start", port=port))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
