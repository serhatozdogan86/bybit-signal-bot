# Fikir Rafı — bir SONRAKİ kilit penceresinde değerlendirilecek
(config-lock.md gereği: pencere boyunca eşik değişikliği yok; fikirler burada birikir)

- 2026-07-30 · HAYALET DOLUŞ BULGUSU: ilk 22 NOT_FILLED hayaletinin toplamı
  +45.78R (ort +2.08R). Konseyin advers seçim uyarısı veriyle doğrulanıyor:
  dolmayanlar en iyi işlemler. Kilit-v2 adayı: giriş agresifliği (bölge
  derinliğinden doluş / kovalamalı limit / kısmi market), NOT_FILLED
  penceresinin kısaltılması (6sa -> 3-4sa) ile birlikte test edilmeli.
- 2026-07-29 · Konsey S3: tahsis politikası A/B (slot doluşta atama,
  güven-öncelikli kuyruk, EV sıralaması, anti-korelasyon bonusu).
- 2026-07-29 · Konsey: hacim eşiğine saatlik mevsimsellik düzeltmesi;
  sweep-reclaim vs breakout-retest rejim uyumu filtresi.
- 2026-07-30 · YENİDEN GİRİŞ GÖZLEMİ: PRL aynı gün aynı bölgeden 3 kez
  sinyallendi (2 LOSS + 1 açık). Dedup yalnız açık pozisyonu engelliyor;
  kapanan kayıptan sonra aynı parite/kümeye soğuma süresi (örn. 8-12sa
  veya 1×4H mum) kilit-v2 adayı.

## Dış kod denetimi bulguları (2026-08-02) — kilit sonrası değerlendirilecek
Bu turda YAPILDI (motor dışı, kilit ihlali yok): eşzamanlı tarama kilidi,
opt-in erişim jetonu, durum değiştiren rotaların POST'a taşınması,
fonksiyon içi import temizliği.

Rafa yazılanlar:
1. **Sentetik TP2 işaretlenmeli.** Gerçek pivot bulunamayınca TP2, TP1–giriş
   farkının simetrik yansıması olarak üretiliyor ve çıktıda gerçek pivot
   hedefiyle aynı görünüyor. Muhasebeye GİRMİYOR (kazanç kriteri yalnız TP1),
   bu yüzden ölçüm etkisi sıfır — ama tüketiciye `tp2_synthetic: true` alanı
   verilmeli.
2. **Yutulan hata sayacı.** `except Exception` blokları taramayı düşürmemek
   için bilinçli; ancak yutulan hata sayısı ölçülmüyor. Olay türü bazında
   sayaç + panoda görünürlük (sessiz veri bozulması erken yakalanır).
3. **TTL (7200s) env'e taşınabilir** — kilit döneminde BİLEREK sabit; v3.6
   gate_log verisi 11 gün sonra bu sayıyı gerekçelendirecek veya değiştirecek.
4. **`entry_max = min(close, level+0.5*ATR)`** teorik olarak bölgeyi seviyenin
   altına kaydırabilir. 149 sinyalde 0 kez oldu; bölge/risk oranı medyan 0.294,
   maks 0.308. `close` bağladığında bölgeyi DARALTIYOR (muhafazakâr yön).
   İzlemede kalsın, müdahale gereksiz.
5. **dashboard.py tek dosya (131KB)** — sıfır bağımlılık/derleme adımı için
   bilinçli tercih. Bölme, ancak derleme adımı kabul edilirse anlamlı.
6. **Scheduler tek sınıfta çok sorumluluk** — market bias, orphan eval,
   funding backfill, commentary, gist. Kilit sonrası ayrıştırma adayı.

## H-1 (2026-08-04): Williams %R aşırı alım bölgesi — RET filtresi hipotezi
**Statü:** hipotez. Kod yok, aday yarışına GİRMEZ, kilit dönemi boyunca
uygulanmaz. Ön-kayıt amaçlıdır: kural bugünden yazılır ki sonradan veriye
uydurulamasın.

**Gözlem (144 kapanmış şampiyon sinyali, arşiv mumlarından hesaplandı):**
sinyal mumunda 14 periyotluk Williams %R değerine göre bölünmüş sonuçlar:

| %R bölgesi | n | WR | brüt R |
|---|---|---|---|
| aşırı satım (< −80) | 24 | %33.3 | +8.23 |
| orta (−80..−20) | 92 | %34.8 | +33.79 |
| aşırı alım (> −20) | 28 | %17.9 | −10.42 |

**Hipotez (önceden ilan edilen kural):** sinyal mumunda %R(14) > −20 ise
sinyal ÜRETİLMEZ. İndikatör sinyal doğurmaz, sinyal ELER — ilkeye uygun tek
kullanım biçimi budur.

**Neden şimdi uygulanmıyor — üç çekinceyi kayda geçiriyorum:**
1. **Örneklem yetersiz.** 28 işlem, küme mantığıyla muhtemelen 8–10 bağımsız
   fikir. Kendi eşiğimiz 50 küme.
2. **Çoklu karşılaştırma.** Bu bölme ARANARAK bulundu. On gösterge denense
   biri tesadüfen ayrışırdı; aranmış-bulunmuş kalıp en zayıf kanıttır.
3. **Muhtemelen yeni bilgi değil.** SHORT sinyallerinin %R medyanı −60.4,
   LONG'un −43.3. "Aşırı alımda doğan sinyal kötü" bulgusu büyük ihtimalle
   market kapısının (karşı-trend blok) yakalaması gereken şeyin gölgesidir.
   Önce şu ayrıştırma yapılmalı: bu 28 sinyalin kaçı zaten kapı tarafından
   bloklanmıştı / bloklanmalıydı? Ayrıştırma yapılmadan filtre eklenirse
   aynı etki iki kez sayılır.

