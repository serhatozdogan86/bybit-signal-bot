"""OI (open interest) gecmisi indirici — SADECE indirme + butunluk sayimi.

P1 OI-Flush on-kaydinin (docs/ideas.md 2026-08-14) veri adimi. Bybit v5
/v5/market/open-interest'ten 1 saatlik OI gecmisini parite basina CSV'ye
yazar: <SYMBOL>_oi_1h.csv (ts, open_interest). Evren, canli botla AYNI
kural (UniverseProvider top-N).

Analiz/istatistik YOKTUR (on-kayit kurali) — yalniz tasima ve sayim.

Sayfalama: imlec (nextPageCursor) tabanli. GUVENLIK: her sayfa YENI zaman
damgasi getirmek zorunda; getirmezse dongu kirilir (kline indiricisinde
yasanan sonsuz-dongu SINIFININ kapali tutulmasi — testli).

KULLANIM (VM):
  cd ~/bybit-signal-bot-audit && git pull
  .venv/bin/python tools/download_oi_data.py --out /home/ubuntu/oi-data
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import Settings                    # noqa: E402
from app.integrations.bybit_client import BybitClient       # noqa: E402
from app.services.universe import UniverseProvider          # noqa: E402

_HOUR_MS = 3_600_000
_LIMIT = 200
_TIMEOUT = (10, 30)
_MAX_ATTEMPTS = 4
_MAX_PAGES = 200          # 200*200 nokta >> 90 gun; kacak dongu freni


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def fetch_oi(session: requests.Session, base: str, symbol: str,
             start_ms: int, end_ms: int, pause: float) -> dict[int, str] | None:
    """[start,end] araligindaki 1 saatlik OI noktalari {ts: deger}.
    Hata -> None (parite 'failed'). Ilerlemeyen sayfa -> dongu kirilir."""
    points: dict[int, str] = {}
    cursor = ""
    for _page in range(_MAX_PAGES):
        params = {"category": "linear", "symbol": symbol,
                  "intervalTime": "1h", "limit": _LIMIT,
                  "startTime": start_ms, "endTime": end_ms}
        if cursor:
            params["cursor"] = cursor
        body = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                r = session.get(f"{base}/v5/market/open-interest",
                                params=params, timeout=_TIMEOUT)
                if r.status_code == 429 or r.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                r.raise_for_status()
                body = r.json()
                break
            except (requests.RequestException, ValueError) as exc:
                if attempt == _MAX_ATTEMPTS:
                    print(f"    ! {symbol}: {exc}")
                    return None
                time.sleep(2 ** (attempt - 1))
        if body.get("retCode") != 0:
            print(f"    ! {symbol}: API {body.get('retCode')} "
                  f"{body.get('retMsg')}")
            return None
        rows = (body.get("result") or {}).get("list") or []
        before = len(points)
        for row in rows:
            ts = int(row["timestamp"])
            if start_ms <= ts <= end_ms:
                points[ts] = row["openInterest"]
        cursor = (body.get("result") or {}).get("nextPageCursor") or ""
        # ILERLEME KORUMASI: yeni nokta yoksa ya da imlec bittiyse dur
        if len(points) == before or not cursor:
            break
        time.sleep(pause)
    return points


def integrity(ts_list: list[int]) -> dict:
    """SADECE sayim: nokta, bosluk, aralik (1 saat izgara)."""
    gaps = sum(1 for a, b in zip(ts_list, ts_list[1:])
               if b - a != _HOUR_MS)
    return {"points": len(ts_list),
            "range": ([_iso(ts_list[0]), _iso(ts_list[-1])]
                      if ts_list else None),
            "gaps": gaps,
            "monotonic": all(b > a for a, b in zip(ts_list, ts_list[1:]))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--top", type=int, default=150)
    ap.add_argument("--pause", type=float, default=0.12)
    ap.add_argument("--base-url", default="https://api.bybit.com")
    ap.add_argument("--resume", action="store_true",
                    help="mevcut CSV'si olan pariteyi atla")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    if "bybit-signal-bot" in out.split(os.sep):
        print("HATA: cikti dizini depo agaci icinde olamaz.")
        return 2
    os.makedirs(out, exist_ok=True)

    settings = Settings(SYMBOLS_MODE="top", SYMBOLS_TOP_N=args.top,
                        BYBIT_BASE_URL=args.base_url)
    symbols = UniverseProvider(
        BybitClient(args.base_url), settings).get_symbols()
    if not symbols:
        print("HATA: evren listesi alinamadi.")
        return 2

    now_ms = int(time.time() * 1000)
    end_ms = (now_ms // _HOUR_MS) * _HOUR_MS
    start_ms = end_ms - args.days * 86_400_000
    session = requests.Session()
    report = {"generated_utc": _iso(now_ms), "days": args.days,
              "universe_size": len(symbols),
              "note": "Yalniz indirme + sayim. Analiz YOKTUR.",
              "pairs": {}, "failed": []}
    t0 = time.time()
    for n, symbol in enumerate(symbols, 1):
        path = os.path.join(out, f"{symbol}_oi_1h.csv")
        if args.resume and os.path.exists(path):
            with open(path, newline="") as f:
                ts = [int(row["ts"]) for row in csv.DictReader(f)]
            report["pairs"][symbol] = {**integrity(sorted(ts)),
                                       "skipped_resume": True}
            continue
        pts = fetch_oi(session, args.base_url, symbol, start_ms, end_ms,
                       args.pause)
        if pts is None:
            report["failed"].append(symbol)
            continue
        ts_sorted = sorted(pts)
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ts", "open_interest"])
            for t in ts_sorted:
                w.writerow([t, pts[t]])
        report["pairs"][symbol] = integrity(ts_sorted)
        time.sleep(args.pause)
        if n % 10 == 0 or n == len(symbols):
            print(f"  [{n}/{len(symbols)}] {symbol} "
                  f"({time.time() - t0:.0f} sn)")

    tot = sum(p.get("points", 0) for p in report["pairs"].values())
    ranges = [p["range"] for p in report["pairs"].values() if p.get("range")]
    report["summary"] = {
        "pairs_ok": len(report["pairs"]),
        "pairs_failed": len(report["failed"]),
        "total_points": tot,
        "date_range": ([min(r[0] for r in ranges),
                        max(r[1] for r in ranges)] if ranges else None),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "_oi_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    s = report["summary"]
    print("\n=== OI RAPORU (yalniz indirme + sayim) ===")
    print(f"parite: {s['pairs_ok']} tamam / {s['pairs_failed']} basarisiz")
    print(f"toplam nokta: {s['total_points']:,}")
    print(f"tarih araligi: {s['date_range']}")
    print(f"sure: {s['elapsed_sec']} sn · cikti: {out}")
    if report["failed"]:
        print(f"basarisiz: {report['failed'][:20]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
