# Dış Denetim #2 (2026-08-17) — İddia İddia Doğrulama Kaydı

Serhat, depoyu bağımsız bir yapay zekâya denetletti; rapor buraya karşı
doğrulandı (denetim şeridi). Hüküm sınıfları: DOĞRU / DOĞRU-AMA-ABARTILI /
YANLIŞ. Eylem sınıfları: DONMUŞ (Kural 1 — app/strategies/ KİLİT-2
altında, davranış değişikliği yasak → v2 tasarım notu) / SERBEST-BÖLGE
(donmamış, istenirse davranış-nötr temizlik) / EYLEM-YOK.

## DOĞRU bulgular

1. **volume_analyzer: event_index ↔ iloc[-2] zaman uyumsuzluğu — DOĞRU,
   şiddeti ABARTILI.** Tetik mumunun hacmi, tetik ANININ değil ŞİMDİNİN
   SMA20 ortalamasıyla kıyaslanıyor. Gerçek kusur. AMA "2 hafta önceki
   breakout" senaryosu imkânsız: _MAX_BREAK_AGE=60 (15dk×60 = en fazla
   15 saat), sweep penceresi 12 bar (3 saat). Uyumsuzluk 15 saatle
   sınırlı. Yine de haber-anı hacim sıçramaları ortalamayı şişirip eski
   tetiği haksız reddedebilir/onaylayabilir. DONMUŞ → v2 notu: "hacim
   oranı, tetik barı anındaki SMA20'ye göre hesaplanmalı."
2. **rsi(): loss=0 iken fillna(50) — DOĞRU.** Saf yükseliş penceresinde
   gerçek RSI 100 olmalıyken 50 (nötr) okunur; 40–65 "sağlıklı bant"
   koşuluna girip hak edilmemiş confluence notu bile üretebilir. Etkisi
   yalnız confidence (filtre değil). DONMUŞ → v2 notu.
3. **detect_sweep_reclaim yalnız candidates[-1] — DOĞRU.** breakout_retest
   tüm pivot adaylarını tararken sweep yalnız en son pivotu tarar; daha
   derin sweep'ler sessizce kapsam dışı. Bilinçli MVP daraltması ama
   dokümante değildi; artık burada. DONMUŞ → v2 notu.
4. **Sabit kodlu parametreler (_MAX_BREAK_AGE, _RETEST_TOL, slope 5-bar
   penceresi) — DOĞRU (yapısal not).** StrategyParams'a taşınmalıydı.
   NOT: bu sabitlerin DEĞERLERİNİ değiştirmek Kural 4 (ön-kayıt) ister;
   yapılandırılabilir hale getirmek bile davranış-riski taşır. DONMUŞ →
   v2 iskeletinde parametreleşir.
5. **RANGING rejimi hiçbir şeyi filtrelemiyor — DOĞRU (dokümantasyon
   eksiği).** Yalnız CHOP keser; RANGING/TRENDING ikisi de sinyale izin
   verir. Bilinçli: kırılım setup'ı zaten yapı ister; RANGING bilgisi
   karara değil arşive gider. Bu karar artık BURADA dokümante. EYLEM-YOK.
6. **settings.py çift default katmanı — DOĞRU (kuru risk).**
   StrategyParams'ın kendi default'ları yalnız testlerde devreye girer
   (strategy_params property her alanı açıkça geçirir); senkron kopma
   riski teorik ama gerçek. SERBEST-BÖLGE (düşük öncelik temizlik).
7. **TREND_PULLBACK ölü enum — DOĞRU.** Hiçbir üretici yok. Kontrat
   alanı olduğundan silmek yerine not düşüldü. SERBEST-BÖLGE (kozmetik).
8. **Scheduler çok sorumluluklu ("God Object") — kısmen DOĞRU (üslup).**
   Refactor davranış-nötr olsa bile kilit döneminde ölçüm altyapısında
   churn riski taşır; kazancı okunabilirlik, maliyeti regresyon riski.
   SERBEST-BÖLGE, bilinçli ERTELEME (v2 ile birlikte).
