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
from datetime import datetime, timedelta, timezone

from app.logging_setup import kv
from app.services import measurement
from app.services.signal_tracker import FUNDING_8H, STOP_SLIP, TAKER_FEE

log = logging.getLogger("challengers")

STRATEGIES = ("S1_TSMOM", "S2_DONCHIAN", "S3_MEANREV", "S4_CARRY", "S6_SWEEP",
              "S7_WYCKOFF", "S8_FUNDSQUEEZE", "S9_GECE", "S10_52WHIGH",
              "S11_SQUEEZE", "S12_RELVOL")
# S7: 2026-08-06, tetik = S6 sinavini doldurdu.
# S8: 2026-08-13, funding sikisma teyidi (on-kayit docs/ideas.md). Momentum
# ailesi (S5 kesitsel + TSM) 90-gun backtest'te kenar gostermedi -> rafta;
# funding-yonu S4'te var ama S8 asiri esik + fiyat teyidiyle ayrisir.
# S9: 2026-08-13, gece penceresi (arastirma raporu #1; on-kayit ideas.md).
# Takvim-tetikli ILK aday: fiyat kalibina bakmaz, gunun saatine bakar.
# S10: 2026-08-16, 52w zirve yakinligi (backtest BELIRSIZ-pozitif: 750 gunde
# net +13.32R, E_net +0.049, CI [-0.137,+0.267]; on-kayit ideas.md).
# Haftalik kadans - hukum yavas gelir (~1 yil), maliyeti dusuk.
# S11: 2026-08-17, oynaklik-sikismasi kirilimi (perakende arastirmasi #1;
# on-kayit ideas.md). S2'den yapisal fark: SIKISMA ONKOSULU tetikler.
# S12: 2026-08-17, goreli-hacim kapili seans kirilimi (arastirma #2,
# Zarattini uyarlamasi; on-kayit ideas.md). Yeni oge: hacim KAPISI.
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
            "S7_WYCKOFF": 15,
            # S8: TREND_TIMEOUT sinifi (S4 kardesi) AMA asiri esik + fiyat
            # teyidi nadir tetiklenir -> footprint kucuk tutuldu (15,
            # varsayilan sinif); kanitlanmamis yeni aday. Yeni slot ICAT
            # degil: S8 yeni bir aday (S7 gibi kendi kotasiyla girer).
            "S8_FUNDSQUEEZE": 15,
            # S9: tek parite (BTCUSDT), gunde tek 2 saatlik islem -> tavan 1.
            "S9_GECE": 1,
            # S10: haftalik sepet = evrenin ust %10'u (~15); 7 gunluk tutus
            # boyunca tek sepet acik -> tavan 15 (varsayilan sinif).
            "S10_52WHIGH": 15,
            # S11/S12: kanitlanmamis yeni adaylar, varsayilan sinif (15).
            # Yeni slot ICAT degil: her yeni aday kendi kotasiyla girer
            # (S7/S8 emsali).
            "S11_SQUEEZE": 15, "S12_RELVOL": 15}
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
# S8 FUNDSQUEEZE (2026-08-13): funding SIKISMA teyidi. S4'ten farki iki
# noktada: (a) DAHA DERIN esik (yalniz asiri kalabalik), (b) FIYAT TEYIDI
# (squeeze basladi mi) sart. Yon S4 ile ortusur (funding-yonu dogasi geregi);
# ayrisma giris zamanlamasindan gelir. On-kayit: docs/ideas.md 2026-08-13.
S8_ANN_FUNDING = 0.60    # S8: yillik |funding| esigi (S4'in %30'undan DERIN)
S8_RISK_ATR = 2.0        # S8: stop (ATR-4H kati)
S8_TP_RISK = 2.0         # S8: hedef (risk kati)
# S9 GECE (2026-08-13): NY kapanisi sonrasi / Asya oncesi gece penceresi.
# Kaynak: Vojtko-Javorska SSRN 4581124 + bagimsiz replikasyonlar (rapor).
# Cikis ZAMANLADIR (stop yalniz felaket freni; hedef sentetik-erisilemez).
S9_PAIR = "BTCUSDT"      # S9: v1 yalniz BTC (genisletme AYRI on-kayit ister)
S9_HOUR_UTC = 21         # S9: giris penceresi 21:00-21:59 UTC'deki ilk tarama
S9_HOLD_BARS = 8         # S9: 8 kapanmis 15dk bar = 2s00-2s15dk tutus
                         #     (giris barina gore cikis fiilen 23:15-00:00 UTC)
