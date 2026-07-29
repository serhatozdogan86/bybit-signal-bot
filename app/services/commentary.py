"""
CommentaryService - saatlik otomatik degerlendirme.

Claude'un bu projede elle yaptigi analiz kaliplarinin kural tabanli
kodlanmis halidir: son pencerede sonuclananlar, basabas konumu, yon
bilancosu, giris isabeti, yuksek-RR kaybi uyarisi, orneklem ve golge
muhasebe uyarilari. LLM cagrisi YOKTUR; deterministik sablonlardir ve
dashboard'da da boyle etiketlenir.

Uretim saatte birdir (COMMENT_INTERVAL_SEC); kayitlar DB'de tutulur,
gist yedegine 0_commentary.json olarak eklenir (uzaktan okunabilirlik).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import logging

from app.logging_setup import kv
from app.services.database import Database
from app.services.signal_tracker import SignalTracker

log = logging.getLogger("commentary")

_TABLE = """
CREATE TABLE IF NOT EXISTS commentary(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  text TEXT NOT NULL,
  stats_json TEXT
);
"""

_DISCLAIMER = ("Tum sonuclar golge muhasebedir (varsayimsal giris, kayma ve "
               "komisyon yok); yatirim tavsiyesi degildir.")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_r(v: float) -> str:
    return ("+" if v > 0 else "") + f"{v:.2f}R"


class CommentaryService:
    def __init__(self, db: Database, tracker: SignalTracker,
                 interval_sec: int = 3600) -> None:
        self._db = db
        self._tracker = tracker
        self._interval = interval_sec
        self._last = 0.0
        self.market_bias = "neutral"   # scheduler her turda gunceller (v3.4)
        db.execute(_TABLE)

    # ------------------------------------------------------------ schedule
    def maybe_generate(self) -> None:
        if time.time() - self._last >= self._interval:
            try:
                self.generate()
            except Exception as exc:  # noqa: BLE001 - yorum motoru asla
                log.error(kv(event="commentary_error",  # botu dusurmemeli
                             error=type(exc).__name__))
            self._last = time.time()

    # ------------------------------------------------------------ generate
    def generate(self) -> dict:
        stats = self._tracker.stats()
        signals = self._tracker.recent_signals(500)
        prev = self._latest()
        prev_stats = (json.loads(prev["stats_json"])
                      if prev and prev.get("stats_json") else {})
        prev_ts = prev["ts_utc"] if prev else None

        text = self._compose(stats, signals, prev_stats, prev_ts)
        row = {"ts_utc": _now_iso(), "text": text,
               "stats_json": json.dumps({
                   "decided": stats.get("decided_trades", 0),
                   "total_r": stats.get("total_r_multiple", 0.0),
                   "win_rate": stats.get("win_rate"),
               })}
        self._db.execute(
            "INSERT INTO commentary(ts_utc, text, stats_json) VALUES(?,?,?)",
            (row["ts_utc"], row["text"], row["stats_json"]))
        self._db.execute(
            "DELETE FROM commentary WHERE id NOT IN "
            "(SELECT id FROM commentary ORDER BY id DESC LIMIT 48)")
        log.info(kv(event="commentary_generated"))
        return row

    # -------------------------------------------------------------- compose
    def _compose(self, stats: dict, signals: list[dict],
                 prev_stats: dict, prev_ts: str | None) -> str:
        p: list[str] = []
        decided = stats.get("decided_trades", 0)
        total_r = stats.get("total_r_multiple", 0.0) or 0.0
        cbo = stats.get("closed_by_outcome", {}) or {}
        w = cbo.get("WIN", {"count": 0, "sum_r": 0.0})
        losses = cbo.get("LOSS", {"count": 0, "sum_r": 0.0})

        # 1) Genel durum + onceki yoruma gore degisim
        if not decided:
            p.append("Henuz sonuclanan sinyal yok; motor kosul bekliyor. "
                     "Muhafazakar profilde bu normaldir.")
        else:
            wr = (stats.get("win_rate") or 0.0) * 100
            avg_win = (w["sum_r"] / w["count"]) if w["count"] else None
            be = (100 / (1 + avg_win)) if avg_win else None
            pos = ("basabasin uzerinde" if be is not None and wr > be else
                   "basabasin altinda" if be is not None else
                   "basabas icin kazanc ornegi bekleniyor")
            delta = ""
            if prev_stats:
                d_r = total_r - (prev_stats.get("total_r") or 0.0)
                d_n = decided - (prev_stats.get("decided") or 0)
                if d_n:
                    delta = (f" Onceki degerlendirmeden bu yana {d_n} sinyal "
                             f"sonuclandi, donem katkisi {_fmt_r(d_r)}.")
                else:
                    delta = " Onceki degerlendirmeden bu yana yeni sonuc yok."
            be_txt = f" (basabas ~%{be:.1f})" if be is not None else ""
            p.append(f"Toplam {decided} sonuclanan sinyal: {w['count']} WIN / "
                     f"{losses['count']} LOSS, isabet %{wr:.1f}{be_txt} -> "
                     f"{pos}. Kumulatif {_fmt_r(total_r)}.{delta}")

        # 2) Son pencerede sonuclananlar (closed_utc ile)
        window = [s for s in signals
                  if s.get("closed_utc")
                  and s.get("outcome") in ("WIN", "LOSS")
                  and (prev_ts is None or s["closed_utc"] > prev_ts)]
        if window:
            det = ", ".join(
                f"{s['pair']} {s['direction']} {s['outcome']} "
                f"{_fmt_r(s.get('r_multiple') or 0.0)}"
                for s in sorted(window, key=lambda x: x["closed_utc"])[:8])
            more = f" (+{len(window)-8} adet daha)" if len(window) > 8 else ""
            p.append(f"Bu donemde sonuclananlar: {det}{more}.")

        # 3) Yon bilancosu + kural yorumu
        def side(direction: str):
            rows = [s for s in signals if s.get("direction") == direction
                    and s.get("outcome") in ("WIN", "LOSS")]
            r = sum(s.get("r_multiple") or 0.0 for s in rows)
            wn = sum(1 for s in rows if s["outcome"] == "WIN")
            return wn, len(rows) - wn, r

        lw, ll, lr = side("LONG")
        sw, sl, sr = side("SHORT")
        if (lw + ll) or (sw + sl):
            bias_tr = {"bull": "boga", "bear": "ayi",
                       "neutral": "notr"}.get(self.market_bias, "notr")
            p.append(f"Yon bilancosu -> LONG {lw}W/{ll}L ({_fmt_r(lr)}) | "
                     f"SHORT {sw}W/{sl}L ({_fmt_r(sr)}). "
                     f"Guncel rejim: BTC {bias_tr}.")
            if self.market_bias == "bear":
                p.append("Ayi rejiminde market gate yeni LONG uretimini "
                         "blokluyor; bloklanan kararlar karsi-olgu "
                         "kohortunda ayrica izleniyor.")
            elif self.market_bias == "bull":
                p.append("Boga rejiminde market gate yeni SHORT uretimini "
                         "blokluyor; bloklanan kararlar karsi-olgu "
                         "kohortunda ayrica izleniyor.")

        # 4) Giris isabeti
        filled = sum(1 for s in signals
                     if (s.get("outcome") or s.get("status"))
                     in ("WIN", "LOSS", "AMBIGUOUS", "FILLED"))
        nf = sum(1 for s in signals if s.get("outcome") == "NOT_FILLED")
        if filled + nf:
            fr = 100 * filled / (filled + nf)
            note = (" Dusuk isabet, retest-limit girisin bilinen bedeli; "
                    "esik %40 altina kalici inerse giris varyanti "
                    "tartisilacak." if fr < 40 else "")
            p.append(f"Giris isabeti %{fr:.0f} ({filled} doldu / "
                     f"{nf} dolmadi).{note}")

        # 5) Yuksek plan-RR kaybi uyarisi (son pencerede)
        hi = [s for s in window
              if s["outcome"] == "LOSS" and (s.get("rr") or 0) >= 6]
        if hi:
            det = ", ".join(f"{s['pair']} (RR {s['rr']:.1f})" for s in hi)
            p.append(f"Uyari: asiri dar stoplu kayip(lar) - {det}. "
                     "RR tavani / minimum stop mesafesi adayligi guclendi.")

        # 6) Acik pozisyonlar
        open_rows = [s for s in signals
                     if (s.get("outcome") or s.get("status"))
                     in ("PENDING", "FILLED")]
        if open_rows:
            oldest = min(open_rows, key=lambda s: s.get("created_utc") or "")
            p.append(f"Izlemede {len(open_rows)} acik sinyal; en eskisi "
                     f"{oldest['pair']} ({oldest.get('created_utc', '')[:16]}"
                     " UTC).")

        # 7) Kapanis uyarilari
        if decided and decided < 30:
            p.append(f"Orneklem hala kucuk (n={decided}); 30-50 sonuclanmis "
                     "sinyalden once parametre karari verilmeyecek.")
        p.append(_DISCLAIMER)
        return "\n".join(p)

    # --------------------------------------------------------------- query
    def _latest(self) -> dict | None:
        rows = self._db.query(
            "SELECT ts_utc, text, stats_json FROM commentary "
            "ORDER BY id DESC LIMIT 1")
        return dict(rows[0]) if rows else None

    def recent(self, limit: int = 5) -> list[dict]:
        rows = self._db.query(
            "SELECT ts_utc, text FROM commentary ORDER BY id DESC LIMIT ?",
            (limit,))
        return [dict(r) for r in rows]
