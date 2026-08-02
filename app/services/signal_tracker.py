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
from app.services import measurement
from app.services.database import Database

log = logging.getLogger("tracker")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_ENGINE_SHA = (os.environ.get("RENDER_GIT_COMMIT")
               or os.environ.get("ENGINE_SHA") or "dev")[:7]


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
                    "fill_ts INTEGER",
                    "hypo_r REAL", "hypo_done INTEGER DEFAULT 0",
                    # v3.6 olcum paketi (yalniz olcum; davranis degismez)
                    "mfe_r REAL", "mae_r REAL",
                    "nf_gap_r REAL", "nf_touch_bars INTEGER",
                    "nf_crossed INTEGER", "nf_done INTEGER DEFAULT 0",
                    "funding_r_real REAL", "funding_done INTEGER DEFAULT 0"):
            try:
                self._db.execute(f"ALTER TABLE signals ADD COLUMN {ddl}")
            except Exception:
                pass  # kolon zaten var
        # v3.6: kapi gecis/TTL olay gunlugu (histerezis gecikmesi olcumu)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS gate_log("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "ts_utc TEXT, kind TEXT, detail TEXT)")

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
        # v3.6-P0: NOT_FILLED anatomisi (bosluk, temas, sonradan gecis)
        pending_nf = self._db.query(
            "SELECT * FROM signals WHERE pair=? AND outcome='NOT_FILLED' "
            "AND nf_done=0", (pair,))
        for sig in pending_nf:
            candles = self._db.query(
                "SELECT ts,low,high FROM candles WHERE symbol=? AND interval=? "
                "AND ts>=? ORDER BY ts ASC",
                (pair, self._ltf, sig["entry_candle_ts"]))
            if len(candles) < self._fill_window:
                continue  # pencere tamamlanmadan anatomi cikarilamaz
            a = measurement.nf_anatomy(sig, candles, self._fill_window)
            if a is None:
                self._db.execute("UPDATE signals SET nf_done=1 WHERE id=?",
                                 (sig["id"],))
                continue
            self._db.execute(
                "UPDATE signals SET nf_gap_r=?, nf_touch_bars=?, nf_crossed=?, "
                "nf_done=1 WHERE id=?",
                (a["gap_r"], a["touch_bars"], a["crossed"], sig["id"]))
            log.info(kv(event="nf_anatomy", pair=sig["pair"],
                        gap_r=a["gap_r"], crossed=a["crossed"]))

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
        # v3.6-P0: MFE/MAE - dolus sonrasi en iyi/en kotu gezinme, R cinsinden.
        # Her degerlendirmede sifirdan yeniden hesaplanir (idempotent).
        mfe = 0.0
        mae = 0.0
        seen_fill = False

        for i, c in enumerate(candles):
            # --- 1) fill kontrolu ---
            if fill_price is None:
                touched = (c["low"] <= sig["entry_max"] if is_long
                           else c["high"] >= sig["entry_min"])
                if touched:
                    fill_price = sig["entry_max"] if is_long else sig["entry_min"]
                    filled_at_idx = i
                    self._db.execute(
                        "UPDATE signals SET status='FILLED', fill_price=?, "
                        "fill_ts=? WHERE id=?",
                        (fill_price, c["ts"], sig["id"]))
                elif i + 1 >= self._fill_window:
                    self._close(sig["id"], "NOT_FILLED", None, 0.0)
                    return
                continue

            # --- 2) sonuc kontrolu ---
            risk = (fill_price - sig["stop_loss"]) if is_long else (sig["stop_loss"] - fill_price)
            if risk <= 0:
                self._close(sig["id"], "AMBIGUOUS", fill_price, 0.0)
                return
            # v3.6: bu mumun lehte/aleyhte gezinmesi (dolus mumu dahil)
            seen_fill = True
            fav = ((c["high"] - fill_price) if is_long
                   else (fill_price - c["low"])) / risk
            adv = ((fill_price - c["low"]) if is_long
                   else (c["high"] - fill_price)) / risk
            mfe = max(mfe, fav)
            mae = max(mae, adv)
            hit_stop = (c["low"] <= sig["stop_loss"] if is_long
                        else c["high"] >= sig["stop_loss"])
            hit_tp = (c["high"] >= sig["tp1"] if is_long
                      else c["low"] <= sig["tp1"])
            if hit_stop and hit_tp:
                # v3.5-P1 (konsey): ayni mumda yol bilinemez -> muhafazakar
                # kural LOSS sayar; ambiguous=1 ile ayrica raporlanabilir.
                self._db.execute(
                    "UPDATE signals SET ambiguous=1 WHERE id=?", (sig["id"],))
                self._save_excursion(sig["id"], mfe, mae)
                self._close(sig["id"], "LOSS", sig["stop_loss"], -1.0)
                return
            if hit_stop:
                self._save_excursion(sig["id"], mfe, mae)
                self._close(sig["id"], "LOSS", sig["stop_loss"], -1.0)
                return
            if hit_tp:
                reward = (sig["tp1"] - fill_price) if is_long else (fill_price - sig["tp1"])
                self._save_excursion(sig["id"], mfe, mae)
                self._close(sig["id"], "WIN", sig["tp1"], round(reward / risk, 2))
                return
            bars_held = i - (filled_at_idx if filled_at_idx is not None else 0)
            if bars_held >= self._max_track:
                pnl = (c["close"] - fill_price) if is_long else (fill_price - c["close"])
                self._save_excursion(sig["id"], mfe, mae)
                self._close(sig["id"], "EXPIRED", c["close"], round(pnl / risk, 2))
                return
        # kapanmadan cikti: acik FILLED sinyalin guncel MFE/MAE'sini yaz
        if seen_fill:
            self._save_excursion(sig["id"], mfe, mae)

    def _save_excursion(self, signal_id: int, mfe: float, mae: float) -> None:
        self._db.execute(
            "UPDATE signals SET mfe_r=?, mae_r=? WHERE id=?",
            (round(mfe, 3), round(mae, 3), signal_id))

    def _close(self, signal_id: int, outcome: str,
               exit_price: float | None, r_multiple: float) -> None:
        self._db.execute(
            "UPDATE signals SET status='CLOSED', outcome=?, exit_price=?, "
            "r_multiple=?, closed_utc=? WHERE id=?",
            (outcome, exit_price, r_multiple, _now_iso(), signal_id))
        log.info(kv(event="shadow_close", signal_id=signal_id,
                    outcome=outcome, r=r_multiple))

    # ----------------------- v3.6-P1: kapi olay gunlugu (histerezis/TTL)
    def log_gate_event(self, kind: str, detail: str) -> None:
        """Market gate gecis/bekleme/TTL olaylarini kalici gunlukle.

        Amac olcum: histerezis kac saat gecikme uretiyor, TTL gercekte
        kac kez tetikleniyor? (Konsey: '2x4H fazla yavas olabilir; olc
        ama simdi degistirme', 'TTL 2 saat keyfi; kesinti loglariyla
        gerekcelendir'.)
        """
        try:
            self._db.execute(
                "INSERT INTO gate_log(ts_utc,kind,detail) VALUES(?,?,?)",
                (_now_iso(), kind, detail))
        except Exception:
            log.exception(kv(event="gate_log_error", kind=kind))

    # ------------------- v3.6-P1: gercek funding yakalama (maliyet v1 verisi)
    def backfill_funding(self, md, budget: int = 2) -> int:
        """Kapanan WIN/LOSS sinyalleri icin GERCEK funding maliyetini cek.

        v0 maliyet modeli sabit %0.01/8s varsayar (kilitli; degismez).
        Burada Bybit funding gecmisinden tutus suresindeki gercek oranlar
        toplanir ve funding_r_real'e yazilir -> v1 maliyet modeli kilit-v2
        penceresinde bu veriyle kurulur. Tarama basina en fazla `budget`
        API cagrisi; hata bir sonraki tura birakilir (fail-soft).
        Isaret kurali cost_r ile ayni: pozitif = maliyet (LONG pozitif
        funding oder, SHORT alir).
        """
        # fill_ts'i olmayan eski kayitlar olculemez -> tek seferde isaretle
        self._db.execute(
            "UPDATE signals SET funding_done=1 WHERE status='CLOSED' "
            "AND funding_done=0 AND (fill_ts IS NULL "
            "OR outcome NOT IN ('WIN','LOSS'))")
        rows = self._db.query(
            "SELECT id,pair,direction,fill_ts,closed_utc,fill_price,"
            "entry_min,entry_max,stop_loss FROM signals "
            "WHERE status='CLOSED' AND blocked=0 AND funding_done=0 "
            "AND outcome IN ('WIN','LOSS') ORDER BY id DESC LIMIT ?",
            (budget,))
        done = 0
        for r in rows:
            try:
                end_ms = int(datetime.strptime(
                    r["closed_utc"], "%Y-%m-%dT%H:%M:%SZ")
                    .replace(tzinfo=timezone.utc).timestamp() * 1000)
                hist = md.get_funding_history(r["pair"], r["fill_ts"], end_ms)
                if hist is None:
                    continue  # API hatasi: sonraki turda tekrar dene
                rate_sum = 0.0
                for h in hist:
                    ts = int(h.get("fundingRateTimestamp", 0))
                    if r["fill_ts"] <= ts <= end_ms:
                        rate_sum += float(h.get("fundingRate", 0.0))
                signed = rate_sum if r["direction"] == "LONG" else -rate_sum
                entry = r["fill_price"] or (
                    r["entry_max"] if r["direction"] == "LONG"
                    else r["entry_min"])
                stop_frac = (abs(entry - r["stop_loss"]) / entry
                             if entry else 0.0)
                funding_r = (round(signed / stop_frac, 4)
                             if stop_frac > 0 else None)
                self._db.execute(
                    "UPDATE signals SET funding_r_real=?, funding_done=1 "
                    "WHERE id=?", (funding_r, r["id"]))
                done += 1
                log.info(kv(event="funding_real", pair=r["pair"],
                            funding_r=funding_r))
            except Exception:
                log.exception(kv(event="funding_backfill_error",
                                 pair=r.get("pair")))
        return done

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
            "SELECT id,direction,outcome,entry_min,entry_max,stop_loss,"
            "fill_price,r_multiple,created_utc,closed_utc,cluster_id "
            "FROM signals WHERE status='CLOSED' AND blocked=0 "
            "AND outcome IN ('WIN','LOSS')")
        net_vals = []
        cluster_map_all: dict[str, list[float]] = {}
        cluster_map_lock: dict[str, list[float]] = {}
        for r in closed_rows:
            cst = cost_r(r)
            if cst is not None and r.get("r_multiple") is not None:
                net = r["r_multiple"] - cst
                net_vals.append(net)
                cid = r.get("cluster_id") or f"solo{r['id']}"
                cluster_map_all.setdefault(cid, []).append(net)
                if (r.get("created_utc") or "") >= measurement.LOCK_UTC:
                    cluster_map_lock.setdefault(cid, []).append(net)
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
        # ---- v3.6 olcum blogu: RESMI CI = kume-blok bootstrap ----
        boot_all = measurement.cluster_bootstrap(cluster_map_all)
        boot_lock = measurement.cluster_bootstrap(cluster_map_lock)
        lock_clusters = len(cluster_map_lock)
        ci_low_lock = (boot_lock or {}).get("ci_low")
        ci_ok = ci_low_lock is not None and ci_low_lock > 0
        ghost_rows = self._db.query(
            "SELECT direction,entry_min,entry_max,stop_loss,hypo_r "
            "FROM signals WHERE outcome='NOT_FILLED' AND hypo_r IS NOT NULL")
        meas = {
            "note": ("Resmi CI kume-blok bootstrap'tir; islem-duzeyi CI "
                     "otokorelasyon nedeniyle raporlarda KULLANILMAZ "
                     "(konsey 2. tur, 5/5)."),
            "bootstrap_all": boot_all,
            "bootstrap_since_lock": boot_lock,
            "faz1": {
                "rule": (">=50 bagimsiz kapanmis kume VE kume-CI alt "
                         "siniri > 0 (sikilastirma: 2026-08-02)"),
                "target_clusters": measurement.FAZ1_TARGET_CLUSTERS,
                "clusters_since_lock": lock_clusters,
                "ci_low_since_lock": ci_low_lock,
                "ci_ok": ci_ok,
                "gate_met": (lock_clusters
                             >= measurement.FAZ1_TARGET_CLUSTERS) and ci_ok,
            },
            "not_filled_hypo_slip": measurement.hypo_slip_summary(ghost_rows),
        }
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
            "measurement": meas,
            "per_pair": per_pair,
            "dataset": {"decisions_recorded": counts["d"], "candles_archived": counts["c"]},
        }

    # ---------------------------------------- v3.6: teshis dagilimlari
    def diagnostics(self) -> dict:
        """Konsey P0-3 teshisleri. Yalniz OKUMA; hicbir esik degistirmez.

        Cevaplanan sorular: bir kume tum kari mi tasiyor? Isi-bloklu kohort
        hangi kumelerde yigildi? Kapi-bloklu kohort hangi rejimlerde dogdu?
        Kar tek paritede mi? WIN'ler LOSS'lardan uzun mu tutuluyor?
        Guven etiketi gercekten ayristiriyor mu? Dolmayanlar kil payi mi
        kacti? MFE/MAE ne soyluyor? Gercek funding v0 varsayimindan ne
        kadar sapiyor?
        """
        rows = self._db.query(
            "SELECT id,pair,direction,outcome,r_multiple,cluster_id,"
            "created_utc,closed_utc,fill_ts,fill_price,entry_min,entry_max,"
            "stop_loss,confidence,ambiguous,mfe_r,mae_r,funding_r_real,"
            "funding_done FROM signals WHERE status='CLOSED' AND blocked=0 "
            "AND outcome IN ('WIN','LOSS')")
        per_cluster: dict[str, dict] = {}
        by_conf: dict[str, list[float]] = {}
        hold_h = {"WIN": [], "LOSS": []}
        mfe_by = {"WIN": [], "LOSS": []}
        mae_by = {"WIN": [], "LOSS": []}
        funding_pairs = []   # (v0 varsayim, gercek) ayni sinyal icin
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        for r in rows:
            cst = cost_r(r)
            net = (r["r_multiple"] - cst
                   if cst is not None and r.get("r_multiple") is not None
                   else None)
            cid = r.get("cluster_id") or f"solo{r['id']}"
            agg = per_cluster.setdefault(cid, {"n": 0, "net_r": 0.0})
            agg["n"] += 1
            if net is not None:
                agg["net_r"] += net
                by_conf.setdefault(r.get("confidence") or "?", []).append(net)
            if r.get("fill_ts") and r.get("closed_utc"):
                try:
                    t1 = datetime.strptime(r["closed_utc"], fmt).replace(
                        tzinfo=timezone.utc)
                    hours = (t1.timestamp() - r["fill_ts"] / 1000) / 3600
                    if 0 <= hours <= 96:
                        hold_h[r["outcome"]].append(round(hours, 2))
                except ValueError:
                    pass
            if r.get("mfe_r") is not None:
                mfe_by[r["outcome"]].append(r["mfe_r"])
                mae_by[r["outcome"]].append(r["mae_r"] or 0.0)
            if r.get("funding_r_real") is not None and cst is not None:
                # v0 funding bileseni = cost - fee - slip
                fee = 2 * TAKER_FEE
                entry = r["fill_price"] or (
                    r["entry_max"] if r["direction"] == "LONG"
                    else r["entry_min"])
                sf = abs(entry - r["stop_loss"]) / entry if entry else 0
                if sf > 0:
                    slip = (STOP_SLIP if r["outcome"] == "LOSS" else 0) / sf
                    v0_f = cst - fee / sf - slip
                    funding_pairs.append((round(v0_f, 4),
                                          r["funding_r_real"]))
        cluster_list = sorted(
            ({"cluster": k, "n": v["n"], "net_r": round(v["net_r"], 2)}
             for k, v in per_cluster.items()),
            key=lambda x: x["net_r"], reverse=True)
        conc = measurement.top_share([c["net_r"] for c in cluster_list])
        # isi-bloklu kohortun kume dagilimi
        heat_dist = self._db.query(
            "SELECT COALESCE(cluster_id,'?') cluster, COUNT(*) n "
            "FROM signals WHERE blocked=2 GROUP BY cluster_id "
            "ORDER BY n DESC LIMIT 15")
        # kapi-bloklu kohortun rejim dagilimi (contract_json'dan)
        gate_regime: dict[str, int] = {}
        for g in self._db.query(
                "SELECT contract_json FROM signals WHERE blocked=1"):
            try:
                regime = (json.loads(g["contract_json"] or "{}")
                          .get("regime") or "unknown")
            except (json.JSONDecodeError, TypeError):
                regime = "unknown"
            gate_regime[regime] = gate_regime.get(regime, 0) + 1
        # parite yogunlasmasi
        pair_rows = self._db.query(
            "SELECT pair, COUNT(*) n, ROUND(SUM(r_multiple),2) gross_r "
            "FROM signals WHERE status='CLOSED' AND blocked=0 "
            "AND outcome IN ('WIN','LOSS') GROUP BY pair "
            "ORDER BY gross_r DESC")
        pair_conc = measurement.top_share(
            [p["gross_r"] or 0.0 for p in pair_rows])
        # guven etiketi permutasyonu: HIGH vs digerleri
        high = by_conf.get("HIGH", [])
        rest = [x for k, v in by_conf.items() if k != "HIGH" for x in v]
        # NOT_FILLED anatomi ozeti
        nf = self._db.query(
            "SELECT nf_gap_r, nf_touch_bars, nf_crossed FROM signals "
            "WHERE outcome='NOT_FILLED' AND nf_done=1 "
            "AND nf_gap_r IS NOT NULL")
        # kapi olay gunlugu
        gate_counts = {r["kind"]: r["n"] for r in self._db.query(
            "SELECT kind, COUNT(*) n FROM gate_log GROUP BY kind")}
        gate_recent = self._db.query(
            "SELECT ts_utc,kind,detail FROM gate_log "
            "ORDER BY id DESC LIMIT 20")
        return {
            "note": ("v3.6 teshis paketi - yalniz olcum; motor/kilit "
                     "degismez. Golge muhasebe; yatirim tavsiyesi degildir."),
            "per_cluster_pnl": {"clusters": cluster_list[:30],
                                "concentration": conc},
            "heat_blocked_cluster_dist": heat_dist,
            "gate_blocked_regime_dist": gate_regime,
            "pair_concentration": {"top": pair_rows[:10],
                                   "concentration": pair_conc},
            "holding_hours": {
                "win_median": measurement.median_or_none(hold_h["WIN"]),
                "loss_median": measurement.median_or_none(hold_h["LOSS"]),
                "win_n": len(hold_h["WIN"]), "loss_n": len(hold_h["LOSS"])},
            "mfe_mae": {
                "win_mfe_median": measurement.median_or_none(mfe_by["WIN"]),
                "win_mae_median": measurement.median_or_none(mae_by["WIN"]),
                "loss_mfe_median": measurement.median_or_none(mfe_by["LOSS"]),
                "loss_mae_median": measurement.median_or_none(mae_by["LOSS"]),
                "note": "yeni sinyallerde birikir; eski kayitlar bos olabilir"},
            "confidence_permutation": measurement.permutation_pvalue(
                high, rest),
            "nf_anatomy": {
                "n": len(nf),
                "gap_r_median": measurement.median_or_none(
                    [x["nf_gap_r"] for x in nf]),
                "touch_bars_median": measurement.median_or_none(
                    [float(x["nf_touch_bars"] or 0) for x in nf]),
                "crossed_ratio": (round(sum(x["nf_crossed"] or 0
                                            for x in nf) / len(nf), 3)
                                  if nf else None)},
            "funding_v1_preview": {
                "n": len(funding_pairs),
                "v0_assumed_sum": round(sum(a for a, _ in funding_pairs), 3),
                "real_sum": round(sum(b for _, b in funding_pairs), 3),
                "note": "maliyet modeli v1 icin veri; v0 kilitli kalir"},
            "gate_log": {"counts": gate_counts, "recent": gate_recent},
        }

    def recent_signals(self, limit: int = 50) -> list[dict]:
        """Golge takipteki son sinyaller (yeni -> eski); r_net dahil (v3.5)."""
        rows = self._db.query(
            "SELECT id,pair,direction,created_utc,entry_candle_ts,status,outcome,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,fill_price,exit_price,"
            "r_multiple,closed_utc,confidence,setup_type,cluster_id,engine_sha,"
            "fill_ts FROM signals WHERE blocked=0 ORDER BY id DESC LIMIT ?",
            (limit,))
        for r in rows:
            c = cost_r(r)
            r["r_net"] = (round(r["r_multiple"] - c, 2)
                          if c is not None and r.get("r_multiple") is not None
                          else None)
        return rows

    def signal_chart(self, sig_id: int, before: int = 48,
                     after: int = 40) -> dict | None:
        """Bir sinyalin kanit paketi: cevresindeki mumlar + plan + teyitler.

        Gorsellestirme icindir; motor kararlarina dokunmaz.
        """
        row = self._db.query_one("SELECT * FROM signals WHERE id=?", (sig_id,))
        if not row:
            return None
        sig = dict(row)
        step = 15 * 60_000                      # 15m ms
        t0 = (sig["entry_candle_ts"] or 0) - before * step
        t1 = (sig["entry_candle_ts"] or 0) + after * step
        candles = self._db.query(
            "SELECT ts,open,high,low,close,volume FROM candles "
            "WHERE symbol=? AND interval=? AND ts BETWEEN ? AND ? ORDER BY ts",
            (sig["pair"], self._ltf, t0, t1))
        contract = {}
        try:
            contract = json.loads(sig.get("contract_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            contract = {}
        ev = contract.get("evidence") or {}
        return {
            "signal": {k: sig.get(k) for k in (
                "id", "pair", "direction", "created_utc", "entry_candle_ts",
                "fill_ts",
                "entry_min", "entry_max", "stop_loss", "tp1", "tp2", "rr",
                "status", "outcome", "fill_price", "exit_price", "r_multiple",
                "closed_utc", "confidence", "setup_type")},
            "candles": [dict(c) for c in candles],
            "evidence": {
                "invalidation": contract.get("invalidation")
                or ev.get("invalidation"),
                "liquidity": contract.get("liquidity") or ev.get("liquidity"),
                "confluence": contract.get("confluence") or ev.get("confluence"),
                "regime": contract.get("regime"),
                "htf_bias": contract.get("htf_bias"),
                "notes": contract.get("notes"),
            },
        }

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
