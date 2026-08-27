# V2 ŞAMPİYON TASARIMI — GİRDİ DOSYASI (açılış: 2026-08-18, Serhat onayı)

Bu dosya TASARIM ÇALIŞMA ALANIDIR — kural değildir, ön-kayıt değildir.
v2 tasarımı bittiğinde kurallar docs/ideas.md'ye ÖN-KAYITLA girer ve v2,
sıfırdan sınava tabi YENİ ADAY olur. app/strategies/ (v1) donmuş kalır;
KİLİT-2 sınavı bu dosyadan etkilenmez.

## Neden v2? (güncelleme 2026-08-20 — HÜKÜMLER KESİNLEŞTİ)
- v1 şampiyonu KİLİT-1'İ ve KİLİT-2'Yİ geçemedi (kilit-2: yanlışlama #2,
  maksDD 20.15R > 20R, 2026-08-20 tutanağı). Üçüncü kilit YOK; v1 artık
  VERİ KAYNAĞI. v2 tek yol.
- S1 doğrulaması da geçemedi (90 küme, net −24.4R) — trend bileşeni v2'ye
  "kanıtlı" değil "denenmiş-belirsiz" statüsüyle girer (aşağıdaki madde 4
  buna göre okunmalı).
- Aday mezarlığı: S3 (ort. dönüş), S6 (süpürme), S4 (ham funding),
  S7 (Wyckoff) — hepsi ilan edilmiş koşulla, canlı veriyle.
- Rallide öne çıkan (2026-08-20): S2 +47.3R (CI alt −0.055, Faz-1'e en
  yakın aday), S11 +12R (erken), S12 +6.2R (erken). Kırılım ailesi v2
  iskeletinin bir numaralı adayı hâline geldi.

