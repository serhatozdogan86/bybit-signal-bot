"""
MarketInfoService - dashboard'in "market" ve "news" panelleri icin veri.

- metrics(): Bybit linear ticker'larindan BTC/ETH ozeti + likit evrende
  24s en cok yukselen/dusenler. 60 sn onbellek (MARKET_TTL_SEC).
- news():    Kripto haber RSS/Atom akislarinin birlesik son basliklari.
  10 dk onbellek (NEWS_TTL_SEC). Kaynak hatalari izole edilir; ulasilamayan
  feed atlanir, digerleri gosterilir.

Sunucu tarafinda calisir: tarayici CORS sorunu yasamaz, ustteki kaynaklara
istek sikligi onbellekle sinirlanir. Basliklar dis iceriktir; yorumlanmadan
aynen gosterilir.
"""
from __future__ import annotations

from app.services.ru_text import to_ru
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests

import logging

from app.logging_setup import kv

log = logging.getLogger("market_info")

_FEED_TIMEOUT = 8
_UA = {"User-Agent": "bybit-signal-bot/2.5 (+dashboard news panel)"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(value: str | None) -> float:
    """RSS (RFC822) veya Atom (ISO8601) tarihini epoch'a cevir; olmazsa 0."""
    if not value:
        return 0.0
    try:
        return parsedate_to_datetime(value).timestamp()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def parse_feed(xml_text: str, source: str) -> list[dict]:
    """RSS 2.0 ve Atom akislarini tek bicime indirger. Bozuk XML -> []."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []
    items: list[dict] = []
    # RSS 2.0: <channel><item>
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        ts = _parse_dt(it.findtext("pubDate"))
        if title and link:
            items.append({"title": title, "url": link,
                          "source": source, "ts": ts})
    if items:
        return items
    # Atom: <entry>
    ns = "{http://www.w3.org/2005/Atom}"
    for it in root.iter(f"{ns}entry"):
        title = (it.findtext(f"{ns}title") or "").strip()
        link_el = it.find(f"{ns}link")
        link = (link_el.get("href") if link_el is not None else "") or ""
        ts = _parse_dt(it.findtext(f"{ns}updated")
                       or it.findtext(f"{ns}published"))
        if title and link:
            items.append({"title": title, "url": link,
                          "source": source, "ts": ts})
    return items


class MarketInfoService:
    def __init__(self, bybit_client, settings) -> None:
        self._client = bybit_client
        self._feeds = [u.strip() for u in settings.NEWS_FEEDS.split(",")
                       if u.strip()]
        self._market_ttl = settings.MARKET_TTL_SEC
        self._news_ttl = settings.NEWS_TTL_SEC
        self._lock = threading.Lock()
        self._m_cache: dict | None = None
        self._m_ts = 0.0
        self._n_cache: dict | None = None
        self._n_ts = 0.0
        self._fng_cache: dict | None = None
        self._fng_ts = 0.0
        self._px_cache: dict | None = None
        self._px_ts = 0.0

    # ------------------------------------------------------------- metrics
    def metrics(self) -> dict:
        with self._lock:
            if self._m_cache and time.time() - self._m_ts < self._market_ttl:
                return self._m_cache
        tickers = self._client.get_all_tickers() or []
        by_sym = {t.get("symbol"): t for t in tickers}

        def major(sym: str) -> dict | None:
            t = by_sym.get(sym)
            if not t:
                return None
            return {
                "symbol": sym,
                "last": _f(t.get("lastPrice")),
                "pct24h": _f(t.get("price24hPcnt")) * 100,
                "funding": _f(t.get("fundingRate")) * 100,
                "turnover24h": _f(t.get("turnover24h")),
            }

        # likit filtre: 24s ciro >= 20M USDT (illikit paritelerin +%400
        # gurultusunu eler)
        liquid = [t for t in tickers
                  if _f(t.get("turnover24h")) >= 20_000_000
                  and t.get("symbol", "").endswith("USDT")]
        ranked = sorted(liquid, key=lambda t: _f(t.get("price24hPcnt")),
                        reverse=True)
        mover = lambda t: {"symbol": t.get("symbol"),  # noqa: E731
                           "pct24h": _f(t.get("price24hPcnt")) * 100}
        adv = sum(1 for t in liquid if _f(t.get("price24hPcnt")) > 0)
        dec = sum(1 for t in liquid if _f(t.get("price24hPcnt")) < 0)
        fng = self._get_fng()
        majors = [m for m in (major("BTCUSDT"), major("ETHUSDT")) if m]
        payload = {
            "updated_utc": _now_iso(),
            "majors": majors,
            "gainers": [mover(t) for t in ranked[:3]],
            "losers": [mover(t) for t in ranked[-3:]][::-1],
            "liquid_universe": len(liquid),
            "breadth": {"advancers": adv, "decliners": dec},
            "fng": fng,
            "pulse": _pulse(majors, adv, dec, fng),
            "pulse_ru": to_ru(_pulse(majors, adv, dec, fng)),
        }
        with self._lock:
            self._m_cache, self._m_ts = payload, time.time()
        return payload

    # ---------------------------------------------------------------- news
    def news(self) -> dict:
        with self._lock:
            if self._n_cache and time.time() - self._n_ts < self._news_ttl:
                return self._n_cache
        items: list[dict] = []
        for url in self._feeds:
            source = urlparse(url).netloc.replace("www.", "")
            try:
                resp = requests.get(url, timeout=_FEED_TIMEOUT, headers=_UA)
                if resp.status_code != 200:
                    log.warning(kv(event="news_feed_http", source=source,
                                   status=resp.status_code))
                    continue
                items.extend(parse_feed(resp.text, source))
            except requests.RequestException as exc:
                log.warning(kv(event="news_feed_error", source=source,
                               error=type(exc).__name__))
        items.sort(key=lambda x: x["ts"], reverse=True)
        for it in items:
            it["published_utc"] = (
                datetime.fromtimestamp(it["ts"], tz=timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%SZ") if it["ts"] else None)
            it.pop("ts", None)
        payload = {"updated_utc": _now_iso(), "items": items[:14],
                   "feeds": len(self._feeds)}
        with self._lock:
            self._n_cache, self._n_ts = payload, time.time()
        return payload


    # ------------------------------------------------------------- prices
    def prices(self) -> dict:
        """Tum linear USDT paritelerinin anlik fiyati (30 sn onbellek).

        Dashboard sinyal tablosunun canli fiyat kolonunu besler; tek ucus,
        istemci tarafinda filtrelenir.
        """
        with self._lock:
            if self._px_cache and time.time() - self._px_ts < 30:
                return self._px_cache
        tickers = self._client.get_all_tickers() or []
        payload = {
            "updated_utc": _now_iso(),
            "prices": {t["symbol"]: _f(t.get("lastPrice"))
                       for t in tickers if t.get("symbol", "").endswith("USDT")},
        }
        with self._lock:
            self._px_cache, self._px_ts = payload, time.time()
        return payload

    # -------------------------------------------------- fear & greed (1 sa)
    def _get_fng(self) -> dict | None:
        with self._lock:
            if self._fng_cache and time.time() - self._fng_ts < 3600:
                return self._fng_cache
        try:
            resp = requests.get("https://api.alternative.me/fng/?limit=1",
                                timeout=_FEED_TIMEOUT, headers=_UA)
            data = (resp.json().get("data") or [{}])[0]
            value = int(data.get("value"))
            fng = {"value": value,
                   "label_en": data.get("value_classification", ""),
                   "label_tr": _fng_tr(value)}
        except Exception:  # noqa: BLE001 - dis kaynak; hata FNG'siz devam
            log.warning(kv(event="fng_fetch_error"))
            fng = None
        with self._lock:
            self._fng_cache, self._fng_ts = fng, time.time()
        return fng


def _fng_tr(v: int) -> str:
    if v < 25:
        return "Asiri Korku"
    if v < 45:
        return "Korku"
    if v <= 55:
        return "Notr"
    if v <= 75:
        return "Acgozluluk"
    return "Asiri Acgozluluk"


def _pulse(majors: list[dict], adv: int, dec: int,
           fng: dict | None) -> str:
    """Kural tabanli anlik piyasa okumasi (yorum degil, sablon).

    Girdi: BTC/ETH 24s, likit evren genisligi, korku/acgozluluk endeksi.
    Cikti: tek paragraf Turkce ozet + motorun sinyal profiline baglanti.
    """
    btc = next((m for m in majors if m["symbol"] == "BTCUSDT"), None)
    parts: list[str] = []
    if btc:
        eth = next((m for m in majors if m["symbol"] == "ETHUSDT"), None)
        seg = f"BTC 24s {btc['pct24h']:+.1f}%"
        if eth:
            seg += f", ETH {eth['pct24h']:+.1f}%"
        parts.append(seg + ".")
    total = adv + dec
    if total:
        ratio = adv / total
        tone = ("genislik pozitif" if ratio > 0.6 else
                "genislik negatif" if ratio < 0.4 else "genislik karisik")
        parts.append(f"Likit evrende {adv} yukselen / {dec} dusen -> {tone}.")
    if fng:
        parts.append(f"Korku/Acgozluluk {fng['value']} ({fng['label_tr']}).")
    # motor profiline baglanti
    if btc:
        neg = btc["pct24h"] < -1 or (total and adv / total < 0.4)
        pos = btc["pct24h"] > 1 or (total and adv / total > 0.6)
        if neg:
            parts.append("Risk istahi zayif: karsi-trend LONG kurulumlari "
                         "dusuk olasilikli bolgede; SHORT tarafinin "
                         "kosullari daha temiz.")
        elif pos:
            parts.append("Risk istahi guclu: karsi-trend SHORT kurulumlari "
                         "dusuk olasilikli bolgede; LONG tarafinin "
                         "kosullari daha temiz.")
        else:
            parts.append("Yon netligi dusuk: motorun NO_TRADE agirlikli "
                         "davranmasi beklenir; sabir maliyet degildir.")
    return " ".join(parts)


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0
