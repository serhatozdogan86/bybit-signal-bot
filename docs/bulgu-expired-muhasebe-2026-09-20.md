# BULGU — Şampiyon ve adaylar AYNI standartla ölçülmüyor (2026-09-20)

**Durum: RAPOR EDİLDİ, DEĞİŞİKLİK YAPILMADI.** Şerit kuralı gereği
(uyuşmazlık bulunursa kod değiştirmeden önce rapor edilir) ve bu
uyuşmazlık MÜHÜRLÜ HÜKÜMLERİ etkilediği için, düzeltme Serhat'ın
kararına bırakıldı.

## Uyuşmazlık

`app/services/challengers.py` → `stats()` kendi notunda şunu iddia eder:

> "Golge adaylar - sampiyonla ayni maliyet modeli, **ayni kume-CI
> standardi, ayni 50-kume esigi**."

Bu iddia **doğru değil**. İki taraf farklı nüfus üzerinden ölçüyor:

| | Şampiyon (`signal_tracker.stats`) | Adaylar (`challengers.stats`) |
|---|---|---|
| Küme/CI nüfusu | `outcome IN ('WIN','LOSS')` | `outcome IN ('WIN','LOSS','EXPIRED')` |
| EXPIRED işlemler | **dışarıda** | **içeride** |

Şampiyon da EXPIRED üretir (`signal_tracker.py:656`, kapanışa göre R)
ama kendi küme sayımına ve CI'sine almaz. Adaylar alır
(`challengers.py:1125`).

## Neden önemli — ölçülebilir etki

Aday tablosunda (2026-09-20) küme sayısı, karara bağlanmış işlem
sayısından BÜYÜK olan adaylar var. Bu yalnız EXPIRED işlemler kümelere
girdiği için mümkündür:

| Aday | Küme | Karara bağlanmış (WIN/LOSS) | En az EXPIRED |
|---|---|---|---|
| S11_SQUEEZE | 91 | 42 | ≥ 49 |
| S9_GECE | 37 | 11 | ≥ 26 |
| S8_FUNDSQUEEZE | 218 | 159 | ≥ 59 |

**S11'in örnekleminin yarısından fazlası EXPIRED işlemlerden oluşuyor.**
S11'in 2026-09-05'te mühürlenen "50 kümede geçemedi" hükmü, şampiyon
standardı uygulansaydı o tarihte HENÜZ VERİLEMEZ olabilirdi — 50 küme
eşiğine o tarihte ulaşılmamış olabilirdi.

Aynı şey ters yönde de geçerli: aday kohortları 50-küme kapısına
şampiyondan daha ÇABUK varıyor, yani sınavlar erken açılıyor.

## Hangisi doğru? — açık soru, hükmü ben veremem

İki savunulabilir görüş var ve bu bir ölçüm felsefesi kararıdır:

- **EXPIRED sayılmalı (adayların yaptığı):** süre dolduğunda pozisyon
  gerçek bir fiyattan kapanır ve gerçek bir R üretir. Onu atmak, gerçek
  sonuçları defterden silmektir.
- **EXPIRED sayılmamalı (şampiyonun yaptığı):** EXPIRED, motorun tezinin
  gerçekleşmediği "karara bağlanmamış" bir sonuçtur; beklenti ölçümünü
  sıfıra doğru seyreltir.

**Hangisi seçilirse seçilsin, İKİSİ AYNI OLMALI** — bugünkü durum
savunulamaz, çünkü kod aynı olduklarını yazıyor ama değiller.

## Neyi DEĞİŞTİRMEDİM ve neden

Bu muhasebe mühürlü hükümleri (S11 09-05, S2 08-30, S1 08-20) besleyen
sayıları değiştirir. Mühürlü hükmü sonradan değişen bir muhasebeyle
yeniden hesaplamak, sonuç-bağımlı yeniden açmadır — projenin en temel
yasağı. O yüzden:

1. Kod DEĞİŞMEDİ.
2. Karar Serhat'ındır: hangi tanım, ve geçmiş hükümlere ne olacak.
3. Benim önerim: tanımı birleştir, **ileriye dönük** uygula, geçmiş
   hükümleri AÇMA. Yani düzeltme yeni pencerelerden itibaren geçerli
   olur; mühürler yerinde kalır.

## Kural 3 gereği yapılacak (karar verilince)

Düzeltmeden ÖNCE sınıfı kapatan test: "şampiyon ve aday küme nüfusu
aynı kuralı kullanır" — bugünkü kodda KIRMIZI vermeli.

## Kural 3b — ikiz depo

midas-signal-bot aynı iskeletten doğdu; aynı asimetri orada da
muhtemeldir. **AÇIK İŞ:** midas'ta şampiyon ve aday küme nüfusları
karşılaştırılmalı, sonuç ikiz-depo-notu'na yazılmalı (bulunmasa bile).
