# V2 ŞAMPİYON TASARIMI — GİRDİ DOSYASI (açılış: 2026-08-18, Serhat onayı)

Bu dosya TASARIM ÇALIŞMA ALANIDIR — kural değildir, ön-kayıt değildir.
v2 tasarımı bittiğinde kurallar docs/ideas.md'ye ÖN-KAYITLA girer ve v2,
sıfırdan sınava tabi YENİ ADAY olur. app/strategies/ (v1) donmuş kalır;
KİLİT-2 sınavı bu dosyadan etkilenmez.

## Neden v2? (durum, 2026-08-18)
- v1 şampiyonu kilit-1'i geçemedi; kilit-2 ara görünümü negatif eğilimli
  (E_net −0.07R, CI [−0.43,+0.32]; hüküm HENÜZ yok — bot ilan edecek).
- Aday mezarlığı büyüdü: S3 (ort. dönüş), S6 (süpürme), S4 (ham funding),
  S7 (Wyckoff) — hepsi ilan edilmiş koşulla, canlı veriyle.
- Elde ilk pozitif-yönlü bulgular birikti (aşağıda). Tasarımın zamanı.

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
4. **S1 gözlemi:** tek net-pozitif veteran (+11.8R, CI alt −0.10).
   Trend/TSMOM bileşeni v2'de giriş ailesi adayı; doğrulama penceresi
   sürüyor, hükmü beklenir.
5. **S11/S12 erken verisi:** sıkışma önkoşulu ve göreli-hacim kapısı
   (perakende araştırması kısa listesi) canlıda; küme dolunca v2 girişine
   aday öğe olurlar.

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