## ÖLÇÜLMÜŞ girdiler (v2 bunları merkeze alır)
1. **Yön/rejim asimetrisi (v1'in en net dersi):** kilit-2 ara verisi
   LONG −49.3R / SHORT +31.5R (net). v1 rejime rağmen iki yöne de aynı
   iştahla bakıyor. v2'de rejim uyumu süs değil, İSKELET olmalı.
2. **P4 OI-kohort bulgusu:** kırılımda dOI(24s) ≥ +%5 filtresi backtestte
   +22R'yi −171R'den ayırdı (BELİRSİZ ama çarpıcı). Canlı gölge-kohort
   sürüyor; v2 kırılım girişine "katılım kapısı" adayı.
3. **Çıkış laboratuvarı (V0 sabit / V1 iz süren):** hüküm kuralı
   ön-kayıtlı, veri birikiyor. v2'nin çıkış tasarımı bu hükümle seçilir
   ("çıkış girişten belirleyici" — midas ikiz bulgusuyla uyumlu).
4. **S1 gözlemi (GÜNCEL 2026-08-27):** doğrulama penceresi 2026-08-20'de
   GEÇEMEDİ hükmüyle mühürlendi. Rakamı sonradan şişti (+89.9R) ama
   küme-CI alt sınırı hiçbir gün sıfırı geçmedi (bugün −0.045) — trend
   bileşeni v2'ye "kanıtlı" değil, "denenmiş-belirsiz" girer.
5. **S11/S12 erken verisi:** sıkışma önkoşulu ve göreli-hacim kapısı
   (perakende araştırması kısa listesi) canlıda; küme dolunca v2 girişine
   aday öğe olurlar.

## ⭐ GİRDİ 0 — MALİYET DAYANIKLILIĞI (ölçüldü 2026-08-27, Serhat onayı)

**Bu, v2'nin BİRİNCİ tasarım kısıtıdır.** Diğer girdiler "hangi giriş?"
sorusuna cevap arar; bu girdi "giriş ne olursa olsun hayatta kalır mı?"
sorusunu cevaplar.

### Bulgu: ölenlerin çoğunu kötü giriş değil, MALİYET öldürdü
Canlı defterden (2026-08-27) ham (maliyetsiz) ve net R yan yana:

| Motor | Ham R | Net R | Maliyet/işlem | Durum |
|---|---|---|---|---|
| Şampiyon | **+52.66** | −33.55 | **0.216R** | kilit-1 ve -2 GEÇEMEDİ |
| S7 Wyckoff | **+30.11** | −246.52 | **0.359R** | EMEKLİ (CI üst < 0) |
| S3 Ort.Dönüş | **+38.70** | −217.27 | **0.261R** | EMEKLİ |
| S6 Süpürme | −4.40 | −102.64 | 0.208R | EMEKLİ |
| S1 TSMOM | +143.36 | +111.72 | 0.040R | yaşıyor |
| S2 Donchian | +88.90 | +65.42 | 0.043R | yaşıyor |
| S12 RelVol | +22.12 | +15.16 | 0.037R | yaşıyor |
| S11 Squeeze | +17.41 | +16.47 | **0.027R** | yaşıyor |
| S8 FundSqueeze | +6.80 | +4.92 | 0.017R | yaşıyor |

Şampiyon, S7 ve S3'ün girişleri HAM olarak ARTIDA. Net'i eksiye çeviren
maliyet: şampiyonda 86R, S7'de 277R, S3'te 256R. Yaşayan adayların
maliyet yükü 5–13 KAT daha düşük.

### Mekanizma: aritmetik, gizem yok (DOĞRUDAN ÖLÇÜLDÜ)
Maliyet modeli v0'da komisyonun R cinsinden yükü
`2 × taker / stop_frac`; yani **R paydası (stop mesafesi) küçüldükçe
maliyet büyür**. Gerçek ekonomi: aynı $ riski için dar stop = büyük
pozisyon = büyük komisyon. Defterdeki son 200 kayıttan ölçülen medyan
stop genişlikleri ve bunun ima ettiği komisyon yükü:

| Motor | Medyan stop (fiyatın %'si) | Teorik komisyon/işlem |
|---|---|---|
| S8 | 15.12% | 0.007R |
| S11 | 11.18% | 0.010R |
| S1 | 8.91% | 0.012R |
| S2 | 8.68% | 0.013R |
| S12 | 6.30% | 0.017R |
| S9 GECE | **0.62%** | **0.178R** |

Emekli motorlar için stop genişliği doğrudan ölçülemedi (yeni kayıt
üretmiyorlar); gözlenen maliyetten geri-çözüldüğünde ~%0.4–0.8 bandına
düşüyor — hepsi 15dk-ATR veya yapısal (dar) stop kullanıyordu. NOT:
gözlenen ortalama maliyet, medyan stoptan hesaplanandan yüksektir
(1/stop_frac dışbükeydir; dar stoplu uçlar ortalamayı yukarı çeker) —
bu yüzden iki tablo birebir eşleşmez, büyüklük sınıfı eşleşir.

### v2 için tasarım sonucu (ön-kayıt: docs/ideas.md 2026-08-27)
1. **Maliyet bütçesi ZORUNLU:** v2'nin stop mesafesi, maliyet modeli
   v0'a göre hesaplanan maliyet/işlem ≤ **0.05R** olacak şekilde
   seçilir. Bu, veriden türetilmiş bir eşik DEĞİL, tasarım anında
   formülden hesaplanabilen bir kısıttır (kanıt gerektirmez, aritmetik).
2. **Dar stop yasağı:** 15dk-ATR veya "fitilin hemen ötesi" tipi stoplar
   v2'ye giremez — bu ailenin dört mezarı var.
3. **Çıkış tasarımı buna bağlıdır:** maliyet işlem başına ~sabit
   olduğundan, ortalama kazancı büyütmek (iz süren çıkış) maliyet
   oranını doğrudan düşürür. Çıkış laboratuvarı hükmü bu girdiyle
   BİRLİKTE okunacak.
4. **Az ve güçlü işlem:** 800 işlemde 0.14R, 100 işlemde 0.5R'den çok
   daha kırılgandır (maliyet her işlemde tekrar alınır).

### YASAK (kayda geçer)
Bu bulgu, maliyet modelini yumuşatmak için KULLANILAMAZ. "Maliyet
modeli v0 gevşetilse şampiyon artıya geçer" akıl yürütmesi, sonuca
bakıp kural değiştirmektir (Kural 4/5 ihlali) ve projenin tüm
hükümlerini geçersiz kılar. Maliyet gerçektir; motor maliyete
DAYANACAK şekilde tasarlanır.

## Dış denetim v2 düzeltme listesi (dis-denetim-2026-08-17.md)
- B1: hacim oranı, tetik barı ANINDAKİ SMA20'ye göre hesaplanmalı
  (karar 2026-08-17: v1'de düzeltilmez, v2'de doğru kurulur).
- RSI: sıfır-kayıp penceresinde 100 (50 değil) — confluence doğruluğu.
- Sweep taraması tüm pivot adaylarını gezmeli (tek-pivot daralması v1
  MVP kısıtıydı).
- Sabitler (_MAX_BREAK_AGE, _RETEST_TOL, eğim penceresi) parametreleşir
  ve ideas.md ön-kaydında DONDURULUR (tarama değil, tek kurulum).

## MEZARLIK — v2'de yeniden DENENMEZ (kanıtla ölenler)
Ortalamaya dönüş (S3 −217R), likidite süpürme dönüşü (S6 −103R),
ham funding taşıması (S4 −35R, CI üst<0), Wyckoff spring+test (S7,
CI üst<0), OI-boşaltma dip alımı (P1, backtest), kesitsel momentum +
TSM sepeti (90g backtest), Wikipedia dikkat şoku (S-ATT1, backtest
net −22R, CI üst<0). Grid/martingale ve kara-kutu ML zaten kapı dışı
(perakende raporu tuzak listesi).

## Süreç (sıra)
1. Çıkış laboratuvarı + S1 doğrulama + P4 kohort hükümlerini bekle/topla
   (veri kendiliğinden birikiyor; acele karar yok).
2. Tasarım taslağı: rejim iskeleti + giriş ailesi (kanıtlı öğelerden) +
   çıkış (lab hükmüyle) + katılım kapıları (hacim/OI).
3. ideas.md ÖN-KAYIT (kurallar donmuş, tek kurulum, tarama yasak).
4. Aday olarak sıfırdan sınav (Faz-1: ≥50 küme + küme-CI alt > 0).