S9_STOP_ATR = 2.0        # S9: felaket stopu (15dk ATR kati) - R paydasi
S9_TP_RISK = 100.0       # S9: SENTETIK erisilemez hedef (cikis zamanla)
# S2/P4 GOLGE-KOHORT (2026-08-16): S2 kirilim kayitlarina dogumda dOI(24s)
# etiketi dusulur (kontrat adedi). SALT OLCUM - hicbir karari degistirmez.
# Backtest bulgusu: artisli kohort +22.32R vs artissiz -170.88R (BELIRSIZ).
S2_OI_RISE = 0.05        # kohort esigi: dOI(24s) >= +%5 -> "artisli"
# S10 52W-HIGH (2026-08-16, on-kayit ideas.md): zirveye yakinlik capasi.
S10_ANCHOR_D = 365       # S10: zirve penceresi (gun)
S10_MIN_HIST = 90        # S10: asgari gunluk gecmis
S10_PROX = 0.90          # S10: yakinlik tabani (kapanis/zirve)
S10_DECILE = 0.10        # S10: kesit ust dilimi
S10_STOP_ATR = 2.0       # S10: stop (GUNLUK ATR kati) - R paydasi
S10_TIMEOUT = 672        # S10: 7 gun x 96 bar - asil cikis ZAMANDIR
S10_TP_RISK = 100.0      # S10: SENTETIK erisilemez hedef (S9 deseni)
# S11 SQUEEZE (2026-08-17, on-kayit ideas.md): oynaklik-sikismasi kirilimi
# (TTM/LazyBear ailesi). Sikisma = BB tamamen KC icinde; >=6 bar surup
# COZULUNCE kirilim yonune girilir. S2'den fark: ham kanal kirilimi degil,
# sikisma ONKOSULU tetikler (patlamayi sessizlik dogurur).
S11_BB_N = 20            # S11: BB/KC/momentum penceresi (4H bar)
S11_BB_K = 2.0           # S11: Bollinger sapma kati (populasyon sigma)
S11_KC_MULT = 1.5        # S11: Keltner genisligi (SMA20(TrueRange) kati)
S11_MIN_SQUEEZE = 6      # S11: asgari sikisma suresi (ardisik 4H bar)
S11_TP_RISK = 2.0        # S11: hedef (risk kati)
# S12 RELVOL (2026-08-17, on-kayit ideas.md): seans kirilimi + GORELI-HACIM
# kapisi (Zarattini-Aziz uyarlamasi; hakemli yeni oge hacim kapisidir).
# Acilis araligi = gunun ILK 4H mumu (00:00-04:00 UTC); cikis GUN SONU.
S12_RELVOL_MIN = 2.0     # S12: acilis hacmi >= 2 x onceki 20 gun ortalamasi
S12_LOOKBACK_D = 20      # S12: goreli-hacim ortalama penceresi (gun)
S12_TP_RISK = 100.0      # S12: SENTETIK erisilemez hedef (cikis gun sonu)


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
    "S8_FUNDSQUEEZE": {
        "name": "Fonlama Sıkışması",
        "how": ("Vadeli piyasada bir tarafa AŞIRI kalabalık binmişse "
                "(fonlama ücreti çok uçlanmışsa) VE fiyat ters yöne dönmeye "
                "başlamışsa, sıkışan tarafın zorla kapatılacağına oynar. "
                "S4 ile aynı yöne bakar ama iki farkla: S4 ücret eşiği "
                "aşılınca hemen girer; S8 hem daha uç bir eşik arar hem de "
                "önce fiyatın dönüşü teyit etmesini bekler — daha seyrek "
                "ama daha yüksek güvenli giriş."),
        "params": {
            "giris": (f"Yıllıklandırılmış |funding| > %{S8_ANN_FUNDING * 100:g} "
                      "(S4'ten derin) VE son 15dk kapanış ters yönde teyit "
                      "(negatif→yukarı dönüş LONG, pozitif→aşağı dönüş SHORT)"),
            "stop": f"{S8_RISK_ATR:g} × ATR(4H)",
            "hedef": f"risk × {S8_TP_RISK:g} — plan RR {S8_TP_RISK:g}",
            "zaman_asimi": _saat(TREND_TIMEOUT),
            "tavan": f"{MAX_OPEN['S8_FUNDSQUEEZE']} açık pozisyon",
            "filtreler": (f"funding kapısı: yıllık |funding| > "
                          f"%{S8_ANN_FUNDING * 100:g} + fiyat teyidi; "
                          "rejim/hacim filtresi yok"),
        },
    },
    "S9_GECE": {
        "name": "Gece Penceresi",
        "how": ("Fiyat grafiğine hiç bakmaz; saate bakar. New York borsası "
                "kapandıktan sonra, Asya güne başlamadan önceki gece "
                "penceresinde (21:00'den itibaren) Bitcoin tarihsel olarak "
                "günün en güçlü ortalama getirisini vermiştir — her akşam "
                "21:00–21:59 UTC'deki ilk taramada girer, girişten ~2 saat "
                "sonra (fiilen 23:15–00:00 UTC arasında) çıkar. Görevi bu "
                "takvim etkisinin hâlâ yaşayıp yaşamadığını ucuza ve hızla "
                "ölçmektir."),
        "params": {
            "giris": (f"Yalnız {S9_PAIR}; {S9_HOUR_UTC}:00–"
                      f"{S9_HOUR_UTC}:59 UTC penceresindeki ilk taramada "
                      "kapanıştan LONG — fiyat/hacim koşulu yok"),
            "stop": (f"{S9_STOP_ATR:g} × ATR(15dk) — yalnız felaket freni; "
                     "R bu mesafeyle tanımlanır"),
            "hedef": (f"risk × {S9_TP_RISK:g} (sentetik, erişilemez) — "
                      "çıkış hedefle değil SÜREYLE olur"),
            "zaman_asimi": _saat(S9_HOLD_BARS),
            "tavan": f"{MAX_OPEN['S9_GECE']} açık pozisyon",
            "filtreler": "yok — takvim tetikli; rejim/hacim/funding bakılmaz",
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
    "S10_52WHIGH": {
        "name": "52 Hafta Zirvesi",
        "how": ("Yatırımcılar bir yılın zirvesini çapa gibi kullanır: fiyat "
                "zirveye yakınken iyi habere eksik tepki verilir ve yükseliş "
                "sürüklenerek devam eder. Her Pazartesi tüm evreni bir yıllık "
                "zirvesine yakınlığa göre sıralar; hem en üst %10'da hem de "
                "zirvesinin %90'ının üstünde olanları alır, bir hafta tutup "
                "çıkar. Haftalık çalışır — hüküm yavaş ama masrafı düşük."),
        "params": {
            "giris": (f"Pazartesi 00:00 UTC kararı: yakınlık = son günlük "
                      f"kapanış ÷ son {S10_ANCHOR_D} günün en yüksek kapanışı "
                      f"(yeni paritede tüm geçmiş, en az {S10_MIN_HIST} gün); "
                      f"kesit üst %{S10_DECILE * 100:g} VE yakınlık ≥ "
                      f"{S10_PROX:g} → LONG"),
            "stop": (f"{S10_STOP_ATR:g} × ATR(14, günlük) — "
                     "R bu mesafeyle tanımlanır"),
            "hedef": (f"risk × {S10_TP_RISK:g} (sentetik, erişilemez) — "
                      "çıkış hedefle değil SÜREYLE olur"),
            "zaman_asimi": _saat(S10_TIMEOUT),
            "tavan": f"{MAX_OPEN['S10_52WHIGH']} açık pozisyon",
            "filtreler": ("yön filtresi: yalnız LONG (kripto kanıtı uzun "
                          "bacakta); rejim/hacim/funding bakılmaz"),
        },
    },
    "S11_SQUEEZE": {
        "name": "Sıkışma Kırılımı",
        "how": ("Fiyat uzun süre dar bir bantta sıkışıp sakinleştikten "
                "sonra genelde büyük bir hareket gelir. Bu motor sıkışmayı "
                "sayar: oynaklık bandı (Bollinger) daha geniş kanalın "
                "(Keltner) içine girip en az 6 tane 4 saatlik mum orada "
                "kalırsa 'sessizlik' var demektir. Sessizlik çözülüp fiyat "
                "sıkışma aralığının dışına taşarsa, taşma yönüne girer. "
                "S2'den farkı: ham kırılımı değil, önce sessizlik ön "
                "koşulunu arar — patlamayı sessizlik doğurur fikri."),
        "params": {
            "giris": (f"4H: BB({S11_BB_N},{S11_BB_K:g}σ) en az "
                      f"{S11_MIN_SQUEEZE} bar KC({S11_BB_N},"
                      f"{S11_KC_MULT:g}×TR) içinde kaldıktan sonra çözülür "
                      "VE 4H kapanış sıkışma aralığının dışında VE momentum "
                      "aynı yönde — giriş taramadaki 15dk kapanışından"),
            "stop": "sıkışma aralığının karşı ucu (LONG: alt, SHORT: üst)",
            "hedef": (f"risk × {S11_TP_RISK:g} — plan RR "
                      f"{S11_TP_RISK:g}"),
            "zaman_asimi": _saat(TREND_TIMEOUT),
            "tavan": f"{MAX_OPEN['S11_SQUEEZE']} açık pozisyon",
            "filtreler": ("sıkışma ön koşulu (oynaklık kapısı) + momentum "
                          "yön teyidi; rejim/hacim/funding bakılmaz"),
        },
    },
    "S12_RELVOL": {
        "name": "Hacim Kapılı Kırılım",
        "how": ("Günün ilk 4 saatlik mumunu (00:00–04:00 UTC) açılış "
                "aralığı sayar. O mumda işlem hacmi olağandışı yüksekse — "
                "son 20 günün açılış ortalamasının en az 2 katı — gün "
                "içinde fiyat bu aralığın dışına çıktığında kırılım yönüne "
                "girer ve gün sonunda çıkar. Dayandığı bulgu: kırılım "
                "ancak olağandışı katılım (hacim) varsa devam etme "
                "eğiliminde — asıl yenilik hacim kapısıdır."),
        "params": {
            "giris": (f"Açılış aralığı = günün ilk 4H mumu (00:00–04:00 "
                      f"UTC); hacmi önceki {S12_LOOKBACK_D} günün açılış "
                      f"ortalamasının ≥ {S12_RELVOL_MIN:g} katıysa gün "
                      "içinde 15dk kapanış aralığın dışına çıkınca — kenar "
                      "tetik, günde yön başına tek giriş"),
            "stop": "açılış aralığının karşı ucu",
            "hedef": (f"risk × {S12_TP_RISK:g} (sentetik, erişilemez) — "
                      "çıkış hedefle değil GÜN SONUYLA olur"),
            "zaman_asimi": ("gün sonu 00:00 UTC — kalan bar sayısı girişte "
                            "hesaplanır"),
            "tavan": f"{MAX_OPEN['S12_RELVOL']} açık pozisyon",
            "filtreler": (f"hacim kapısı: açılış hacmi ≥ "
                          f"{S12_RELVOL_MIN:g} × son {S12_LOOKBACK_D} gün "
                          "ort.; rejim/funding bakılmaz"),
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


def weekly_52w_selection(daily: dict[str, list]) -> list[tuple]:
    """S10 haftalik secimi - SAF fonksiyon (on-kayit 2026-08-16, birebir):
    yakinlik = son KAPANMIS gunluk kapanis / son 365 gunun en yuksek kapanisi
    (yeni paritede tum gecmis, en az 90 gun). Secim: kesit ust %10 VE
    yakinlik >= 0.90. Donen: [(yakinlik, sembol, giris, stop, son_ts)].

    daily: {sembol: [[ts,o,h,l,c], ...]} artan, yalniz kapanmis gunler.
    """
    # ayni-gun sepeti: karar gunu = kesitteki EN TAZE kapanmis gun; bayat
    # (kline'i geride kalmis/duraklamis) pariteler sepete GIREMEZ - aksi
    # halde gunler oncesinin fiyatiyla geriye donuk giris yazilir
    fresh_ts = max((bars[-1][0] for bars in daily.values() if bars),
                   default=None)
    if fresh_ts is None:
        return []
    cross: list[tuple] = []
    for sym, bars in daily.items():
        if not bars or len(bars) < S10_MIN_HIST:
            continue
        if bars[-1][0] != fresh_ts:
            continue                    # bayat parite: karar gunu farkli
        closes = [b[4] for b in bars]
        highs = [b[2] for b in bars]
        lows = [b[3] for b in bars]
        anchor = max(closes[-S10_ANCHOR_D:])
        if anchor <= 0:
            continue
        entry = closes[-1]
        atr_d = _atr(highs, lows, closes)
        if atr_d is None or atr_d <= 0:
            continue
        stop = entry - S10_STOP_ATR * atr_d
        if entry - stop <= 0:
            continue
        cross.append((entry / anchor, sym, entry, stop, bars[-1][0]))
    if not cross:
        return []
    cross.sort(reverse=True)
    k = max(1, round(S10_DECILE * len(cross)))
    return [c for c in cross[:k] if c[0] >= S10_PROX]


def _linreg_last(vals: list[float]) -> float:
    """Dogrusal regresyon dogrusunun SON noktadaki degeri (S11 momentum)."""
    n = len(vals)
    xm = (n - 1) / 2.0
    ym = sum(vals) / n
    den = sum((i - xm) ** 2 for i in range(n))
    if den <= 0:
        return ym
    slope = sum((i - xm) * (v - ym) for i, v in enumerate(vals)) / den
    return ym + slope * ((n - 1) - xm)


def squeeze_run(high: list[float], low: list[float],
                close: list[float]) -> tuple[float, float] | None:
    """S11: son kapanmis 4H barda ATESLEME var mi? (on-kayit 2026-08-17)

    Sikisma ACIK (bar i): S11_BB_K x sigma20(kapanis) < S11_KC_MULT x
    SMA20(TrueRange) - orta bant iki kanalda da ayni oldugundan bu,
    'BB tamamen KC icinde' kosulunun birebir esdegeridir.
    ATESLEME: son bar KAPALI, onceki ACIK, biten ACIK serisi >=
    S11_MIN_SQUEEZE. Donen: (aralik_yuksek, aralik_dusuk) = ACIK serisi
    barlarinin ekstremumlari; kosul yoksa None."""
    n = len(close)
    if n < 2 * S11_BB_N + 1:
        return None
    trs = [max(high[i] - low[i], abs(high[i] - close[i - 1]),
               abs(low[i] - close[i - 1])) for i in range(1, n)]

    def _on(i: int) -> bool:
        w = close[i - S11_BB_N + 1:i + 1]
        sma = sum(w) / S11_BB_N
        sd = (sum((x - sma) ** 2 for x in w) / S11_BB_N) ** 0.5
        atr_sma = sum(trs[i - S11_BB_N:i]) / S11_BB_N
        return S11_BB_K * sd < S11_KC_MULT * atr_sma

    last = n - 1
    if _on(last) or not _on(last - 1):
        return None
    run_start = last - 1
    while run_start - 1 >= S11_BB_N and _on(run_start - 1):
        run_start -= 1
    if last - run_start < S11_MIN_SQUEEZE:
        return None
    return (max(high[run_start:last]), min(low[run_start:last]))


def squeeze_momentum(high: list[float], low: list[float],
                     close: list[float]) -> float | None:
    """S11 momentum (LazyBear birebir): d = kapanis - ort((HH20+LL20)/2,
    SMA20(kapanis)) serisinin son 20 barina dogrusal regresyon, son nokta."""
    n = len(close)
    if n < 2 * S11_BB_N:
        return None
    deltas = []
    for j in range(n - S11_BB_N, n):
        hh = max(high[j - S11_BB_N + 1:j + 1])
        ll = min(low[j - S11_BB_N + 1:j + 1])
        sma = sum(close[j - S11_BB_N + 1:j + 1]) / S11_BB_N
        deltas.append(close[j] - ((hh + ll) / 2 + sma) / 2)
    return _linreg_last(deltas)


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
        try:
            # P4 golge-kohort (2026-08-16): S2 kirilim kayitlarina dogumda
            # dusulen dOI(24s) etiketi. SALT metadata - karar okumaz.
            self._db.execute("ALTER TABLE challenger_signals ADD COLUMN "
                             "doi_24h REAL")
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
            if strat == "S12_RELVOL":
                # kume + dedup = TAKVIM GUNU (on-kayit: gunde yon basina
                # tek giris; 4H kovasi gunu 5 parcaya bolerdi)
                cid = f"{strat}:{direction[0]}D{last.ts // 86_400_000}"
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

    # ------------------------------------------ P4 golge-kohort (salt olcum)
    def untagged_s2(self, pair: str, max_age_sec: int = 600) -> int | None:
        """YALNIZ bu taramada dogmus (taze), etiket bekleyen S2 kaydi.

        Yas siniri sart (inceleme 2026-08-16): deploy oncesi eski kayitlar
        veya dogum aninda OI'si alinamayanlar SONRADAN etiketlenirse kohort
        'dogum ani dOI'si' olmaktan cikar. Yaslananlar etiketsiz kalir ve
        durustce sayilir."""
        cutoff = (datetime.now(timezone.utc)
                  - timedelta(seconds=max_age_sec)).strftime(
                      "%Y-%m-%dT%H:%M:%SZ")
        r = self._db.query_one(
            "SELECT id FROM challenger_signals WHERE strategy='S2_DONCHIAN' "
            "AND pair=? AND status='OPEN' AND doi_24h IS NULL "
            "AND created_utc >= ? ORDER BY id DESC LIMIT 1", (pair, cutoff))
        return r["id"] if r else None

    def set_doi(self, row_id: int, doi: float) -> None:
        """dOI(24s) etiketini yaz - karar mantigi bu alani OKUMAZ."""
        self._db.execute(
            "UPDATE challenger_signals SET doi_24h=? WHERE id=?",
            (round(doi, 6), row_id))

    # ------------------------------------------------ S10 haftalik gecit
    def weekly_52w_done(self, week_key: str) -> bool:
        r = self._db.query_one(
            "SELECT value FROM meta WHERE key='s10_last_week'")
        return bool(r and r["value"] == week_key)

    def mark_weekly_52w(self, week_key: str) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO meta(key,value) "
            "VALUES('s10_last_week',?)", (week_key,))

    def on_weekly_52w(self, daily: dict[str, list], week_key: str) -> int:
        """S10 haftalik sepetini yaz (secim weekly_52w_selection'da - saf).

        entry_ts = son kapanmis gunluk mumun BITISI (Pazartesi 00:00) ->
        degerlendirme Pazartesi 15dk mumlarindan baslar. Kume = GECIDIN
        hafta anahtari (tum sepet TEK kume; per-sembol ts'den turetmek
        bayat paritede kumeyi bolerdi - inceleme 2026-08-16)."""
        if "S10_52WHIGH" in RETIRED:
            return 0
        made = 0
        for prox, sym, entry, stop, last_ts in weekly_52w_selection(daily):
            entry_ts = last_ts + 86_400_000
            cid = f"S10_52WHIGH:L{week_key}"
            if self._dup("S10_52WHIGH", sym, cid) \
                    or self._crowded("S10_52WHIGH"):
                continue
            tp = entry + S10_TP_RISK * (entry - stop)
            self._db.execute(
                "INSERT INTO challenger_signals(strategy,pair,direction,"
                "created_utc,entry_ts,entry,stop,tp,timeout_bars,cluster_id,"
                "regime) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                ("S10_52WHIGH", sym, "LONG", _now_iso(), entry_ts,
                 round(entry, 8), round(stop, 8), round(tp, 8),
                 S10_TIMEOUT, cid, SAMPLING_REGIME))
            made += 1
            log.info(kv(event="challenger_signal", strategy="S10_52WHIGH",
                        pair=sym, direction="LONG"))
        return made

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

        # S11 SQUEEZE: oynaklik sikismasi (BB icinde KC, >=6 x 4H bar)
        # COZULUNCE kirilim yonune girer (on-kayit 2026-08-17). Yon cifte
        # kosullu: 4H kapanis aralik disinda VE momentum ayni yonde.
        # Stop = sikisma araliginin KARSI ucu (dogal stop).
        if atr_h and len(h_close) >= 2 * S11_BB_N + 1:
            sq = squeeze_run(h_high, h_low, h_close)
            if sq is not None:
                rng_hi, rng_lo = sq
                mom = squeeze_momentum(h_high, h_low, h_close)
                c4 = h_close[-1]
                if mom is not None and mom > 0 and c4 > rng_hi \
                        and entry - rng_lo > 0:
                    out.append(("S11_SQUEEZE",
                                ("LONG", rng_lo,
                                 entry + S11_TP_RISK * (entry - rng_lo),
                                 TREND_TIMEOUT)))
                elif mom is not None and mom < 0 and c4 < rng_lo \
                        and rng_hi - entry > 0:
                    out.append(("S11_SQUEEZE",
                                ("SHORT", rng_hi,
                                 entry - S11_TP_RISK * (rng_hi - entry),
                                 TREND_TIMEOUT)))

        # S12 RELVOL: gunun ilk 4H mumu (00-04 UTC) = acilis araligi; hacmi
        # onceki 20 gunun acilis ortalamasinin >= 2 kati ise gun icindeki
        # 15dk kenar-tetik kirilimina girer; cikis GUN SONU (on-kayit
        # 2026-08-17, Zarattini uyarlamasi - yeni oge GORELI-HACIM kapisi).
        if h_ok and len(l_close) >= 2:
            hc = htf.candles[:-1]              # yalniz kapanmis 4H mumlar
            last15 = ltf.candles[-1]
            day_start = last15.ts - (last15.ts % 86_400_000)
            opening = next((c for c in reversed(hc) if c.ts == day_start),
                           None)
            if opening is not None:
                prior = [c.volume for c in hc
                         if c.ts % 86_400_000 == 0 and c.ts < day_start]
                prior = prior[-S12_LOOKBACK_D:]
                avg_v = (sum(prior) / len(prior)
                         if len(prior) >= S12_LOOKBACK_D else 0.0)
                # zaman asimi: kalan 15dk bar sayisi -> son cikis mumu tam
                # gun sonunda (00:00 UTC) kapanir
                timeout = int((day_start + 86_400_000 - last15.ts)
                              // 900_000) - 1
                if avg_v > 0 and opening.volume >= S12_RELVOL_MIN * avg_v \
                        and timeout >= 1:
                    o_hi, o_lo = opening.high, opening.low
                    if l_close[-2] <= o_hi < l_close[-1] \
                            and entry - o_lo > 0:
                        out.append(("S12_RELVOL",
                                    ("LONG", o_lo,
                                     entry + S12_TP_RISK * (entry - o_lo),
                                     timeout)))
                    elif l_close[-2] >= o_lo > l_close[-1] \
                            and o_hi - entry > 0:
                        out.append(("S12_RELVOL",
                                    ("SHORT", o_hi,
                                     entry - S12_TP_RISK * (o_hi - entry),
                                     timeout)))

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

        # S8 FUNDSQUEEZE: ASIRI funding (S4'ten derin) + FIYAT TEYIDI. Squeeze
        # basladi mi? Negatif funding (short kalabalik) + son 15dk kapanis
        # YUKARI -> LONG; pozitif (long kalabalik) + kapanis ASAGI -> SHORT.
        # S4 hemen girer; S8 fiyatin donusunu bekler (daha seyrek, yuksek guven).
        if atr_h and funding is not None and len(l_close) >= 2:
            ann = funding * 3 * 365
            risk = S8_RISK_ATR * atr_h
            if ann < -S8_ANN_FUNDING and l_close[-1] > l_close[-2]:
                out.append(("S8_FUNDSQUEEZE",
                            ("LONG", entry - risk,
                             entry + S8_TP_RISK * risk, TREND_TIMEOUT)))
            elif ann > S8_ANN_FUNDING and l_close[-1] < l_close[-2]:
                out.append(("S8_FUNDSQUEEZE",
                            ("SHORT", entry + risk,
                             entry - S8_TP_RISK * risk, TREND_TIMEOUT)))

        # S9 GECE: yalniz BTCUSDT, 21:00-21:59 UTC penceresindeki ilk tarama.
        # Fiyat kalibina BAKMAZ - takvim tetikli. Cikis zaman-cikisidir
        # (8 bar -> EXPIRED, R = pnl/risk); stop yalniz felaket freni, hedef
        # sentetik-erisilemez. Dedup 4H kovasi (20-24) -> gunde tek kayit,
        # kume = takvim gunu (on-kayit ideas.md 2026-08-13).
        if atr_l and symbol == S9_PAIR:
            hour = (ltf.candles[-1].ts // 3_600_000) % 24
            if hour == S9_HOUR_UTC:
                risk = S9_STOP_ATR * atr_l
                out.append(("S9_GECE",
                            ("LONG", entry - risk,
                             entry + S9_TP_RISK * risk, S9_HOLD_BARS)))

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
            net_by_id: dict[int, float] = {}     # kohort blogu yeniden kullanir
            for r in closed:
                if r.get("r_multiple") is not None:
                    gross += r["r_multiple"]
                n = self._net_r(r)
                if n is not None:
                    net += n
                    net_by_id[r["id"]] = n
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
            # --- P4 golge-kohort: S2 kirilimlarinin dOI ayrimi (salt olcum,
            #     on-kayit 2026-08-16; hicbir karari degistirmez) ---
            if strat == "S2_DONCHIAN":
                labeled = [r for r in closed
                           if r.get("doi_24h") is not None]
                coh_out: dict[str, dict] = {}
                for cname, cond in (
                        ("oi_artisli", lambda d: d >= S2_OI_RISE),
                        ("oi_artissiz", lambda d: d < S2_OI_RISE)):
                    crows = [r for r in labeled if cond(r["doi_24h"])]
                    ccl: dict[str, list[float]] = {}
                    cnet = 0.0
                    for r in crows:
                        n = net_by_id.get(r["id"])   # ana donguyle TEK hesap
                        if n is not None:
                            cnet += n
                            ccl.setdefault(
                                r["cluster_id"] or "?", []).append(n)
                    cboot = measurement.cluster_bootstrap(ccl)
                    coh_out[cname] = {
                        "closed": len(crows), "net_r": round(cnet, 2),
                        "clusters": len(ccl),
                        "ci": ([cboot["ci_low"], cboot["ci_high"]]
                               if cboot and cboot.get("ci_low") is not None
                               else None),
                        "e_net": cboot["e_net"] if cboot else None,
                    }
                out["strategies"][strat]["oi_cohorts"] = {
                    **coh_out,
                    "unlabeled_closed": len(closed) - len(labeled),
                    "threshold": S2_OI_RISE,
                }
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