9. **main.py app.run() (Gunicorn değil) — DOĞRU.** Tek-işlemli gölge
   ölçüm botu için bilinçli sadelik; eşzamanlılık ihtiyacı yok (tarama
   kilidi zaten tek tarama dayatır). EYLEM-YOK, bilinçli ödünleşim.

## DOĞRU-AMA-ABARTILI

10. **Scheduler lazy-init "sessizce yanlış sonuç üretebilir" — ABARTILI.**
    getattr(default) desenindeki default'lar başlangıç durumunun ta
    kendisi (_bias_state="neutral", _audit_tick=0...); yanlış sonuç
    üretemez, üslup meselesi. Ayrıca test_scheduler.py bu deseni
    (object.__new__ ile __init__'siz kurulum) BİLEREK kullanıyor.
    SERBEST-BÖLGE (kozmetik; testle birlikte değişmeli).
11. **"7.5 MARKET_GATE numarası kafa karıştırıcı" — ABARTILI.** Yorumun
    kendisi taşınma tarihçesini ve nedenini açıklıyor (v3.4 + n=49
    gerekçesi); numara bilinçli olarak tarihsel iz bırakır. EYLEM-YOK.
12. **"Scheduler kritik path'leri test edilmemiş" — KISMEN YANLIŞ.**
    test_scheduler.py küçük AMA tam da denetçinin istediği şeyi test
    ediyor: histerezis 2-mum teyidi + banda sarkma + TTL + fail-closed
    halt. Kapsam genişletilebilir (S10 geçidi ayrı test dosyasında,
    dispatch ayrı) ama "yok" iddiası yanlış. EYLEM-YOK.

## YANLIŞ bulgular

13. **"ADX'te EWM, Wilder smoothing'e yakın ama birebir aynı değil" —
    YANLIŞ.** ewm(alpha=1/n, adjust=False) Wilder RMA'nın TA KENDİSİDİR
    (s_t = s_{t-1} + (x_t − s_{t-1})/n). Tek fark tohumlama: Wilder ilk
    n barın SMA'sıyla başlar, EWM ilk değerle; 200 barlık seride fark
    asimptotik sıfır. TradingView farkı tohumlamadan gelir, formülden
    değil.
14. **"RR hesabı entry_max açılınca ciddi sapar" — TEKNİK OLARAK EKSİK.**
    entry_max = min(close, level+0.5·ATR) ile zaten yarım ATR'ye
    kelepçeli; "büyük açılma" mümkün değil.

## Sonuç

Dış denetimin en değerli iki bulgusu (hacim zaman-uyumsuzluğu, RSI
fillna) GERÇEK ama ikisi de DONMUŞ bölgede ve karar-kritik değil (biri
15 saatle sınırlı kıyas kusuru, öteki yalnız confidence notu). KİLİT-2
sınavı sürerken hiçbirine dokunulmaz; tamamı v2 şampiyon tasarımının
girdi listesine işlendi. Serbest bölgedeki temizlikler (settings çift
default, lazy-init, ölü enum) istenirse ayrı, davranış-nötr bir bakım
dalgasında yapılabilir — aciliyeti yok.

## KARAR KAYDI (2026-08-17, Serhat onayı "tamam")

**Bulgu 1 (hacim zaman uyumsuzluğu): v2'YE ERTELENDİ — şimdi düzeltme
YOK.** Gerekçe: kusur karar-kritik değil (≤15 saatlik ortalama kayması,
yönü iki taraflı, yalnız hacim kapısı hassasiyeti); davranış değişikliği
KİLİT-2 sınav sayaçlarını sıfırlatırdı ve bedel kusurdan büyük. Sınav,
motoru olduğu gibi yargılar; düzeltme v2 iskeletinin girdi listesinde
("hacim oranı, tetik barı anındaki SMA20'ye göre"). Gölge-ölçüm ara yolu
(kayıtlı istisna kapsamında salt-metadata) İSTENMEDİ — gerekirse ayrı
karar olur.
