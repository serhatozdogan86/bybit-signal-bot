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

STRATEGIES = ("S1_TSMOM", "S2_DONCHIAN", "S3_MEANREV", "S4_CARRY", "S6_SWEEP",
              "S7_WYCKOFF")   # S7: 2026-08-06, tetik = S6 sinavini doldurdu
# Acik pozisyon tavani - STRATEJIYE GORE (v1.1 duzeltmesi).
# NEDEN: tek tavan (15) yarisi adaletsiz kildi. Uzun tutan trend adaylari
# (S1 medyan 45 bar, S4 37 bar) slotlari doldurup YENI SINYAL URETEMEZ hale
# geldi; hizli devreden S3 (6 bar) ve S6 (2 bar) veriyi hizla biriktirdi.
# 8 saat sonunda S3 8 kume toplarken S1 hala 1 kumedeydi. Boyle giderse
# "en iyi aday" degil "en hizli devreden aday" hukum alirdi.
# Tavan artik ortalama tutus suresiyle ORANTILI: yavas adaylar da makul
# surede 50 kumeye ulasabilsin. Bu bir OLCUM ALTYAPISI duzeltmesidir;
# hicbir stratejinin giris/cikis kurali degismedi.
# 2026-08-12 karar toplantisi (Madde 4): S3/S6 kenar olumu ILAN EDILMIS
# kosulla kanitlandi (CHALLENGER_DEAD) -> emekli. Bosalan 15+15=30 slot,
# tavana bogulan S1'e devredildi (40->70). Efektif toplam butce SABIT
# (165): bu bir TURETMEDIR, yeni butce icat edilmedi. S1 dogrulama
# penceresi ayni gun acildigi icin dogrulama kohortu TAMAMEN tavan-70
# altinda toplanir; secim kohortu (tavan-40) arsivde ayri durur.
MAX_OPEN = {"S1_TSMOM": 70, "S2_DONCHIAN": 40, "S4_CARRY": 40,
            "S3_MEANREV": 15, "S6_SWEEP": 15,
            # S7: tasarimda tavan yazilmadi; rejim-2 kurali uygulanir
            # ("tavan tutus suresiyle orantili") - zaman asimi 96 bar =
            # S3/S6 sinifi -> 15 (varsayilanla ayni, ICAT degil turetme)
            "S7_WYCKOFF": 15}
# Emekli adaylar: yeni sinyal uretimi DURUR; acik pozisyonlar normal
# degerlendirilir, kapanmis kohort arsivde kalir ve stats'ta
# retired_utc ile raporlanir (sessiz kaybolma yok).
RETIRED = {"S3_MEANREV": "2026-08-12", "S6_SWEEP": "2026-08-12"}
MAX_OPEN_DEFAULT = 15
# Ornekleme rejimi damgasi: tavan degisimi oncesi/sonrasi kohortlar
# BIRLESTIRILEMEZ (farkli kisitla toplandilar). Istatistikler yalniz
# gecerli rejimi sayar; eski kayitlar tabloda kalir ama hesaba girmez.
SAMPLING_REGIME = 2
FAZ1_TARGET = 50                # sampiyonla ayni sinav esigi

# ---- ON-KAYITLI dogrulama pencereleri (secim-sonrasi walk-forward) ----
# Kural (challengers-design.md, coklu karsilastirma): one cikan aday,
# ilan ANINDAN SONRA toplanan veride sinavi YENIDEN gecmek zorundadir.
# Ilan sonuca bakilarak uzatilamaz/geri alinamaz; hukum = yeni kohortta
# >=FAZ1_TARGET kapanmis kume VE kume-CI alt siniri > 0. Strateji
# kurallari, tavan ve maliyet modeli AYNEN kalir (rejim degismez).
# S1: secim penceresi 50 kumede doldu, CI alt siniri -0.053 -> kil payi
# gecemedi; dogrulama penceresi 2026-08-12'de ilan edildi (Serhat onayi).
VALIDATION_WINDOWS = {"S1_TSMOM": "2026-08-12T00:00:00Z"}