**Test protokolü (kilit-v2 penceresinde):** filtre uygulanmaz; sinyal
üretilmeye devam eder ve %R değeri kayda geçer. 50 küme dolduğunda
"filtre olsaydı" kohortu ile gerçek kohort küme-CI ile karşılaştırılır.
Karar seçim penceresinde DEĞİL, doğrulama penceresinde verilir.

**Williams %R hakkında dürüstlük:** gösterge, Hızlı Stokastik %K'nın ters
çevrilmiş hâlidir — matematiksel olarak yeni bilgi taşımaz, aynı bilginin
farklı ambalajıdır. Klasik kullanımı (aşırı satımda al) S3'ün hipotez
ailesiyle aynıdır ve S3 şu an adayların en kötüsüdür (66 işlem, %23 WR,
net −51R, CI [−0.98, −0.53]). Bu yüzden %R aday strateji olarak
EKLENMEDİ; yalnızca reddetme filtresi hipotezi olarak kaydedildi.

## S5 KESİTSEL MOMENTUM — ÖN-KAYIT (2026-08-13, Serhat onayı)
Bu belge S5'i geçmiş veride TEST ETMEDEN ÖNCE yazıldı; kurallar burada
donduruldu. Tasarım metnindeki ilk parametre (24s bakış / 8s denge)
LİTERATÜR gerekçesiyle güncellendi (aşağıda) — bu güncelleme bizim
verimize DEĞİL, yayınlanmış dış çalışmalara dayanır (p-hacking değil).

**Neden 24s değil 14 gün?** Yayınlanmış kripto momentum çalışmaları
(Drogen-Hoffstein-Otte 2023: 30g bakış/7g denge; Dobrynskaya 2021: momentum
yalnız 2–4 hafta bakışında pozitif, 1 aydan sonra TERSİNE döner) 24 saatlik
bakışın momentum değil gürültü/ters-dönüş bölgesi olduğunu gösteriyor.
İdeal 30g/7g ise 90 günlük veride 50 kümeye ulaşamaz (ilk 30g ısınmaya
gider → ~17 küme). Uzlaşma: **14 gün bakış / 48 saat denge** — literatürün
momentum penceresinin kısa ucu VE 90 günde ~76 küme (sınav geçebilir).

**Dondurulmuş kurallar (v1):**
- Zaman dilimi: 4H. Bakış = 84×4H bar (14 gün). Denge = 12×4H bar (48 saat).
- Evren: her denge anında ≥84 bar geçmişi olan + o anda ve 12 bar sonra
  mumu bulunan tüm pariteler (uygun evren N).
- Sıralama sinyali: HAM getiri = close[t]/close[t−84] − 1 (vol-ayarsız;
  vol-ayarlı sıralama AYRI hipotez, ayrı test).
- Sepet: en güçlü %10 → LONG, en zayıf %10 → SHORT; sepet boyu =
  max(1, round(0.10×N)).
- Giriş close[t], çıkış close[t+12] (48 saat sabit tutuş; stop/hedef YOK).
- Risk birimi (R paydası): ATR(14,4H)[t] / close[t] = atr_frac.
  Ham getiri (yönle işaretli) ÷ atr_frac = brüt R.
- Maliyet (net R): brüt R − 2×TAKER/atr_frac − FUNDING_8H×6/atr_frac.
  (2×taker round-trip market; 48s = 6 funding penceresi; STOP kayması YOK
  çünkü stop yok. TAKER=0.00055, FUNDING_8H=0.0001 — canlı motorla aynı.)
