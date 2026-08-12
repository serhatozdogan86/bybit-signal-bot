"""Backtest veri indirici - SADECE indirme + butunluk kontrolu.

KULLANIM (VM'de, autodeploy agacinin DISINDA ayri bir clone'dan):
    cd ~/bybit-signal-bot-audit           # ayri clone (CLAUDE.md kurali)
    python3 tools/download_backtest_data.py --out /home/ubuntu/backtest-data

Ne yapar:
  1. Evreni secer (canli botla AYNI kural: 24s ciroya gore top-N USDT perp,
     stable ciftleri haric - UniverseProvider yeniden kullanilir).
  2. Her parite icin 15dk ve 4sa kline gecmisini (varsayilan 90 gun) Bybit
     v5 public API'den sayfalayarak indirir; olusmakta olan son mum ATILIR.
  3. Parite basina CSV yazar: <SYMBOL>_<interval>.csv (ts,open,high,low,
     close,volume) - mevcut candles export formatiyla ayni.
  4. BUTUNLUK: satir sayisi, beklenen sayi, tekrar (dedup), zaman bosluklari,
     tarih araligi. Sonuc _report.json + konsol ozeti.

Ne YAPMAZ (on-kayit kurali, docs/error-prevention.md):
  Hicbir istatistik, gosterge, kalip aramasi, getiri hesabi YOKTUR.
  Bu betik yalniz veri tasir ve sayar. Analiz, ON-KAYITLI hipotezle ve
  ayri bir adimla yapilir.

Notlar:
  - --resume: butunlugu saglam mevcut CSV'leri atlar (kesinti sonrasi
    kaldigi yerden devam).
  - Bybit public rate limitine karsi istekler arasi kisa bekleme + 429/5xx
    icin ustel geri cekilme vardir. ~150 parite x ~47 istek ~= 20-30 dk.
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

_MS = {"15": 15 * 60_000, "240": 240 * 60_000}
_LIMIT = 200
_TIMEOUT = (10, 30)
_MAX_ATTEMPTS = 4


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def fetch_window(session: requests.Session, base: str, symbol: str,
                 interval: str, start_ms: int, end_ms: int,
                 pause: float) -> list[list[str]] | None:
    """[start,end) araligindaki KAPANMIS mumlari indirir (eski->yeni).

    Bybit yeniden->eskiye dondurur; 'end' imleciyle geriye yuruyerek
    sayfalanir. Hata -> None (parite raporda 'failed' olarak isaretlenir).
    """
    rows_by_ts: dict[int, list[str]] = {}
    cursor_end = end_ms
    while cursor_end > start_ms:
        params = {"category": "linear", "symbol": symbol,
                  "interval": interval, "limit": _LIMIT,
                  "start": start_ms, "end": cursor_end}
        data = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                r = session.get(f"{base}/v5/market/kline", params=params,
                                timeout=_TIMEOUT)
                if r.status_code == 429 or r.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                r.raise_for_status()
                body = r.json()
                if body.get("retCode") != 0:
                    print(f"    ! {symbol} {interval}: API {body.get('retCode')} "
                          f"{body.get('retMsg')}")
                    return None
                data = body.get("result", {}).get("list", [])
                break
            except (requests.RequestException, ValueError) as exc:
                if attempt == _MAX_ATTEMPTS:
                    print(f"    ! {symbol} {interval}: {exc}")
                    return None
                time.sleep(2 ** (attempt - 1))
        if not data:
            break                       # aralikta veri kalmadi (yeni listing)
        oldest = None
        for row in data:
            ts = int(row[0])
            if start_ms <= ts < end_ms:
                rows_by_ts[ts] = row
            oldest = ts if oldest is None else min(oldest, ts)
        if oldest is None or oldest <= start_ms:
            break
        # Bybit v5'te start/end DAHILdir: imlec 'oldest' birakilirsa ayni mum
        # tekrar doner ve pencere baslangicindan sonra listelenen paritede
        # dongu sonsuza gider (2026-08-12 canli vaka). Strict kucult.
        cursor_end = oldest - 1         # bir sonraki sayfa: en eskinin oncesi
        time.sleep(pause)
    return [rows_by_ts[t] for t in sorted(rows_by_ts)]


def integrity(ts_list: list[int], step_ms: int) -> dict:
    """SADECE sayim: satir, tekrar, bosluk, aralik. Istatistik YOK."""
    gaps = []
    for a, b in zip(ts_list, ts_list[1:]):
        if b - a != step_ms:
            gaps.append({"after": _iso(a), "missing": (b - a) // step_ms - 1})
    return {
        "rows": len(ts_list),
        "range": ([_iso(ts_list[0]), _iso(ts_list[-1])] if ts_list else None),
        "gaps": len(gaps),
        "gap_details": gaps[:10],
        "monotonic": all(b > a for a, b in zip(ts_list, ts_list[1:])),
    }


def csv_ok(path: str, step_ms: int, start_ms: int, min_cover: float) -> bool:
    """--resume icin: mevcut CSV istenen araligi bosluksuz kapsiyor mu?"""
    try:
        with open(path, newline="") as f:
            ts = [int(row["ts"]) for row in csv.DictReader(f)]
    except (OSError, ValueError, KeyError):
        return False
    if not ts or ts[0] > start_ms + step_ms * 2:
        return False
    rep = integrity(ts, step_ms)
    return rep["monotonic"] and rep["gaps"] == 0 and \
        len(ts) >= min_cover * ((ts[-1] - ts[0]) // step_ms + 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True,
                    help="cikti dizini (autodeploy agacinin DISINDA olmali)")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--top", type=int, default=150)
    ap.add_argument("--intervals", default="15,240")
    ap.add_argument("--pause", type=float, default=0.12,
                    help="istekler arasi bekleme (sn)")
    ap.add_argument("--base-url", default="https://api.bybit.com")
    ap.add_argument("--resume", action="store_true",
                    help="butunlugu saglam mevcut CSV'leri atla")
    ap.add_argument("--symbols", default="",
                    help="virgullu liste ile evreni ELLE ver (test icin)")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    if "bybit-signal-bot" in out.split(os.sep):
        print("HATA: cikti dizini depo/autodeploy agacinin icinde olamaz "
              f"({out}) - CLAUDE.md operasyon kurali.")
        return 2
    os.makedirs(out, exist_ok=True)

    if args.symbols.strip():
        symbols = [s.strip().upper() for s in args.symbols.split(",")
                   if s.strip()]
    else:
        settings = Settings(SYMBOLS_MODE="top", SYMBOLS_TOP_N=args.top,
                            BYBIT_BASE_URL=args.base_url)
        symbols = UniverseProvider(
            BybitClient(args.base_url), settings).get_symbols()
    if not symbols:
        print("HATA: evren listesi alinamadi (tickers istegi bos dondu).")
        return 2

    intervals = [i.strip() for i in args.intervals.split(",") if i.strip()]
    for iv in intervals:
        if iv not in _MS:
            print(f"HATA: desteklenmeyen interval {iv} (15, 240)")
            return 2

    now_ms = int(time.time() * 1000)
    session = requests.Session()
    report: dict = {
        "generated_utc": _iso(now_ms),
        "days": args.days, "intervals": intervals,
        "universe_size": len(symbols), "symbols": symbols,
        "note": ("Yalniz indirme + butunluk sayimi. Analiz/istatistik "
                 "YOKTUR (on-kayit kurali)."),
        "pairs": {}, "failed": [],
    }
    t0 = time.time()
    for n, symbol in enumerate(symbols, 1):
        report["pairs"][symbol] = {}
        for iv in intervals:
            step = _MS[iv]
            # olusmakta olan son mumu disarida birak: yalniz KAPANMIS mumlar
            end_ms = (now_ms // step) * step
            start_ms = end_ms - args.days * 86_400_000
            path = os.path.join(out, f"{symbol}_{iv}.csv")
            if args.resume and csv_ok(path, step, start_ms, 0.55):
                with open(path, newline="") as f:
                    ts = [int(row["ts"]) for row in csv.DictReader(f)]
                report["pairs"][symbol][iv] = {**integrity(ts, step),
                                               "skipped_resume": True}
                continue
            rows = fetch_window(session, args.base_url, symbol, iv,
                                start_ms, end_ms, args.pause)
            if rows is None:
                report["failed"].append(f"{symbol}:{iv}")
                continue
            with open(path, "w", newline="") as f:
                wr = csv.writer(f)
                wr.writerow(["ts", "open", "high", "low", "close", "volume"])
                for r in rows:
                    wr.writerow([int(r[0]), r[1], r[2], r[3], r[4], r[5]])
            ts_list = [int(r[0]) for r in rows]
            rep = integrity(ts_list, step)
            rep["expected_max"] = args.days * 86_400_000 // step
            report["pairs"][symbol][iv] = rep
            time.sleep(args.pause)
        if n % 10 == 0 or n == len(symbols):
            print(f"  [{n}/{len(symbols)}] {symbol} "
                  f"({time.time() - t0:.0f} sn)")

    # ---- ozet (yalniz sayim) ----
    tot_rows = sum(v.get("rows", 0) for p in report["pairs"].values()
                   for v in p.values())
    tot_gaps = sum(v.get("gaps", 0) for p in report["pairs"].values()
                   for v in p.values())
    all_ranges = [v["range"] for p in report["pairs"].values()
                  for v in p.values() if v.get("range")]
    report["summary"] = {
        "pairs_ok": sum(1 for p in report["pairs"].values()
                        if len(p) == len(intervals)),
        "pairs_failed": len({f.split(":")[0] for f in report["failed"]}),
        "total_candles": tot_rows,
        "total_gap_events": tot_gaps,
        "date_range": ([min(r[0] for r in all_ranges),
                        max(r[1] for r in all_ranges)] if all_ranges else None),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(os.path.join(out, "_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    s = report["summary"]
    print("\n=== RAPOR (yalniz indirme + butunluk) ===")
    print(f"parite: {s['pairs_ok']} tamam / {s['pairs_failed']} basarisiz "
          f"(evren {report['universe_size']})")
    print(f"toplam mum: {s['total_candles']:,}")
    print(f"tarih araligi: {s['date_range']}")
    print(f"bosluk olayi: {s['total_gap_events']} "
          "(detay: _report.json -> gap_details)")
    print(f"sure: {s['elapsed_sec']} sn · cikti: {out}")
    if report["failed"]:
        print(f"basarisiz: {report['failed'][:20]}")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
