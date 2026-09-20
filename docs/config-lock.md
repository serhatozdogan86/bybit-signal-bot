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

## Faz B başladı (2026-08-04): aday motoru — kilit İHLAL EDİLMEDİ
Şampiyon motoru, eşikleri ve ölçüm penceresi aynen sürüyor; `app/strategies/`
0 satır değişiklik. Eklenen her şey İZOLE gölge altyapısı:
- `app/services/challengers.py`: 5 aday (S1 TSMOM, S2 Donchian, S3 ortalamaya
  dönüş, S4 funding carry, S6 süpürme dönüşü), tek denetlenebilir
  değerlendirici (sabit stop+hedef+zaman aşımı; iz-süren çıkışlar v2),
  şampiyonla aynı maliyet sabitleri ve küme-CI standardı.
- Ayrı tablo (`challenger_signals`); izolasyon testle zorlanır:
  adaylar açıkken şampiyon `stats()` çıktısı bayt-bayt aynı.
- Veri: taramada zaten çekilen seriler; tek istisna tarama başına 1 toplu
  tickers çağrısı (S4 funding). Aday hatası taramayı düşüremez (fail-soft).
- `/challengers` endpoint'i + panoda "Adaylar" sekmesi (mobil).
- Bakış-öncesi yasağı adaylarda DOĞUŞTAN testli: giriş mumu ve öncesi karara
  giremez (şampiyonda dört kez tekrarlanan sınıf burada kapalı doğdu).


# ============================================================
# KİLİT AÇILDI — 2026-08-05, YANLIŞLAMA KRİTERİ #2 TETİKLENDİ
# ============================================================
Kriter (kilit günü yazılmıştı): "gerçek kohortta maliyet-modelli
maksDD > 20R → kenar var olsa bile taşınamaz."
**Ölçüm: kilit sonrası kohortta maksDD 35.58R.** Eşik iki katına yakın
aşıldı. Kural gereği ölçüm penceresi burada KAPANIR.

## Hüküm
Şampiyon (breakout_retest) Faz-1'i GEÇEMEDİ. 41/50 kümede durduruldu;
kalan 9 küme sonucu değiştirmezdi — düşüş kriteri kenardan bağımsızdır.
Kilit sonrası: 102 işlem, %28 WR, net **−7.72R** (zirve +23.1R → dip −7.7R).
Diğer iki kriter tetiklenmedi (kenar ölümü: CI üst sınırı +0.37 hâlâ pozitif;
açlık yok).

## Otopsi — kayıp nerede yoğunlaştı
| Eksen | Bulgu |
|---|---|
| Güven etiketi | MEDIUM: 40 işlem, %18 WR, **−20.8R**. HIGH: 24 işlem, %29, +0.3R |
| Kurulum | breakout_retest −24.4R; sweep_reclaim (5 işlem) +1.7R |
| Stop mesafesi | dar (<%0.75): −11.5R · orta: −3.0R · geniş (>%1.5): **+6.8R** |
| Plan RR | RR 2–3: **−14.2R** · RR 3–4: +4.1R · RR≥4: +2.4R |
| Zaman | 08-02 tek başına −16.2R (20 işlem, %10 WR) |
| Küme | En kötü 3 küme −16.3R; çıkarılsa net +8.6R |

**Kök neden (tek cümle):** motor kaybetmedi, RİSK YOĞUNLAŞMASI kaybettirdi.
41 kümenin 3'ü toplam düşüşün yarısını üretti; 08-02'de 8 farklı kümede
20 pozisyon aynı anda açıldı ve gün −16.2R kapandı. Küme-içi ısı limiti
(2) vardı ama **kümeler arası** korelasyon limiti yoktu.

## "Ne olsaydı" — geriye dönük, TEK değişken, aşırı iyimser
| Senaryo | n | net | maksDD |
|---|---|---|---|
| Gerçek | 102 | −7.72R | 35.58R |
| RR≥3 **ve** stop≥%0.75 | 41 | **+9.20R** | 14.30R |
| Yalnız geniş stop (>%1.5) | 40 | +6.75R | 16.14R |
| Günlük −4R freni | 74 | +3.24R | 16.97R |
| HIGH + stop≥%0.75 | 17 | +0.72R | 8.82R |
| Yalnız HIGH güven | 24 | +0.29R | 13.09R |

**Bu tablo bir vaat değildir.** Hepsi geriye dönük seçim; sonucu bilerek
filtre aramak en zayıf kanıt türüdür. Değeri sıralamada, rakamlarda değil.
Ortak yön nettir ve üç bağımsız eksende aynı şeyi söylüyor: **dar stop +
düşük RR + MEDIUM güven** kombinasyonu zararın taşıyıcısı.

## Bundan sonra
Yeni motor tasarımı ayrı bir belgeye yazılır ve ÖN-KAYITLI olarak yeni bir
ölçüm penceresinde sınanır. Yukarıdaki hiçbir eşik, bu veriden türetildiği
için doğrudan kural yapılamaz — hipotez olarak kaydedilip GELECEK veride
test edilir. Aday yarışı (S1–S6) etkilenmez, kendi sınavına devam eder.

## v3.7 ölçüm düzeltmesi (2026-08-05, kilit açıldıktan SONRA): doluş mumu + AMBIGUOUS eşdeğerliği
Kritik bug fix istisnası kapsamında iki muhasebe düzeltmesi; motor
(`app/strategies/`), eşikler, maliyet modeli ve ısı limitlerine sıfır dokunuş.
Kilit-v2 penceresi başlamadan yapıldı — yeni pencere temiz defterle açılır.

