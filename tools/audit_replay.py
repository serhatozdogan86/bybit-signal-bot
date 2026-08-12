"""Kayit-arsiv denetimi - SADECE karsilastirma + sayim (analiz YOK).

NE YAPAR:
  Botun kapanmis kayitlarini (sampiyon 'signals' + aday 'challenger_signals')
  BAGIMSIZ bir mum kaynagiyla yeniden oynatir ve kayitla karsilastirir.
  Mum kaynagi: tools/download_backtest_data.py ciktisi (Bybit'ten ayrica
  indirilen arsiv) - botun kendi 'candles' tablosu DEGIL. Botun arsivindeki
  olasi bir hata kendini dogrulayamasin diye.

  Sampiyon kurallari: app/services/verifier.py (dokunulmadan yeniden
  kullanilir). Aday kurallari: challengers._evaluate_one'in ilan edilmis
  kurallarinin buradaki BAGIMSIZ kopyasi (giris mumu SONRASI; ayni mumda
  stop+tp -> LOSS ambiguous=1; timeout -> EXPIRED, close ile).

NE YAPMAZ (on-kayit kurali, docs/error-prevention.md):
  Istatistik, gosterge, kalip aramasi, getiri analizi YOKTUR. Rapor yalniz
  sayar: kac kayit denetlendi, kaci uyusti, kaci uyusmadi, kaci neden
  denetlenemedi. Uyusmazlik = kayit ile arsiv celisiyor; hukum vermez,
  insana getirir.

CANLI GUVENLIGI:
  --live-db verilirse dosya SALT-OKUNUR acilir ve sqlite backup API ile
  gecici bir kopyaya alinir; denetim yalniz kopyada calisir. Canli
  veritabanina hicbir yazma yapilmaz (CLAUDE.md operasyon kurali).

KULLANIM (VM):
  cd ~/bybit-signal-bot-audit
  sudo .venv/bin/python tools/audit_replay.py \\
      --live-db /opt/bybit-signal-bot/data/bot.db \\
      --data /home/ubuntu/backtest-data
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import verifier                           # noqa: E402

R_TOL = 0.05          # verifier.compare ile ayni R toleransi
DETAIL_LIMIT = 20     # raporda listelenen uyusmazlik sayisi


# ---------------------------------------------------------------- veri erisim
def backup_live(live_path: str, dst_path: str) -> None:
    """Canli DB'yi salt-okunur acip tutarli anlik kopya al (yazma YOK)."""
    src = sqlite3.connect(f"file:{live_path}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(dst_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def load_candles(data_dir: str, pair: str, interval: str = "15"
                 ) -> list[dict] | None:
    """PAIR_15.csv -> [{ts,open,high,low,close}] (artan). Dosya yoksa None."""
    path = os.path.join(data_dir, f"{pair}_{interval}.csv")
    if not os.path.exists(path):
        return None
    out = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out.append({"ts": int(row["ts"]), "open": float(row["open"]),
                        "high": float(row["high"]), "low": float(row["low"]),
                        "close": float(row["close"])})
    out.sort(key=lambda c: c["ts"])
    return out


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ------------------------------------------------------------------- sampiyon
def audit_champion(conn: sqlite3.Connection, data_dir: str,
                   fill_window: int, max_track: int) -> dict:
    rows = _rows(conn, "SELECT * FROM signals WHERE outcome IS NOT NULL "
                       "AND blocked=0 ORDER BY id")
    res = {"closed": len(rows), "checked": 0, "match": 0, "mismatch": 0,
           "mismatch_details": [],
           "skipped": {"arsiv_yok": 0, "pencere_disi": 0,
                       "veri_yetersiz": 0, "plan_eksik": 0}}
    cache: dict[str, list[dict] | None] = {}
    for r in rows:
        if not r.get("entry_candle_ts"):
            res["skipped"]["plan_eksik"] += 1
            continue
        pair = r["pair"]
        if pair not in cache:
            cache[pair] = load_candles(data_dir, pair)
        candles = cache[pair]
        if candles is None:
            res["skipped"]["arsiv_yok"] += 1
            continue
        if r["entry_candle_ts"] < candles[0]["ts"]:
            res["skipped"]["pencere_disi"] += 1     # arsiv o tarihe uzanmiyor
            continue
        rep = verifier.replay(r, candles, fill_window, max_track)
        if rep.get("outcome") is None:
            res["skipped"]["veri_yetersiz"] += 1
            continue
        res["checked"] += 1
        diff = verifier.compare(r, rep)
        if diff is None:
            res["match"] += 1
        else:
            res["mismatch"] += 1
            if len(res["mismatch_details"]) < DETAIL_LIMIT:
                res["mismatch_details"].append(diff)
    return res


