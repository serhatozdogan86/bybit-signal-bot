# KONFİG KİLİDİ — v3.5-P1
İlan: 2026-07-29 · Bu commit itibarıyla motor/risk parametreleri DONMUŞTUR.

Kilit kapsamı (değiştirilemez; yalnız kritik bug fix istisna, o da bu dosyaya
tarihli not düşülerek):
- Boru hattı eşikleri: ADX≥20, hacim ≥1.5×ort(20), RR bandı 2.0–6.0
- Market gate: BTC 4H EMA200, ±%0.5 histerezis, 2×4H kapanış teyidi,
  fail-closed (TTL 2sa), karşı-olgu takibi
- Gölge kuralları: giriş 6sa / izleme 48sa, aynı-mum → LOSS (ambiguous=1)
- Maliyet modeli v0: 2×taker %0.055 + stop kayması 5bps + funding %0.01/8sa işaretli
- Portföy ısısı: aynı yön ≤4 açık, küme ≤2, eşzamanlı ≤8
- Evren: 24s ciroya göre top-150, günlük rotasyon

Faz-1 gölge sayacı (bkz. go-live-criteria.md) BU KİLİT ANINDAN başlar.
Kilit sonrası her sinyal engine_sha ile damgalıdır; kilit-öncesi ve sonrası
kohortlar ayrı değerlendirilir. Eşik "iyileştirme" fikirleri docs/ideas.md'ye
yazılır, bir SONRAKİ kilit penceresinde topluca değerlendirilir.

## Yanlışlama Kriterleri (eklendi: 2026-07-29, aynı gün — pencere başlamadan)
Ön-kayıt simetriktir: yalnız başarı değil, başarısızlık da önceden tanımlıdır.
Aşağıdakilerden HERHANGİ BİRİ tetiklenirse deney resmen DÜŞER, kilit erken
açılır, dört kohort + engine_sha ile otopsi yapılır, yeni hipotezle kilit v2
ilan edilir. Tetiklenmedikçe eşiklere dokunulmaz — bunlar erken-DURDURMA
kriterleridir, ayar izni değildir.

1. KENAR ÖLÜMÜ: ≥60 maliyet-modelli sonuçlanan doluşta küme-bazlı bootstrap
   %95 CI(E_net) ÜST sınırı < 0 → pozitif kenar istatistiksel olarak
   dışlanmış demektir; beklemek anlamsız.
2. RİSK PROFİLİ İHLALİ: gerçek kohortta maliyet-modelli maksDD > 20R →
   kenar var olsa bile taşınamaz.
3. AÇLIK: kilitten itibaren 30 günde < 40 sonuçlanan doluş → kilitli motor
   ölçüm için bile yeterli veri üretemiyor; deney tasarımı revize edilir.

Denetim: her "durum" raporunda bu üç kriter kontrol edilir (bootstrap dahil);
tetiklenme yoksa rapora tek satır "yanlışlama: temiz" düşülür.
