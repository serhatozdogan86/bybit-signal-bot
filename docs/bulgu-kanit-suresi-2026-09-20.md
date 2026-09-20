# ⭐ BULGU — KANIT SÜRESİ: standardımız kaç yıl veri istiyor? (2026-09-20)

**Bu, projenin iki yılda bulduğu en önemli tek şey olabilir.** Hiçbir
kuralı değiştirmiyor; ama iki yıldır aldığımız sonuçların ANLAMINI
değiştiriyor.

## Ölçülen (portföy, /portfolio ilk koşu)

| Ölçü | Değer |
|---|---|
| Üye | S1, S2, S8, S11, S12 (üye kuralı getiriye bakmaz) |
| İşlem | 4.324 |
| Portföy bloğu (yön+gün) | 96 |
| Net | **+118.53R** |
| Beklenti | **+0.027R/işlem** |
| Küme-CI | **[−0.095, +0.154]** → sıfırı içeriyor |
| Kapı | **GEÇMEDİ** |
| Blok başına oynaklık | 0.622 |
| CI alt sınırı > 0 için gereken blok | **2.039** |

## Bundan çıkan aritmetik

Günde ~1.92 blok üretiyoruz (2 yön × gün). 2.039 blok = **1.062 gün ≈
2,9 YIL.**

### Kova seçimi bu sonucu değiştirmiyor
Portföy bloğunu bilinçli olarak kaba seçmiştim (yön + takvim günü).
"Acaba fazla mı muhafazakâr davrandım, 4 saatlik kova daha mı adil?"
diye kontrol ettim:

| Kova | Gereken blok | Blok/gün | Süre |
|---|---|---|---|
| Günlük (kullanılan) | 2.039 | 1,92 | **2,9 yıl** |
| 4 saatlik (kontrol) | 12.742 | 12 | **2,9 yıl** |

Aynı. Beklenen bir sonuç: kova boyutu verinin **bilgi miktarını**
değiştirmez, yalnız onu nasıl paketlediğimizi. Yani muhafazakâr
seçimim sonucu bozmamış — rahatlatıcı.

## GENEL KURAL (bunu bilmiyorduk)

Bir stratejinin kenarını %95 güvenle kanıtlamak için gereken süre,
yaklaşık olarak:

> **süre (yıl) ≈ (1,96 / yıllık Sharpe)²**

| Yıllık Sharpe | Kanıt için gereken süre |
|---|---|
| 0,5 | 15,4 yıl |
| 0,8 | 6,0 yıl |
| 1,0 | **3,8 yıl** |
| 1,5 | 1,7 yıl |
| 2,0 | 1,0 yıl |

Portföyümüzün ima ettiği yıllık Sharpe ≈ **1,15** → 2,9 yıl. Ölçümle
birebir tutarlı.

## ⭐ BUNUN ANLAMI: "geçemedi" ile "kötü" AYNI ŞEY DEĞİL

Bugüne kadar her motor için "sınavı geçemedi" dedik. Şimdi iki farklı
şeyi ayırmamız gerekiyor:

**A) KANITLI KÖTÜ** — küme-CI'nin ÜST sınırı sıfırın altında. Bunlar
gerçekten negatif; tartışma yok:
şampiyon (üst −0.028), S7 [−0.440,−0.194], S3 [−0.327,−0.110],
S6 [−0.373,−0.055], S9 [−0.756,−0.254].

**B) KANITLANAMAMIŞ** — CI sıfırı içeriyor. Bunlar "kötü olduğu
gösterilmiş" DEĞİL, "iyi olduğu gösterilememiş":
S1 [−0.051,+0.133], S2 [−0.075,+0.142], S8 [−0.084,+0.119],
S11 [−0.132,+0.259], S12 [−0.169,+0.150].

B grubunun pencereleri 2 ay sürdü. Bu büyüklükte bir kenar için
gereken süre ~3 yıl. **Yani deneyi, olumlu sonuç veremeyeceği bir
süreyle kurmuşuz.** İki yıllık "her motor battı" tablosunun bir kısmı
motorların kötülüğü değil, ölçüm süresinin kısalığıdır.

## ⚠️ BU BİR GEVŞETME GEREKÇESİ DEĞİLDİR

Kanıt eşiği DÜŞÜRÜLMEZ. "Nasılsa kanıtlanamıyor, o zaman daha zayıf
kanıtla yetinelim" demek, bu projeyi değerli kılan tek şeyi yok eder —
ve zaten A grubu gösteriyor ki standart gerçek kötüyü yakalıyor.
Bulgunun doğru kullanımı: **beklentiyi ve takvimi gerçekçi yapmak**,
eşiği aşağı çekmek değil.

## 50-KÜME KAPISI PORTFÖYE UYMUYOR (süreç uyarısı)

Ön-kayıtladığım portföy kapısı "≥50 küme + CI alt > 0" idi. Günlük
kovayla 50 bloğa **26 günde** varılır; o noktada CI yarı-genişliği
~0.172 olur, yani CI [−0.145, +0.199] — sıfırı içermesi neredeyse
garantidir.

**Yani pencereyi bu kapıyla açarsak, 26 gün sonra ANLAMSIZ bir
"geçemedi" üretiriz.** Bu hüküm değil, güçsüzlüktür. 50-küme eşiği
motor başına 4 saatlik kümeler için tasarlanmıştı; kaba bloklu bir
portföye olduğu gibi taşınamaz.

DÜZELTME (pencere açılmadan ÖNCE kararlaştırılmalı): portföyün
örneklem gereksinimi GÜÇ HESABINDAN türetilir (yukarıdaki aritmetik;
getirilerden değil, oynaklıktan) ve ÖN-KAYITLA sabitlenir.

## Önümüzdeki gerçek seçenekler

1. **Uzun pencere.** 3 yıllık bir pencere ilan et, sabırla bekle.
   Dürüst ama yavaş; ve 3 yıl boyunca rejim değişmeyeceği varsayımı
   kendi başına şüpheli.
2. **Daha BÜYÜK kenar ara.** Sharpe 2 → 1 yıl. Bu, "biraz daha iyi
   giriş" değil, nitelik olarak farklı bir kenar demek.
3. **Oynaklığı düşür.** Sharpe = kenar / oynaklık. Kenarı büyütmek zor,
   oynaklığı küçültmek bazen daha kolay (çıkış tasarımı, pozisyon
   boyutlandırma, aşırı korelasyonlu işlemleri elemek).
4. **Kararı "kanıt yok" ile kapat.** A grubu gerçekten kötü; B grubu
   kanıtlanamaz. Bu da geçerli bir bilimsel sonuçtur.

Bu dosya seçeneği SEÇMEZ — karar Serhat'ındır.