1. **Doluş mumu sonuç kontrolüne girer** (`_evaluate_signal`): canlı takipçi,
   doluşun gerçekleştiği mumu `continue` ile atlıyor, stop/TP kontrolüne bir
   SONRAKİ mumdan başlıyordu. İlan edilen kural (verifier, v3.6: "doluş
   mumundan İTİBAREN önce STOP mu TP mi") doluş mumunu kapsar. Atlama,
   doluş mumundaki stop temasını kaçırır; fiyat sonra TP'ye koşarsa uydurma
   WIN yazılırdı — "doluş öncesi bulaşma" sınıfının son üyesi. Yön İYİMSER
   olduğundan düzeltme yanlışlama #2 hükmünü etkilemez, olsa olsa güçlendirir.
   Etkilenen kapanmış kayıtlar mevcut onarım mekanizmasıyla
   (`_repair_bad_outcomes`) açılışta yeniden karara bağlanır; başlık
   rakamları onarım sonrası yeniden okunmalıdır.
2. **LOSS(ambiguous=1) ≡ AMBIGUOUS** (`verifier.compare`): kilitli kural
   aynı-mum TP+STOP'u defterde LOSS (ambiguous=1) yazar; denetçi aynı olayı
   AMBIGUOUS diye adlandırır. İki isim aynı karardır (r=−1). Eşdeğerlik
   tanınmadığından her ambiguous vaka kalıcı sahte "uyuşmazlık" üretiyor ve
   onarım döngüsünce gereksiz yeniden açılıyordu. Düzeltme denetim aracına
   yapıldı; motor tarafı kilitli kurala zaten uyuyordu.

Regresyon testleri: `test_fill_candle_stop_counts`,
`test_fill_candle_both_is_ambiguous_loss`, `test_compare_ambiguous_loss_equivalence`.

## v3.7 ölçüm eki (2026-08-05): rejim bilgisi sinyal kayıtlarında yaşar
Otopside geriye dönük rejim analizi yapılamadı çünkü sinyal anındaki piyasa
rejimi (market_bias: bull/bear/neutral/halt) HİÇBİR yere yazılmıyordu —
Decision.regime sembol rejimidir ve her SIGNAL tanım gereği trending doğar,
ayrıştırmaz. Ölçüm eki (motor davranışı değişmez):
- Sözleşme v1.1 → v1.2: `market_bias` alanı eklendi (yalnız alan eklemesi,
  geriye uyumlu). Karar arşivi (decisions) bunu otomatik taşır.
- `signals` tablosuna `regime` + `market_bias` KOLONLARI eklendi; üç yazım
  yolu da (gerçek / kapı-bloklu / ısı-bloklu kohort) doldurur. Kolon olarak
  eklendi çünkü contract_json yedek muafiyetindedir — restore'da kaybolur
  (kural 2: her kolon yedekten sağ çıkar; kolonlar yedek payload'ına ve
  import'a eklendi, değişmezlik testi otomatik zorlar).
- Geriye dönük doldurma `_backfill_regime_bias`: eski kayıtların rejimi
  KAYITLI veriden okunur (contract_json; eski kapı-bloklularda reject_reason
  metnindeki "market gate: BTC …"). Kaynağı olmayan NULL kalır ve
  `market_bias_dist`'te '?' olarak raporlanır (kural 1: uydurma yok).
- `/measurement`: `gate_blocked_regime_dist` artık kolondan okur (restore
  sonrası da çalışır); gerçek kohort için `market_bias_dist` eklendi.
Kural 7 uygulandı: 5 test önce KIRMIZI gösterildi, düzeltme sonrası yeşil.


# ============================================================
# KİLİT-2 İLANI — 2026-08-12 KARAR TOPLANTISI (Serhat onayı)
# ============================================================
Kaynak: iki-bot karşılaştırma raporu (bot-kod-analizi.md) + her bulgunun
bu depoda bağımsız yeniden üretimi. Dört madde, tek oturum, tarihli tutanak.

## Madde 1 — TUTANAK: maksDD alarmı ölüydü; tavan 2.7× aşılmıştı
Alarm, düşüş değerini stats üst düzeyinde arıyordu; değer measurement
içinde yaşıyor → alarm İLK GÜNDEN BERİ hiç ateşlenemedi. Dış denetimin
kanıt testine göre gerçek (tüm-zaman, maliyet-modelli) maksimum düşüş
≈54.5R — ilan edilen 20R tavanının 2.7 katı. 35.6R'lik yanlışlama-#2
ihlalini alarm değil İNSAN yakalamıştı; şimdi kayda geçiyor. Düzeltme +
sınıf-kapatan test (test_declared_alarms_can_actually_fire) + Kural 10
(error-prevention.md) bu ilana eşlik eden commit'lerdedir. Motor dışı
katman; hiçbir sayaç sıfırlanmadı.

## Madde 2 — RETEST DÜZELTMESİ (motor değişikliği, kilit-2'nin gerekçesi)
Kusur: retest/acceptance dilimleri kırılım mumunun KENDİSİNDEN başlıyordu;
kırılım mumunun dibi seviye toleransı içinde kaldığı için retest şartı
fiilen BOŞTU — motor kırılımı görür görmez kovalıyordu. Kanıt: fiyatın
kırıp HİÇ geri dönmediği sentetik seride eski kod kurulum buldu (kırmızı
test: test_breakout_retest_requires_actual_retest; düzeltme sonrası aynı
seri kurulum üretmez, gerçek retest'li seri üretmeye devam eder).
Düzeltme: dilimler break_i+1'den başlar (structure_analyzer.py).
AÇIK SINIR: "düzeltilince kâra geçer" DENMEDİ ve DENMEZ — bunu yalnız
kilit-2 kohortu söyleyebilir.

## Madde 3 — KİLİT-1 HÜKMÜ ARŞİVLENDİ (seçenek b, gerekçeli)
Botun kendi alarmı: örneklem doldu (≥50 küme), CI koşulu sağlanmadı →
hüküm "GEÇEMEDİ". Bu hüküm ESKİ (retest'i boş) motora aittir ve zaten
2026-08-05'te yanlışlama-#2 ile pencere kapanmıştı. Karar: şampiyon
durdurulmaz; hüküm kilit-1 arşivine yazılır, düzeltilmiş motor KİLİT-2
penceresinde SIFIRDAN ölçülür. Gerekçe: aynı anda hem motoru düzeltip hem
eski defterden hüküm sürdürmek iki farklı motorun karnesini karıştırırdı.

## KİLİT-2 KURALLARI
- Pencere başlangıcı: **LOCK2_UTC = 2026-08-13T00:00:00Z**
  (measurement.ACTIVE_LOCK_UTC). Tüm "kilit sonrası" sayaçlar (Faz-1
  küme sayacı, küme-CI, maksDD, kenar-ölümü alarmı) SIFIRDAN bu andan okur.
- ŞART: bu ilanın commit'i LOCK2_UTC'den ÖNCE canlıya alınmalıdır
  (main'e merge → autodeploy). Alınamazsa pencere fiili deploy anına
  kayar ve buraya tarihli not düşülür.
- Eşikler, maliyet modeli v0, küme tanımı, gölge kuralları, portföy ısısı,
  evren kuralı: kilit-1 ile AYNEN (hiçbiri değişmedi).
- Yanlışlama kriterleri (1: kenar ölümü, 2: maksDD>20R, 3: açlık) AYNEN
  devralınır ve kilit-2 kohortunda izlenir.
- `app/strategies/` bu commit'ten itibaren YENİDEN DONMUŞTUR (CLAUDE.md
  kural 1); bu ilandaki break_i+1 değişikliği donmanın kayıtlı istisnası
  değil, kilidin kendisinin parçasıdır.

## Madde 4 — ADAY BÜTÇESİ (ölçüm katmanı; ayrı tarihli not)
S3_MEANREV ve S6_SWEEP kenar ölümü İLAN EDİLMİŞ koşulla kanıtlandı
(CHALLENGER_DEAD: küme-CI üst sınırı < 0, ≥20 küme; S3: 83 küme
[−0.30,−0.07], S6: 82 küme [−0.38,−0.03]) → EMEKLİ (RETIRED sözlüğü).
Yeni sinyal üretimi durur; açık pozisyonlar normal değerlendirilir;
kapanmış kohort arşivde kalır ve stats'ta retired_utc ile görünür;
alarmları susturulur (hüküm verildi, gürültü olmaz).
Boşalan 15+15=30 slot, tavana boğulan S1'e devredildi: **S1 tavanı
40→70; efektif toplam bütçe SABİT (165)** — türetme, icat değil.
KIYASLANABİLİRLİK: S1'in doğrulama penceresi AYNI GÜN açıldı ve kohortu
henüz BOŞTU → doğrulama kohortu tamamen tavan-70 altında toplanır; seçim
kohortu (tavan-40) arşivde ayrı durur. Dünkü "tavan büyütülmedi" ilanı
bu kararla AYNI GÜN, kohort boşken değiştirildi — sonuç-bağımlı örnekleme
oluşmadı; çelişki bu notla kapatıldı.

# ============================================================
# 2026-08-18 KARAR TOPLANTISI (Serhat onayı: "ikisine de tamam")
# ============================================================

## Madde 1 — S4_CARRY ve S7_WYCKOFF EMEKLİ (CHALLENGER_DEAD)
Botun kendi alarm sayfası (2026-08-18T19:50Z kontrolü), önceden ilan
edilmiş kenar-ölümü koşulunun (küme-CI üst sınırı < 0, ≥20 küme) İKİ
aday için gerçekleştiğini raporladı:
- S4_CARRY: küme-CI üst −0.018 < 0 (126 küme)
- S7_WYCKOFF: küme-CI üst −0.199 < 0 (108 küme)
Karar: ikisi de RETIRED (2026-08-18). Yeni sinyal durur; açık pozisyonlar
normal değerlendirilir; kohort arşivde retired_utc ile kalır; alarmları
susar (hüküm verildi). S7 kararı, S4 ile AYNI ilan koşulunun
uygulamasıdır ve Serhat'a açıkça raporlanmıştır (pano ekranında S7
satırı görünmüyordu; alarm yakaladı — alarm altyapısının değeri).
SLOT DEVRİ YOK (2026-08-12'den fark): S1'in doğrulama penceresi "aynı
kurallar" sözüyle açıldı; pencere ortasında tavan değiştirmek kohortu
kirletirdi. Efektif toplam bütçe BİLEREK küçüldü. Not: ham funding
sinyali (S4) öldü; rafine türevi S8 (daha derin eşik + fiyat teyidi)
ayrı aday olarak ölçülmeye devam ediyor — aile hükmü S8'in kendi
kohortundan gelecek.

## Madde 2 — KİLİT-2 DURUM NOTU: HENÜZ HÜKÜM YOK (düzeltme kaydı)
Claude'un pano ölçüm kartından yaptığı "72 küme; örneklem doldu, sınav
geçilemedi" okuması YANLIŞTI ve burada düzeltiliyor. Ön-kayıtlı hüküm
kanalı (FAZ1_GATE_MET / FAZ1_SAMPLE_FULL alarmları; clusters_since_lock
= LOCK2 penceresi) 2026-08-18T19:50Z kontrolünde SESSİZ → kilit
kohortunda küme < 50, SINAV SÜRÜYOR. Ara görünüm (E_net −0.07R,
küme-CI [−0.43, +0.32], isabet başabaşın altında, LONG −49.3R /
SHORT +31.5R) negatif eğilimli AMA hüküm değildir. Hüküm, kilit-1
usulünce botun kendi alarmıyla ilan edilecek. DERS (kayda): hüküm
YALNIZ ilan edilmiş kanaldan okunur; pano kartları ara göstergedir.

## Madde 3 — V2 TASARIM SÜRECİ AÇILDI
docs/v2-tasarim.md girdi dosyası oluşturuldu (yön asimetrisi, çıkış
laboratuvarı, P4 OI kapısı, dış denetim düzeltme listesi, perakende
araştırması, ölü aile mezarlığı). v2 tasarımı KİLİT-2 hükmünü BEKLEMEZ
ama onu ETKİLEMEZ: app/strategies/ donmuş kalır; v2 tasarlanınca
ideas.md'ye ÖN-KAYITLA yeni aday olarak girer ve sıfırdan sınava tabi
olur. Şampiyon durdurulMAZ (gerçek para yok; ürettiği veri ölçüm
aletlerini besliyor).

# ============================================================
# KİLİT-2 HÜKMÜ — 2026-08-20 (Serhat onayı: "önerilerini kabul ediyorum")
# ============================================================

## HÜKÜM: GEÇEMEDİ — YANLIŞLAMA #2 (maksDD tavanı)
Kilit penceresi (2026-08-13'ten itibaren) maksimum düşüşü **20.15R**,
önceden ilan edilmiş tavan **20R** (kilit-1'den AYNEN devralınan
yanlışlama kriteri #2). Değer botun KENDİ ölçümünden okunmuştur
(0_performance.json → measurement.max_drawdown_r, since_lock=True;
yedek tazeliği 2026-08-20T19:35Z). Alarm eşiği MAX_DD_LIMIT_R=20.0 →
MAX_DD kanalı kod gereği aktif. İhlal anında küme sayacı 46/50 idi ve
kilit kohortu CI görünümü [−0.307, +0.353] — geçiş koşulundan uzak;
hüküm sayaç dolmadan, yanlışlama kuralıyla verilmiştir (kilit-1'de
yanlışlama-#2'nin pencereyi kapattığı emsalle aynı usul).
İnce not (dürüstlük): ihlal kıl payıdır (20.15) ve ralli sonrası
toparlanma sürerken gerçekleşmiştir — kural sonuç-bağımlı esnetilmez;
esneme hakkı isteyen, kuralı VERİDEN ÖNCE yazmalıydı.

SONUÇ:
- v1 şampiyonu (breakout_retest + sweep) iki kilit penceresinde de
  kanıt üretemedi. Hüküm nihaidir; üçüncü kilit penceresi İLAN EDİLMEZ.
- Şampiyon DURDURULMAZ: gerçek para yok; ürettiği karar/mum arşivi
  ölçüm aletlerini (çıkış lab, korelasyon, karşı-olgu kohortları)
  beslemeye devam eder. Statüsü: VERİ KAYNAĞI.
- app/strategies/ donmuş kalır (artık sınav bütünlüğü için değil,
  arşiv tutarlılığı için: değişen motor eski verinin anlamını bozar).
- Ana gündem: v2 tasarımı (docs/v2-tasarim.md; takvim: çıkış-lab ilk
  hükümleri + S2 CI seyri ile birlikte, hedef ~2 hafta).

## S1_TSMOM DOĞRULAMA HÜKMÜ: GEÇEMEDİ (aynı tutanak)
Ön-kayıt (2026-08-12, challengers-design.md sonu): yeni ≥50 kapanmış
küme + küme-CI alt > 0. Gerçekleşen (2026-08-20): **90 küme**, net
**−24.36R**, CI **[−0.25, +0.113]** → GEÇEMEDİ. Seçim penceresi kıl
payıydı (−0.053); doğrulama değil. ÜÇÜNCÜ PENCERE İLAN EDİLMEZ.
S1 emekli DEĞİLDİR (kenar-ölümü koşulu — CI üst < 0 — oluşmadı):
ölçüm/kıyas değeri için koşmaya devam eder, umut statüsü düşmüştür.
VALIDATION_WINDOWS kaydı arşiv raporlaması için kodda kalır.

# ============================================================
# 2026-08-21 — S2 SEÇİM SINAVINI GEÇTİ (PROJEDE İLK) + DOĞRULAMA İLANI
# ============================================================

## S2_DONCHIAN: Faz-1 seçim koşulu SAĞLANDI
2026-08-21 defteri (rejim-2 kohortu): 165 kapanmış küme (hedef 50),
net +95.77R, küme-CI **[+0.027, +0.432]**, E_net +0.221. İki yıllık
disiplinde "≥50 küme VE küme-CI alt sınırı > 0" koşulunu sağlayan İLK
aday. Bağlam dürüstlüğü: alt sınır sıfırın üstüne hızlı-yükseliş
haftasında çıktı — tam da bu yüzden hüküm SEÇİMLE VERİLMEZ.

## DOĞRULAMA PENCERESİ İLANI (Serhat onayı "tamam")
Çoklu karşılaştırma kuralı (challengers-design.md) gereği: hüküm, ilan
ANINDAN SONRA toplanan yeni kohorttan verilir. Pencere başlangıcı:
**2026-08-21T20:00:00Z** (ilan anının İLERİSİNE yuvarlandı; ilan-öncesi
veri kohorta sızamaz). Koşul aynen: yeni kohortta ≥50 kapanmış küme VE
küme-CI alt sınırı > 0. Kurallar/tavan/maliyet DEĞİŞMEZ.

## HÜKÜM ANI KURALI (S1 dersi; süreç düzeltmesi — ön-kayıt)
S1 hükmü 90. kümede elle okunmuştu; mühürden SONRA kohort ralliyle
artıya döndü (+35.15R, 95 küme). HÜKÜM SABİTTİR — sonuç-bağımlı yeniden
açma p-hacking'dir; S1 statüsü değişmez. Alınan ders kurallaştırıldı:
bundan böyle doğrulama hükmünün ANI insana bırakılmaz — kohort 50.
kümesini doldurduğunda botun önceden-ilanlı alarmı hükmü ilan eder:
CI alt > 0 → VALIDATION_GATE_MET; değilse VALIDATION_SAMPLE_FULL.
Mühürlü hükümler (VALIDATION_VERDICTS) için alarm susar. Kırmızı-önce
testli (test_alarms_announce_validation_verdict_moment).

# ============================================================
# 2026-08-30 KARAR TOPLANTISI (Serhat onayı: "mühürle")
# İKİ HÜKÜM: S2 doğrulaması GEÇEMEDİ + P4 filtresi ELENDİ
# ============================================================

## Madde 1 — S2_DONCHIAN DOĞRULAMA HÜKMÜ: GEÇEMEDİ
Pencere 2026-08-21T20:00Z'de ilan edilmişti (seçim sınavı 165 kümede
GEÇİLMİŞTİ — projede ilk). Doğrulama kohortu 2026-08-29'da doldu ve
hükmü **botun kendi alarmı ilan etti** (VALIDATION_SAMPLE_FULL) — 08-21'de
kurduğumuz hüküm-anı mekanizması ilk işini yaptı, hüküm insan okumasına
bırakılmadı.
Gerçekleşen (2026-08-30 defteri): **54 küme** (hedef 50), net **−77.3R**,
küme-CI **[−0.627, −0.298]**. Geçmek için CI alt > 0 gerekiyordu.
DİKKAT ÇEKİCİ: CI'nin ÜST sınırı bile sıfırın altında — bu "kanıt
bulunamadı" değil, ters yönde belirgin bir sonuç. Seçim geçişinin ralli
haftasına ait bir eser olduğu tezi doğrulandı; S2'nin GENEL küme-CI'si de
[−0.108, +0.230]'a gerileyerek 08-21'deki geçişi tamamen sildi.
SONUÇ: ÜÇÜNCÜ PENCERE İLAN EDİLMEZ (S1 emsali). S2 emekli DEĞİLDİR —
kenar-ölümü koşulu (genel CI üst < 0) oluşmadı; ölçüm/kıyas için koşar,
umut statüsü düşer. VALIDATION_VERDICTS kaydı girildi → alarm susar.

## Madde 2 — P4 (OI-ONAYLI KIRILIM FİLTRESİ): ELENDİ
Ön-kayıt: docs/ideas.md 2026-08-16 (kurallar backtest KOŞULMADAN
donduruldu). Canlı gölge-kohort 2026-08-16'da açıldı; hüküm koşulu
"her iki kohortta ≥50 küme" 2026-08-29'da sağlandı.

| Kohort | Küme | Kapanmış | E_net | küme-CI |
|---|---|---|---|---|
| OI-ARTIŞLI (ΔOI ≥ +%5) | 56 | 84 | **−0.078** | [−0.377, +0.298] |
| OI-ARTIŞSIZ | 80 | 219 | **+0.078** | [−0.246, +0.442] |

Ön-kayıtlı merdiven: *"FİLTRE ELENDİ: OI-ARTIŞLI E_net ≤ OI-ARTIŞSIZ
E_net (teyit katkı vermiyor) VEYA OI-ARTIŞLI küme-CI üst < 0."*
−0.078 ≤ +0.078 → **ELENDİ**. Üstelik işaret backtest'in TERSİ yönde.

BACKTEST vs CANLI (projenin en öğretici karşıtlığı):
- Backtest (2026-08-16, 2877 işlem): artışlı +22.32R / artışsız −170.88R;
  E_net farkı +0.113 — "çarpıcı ve hipotez yönünde" diye kaydedilmişti.
- Canlı ileriye dönük (2026-08-29): fark −0.156, İŞARET TERS.
DERS: geçmişe bakan analiz çarpıcı bir fark gösterdi; ileriye dönük
ölçüm o farkın tesadüf olduğunu ortaya çıkardı. "Backtest hüküm değil,
budamadır" kuralının canlı kanıtı. Bu, ön-kayıt disiplininin bu projede
ölçülen EN NET getirisidir: filtre v2'ye kanıtsız girseydi, temele
konmuş çürük bir taş olurdu.

SONUÇ: OI-onay kapısı v2 tasarımından DÜŞTÜ (v2-tasarim.md girdi #2
güncellendi). Etiketleme DURMAZ — ölçüm sürer, arşiv büyür, hüküm
oi_cohorts.verdict alanında görünür (sessiz kaybolma yok).
NOT: "katılım kapısı" fikri tamamen ölmedi — HACİM ayağı (S12_RELVOL)
ayrı bir aday olarak yaşıyor (26 küme, +9.4R). Ölen, OI ayağıdır.

## Genel tablo (2026-08-30 itibarıyla)
İstatistiksel olgunluğa (≥50 küme) ulaşan HER motor sınavı geçemedi:
şampiyon (kilit-1, kilit-2), S1 (seçim + doğrulama), S2 (seçim geçti →
doğrulama geçemedi), S8 (seçim), + dört emekli (S3/S6/S4/S7) + backtest
mezarları (P1, S5/TSM, S-ATT1, ve şimdi P4). Ayakta kalan tek umut:
genç adaylar S11 (26 küme, +18.6R) ve S12 (26 küme, +9.4R).

# ============================================================
# 2026-09-18 KARAR TOPLANTISI (Serhat onayı: "mühürle")
# ŞAMPİYON (breakout_retest): KENAR ÖLÜMÜ — v1 DOSYASI KAPANDI
# ============================================================

## Madde 1 — YANLIŞLAMA #1 (KENAR ÖLÜMÜ) TETİKLENDİ
Hüküm, ön-kayıtlı kanaldan okundu (2026-08-20 dersi: hüküm YALNIZ ilan
edilmiş alarm kanalından okunur, pano kartları ara göstergedir). VM
scheduler günlüğü, 2026-09-18:

    WARNING | scheduler | event=alarm code=EDGE_DEATH
      msg=kume-CI ust siniri -0.028 < 0 (197 kume) - onceden ilan
          edilmis kenar olumu kriteri tetiklendi.
    WARNING | scheduler | event=alarm code=MAX_DD
      msg=maksimum dusus 100.6R > 20.0R esigi.

Ölçüm penceresi: KİLİT-2 kohortu (`bootstrap_since_lock`,
ACTIVE_LOCK_UTC = 2026-08-13T00:00:00Z). maksDD de kilit-içi
(`max_drawdown_r(since_lock=True)`).

**197 kapanmış küme, küme-CI ÜST sınırı −0.028.** Üst sınırın bile
sıfırın altında olması "kanıt bulunamadı" değildir; ters yönde belirgin
bir sonuçtur — S2'nin 08-30 doğrulamasıyla aynı imza. Eşik 20 kümeydi;
197 küme ile örneklem tartışılacak gibi değil.

## Madde 2 — İKİNCİ YANLIŞLAMA DA AÇIK
maksDD 100.6R, ilan edilmiş 20R tavanının **5 katı**. KİLİT-2 zaten
20.15R ile 08-20'de bu kriterden düşmüştü; aradaki dört haftada düşüş
100.6R'ye çıktı. Yani motor yalnız "kenarını yitirmiş" değil, kilit
penceresinde ağır kayıp üretmiştir.

## HÜKÜM
Şampiyon **breakout_retest** motorunun v1 dosyası KAPANDI. İki ayrı
ön-kayıtlı yanlışlama kriteri (kenar ölümü + maksDD) bağımsız olarak
tetiklendi. ÜÇÜNCÜ KİLİT İLAN EDİLMEZ (KİLİT-2 tutanağı, 08-20: üçüncü
kilit yok). Sonuç-bağımlı yeniden açma p-hacking'dir.

STATÜ: motor DURDURULMAZ — **VERİ KAYNAĞI** olarak koşmaya devam eder
(mum arşivi, küme etiketleme, çıkış laboratuvarı ve korelasyon aleti
onun defterinden beslenir). Umut statüsü SIFIRDIR; hiçbir karar, hiçbir
v2 bileşeni onun canlı sonuçlarına dayandırılamaz.
`app/strategies/` DONMUŞ kalır (Kural 1) — hüküm mühürlendi diye motor
kurcalanmaz; donmuş motor, ölçüm aletinin kalibrasyonudur.

## Madde 3 — GENEL TABLO (projenin bilançosu, 2026-09-18)
İstatistiksel olgunluğa (≥50 kapanmış küme) ulaşan **HER** motor
sınavı geçemedi. İstisna YOK:

| Motor | Pencere | Sonuç |
|---|---|---|
| Şampiyon breakout_retest | kilit-1 | GEÇEMEDİ (yanlışlama #2 + CI) |
| Şampiyon breakout_retest | kilit-2 | GEÇEMEDİ (08-20 maksDD) → **09-18 KENAR ÖLÜMÜ** |
| S1_TSMOM | seçim + doğrulama | GEÇEMEDİ (08-20) |
| S2_DONCHIAN | seçim GEÇTİ → doğrulama | GEÇEMEDİ (08-30) |
| S8_FUNDING | seçim | GEÇEMEDİ |
| S11_SQUEEZE | seçim (50 küme) | GEÇEMEDİ (09-05) |
| S3, S6 | — | EMEKLİ (08-12, kenar ölümü) |
| S4, S7 | — | EMEKLİ (08-18, CHALLENGER_DEAD) |
| P1, S5/TSM, S-ATT1, P4 | backtest / gölge kohort | ELENDİ |

Sınava **hiç girmemiş tek aday: S12_RELVOL** (hacim-kapılı seans
kırılımı). Ondan başka canlı umut yoktur.

SONUÇ: v2 tasarımı (docs/v2-tasarim.md) artık **tek gündem**dir. v1'in
bıraktığı bağlayıcı girdiler: GİRDİ 0 (maliyet dayanıklılığı —
maliyet/işlem ≤ 0.05R, dar stop yasak), OI kapısının düşmesi (P4),
çıkış-lab ara okuması (hüküm değil; yeni ön-kayıt ister).

## Madde 4 — SÜREÇ DERSİ: İZLEME KANALI ile ARIZA KANALI AYNI OLAMAZ
Bu hüküm 13 gün GEÇ okundu. Sebep: 2026-09-05'te gist yedeği 300-dosya
sert sınırına çarpıp sustu (HTTP 422). Gist, hem uzaktan izleme
penceresi hem felaket-kurtarma kopyasıydı; o kırılınca dışarıdan bakan
göz "bot mu öldü, yedek mi öldü" ayrımını yapamadı.
Dürüst tespit: **alarm mekanizması çalışıyordu** — STALE_BACKUP
(eşik 3 saat) 13 gün boyunca ötmüştü. Kusur ilan etmekte değil,
ilan edileni Serhat'a ULAŞTIRMAKTAydı: alarmın tek çıkışı panoydu,
panoya da bakan yoktu.
KURAL (bundan böyle bağlayıcı): bir arızayı BİLDİREN yolun, o arızadan
ETKİLENMEYEN bir yol olması gerekir. Yedek kanalının sağlığı, yedek
kanalının kendisinden okunamaz.
Yapılan (2026-09-18): 300-dosya sınırı düzeltildi — mum yedeği yalnız
en ince dilim, MAX_GIST_FILES=280 bütçesi, yetim candles_* budaması;
sınıfı kapatan 4 kırmızı-önce test (tests/test_gist_file_limit.py).
AÇIK MADDE (v2 gündemine): panodan bağımsız bir bildirim yolu
(örn. dışarıdan çekilen sağlık ucu veya ikinci bir kanal). Ön-kayıt
gerektirmez — ölçüm kuralı değil, işletim altyapısıdır.

# ============================================================
# 2026-09-20 KARAR TOPLANTISI (Serhat onayı: "1. portföy yolunu aç,
# önce korelasyonu ölç / 2. önerdiğin gibi / 3. v2'yi beklet")
# ÜÇ MADDE: ölçüm nüfusu birleştirildi + portföy yolu açıldı +
# v2'nin raftan çıkma koşulları ön-kayıtlandı
# ============================================================

## Madde 1 — ÖLÇÜM NÜFUSU BİRLEŞTİRİLDİ (EXPIRED)

### Bulgu
`challengers.stats()` kendi notunda "şampiyonla aynı küme-CI standardı,
aynı 50-küme eşiği" yazıyordu. **Bu iddia yanlıştı:**

| | Şampiyon | Adaylar |
|---|---|---|
| Küme/CI nüfusu | `WIN, LOSS` | `WIN, LOSS, EXPIRED` |

Ölçülen etki (09-20 tablosu): S11 **91 küme / 42 karara bağlanmış**,
S9 37/11, S8 218/159. S11'in örnekleminin yarısından fazlası EXPIRED.
Aday kohortları 50-küme kapısına şampiyondan ÇABUK varıyordu.

### Karar: EXPIRED İÇERİDE, her iki tarafta
Gerekçe: süre dolunca GERÇEK fiyattan kapanan GERÇEK bir pozisyondur ve
gerçek bir R üretir. Dahası bazı adaylarda (S12, hedefsiz) zaman-çıkışı
motorun ASIL çıkış biçimidir — dışarıda bırakmak stratejinin ana
sonucunu defterden silmek olurdu. Korelasyon aleti (correlation.py)
şampiyonun EXPIRED'ini ZATEN sayıyordu; tutarsız olan tek yer
şampiyonun `stats()`'iydi.
NOT_FILLED ve AMBIGUOUS DIŞARIDA kalır (ilkinde pozisyon hiç açılmadı,
ikincisi patolojik kapanış). Düzeltmenin fazla geniş olmadığı testle
zorlanır (`test_not_filled_still_excluded_everywhere`).

### ⚠️ ÖN-KAYIT — SAYILARI GÖRMEDEN İLAN EDİLDİ
**Bu düzeltmeden sonra çıkacak yeni sayılar NE OLURSA OLSUN, aşağıdaki
mühürlü hükümler AÇILMAZ:**
- Şampiyon kilit-1 ve kilit-2 hükümleri (2026-08-20, 2026-09-18)
- S1 seçim + doğrulama hükümleri (2026-08-20)
- S2 seçim + doğrulama hükümleri (2026-08-21, 2026-08-30)
- S11 seçim hükmü (2026-09-05)
- S8, S3/S6/S4/S7 hükümleri

Gerekçe: mührü, sonradan değişen bir muhasebeyle yeniden hesaplamak
SONUÇ-BAĞIMLI YENİDEN AÇMADIR — bu projenin en temel yasağı. Hükümler
verildikleri günün muhasebesiyle verilmiştir ve o hâlleriyle kalırlar.
Bu paragraf, düzeltme koşulmadan ÖNCE yazılmıştır; yani "yeni sayı
hoşuma gitti/gitmedi" diye karar veremeyiz. Kendi kuralımızı kendimize
uyguluyoruz.

Düzeltme İLERİYE dönüktür: bundan sonra açılacak pencereler ve canlı
ölçümler ortak nüfusu kullanır.

### Kural 3 uyumu
`tests/test_expired_cohort.py` — 7 test, düzeltmeden ÖNCE 6'sı KIRMIZI
verdi (doğrulandı). Tek gerçek kaynak: `measurement.MEASURED_OUTCOMES`
+ `MEASURED_OUTCOMES_SQL`; şampiyon ve adaylar AYNI nesneyi kullanır
(`test_champion_and_challenger_use_the_same_cohort`, `is` ile).
Dokunulan noktalar: `cost_r` kapısı, `stats()` kohortu, `max_drawdown_r`,
`anatomy_report`. Kasıtlı DOKUNULMAYANLAR: WIN/LOSS'a ÖZGÜ kırılımlar
(kazanma oranı, WIN/LOSS tutuş medyanı, MFE/MAE) — onlar zaten
"kazanan mı kaybeden mi" sorusunu sorar.

### Kural 3b — ikiz depo
midas-signal-bot aynı iskeletten doğdu; aynı asimetri orada da
muhtemeldir. AÇIK İŞ: midas'ta şampiyon/aday küme nüfusları
karşılaştırılacak, sonuç ikiz-depo-notu'na yazılacak (bulunmasa bile).

## Madde 2 — PORTFÖY YOLU AÇILDI (Faz B)

Gerekçe (09-20 aday tablosu): dört motor küçük-ama-pozitif ve maliyet
bütçesi İÇİNDE — S1 (+78.16R, 0.037), S2 (+39.94R, 0.041),
S11 (+10.47R, 0.022), S8 (+5.40R, 0.019). Hiçbiri tek başına sınavı
geçemiyor çünkü gürültü kenardan büyük; hepsinin CI'si sıfırı içeriyor.

**Portföy tezi:** birbirleriyle tam örtüşmüyorlarsa, birlikte ölçülen
defterin gürültüsü azalır ve CI daralır. Bu yalnız "geçme" ihtimalini
artırmaz — **her iki yönde de KESİN bir cevaba** götürür: gerçek kenar
sıfırsa CI sıfır etrafında daralır ve temiz bir HAYIR alırız.

**ADIM 1 (şimdi): korelasyon ölçümü.** Üyeler birbirini gerçekten
dengeliyor mu? `/correlation` aleti (Faz A, 2026-08-13'te yazıldı, hiç
kullanılmadı) etkin bağımsız bahis sayısını (N_eff) verir. Ölçüm
sonucu görülmeden ön-kayıt YAZILMAZ.

**ÜYE SEÇİM KURALI — getiriye BAKMAZ (p-hacking kapısı):**
> Emekli olmayan, maliyet/işlem ≤ 0.05R olan ve ≥50 kümeye ulaşmış
> TÜM adaylar.
Bugün bu kural S1, S2, S8, S11 **ve S12'yi** seçer — S12 net EKSİ
olmasına rağmen, çünkü kural getiriye bakmıyor. Kuralı dürüst yapan
tam olarak budur.

**AÇIKÇA KAYDA GEÇEN GERİLİM:** bu havuzu geçmiş veriye bakarak
tanıyoruz. Seçim kuralı getiriye bakmasa bile havuzun kendisi geçmişte
oluştu. Tek ilacı: pencere İLAN EDİLDİKTEN SONRAKİ veriyle test etmek.
Portföy de sıfırdan sınava girer; geçmiş sayılar SAYILMAZ.

## Madde 3 — v2 RAFA KALKTI + RAFTAN ÇIKMA KOŞULLARI (ön-kayıt)

v2 şampiyon tasarımı BEKLEMEYE alındı. Sebep: portföy çıkarsa v2'nin
sıfırdan tasarımına gerek kalmayabilir; elimizdeki parçalardan kurulur.

**v2 ŞU KOŞULLARDAN BİRİ GERÇEKLEŞİRSE RAFTAN ÇIKAR** (şimdi ilan
edildi ki sonradan hedef kaydırmayalım):

1. **Portföy penceresi GEÇEMEZSE.** Pencere ≥50 kümeye ulaşır ve
   küme-CI alt sınırı ≤ 0 olursa. (Portföyün de ÜÇÜNCÜ penceresi YOK —
   S1/S2 emsali.)
2. **Portföy KURULAMAZSA.** Korelasyon ölçümü üyelerin birbirinin
   kopyası olduğunu gösterirse (etkin bağımsız bahis sayısı ~1),
   çeşitlendirme kazancı yoktur; portföy tezi daha kurulmadan düşer.
3. **ÜYELER ÖLÜRSE.** Pencere dolmadan üyelerin çoğu kenar-ölümü
   koşuluna (küme-CI üst sınırı < 0, ≥20 küme) girerse.
4. **ZAMAN AŞIMI.** Portföy penceresi ilan tarihinden itibaren
   **4 ay** içinde 50 kümeye ulaşmazsa, aç kalma (starvation) sayılır
   ve gündem v2'ye döner.

**v2 raftan çıkarsa ne OLMAYACAĞI da şimdi kayıtlıdır:** v2 bir
"maliyet düzeltme" motoru DEĞİLDİR. 09-20 tablosu gösterdi ki en güçlü
adaylarımızda maliyet ZATEN bütçe içinde (0.019–0.041); maliyet teşhisi
şampiyon ve emekliler (S7 0.359, S3 0.261, S6 0.208, S9 0.330) için
geçerlidir, en iyi adaylar için değil. Dolayısıyla v2, ya ZEMİNİ
değiştirmeli (zaman dilimi / evren) ya da gerçekten farklı bir kenar
kaynağı bulmalıdır. Bu satır, 09-18'de yazdığım "v2 GİRDİ 0 ekseninde
kurulmalı" önerisinin DÜZELTMESİDİR.
