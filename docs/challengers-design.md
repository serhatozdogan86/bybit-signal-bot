# Challenger Stratejiler — Tasarım Belgesi (v0, 2026-08-03)

## Amaç
Şampiyon (breakout-retest motoru) Faz-1'i geçemezse elde ölçülmüş
alternatifler olsun. Kurumsal adı **champion/challenger**: sistematik
fonların standart pratiği — mevcut strateji yayında ölçülürken adaylar
paralel gölge modda aynı standartla ölçülür.

**Dürüstlük notu:** Büyük şirketlerin gerçek algoritmaları kamuya açık
değildir. Kamuya açık ve on yıllardır belgeli olan şey strateji AİLELERİDİR:
trend takibi (CTA/managed futures), ortalamaya dönüş (stat-arb ailesi),
taşıma/carry, kesitsel momentum. Market-making ve HFT de kurumların ana işi
ama bizim altyapıyla (emir defteri eşleşmesi, gecikme, envanter yönetimi)
imkânsız — kapsam dışı.

**SMC hakkında dürüstlük (S6):** "Smart Money Concepts" kurumsal bir yöntem
değil, perakende eğitim dünyasının (ICT kökenli) fiyat-aksiyonu SÖZLÜĞÜDÜR.
Kurumsal akrabası emir-akışı/likidite sağlayıcılığıdır — kapsam dışı. İkinci
gerçek: şampiyonumuz zaten SMC lehçesi konuşuyor (süpürme teyidi, yapı
kırılımı, kabul, retest ≈ BOS + order-block dönüşü). Bu yüzden S6, SMC'nin
şampiyonla ÖRTÜŞMEYEN tek çekirdeğine indirgendi: süpürme-dönüşü (stop avı
sonrası ters yön). Order block / FVG v1'de bilinçli olarak YOK — tanımları
esnek olduğu için ölçülemez; mekanik tanım bulunursa v2'de confluence olarak
denenir. Kural: takdire dayalı hiçbir öğe ölçüme giremez (yanlışlanamaz
strateji, strateji değildir).

**Wyckoff hakkında dürüstlük (S7):** Yöntemin üç yasası (arz-talep,
sebep-sonuç, çaba/sonuç) düşünme çerçevesi olarak sağlamdır; şematik
etiketleme (Faz A–E, "birikim mi dağıtım mı") ise GERİYE DÖNÜK yapılır —
ders kitabı örnekleri seçilmiş örneklerdir, gerçek zamanda hangi fazda
olunduğunu söyleyen mekanik kural yoktur. Bu yüzden S7, tüm şema
etiketlemesini dışarıda bırakıp yalnız Spring+Test ikilisine indirgendi.
Ayrıca bağlam farkı kayda geçsin: Wyckoff 1930'ların hisse mikroyapısı
için tasarlandı (seans kapanışları, tek borsa, temiz hacim); kripto perp'te
hacim 7/24, parçalı ve kısmen şişkindir — hacim eşikleri bu yüzden mutlak
değil SMA20'ye göreli tanımlandı.

**Kayda geçen çakışma:** Şampiyon motoru zaten kısmi bir Wyckoff
uygulamasıdır (süpürme≈Spring, hacimli kırılım≈SOS, retest≈LPS, hacim
teyidi≈çaba/sonuç). Kilit sonrası beklentisi ≈0 olması Wyckoff'u çürütmez
ama "aynı fikri Wyckoff diline çevirince düzelir" beklentisini de baştan
geçersiz kılar. S7'nin varlık nedeni yeni bir dil değil, TERS HACİM
FİLTRESİDİR.

## Aday stratejiler (6 canlı + 1 beklemede)

