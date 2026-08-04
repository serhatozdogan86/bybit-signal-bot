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
