"""
Telegram Bot API notifier (plain text - MVP'de parse_mode gonderilmez).
Davranis sozlesmesi:
- Timeout: connect 10s / read 15s.
- Retry: network hatasi ve 5xx -> exponential backoff (1s, 2s), toplam 3 deneme.
- HTTP 429 -> yanittaki parameters.retry_after kadar bekle, deneme hakki yakmadan tekrarla (en fazla 2 kez).
- Tum denemeler biterse ERROR loglanir ve False doner; SERVIS DUSMEZ (bildirim kaybi kabul edilir).
- Token/chat_id yoksa WARNING loglanir, False doner (dry-run calismaya devam eder).
"""
from __future__ import annotations

import logging
import time

import requests

from app.logging_setup import kv

log = logging.getLogger("telegram")

_MAX_ATTEMPTS = 3
_MAX_RATE_LIMIT_WAITS = 2
_TIMEOUT = (10, 15)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, parse_mode: str = "") -> None:
        self._token = bot_token
        self._chat_id = chat_id
        self._parse_mode = parse_mode  # "" = plain text | "MarkdownV2"
        self._session = requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self._token and self._chat_id)

    def send(self, text: str) -> bool:
        if not self.configured:
            log.warning(kv(event="telegram_not_configured"))
            return False

        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {"chat_id": self._chat_id, "text": text,
                   "disable_web_page_preview": True}
        if self._parse_mode:
            payload["parse_mode"] = self._parse_mode

        rate_limit_waits = 0
        attempt = 1
        while attempt <= _MAX_ATTEMPTS:
            try:
                resp = self._session.post(url, json=payload, timeout=_TIMEOUT)

                if resp.status_code == 429 and rate_limit_waits < _MAX_RATE_LIMIT_WAITS:
                    retry_after = int(
                        resp.json().get("parameters", {}).get("retry_after", 3)
                    )
                    rate_limit_waits += 1
                    log.warning(kv(event="telegram_rate_limited",
                                   retry_after_s=retry_after, wait_no=rate_limit_waits))
                    time.sleep(min(retry_after, 30))
                    continue  # deneme hakki yakmadan tekrar

                if resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}")

                body = resp.json()
                if body.get("ok"):
                    return True
                # 4xx: kalici hata (yanlis chat_id vb.) -> retry etme
                log.error(kv(event="telegram_api_error",
                             status=resp.status_code,
                             description=body.get("description", "")[:200]))
                return False

            except (requests.RequestException, ValueError) as exc:
                wait = 2 ** (attempt - 1)
                log.warning(kv(event="telegram_retry", attempt=attempt,
                               max=_MAX_ATTEMPTS, error=str(exc), wait_s=wait))
                if attempt == _MAX_ATTEMPTS:
                    log.error(kv(event="telegram_failed", error=str(exc)))
                    return False
                time.sleep(wait)
                attempt += 1
        return False
