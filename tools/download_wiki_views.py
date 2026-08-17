"""Wikipedia gunluk goruntuleme indirici - S-ATT1 verisi (SADECE indirme).

KULLANIM (VM'de, autodeploy agacinin DISINDA ayri clone'dan):
    cd ~/bybit-signal-bot-audit && git pull
    python3 tools/download_wiki_views.py --out /home/ubuntu/backtest-data

Ne yapar:
  1. data/wiki-eslesme.csv esleme tablosunu okur (sembol -> makale).
  2. Her makale icin Wikimedia REST API'den gunluk goruntuleme ceker
     (en.wikipedia, agent=USER - bot trafigi disarida; on-kayit eki
     2026-08-17). Varsayilan 200 gun: 90 gun taban + 90 gun test + tampon.
  3. Tek CSV yazar: wiki_views.csv (symbol,article,date,views).
  4. CIFT KONTROLUN 2. AYAGI: makale bulunamazsa (404) sembol DURUSTCE
     dislanir ve raporda listelenir; gun boslukları sayilir.

Ne YAPMAZ (on-kayit kurali): istatistik/kalip aramasi YOK - yalniz veri
tasima + butunluk sayimi. Analiz ayri adimda (tools/backtest_att1.py).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

_API = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        "en.wikipedia/all-access/user/{article}/daily/{start}/{end}")
_UA = ("bybit-signal-bot-research/1.0 "
       "(S-ATT1 on-kayitli backtest; kisisel arastirma)")
_MAX_ATTEMPTS = 4
_TIMEOUT = (10, 30)


def build_url(article: str, start: str, end: str) -> str:
    """Makale adi -> API URL (bosluk -> alt cizgi, tam yuzde-kodlama)."""
    return _API.format(article=quote(article.replace(" ", "_"), safe=""),
                       start=start, end=end)


def parse_views(payload: dict) -> dict[str, int]:
    """API cevabi -> {YYYYMMDD: goruntuleme}. Bozuk kayit atlanir."""
    out: dict[str, int] = {}
    for item in payload.get("items", []):
        ts = str(item.get("timestamp", ""))[:8]
        try:
            out[ts] = int(item["views"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def expected_dates(start: str, end: str) -> list[str]:
    """YYYYMMDD araligindaki tum gunler (iki uc dahil)."""
    d0 = datetime.strptime(start, "%Y%m%d")
    d1 = datetime.strptime(end, "%Y%m%d")
    out = []
    while d0 <= d1:
        out.append(d0.strftime("%Y%m%d"))
        d0 += timedelta(days=1)
    return out


def fetch_article(session: requests.Session, article: str, start: str,
                  end: str) -> dict[str, int] | None:
    """Bir makalenin gunluk serisi; 404 -> None (makale yok), agir hata
    -> None. 429/5xx ustel geri cekilmeyle denenir."""
    url = build_url(article, start, end)
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            resp = session.get(url, timeout=_TIMEOUT,
                               headers={"User-Agent": _UA})
            if resp.status_code == 404:
                return None
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return parse_views(resp.json())
        except (requests.RequestException, ValueError) as exc:
            if attempt == _MAX_ATTEMPTS:
                print(f"  HATA {article}: {exc}")
                return None
            time.sleep(2 ** attempt)
    return None


def load_mapping(path: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sym = (row.get("symbol") or "").strip()
            art = (row.get("article") or "").strip()
            if not sym or not art or sym in seen:
                continue
            seen.add(sym)
            rows.append((sym, art))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="cikti klasoru")
    ap.add_argument("--map", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "wiki-eslesme.csv"))
    ap.add_argument("--days", type=int, default=200,
                    help="kac gun geriye (varsayilan 200 = 90 taban + "
                         "90 test + tampon)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    mapping = load_mapping(args.map)
    if not mapping:
        print("HATA: esleme tablosu bos:", args.map)
        return 2
    # son TAM gun = dun (bugunun sayimi bitmedi)
    end_d = datetime.now(timezone.utc).date() - timedelta(days=1)
    start_d = end_d - timedelta(days=args.days - 1)
    start, end = start_d.strftime("%Y%m%d"), end_d.strftime("%Y%m%d")
    exp = expected_dates(start, end)

    session = requests.Session()
    out_rows: list[tuple] = []
    ok, missing_article, gap_total = [], [], 0
    for sym, art in mapping:
        views = fetch_article(session, art, start, end)
        if views is None:
            missing_article.append(f"{sym} ({art})")
            time.sleep(0.3)
            continue
        gaps = sum(1 for d in exp if d not in views)
        gap_total += gaps
        ok.append((sym, len(views), gaps))
        for d in sorted(views):
            out_rows.append((sym, art, d, views[d]))
        time.sleep(0.3)                     # Wikimedia nezaket araligi

    out_csv = os.path.join(args.out, "wiki_views.csv")
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "article", "date", "views"])
        w.writerows(out_rows)

    report = {
        "generated_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "range": [start, end], "days": args.days,
        "mapped": len(mapping), "ok": len(ok),
        "missing_article": missing_article,
        "gap_days_total": gap_total,
        "rows": len(out_rows), "csv": out_csv,
    }
    with open(os.path.join(args.out, "_wiki_report.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n=== WIKI GORUNTULEME RAPORU ===")
    print(f"aralik: {start} -> {end} ({args.days} gun)")
    print(f"esleme: {len(mapping)} sembol | veri OK: {len(ok)} | "
          f"makale bulunamadi: {len(missing_article)}")
    if missing_article:
        print("BULUNAMAYAN (dislandi):")
        for m in missing_article:
            print("  -", m)
    print(f"toplam gun boslugu: {gap_total} | satir: {len(out_rows)}")
    print(f"cikti: {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
