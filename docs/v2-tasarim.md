# V2 ŞAMPİYON TASARIMI — GİRDİ DOSYASI (açılış: 2026-08-18, Serhat onayı)

Bu dosya TASARIM ÇALIŞMA ALANIDIR — kural değildir, ön-kayıt değildir.
v2 tasarımı bittiğinde kurallar docs/ideas.md'ye ÖN-KAYITLA girer ve v2,
sıfırdan sınava tabi YENİ ADAY olur. app/strategies/ (v1) donmuş kalır;
KİLİT-2 sınavı bu dosyadan etkilenmez.

## Neden v2? (güncelleme 2026-09-18 — v1 DOSYASI KAPANDI)
- v1 şampiyonu KİLİT-1'İ ve KİLİT-2'Yİ geçemedi (kilit-2: yanlışlama #2,
  maksDD 20.15R > 20R, 2026-08-20 tutanağı). Üçüncü kilit YOK; v1 artık
  VERİ KAYNAĞI. v2 tek yol.
- **2026-09-18 MÜHÜR — KENAR ÖLÜMÜ:** kilit kohortunda 197 kapanmış küme,
  küme-CI **ÜST** sınırı −0.028 (< 0) → ön-kayıtlı yanlışlama #1
  tetiklendi; maksDD 100.6R (20R tavanının 5 katı). v1'in umut statüsü
  SIFIRDIR. **Bağlayıcı sonuç: v2'nin hiçbir bileşeni v1'in canlı
  sonuçlarına "işe yarıyor" gerekçesiyle dayandırılamaz.** v1 defterinden
  alınabilecek tek şey ÖLÇÜM (maliyet, çıkış, rejim asimetrisi) —
  performans DEĞİL. Tutanak: config-lock.md 2026-09-18.
- S1 doğrulaması da geçemedi (90 küme, net −24.4R) — trend bileşeni v2'ye
  "kanıtlı" değil "denenmiş-belirsiz" statüsüyle girer (aşağıdaki madde 4
  buna göre okunmalı).
- Aday mezarlığı: S3 (ort. dönüş), S6 (süpürme), S4 (ham funding),
  S7 (Wyckoff) — hepsi ilan edilmiş koşulla, canlı veriyle.
- **S2 (2026-08-30 GÜNCEL):** seçim sınavını 08-21'de GEÇTİ (projede ilk)
  ama DOĞRULAMA penceresinde GEÇEMEDİ (54 küme, net −77.3R, CI üst sınırı
  bile eksi). Kırılım ailesi v2 iskeletinin "kanıtlı" adayı DEĞİLDİR;
  seçim geçişi ralli eseriydi. Üçüncü pencere yok.
- **Ayakta kalan umut (GÜNCEL 2026-09-05):** S11 seçim örneklemini
  DOLDURDU (50 küme) ve GEÇEMEDİ (net +14.9R, CI [−0.146, +0.488]);
  ölüm koşulu oluşmadı, koşmaya devam ediyor ama umut listesinden düştü.
  Sınava girmemiş TEK aday kaldı: S12 (39 küme, +18.1R). S9 ölüm eşiğine
  yakın (22 küme, CI üst +0.033).
- **UYARI (kayda geçer):** ≥50 kümeye ulaşan HER motor sınavı geçemedi.
  v2, "daha iyi bir giriş kalıbı" arayışıyla değil, GİRDİ 0 (maliyet) +
  çıkış tasarımı ekseninde kurulmalıdır — giriş kalıbı arayışının bu
  evrende getirisi ölçülmüş biçimde düşüktür.

