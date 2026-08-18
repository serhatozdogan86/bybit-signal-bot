"""
Bybit v5 REST client (public market data - API key GEREKMEZ, emir gonderilmez).
Retry politikasi: network hatasi / HTTP 429 / 5xx -> exponential backoff (1s, 2s, 4s).
API-seviyesi hata (retCode != 0) retry edilmez -> loglanir, None doner.
Hata durumunda None doner; ust katman DATA_MISSING uretir - tahmin yok.
"""
from __future__ import annotations

import logging
import time

import requests

from app.logging_setup import kv

log = logging.getLogger("bybit")

_CATEGORY = "linear"
_KLINE_LIMIT = 200
_MAX_ATTEMPTS = 3
_TIMEOUT = (10, 15)  # (connect, read) saniye

# --- Saglayici tavanlari (VM'den olculdu 2026-08-18; ikiz notu 3b) --------
# Bybit tavani ASARSA hata vermez: retCode=0 doner ve fazlasini SESSIZCE
# kirpar. Olcum: kline limit=1500 -> 1000 satir; funding 200 gun -> 66.3 gun.
# Kirpilan uc ESKI uctur. Bu, midas'ta v4.40 ile kapatilan Finnhub
# kusurunun ayni sinifidir - orada da HTTP 200 ile eksik veri geliyordu.
_KLINE_CAP = 1000            # /v5/market/kline azami satir
_FUNDING_CAP = 200           # /v5/market/funding/history azami satir
# Funding araligi paritye gore 1s/4s/8s olabilir; 200 kayit sirasiyla
# 8.3 / 33.3 / 66.7 gun kapsar. 4 saatlik grup evrenin yarisidir (408/824),
# yani 33 gunden uzun her islem tek istekte EKSIK olculurdu.
_FUNDING_MAX_PAGES = 25      # emniyet freni: 25 x 200 = 5000 kayit


class BybitClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def _get(self, path: str, params: dict) -> dict | None:
        url = f"{self._base_url}{path}"
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                resp = self._session.get(url, params=params, timeout=_TIMEOUT)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                data: dict = resp.json()
                if data.get("retCode") != 0:
                    log.error(kv(event="bybit_api_error", path=path,
                                 ret_code=data.get("retCode"), msg=data.get("retMsg")))
                    return None
                return data
            except (requests.RequestException, ValueError) as exc:
                wait = 2 ** (attempt - 1)
                log.warning(kv(event="bybit_retry", path=path, attempt=attempt,
                               max=_MAX_ATTEMPTS, error=str(exc), wait_s=wait))
                if attempt == _MAX_ATTEMPTS:
                    log.error(kv(event="bybit_failed", path=path, error=str(exc)))
                    return None
                time.sleep(wait)
        return None

    def get_kline_rows(self, symbol: str, interval: str,
                       limit: int = _KLINE_LIMIT) -> list[list[str]] | None:
        """Ham kline satirlari (Bybit sirasi: yeniden eskiye). Hata -> None."""
        if limit > _KLINE_CAP:
            # Tavan ustu istek SESSIZCE kirpilir (retCode=0, 1000 satir).
            # Istegi tavana cekip durumu bildiriyoruz: "istedigim kadar
            # geldi" yanilsamasi ust katmana tasinmasin.
            log.warning(kv(event="bybit_limit_capped", path="/v5/market/kline",
                           symbol=symbol, requested=limit, cap=_KLINE_CAP))
            limit = _KLINE_CAP
        data = self._get("/v5/market/kline", {
            "category": _CATEGORY, "symbol": symbol,
            "interval": interval, "limit": limit,
        })
        if data is None:
            return None
        rows: list[list[str]] = data.get("result", {}).get("list", [])
        return rows or None

    def get_last_price(self, symbol: str) -> float | None:
        data = self._get("/v5/market/tickers", {"category": _CATEGORY, "symbol": symbol})
        if data is None:
            return None
        try:
            return float(data["result"]["list"][0]["lastPrice"])
        except (KeyError, IndexError, ValueError):
            log.error(kv(event="bybit_ticker_parse_error", symbol=symbol))
            return None

    def get_all_tickers(self) -> list[dict] | None:
        """Tum linear pariteler icin ticker listesi (evren secimi icin)."""
        data = self._get("/v5/market/tickers", {"category": _CATEGORY})
        if data is None:
            return None
        return data.get("result", {}).get("list") or None

    def get_orderbook(self, symbol: str, depth: int = 50) -> dict | None:
        """Orderbook snapshot (Phase 2). result: {"b": [[p,s],...], "a": [...]}."""
        data = self._get("/v5/market/orderbook",
                         {"category": _CATEGORY, "symbol": symbol, "limit": depth})
        return data.get("result") if data else None

    def get_open_interest_rows(self, symbol: str,
                               limit: int = 25) -> list[dict] | None:
        """1 saatlik OI noktalari, yeniden eskiye (P4 golge-kohort verisi).

        Donen liste: [{"openInterest": "...", "timestamp": "..."}].
        KONTRAT adedi cinsindendir (USD degil) - P4 on-kaydi bunu sart kosar.
        Hata -> None (etiket bosta kalir; eksik veri eksik kalir).
        """
        data = self._get("/v5/market/open-interest", {
            "category": _CATEGORY, "symbol": symbol,
            "intervalTime": "1h", "limit": limit,
        })
        if data is None:
            return None
        rows: list[dict] = data.get("result", {}).get("list", [])
        return rows or None

    def get_funding_history(self, symbol: str, start_ms: int | None = None,
                            end_ms: int | None = None) -> list[dict] | None:
        """Gercek funding oranlari (v3.6: maliyet modeli v1 verisi).

        Donen liste: [{"fundingRate": "...", "fundingRateTimestamp": "..."}],
        ESKIDEN YENIYE sirali. Hata -> None (cagiran sonraki turda dener).

        SAYFALAMA (2026-08-18, ikiz notu 3b): uc tek istekte en cok 200
        kayit ve YALNIZ en yeni uctan verir; startTime ne kadar geriye
        verilirse verilsin eskiler SESSIZCE duser (retCode=0). Tavana
        dayanan her sayfadan sonra endTime en eski kaydin bir oncesine
        cekilerek aralik tamamlanir.

        Yarim veri DONDURULMEZ: sayfalar arasinda hata olursa None doner.
        Eksik funding, maliyeti oldugundan KUCUK gosterip net-R'yi sisirir;
        fail-soft burada sessiz muhasebe hatasi demektir (fail-close 2.2).
        """
        toplam: dict[str, dict] = {}
        imlec_end = end_ms
        for _ in range(_FUNDING_MAX_PAGES):
            params: dict = {"category": _CATEGORY, "symbol": symbol,
                            "limit": _FUNDING_CAP}
            if start_ms is not None:
                params["startTime"] = int(start_ms)
            if imlec_end is not None:
                params["endTime"] = int(imlec_end)
            data = self._get("/v5/market/funding/history", params)
            if data is None:
                return None                    # yarim veri yerine acik hata
            rows: list[dict] = data.get("result", {}).get("list") or []
            if not rows:
                break
            onceki = len(toplam)
            for r in rows:
                ts = r.get("fundingRateTimestamp")
                if ts is not None:
                    toplam[str(ts)] = r
            if len(rows) < _FUNDING_CAP:
                break                          # tavana dayanmadi -> aralik bitti
            if len(toplam) == onceki:
                break                          # ilerleme yok -> sonsuz dongu freni
            try:
                en_eski = min(int(r["fundingRateTimestamp"]) for r in rows)
            except (KeyError, TypeError, ValueError):
                break
            if start_ms is not None and en_eski <= int(start_ms):
                break                          # aralik basina ulasildi
            imlec_end = en_eski - 1
        else:
            log.warning(kv(event="bybit_funding_pages_exhausted", symbol=symbol,
                           pages=_FUNDING_MAX_PAGES, rows=len(toplam)))
        return [toplam[k] for k in sorted(toplam, key=int)]