# ---- strateji parametre sabitleri: TEK KAYNAK (v1.2, suruklenme yasagi) ----
# Hem _generate() hem STRATEGY_INFO (pano detay penceresi) BU sabitleri okur;
# kod degisince aciklama otomatik guncellenir, elle es tutulan metin yoktur.
# DEGERLER AYNEN KORUNDU - bu bir yeniden adlandirmadir, esik degisikligi degil.
TSMOM_EMA_N = 200        # S1: 4H EMA uzunlugu
TSMOM_MOM_BARS = 12      # S1: momentum penceresi (4H bar)
DONCHIAN_N = 20          # S2: kanal penceresi (4H bar)
TREND_STOP_ATR = 2.0     # S1/S2: stop mesafesi (ATR-4H kati)
TREND_TP_ATR = 6.0       # S1/S2: hedef mesafesi (ATR-4H kati)
TREND_TIMEOUT = 192      # S1/S2/S4: zaman asimi (15dk bar) = 48 saat
S3_ADX_MAX = 20.0        # S3: yatay-rejim kapisi (4H ADX ust siniri)
S3_SMA_N = 20            # S3: ortalama penceresi (15dk bar)
S3_SIGMA = 2.0           # S3: sapma esigi (standart sapma kati)
S3_STOP_ATR = 1.5        # S3: stop mesafesi (ATR-15dk kati)
FAST_TIMEOUT = 96        # S3/S6/S7: zaman asimi (15dk bar) = 24 saat
S4_ANN_FUNDING = 0.30    # S4: yillik |funding| esigi
S4_RISK_ATR = 2.0        # S4: risk birimi (ATR-4H kati)
S4_TP_RISK = 2.0         # S4: hedef (risk kati)
S6_SWING_N = 96          # S6: swing penceresi (15dk bar)
S6_VOL_MULT = 1.5        # S6: hacim esigi (SMA20 kati)
S6_WICK_ATR = 0.5        # S6: stop tamponu (fitil otesi, ATR-15dk kati)
S6_TP_RISK = 2.0         # S6: hedef (risk kati)
# S7 Wyckoff Spring+Test - tasarim 8eecb5a'daki sayilar BIREBIR:
S7_SWING_N = 96          # S7: swing penceresi (15dk bar)
S7_VOL_SPRING = 1.5      # S7: spring hacmi >= 1.5 x SMA20 (yuksek)
S7_VOL_TEST = 0.7        # S7: test hacmi   <= 0.7 x SMA20 (KURUMUS - S6'nin tersi)
S7_ATR_PROX = 0.25       # S7: test yaklasma VE stop tamponu (ATR-15dk kati)
S7_TEST_WINDOW = 6       # S7: spring sonrasi test icin 1-6 bar
S7_TP_RISK = 2.0         # S7: hedef (risk kati)


def _saat(bars: int) -> str:
    return f"{bars} bar ({bars * 15 // 60} saat)"


def _honesty(strat: str) -> list[str]:
    """Durustluk notlari - sabitlerden turetilir, elle es tutulmaz."""
    if strat in ("S1_TSMOM", "S2_DONCHIAN"):
        notes = ["v1 çıkışları sabit hedeflidir — trend stratejileri için bu, "
                 "muhafazakâr bir alt sınırdır; iz süren çıkışlar v2'de."]
    else:
        notes = ["v1 çıkışları sabit hedeflidir; iz süren çıkışlar "
                 "v2'ye ertelendi."]
    notes.append(f"Örnekleme rejimi {SAMPLING_REGIME}: açık pozisyon tavanı "
                 "stratejiye göre ayarlandı; önceki rejimin kayıtları hesaba "
                 "girmez.")
    notes.append("Gölge ölçümdür, gerçek emir yoktur; "
                 "yatırım tavsiyesi değildir.")
    return notes