## ÖLÇÜLMÜŞ girdiler (v2 bunları merkeze alır)
1. **Yön/rejim asimetrisi (v1'in en net dersi):** kilit-2 ara verisi
   LONG −49.3R / SHORT +31.5R (net). v1 rejime rağmen iki yöne de aynı
   iştahla bakıyor. v2'de rejim uyumu süs değil, İSKELET olmalı.
2. **~~P4 OI-kohort bulgusu~~ → ELENDİ (2026-08-29, canlı):** backtest
   artışlıyı +22R, artışsızı −171R göstermişti; canlı ileriye dönük veri
   TERSİNİ verdi (artışlı E_net −0.078 ≤ artışsız +0.078, ön-kayıtlı
   merdiven → ELENDİ). **OI katılım kapısı v2'den DÜŞTÜ.** Ders: backtest
   farkı çarpıcıydı ve yanlıştı — ön-kayıt disiplini bu taşı temele
   koymamızı engelledi. Katılım fikrinin HACİM ayağı (S12) yaşıyor.
3. **Çıkış laboratuvarı (V0 sabit / V1 iz süren) — ARA OKUMA 2026-09-05,
   HÜKÜM DEĞİL.** Tam defter yeniden oynatıldı: 5340 işlem, V0 sadakat
   uyumsuzluğu 0 (alet defteri birebir üretiyor). Fark = V1 − V0:

   | Motor | Küme | V0 net | V1 net | Fark E | Fark-CI | Durum |
   |---|---|---|---|---|---|---|
   | S1 | 295 | +72.75 | +14.51 | −0.047 | [−0.114, +0.013] | BELİRSİZ |
   | S2 | 285 | +30.56 | **−30.10** | −0.075 | [−0.164, +0.016] | BELİRSİZ |
   | S12 | 39 | +18.13 | −1.12 | −0.054 | [−0.182, +0.054] | veri birikiyor |
   | S11 | 50 | +14.94 | +17.23 | +0.026 | [−0.064, +0.113] | BELİRSİZ |
   | S8 | 123 | −6.67 | +1.20 | +0.035 | [−0.049, +0.126] | BELİRSİZ |
   | S7 (ölü) | 108 | −250.31 | −192.75 | +0.075 | [−0.032, +0.181] | BELİRSİZ |

   **Hiçbiri hüküm değildir** — tüm fark-CI'leri sıfırı içeriyor
   (ön-kayıtlı kural: ≥50 küme VE fark-CI alt > 0 → V1 üstün).
   YÖN BİLGİSİ (tasarım girdisi): trend/kırılım ailesinde (S1, S2, S12)
   1×R iz süren stop **geri tepiyor** — S2'yi artıdan eksiye çeviriyor.
   Mekanizma makul: bu motorlar uzun tutuşla yaşıyor; 1 risk mesafesinde
   peşi sıra gelen stop, olağan dalgalanmada pozisyonu erken atıyor.
   Perakende araştırmasının ve midas'ın "kazananı koştur" fikri bu
   evrene BU HALİYLE transfer olmuyor.

   **KAPSAM UYARISI:** yalnız TEK iz mesafesi (1×R) ölçüldü ve bu görece
   DAR bir iz. Sonuç "iz süren çıkış kötüdür" DEĞİL, "1×R iz bu
   motorlarda daha kötü"dür. Daha geniş iz (2×R, 3×R…) denemek YENİ
   ÖN-KAYIT ister — bu ara okumaya bakarak "en iyi mesafeyi" seçmek
   arka kapıdan parametre taramasıdır ve YASAKTIR (Kural 4/5).

   **METODOLOJİK KAYIT (kendi hatam, kayda geçer):** 2026-09-01'de bu
   aletin KISMİ örneklemine (son ~200 sinyalden 61 işlem, geri çekilme
   haftası) bakıp "V1 her stratejide önde" demiştim; aynı mesajda
   "örneklem taraflı, tek rejimden hüküm çıkmaz" diye uyarmıştım.
   Tam defter bunu TERSİNE çevirdi. Uyarı doğruydu, okuma yanlıştı.
   P4 dersiyle aynı sınıf: kısmi/geçmişe dönük bakış ile ön-kayıtlı tam
   ölçüm farklı sonuç verir; hüküm YALNIZ ikincisinden gelir.
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
net −22R, CI üst<0), **OI-onaylı kırılım filtresi (P4, canlı kohort
2026-08-29: artışlı E_net ≤ artışsız — backtest'in tersi)**.
Grid/martingale ve kara-kutu ML zaten kapı dışı (perakende raporu
tuzak listesi).

## Süreç (sıra) — GÜNCEL 2026-08-30
1. Bekleyen tek hüküm: **çıkış laboratuvarı** (V0/V1). S1, S2 ve P4
   hükümleri MÜHÜRLENDİ; S11/S12 küme biriktiriyor.
2. Tasarım taslağı: GİRDİ 0 (maliyet bütçesi) + rejim iskeleti + çıkış
   (lab hükmüyle) + katılım kapısı YALNIZ hacim (OI ayağı elendi).
   Giriş kalıbı arayışı ARTIK ANA EKSEN DEĞİL (yukarıdaki uyarı).
3. ideas.md ÖN-KAYIT (kurallar donmuş, tek kurulum, tarama yasak).
4. Aday olarak sıfırdan sınav (Faz-1: ≥50 küme + küme-CI alt > 0).
