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
from app.services import measurement, verifier
from app.services.database import Database

log = logging.getLogger("tracker")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_ENGINE_SHA = (os.environ.get("RENDER_GIT_COMMIT")
               or os.environ.get("ENGINE_SHA") or "dev")[:7]


def _cluster_key(direction: str, ts_ms: int) -> str:
    """Kume kimligi: yon harfi + 4H pencere numarasi.

    Tek dogruluk kaynagi - hem canli kayitta hem geriye donuk doldurmada
    AYNI fonksiyon kullanilir ki iki yol asla ayrisamasin.
    """
    return f"{direction[0]}{int(ts_ms // 14_400_000)}"


def _cluster_id(d, ltf) -> str:
    """Ayni yon + ayni 4H penceresi = tek 'fikir' (konsey P0-4).

    Kume istatistigi icin gozlem birimi; n_eff tartismasinin altyapisi.
    """
    return _cluster_key(d.direction.value, ltf.candles[-1].ts)


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
                    "funding_r_real REAL", "funding_done INTEGER DEFAULT 0",
                    "prefill_repaired INTEGER DEFAULT 0"):
            try:
                self._db.execute(f"ALTER TABLE signals ADD COLUMN {ddl}")
            except Exception:
                pass  # kolon zaten var
        # v3.6: kapi gecis/TTL olay gunlugu (histerezis gecikmesi olcumu)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS gate_log("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "ts_utc TEXT, kind TEXT, detail TEXT)")
        self._backfill_cluster_ids()
        self._backfill_fill_ts()
        self._repair_bad_outcomes()

    def verify_outcomes(self, limit: int = 400) -> dict:
        """BAGIMSIZ DENETIM: her kapanmis sinyali mumlardan yeniden oynat.

        Tracker'in kendi dongusunu KULLANMAZ (app/services/verifier.py ayri
        ve sade bir implementasyondur) - yoksa hata kendini dogrular.
        Uyusmazlik = en az biri yanlis; insana getirilir.
        """
        rows = self._db.query(
            "SELECT * FROM signals WHERE outcome IS NOT NULL AND blocked=0 "
            "ORDER BY id DESC LIMIT ?", (limit,))
        checked = 0
        skipped = 0
        issues: list[dict] = []
        for r in rows:
            if not r.get("entry_candle_ts"):
                skipped += 1
                continue
            candles = self._db.query(
                "SELECT ts,open,high,low,close FROM candles WHERE symbol=? "
                "AND interval=? AND ts>=? ORDER BY ts ASC",
                (r["pair"], self._ltf, r["entry_candle_ts"]))
            if not candles:
                skipped += 1
                continue
            rep = verifier.replay(r, candles, self._fill_window,
                                  self._max_track)
            if rep.get("outcome") is None:
                skipped += 1
                continue
            checked += 1
            diff = verifier.compare(r, rep)
            if diff:
                issues.append(diff)
        if issues:
            log.error(kv(event="outcome_audit_mismatch", n=len(issues),
                         ids=",".join(str(i["id"]) for i in issues)))
        return {"checked": checked, "unauditable": skipped,
                "mismatches": len(issues), "details": issues[:25],
                "note": ("bagimsiz yeniden oynatma; uyusmazlik = kayit ile "
                         "mum arsivi celisiyor, elle incelenmeli")}

    def _repair_bad_outcomes(self) -> int:
        """Denetimde celisen kapanmis kayitlari geri ac (v3.6).

        Kok neden (duzeltildi): sinyal onceki turda doldugunda sonuc dongusu
        entry_candle_ts'ten basliyor, DOLUS ONCESI mumlar TP/STOP'a degmis
        sayiliyordu -> LONG'ta uydurma WIN. Bu metot mirasi temizler:
        bagimsiz denetci ile celisen kayit yeniden acilir, duzeltilmis motor
        dolustan itibaren yeniden karara baglar. Denetlenemeyen kayit
        prefill_repaired=2 ile isaretlenir - sessizce dogru varsayilmaz.
        """
        rows = self._db.query(
            "SELECT * FROM signals WHERE status='CLOSED' AND "
            "prefill_repaired=0 AND outcome IN ('WIN','LOSS')")
        reopened = 0
        for r in rows:
            if not r.get("entry_candle_ts"):
                self._db.execute("UPDATE signals SET prefill_repaired=2 "
                                 "WHERE id=?", (r["id"],))
                continue
            candles = self._db.query(
                "SELECT ts,open,high,low,close FROM candles WHERE symbol=? "
                "AND interval=? AND ts>=? ORDER BY ts ASC",
                (r["pair"], self._ltf, r["entry_candle_ts"]))
            rep = verifier.replay(r, candles, self._fill_window,
                                  self._max_track) if candles else {}
            if rep.get("outcome") is None:
                self._db.execute("UPDATE signals SET prefill_repaired=2 "
                                 "WHERE id=?", (r["id"],))
                continue
            if verifier.compare(r, rep) is None:
                self._db.execute("UPDATE signals SET prefill_repaired=1 "
                                 "WHERE id=?", (r["id"],))
                continue
            self._db.execute(
                "UPDATE signals SET status='FILLED', outcome=NULL, "
                "exit_price=NULL, r_multiple=NULL, closed_utc=NULL, "
                "mfe_r=NULL, mae_r=NULL, ambiguous=0, funding_done=0, "
                "funding_r_real=NULL, prefill_repaired=1 WHERE id=?",
                (r["id"],))
            reopened += 1
            log.warning(kv(event="bad_outcome_reopened", signal_id=r["id"],
                           pair=r["pair"], stored=r["outcome"],
                           verifier=rep["outcome"]))
        if reopened:
            log.warning(kv(event="outcome_repair_done", reopened=reopened))
        return reopened

    def _backfill_fill_ts(self) -> int:
        """fill_ts'i olmayan DOLMUS kayitlara dolus anini ham mumlardan turet.

        NEDEN: fill_ts kolonu sonradan eklendi; oncesinde dolan kayitlarda
        NULL. "Dolus oncesi mum karara giremez" kapisi fill_ts'e bagli
        oldugundan, bu eski kayitlar degerlendirmede HER mumu atlayip zombi
        kaliyordu (#57, #6). Uydurma degil TURETMEDIR: giris bolgesi ve
        mumlar kayitli; canli dolus kuraliyla (kenara ilk temas, dolus
        penceresi icinde) birebir ayni kosul uygulanir. Temas bulunamazsa
        NULL birakilir ve sayisi loglanir - sessiz kabul yok.
        """
        rows = self._db.query(
            "SELECT id,pair,direction,entry_candle_ts,entry_min,entry_max "
            "FROM signals WHERE fill_price IS NOT NULL AND fill_ts IS NULL "
            "AND entry_candle_ts IS NOT NULL")
        fixed = 0
        for r in rows:
            candles = self._db.query(
                "SELECT ts,high,low FROM candles WHERE symbol=? AND interval=? "
                "AND ts>=? ORDER BY ts ASC LIMIT ?",
                (r["pair"], self._ltf, r["entry_candle_ts"],
                 self._fill_window))
            is_long = r["direction"] == Direction.LONG.value
            edge = r["entry_max"] if is_long else r["entry_min"]
            if edge is None:
                continue
            for c in candles:
                if (c["low"] <= edge) if is_long else (c["high"] >= edge):
                    self._db.execute(
                        "UPDATE signals SET fill_ts=? WHERE id=?",
                        (c["ts"], r["id"]))
                    fixed += 1
                    break
        if rows:
            log.info(kv(event="fill_ts_backfill", scanned=len(rows),
                        fixed=fixed))
        return fixed

    def _backfill_cluster_ids(self) -> int:
        """cluster_id'si bos kayitlari geriye donuk etiketle (v3.6 duzeltme).

        NEDEN: kolon v3.5'te eklendi; oncesinde dogan ve gist'ten geri
        yuklenen kayitlarda bos. Bos etiketi 'kendi basina kume' saymak
        bagimsiz kanit sayisini SISIRIR - konseyin elestirdigi hatanin ta
        kendisi. Etiket kayipsizdir: yon + 4H penceresi zaten kayitli
        (entry_candle_ts, yoksa created_utc), canli yolla AYNI fonksiyondan
        yeniden uretilir.

        Idempotent: yalniz NULL/bos olanlara dokunur, her acilista guvenle
        calisir. Zamani okunamayan kayit etiketsiz KALIR (uydurma yok) ve
        istatistikten disarida tutulur.
        """
        rows = self._db.query(
            "SELECT id,direction,entry_candle_ts,created_utc FROM signals "
            "WHERE cluster_id IS NULL OR cluster_id=''")
        updates: list[tuple] = []
        for r in rows:
            if not r.get("direction"):
                continue
            ts = r.get("entry_candle_ts")
            if not ts and r.get("created_utc"):
                try:
                    ts = int(datetime.strptime(
                        r["created_utc"], "%Y-%m-%dT%H:%M:%SZ")
                        .replace(tzinfo=timezone.utc).timestamp() * 1000)
                except (ValueError, TypeError):
                    ts = None
            if not ts:
                continue                      # zaman yok -> etiketsiz birak
            updates.append((_cluster_key(r["direction"], ts), r["id"]))
        if updates:
            self._db.executemany(
                "UPDATE signals SET cluster_id=? WHERE id=?", updates)
            log.info(kv(event="cluster_backfill", filled=len(updates),
                        scanned=len(rows)))
        return len(updates)

    @property
    def db(self):
        """Ayni SQLite baglantisi - aday motoru kendi tablosunu burada acar."""
        return self._db

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
        # Zombi kilidi (ayni sinifin son kapisi): dolmus ama fill_ts'i
        # olmayan kayitta dolus ani yuruyus sirasinda ayni temas kuraliyla
        # tespit edilir; kapi sonsuza dek kapali kalamaz.
        derive_fill = fill_price is not None and sig.get("fill_ts") is None
        edge = sig["entry_max"] if is_long else sig["entry_min"]
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
                if not touched:
                    if i + 1 >= self._fill_window:
                        self._close(sig["id"], "NOT_FILLED", None, 0.0)
                        return
                    continue
                fill_price = sig["entry_max"] if is_long else sig["entry_min"]
                filled_at_idx = i
                self._db.execute(
                    "UPDATE signals SET status='FILLED', fill_price=?, "
                    "fill_ts=? WHERE id=?",
                    (fill_price, c["ts"], sig["id"]))
                sig["fill_ts"] = c["ts"]
                # v3.7 (2026-08-05): dolus mumu da SONUC kontrolune girer -
                # continue YOK. Ilan edilen kural (verifier): "dolus mumundan
                # ITIBAREN once stop mu TP mi". Mumu atlamak dolus mumundaki
                # stop temasini kacirir; sonraki ralli uydurma WIN yazar.

            # --- 2) sonuc kontrolu ---
            risk = (fill_price - sig["stop_loss"]) if is_long else (sig["stop_loss"] - fill_price)
            if risk <= 0:
                self._close(sig["id"], "AMBIGUOUS", fill_price, 0.0)
                return
            # v3.6: lehte/aleyhte gezinme YALNIZ dolus anindan itibaren.
            # DIKKAT: sinyal onceki turda dolduysa fill_price DB'den gelir ve
            # dongu entry_candle_ts'ten baslar - dolus ONCESI mumlar da bu
            # bloga girer. fill_ts ile filtrelenmezse MFE/MAE sisirilir.
            if (derive_fill and filled_at_idx is None and edge is not None
                    and ((c["low"] <= edge) if is_long
                         else (c["high"] >= edge))):
                filled_at_idx = i
                self._db.execute("UPDATE signals SET fill_ts=? WHERE id=?",
                                 (c["ts"], sig["id"]))
                sig["fill_ts"] = c["ts"]
            at_or_after_fill = (filled_at_idx is not None
                                or (sig.get("fill_ts") is not None
                                    and c["ts"] >= sig["fill_ts"]))
            if at_or_after_fill:
                seen_fill = True
                fav = ((c["high"] - fill_price) if is_long
                       else (fill_price - c["low"])) / risk
                adv = ((fill_price - c["low"]) if is_long
                       else (c["high"] - fill_price)) / risk
                mfe = max(mfe, fav)
                mae = max(mae, adv)
            # v3.6-KRITIK: SONUC kontrolu de yalniz dolustan itibaren.
            # Sinyal onceki turda dolduysa fill_price DB'den gelir, dolus
            # dallanmasi atlanir ve dongu entry_candle_ts'ten baslar. Bu
            # filtre olmadan DOLUS ONCESI mumlar TP/STOP'a degmis sayilir:
            # LONG'ta fiyat once TP'ye kosup sonra bolgeye inerse UYDURMA
            # WIN yazilir - kacirilan hareket kazanc gibi kaydedilir.
            if not at_or_after_fill:
                continue
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
            # v3.6: tutus suresi DOLUSTAN sayilir. Onceki turda dolan
            # sinyalde filled_at_idx=None'dir; 0'a dusmek suresi
            # entry_candle_ts'ten saymak demektir ve izleme penceresini
            # gecikme kadar ERKEN bitirir (ayni "dolus oncesi bulasma"
            # sinifi - kural 6: ornegi degil sinifi duzelt).
            if filled_at_idx is not None:
                bars_held = i - filled_at_idx
            elif sig.get("fill_ts") is not None:
                bars_held = len([1 for cc in candles[:i + 1]
                                 if cc["ts"] >= sig["fill_ts"]]) - 1
            else:
                bars_held = i                      # eski kayit: fill_ts yok
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
        unclustered = 0
        for r in closed_rows:
            cst = cost_r(r)
            if cst is not None and r.get("r_multiple") is not None:
                net = r["r_multiple"] - cst
                net_vals.append(net)
                cid = r.get("cluster_id")
                if not cid:
                    # v3.6 DUZELTME: etiketsiz kaydi 'kendi basina kume'
                    # saymak bagimsiz kanit sayisini sisirir. Disarida
                    # birakilir ve sayisi raporlanir (sessiz kayip yok).
                    unclustered += 1
                    continue
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
            "unclustered_excluded": unclustered,
            "max_drawdown_r": self.max_drawdown_r(),          # gercek kohort
            "max_drawdown_r_all": self.max_drawdown_r(False),
            # v3.6: denetim OZETI stats'a girer ki yedekten uzaktan
            # gorulebilsin. Tam rapor /verify ve /measurement'ta.
            "outcome_audit": self._audit_summary(),
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
    def _audit_summary(self) -> dict:
        """Son denetimin ozeti (onbellekli). Alarm kaydi ve yedek bunu okur;
        agac ormanda devrilmesin diye sonuc DISARIYA ulasmali."""
        try:
            cached = getattr(self, "_audit_cache", None)
            if cached is None:
                cached = self.verify_outcomes()
                self._audit_cache = cached
            return {"checked": cached.get("checked"),
                    "mismatches": cached.get("mismatches"),
                    "unauditable": cached.get("unauditable"),
                    "ids": [d.get("id") for d in cached.get("details", [])][:10]}
        except Exception:
            log.exception(kv(event="audit_summary_error"))
            return {"error": "denetim ozeti uretilemedi"}

    def refresh_audit(self) -> dict:
        """Periyodik denetim: onbellegi tazeler (scheduler ~6 saatte cagirir)."""
        self._audit_cache = self.verify_outcomes()
        return self._audit_cache

    def max_drawdown_r(self, since_lock: bool = True) -> float:
        """Net R serisinde en buyuk tepe-dip mesafesi.

        KAPSAM ONEMLI: yanlislama kriteri #2 (config-lock.md) "GERCEK
        KOHORTTA maliyet-modelli maksDD > 20R" der - yani kilit sonrasi
        kohort. Tum zamanlari olcmek ilan edilen tanimdan SAPMAKTIR; iki
        pencere farkli cevap verebilir (olculdu: tumu 36.7R, kilit oncesi
        11.8R, kilit sonrasi 35.6R). Varsayilan ilan edilen tanimdir.
        """
        sql = ("SELECT direction,outcome,entry_min,entry_max,stop_loss,"
               "fill_price,r_multiple,closed_utc FROM signals WHERE "
               "status='CLOSED' AND blocked=0 AND outcome IN ('WIN','LOSS')")
        params: tuple = ()
        if since_lock:
            sql += " AND created_utc >= ?"
            params = (measurement.LOCK_UTC,)
        rows = self._db.query(sql + " ORDER BY closed_utc ASC", params)
        peak = cum = dd = 0.0
        for r in rows:
            c = cost_r(r)
            if c is None or r.get("r_multiple") is None:
                continue
            cum += r["r_multiple"] - c
            peak = max(peak, cum)
            dd = max(dd, peak - cum)
        return round(dd, 2)

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
            # v3.6: etiketsizler tek bir '?' kovasinda toplanir; her biri
            # ayri kume sayilmaz (bagimsiz kanit sisirmesi olmasin).
            cid = r.get("cluster_id") or "?etiketsiz"
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
        # yogunlasma yalniz GERCEK kumeler uzerinden (etiketsiz kova haric)
        conc = measurement.top_share([c["net_r"] for c in cluster_list
                                      if c["cluster"] != "?etiketsiz"])
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
            "outcome_audit": self.verify_outcomes(),
        }

    def recent_signals(self, limit: int = 50) -> list[dict]:
        """Golge takipteki son sinyaller (yeni -> eski); r_net dahil (v3.5)."""
        rows = self._db.query(
            "SELECT id,pair,direction,created_utc,entry_candle_ts,status,outcome,"
            "entry_min,entry_max,stop_loss,tp1,tp2,rr,fill_price,exit_price,"
            "r_multiple,closed_utc,confidence,setup_type,cluster_id,engine_sha,"
            # v3.6: olcum kolonlari yedege girmezse her restore'da SESSIZCE
            # kaybolur - hypo/nf/mfe/funding verisi yeniden uretilemez.
            "fill_ts,ambiguous,hypo_r,hypo_done,mfe_r,mae_r,nf_gap_r,"
            "nf_touch_bars,nf_crossed,nf_done,funding_r_real,funding_done "
            "FROM signals WHERE blocked=0 ORDER BY id DESC LIMIT ?",
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
            "cluster_id,engine_sha,block_reason,"
            # v3.6: bloklu kohort da degerlendiriliyor -> olcum kolonlari
            # yedege girmezse restore'da kaybolur (gercek kohortla ayni kural)
            "fill_ts,ambiguous,hypo_r,hypo_done,mfe_r,mae_r,nf_gap_r,"
            "nf_touch_bars,nf_crossed,nf_done,funding_r_real,funding_done "
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
                "hypo_r,hypo_done,fill_ts,ambiguous,mfe_r,mae_r,nf_gap_r,"
                "nf_touch_bars,nf_crossed,nf_done,funding_r_real,funding_done) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,"
                "?,?,?,?,?,?,?,?,?,?)",
                (r.get("pair"), r.get("direction"), r.get("created_utc"),
                 r.get("entry_candle_ts"), r.get("entry_min"), r.get("entry_max"),
                 r.get("stop_loss"), r.get("tp1"), r.get("tp2"), r.get("rr"),
                 r.get("status", "PENDING"), r.get("outcome"),
                 r.get("fill_price"), r.get("exit_price"),
                 r.get("r_multiple"), r.get("closed_utc"),
                 r.get("confidence"), r.get("setup_type"),
                 r.get("blocked", 0), r.get("cluster_id"),
                 r.get("engine_sha"), r.get("block_reason"),
                 r.get("hypo_r"), r.get("hypo_done", 0),
                 r.get("fill_ts"), r.get("ambiguous", 0),
                 r.get("mfe_r"), r.get("mae_r"), r.get("nf_gap_r"),
                 r.get("nf_touch_bars"), r.get("nf_crossed"),
                 r.get("nf_done", 0), r.get("funding_r_real"),
                 r.get("funding_done", 0)))
            imported += 1
        if imported:
            # gist yedekteki eski kayitlarda cluster_id bos olabilir;
            # geri yukler yuklemez etiketle ki istatistik disi kalmasin
            self._backfill_cluster_ids()
        return imported