# Pano detay penceresinin TEK bilgi kaynagi. UI bu sozlugu /challengers
# uzerinden okur; metinler arayuze elle YAZILMAZ. Sayilar yukaridaki gercek
# sabitlerden gelir (test_strategy_info_* bunu zorlar).
STRATEGY_INFO: dict[str, dict] = {
    "S1_TSMOM": {
        "name": "Trend Takibi (TSMOM)",
        "how": ("Fiyat uzun vadeli ortalamasının üstündeyse ve son günlerde "
                "de yükselmişse, yokuşun devam edeceğine oynar; düşüşte "
                "aynısının tersini yapar. Güçlü hareketlerin bir süre daha "
                "sürme eğilimi olduğu fikrine dayanır. Yön dönene kadar "
                "bekler, erken inmez."),
        "params": {
            "giris": (f"4H kapanış EMA{TSMOM_EMA_N} üstünde (LONG) / altında "
                      f"(SHORT) VE son {TSMOM_MOM_BARS}×4H momentum aynı "
                      "yönde"),
            "stop": f"{TREND_STOP_ATR:g} × ATR(4H)",
            "hedef": (f"{TREND_TP_ATR:g} × ATR(4H) — plan RR "
                      f"{TREND_TP_ATR / TREND_STOP_ATR:g}"),
            "zaman_asimi": _saat(TREND_TIMEOUT),
            "tavan": f"{MAX_OPEN['S1_TSMOM']} açık pozisyon",
            "filtreler": "rejim/hacim filtresi yok; funding kullanılmaz",
        },
    },
    "S2_DONCHIAN": {
        "name": "Kırılım (Donchian)",
        "how": ("Fiyat, son birkaç günün en yükseğini yukarı kırarsa alır; "
                "en düşüğünü aşağı kırarsa satar. Yeni zirvenin veya yeni "
                "dibin çoğu zaman devamı geldiği fikrine dayanır. Kırılım "
                "yoksa hiçbir şey yapmaz."),
        "params": {
            "giris": (f"Kapanış {DONCHIAN_N}×4H Donchian kanalının dışına "
                      "çıkınca — kenar tetik: önceki kapanış içeride"),
            "stop": f"{TREND_STOP_ATR:g} × ATR(4H)",
            "hedef": (f"{TREND_TP_ATR:g} × ATR(4H) — plan RR "
                      f"{TREND_TP_ATR / TREND_STOP_ATR:g}"),
            "zaman_asimi": _saat(TREND_TIMEOUT),
            "tavan": f"{MAX_OPEN['S2_DONCHIAN']} açık pozisyon",
            "filtreler": "rejim/hacim filtresi yok; funding kullanılmaz",
        },
    },
    "S3_MEANREV": {
        "name": "Ortalamaya Dönüş",
        "how": ("Piyasa yatayken fiyat ortalamasından aşırı uzaklaşırsa, "
                "gerilen lastik gibi geri çekileceğine oynar: aşırı düşene "
                "alıcı, aşırı yükselene satıcı olur. Yalnızca trend yokken "
                "çalışır; trend varken bu oyun tehlikelidir, o yüzden kapısı "
                "kapalıdır."),
        "params": {
            "giris": (f"4H ADX < {S3_ADX_MAX:g} (yatay rejim) VE fiyat "
                      f"{S3_SMA_N} bar ortalamasından {S3_SIGMA:g}σ uzakta"),
            "stop": f"{S3_STOP_ATR:g} × ATR(15dk)",
            "hedef": f"{S3_SMA_N} bar ortalamasına dönüş",
            "zaman_asimi": _saat(FAST_TIMEOUT),
            "tavan": f"{MAX_OPEN['S3_MEANREV']} açık pozisyon",
            "filtreler": (f"rejim kapısı: 4H ADX < {S3_ADX_MAX:g}; "
                          "hacim/funding filtresi yok"),
        },
    },
    "S4_CARRY": {
        "name": "Fonlama Taşıması",
        "how": ("Vadeli piyasada bir tarafa aşırı kalabalık binmişse — "
                "fonlama ücreti çok yükselmişse — kalabalığın tersine geçer. "
                "Herkesin aynı fikirde olduğu an, çoğu zaman dönüşün yakın "
                "olduğu andır. Ücret normalken hiçbir şey yapmaz."),
        "params": {
            "giris": (f"Yıllıklandırılmış |funding| > %{S4_ANN_FUNDING * 100:g} "
                      "— kalabalığın tersi yönde"),
            "stop": f"{S4_RISK_ATR:g} × ATR(4H)",
            "hedef": f"risk × {S4_TP_RISK:g} — plan RR {S4_TP_RISK:g}",
            "zaman_asimi": _saat(TREND_TIMEOUT),
            "tavan": f"{MAX_OPEN['S4_CARRY']} açık pozisyon",
            "filtreler": (f"funding kapısı: yıllık |funding| > "
                          f"%{S4_ANN_FUNDING * 100:g}; rejim/hacim filtresi yok"),
        },
    },
    "S7_WYCKOFF": {
        "name": "Wyckoff Spring+Test",
        "how": ("Fiyat bilinen bir dibi yüksek işlem hacmiyle kırıp hemen "
                "üstüne geri dönerse buna kapan (spring) der. Birkaç mum "
                "sonra fiyat aynı dibe bir kez daha yaklaşır ama bu sefer "
                "hacim kurumuşsa, satmak isteyen kalmadığını varsayar ve "
                "alır. S6 ile aynı olaya bakar ama tam ters filtreyle: S6 "
                "teyitte hacim patlaması ister, S7 hacim kuruması ister."),
        "params": {
            "giris": (f"Spring: son {S7_SWING_N} barın dibi kırılır (hacim ≥ "
                      f"{S7_VOL_SPRING:g} × SMA20) ve kapanış üstüne döner; "
                      f"Test: sonraki {S7_TEST_WINDOW} bar içinde dibe ≤ "
                      f"{S7_ATR_PROX:g}×ATR yaklaşan, spring dibinin üstünde "
                      f"kalan, hacmi ≤ {S7_VOL_TEST:g} × SMA20 olan mum — "
                      "giriş test mumunun kapanışında (ayna kurgu SHORT)"),
            "stop": f"spring dibinin {S7_ATR_PROX:g} × ATR(15dk) altı",
            "hedef": f"risk × {S7_TP_RISK:g} — plan RR {S7_TP_RISK:g}",
            "zaman_asimi": _saat(FAST_TIMEOUT),
            "tavan": f"{MAX_OPEN['S7_WYCKOFF']} açık pozisyon",
            "filtreler": (f"hacim kapısı çift yönlü: spring ≥ "
                          f"{S7_VOL_SPRING:g}×, test ≤ {S7_VOL_TEST:g}× "
                          "SMA20; rejim/funding filtresi yok"),
        },
    },
    "S6_SWEEP": {
        "name": "Süpürme Dönüşü",
        "how": ("Fiyat bilinen bir tepeyi ya da dibi iğneyle aşıp hemen geri "
                "dönerse, bunun stopları toplamak için yapılmış bir hamle "
                "olduğunu varsayar ve dönüş yönüne girer. Teyit için o mumda "
                "işlem hacminin de sıçramış olmasını ister."),
        "params": {
            "giris": (f"Fitil son {S6_SWING_N} barın ekstremumunu aşar ama "
                      f"kapanış gerisinde kalır VE hacim ≥ {S6_VOL_MULT:g} × "
                      "SMA20"),
            "stop": f"süpürme fitilinin {S6_WICK_ATR:g} × ATR(15dk) ötesi",
            "hedef": f"risk × {S6_TP_RISK:g} — plan RR {S6_TP_RISK:g}",
            "zaman_asimi": _saat(FAST_TIMEOUT),
            "tavan": f"{MAX_OPEN['S6_SWEEP']} açık pozisyon",
            "filtreler": (f"hacim kapısı: tetik mumu ≥ {S6_VOL_MULT:g} × "
                          "SMA20; rejim/funding filtresi yok"),
        },
    },
}
for _k in STRATEGY_INFO:
    STRATEGY_INFO[_k]["honesty"] = _honesty(_k)


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
            if strat in RETIRED:
                continue        # emekli: hukum verildi, yeni sinyal yok
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

        # S1 TSMOM: 4H kapanis EMA ustunde VE momentum ayni yonde
        # (sabitler yukarida; UI aciklamasi da AYNI sabitlerden turetilir)
        if atr_h and len(h_close) >= 120:
            ema = _ema(h_close, TSMOM_EMA_N)
            if ema is not None and len(h_close) >= TSMOM_MOM_BARS + 1:
                mom = h_close[-1] - h_close[-(TSMOM_MOM_BARS + 1)]
                if h_close[-1] > ema and mom > 0:
                    out.append(("S1_TSMOM",
                                ("LONG", entry - TREND_STOP_ATR * atr_h,
                                 entry + TREND_TP_ATR * atr_h, TREND_TIMEOUT)))
                elif h_close[-1] < ema and mom < 0:
                    out.append(("S1_TSMOM",
                                ("SHORT", entry + TREND_STOP_ATR * atr_h,
                                 entry - TREND_TP_ATR * atr_h, TREND_TIMEOUT)))

        # S2 DONCHIAN: kanal kirilimi (kenar tetik: onceki bar icerde)
        if atr_h and len(h_high) >= DONCHIAN_N + 1 and len(l_close) >= 2:
            dh, dl = max(h_high[-DONCHIAN_N:]), min(h_low[-DONCHIAN_N:])
            if l_close[-2] <= dh < l_close[-1]:
                out.append(("S2_DONCHIAN",
                            ("LONG", entry - TREND_STOP_ATR * atr_h,
                             entry + TREND_TP_ATR * atr_h, TREND_TIMEOUT)))
            elif l_close[-2] >= dl > l_close[-1]:
                out.append(("S2_DONCHIAN",
                            ("SHORT", entry + TREND_STOP_ATR * atr_h,
                             entry - TREND_TP_ATR * atr_h, TREND_TIMEOUT)))

        # S3 MEANREV: yalniz yatay rejimde sigma-sapmayi sat/al
        if atr_l and len(l_close) >= S3_SMA_N + 1:
            adx = _adx(h_high, h_low, h_close) if h_ok else None
            if adx is not None and adx < S3_ADX_MAX:
                sma = sum(l_close[-S3_SMA_N:]) / S3_SMA_N
                var = sum((x - sma) ** 2
                          for x in l_close[-S3_SMA_N:]) / S3_SMA_N
                sd = var ** 0.5
                if sd > 0:
                    if entry < sma - S3_SIGMA * sd:
                        out.append(("S3_MEANREV",
                                    ("LONG", entry - S3_STOP_ATR * atr_l,
                                     sma, FAST_TIMEOUT)))
                    elif entry > sma + S3_SIGMA * sd:
                        out.append(("S3_MEANREV",
                                    ("SHORT", entry + S3_STOP_ATR * atr_l,
                                     sma, FAST_TIMEOUT)))

        # S4 CARRY: yilliklandirilmis |funding| esigi -> kalabaligin tersi
        if atr_h and funding is not None:
            ann = funding * 3 * 365
            if ann > S4_ANN_FUNDING:
                risk = S4_RISK_ATR * atr_h
                out.append(("S4_CARRY",
                            ("SHORT", entry + risk,
                             entry - S4_TP_RISK * risk, TREND_TIMEOUT)))
            elif ann < -S4_ANN_FUNDING:
                risk = S4_RISK_ATR * atr_h
                out.append(("S4_CARRY",
                            ("LONG", entry - risk,
                             entry + S4_TP_RISK * risk, TREND_TIMEOUT)))

        # S6 SWEEP: swing ekstremumu asilir ama kapanis gerisinde + hacim
        if atr_l and len(l_close) >= S6_SWING_N + 4:
            sw_h = max(l_high[-(S6_SWING_N + 2):-2])
            sw_l = min(l_low[-(S6_SWING_N + 2):-2])
            vol_sma = sum(l_vol[-21:-1]) / 20
            c = ltf.candles[-1]
            vol_ok = vol_sma > 0 and c.volume >= S6_VOL_MULT * vol_sma
            if c.high > sw_h and c.close < sw_h and vol_ok:
                # stop, ESKI swing degil supurme FITILININ otesinde durur:
                # fitilin siradan retesti pozisyonu dusurmemeli
                stop = c.high + S6_WICK_ATR * atr_l
                risk = stop - entry
                if risk > 0:
                    out.append(("S6_SWEEP",
                                ("SHORT", stop,
                                 entry - S6_TP_RISK * risk, FAST_TIMEOUT)))
            elif c.low < sw_l and c.close > sw_l and vol_ok:
                stop = c.low - S6_WICK_ATR * atr_l
                risk = entry - stop
                if risk > 0:
                    out.append(("S6_SWEEP",
                                ("LONG", stop,
                                 entry + S6_TP_RISK * risk, FAST_TIMEOUT)))

        # S7 WYCKOFF SPRING+TEST (tasarim 8eecb5a, BIREBIR):
        # Faz 1 (spring): low < swing_low VE hacim >= 1.5xSMA20 VE kapanis
        #   swing dibinin ustune doner. Faz 2 (test): sonraki 1-6 barda
        #   low <= swing_low + 0.25xATR14 AMA low > spring_low VE hacim
        #   <= 0.7xSMA20. Giris test kapanisinda; stop spring_low-0.25xATR;
        #   TP 2R; 96 bar zaman asimi. Ayna kurgu SHORT (upthrust+test).
        # Gecersizlik: arada low <= spring_low -> iptal (test penceresi 6
        #   bar; disarida kalan spring zaten taranmaz). S6'dan yapisal
        #   fark: teyitte YUKSEK degil DUSUK hacim aranir (ters filtre).
        if atr_l and len(l_close) >= S7_SWING_N + S7_TEST_WINDOW + 2:
            n_ = len(l_close)
            cur = n_ - 1                       # aday TEST mumu = son mum

            def _vol_sma20(idx: int) -> float | None:
                if idx < 20:
                    return None
                s = sum(l_vol[idx - 20:idx]) / 20
                return s if s > 0 else None

            cur_sma = _vol_sma20(cur)
            if cur_sma and l_vol[cur] <= S7_VOL_TEST * cur_sma:
                for back in range(1, S7_TEST_WINDOW + 1):
                    j = cur - back             # aday SPRING/UPTHRUST mumu
                    if j < S7_SWING_N:
                        break
                    j_sma = _vol_sma20(j)
                    if not j_sma or l_vol[j] < S7_VOL_SPRING * j_sma:
                        continue
                    sw_low = min(l_low[j - S7_SWING_N:j])
                    sw_high = max(l_high[j - S7_SWING_N:j])
                    if l_low[j] < sw_low and l_close[j] > sw_low:
                        spring_low = l_low[j]
                        if any(l_low[k] <= spring_low
                               for k in range(j + 1, cur)):
                            continue           # gecersizlik: dibe geri donus
                        if (l_low[cur] <= sw_low + S7_ATR_PROX * atr_l
                                and l_low[cur] > spring_low):
                            stop = spring_low - S7_ATR_PROX * atr_l
                            risk = entry - stop
                            if risk > 0:
                                out.append(("S7_WYCKOFF",
                                            ("LONG", stop,
                                             entry + S7_TP_RISK * risk,
                                             FAST_TIMEOUT)))
                                break
                    elif l_high[j] > sw_high and l_close[j] < sw_high:
                        up_high = l_high[j]
                        if any(l_high[k] >= up_high
                               for k in range(j + 1, cur)):
                            continue           # gecersizlik: tepeye donus
                        if (l_high[cur] >= sw_high - S7_ATR_PROX * atr_l
                                and l_high[cur] < up_high):
                            stop = up_high + S7_ATR_PROX * atr_l
                            risk = stop - entry
                            if risk > 0:
                                out.append(("S7_WYCKOFF",
                                            ("SHORT", stop,
                                             entry - S7_TP_RISK * risk,
                                             FAST_TIMEOUT)))
                                break
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
                # v1.2 detay penceresi: belirsiz sayisi + tutus medyani
                "ambiguous": sum(1 for r in closed if r.get("ambiguous")),
                "hold_bars_median": measurement.median_or_none(
                    [float(r["hold_bars"]) for r in closed
                     if r.get("hold_bars") is not None]),
            }
            if strat in RETIRED:
                out["strategies"][strat]["retired_utc"] = RETIRED[strat]
            # --- on-kayitli dogrulama penceresi muhasebesi (varsa) ---
            vstart = VALIDATION_WINDOWS.get(strat)
            if vstart:
                vclosed = [r for r in closed
                           if (r.get("created_utc") or "") >= vstart]
                vdecided = [r for r in vclosed
                            if r["outcome"] in ("WIN", "LOSS")]
                vclusters: dict[str, list[float]] = {}
                vnet = 0.0
                for r in vclosed:
                    n = self._net_r(r)
                    if n is not None:
                        vnet += n
                        vclusters.setdefault(
                            r["cluster_id"] or "?", []).append(n)
                vboot = measurement.cluster_bootstrap(vclusters)
                out["strategies"][strat]["validation"] = {
                    "start_utc": vstart,
                    "decided": len(vdecided),
                    "net_r": round(vnet, 2),
                    "clusters": len(vclusters),
                    "target_clusters": FAZ1_TARGET,
                    "ci": ([vboot["ci_low"], vboot["ci_high"]]
                           if vboot and vboot.get("ci_low") is not None
                           else None),
                    "note": ("on-kayitli walk-forward dogrulama; hukum "
                             "YALNIZ bu kohorttan (ilan oncesi kayitlar "
                             "karisamaz)"),
                }
        return out

    def strategy_info(self) -> dict:
        """Detay penceresinin tek bilgi kaynagi (aciklama + parametreler)."""
        return STRATEGY_INFO

    def recent(self, limit: int = 120) -> list[dict]:
        rows = self._db.query(
            "SELECT * FROM challenger_signals ORDER BY id DESC LIMIT ?",
            (limit,))
        # v1.2: net R sunucuda hesaplanir (tek kaynak _net_r; JS kopyasi yok)
        for r in rows:
            n = self._net_r(r) if r.get("r_multiple") is not None else None
            r["net_r"] = round(n, 2) if n is not None else None
        return rows
