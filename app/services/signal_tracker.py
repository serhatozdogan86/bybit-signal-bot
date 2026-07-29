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
import os
import logging
from datetime import datetime, timezone

from app.logging_setup import kv
from app.models.candle import KlineSeries
from app.models.decision import Decision, DecisionType, Direction
from app.services.database import Database

log = logging.getLogger("tracker")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_ENGINE_SHA = (os.environ.get("RENDER_GIT_COMMIT") or "dev")[:7]


def _cluster_id(d, ltf) -> str:
    """Ayni yon + ayni 4H penceresi = tek 'fikir' (konsey P0-4).

    Kume istatistigi icin gozlem birimi; n_eff tartismasinin altyapisi.
    """
    bucket = int(ltf.candles[-1].ts // 14_400_000)   # 4H ms penceresi
    return f"{d.direction.value[0]}{bucket}"


# ---------------- v3.5 maliyet motoru v0 (konsey P0-1) ----------------
# Varsayimlar (proxy; tick-level degil):
#   fee: 2 x taker %0.055 (limit varsayimi kanitlanana kadar taker)
#   kayma: yalniz stop cikisinda 5 bps (hizli piyasa cezasi)
#   funding: |0.01%| / 8s, tutus suresince; isaret: LONG oder, SHORT alir
#            (Bybit uzun donem ortalama pozitif funding varsayimi; tarihsel
#             oranlarla degistirilebilir - bilincli v0 yaklasikligi)
TAKER_FEE = 0.00055
STOP_SLIP = 0.0005
FUNDING_8H = 0.0001


def cost_r(row: dict) -> float | None:
    """Kapanmis bir sinyalin toplam maliyetini R cinsinden dondurur.

    R birimi = stop mesafesi (notional orani); maliyet orani / stop orani
    dogrudan R'ye cevrilir. Veri eksikse None.
    """
    try:
        if row.get("outcome") not in ("WIN", "LOSS"):
            return None
        entry = row.get("fill_price") or (
            row["entry_max"] if row["direction"] == "LONG" else row["entry_min"])
        stop_frac = abs(entry - row["stop_loss"]) / entry
        if stop_frac <= 0:
            return None
        fee = 2 * TAKER_FEE
        slip = STOP_SLIP if row["outcome"] == "LOSS" else 0.0
        hours = 0.0
        if row.get("created_utc") and row.get("closed_utc"):
            from datetime import datetime
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            t0 = datetime.strptime(row["created_utc"], fmt)
            t1 = datetime.strptime(row["closed_utc"], fmt)
            hours = max(0.0, min(48.0, (t1 - t0).total_seconds() / 3600))
        funding = FUNDING_8H * (hours / 8.0)
        signed_funding = funding if row["direction"] == "LONG" else -funding
        return round((fee + slip + signed_funding) / stop_frac, 4)
    except Exception:
        return None


class SignalTracker:
    def __init__(self, db: Database, ltf_interval: str,
                 fill_window_bars: int = 24, max_track_bars: int = 192) -> None:
        self._db = db
        self._ltf = ltf_interval
        self._fill_window = fill_window_bars
        self._max_track = max_track_bars
        self._migrate()

    # ------------------------------------------------------ veri birikimi
    def _migrate(self) -> None:
        """v3.3: eski DB'lere confidence/setup_type kolonlarini ekle."""
        for ddl in ("confidence TEXT", "setup_type TEXT",
                    "blocked INTEGER NOT NULL DEFAULT 0",
                    "cluster_id TEXT", "engine_sha TEXT",
                    "block_reason TEXT", "ambiguous INTEGER DEFAULT 0",
                    "hypo_r REAL", "hypo_done INTEGER DEFAULT 0"):
            try:
                self._db.execute(f"ALTER TABLE signals ADD COLUMN {ddl}")
            except Exception:
                pass  # kolon zaten var

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
            "confidence,setup_type,cluster_id,engine_sha) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d.pair, d.direction.value, d.timestamp_utc, ltf.candles[-1].ts,
             d.entry_zone.min, d.entry_zone.max, d.stop_loss,
             d.targets.tp1, d.targets.tp2, d.rr, json.dumps(d.contract_dict()),
             d.confidence.value, d.setup_type.value,
             _cluster_id(d, ltf), _ENGINE_SHA))
        log.info(kv(event="shadow_track", pair=d.pair, direction=d.direction.value))
        return True

    # -------- v3.5-P1: portfoy isi motoru (konsey 4/4 "en acil") --------
    HEAT_SAME_DIR = 4     # ayni yonde en fazla 4 acik gercek sinyal (4R)
    HEAT_CLUSTER = 2      # ayni kume (yon+4H penceresi) en fazla 2
    HEAT_TOTAL = 8        # eszamanli acik gercek sinyal tavani

    def heat_check(self, direction: str, cluster_id: str) -> str | None:
        """Yeni sinyal kabul edilirse isi limitleri asilir mi? Asilirsa neden."""
        q = lambda sql, p=(): self._db.query_one(sql, p)["n"]
        if q("SELECT COUNT(*) n FROM signals WHERE status!='CLOSED' "
             "AND blocked=0 AND direction=?", (direction,)) >= self.HEAT_SAME_DIR:
            return f"direction heat: >={self.HEAT_SAME_DIR} open {direction}"
        if q("SELECT COUNT(*) n FROM signals WHERE status!='CLOSED' "
             "AND blocked=0 AND cluster_id=?", (cluster_id,)) >= self.HEAT_CLUSTER:
            return f"cluster cap: >={self.HEAT_CLUSTER} open in {cluster_id}"
        if q("SELECT COUNT(*) n FROM signals WHERE status!='CLOSED' "
             "AND blocked=0") >= self.HEAT_TOTAL:
            return f"concurrent cap: >={self.HEAT_TOTAL} open total"
        return None

    def track_portfolio_blocked(self, d: Decision, ltf: KlineSeries,
                                reason: str) -> bool:
        """Isi limitine takilan SIGNAL -> blocked=2 kohortu (skora karismaz)."""
        existing = self._db.query_one(
            "SELECT id FROM signals WHERE pair=? AND direction=? "
            "AND status!='CLOSED' AND blocked=2", (d.pair, d.direction.value))
        if existing:
            return False
        self._db.execute(
            "INSERT INTO signals(pair,direction,created_utc,entry_candle_ts,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,contract_json,"
            "confidence,setup_type,blocked,cluster_id,engine_sha,block_reason) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,2,?,?,?)",
            (d.pair, d.direction.value, d.timestamp_utc, ltf.candles[-1].ts,
             d.entry_zone.min, d.entry_zone.max, d.stop_loss,
             d.targets.tp1, d.targets.tp2, d.rr, json.dumps(d.contract_dict()),
             d.confidence.value, d.setup_type.value,
             _cluster_id(d, ltf), _ENGINE_SHA, reason))
        log.info(kv(event="portfolio_heat_block", pair=d.pair, reason=reason))
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
            "confidence,setup_type,blocked,cluster_id,engine_sha,block_reason) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,'counter-regime')",
            (d.pair, d.direction.value, d.timestamp_utc, ltf.candles[-1].ts,
             d.entry_zone.min, d.entry_zone.max, d.stop_loss,
             d.targets.tp1, d.targets.tp2, d.rr, json.dumps(d.contract_dict()),
             d.confidence.value, d.setup_type.value,
             _cluster_id(d, ltf), _ENGINE_SHA))
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
        # v3.5-P1: NOT_FILLED hayalet degerlendirme (teshis verisi;
        # "dolmayanlar en iyi islemler miydi?" sorusuna sayisal cevap)
        ghosts = self._db.query(
            "SELECT * FROM signals WHERE pair=? AND outcome='NOT_FILLED' "
            "AND hypo_done=0", (pair,))
        for sig in ghosts:
            candles = self._db.query(
                "SELECT * FROM candles WHERE symbol=? AND interval=? AND ts>=? "
                "ORDER BY ts ASC", (pair, self._ltf, sig["entry_candle_ts"]))
            if candles:
                self._evaluate_hypo(sig, candles)

    def _evaluate_hypo(self, sig: dict, candles: list[dict]) -> None:
        """NOT_FILLED sinyali 'kenardan dolmus' varsayip hayalet R hesaplar.

        Fill penceresi bitiminden itibaren ayni kurallar: once stop -> -1,
        once TP -> +R, ayni mum -> -1 (muhafazakar), 48s -> son kapanisla.
        Sonuc hypo_r kolonuna yazilir; skora ASLA karismaz.
        """
        is_long = sig["direction"] == Direction.LONG.value
        entry = sig["entry_max"] if is_long else sig["entry_min"]
        risk = (entry - sig["stop_loss"]) if is_long else (sig["stop_loss"] - entry)
        if risk <= 0:
            self._db.execute("UPDATE signals SET hypo_done=1 WHERE id=?",
                             (sig["id"],))
            return
        window = candles[self._fill_window:]
        for i, c in enumerate(window):
            hit_stop = (c["low"] <= sig["stop_loss"] if is_long
                        else c["high"] >= sig["stop_loss"])
            hit_tp = (c["high"] >= sig["tp1"] if is_long
                      else c["low"] <= sig["tp1"])
            if hit_stop:
                r = -1.0
            elif hit_tp:
                reward = (sig["tp1"] - entry) if is_long else (entry - sig["tp1"])
                r = round(reward / risk, 2)
            elif i >= self._max_track:
                pnl = (c["close"] - entry) if is_long else (entry - c["close"])
                r = round(pnl / risk, 2)
            else:
                continue
            self._db.execute(
                "UPDATE signals SET hypo_r=?, hypo_done=1 WHERE id=?",
                (r, sig["id"]))
            log.info(kv(event="hypo_eval", pair=sig["pair"], hypo_r=r))
            return

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
                # v3.5-P1 (konsey): ayni mumda yol bilinemez -> muhafazakar
                # kural LOSS sayar; ambiguous=1 ile ayrica raporlanabilir.
                self._db.execute(
                    "UPDATE signals SET ambiguous=1 WHERE id=?", (sig["id"],))
                self._close(sig["id"], "LOSS", sig["stop_loss"], -1.0)
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
        # v3.5: maliyet-sonrasi net metrikler + kume sayisi (n_eff altyapisi)
        closed_rows = self._db.query(
            "SELECT direction,outcome,entry_min,entry_max,stop_loss,"
            "fill_price,r_multiple,created_utc,closed_utc,cluster_id "
            "FROM signals WHERE status='CLOSED' AND blocked=0 "
            "AND outcome IN ('WIN','LOSS')")
        net_vals = []
        for r in closed_rows:
            cst = cost_r(r)
            if cst is not None and r.get("r_multiple") is not None:
                net_vals.append(r["r_multiple"] - cst)
        total_r_net = round(sum(net_vals), 2) if net_vals else None
        clusters = len({r["cluster_id"] for r in closed_rows
                        if r.get("cluster_id")}) or None
        heat = self._db.query_one(
            "SELECT SUM(CASE WHEN blocked=1 THEN 1 ELSE 0 END) g,"
            "SUM(CASE WHEN blocked=2 THEN 1 ELSE 0 END) h,"
            "SUM(CASE WHEN outcome='NOT_FILLED' AND hypo_r IS NOT NULL "
            "THEN hypo_r ELSE 0 END) hr,"
            "SUM(CASE WHEN outcome='NOT_FILLED' AND hypo_r IS NOT NULL "
            "THEN 1 ELSE 0 END) hn FROM signals")
        return {
            "note": "Shadow accounting: estimated fills, no slippage. Not real trading results.",
            "open_signals": open_row["n"] if open_row else 0,
            "closed_by_outcome": by_outcome,
            "win_rate": round(wins / decided, 3) if decided else None,
            "decided_trades": decided,
            "total_r_multiple": total_r,
            "total_r_net": total_r_net,
            "expectancy_net": (round(total_r_net / len(net_vals), 3)
                               if net_vals else None),
            "cost_model": "v0: 2x taker 0.055% + stop slip 5bps + funding 0.01%/8h signed",
            "clusters_closed": clusters,
            "cohorts": {"gate_blocked": (heat["g"] or 0),
                        "heat_blocked": (heat["h"] or 0)},
            "not_filled_hypo": {"n": (heat["hn"] or 0),
                                "sum_r": round(heat["hr"] or 0, 2),
                                "note": "teshis verisi; pismanlik sayaci degil"},
            "per_pair": per_pair,
            "dataset": {"decisions_recorded": counts["d"], "candles_archived": counts["c"]},
        }

    def recent_signals(self, limit: int = 50) -> list[dict]:
        return self._db.query(
            "SELECT id,pair,direction,created_utc,entry_candle_ts,status,outcome,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,fill_price,exit_price,"
            "r_multiple,closed_utc,confidence,setup_type,cluster_id,engine_sha "
            "FROM signals WHERE blocked=0 ORDER BY id DESC LIMIT ?", (limit,))
        for r in rows:
            c = cost_r(r)
            r["r_net"] = (round(r["r_multiple"] - c, 2)
                          if c is not None and r.get("r_multiple") is not None
                          else None)
        return rows

    def blocked_signals(self, limit: int = 300) -> list[dict]:
        """Karsi-olgu kohortu: kapinin blokladigi, golgede izlenen kararlar."""
        return self._db.query(
            "SELECT id,pair,direction,created_utc,entry_candle_ts,status,outcome,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,fill_price,exit_price,"
            "r_multiple,closed_utc,confidence,setup_type,blocked,"
            "cluster_id,engine_sha,block_reason "
            "FROM signals WHERE blocked>=1 ORDER BY id DESC LIMIT ?", (limit,))

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
                "setup_type,blocked,cluster_id,engine_sha,block_reason,"
                "hypo_r,hypo_done) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r.get("pair"), r.get("direction"), r.get("created_utc"),
                 r.get("entry_candle_ts"), r.get("entry_min"), r.get("entry_max"),
                 r.get("stop_loss"), r.get("tp1"), r.get("tp2"), r.get("rr"),
                 r.get("status", "PENDING"), r.get("outcome"),
                 r.get("fill_price"), r.get("exit_price"),
                 r.get("r_multiple"), r.get("closed_utc"),
                 r.get("confidence"), r.get("setup_type"),
                 r.get("blocked", 0), r.get("cluster_id"),
                 r.get("engine_sha"), r.get("block_reason"),
                 r.get("hypo_r"), r.get("hypo_done", 0)))
            imported += 1
        return imported