- Küme: yön + denge zaman damgası (bir dengedeki tüm LONG'lar tek fikir,
  tüm SHORT'lar tek fikir — aynı piyasa dalgasına maruzlar).
- Faz-1 kapısı DİĞER ADAYLARLA AYNI: ≥50 kapanmış küme + küme-CI alt > 0.

**Başarı ölçütü (önceden ilan — sonra kaydırılamaz):**
- Canlı yarışa ADAY olur: küme-CI alt sınırı ≥ 0 VE net R toplamı > 0.
- ELENİR (canlıya girmez): küme-CI üst sınırı < 0.
- BELİRSİZ (arası): canlı gölge yarışa aday olur ama "umut vaat etti"
  DENMEZ; hüküm yine ileriye dönük veriden.
- HER HÂLDE backtest HÜKÜM DEĞİL, yalnız budama. Kesin söz canlı yarışın
  50 kümesi + walk-forward doğrulamasından çıkar.

**Bilinen zayıflıklar (önceden kabul):** (1) momentum çöküşü — dip sonrası
kaybedenlerin sert sıçraması kuyruğu domine eder (küme-CI tam bunu yakalar);
(2) short bacağı likidite tuzağı — kaybedenler ince paritelerde yoğunlaşır;
top-150 evreni kısmen filtreler ama v1'e ek likidite filtresi konmadı
(sadık kalındı, not edildi); (3) ATR normalizasyonu bir vekildir, "gerçek"
S5 metriği değil — budama için yeterli, canlıda (B) portföy metriği ayrıca
kurulabilir. (4) 90 gün tek rejimdir; backtest bir rejim çöküşü görmezse
sonuç iyimser olabilir.

**Ölçüm yolu:** (A) risk-birimli R (yukarıda). Alternatif (B) portföy
getirisi+Sharpe reddedildi (yeni altyapı, şampiyon diliyle kıyaslanamaz).

**Kilit/izolasyon:** bu adım docs + tools/backtest_s5.py; şampiyon motoruna,
eşiklerine, canlı DB'ye SIFIR dokunuş. S5 canlıya (challengers.py) ancak
backtest'i geçerse ve AYRI izolasyonlu bir dalgada girer.

### S5 BACKTEST SONUCU (2026-08-13, tek atış — ön-kayıt kuralıyla)
90 günlük gerçek veri (2026-05-12 → 08-12), 150 parite, 39 denge, 78 küme,
1008 pozisyon (504L/504S). **Brüt R −26.26, net R −66.54, küme-CI
[−0.413, +0.261], E_net −0.066.** İlan edilmiş kurala göre **BELİRSİZ**
(küme-CI üst sınırı <0 değil → elenmedi; ama alt<0 ve net<0 → "umut vaat
etti" DENMEZ). Maliyetten ÖNCE bile ekside — hipotezin beklediği kenar YOK.
Araştırma uyarısını doğruluyor (kripto'da kesitsel momentum, zaman-serisi
momentumdan zayıf).
**Karar:** S5 canlı yarışa EKLENMEDİ (backtest'te net kenar yok; slot daha
güçlü adaya). Vol-ayarlı sıralama AYRI hipotezdir; aynı veride yeniden
koşmak p-hacking olur — ayrı ön-kayıt + gelecek veri gerektirir.

## TSM ZAMAN-SERİSİ MOMENTUM — ÖN-KAYIT (2026-08-13, Serhat onayı)
Bu belge TSM'i geçmiş veride TEST ETMEDEN ÖNCE yazıldı; kurallar donduruldu.

**Tasarım: S5'in TEMİZ KONTROL KOLU.** TSM = S5 ile birebir aynı boru hattı,
TEK fark sinyalde: S5 evreni kıyaslar (kesitsel/göreli sıralama); TSM her
pariteye KENDİ geçmişine göre bakar (mutlak/zaman-serisi işaret). Diğer her
şey aynı: 14 gün (84×4H) bakış, 48s (12×4H) tutuş, ATR-normalize R, aynı
maliyet, küme=yön+denge, Faz-1 kapısı ≥50 küme + küme-CI alt>0. Amaç:
"kripto'da mutlak trend mi göreli sıralama mı kazanır" sorusunu AYNI veride
temiz kıyasla ölçmek (Moskowitz-Ooi-Pedersen 2012; araştırma: kripto'da
TSM > kesitsel momentum).

**Dondurulmuş kurallar (v1):**
- Sinyal: her uygun parite için ret = close[t]/close[t−84] − 1.
  ret>0 → LONG, ret<0 → SHORT, ret==0 → atla. (Ölü bant YOK; ayrı hipotez.)
- Sepet YOK: uygun evrendeki HER parite işaretine göre pozisyonlanır
  (S5'teki %10 decile burada yok — mutlak sinyal herkese uygulanır).
- Giriş close[t], çıkış close[t+12]. R paydası ATR(14,4H)/close.
  net R = (getiri − maliyet)/atr_frac; maliyet = 2×taker + funding×6.
- Küme: yön + denge zaman damgası. Faz-1 kapısı diğerleriyle AYNI.

**Başarı ölçütü (önceden ilan — S5 ile aynı):**
- ADAY: küme-CI alt ≥ 0 VE net R > 0 (VE ≥50 küme).
- ELENİR: küme-CI üst < 0.
- BELİRSİZ (arası): canlıya aday, "umut vaat etti" DENMEZ.
- Backtest HÜKÜM DEĞİL, budama. Kesin söz canlı 50 küme + walk-forward'dan.

**Dürüstlük notu (araştırmadan):** TSM başarısının çoğu momentum
"zamanlamasından" değil vol-ölçeklemeden gelebilir. ATR-normalize R bizim
vol-ölçeklememizdir ve S5 ile TSM'de AYNIdır → iki aday arasındaki fark
yalnız sinyal türüne (mutlak vs göreli) atfedilebilir; bu, kıyası temiz
kılar ama "TSM zamanlaması mutlak değer katıyor mu" ayrı bir sorudur.

**Bilinen zayıflıklar:** yatay piyasada whipsaw; sert dönüşte geç çıkış;
90 gün tek rejim. **Kilit/izolasyon:** docs + tools/backtest_tsm.py;
şampiyona/canlı DB'ye sıfır dokunuş.

### TSM BACKTEST SONUCU (2026-08-13, tek atış) + S5/TSM KARŞILAŞTIRMASI
90 gün, 150 parite, 39 denge, 78 küme, 5021 pozisyon (1949L/**3072S**).
**Brüt R −417.4, net R −822.51, küme-CI [−0.499, +0.189], E_net −0.164.**
İlan edilmiş kurala göre **BELİRSİZ** (üst<0 değil ama net ve alt açık ekside).

**S5 vs TSM (aynı ölçüm, tek fark sinyal):**
| | net R | E_net | küme-CI |
|--|--|--|--|
| S5 (göreli sıralama) | −66.54 | −0.066 | [−0.413, +0.261] |
| TSM (mutlak işaret) | −822.51 | −0.164 | [−0.499, +0.189] |

**Yorum (regime gözlemi — strateji ayarı DEĞİL):** İkisi de bu 90 günde
kenar göstermedi; TSM belirgin daha kötü. TSM'de 3072 short vs 1949 long →
pencerede pariteler çoğunlukla negatif 14g getiriyle short işaretledi ama
piyasa short'ları takip etmedi → geniş whipsaw (klasik trend-takibi başarısızlığı,
yükselen/çırpınan rejimde). Bu TEK rejimdir; literatürün pozitif momentum
sonuçları çok-yıllı, çöküş içeren örneklemlerden gelir ("crisis alpha" —
bu pencerede yok). Sonuç: "momentum çalışmıyor" DEĞİL, "bu rejimde çalışmadı".

**Karar:** Ne S5 ne TSM canlı slota HAK ETMEDİ (ikisi de net ekside).
Kombinasyon/vol-ayarlı/farklı-bakış varyantlarını AYNI veride aramak
YASAK (p-hacking) — her biri ayrı ön-kayıt + gelecek/başka veri ister.
Momentum ailesi şimdilik rafta; canlı gölge yarışın kendi ileriye dönük
verisi bir gün trend/çöküş rejimi görürse aile yeniden değerlendirilir.

## MOMENTUM AİLESİ RAFTAN ÇIKARMA TETİĞİ (ÖN-KAYIT — 2026-08-13, Serhat onayı)
S5 (kesitsel) + TSM (zaman-serisi) 90 günlük backtest'te kenar göstermedi
(tek rejim: yükselen/çırpınan, trend/çöküş yok). Aile RAFTA. Aşağıdaki
tetiklerden **HERHANGİ BİRİ** olursa yeniden değerlendirilir:

1. **Canlı kanıt:** S1_TSMOM (zaten canlıda, momentum ailesinden) küme-CI
   ALT sınırı > 0 verirse — momentum ileriye dönük gerçek veride çalışmaya
   başladı demektir.
2. **Rejim olayı (nesnel):** BTC 4H'de 90 günlük getiri büyüklüğü ≥ **%40**
   (güçlü sürekli trend) VEYA 60 gün içinde tepe-dip düşüş ≥ **%25** (çöküş/
   kriz rejimi).

**Tetik gelince:** o rejimi kapsayan TAZE veri indirilir ve DONMUŞ S5/TSM
araçları (tools/backtest_s5.py, backtest_tsm.py) HİÇ DEĞİŞTİRİLMEDEN yeni
pencerede koşulur. Yeni parametre/varyant = p-hacking (yasak). Momentum
yeni rejimde kenar gösterirse canlıya yeniden değerlendirilir.

## S8 FONLAMA SIKIŞMASI — ÖN-KAYIT + CANLI (2026-08-13, Serhat onayı)
Funding yön sinyali; backtest ATLANDI çünkü indirilen veride funding geçmişi
YOK (yalnız fiyat mumu) ve araştırma funding'i "hipotez seviyesi" işaretledi.
Kuralımız (Kural 4/5): veriden türetilen fikir gelecek/canlı veride test
edilir → S8 doğrudan canlı gölge yarışa aday olarak girdi.

**S4'ten AYRIŞMA (yönü örtüşür — funding-yönü doğası gereği; fark girişte):**
- (a) DAHA DERİN eşik: yıllık |funding| > **%60** (S4: %30) — yalnız aşırı
  kalabalık.
- (b) FİYAT TEYİDİ şart: son 15dk kapanış sıkışma yönünde dönmüş olmalı
  (negatif funding → kapanış YUKARI → LONG; pozitif → kapanış AŞAĞI → SHORT).
  S4 teyit istemez, hemen girer; S8 fiyat dönüşünü bekler → daha seyrek,
  daha yüksek güven.

**Dondurulmuş kurallar (challengers.py sabitleri):** S8_ANN_FUNDING=0.60,
stop 2×ATR(4H), hedef 2R, zaman aşımı 192 bar (48 saat), tavan 15.
Küme=yön+4H penceresi (diğerleriyle aynı). Faz-1 kapısı AYNI: ≥50 küme +
küme-CI alt>0.

**Dürüst etiket:** S8 sıfırdan yeni kenar değil, RAFİNASYON hipotezi —
"aşırılık + fiyat teyidi, S4'ün mekanik carry'sini geçer mi?" Hüküm canlı
50 küme + walk-forward'dan çıkar; backtest yok.

**İzolasyon:** ayrı tablo (challenger_signals), şampiyona sıfır dokunuş,
bayt-bayt izolasyon testi yeşil. İkiz (midas) kontrolü: N/A — midas ABD
hisse botu, funding kavramı yok (docs/ikiz-depo-notu.md).

## S9 GECE PENCERESİ — ÖN-KAYIT + CANLI (2026-08-13, Serhat onayı)
Kaynak: docs/aile-arastirmasi-2026-08-13.md #1 (Vojtko-Javorská SSRN 4581124
+ Quantpedia/Concretum bağımsız replikasyonları; rakamlar özet düzeyi,
birincil PDF doğrulanamadı — DOĞRULANAMADI statüsüyle anılır).

**Hipotez:** NY kapanışı sonrası / Asya öncesi (21:00–23:00 UTC) BTC günün
en güçlü ortalama getirisini verir. Görev kenarı kanıtlamak DEĞİL, bu
takvim etkisinin hâlâ yaşayıp yaşamadığını ucuza/hızla ölçmek (örneklem
2022'de bitiyor; ETF sonrası ölmüş olabilir — bilinçli risk).

**Dondurulmuş kurallar (challengers.py sabitleri):**
- Yalnız BTCUSDT (S9_PAIR). Genişletme (likit 5 parite) AYRI ön-kayıt ister.
- Giriş: 21:00–21:59 UTC penceresindeki İLK taramada son 15dk kapanıştan
  LONG. Fiyat/hacim/rejim koşulu YOK (takvim tetikli).
- Çıkış: girişten 8 KAPANMIŞ 15dk bar sonra (2s00–2s15dk; giriş barına göre
  fiilen 23:15–00:00 UTC arası) zaman-çıkışı → defterde EXPIRED,
  R = pnl/risk. Hedef sentetik-erişilemez (risk×100); stop 2×ATR(15dk)
  yalnız felaket freni ve R paydası.
- Küme = takvim günü (dedup 4H kovası 20–24 penceresini kapsar → günde tek
  kayıt). Tavan 1. Faz-1 kapısı DİĞERLERİYLE AYNI: ≥50 küme + küme-CI alt>0.
- Bot 21–22 UTC arası kapalıysa o gün atlanır (eksik veri eksik kalır).

**Bilinen zayıflıklar (önceden kabul):** 24 saatten seçilmiş 2 saat = veri
madenciliği şüphesi taşır; koşulsuz long ayı rejiminde kanar; kenar saat
başına küçük → maliyet modeli belirleyici. 50 küme ≈ 2–2.5 ayda dolar —
envanterin en hızlı hükmü; kötüyse ucuza öğrenilmiş olur.

## KORELASYON ÖLÇÜM ALETİ — Faz A (2026-08-13, Serhat onayı)
app/services/correlation.py + /correlation rotası. SALT RAPOR: strateji-çifti
günlük brüt-R korelasyon matrisi (çiftin her iki tarafında ≥10 aktif gün),
etkin bağımsız bahis sayısı N_eff = N/(1+(N−1)·ort_korelasyon), aynı-gün-
aynı-yön çakışma oranı. Hiçbir karar/eşik üretmez; test_report_is_measurement_only
bunu zorlar. Yeni aday ön-kayıtlarının şart koştuğu örtüşme ölçümlerinin
(S8↔türevleri, V1/S-ATT1 çakışma raporları) altyapısıdır. Faz B (ağırlıklama)
AYRI ön-kayıt ister; en erken 3 ay rapor birikince.

## P1 OI-FLUSH DÖNÜŞÜ — ÖN-KAYIT (2026-08-14, Serhat onayı "Başla")
Kaynak: docs/aile-arastirmasi-2026-08-13.md #2 (Hong-Yogo JFE 2012 çerçevesi
+ Glassnode deleveraging analizi — kripto-saatlik kurala sıçrama BÜYÜK,
bilinçli risk). Kurallar OI VERİSİ GÖRÜLMEDEN donduruldu (rakamlar rapor +
yayın kaynaklı; bizim veriden türetilmedi).

**Hipotez:** Fiyat düşerken açık pozisyon stoku (OI, kontrat adedi) hızla
eriyorsa satış zorunlu kapatmadır (fiyata duyarsız); akış bittiğinde baskı
kalkar → stabilizasyon anında LONG kenarı doğar.

**Dondurulmuş kurallar (v1):**
- Tetik (her 15m kapanışta): ΔOI(24s)/OI ≤ **−%10** (KONTRAT adedi; USD
  değil — USD kullanmak sinyali fiyatın kendisine döndürür) VE fiyat aynı
  24s'de ≥ **2×ATR(14,4H)** düşmüş (kapanış-kapanış) VE son 15m kapanış bir
  öncekinin ÜSTÜNDE (stabilizasyon) → LONG, girişte 15m kapanış.
- Stop: 24s penceresinin dibi − 1×ATR(14,15m). Hedef: 2R. Zaman aşımı:
  96×15m bar (24 saat) → EXPIRED, R=pnl/risk. Aynı mumda stop+hedef →
  LOSS(ambiguous) — motorla aynı muhafazakâr kural.
- Küme = yön + 4H penceresi (pariteler arası ORTAK — challenger kural
  uzayıyla aynı). Parite başına aynı anda tek pozisyon; aynı küme aynı
  paritede tekrar işlem açmaz.
- Maliyet: canlı model (2×taker + LOSS'ta kayma + funding×tutuş) — sabitler
  signal_tracker ile aynı.
- OI verisi: Bybit v5 open-interest, 1 saatlik; arşiv derinliği API ne
  verirse o (beklenti ~90 gün; kısaysa pencere daralır ve rapora yazılır).

**Başarı ölçütü (S5/TSM ile aynı, önceden ilan):** ELENİR: küme-CI üst < 0.
ADAY: küme-CI alt ≥ 0 VE net R > 0 VE ≥50 küme. Arası: BELİRSİZ (canlıya
aday olabilir, "umut vaat etti" denmez). Backtest HÜKÜM DEĞİL, budama.

**P4 OI-ONAYLI KIRILIM FİLTRESİ (koşullu ön-not):** P1 verisiyle aynı OI
akışını kullanır; kırılım sinyallerinde ΔOI(24s) ≥ +%5 kohort etiketi —
GÖLGE kohort, hiçbir motora dokunmaz. TAM ön-kaydı P1 backtest SONUCU
görüldükten sonra, canlı OI toplama kararıyla birlikte yazılır (şimdi
yazılmıyor ki P1 sonucuna göre ayarlanmış görünmesin).

**Bilinen zayıflıklar:** aylık-emtia kanıtından saatlik-kripto kurala
sıçrama; kaskad ortamında kâğıt-doluş iyimserliği (S6 akrabalığı — fark:
tetik verisi OI STOKU, fiyat süpürmesi değil + stabilizasyon teyidi + sıkı
zaman-stopu, rapor 'Tuzaklar' bölümü şartları); OI arşiv derinliği API
kısıtına tabi.

### P1 OI-FLUSH BACKTEST SONUCU (2026-08-16, tek atış — ön-kayıt kuralıyla)
OI verisi: 150 parite, 303.202 nokta, 2026-05-18 → 2026-08-16 (~90 gün, tam
derinlik). Backtest: 105 parite işlendi (45'i OI'siz — evren kayması: kline
arşivi 08-12 top-150'si, OI arşivi 08-16 top-150'si; dürüstçe sayıldı).
**308 işlem (63W/194L/51E), 201 küme, brüt R −55.89, net R −77.44,
küme-CI [−0.396, −0.093], E_net −0.251.**

**HÜKÜM: ELENDİ** — ilan edilmiş EN SERT kriterle (küme-CI ÜST sınırı < 0):
%95 güvenle gerçek kenar negatif. Kazanma oranı %24.5 (2R hedefle başabaş
~%33 gerekirdi). P1 canlıya GİRMEZ.

**Ders (rapor 'Tuzaklar' bölümünün öngörüsü gerçekleşti):** OI teyidi eklense
bile "düşen bıçağı tutma" ailesi bu piyasada kaybediyor — S3 (−158R), S6
(−84R) ve şimdi P1 (−77R backtest) aynı ailenin üçüncü kaybı. Stabilizasyon
mumu + OI stoku farklılaşması yetmedi. CEPTEKİ "ortalamaya dönüş dirilişi"
fikri için de güçlü bir karşı-kanıt olarak not edildi.

**P4 kararı (ön-nottaki kapı):** P1'in ölümü P4'ü otomatik öldürmez — P4
farklı hipotez (dönüş değil, KIRILIM teyidi). OI verisi artık diskte;
P4 önce ucuz backtest'le sınanabilir (S2-Donchian kırılımlarını ΔOI'li/
ΔOI'siz iki kohorta bölüp eşleştirilmiş karşılaştırma). Karar Serhat'a
sunuldu; canlı OI toplama yatırımı ancak P4 backtest'i olumluysa düşünülür.

## P4 OI-ONAYLI KIRILIM FİLTRESİ — TAM ÖN-KAYIT (2026-08-16, Serhat onayı)
P1 ELENDİ; P4 farklı hipotez (dönüş değil KIRILIM teyidi): "kırılımda OI
artıyorsa hareketi yeni para taşıyor (devam olası); OI düşüyorsa eski
pozisyon kapanışı (sahte kırılıma yatkın)". Kaynak: Hong-Yogo JFE 2012.
Kurallar backtest KOŞULMADAN donduruldu:
- Kırılım: S2-Donchian kuralının BİREBİR kopyası (20×4H kanal, kenar tetik,
  stop 2×ATR-4H, hedef 6×ATR-4H, 192 bar zaman aşımı, LONG+SHORT ayna).
- Kohort ayrımı (tek fark): tetik anında ΔOI(24s)/OI ≥ +%5 (kontrat adedi)
  → "OI-ARTIŞLI" kohort; < +%5 → "OI-ARTIŞSIZ". OI verisi yoksa işlem
  atlanır ve sayılır.
- Küme = yön+4H (kohort içi). Maliyet canlı model. TEK atış.
**Önceden ilan edilen hüküm kuralı:**
- FİLTRE UMUT VAAT EDİYOR (canlı gölge-kohort dalgası açılabilir):
  OI-ARTIŞLI E_net > OI-ARTIŞSIZ E_net VE OI-ARTIŞLI küme-CI alt ≥ 0.
- FİLTRE ELENDİ: OI-ARTIŞLI E_net ≤ OI-ARTIŞSIZ E_net (teyit katkı
  vermiyor) VEYA OI-ARTIŞLI küme-CI üst < 0.
- Arası: BELİRSİZ. Her hâlde backtest hüküm değil, budama.

## 52w-HIGH ZİRVE YAKINLIĞI — ÖN-KAYIT (2026-08-16, Serhat onayı)
Kaynak: rapor #4 (Jia ve ark. JBF 2026; George-Hwang 2004 — listenin en
güçlü hakemli kanıtı; rakamlar özet düzeyi). Kurallar veri İNMEDEN donduruldu:
- Veri: GÜNLÜK kline, hedef 750 gün (API verirse; 365 gün çapa + ~55 hafta
  test penceresi).
- Her Pazartesi 00:00 UTC: yakınlık = son günlük kapanış / son 365 günün
  (parite 365 günden yeniyse listing'den beri; en az 90 gün şart) en yüksek
  GÜNLÜK kapanışı.
- Seçim: yakınlık ≥ 0.90 VE o haftanın kesitinde en üst %10 (iki koşul
  birden). Yalnız LONG (kripto kanıtı uzun bacakta).
- Karar Pazartesi 00:00 UTC'de, son KAPANMIŞ günlük mumla (= Pazar
  kapanışı); giriş o kapanış fiyatından. Stop = giriş − 2×ATR(14,günlük);
  çıkış 7 gün sonra kapanış (zaman) veya stop (önce gelen). Hedef YOK → aynı-mum
  belirsizliği yok. Küme = formasyon haftası (haftanın tüm girişleri TEK
  küme — LONG-only).
- Maliyet canlı model. Başarı ölçütü S5/TSM ile aynı (ELENDİ: CI üst<0;
  ADAY: CI alt≥0 + net>0 + ≥50 küme; arası BELİRSİZ).

## S-ATT1 WİKİPEDİA DİKKAT ŞOKU — ÖN-KAYIT (2026-08-16, Serhat onayı)
Kaynak: rapor #5 (Hoang-Vo JBEF 2024; Maitre JBF 2025; karşı-kanıt
Shen-Urquhart 2019 dürüstçe not). Kurallar donduruldu; İMPLEMENTASYON
SIRADAKİ DALGA (sembol→makale eşlemesi elle + çift kontrol gerektirir,
aceleye getirilmez):
- Evren: perp listesinde Wikipedia makalesi olan coinler (eşleme elle,
  çift kontrollü; eşleme tablosu depoya commit edilir).
- Sinyal: günlük görüntülemede log-z skoru ≥ 2 (son 90 güne göre) VE 24s
  getiri 0 ile +%25 arasında (kötü-haber ve pump-kovalama filtreleri) →
  LONG. Stop 2×ATR(4H); 3 gün zaman-stopu; 7 gün yeniden-giriş yasağı.
- Küme = takvim günü. Wikimedia geçmişi mevcut → önce backtest (90 gün),
  sonra canlı karar. Başarı ölçütü S5/TSM ile aynı.
- Bilinen riskler: ters nedensellik (dikkat dünkü fiyatın sonucu olabilir),
  T+1 veri gecikmesi, büyük-coin yanlılığı, dış API bağımlılığı (fail-soft).

### P4 + 52w BACKTEST SONUÇLARI (2026-08-16, tek atış — ön-kayıt kuralıyla)

**P4 OI-onaylı kırılım (eşleşmiş kohort):** 105 parite, 2877 kırılım işlemi.
| Kohort | işlem | küme | net R | E_net | küme-CI |
|---|---|---|---|---|---|
| OI-ARTIŞLI (ΔOI≥+%5) | 594 | 382 | **+22.32** | **+0.038** | [−0.089, +0.171] |
| OI-ARTIŞSIZ | 2283 | 706 | **−170.88** | −0.075 | [−0.153, +0.009] |

**HÜKÜM: BELİRSİZ** (ilan kuralı: UMUT için artışlı CI alt ≥ 0 gerekirdi;
alt −0.089). AMA fark ÇARPICI ve hipotez yönünde: E_net farkı +0.113;
filtre +22R'yi −171R'den ayırıyor. Kırılım ailemizin (şampiyon+S2) isabetini
artırma potansiyeli ilk kez veriyle desteklendi. Sonraki adım kararı:
canlı OI toplama + gölge-kohort ölçümü (altyapı yatırımı) Serhat'a sunuldu.
(tetikte-OI-yok 170: OI arşivi 05-18'de, kline 05-12'de başlıyor — masum.)

**52w-HIGH zirve yakınlığı:** 150 parite, 750 gün TAM derinlik (2024-07-27 →
2026-08-15; ÇOK REJİMLİ örneklem — 90-günlük testlerin tek-rejim zaafı yok).
93 hafta, 83 girişli, 273 işlem (120W/87L), brüt +24.57, **net +13.32**,
küme 83 (≥50 ✓), **E_net +0.049**, küme-CI [−0.137, +0.267].
**HÜKÜM: BELİRSİZ** — ADAY için CI alt ≥ 0 gerekirdi. Ön-kayıt gereği
"umut vaat etti" DENMEZ; ama iki yıllık, çok-rejimli örneklemde pozitif
beklenti + ≥50 küme ile canlıya aday OLABİLİR (kural buna izin veriyor).
Karar Serhat'a sunuldu.

**Bağlam:** Bu ikisi, S5/TSM/P1'in net-negatif sonuçlarından sonra ilk
pozitif-yönlü budama sonuçları.

## P4-CANLI + S10-CANLI UYGULAMA NOTLARI (2026-08-16, Serhat onayı "ikisini de yap")
**P4 gölge-kohort canlıda:** v1 YALNIZ S2 kayıtları etiketlenir (şampiyon
tablosuna dokunuş ertelendi — az sinyal, tablo riski; ayrı karar ister).
Etiket: S2 sinyali doğduğu taramada 1 OI çağrısı (25×1h nokta) → dOI(24s)
kaydedilir; veri yoksa etiket boş kalır ve "etiketsiz" DÜRÜSTÇE sayılır.
Eşik +%5 (S2_OI_RISE, backtest ile aynı). /challengers → S2 → oi_cohorts
bloğu salt ölçümdür; HİÇBİR karar okumaz. Hüküm: her iki kohortta ≥50 küme
dolunca E_net + CI karşılaştırılır (ileriye dönük veri).
**S10 canlı uyarlaması (backtest'ten farklar, dürüstçe):** (a) karar
Pazartesi günkü İLK TAM TARAMANIN SONUNDA verilir (00:00 değil; bot tarama
döngüsüne bağlı — saat kayması ~dakikalar); (b) giriş fiyatı backtest'teki
gibi son KAPANMIŞ günlük kapanış (Pazar); değerlendirme 15dk mumlarla
(backtest günlükle — canlı daha hassas, stop tespiti daha erken olabilir);
(c) günlük mumlar haftada bir evren çapında çekilir (~150 istek), ana
taramadan SONRA — şampiyon zamanlamasına dokunmaz; (d) hafta anahtarı
ISO (YYYY-Www), meta'da; başarısız geçit işaretlenmez → sonraki tarama
yeniden dener.

## S11 SIKIŞMA-KIRILIMI + S12 HACİM-KAPILI SEANS KIRILIMI — ÖN-KAYIT (2026-08-17, Serhat onayı "ikisiyle başla")
Kaynak: perakende araştırması (docs/perakende-arastirmasi-2026-08-17.md,
kısa liste #1 ve #2). Kurallar AŞAĞIDA DONDURULDU; parametre taraması yok,
tek kurulum. İkisi de doğrudan CANLI aday (S8/S9 deseni); hüküm her
zamanki gibi YALNIZ ileriye dönük veriden: ≥50 kapanmış küme + küme-CI.

### S11_SQUEEZE — oynaklık-sıkışması kırılımı (TTM/LazyBear ailesi)
- Veri: KAPANMIŞ 4H mumlar. BB(20, 2σ; popülasyon sapması) ve
  KC(20, 1.5 × SMA20(TrueRange)); orta bant ikisinde de SMA20(kapanış).
- Sıkışma AÇIK (bar i): BB tamamen KC içinde ⇔ 2σ < 1.5 × SMA20(TR).
- ATEŞLEME: son kapanmış 4H mum sıkışma KAPALI, bir önceki AÇIK ve biten
  AÇIK serisi ≥ 6 bar.
- Sıkışma aralığı: AÇIK serisi barlarının min-düşük / maks-yüksek bandı.
- Yön: 4H kapanış aralığın ÜSTÜNDE VE momentum > 0 → LONG; ALTINDA VE
  momentum < 0 → SHORT. Momentum (LazyBear tanımı birebir): son 20 barın
  d = kapanış − ort((HH20+LL20)/2, SMA20(kapanış)) serisine doğrusal
  regresyon, son noktadaki değer.
- Giriş: koşulun sağlandığı taramadaki 15dk kapanış. Stop: aralığın karşı
  ucu. Hedef: risk × 2. Zaman aşımı: 192 × 15dk (48s). Küme: standart
  (strateji + yön + 4H kovası). Tavan 15. S2'den yapısal fark: ham kanal
  kırılımı değil, SIKIŞMA ÖN KOŞULU tetikler.

### S12_RELVOL — göreli-hacim kapılı seans kırılımı (Zarattini uyarlaması)
- Çapa: 00:00 UTC. Açılış aralığı = günün İLK 4H mumu (00:00–04:00);
  mum KAPANMADAN işlem yok.
- HACİM KAPISI (işin yeni öğesi): açılış mumu hacmi ≥ 2.0 × önceki
  20 günün açılış-mumu hacim ortalaması (20 tam gün yoksa o gün sinyal
  yok).
- Giriş: gün içinde 15dk kapanış aralığın dışına çıkınca (kenar tetik:
  önceki kapanış beride). Yön = kırılım yönü; iki yön de serbest.
- Stop: aralığın karşı ucu. Çıkış: GÜN SONU 00:00 UTC (zaman aşımı,
  girişte kalan 15dk bar sayısı olarak hesaplanır); hedef sentetik
  erişilemez (risk × 100, S9 deseni). Günde yön başına TEK giriş:
  küme = takvim günü + yön (dedup bunu zorlar). Tavan 15.
- Dürüst not: Zarattini bulgusu ABD hissesi ORB'dir; kripto uyarlaması
  (7/24 piyasada 00:00 UTC seansı) TEST EDİLMEMİŞ bir transferdir —
  canlı ölçüm tam olarak bunu sınar.

## ÇIKIŞ LABORATUVARI (V0/V1) — ÖN-KAYIT (2026-08-17, Serhat onayı "başla")
Kaynak: perakende araştırması kısa liste #3 (ATR iz-süren çıkış) + midas
ikiz bulgusu (çıkış tasarımı girişten belirleyici; midas V4_IZ) + Kural 3b
(ikizde yeni ölçüm aleti doğdu → karşılığı burada kurulur).
SALT ÖLÇÜM ALETİDİR: kapanmış aday sinyalleri mum arşivinden YENİDEN
oynatılır; hiçbir karar/kayıt değişmez; motora, kilide, sayaçlara sıfır
dokunuş. Alet: app/services/exit_lab.py, rapor: /exitlab.
- V0_SABIT (kıyas çizgisi): motorun mevcut değerlendirme kuralı BİREBİR —
  stop/hedef/zaman aşımı; aynı mumda stop+hedef → LOSS (ambiguous).
  SADAKAT ŞARTI: V0 yeniden-oynatması defterdeki kayıtlı sonucu üretmek
  zorundadır; uyumsuzluk sayısı raporda görünür (ölçüm dürüstlüğü).
- V1_IZ (iz süren çıkış, Chandelier tarzı): giriş ve başlangıç stopu
  kayıttakiyle AYNI; hedef YOK (kâr koşturulur). Her kapanmış 15dk mumda
  SIRA: (1) önce mevcut stop vurulmuş mu bakılır — vurulduysa stoptan
  çıkılır; (2) sonra stop çekilir: LONG stop = max(önceki, mumun en
  yükseği − iz mesafesi); SHORT ayna (min, en düşük + iz). İz mesafesi =
  1 × başlangıç risk mesafesi (|giriş−stop|; çoğu stratejide k×ATR'ye
  eşdeğer). Muhafazakâr sıra bilinçli: aynı mumdaki yeni tepe o mumun
  stopunu kurtaramaz. Zaman aşımı kayıttaki timeout_bars ile AYNI
  (kapanıştan çıkış, EXPIRED).
- Maliyet modeli v0 AYNEN: 2×taker + STOP çıkışlarında slip (iz süren
  stop kârda da stop-emridir, slip uygulanır) + funding × tutuş.
- HÜKÜM KURALI (önceden ilan): sinyal başına fark d = V1_net − V0_net;
  kümesi sinyalin kendi cluster_id'si. Bir stratejide ≥50 kapanmış küme
  VE fark serisinin küme-CI alt sınırı > 0 → "V1 o strateji için üstün"
  ilan edilir ve v2 TASARIM GİRDİSİ olur (motora asla doğrudan girmez).
  Küme-CI üst sınırı < 0 → V0 üstün. Arada → belirsiz, veri birikir.
- Parametre taraması YOK: iz mesafesi 1×R tek değerdir; başka katsayı
  denemek YENİ ön-kayıt ister.

### S-ATT1 UYGULAMA EKİ — veri koşusundan ÖNCE donduruldu (2026-08-17, "başla")
Ana kurallar 2026-08-16 ön-kaydında; burada yalnız uygulama serbestlikleri
kapatılır (sonuç görülmeden):
- Görüntüleme verisi: Wikimedia REST, en.wikipedia, agent=USER (bot
  trafiği dışarıda), all-access. Eşleme tablosu: data/wiki-eslesme.csv
  (elle kürasyon = 1. kontrol; indiricinin makale-varlık doğrulaması ve
  404 raporu = 2. kontrol; bulunamayan makale DÜRÜSTÇE dışlanır).
- z-skoru: x = log(1+görüntüleme); taban = önceki 90 takvim günü
  (en az 81 gün veri şartı; popülasyon sapması; sapma 0 → sinyal yok).
- 24s getiri: D gününün son 4H kapanışı ÷ (D−1)'in son 4H kapanışı − 1;
  0 < getiri ≤ +0.25 şartı.
- T+1 dürüstlüğü: giriş, D+1 gününün İLK 4H mumunun AÇILIŞI (gün D
  verisi ancak gün bitince tamdır; aynı-gün girişi bakış-öncesi olurdu).
- Stop: giriş − 2 × ATR(14, 4H; girişten önceki son kapanmış mumda).
  Zaman-stopu: 18 × 4H bar (3 gün), kapanıştan. Hedef yok.
- Yeniden-giriş yasağı: sembol başına giriş gününden itibaren 7 takvim
  günü. Küme = SİNYAL takvim günü (aynı gün tüm semboller TEK küme —
  dikkat şokları günler arasında değil gün içinde korelelidir).
- Maliyet: v0 aynen (2×taker + stop çıkışında slip + funding×tutuş),
  R paydası stop mesafesi. Hüküm merdiveni S5 ile aynı (tek atış).