| # | Aile | Kural özeti (v1) | Neden |
|---|------|------------------|-------|
| S1 | **Trend takibi (TSMOM)** | 4H kapanış EMA200 üstünde VE son 12×4H getiri > 0 → LONG (tersi SHORT). Giriş LTF kapanışta (market). Stop 2×ATR(14,4H). Çıkış: 3×ATR chandelier (4H kapanışta) veya karşı rejim. | En çok belgelenmiş kurumsal aile (managed futures). Bizim kapı zaten yarısını yapıyor; bu, tam hâli. |
| S2 | **Donchian kırılımı (Turtle)** | 20×4H yüksek kırılımında LONG, 20×4H düşük kırılımında SHORT; giriş kırılım mumu kapanışında. Stop 2×ATR. Çıkış: 10×4H karşı Donchian. | Klasik trend; şampiyonun "retest bekle" yaklaşımının tersi — retest beklemenin maliyetini ölçer (hayalet R bulgusuyla doğrudan konuşur). |
| S3 | **Kısa vadeli ortalamaya dönüş** | Yalnız range rejiminde (4H ADX<20): 15m kapanış 20-SMA'dan 2σ saptığında ters yön. Stop 1.5×ATR(15m). TP: orta banda dönüş. Zaman aşımı 96 bar. | Şampiyonun sustuğu chop rejiminde çalışır — portföy açısından en tamamlayıcı bahis. |
| S4 | **Funding carry** | 8s funding penceresinde yıllıklandırılmış \|oran\| > %30 olan parite: pozitif → SHORT, negatif → LONG. Stop 2×ATR(4H). Çıkış: funding normalleşince veya 48 saat. | Kripto fonlarının fiilen işlettiği taşıma stratejisi. Gerçek funding verisini v3.6'da toplamaya başladık — doğrudan sinerji. |
| S5 | **Kesitsel momentum** (2. dalga) | Evrende 24s göreli güç sıralaması; en güçlü %10 LONG / en zayıf %10 SHORT, 8 saatte bir yeniden denge. | Farklı bahis türü (mutlak değil göreli yön). R-muhasebesine oturmaz; kendi Sharpe'ıyla raporlanmalı → implementasyonu ayrı dalga. |
| S6 | **Likidite süpürme dönüşü (SMC'nin ölçülebilir çekirdeği)** | Fiyat son 96×15m swing ekstremumunu aşar AMA mum o seviyenin gerisinde kapanır (yukarı süpürme → SHORT adayı, ayna LONG). Teyit: aynı/sonraki mum süpürme öncesi aralığa geri kapanır + hacim ≥1.5×SMA20. Giriş teyit kapanışında. Stop: ekstremum ±0.5×ATR. TP 2R sabit, zaman aşımı 96 bar. | Şampiyon kırılım DEVAMINI oynar; S6 süpürme DÖNÜŞÜNÜ oynar — stop avını satın alan taraf. Portföyde gerçek çeşitlendirme. |
| S7 | **Wyckoff Spring + Test (CANLI — 2026-08-06)** | Faz 1 (spring): 15m mum son 96 barın swing dibini kırar (`low < swing_low`) VE hacim ≥1.5×SMA20 VE kapanış swing dibinin üstüne döner. Faz 2 (test): sonraki 1–6 bar içinde bir mum swing dibine yaklaşır (`low ≤ swing_low + 0.25×ATR14`) AMA spring dibinin ÜSTÜNDE kalır (`low > spring_low`) VE hacim ≤0.7×SMA20. Giriş: test mumunun kapanışı. Stop: `spring_low − 0.25×ATR`. TP 2R, zaman aşımı 96 bar. Ayna kurgu SHORT (upthrust + test). Geçersizlik: 6 bar içinde test gelmezse veya `low ≤ spring_low` olursa kurulum iptal. | Wyckoff'un tek mekanikleştirilebilir çekirdeği. **S6'dan yapısal farkı:** S6 teyit için YÜKSEK hacim arar; Wyckoff teyitte DÜŞÜK hacim ister ("satıcı kalmadı" = kuruyan arz). Aynı olayın zıt filtresi → gerçek hipotez ayrımı. |

Hepsi **kapanış-bazlı giriş** kullanır: limit-bölge doluşu yok →
NOT_FILLED belirsizliği yok → hem gölge takip hem geçmiş test şampiyondan
daha dürüst ölçülür. Karşılaştırmada bu asimetri açıkça not edilecek
(şampiyonun hayalet R'si limit-giriş bedelini zaten gösteriyor).

## Ölçüm standardı (şampiyonla birebir aynı)
- Maliyet modeli v0 (2×taker + stop kayması + funding varsayımı) her aday için.
- Küme tanımı aynı: yön + 4H penceresi; küme-blok bootstrap CI.
- Karar eşiği aynı: **≥50 kapanmış küme + küme-CI alt sınırı > 0.**
- Bağımsız denetçi (verifier) her adayın kayıtlarını da yeniden oynatır.

## Çoklu karşılaştırma tuzağı (kritik)
5 stratejiden en iyisini seçmek, kazananın görünür performansını şişirir
(seçim yanlılığı). Kural:
1. **Seçim penceresi** ve **doğrulama penceresi** ayrılır.
2. Kazanan aday, seçildikten SONRA toplanan veride de küme-CI > 0 vermek
   zorundadır (walk-forward). Seçim penceresindeki rakamı hüküm değildir.
3. Ara sıralamalar rapor edilir ama "başarılı" etiketi yalnız doğrulama
   penceresinden çıkar.

## Geçmiş test (backtest) gerçekliği
- Gist arşivi ~2–8.5 gün derinliğinde (parite başına 262–818×15m mum) —
  dürüst backtest için YETERSİZ.
- VM üzerinden (Claude Code) Bybit kline geçmişi aylar geriye çekilebilir;
  kapanış-bazlı adaylar bu veriyle dürüst backtest edilebilir.
- Backtest yalnız BUDAMA için kullanılır (bariz çöpü ele); karar her zaman
  ileriye dönük gölge veriden çıkar.

## İzolasyon şartları (implementasyon ön koşulu)
1. Adaylar **saf fonksiyon**dur: aynı taramada zaten çekilmiş mum serileri
   üzerinde değerlendirilir — **ekstra API çağrısı sıfır** (funding zaten
   çekiliyor). Şampiyonun veri toplama zamanlaması etkilenemez.
2. Aday kayıtları **ayrı tabloya** yazılır (`challenger_signals`);
   şampiyon tablolarına tek satır yazım yok.
3. Değişmezlik testi: adaylar açıkken ve kapalıyken şampiyonun `stats()`
   çıktısı **bayt-bayt aynı** olmalı — test bunu zorlar.
4. Aday kodundaki hiçbir hata taramayı düşüremez (fail-soft, hata sayaçlı).

## Zamanlama
- **Faz A (şimdi):** bu belge. Kod yok, kilit ihlali yok.
- **Faz B tetikleyicisi:** otomatik denetim art arda 2 temiz tur + #57/#6
  kapanışı. Sonra S1–S4 + S6 implementasyonu (izolasyon şartlarıyla) + VM'de
  backtest verisi çekimi.
- **S7 tetikleyicisi (bilinçli erteleme):** S7 şu an KODLANMAZ. Gerekçe:
  (1) S3 ve S6 tam eleme aşamasında; sınav ortasında yeni değişken sokmak
  o ölçümü kirletir. (2) S6'nın "yüksek hacimli teyit" filtresi hakkında
  birkaç gün içinde veri gelecek — S6 elenirse ters filtre hipotezi
  güçlenir ve S7 daha isabetli tasarlanır. S6 kendi 50 kümesini
  doldurduğunda S7 kodlanır ve YENİ aday olarak yarışa girer; mevcut
  verinin üstüne asla yazılmaz. — **TETİKLENDİ (2026-08-06):** S6 kendi
  50 kümesini doldurdu (sahip beyanı); S7 tasarımdaki sayılarla BİREBİR
  kodlandı ve yarışa girdi. Tasarım metni değişmedi.
- **Karşılaştırma raporu:** şampiyonun Faz-1 hükmü çıktığında (≈50 küme)
  adayların ara sıralaması hazır olur. Adaylar için kesin hüküm kendi 50
  kümelerini doldurunca verilir — 8 günde kimseye madalya yok.

## Kilit uyumu
Şampiyon motoruna, eşiklerine, ölçüm penceresine dokunulmaz. Adaylar ayrı
kohort, ayrı tablo, sıfır etkileşim. Bu belge docs-only'dir.


## Örnekleme rejimi 2 (2026-08-04): stratejiye göre açık pozisyon tavanı
**Bulunan tasarım hatası:** tek tavan (15 açık pozisyon/strateji) yarışı
adaletsiz kıldı. Ölçülen tutuş süreleri: S1 medyan 45 bar, S4 37 bar,
S2 13 bar; buna karşılık S3 6 bar, S6 2 bar. Uzun tutan adaylar slotları
doldurup **yeni sinyal üretemez** hale geldi — 8 saat sonunda S3 8 küme
toplamışken S1 hâlâ 1 kümedeydi. Bu hızla hüküm "en iyi aday"a değil
"en hızlı devreden aday"a çıkardı.

**Düzeltme:** tavan tutuş süresiyle orantılı → S1/S2/S4: 40, S3/S6: 15.
Hiçbir stratejinin giriş/çıkış kuralı değişmedi; bu bir **ölçüm altyapısı**
düzeltmesidir.

**Bedeli açıkça kayda geçiyor:** tavan öncesi kayıtlar farklı kısıtla
toplandı, dolayısıyla yeni kohortla **birleştirilemez**. `regime` kolonu
eklendi; istatistikler yalnız geçerli rejimi sayar, eski kayıtlar tabloda
kalır (silinmez) ve sayısı `retired_rows` ile hem API'de hem panoda
gösterilir. S1/S2/S4 sayaçları fiilen sıfırdan başlar. Sessiz sıfırlama
yoktur — kullanıcı ne kaybettiğini görür.


## S1 doğrulama penceresi (ÖN-KAYIT — 2026-08-12, Serhat onayı)
**Seçim penceresi hükmü:** S1_TSMOM rejim-2 kohortunda 50 kümeyi doldurdu:
56 işlem, net +24.17R, küme-CI **[−0.053, +0.406]** — alt sınır sıfırın
altında → ilan edilmiş kurala göre sınavı **KIL PAYI GEÇEMEDİ**. Bu hüküm
kayda geçti; seçim penceresi rakamları bundan sonraki hiçbir hükme karışmaz.

**Ön-kayıt (bu ilandan İLERİYE):** Çoklu karşılaştırma kuralının öngördüğü
walk-forward doğrulaması S1 için bu ilanla başlar.
- Başlangıç: **2026-08-12T00:00:00Z** (`VALIDATION_WINDOWS`, challengers.py).
- Kohort: yalnız bu andan sonra DOĞAN S1 sinyalleri.
- Hüküm kuralı seçimle AYNI: ≥50 kapanmış küme VE küme-CI alt sınırı > 0.
- Strateji kuralları, tavan (40), maliyet modeli v0, küme tanımı ve
  örnekleme rejimi (2) AYNEN kalır — tavan bilerek BÜYÜTÜLMEDİ: sonuca
  bakıp örneklemi hızlandırmak/uzatmak sonuç-bağımlı örnekleme olurdu.
- İlan geri alınamaz, sonuca bakılarak uzatılamaz; pencere dolduğunda
  hüküm otomatik okunur (`/challengers → strategies.S1_TSMOM.validation`).
- Diğer adaylar etkilenmez; S3/S6'nın kenar-ölümü alarmları ayrı karar
  konusudur.


### Değişiklik notu (2026-08-12, aynı gün — kohort boşken)
Karar toplantısı Madde 4: S3/S6 kenar ölümüyle EMEKLİ; boşalan 30 slot
S1'e devredildi (tavan 40→70, efektif toplam bütçe sabit). Yukarıdaki
"tavan bilerek BÜYÜTÜLMEDİ" cümlesi bu kararla değiştirildi — doğrulama
kohortu henüz BOŞ olduğundan pencere tek tip (tavan-70) kısıtla toplanır;
sonuç-bağımlı örnekleme oluşmadı. Seçim kohortu (tavan-40) arşivde ayrıdır.
Ayrıntı ve gerekçe: config-lock.md → KİLİT-2 İLANI, Madde 4.
