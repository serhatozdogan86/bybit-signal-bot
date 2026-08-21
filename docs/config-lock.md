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
