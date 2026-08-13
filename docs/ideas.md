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
