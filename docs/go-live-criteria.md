# GERÇEK PARAYA GEÇİŞ KRİTERLERİ — ÖN KAYIT
Yazım tarihi: 2026-07-29 · Bu dosya kriter YUMUŞATMAK için değiştirilemez.
(Sıkılaştırma serbest. Değişiklik = yeni tarihli ek bölüm; eskisi silinmez.)

Kaynak: 4 bağımsız LLM değerlendirmesinin yakınsaması (docs/council-review-2026-07.md).

## Faz 1 — Mikro-canlı (ÖLÇÜM amaçlı; kâr amaçlı DEĞİL)
Tamamı sağlanmadan başlanamaz:
- [ ] Maliyet motoru (v0+) aktif; E_net raporlanıyor
- [ ] ≥100 maliyet-modelli sonuçlanan doluş VE ≥30 takvim günü gölge
- [ ] ≥2 belirgin BTC rejimi kapsandı (boğa/ayı/yatay'dan ikisi)
- [ ] Küme-bazlı blok-bootstrap %95 CI(E_net) alt sınırı > 0
- [ ] Portföy ısı motoru (P1) canlı ve kapasite simülasyonunda PF ≥ 1.3
- [ ] Dead-man's switch + /health izleme aktif
Boyut: ≤500 USDT · risk ≤%0.5/işlem · ≤2 slot · kaldıraç ≤3x · yalnız
gate-uyumlu sinyaller. Amaç: 50 canlı doluşta gölge-canlı sapması ölçümü
(medyan |sapma| < 0.15R hedefi).

## Faz 2 — Küçük canlı
- [ ] Faz 1 sapma hedefi tutturuldu
- [ ] ≥200 sonuçlanan doluş VEYA ≥80 küme; ≥3 rejim (her birinde ≥40)
- [ ] E_net ≥ +0.20R ve CI alt > 0 (küme bootstrap)
- [ ] LONG ve SHORT ayrı karneler; zayıf bacak ya pozitif ya bilinçli mikro-boyut
- [ ] MaksDD (gerçekçi sim) ≤ 15R/100 işlem
Boyut: ≤2.000 USDT · risk ≤%0.5 · ≤3 slot.

## Faz 3 — Ölçek
- [ ] Faz 2'de 60 gün tutarlılık; kill-switch kuralları yazılı ve test edilmiş
  (günlük −4R / haftalık −8R / son-20 işlem E<0 → dur)
- [ ] Risk-of-ruin (%1 risk, E_net, σ) < %5 @ 1 yıl
Boyut kademeli; risk asla >%1/işlem.

## Her fazda geçerli
Gölge motor paralel çalışmaya devam eder (canlı-gölge farkı = gerçek maliyet
ölçümü). Tüm sonuçlar için: geçmiş performans gelecek garantisi değildir;
hiçbir şey yatırım tavsiyesi değildir.