# ---------------------------------------------------------------------- aday
def replay_challenger(r: dict, candles: list[dict]) -> dict:
    """challengers._evaluate_one'in ilan edilmis kurallarinin bagimsiz
    kopyasi. Motor kodunu IMPORT ETMEZ - hata kendini dogrulamasin."""
    is_long = r["direction"] == "LONG"
    risk = (r["entry"] - r["stop"]) if is_long else (r["stop"] - r["entry"])
    if risk <= 0:
        return {"outcome": "AMBIGUOUS", "r": 0.0, "ambiguous": 1}
    for i, c in enumerate(candles):
        hit_stop = (c["low"] <= r["stop"]) if is_long else (c["high"] >= r["stop"])
        hit_tp = (c["high"] >= r["tp"]) if is_long else (c["low"] <= r["tp"])
        if hit_stop and hit_tp:
            return {"outcome": "LOSS", "r": -1.0, "ambiguous": 1}
        if hit_stop:
            return {"outcome": "LOSS", "r": -1.0, "ambiguous": 0}
        if hit_tp:
            rr = (r["tp"] - r["entry"]) if is_long else (r["entry"] - r["tp"])
            return {"outcome": "WIN", "r": round(rr / risk, 2), "ambiguous": 0}
        if i + 1 >= r["timeout_bars"]:
            pnl = (c["close"] - r["entry"]) if is_long else (r["entry"] - c["close"])
            return {"outcome": "EXPIRED", "r": round(pnl / risk, 2),
                    "ambiguous": 0}
    return {"outcome": None}                    # arsiv bitti, karar dogmadi


def audit_challengers(conn: sqlite3.Connection, data_dir: str) -> dict:
    rows = _rows(conn, "SELECT * FROM challenger_signals WHERE "
                       "status='CLOSED' AND outcome IS NOT NULL ORDER BY id")
    res = {"closed": len(rows), "checked": 0, "match": 0, "mismatch": 0,
           "mismatch_details": [], "per_strategy": {},
           "skipped": {"arsiv_yok": 0, "pencere_disi": 0, "veri_yetersiz": 0}}
    cache: dict[str, list[dict] | None] = {}
    for r in rows:
        pair = r["pair"]
        if pair not in cache:
            cache[pair] = load_candles(data_dir, pair)
        candles = cache[pair]
        if candles is None:
            res["skipped"]["arsiv_yok"] += 1
            continue
        if r["entry_ts"] < candles[0]["ts"]:
            res["skipped"]["pencere_disi"] += 1
            continue
        seq = [c for c in candles if c["ts"] > r["entry_ts"]]
        rep = replay_challenger(r, seq)
        if rep["outcome"] is None:
            res["skipped"]["veri_yetersiz"] += 1
            continue
        res["checked"] += 1
        ps = res["per_strategy"].setdefault(
            r["strategy"], {"checked": 0, "mismatch": 0})
        ps["checked"] += 1
        problems = []
        if r["outcome"] != rep["outcome"]:
            problems.append(f"sonuc: kayit={r['outcome']} "
                            f"denetci={rep['outcome']}")
        if int(r.get("ambiguous") or 0) != rep["ambiguous"]:
            problems.append(f"ambiguous: kayit={r.get('ambiguous')} "
                            f"denetci={rep['ambiguous']}")
        r_s = r.get("r_multiple")
        if (r_s is not None and rep.get("r") is not None
                and abs(r_s - rep["r"]) > R_TOL):
            problems.append(f"R: kayit={r_s} denetci={rep['r']}")
        if problems:
            res["mismatch"] += 1
            ps["mismatch"] += 1
            if len(res["mismatch_details"]) < DETAIL_LIMIT:
                res["mismatch_details"].append(
                    {"id": r["id"], "strategy": r["strategy"],
                     "pair": pair, "problems": problems})
        else:
            res["match"] += 1
    return res


# --------------------------------------------------------------------- rapor
def run(db_path: str, data_dir: str, fill_window: int = 24,
        max_track: int = 192) -> dict:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        report = {
            "generated_utc": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "note": ("Salt denetim: kayitlar bagimsiz mum arsiviyle yeniden "
                     "oynatildi. Istatistik/analiz YOKTUR; uyusmazlik hukum "
                     "degil, elle inceleme cagrisidir."),
            "champion": audit_champion(conn, data_dir, fill_window, max_track),
            "challengers": audit_challengers(conn, data_dir),
        }
    finally:
        conn.close()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--live-db", help="canli DB (salt-okunur kopyalanir)")
    g.add_argument("--db", help="onceden alinmis kopya DB")
    ap.add_argument("--data", required=True,
                    help="backtest-data klasoru (PAIR_15.csv dosyalari)")
    ap.add_argument("--fill-window", type=int, default=24)
    ap.add_argument("--max-track", type=int, default=192)
    ap.add_argument("--json", default="", help="raporu bu dosyaya da yaz")
    args = ap.parse_args()

    if args.live_db:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        backup_live(args.live_db, tmp.name)
        db_path = tmp.name
        print(f"canli DB salt-okunur kopyalandi -> {db_path}")
    else:
        db_path = args.db

    rep = run(db_path, args.data, args.fill_window, args.max_track)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=2)

    print("\n=== DENETIM RAPORU (salt karsilastirma) ===")
    for adi, k in (("SAMPIYON", "champion"), ("ADAYLAR", "challengers")):
        s = rep[k]
        print(f"{adi}: kapanmis {s['closed']} | denetlenen {s['checked']} | "
              f"uyusan {s['match']} | UYUSMAYAN {s['mismatch']} | "
              f"denetlenemeyen {s['skipped']}")
        for d in s["mismatch_details"]:
            print(f"  ! {d}")
    if rep["challengers"]["per_strategy"]:
        print("aday kirilimi:", json.dumps(
            rep["challengers"]["per_strategy"], ensure_ascii=False))
    bad = rep["champion"]["mismatch"] + rep["challengers"]["mismatch"]
    print("SONUC:", "TEMIZ - kayitlar bagimsiz arsivle uyusuyor"
          if bad == 0 else f"{bad} UYUSMAZLIK - elle incelenmeli")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
