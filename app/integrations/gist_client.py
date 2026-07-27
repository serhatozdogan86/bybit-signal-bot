"""
GitHub Gist API istemcisi - performans/backtest verisinin kalici deposu.

Neden Gist:
- Ucretsiz ve kalici (Render free plan'in ephemeral disk sorununu cozer)
- Her guncelleme bir revizyon olur -> istatistik GECMISI otomatik saklanir
- Sadece 'gist' scope'lu bir token yeter (repo erisimi GEREKMEZ)

Guvenlik notu: gist "secret" olarak olusturulur (public degil) ama URL'yi bilen
herkes gorebilir. Icerikte API key/secret YOKTUR (sadece sinyal istatistigi ve
OHLCV) - yine de token'i yalnizca gist scope ile sinirlayin.
"""
from __future__ import annotations

import logging

import requests

from app.logging_setup import kv

log = logging.getLogger("gist")

_API = "https://api.github.com"
_TIMEOUT = (10, 30)


class GistClient:
    def __init__(self, token: str) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def find_gist(self, description_marker: str) -> str | None:
        """Kullanicinin gist'leri icinde marker aciklamali olani bulur."""
        try:
            r = self._session.get(f"{_API}/gists", params={"per_page": 100},
                                  timeout=_TIMEOUT)
            r.raise_for_status()
            for g in r.json():
                if g.get("description") == description_marker:
                    return str(g["id"])
            return None
        except requests.RequestException as exc:
            log.error(kv(event="gist_find_error", error=str(exc)[:150]))
            return None

    def create_gist(self, description_marker: str,
                    files: dict[str, str]) -> str | None:
        try:
            r = self._session.post(f"{_API}/gists", timeout=_TIMEOUT, json={
                "description": description_marker, "public": False,
                "files": {n: {"content": c} for n, c in files.items()},
            })
            r.raise_for_status()
            gist_id = str(r.json()["id"])
            log.info(kv(event="gist_created", gist_id=gist_id))
            return gist_id
        except requests.RequestException as exc:
            log.error(kv(event="gist_create_error", error=str(exc)[:150]))
            return None

    def update_gist(self, gist_id: str, files: dict[str, str]) -> bool:
        try:
            r = self._session.patch(f"{_API}/gists/{gist_id}", timeout=_TIMEOUT,
                                    json={"files": {n: {"content": c}
                                                    for n, c in files.items()}})
            r.raise_for_status()
            return True
        except requests.RequestException as exc:
            log.error(kv(event="gist_update_error", gist_id=gist_id,
                         error=str(exc)[:150]))
            return False

    def fetch_gist(self, gist_id: str) -> dict[str, str] | None:
        """Gist dosyalarini {isim: icerik} olarak dondurur (truncation'i cozer)."""
        try:
            r = self._session.get(f"{_API}/gists/{gist_id}", timeout=_TIMEOUT)
            r.raise_for_status()
            out: dict[str, str] = {}
            for name, meta in r.json().get("files", {}).items():
                if meta.get("truncated") and meta.get("raw_url"):
                    raw = self._session.get(meta["raw_url"], timeout=_TIMEOUT)
                    raw.raise_for_status()
                    out[name] = raw.text
                else:
                    out[name] = meta.get("content", "")
            return out
        except requests.RequestException as exc:
            log.error(kv(event="gist_fetch_error", gist_id=gist_id,
                         error=str(exc)[:150]))
            return None

    def gist_url(self, gist_id: str) -> str:
        return f"https://gist.github.com/{gist_id}"
