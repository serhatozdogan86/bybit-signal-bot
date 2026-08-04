"""
ADAY (CHALLENGER) MOTORU - v1. Golge yarisci; sampiyona SIFIR dokunus.

Tasarim: docs/challengers-design.md. Izolasyon sartlari:
- Yalniz kendi tablosuna yazar (challenger_signals). Sampiyon tablolarini
  OKUMAZ ve onlara YAZMAZ (test_invariants bunu bayt-bayt zorlar).
- Ekstra pazar verisi cekmez: tarama sirasinda zaten cekilmis serileri alir.
  Tek istisna: tarama basina 1 toplu tickers cagrisi (funding icin) -
  scheduler'da, tum semboller tek istekte.
- Hicbir hatasi taramayi dusuremez (cagiran taraf fail-soft sarar).

Olcum durustlugu:
- Girisler KAPANIS bazli (limit-bolge yok -> NOT_FILLED belirsizligi yok).
- v1'de TUM stratejiler sabit stop + sabit hedef + zaman asimi kullanir;
  iz-suren cikislar (chandelier, karsi-Donchian) v2'ye ertelendi. Not:
  bu, trend stratejileri (S1/S2) icin MUHAFAZAKAR alt sinir uretir.
- Ayni mumda hem stop hem hedef -> yol bilinemez -> LOSS + ambiguous=1
  (sampiyonla ayni kural).
- Maliyet modeli v0 sabitleri sampiyonla AYNI (signal_tracker'dan import).
- Kume = strateji + yon + 4H penceresi; CI = kume-blok bootstrap.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.logging_setup import kv
from app.services import measurement
from app.services.signal_tracker import FUNDING_8H, STOP_SLIP, TAKER_FEE

log = logging.getLogger("challengers")

STRATEGIES = ("S1_TSMOM", "S2_DONCHIAN", "S3_MEANREV", "S4_CARRY", "S6_SWEEP")
# Acik pozisyon tavani - STRATEJIYE GORE (v1.1 duzeltmesi).
# NEDEN: tek tavan (15) yarisi adaletsiz kildi. Uzun tutan trend adaylari
# (S1 medyan 45 bar, S4 37 bar) slotlari doldurup YENI SINYAL URETEMEZ hale
# geldi; hizli devreden S3 (6 bar) ve S6 (2 bar) veriyi hizla biriktirdi.
# 8 saat sonunda S3 8 kume toplarken S1 hala 1 kumedeydi. Boyle giderse
# "en iyi aday" degil "en hizli devreden aday" hukum alirdi.
# Tavan artik ortalama tutus suresiyle ORANTILI: yavas adaylar da makul
# surede 50 kumeye ulasabilsin. Bu bir OLCUM ALTYAPISI duzeltmesidir;
# hicbir stratejinin giris/cikis kurali degismedi.
MAX_OPEN = {"S1_TSMOM": 40, "S2_DONCHIAN": 40, "S4_CARRY": 40,
            "S3_MEANREV": 15, "S6_SWEEP": 15}
MAX_OPEN_DEFAULT = 15
# Ornekleme rejimi damgasi: tavan degisimi oncesi/sonrasi kohortlar
# BIRLESTIRILEMEZ (farkli kisitla toplandilar). Istatistikler yalniz
# gecerli rejimi sayar; eski kayitlar tabloda kalir ama hesaba girmez.
SAMPLING_REGIME = 2
FAZ1_TARGET = 50                # sampiyonla ayni sinav esigi


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------ gostergeler
def _ema(vals: list[float], n: int) -> float | None:
    if len(vals) < n // 2:
        return None
    k = 2.0 / (n + 1)
    seed = min(30, len(vals))
    e = sum(vals[:seed]) / seed
    for v in vals[seed:]:
        e = v * k + e * (1 - k)
    return e


def _atr(high: list[float], low: list[float], close: list[float],
         n: int = 14) -> float | None:
    if len(close) < n + 1:
        return None
    trs = [max(high[i] - low[i], abs(high[i] - close[i - 1]),
               abs(low[i] - close[i - 1])) for i in range(1, len(close))]
    a = sum(trs[:n]) / n
    for t in trs[n:]:
        a = (a * (n - 1) + t) / n
    return a


def _adx(high: list[float], low: list[float], close: list[float],
         n: int = 14) -> float | None:
    """Wilder ADX - S3'un 'yatay rejim' kapisi (ADX < 20)."""
    if len(close) < 2 * n + 2:
        return None
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(close)):
        up = high[i] - high[i - 1]
        dn = low[i - 1] - low[i]
        plus_dm.append(up if (up > dn and up > 0) else 0.0)
        minus_dm.append(dn if (dn > up and dn > 0) else 0.0)
        trs.append(max(high[i] - low[i], abs(high[i] - close[i - 1]),
                       abs(low[i] - close[i - 1])))
    def wilder(xs):
        s = sum(xs[:n])
        out = [s]
        for x in xs[n:]:
            s = s - s / n + x
            out.append(s)
        return out
    tr_s, p_s, m_s = wilder(trs), wilder(plus_dm), wilder(minus_dm)
    dxs = []
    for t, p, m in zip(tr_s, p_s, m_s):
        if t <= 0:
            continue
        pdi, mdi = 100 * p / t, 100 * m / t
        if pdi + mdi > 0:
            dxs.append(100 * abs(pdi - mdi) / (pdi + mdi))
    if len(dxs) < n:
        return None
    a = sum(dxs[:n]) / n
    for d in dxs[n:]:
        a = (a * (n - 1) + d) / n
    return a


