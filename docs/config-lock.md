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

## v3.6 Ölçüm Paketi notu (eklendi: 2026-08-02 — kilit İHLAL EDİLMEDİ)
Konsey 2. turunun tüm P0 talepleri ÖLÇÜMDÜR, davranış değildir; motor aynı
sinyalleri aynı eşiklerle üretmeye devam eder. Bu commit'te eklenenler:
küme-blok bootstrap CI (resmî CI; işlem-düzeyi CI raporlardan kaldırıldı),
NOT_FILLED anatomisi (boşluk/temas/geçiş + kaymalı hayalet R), teşhis
dağılımları (/measurement), MFE/MAE kaydı, kapı geçiş/TTL günlüğü, gerçek
funding yakalama (maliyet v1 VERİSİ — v0 modeli kilitli kalır, başlık
metrikleri v0 ile hesaplanmaya devam eder), güven etiketi permütasyon testi
(sonuç negatifse etiket kilit-v2'de kaldırılır).
Faz-1 eşiği go-live-criteria.md 2026-08-02 ekiyle sıkılaştırıldı:
≥50 kapanmış küme + küme-CI alt sınırı > 0. Sıkılaştırma kurala uygundur.

## v3.6 düzeltme notu (2026-08-02, aynı gün): küme sayacı hatası
İlk v3.6 sürümünde küme-bootstrap, `cluster_id` etiketi BOŞ olan kayıtları
"kendi başına küme" sayıyordu. Etiket kolonu v3.5'te eklendiği için ondan
önce doğan / eski gist yedeğinden geri yüklenen 84 kayıt etiketsizdi ve
sayaç 53 küme gösteriyordu — gerçek sayı 16'ydı. Bu, konseyin eleştirdiği
"bağımsız kanıt şişirmesi" hatasının kodun içinde tekrarıydı.
Düzeltme (aynı gün, veri kaybı yok):
- Etiketler geriye dönük üretildi: yön + 4H penceresi zaten kayıtlıydı
  (entry_candle_ts, yoksa created_utc); canlı yolla AYNI fonksiyon kullanılır.
- Etiketi olmayan kayıt artık kümeden SAYILMAZ; sayısı `unclustered_excluded`
  ile raporlanır ve panoda görünür (sessiz kayıp yok).
- Ölçüm kolonları (hypo/nf/mfe/mae/funding/fill_ts/ambiguous) yedek
  payload'ına eklendi; önceden her restore'da sessizce siliniyorlardı.
Düzeltme sonrası gerçek tablo: 33 küme (114 işlem), kilit sonrası 21 küme
(67 işlem). Faz-1: 21/50. Küme-CI kilit sonrası [−0.41, +0.70] — sıfırı
kesiyor, kapı KAPALI.

## v3.6-kritik düzeltme (2026-08-02): dolum öncesi mumlar sonucu belirliyordu
**Bulgu:** ELSAUSDT #390 panoda WIN +1.58R göründü. Botun kendi mum arşiviyle
yeniden oynatınca ortaya çıktı: sinyal 02:12'de doğdu, fiyat 02:00–04:00
arasında zaten TP1'in ÜSTÜNDEYDİ, giriş bölgesine ancak 04:15'teki çöküşte
indi ve orada doldu. Yani kazanç yazılan hareket, girişten önce yaşanmıştı.

**Kök neden:** `_evaluate_signal`, sinyal önceki turda dolduğunda `fill_price`'ı
DB'den okur, dolum dallanmasını atlar ve sonuç döngüsü `entry_candle_ts`'ten
başlar. Dolum öncesi mumlar TP/STOP'a değmiş sayılıyordu. Sabahki MFE/MAE
düzeltmesi yalnız gezinme istatistiğini korumuştu; **karar satırları
korumasız kalmıştı.**

**Yön:** LONG'ta sistematik olarak UYDURMA WIN üretir (fiyat TP'ye koşup sonra
bölgeye iner). SHORT'ta ayna durum. Kaçırılan hareket kazanç gibi kaydedilir.

**Ölçülen kirlilik (arşiv kapsamındaki 7 gecikmeli dolum):** 3 kayıt kirli
(#382, #359, #341 — hepsi WIN), + #390. Oran ~%43–50, tamamı WIN yönünde.

**Düzeltme:** sonuç kontrolü `fill_ts` ile kapılandı; dolum öncesi mum karara
giremez. Regresyon testi hatalı kodda "uydurma sonuç yazıldı: WIN" verir.
**Onarım:** gecikmeli dolan kapanmış kayıtlar arşiv mumlarıyla denetlenir;
kirli olan yeniden açılır ve düzeltilmiş motor dolumdan itibaren yeniden karara
bağlar. Mumu arşivde olmayan kayıt `prefill_repaired=2` ile işaretlenir —
sessizce doğru varsayılmaz.

**Sonuç:** kilit öncesi/sonrası tüm başlık rakamları bu onarımdan sonra
yeniden okunmalıdır. Faz-1 sayacı etkilenir (bazı kayıtlar geçici olarak
açığa döner).

## v3.6: kalıcı bağımsız sonuç denetimi (2026-08-02)
Dört ölçüm hatasının dördüncüsünü kod değil **insan** yakaladı (ekran
görüntüsündeki grafik tutarsızlığı). Bu, sürecin eksiğiydi: kayıtları ham mum
arşiviyle karşılaştıran hiçbir otomatik kontrol yoktu.

`app/services/verifier.py` — tracker'ın döngüsünü KULLANMAYAN, ayrı ve sade
bir yeniden-oynatma. Aynı hata iki bağımsız yolda birden bulunamayacağı için
uyuşmazlık gerçek bir sinyaldir. Kurallar kasten en muhafazakâr hâlde:
doluş öncesi mum asla karara giremez; aynı mumda TP ve STOP varsa AMBIGUOUS.

- `/verify` ve `/measurement → outcome_audit`: her an denetlenebilir.
- Tarayıcı döngüsü ~6 saatte bir otomatik denetler; uyuşmazlıkta ERROR log
  ve `gate_log`'a `audit_mismatch` kaydı düşer.
- Açılışta `_repair_bad_outcomes()`: arşivle çelişen kapanmış kayıtları
  yeniden açar, düzeltilmiş motor doluştan itibaren yeniden karara bağlar;
  denetlenemeyen kayıt `prefill_repaired=2` ile işaretlenir.

**İlk tam tarama sonucu (156 denetlenebilir kapanmış sinyal):** 5 uyuşmazlık,
hepsi kayıt=WIN / denetçi=LOSS — #382, #359, #341, #57, #6. Brüt şişme
yaklaşık +14.7R. Onarım sonrası başlık rakamları yeniden okunmalıdır.
