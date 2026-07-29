"""
SignalTracker - golge donemi takip motoru. SESSIZ calisir (Telegram'a yazmaz).

Sorumluluklar:
1. Her karari (SIGNAL/NO_TRADE/DATA_MISSING) decisions tablosuna kaydet
   -> backtest'te "hangi kosulda ne karar verildi" etiketi.
2. Her taramada kapanmis mumlari candles tablosuna biriktir (INSERT OR IGNORE)
   -> backtest icin ham OHLCV arsivi.
3. Her SIGNAL'i signals tablosunda izle ve sonraki mumlarla sonuclandir:
     PENDING -> fiyat entry bolgesine girerse FILLED, girmezse NOT_FILLED
     FILLED  -> stop'a deger LOSS (-1R), TP1'e deger WIN (+reward/risk R),
                ayni mumda ikisi de degerse AMBIGUOUS (0R, sayilmaz),
                sure asarsa EXPIRED (kapanisa gore R)
4. stats() ile basari orani / toplam R hesabi.

Varsayimlar (golge muhasebesi - dokumante edilmis, muhafazakar):
- Fill fiyati: LONG'da entry_max, SHORT'ta entry_min (bolgenin ilk degen kenari).
- Ayni mumda hem stop hem TP kesilirse sira bilinemez -> AMBIGUOUS, orana dahil edilmez.
- Bu tahmini bir olcumdur; gercek emir doldurma/slippage icermez.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.logging_setup import kv
from app.models.candle import KlineSeries
from app.models.decision import Decision, DecisionType, Direction
from app.services.database import Database

log = logging.getLogger("tracker")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SignalTracker:
    def __init__(self, db: Database, ltf_interval: str,
                 fill_window_bars: int = 24, max_track_bars: int = 192) -> None:
        self._db = db
        self._ltf = ltf_interval
        self._fill_window = fill_window_bars
        self._max_track = max_track_bars

    # ------------------------------------------------------ veri birikimi
    def _migrate(self) -> None:
        """v3.3: eski DB'lere confidence/setup_type kolonlarini ekle."""
        for ddl in ("confidence TEXT", "setup_type TEXT",
                    "blocked INTEGER NOT NULL DEFAULT 0"):
            try:
                self._db.execute(f"ALTER TABLE signals ADD COLUMN {ddl}")
            except Exception:
                pass  # kolon zaten var
        self._migrate()

    def record_candles(self, series: KlineSeries) -> None:
        """Kapanmis mumlari arsivle. Son bar henuz olusuyor -> atlanir."""
        closed = series.candles[:-1]
        rows = [(series.symbol, series.interval, c.ts, c.open, c.high,
                 c.low, c.close, c.volume) for c in closed]
        self._db.executemany(
            "INSERT OR IGNORE INTO candles(symbol,interval,ts,open,high,low,close,volume) "
            "VALUES(?,?,?,?,?,?,?,?)", rows)

    def record_decision(self, d: Decision) -> None:
        self._db.execute(
            "INSERT INTO decisions(ts_utc,pair,decision,direction,regime,htf_bias,"
            "setup_type,reject_reason,contract_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (d.timestamp_utc, d.pair, d.decision.value, d.direction.value,
             d.regime.value, d.htf_bias.value, d.setup_type.value,
             d.reject_reason, json.dumps(d.contract_dict())))

    # ------------------------------------------------------ sinyal takibi
    def maybe_track(self, d: Decision, ltf: KlineSeries) -> bool:
        """SIGNAL'i izlemeye al. Ayni pair+direction icin acik kayit varsa alma."""
        if d.decision is not DecisionType.SIGNAL:
            return False
        existing = self._db.query_one(
            "SELECT id FROM signals WHERE pair=? AND direction=? "
            "AND status!='CLOSED' AND blocked=0",
            (d.pair, d.direction.value))
        if existing:
            return False
        self._db.execute(
            "INSERT INTO signals(pair,direction,created_utc,entry_candle_ts,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,contract_json,"
            "confidence,setup_type) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d.pair, d.direction.value, d.timestamp_utc, ltf.candles[-1].ts,
             d.entry_zone.min, d.entry_zone.max, d.stop_loss,
             d.targets.tp1, d.targets.tp2, d.rr, json.dumps(d.contract_dict()),
             d.confidence.value, d.setup_type.value))
        log.info(kv(event="shadow_track", pair=d.pair, direction=d.direction.value))
        return True

    def track_blocked(self, d: Decision, ltf: KlineSeries) -> bool:
        """v3.4 karsi-olgu: market gate'in blokladigi karari blocked=1 ile izle.

        Skor tablosuna ASLA karismaz (stats/recent_signals blocked=0 filtreler);
        ayni degerlendirme dongusunden gecer -> kapinin gercek etkisi olculur.
        """
        if not d.rr or d.entry_zone.min is None:
            return False
        existing = self._db.query_one(
            "SELECT id FROM signals WHERE pair=? AND direction=? "
            "AND status!='CLOSED' AND blocked=1",
            (d.pair, d.direction.value))
        if existing:
            return False
        self._db.execute(
            "INSERT INTO signals(pair,direction,created_utc,entry_candle_ts,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,contract_json,"
            "confidence,setup_type,blocked) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
            (d.pair, d.direction.value, d.timestamp_utc, ltf.candles[-1].ts,
             d.entry_zone.min, d.entry_zone.max, d.stop_loss,
             d.targets.tp1, d.targets.tp2, d.rr, json.dumps(d.contract_dict()),
             d.confidence.value, d.setup_type.value))
        log.info(kv(event="shadow_track_blocked", pair=d.pair,
                    direction=d.direction.value))
        return True

    def evaluate_open(self, pair: str) -> None:
        """Acik sinyalleri arsivlenen mumlarla degerlendir."""
        open_signals = self._db.query(
            "SELECT * FROM signals WHERE pair=? AND status!='CLOSED'", (pair,))
        for sig in open_signals:
            candles = self._db.query(
                "SELECT * FROM candles WHERE symbol=? AND interval=? AND ts>=? "
                "ORDER BY ts ASC", (pair, self._ltf, sig["entry_candle_ts"]))
            if candles:
                self._evaluate_signal(sig, candles)

    def _evaluate_signal(self, sig: dict, candles: list[dict]) -> None:
        is_long = sig["direction"] == Direction.LONG.value
        fill_price = sig["fill_price"]
        filled_at_idx: int | None = None

        for i, c in enumerate(candles):
            # --- 1) fill kontrolu ---
            if fill_price is None:
                touched = (c["low"] <= sig["entry_max"] if is_long
                           else c["high"] >= sig["entry_min"])
                if touched:
                    fill_price = sig["entry_max"] if is_long else sig["entry_min"]
                    filled_at_idx = i
                    self._db.execute(
                        "UPDATE signals SET status='FILLED', fill_price=? WHERE id=?",
                        (fill_price, sig["id"]))
                elif i + 1 >= self._fill_window:
                    self._close(sig["id"], "NOT_FILLED", None, 0.0)
                    return
                continue

            # --- 2) sonuc kontrolu ---
            risk = (fill_price - sig["stop_loss"]) if is_long else (sig["stop_loss"] - fill_price)
            if risk <= 0:
                self._close(sig["id"], "AMBIGUOUS", fill_price, 0.0)
                return
            hit_stop = (c["low"] <= sig["stop_loss"] if is_long
                        else c["high"] >= sig["stop_loss"])
            hit_tp = (c["high"] >= sig["tp1"] if is_long
                      else c["low"] <= sig["tp1"])
            if hit_stop and hit_tp:
                self._close(sig["id"], "AMBIGUOUS", fill_price, 0.0)
                return
            if hit_stop:
                self._close(sig["id"], "LOSS", sig["stop_loss"], -1.0)
                return
            if hit_tp:
                reward = (sig["tp1"] - fill_price) if is_long else (fill_price - sig["tp1"])
                self._close(sig["id"], "WIN", sig["tp1"], round(reward / risk, 2))
                return
            bars_held = i - (filled_at_idx if filled_at_idx is not None else 0)
            if bars_held >= self._max_track:
                pnl = (c["close"] - fill_price) if is_long else (fill_price - c["close"])
                self._close(sig["id"], "EXPIRED", c["close"], round(pnl / risk, 2))
                return

    def _close(self, signal_id: int, outcome: str,
               exit_price: float | None, r_multiple: float) -> None:
        self._db.execute(
            "UPDATE signals SET status='CLOSED', outcome=?, exit_price=?, "
            "r_multiple=?, closed_utc=? WHERE id=?",
            (outcome, exit_price, r_multiple, _now_iso(), signal_id))
        log.info(kv(event="shadow_close", signal_id=signal_id,
                    outcome=outcome, r=r_multiple))

    # ------------------------------------------------------- istatistik
    def stats(self) -> dict:
        by_outcome = {r["outcome"]: {"count": r["n"], "sum_r": r["sum_r"] or 0.0}
                      for r in self._db.query(
                          "SELECT outcome, COUNT(*) n, SUM(r_multiple) sum_r "
                          "FROM signals WHERE status='CLOSED' AND blocked=0 GROUP BY outcome")}
        wins = by_outcome.get("WIN", {}).get("count", 0)
        losses = by_outcome.get("LOSS", {}).get("count", 0)
        decided = wins + losses
        total_r = round(sum(v["sum_r"] for v in by_outcome.values()), 2)
        open_row = self._db.query_one(
            "SELECT COUNT(*) n FROM signals WHERE status!='CLOSED' AND blocked=0")
        per_pair = self._db.query(
            "SELECT pair, outcome, COUNT(*) n, ROUND(SUM(r_multiple),2) sum_r "
            "FROM signals WHERE status='CLOSED' AND blocked=0 "
            "GROUP BY pair, outcome ORDER BY pair")
        counts = self._db.query_one(
            "SELECT (SELECT COUNT(*) FROM decisions) d, (SELECT COUNT(*) FROM candles) c")
        return {
            "note": "Shadow accounting: estimated fills, no slippage. Not real trading results.",
            "open_signals": open_row["n"] if open_row else 0,
            "closed_by_outcome": by_outcome,
            "win_rate": round(wins / decided, 3) if decided else None,
            "decided_trades": decided,
            "total_r_multiple": total_r,
            "per_pair": per_pair,
            "dataset": {"decisions_recorded": counts["d"], "candles_archived": counts["c"]},
        }

    def recent_signals(self, limit: int = 50) -> list[dict]:
        return self._db.query(
            "SELECT id,pair,direction,created_utc,entry_candle_ts,status,outcome,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,fill_price,exit_price,"
            "r_multiple,closed_utc,confidence,setup_type "
            "FROM signals WHERE blocked=0 ORDER BY id DESC LIMIT ?", (limit,))

    def blocked_signals(self, limit: int = 300) -> list[dict]:
        """Karsi-olgu kohortu: kapinin blokladigi, golgede izlenen kararlar."""
        return self._db.query(
            "SELECT id,pair,direction,created_utc,entry_candle_ts,status,outcome,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,fill_price,exit_price,"
            "r_multiple,closed_utc,confidence,setup_type,blocked "
            "FROM signals WHERE blocked=1 ORDER BY id DESC LIMIT ?", (limit,))

    def recent_decisions(self, limit: int = 2000) -> list[dict]:
        return self._db.query(
            "SELECT ts_utc,pair,decision,direction,regime,htf_bias,setup_type,"
            "reject_reason FROM decisions ORDER BY id DESC LIMIT ?", (limit,))

    def export_candles(self, symbol: str, interval: str) -> list[dict]:
        return self._db.query(
            "SELECT ts,open,high,low,close,volume FROM candles "
            "WHERE symbol=? AND interval=? ORDER BY ts ASC", (symbol, interval))

    def open_pairs(self) -> list[str]:
        """Acik (PENDING/FILLED) sinyali olan pariteler - orphan eval icin."""
        rows = self._db.query(
            "SELECT DISTINCT pair FROM signals WHERE status!='CLOSED'")
        return [r["pair"] for r in rows]

    def signal_pairs(self) -> list[str]:
        """Sinyal kaydi olan pariteler (gist candle_mode=signals icin)."""
        return [r["pair"] for r in
                self._db.query("SELECT DISTINCT pair FROM signals ORDER BY pair")]

    # ------------------------------------------- gist restore destegi
    def candles_count(self) -> int:
        row = self._db.query_one("SELECT COUNT(*) n FROM candles")
        return row["n"] if row else 0

    def import_candles(self, symbol: str, interval: str,
                       rows: list[tuple]) -> int:
        """rows: [(ts,open,high,low,close,volume), ...] - tekrarsiz eklenir."""
        self._db.executemany(
            "INSERT OR IGNORE INTO candles(symbol,interval,ts,open,high,low,close,volume) "
            "VALUES(?,?,?,?,?,?,?,?)",
            [(symbol, interval, *r) for r in rows])
        return len(rows)

    def import_signals(self, rows: list[dict]) -> int:
        """Gist yedekten sinyal kayitlarini geri yukler (created_utc ile tekrarsiz)."""
        imported = 0
        for r in rows:
            exists = self._db.query_one(
                "SELECT id FROM signals WHERE pair=? AND direction=? AND created_utc=?",
                (r.get("pair"), r.get("direction"), r.get("created_utc")))
            if exists:
                continue
            self._db.execute(
                "INSERT INTO signals(pair,direction,created_utc,entry_candle_ts,"
                "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,outcome,"
                "fill_price,exit_price,r_multiple,closed_utc,confidence,"
                "setup_type,blocked) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r.get("pair"), r.get("direction"), r.get("created_utc"),
                 r.get("entry_candle_ts"), r.get("entry_min"), r.get("entry_max"),
                 r.get("stop_loss"), r.get("tp1"), r.get("tp2"), r.get("rr"),
                 r.get("status", "PENDING"), r.get("outcome"),
                 r.get("fill_price"), r.get("exit_price"),
                 r.get("r_multiple"), r.get("closed_utc"),
                 r.get("confidence"), r.get("setup_type"),
                 r.get("blocked", 0)))
            imported += 1
        return imported