def _arrays(series, drop_last: bool):
    cs = series.candles[:-1] if drop_last else series.candles
    return ([c.high for c in cs], [c.low for c in cs],
            [c.close for c in cs], [c.volume for c in cs])


# ------------------------------------------------------------------ motor
class ChallengerEngine:
    def __init__(self, db, ltf: str = "15"):
        self._db = db
        self._ltf = ltf
        self._migrate()

    def _migrate(self) -> None:
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS challenger_signals("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "strategy TEXT, pair TEXT, direction TEXT, created_utc TEXT,"
            "entry_ts INTEGER, entry REAL, stop REAL, tp REAL,"
            "timeout_bars INTEGER, status TEXT DEFAULT 'OPEN',"
            "outcome TEXT, exit_price REAL, exit_ts INTEGER,"
            "r_multiple REAL, hold_bars INTEGER, cluster_id TEXT,"
            "ambiguous INTEGER DEFAULT 0, regime INTEGER DEFAULT 1)")
        try:
            self._db.execute("ALTER TABLE challenger_signals ADD COLUMN "
                             "regime INTEGER DEFAULT 1")
        except Exception:
            pass  # kolon zaten var

    # ------------------------------------------------------- sinyal uretimi
    def on_scan(self, symbol: str, htf, ltf, funding: float | None) -> int:
        """Tarama sirasinda zaten cekilmis serilerle aday sinyalleri uret."""
        if ltf is None or len(ltf.candles) < 40:
            return 0
        last = ltf.candles[-1]
        bucket = int(last.ts // 14_400_000)
        made = 0
        for strat, sig in self._generate(symbol, htf, ltf, funding):
            direction, stop, tp, timeout = sig
            cid = f"{strat}:{direction[0]}{bucket}"
            if self._dup(strat, symbol, cid) or self._crowded(strat):
                continue
            self._db.execute(
                "INSERT INTO challenger_signals(strategy,pair,direction,"
                "created_utc,entry_ts,entry,stop,tp,timeout_bars,cluster_id,"
                "regime) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (strat, symbol, direction, _now_iso(), last.ts,
                 round(last.close, 8), round(stop, 8), round(tp, 8),
                 timeout, cid, SAMPLING_REGIME))
            made += 1
            log.info(kv(event="challenger_signal", strategy=strat,
                        pair=symbol, direction=direction))
        return made

    def _dup(self, strat: str, pair: str, cid: str) -> bool:
        r = self._db.query_one(
            "SELECT 1 x FROM challenger_signals WHERE strategy=? AND pair=? "
            "AND (status='OPEN' OR cluster_id=?) LIMIT 1",
            (strat, pair, cid))
        return r is not None

    def _crowded(self, strat: str) -> bool:
        r = self._db.query_one(
            "SELECT COUNT(*) n FROM challenger_signals WHERE strategy=? "
            "AND status='OPEN'", (strat,))
        return (r["n"] or 0) >= MAX_OPEN.get(strat, MAX_OPEN_DEFAULT)

    def _generate(self, symbol, htf, ltf, funding):
        """(strateji, (yon, stop, tp, timeout_bar)) ciftleri."""
        out = []
        l_high, l_low, l_close, l_vol = _arrays(ltf, drop_last=False)
        entry = l_close[-1]
        atr_l = _atr(l_high, l_low, l_close)
        h_ok = htf is not None and len(htf.candles) >= 40
        if h_ok:
            h_high, h_low, h_close, _ = _arrays(htf, drop_last=True)
            atr_h = _atr(h_high, h_low, h_close)
        else:
            h_high = h_low = h_close = []
            atr_h = None

        # S1 TSMOM: 4H kapanis EMA200 ustunde VE 12x4H momentum ayni yonde
        if atr_h and len(h_close) >= 120:
            ema = _ema(h_close, 200)
            if ema is not None and len(h_close) >= 13:
                mom = h_close[-1] - h_close[-13]
                if h_close[-1] > ema and mom > 0:
                    out.append(("S1_TSMOM",
                                ("LONG", entry - 2 * atr_h,
                                 entry + 6 * atr_h, 192)))
                elif h_close[-1] < ema and mom < 0:
                    out.append(("S1_TSMOM",
                                ("SHORT", entry + 2 * atr_h,
                                 entry - 6 * atr_h, 192)))

        # S2 DONCHIAN: 20x4H kanal kirilimi (kenar tetik: onceki bar icerde)
        if atr_h and len(h_high) >= 21 and len(l_close) >= 2:
            dh, dl = max(h_high[-20:]), min(h_low[-20:])
            if l_close[-2] <= dh < l_close[-1]:
                out.append(("S2_DONCHIAN",
                            ("LONG", entry - 2 * atr_h,
                             entry + 6 * atr_h, 192)))
            elif l_close[-2] >= dl > l_close[-1]:
                out.append(("S2_DONCHIAN",
                            ("SHORT", entry + 2 * atr_h,
                             entry - 6 * atr_h, 192)))

        # S3 MEANREV: yalniz yatay rejimde (4H ADX<20) 2σ sapmayi sat/al
        if atr_l and len(l_close) >= 21:
            adx = _adx(h_high, h_low, h_close) if h_ok else None
            if adx is not None and adx < 20:
                sma = sum(l_close[-20:]) / 20
                var = sum((x - sma) ** 2 for x in l_close[-20:]) / 20
                sd = var ** 0.5
                if sd > 0:
                    if entry < sma - 2 * sd:
                        out.append(("S3_MEANREV",
                                    ("LONG", entry - 1.5 * atr_l, sma, 96)))
                    elif entry > sma + 2 * sd:
                        out.append(("S3_MEANREV",
                                    ("SHORT", entry + 1.5 * atr_l, sma, 96)))

        # S4 CARRY: yilliklandirilmis |funding| > %30 -> kalabaligin tersi
        if atr_h and funding is not None:
            ann = funding * 3 * 365
            if ann > 0.30:
                risk = 2 * atr_h
                out.append(("S4_CARRY",
                            ("SHORT", entry + risk, entry - 2 * risk, 192)))
            elif ann < -0.30:
                risk = 2 * atr_h
                out.append(("S4_CARRY",
                            ("LONG", entry - risk, entry + 2 * risk, 192)))

        # S6 SWEEP: swing ekstremumu asilir ama kapanis gerisinde + hacim
        if atr_l and len(l_close) >= 100:
            sw_h = max(l_high[-98:-2])
            sw_l = min(l_low[-98:-2])
            vol_sma = sum(l_vol[-21:-1]) / 20
            c = ltf.candles[-1]
            vol_ok = vol_sma > 0 and c.volume >= 1.5 * vol_sma
            if c.high > sw_h and c.close < sw_h and vol_ok:
                # stop, ESKI swing degil supurme FITILININ otesinde durur:
                # fitilin siradan retesti pozisyonu dusurmemeli
                stop = c.high + 0.5 * atr_l
                risk = stop - entry
                if risk > 0:
                    out.append(("S6_SWEEP",
                                ("SHORT", stop, entry - 2 * risk, 96)))
            elif c.low < sw_l and c.close > sw_l and vol_ok:
                stop = c.low - 0.5 * atr_l
                risk = entry - stop
                if risk > 0:
                    out.append(("S6_SWEEP",
                                ("LONG", stop, entry + 2 * risk, 96)))
        return out

    # ------------------------------------------------------- degerlendirme
    def evaluate_open(self, pair: str) -> None:
        """Acik aday pozisyonlarini DB mumlariyla kapat. Tek yol, tek kural:
        giris mumu SONRASI mumlar; ayni mumda stop+tp -> LOSS ambiguous."""
        rows = self._db.query(
            "SELECT * FROM challenger_signals WHERE pair=? AND status='OPEN'",
            (pair,))
        for r in rows:
            candles = self._db.query(
                "SELECT ts,high,low,close FROM candles WHERE symbol=? AND "
                "interval=? AND ts>? ORDER BY ts ASC",
                (pair, self._ltf, r["entry_ts"]))
            self._evaluate_one(r, candles)

    def _evaluate_one(self, r: dict, candles: list[dict]) -> None:
        is_long = r["direction"] == "LONG"
        risk = (r["entry"] - r["stop"]) if is_long else (r["stop"] - r["entry"])
        if risk <= 0:
            self._close(r["id"], "AMBIGUOUS", r["entry"], 0.0, 0, 1)
            return
        for i, c in enumerate(candles):
            hit_stop = (c["low"] <= r["stop"]) if is_long else (c["high"] >= r["stop"])
            hit_tp = (c["high"] >= r["tp"]) if is_long else (c["low"] <= r["tp"])
            if hit_stop and hit_tp:
                self._close(r["id"], "LOSS", r["stop"], -1.0, i + 1, 1)
                return
            if hit_stop:
                self._close(r["id"], "LOSS", r["stop"], -1.0, i + 1, 0)
                return
            if hit_tp:
                rr = (r["tp"] - r["entry"]) if is_long else (r["entry"] - r["tp"])
                self._close(r["id"], "WIN", r["tp"],
                            round(rr / risk, 2), i + 1, 0)
                return
            if i + 1 >= r["timeout_bars"]:
                pnl = (c["close"] - r["entry"]) if is_long else (r["entry"] - c["close"])
                self._close(r["id"], "EXPIRED", c["close"],
                            round(pnl / risk, 2), i + 1, 0)
                return

    def _close(self, cid: int, outcome: str, exit_price: float,
               r_multiple: float, hold_bars: int, ambiguous: int) -> None:
        self._db.execute(
            "UPDATE challenger_signals SET status='CLOSED', outcome=?, "
            "exit_price=?, exit_ts=NULL, r_multiple=?, hold_bars=?, "
            "ambiguous=? WHERE id=?",
            (outcome, round(exit_price, 8), r_multiple, hold_bars,
             ambiguous, cid))
        log.info(kv(event="challenger_close", id=cid, outcome=outcome,
                    r=r_multiple))

    def open_pairs(self) -> list[str]:
        return [r["pair"] for r in self._db.query(
            "SELECT DISTINCT pair FROM challenger_signals WHERE status='OPEN'")]

    # ------------------------------------------------------------ istatistik
    def _net_r(self, r: dict) -> float | None:
        if r.get("r_multiple") is None or not r.get("entry"):
            return None
        stop_frac = abs(r["entry"] - r["stop"]) / r["entry"]
        if stop_frac <= 0:
            return None
        fee = 2 * TAKER_FEE / stop_frac
        slip = (STOP_SLIP / stop_frac) if r["outcome"] == "LOSS" else 0.0
        hours = (r.get("hold_bars") or 0) * 0.25
        funding = FUNDING_8H * (hours / 8.0) / stop_frac
        return r["r_multiple"] - fee - slip - funding

    def stats(self) -> dict:
        out = {"note": ("Golge adaylar - sampiyonla ayni maliyet modeli, "
                        "ayni kume-CI standardi, ayni 50-kume esigi. "
                        "v1 cikislari sabit hedefli (trend adaylari icin "
                        "muhafazakar alt sinir). Rejim-2: acik pozisyon "
                        "tavani stratejiye gore ayarlandi; rejim-1 kayitlari "
                        "farkli kisitla toplandigi icin hesaba GIRMEZ. "
                        "Yatirim tavsiyesi degildir."),
               "faz1_target": FAZ1_TARGET, "strategies": {}}
        allrows = self._db.query("SELECT * FROM challenger_signals")
        rows = [r for r in allrows
                if (r.get("regime") or 1) == SAMPLING_REGIME]
        eski = [r for r in allrows
                if (r.get("regime") or 1) != SAMPLING_REGIME]
        out["sampling_regime"] = SAMPLING_REGIME
        out["retired_rows"] = len(eski)
        out["max_open"] = MAX_OPEN
        for strat in STRATEGIES:
            mine = [r for r in rows if r["strategy"] == strat]
            closed = [r for r in mine if r["status"] == "CLOSED"
                      and r["outcome"] in ("WIN", "LOSS", "EXPIRED")]
            decided = [r for r in closed if r["outcome"] in ("WIN", "LOSS")]
            wins = sum(1 for r in decided if r["outcome"] == "WIN")
            clusters: dict[str, list[float]] = {}
            gross = net = 0.0
            for r in closed:
                if r.get("r_multiple") is not None:
                    gross += r["r_multiple"]
                n = self._net_r(r)
                if n is not None:
                    net += n
                    clusters.setdefault(r["cluster_id"] or "?", []).append(n)
            boot = measurement.cluster_bootstrap(clusters)
            out["strategies"][strat] = {
                "open": sum(1 for r in mine if r["status"] == "OPEN"),
                "decided": len(decided), "wins": wins,
                "win_rate": round(wins / len(decided), 3) if decided else None,
                "expired": sum(1 for r in closed if r["outcome"] == "EXPIRED"),
                "gross_r": round(gross, 2), "net_r": round(net, 2),
                "clusters": len(clusters),
                "ci": ([boot["ci_low"], boot["ci_high"]]
                       if boot and boot.get("ci_low") is not None else None),
                "e_net": boot["e_net"] if boot else None,
            }
        return out

    def recent(self, limit: int = 120) -> list[dict]:
        return self._db.query(
            "SELECT * FROM challenger_signals ORDER BY id DESC LIMIT ?",
            (limit,))
