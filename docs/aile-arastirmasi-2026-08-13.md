# KARŞILAŞTIRMALI NİHAİ RAPOR — Aday Strateji Envanteri Sentezi

**Tarih:** 2026-08-13 · **Kapsam:** 7 araştırma kolundan gelen 37 aday + 6 meta-katman önerisi + denetçi uyarıları
**Önce sonuç:** 37 aday tekilleştirme sonrası **26 gerçek adaya** indi. Puanlamada ilk 5: **Gece Penceresi (21–23 UTC)**, **P1 OI-Flush Dönüşü**, **P4 OI-Onaylı Kırılım Filtresi**, **52-Hafta Zirvesi Yakınlığı**, **S-ATT1 Wikipedia Dikkat Şoku**. Bu beşli bilinçli olarak beş FARKLI bilgi kaynağından seçildi: takvim, pozisyon stoku, pozisyon teyidi, çapa-momentumu, kitle dikkati — hiçbiri roster'daki fiyat-kırılım/funding ailelerinin kopyası değil. Meta-katman önerileri aday değil defter iyileştirmesidir; orada ilk iş **korelasyon ölçüm aleti (Faz A)** olmalı çünkü diğer her şeyin altyapısını kurar.

---

## 1. Tekilleştirme ve elemeler

Denetçi uyarılarının tamamı uygulandı:

| İşlem | Aday(lar) | Gerekçe |
|---|---|---|
| **BİRLEŞTİRİLDİ** | Mevsimsellik "Gece Penceresi" + Geniş-süpürme "BTC gün-içi mevsimsellik" | Aynı strateji (21–23 UTC long), iki koldan geldi. Tek ön-kayıt olarak birleştirildi ("GECE" adıyla). İki ayrı aday gibi yarışsaydı çifte sayım olurdu. |
| **ELENDİ** | V5 Keltner/ATR kanal | S2 Donchian ile aynı vol-ölçekli kanal-kırılım ailesi. Bağımsız aday değil; **S2 emekli olursa halef adayı** olarak nota alındı. Hudson-Urquhart kanıtı kaybolmuyor — o kanıt zaten S2'nin ailesini destekliyor. |
| **ELENDİ** | Hacim-koşullu 1-gün reversal (likidite provizyonu) | Ölü S3 ve CEPTE'deki "ortalamaya-dönüş dirilişi" ile aynı aile; CLAUDE.md ÖNERME kuralı gereği kurul önüne çıkamaz. Kolun kendisi de işaretlemişti. |
| **ÜÇTEN BİR SEÇİLDİ** | V4 Larry Williams / k-sigma aşırı-gün / MAX-momentum | Üçü aynı "günlük aşırılık + ~1 gün/hafta tutma" ailesi. **MAX-momentum seçildi** (iki hakemli makale + robustluk kontrolleri; V4 tamamen doğrulanamayan pratisyen kanıt, k-sigma dar/eski örneklem). V4 ve k-sigma listeden düştü. |
| **KOŞULA BAĞLANDI** | PREM-DIV ve P5 | S8 ile "kalabalık taraf çözülmesi" üçlüsü. İkisi de ancak **S8 ile işlem-örtüşme oranı ölçüldükten sonra** ve aynı anda en fazla biri yarışa girebilir. |
| **KOŞULA BAĞLANDI** | V1 sıkışma kırılımı | Kabul edilirse S2/şampiyonla aynı-gün-aynı-yön sinyal örtüşme raporu zorunlu ön-kayıt maddesi. |
| **TEK SAHİBE VERİLDİ** | Vol-hedefleme overlay | Hem volatilite kolunda hem meta-katmanda vardı; **meta-katmana** atandı. |
| **ŞART EKLENDİ** | V2 düşük-vol, ML kompozit | Raftaki kesitsel momentumun ölüm nedeni (tek-rejim penceresi) bunlarda da geçerli; hüküm penceresine "en az 2 farklı rejim epizodu örneklenmiş olmalı" şartı ön-kayda yazılır. |

Kalan: **26 aday** (5 baz/pozisyonlanma-P, 3 baz-endeks, 4 mevsimsellik/takvim, 3 öncül-gecikme, 4 kesitsel, 3 volatilite, 4 dış-veri) + 6 meta-katman.

---

## 2. Puan tablosu

Dört boyut, her biri 1–5: **Kanıt** (yayınlanmış kenar kanıtının gücü), **Veri** (Bybit v5'te erişilebilirlik + geriye dönük test edilebilirlik), **Ölçüm** (R-katsayısı + küme-CI çerçevesine uyum ve 50 kümenin makul sürede dolması), **Çeşitlilik** (mevcut roster'a mekanizma katkısı).

| # | Aday | Kanıt | Veri | Ölçüm | Çeşit. | **Toplam** |
|---|---|---|---|---|---|---|
| 1 | **GECE — 21–23 UTC penceresi** (birleşik) | 3 | 5 | 5 | 5 | **18** |
| 2 | **P1 — OI-Flush dönüşü** | 3 | 5 | 5 | 4 | **17** |
| 3 | **P4 — OI-onaylı kırılım filtresi** | 3 | 5 | 5 | 2 | **15** |
| 4 | **52w-HIGH — zirveye yakınlık** | 4 | 5 | 3 | 3 | **15** |
| 5 | **S-ATT1 — Wikipedia dikkat şoku** | 3 | 3 | 4 | 5 | **15** |
| 6 | V1 — sıkışma kırılımı | 2 | 5 | 5 | 3 | 15 |
| 7 | PB-MOM — baz momentumu | 3 | 4 | 5 | 3 | 15 |
| 8 | MID-FADE — perp−endeks sapma söndürme | 2 | 4 | 4 | 5 | 15 |
| 9 | L1 — BTC şok → gecikmeli alt takibi | 3 | 5 | 3 | 4 | 15 |
| 10 | L3 — tahterevalli (haftalık ters) | 3 | 5 | 3 | 4 | 15 |
| 11 | MAX-momentum (aile temsilcisi) | 3 | 5 | 3 | 3 | 14 |
| 12 | V2 — düşük-vol eğimi | 3 | 5 | 2 | 4 | 14 |
| 13 | S9 — unlock-öncesi short | 3 | 2 | 4 | 5 | 14 |
| 14 | PREM-DIV — prim−funding ıraksaması | 2 | 4 | 5 | 2 | 13 |
| 15 | P3 — taker akış dengesizliği | 4 | 2 | 3 | 4 | 13 |
| 16 | P2 — likidasyon kaskadı dönüşü | 3 | 2 | 3 | 4 | 12 |
| 17 | Funding-damgası emir dengesizliği | 3 | 2 | 3 | 4 | 12 |
| 18 | V3 — vol rejim anahtarı | 2 | 5 | 2 | 3 | 12 |
| 19 | ML kompozit (illikidite×mom×alfa) | 3 | 5 | 2 | 2 | 12 |
| 20 | S-ATT2 — CoinGecko trending | 2 | 3 | 3 | 4 | 12 |
| 21 | FOMC-öncesi drift | 2 | 5 | 1 | 3 | 11 |
| 22 | CME vade-öncesi short | 2 | 5 | 1 | 3 | 11 |
| 23 | P5 — account-ratio kontraryan | 1 | 3 | 3 | 3 | 10 |
| 24 | L2 — alt-sezon rejim kapısı | 1 | 4 | 1 | 3 | 9 |
| 25 | UNLOCK-REBOUND long | 1 | 2 | 3 | 3 | 9 |
| 26 | S-ATT3 — Fear & Greed kontraryan | 1 | 3 | 1 | 2 | 7 |

**Eşitlik kırma notu (15 puanlılar):** P4, 52w-HIGH ve S-ATT1 öne alındı çünkü P4'ün marjinal maliyeti sıfıra yakın (P1'in verisini paylaşır), 52w-HIGH bu listedeki en güçlü hakemli kanıta sahip (JBF 2026) ve S-ATT1 roster'a ilk kez fiyat-dışı bilgi kaynağı sokuyor (denetçinin tespit ettiği sistematik kör noktanın doğrudan kapanışı). V1/PB-MOM/MID-FADE/L1/L3 "ikinci dalga" olarak sırada bekler.

---

## 3. İlk 5 aday — detaylı

### 3.1 GECE — 21:00–23:00 UTC Gece Penceresi Long'u (18 puan)

**Fikir tek cümleyle:** New York borsası kapandıktan sonra, Asya açılmadan önceki iki saatte BTC tarihsel olarak günün en güçlü ortalama getirisini veriyor; her gün bu iki saati long tut, başka hiçbir şeye bakma.

**Kural (ön-kayıt taslağı):** Her gün 21:00 UTC'de BTCUSDT long aç, 23:00 UTC'de kapat. Felaket stopu = giriş − 2×ATR(15m,14); R bu mesafeyle tanımlanır (zaman-çıkışlı işlemde R tanımı için sentetik stop şart). Küme = takvim günü. Genişletme (ayrı ön-kayıt): en likit 5 parite eşit riskle — o zaman aynı günün tüm işlemleri TEK küme. Pazartesi-Asya varyantı (Pazar 23:00 → Pazartesi 23:00) AYRI ön-kayıt olarak notlanır, veriye bakıp seçim YAPILMAZ.

**Kaynak:** Vojtko & Javorská, SSRN 4581124; Quantpedia; QuantifiedStrategies ve Concretum bağımsız replikasyonları. Rapor edilen: yıllık ~%40.6, Calmar 1.79 (2015–2022, Gemini verisi) — rakamlar özet düzeyi, birincil PDF'ten doğrulanamadı.

**Neden 1 numara:** (a) Çeşitlilik tavan — roster'da takvim/saat tetikli hiçbir motor yok, fiyat kalıbından tamamen bağımsız; (b) ölçüm hızı tavan — günde 1 küme, **50 küme ~2–2.5 ayda dolar**, tüm envanterin en hızlı hükmü; (c) maliyet taban — 1 günlük iş, sıfır yeni veri. "Ucuz, hızlı yanlışlanabilir, tamamen farklı" üçlüsünü tek başına sağlayan tek aday.

**Riskler:** Örneklem 2022 başında bitiyor; ETF sonrası pencere ölmüş olabilir (Quantpedia'nın kendisi 2022–23 zayıflığını söylüyor). 24 saatten seçilmiş 2 saat = veri madenciliği şüphesi taşır. Koşulsuz long — ayı rejiminde sürekli kanar. Kenar saat başına küçük; kâğıt maliyet sabitleri (spread/kayma) kötümser seçilmezse sahte pozitif üretir. **Bu adayın işi kenarı kanıtlamak değil, hâlâ yaşayıp yaşamadığını iki ayda öğrenmek.**

**Uygulama planı:** (1) Eşikleri docs/ideas.md'ye ön-kayıt; (2) challengers.py'ye saat-tetikli sınıf (~1 gün); (3) yalnız BTCUSDT ile başla, 5-parite genişletmesi ayrı kayıt; (4) maliyet modeline gece-saat spread payı eklendiğini testle doğrula; (5) izolasyon + değişmezlik testleri, pytest yeşil → push.

---

### 3.2 P1 — OI-Flush Deleveraging Dönüşü (17 puan)

**Fikir:** Fiyat düşerken açık pozisyon toplamı (OI = piyasadaki açık bahis miktarı) hızla eriyorsa, satışın kaynağı zorla kapatılan kaldıraçlı pozisyonlardır; bu satıcılar fiyata bakmaz ve bittiklerinde baskı kalkar — orada long al.

**Kural (ön-kayıt taslağı):** 24 saatte ΔOI/OI ≤ −%10 (**kontrat adedi** bazlı, USD değeri değil) VE fiyat aynı pencerede ≥ 2 ATR(4H) düşmüş VE son 15m kapanış bir öncekinin üstünde (stabilizasyon) → LONG. Stop: pencere dibi − 1 ATR(15m); hedef 2R; zaman aşımı 24 saat. Küme = yön+4H pencere.

**Kaynak:** Glassnode deleveraging analizi (nitel: "long-kapanış sinyali birçok lokal dibi işaretledi"); Hong & Yogo (JFE 2012) — OI'nin fiyattan daha bilgilendirici olduğuna hakemli çapa (emtia, analoji).

**Neden 2 numara:** Veri durumu mükemmel ve **doğrulanmış**: `/v5/market/open-interest` geçmişi sembolün lansmanına kadar çekilebilir → **geriye dönük test MÜMKÜN** (bu listede dış-veri gerektirmeyen adaylar içinde tek gerçek backtest'li dönüş fikri). Üstelik scheduler'ın zaten her taramada çektiği tickers yanıtında anlık OI bedava geliyor — canlı toplama maliyeti sıfır. Roster'da pozisyonlanma verisi kullanan hiçbir motor yok.

**Riskler:** Düşen bıçak — deleveraging çok-günlük kaskada dönüşürse erken giriş (Ekim 2025 tipi). Glassnode isabetin yükselen rejimde yoğunlaştığını söylüyor; ayıda zayıflar. Ve dürüst uyarı: bu bir DÖNÜŞ stratejisi — S3/S6'nın öldüğü aile (ayrıntı Tuzaklar bölümünde; ön-kayıtta S6'dan farklılaşma gerekçesi açık yazılmalı: tetik verisi pozisyon STOKU, fiyat süpürmesi değil).

**Uygulama planı:** (1) Taramada OI'yi DB'ye yazan kolon (~yarım gün); (2) open-interest endpoint'inden geçmiş indirip **önce backtest** — kural canlıya çıkmadan kâğıt üstünde tarihsel davranışı görülebilir (bu lüks az adayda var); (3) eşikler ön-kayıt; (4) challenger sınıfı + testler. Toplam ~2-3 gün.

---

### 3.3 P4 — OI-Onaylı Kırılım Filtresi (15 puan)

**Fikir:** Kırılım anında OI artıyorsa hareketi "yeni para" finanse ediyor (devam olası); OI düşüyorsa hareket eski pozisyonların kapanması (yakıt bitiyor, kırılım sahte olmaya yatkın). Yeni motor değil, sahte-kırılım ayıklayıcı.

**Kural:** FİLTRE modu (önerilen): şampiyon/S2 sinyali tetiklendiğinde ΔOI(24h, kontrat adedi) ≥ +%5 ise gir, değilse atla — **gölge kohort olarak**, mevcut motorlara dokunmadan (Kural 1 ihlali yok, yeni challenger kaydı). Aynı kırılım sinyalinin OI'li/OI'siz iki kohortu yan yana ölçülür; filtrenin katkısı doğrudan CI ile sınanır.

**Kaynak:** Hong & Yogo (JFE 2012, NBER w16712) — OI büyümesi getirileri öngörür; kripto kadran çerçevesi pratisyen düzeyi.

**Neden ilk 5'te:** P1'in veri yatırımını paylaşır — **tek veri işiyle iki aday**. Ölçüm tasarımı envanterin en zarifi: eşleştirilmiş kohort karşılaştırması mutlak CI'dan çok daha hızlı bilgi verir. Çeşitlilik puanı düşük (2) ama rolü zaten çeşitlilik değil, mevcut en güçlü ailenin isabetini artırmak.

**Riskler:** USD-değerli OI kullanılırsa sinyal fiyatın kendisine döner (mekanik korelasyon) — kontrat adedi zorunlu, birim testiyle kilitlenmeli. Aylık-emtia kanıtından saatlik-kripto kurala sıçrama büyük. OI artışı yön söylemez — yön fiyattan, OI yalnız teyit.

**Uygulama planı:** P1'in OI deposu üstüne birkaç satır kural + kohort etiketi + test; ~1 gün.

---

### 3.4 52w-HIGH — 52-Hafta Zirvesine Yakınlık (15 puan)

**Fikir:** Yatırımcılar 52-hafta zirvesini çapa alır; fiyat zirveye yakınken iyi habere eksik tepki verilir ve yükseliş sürüklenerek devam eder. Hisselerde 20 yıllık literatür (George-Hwang 2004), kripto kesitinde yeni hakemli doğrulama.

**Kural:** Pazartesi 00:00 UTC: yakınlık = günlük kapanış / son 365 günün en yüksek kapanışı. Hem üst decile'da hem yakınlık ≥ 0.90 olanlara long; stop = giriş − 2×ATR(14g); çıkış 1 hafta zaman-çıkışı veya stop. Küme = formasyon haftası. Long-only (Cakici 2024: kriptoda kenar uzun bacakta).

**Kaynak:** Jia ve ark., Journal of Banking & Finance Vol.182 (2026): decile long-short haftalık EW %0.7 / VW %1.4, momentumdan bağımsız — **envanterin en güçlü hakemli kenar rakamı** (özet düzeyinden; birincil tablolar doğrulanamadı).

**Neden ilk 5'te:** Kanıt gücü 4 — listede yalnız P3 bununla yarışıyor ama P3'ün veri maliyeti çok yüksek. Veri tamamen mevcut. Raftaki kesitsel momentumdan farkı gerçek: sinyal geçmiş getiri değil, zirveye-YAKINLIK çapası (kırılım olmasa da örnekler; George-Hwang iki sinyalin ayrı bilgi taşıdığını göstermişti).

**Riskler:** Ölçüm yavaş — küme=hafta ile 50 küme ≈ 1 yıl. Ayı rejiminde sinyal kurur (doğal fren ama hüküm gecikir). Akademik evren mikro-cap dahil binlerce coin; 150 likit perp'te kenar incelebilir. S2/şampiyonla kesişim oranı ilk 4 hafta raporlanmalı. Rejim-çeşitliliği şartı (V2/ML ile aynı madde) ön-kayda yazılmalı.

**Uygulama planı:** Haftalık tarama + challengers şablonu, ~1-2 gün; 365 günlük kline arşiv derinliği kontrolü ilk iş.

---

### 3.5 S-ATT1 — Wikipedia Dikkat Şoku Momentumu (15 puan)

**Fikir:** Bir coine olağandışı kitle dikkati (Wikipedia sayfa görüntülemesi patlaması) geldiğinde perakende alım baskısı 1–5 gün fiyatı sürükler. Denetçinin işaretlediği sistematik kör noktanın — "Bybit-dışı bilgi kaynağı hiç taranmadı" — doğrudan kapanışı.

**Kural:** ~150 perp'ten Wikipedia makalesi olanlar (~40-70 coin, bir kez elle eşlenir). Günlük görüntülemede log-z skoru ≥ 2 VE 24h getiri 0 ile +%25 arasında (kötü-haber ve pump-kovalama filtreleri) → LONG, stop 2×ATR(4H), 3 gün zaman-stopu, 7 gün yeniden-giriş yasağı. Küme = takvim günü (dikkat şokları haber günlerinde korelasyonlu).

**Kaynak:** Hoang & Vo (J. Behavioral & Experimental Finance 2024, Google aramaları), Maitre ve ark. (JBF 2025, Twitter), Smales (IRFA 2022) — kesitsel coin-bazlı çalışmalar pozitif. Karşı-kanıt dürüstçe not: BTC-tek-seri çalışmaları (Shen/Urquhart 2019) getiri öngörüsü bulamıyor; Google/Twitter→Wikipedia aktarımı bir varsayım.

**Neden ilk 5'te:** Çeşitlilik 5 — roster'a **ilk fiyat-dışı sinyal**. Wikimedia API ücretsiz, anahtarsız, günde ~60 istek (önemsiz yük). Ölçüm hızı makul (50 küme ~4-8 ay tahmini). Gerçekleşen S2-korelasyonu bilgi-kaynağı ayrımından yüksek çıkabilir — "S2 girişinden 24h içinde açılan dikkat-işlemi oranı" ölçüm gereği loglanır.

**Riskler:** Ters nedensellik (dikkat çoğu kez DÜNKÜ fiyatın sonucu — sinyal gecikmiş momentum kopyasına dönüşebilir); kötü-haber dikkati (hack de görüntüleme patlatır — fiyat filtresi kısmi koruma); veri T+1 gecikmeli; kapsam büyük-coin yanlı; yeni dış bağımlılık (API kesintisi izlenmeli); ayı rejiminde dikkat-longları S3-vari kanayabilir.

**Uygulama planı:** (1) Sembol→makale eşlemesi elle, çift kontrollü (~2 saat, en riskli adım); (2) VM'den Wikimedia erişim testi; (3) günlük fetch cron'u fail-soft (Bybit taramasını asla bloklamaz); (4) z-hesabı + challenger; toplam ~1-2 gün.

---

## 4. Meta-katman değerlendirmesi (aday DEĞİL — defter iyileştirmesi)

Bu altı öneri yeni kenar aramaz; mevcut ve gelecek stratejilerin ölçümünü/riskini iyileştirir. Hepsi "gölge çift-defter + eşleştirilmiş küme bootstrap" desenini kullanıyor — bu doğru desen, çünkü ana kitap davranışına dokunmadan (Kural 1) çarpanın katkısı ölçülüyor. Önerilen sıra:

**1. Korelasyon/risk-katkısı ölçüm aleti — Faz A (ÖNCE BU).** Salt rapor: strateji-çifti R korelasyon matrisi, etkin bağımsız bahis sayısı, aynı-gün-aynı-yön çakışma oranı. Hiçbir karar değiştirmez, 1 günlük iş, /measurement rotasına eklenir. İki ek gerekçe: (a) denetçinin şart koştuğu **S8↔PREM-DIV↔P5 örtüşme ölçümü** ve V1/S-ATT1'in çakışma raporları zaten bu aleti gerektiriyor — bu yapılmadan o adaylar yarışa giremez; (b) diğer tüm meta-katmanların paralel-defter altyapısını kurar. Faz B (ters-vol ağırlıklama) DeMiguel/Timmermann frenleriyle, en erken 3 ay yayın sonrası, ayrı ön-kayıtla.

**2. İstatistiksel drawdown alarm katmanı (Rej-Seager-Bouchaud).** Botun felsefesiyle birebir aynı dilde: "ilan edilen Sharpe ile bu derinlik/süredeki zarar dönemi tutarlı mı?" sorusunun kapalı-form cevabı. S3'ün −158R'sini daha erken yakalardı. Kural 5'in "alarm önceden ilan edilir" şartına doğal uyar; alarms.py'ye eklenir. Şişman kuyruk için kuantiller Monte Carlo/blok-bootstrap ile tablolanmalı, normal varsayımıyla değil. Önerilen yetki sınırı: bu katman yalnız AĞIRLIK kısar, emeklilik hükmü CI sürecinde kalır. ~2-3 gün.

**3. Koşullu vol-hedefleme overlay'i.** Kanıt tabanı geniş ve hakemli (Moreira-Muir JoF 2017; Harvey/Man 2018; Bongaerts FAJ 2020). Cederburg karşı-kanıtı ciddiye alınarak yalnız UÇLARDA ayar yapan koşullu varyant, donmuş parametreyle. Tek dikkat: kriptoda en iyi kırılım işlemleri vol patlamasıyla gelir — yüksek-vol'de küçülme şampiyonun en iyi işlemlerini kırpabilir; ölçüm bu etkileşimi strateji-bazında ayrıştırmalı. ~1-2 gün.

**4. Trend×Carry uyum çarpanı.** İki mevcut bilgi kaynağını (yön sinyali + funding) ilk kez tek işlemde birleştirir; sıfır yeni veri. Dikkat: kriptoda funding çoğunlukla hafif pozitif → LONG'lar sistematik 0.75-1.0 bandına kayıp yön eğilimi doğabilir; ilk ay hücre dağılımı raporlanmalı. S4/S8'e karşı artımsal katkı ölçülmeli. ~1-2 gün.

**5-6. Rejim-koşullu ağırlıklama ve strateji-momentum tilti — BEKLESİN.** İkisi de aynı şeyin (hangi strateji şu an çalışıyor) modelli/modelsiz versiyonu; **aynı pencerede birlikte test edilemezler** (etki ayrıştırılamaz) ve p-hacking'e en açık iki öneri bunlar. Ayrıca 1-4 üst üste bindikçe atıf sorunu büyür. Önerim: aynı anda EN FAZLA BİR meta-katman aktif ölçümde olsun; sıra yukarıdaki gibi. Strateji-momentum için "ölçüm-önce" modu (tilt uygulamadan salt-rapor: T_i işareti sonraki 20-küme R'sini öngörüyor mu?) neredeyse bedava ve zararsız — o başlatılabilir.

---

## 5. Tuzaklar — cazip görünen ama ölülerimizin ailesinden olanlar

S3 (ortalamaya-dönüş, net −158R) ve S6 (süpürme-dönüşü) bu depoda "aşırılığı söndür / dönüşü yakala" ailesinin iki cesedi. Aşağıdakiler o aileye değişen yakınlıkta akraba:

| Aday | Akrabalık | Hüküm |
|---|---|---|
| **Hacim-koşullu 1-gün reversal** | S3'ün birebir ailesi + CEPTE ihlali; üstelik kenarın yoğun olduğu illikit dilim, S3'ü öldüren kâğıt-dolum iyimserliğinin tam adresi | **ELENDİ** — kurul önüne çıkamaz |
| **UNLOCK-REBOUND long** | "Büyük düşüş sonrası toparlanma longu" = klasik düşen bıçak; doğrudan kanıt sıfır | Elenmedi ama tek başına ÖNERİLMEZ; ancak S9 kurulursa yarım günlük ek olarak |
| **P1 OI-Flush** ve **P2 kaskad fade** | S6'ya mekanik akraba: ikisi de zorunlu-akış spike'ını fade ediyor | Yaşayabilirler, ŞARTLA: ön-kayıtta S6'dan farklılaşma açıkça yazılmalı (tetik verisi OI/likidasyon STOKU, fiyat süpürmesi değil; stabilizasyon teyidi + sıkı zaman-stopu). Bu yazılmazsa aynı ailenin üçüncü ölümü olası. P2'nin ek sorunları: geçmiş veri yok (backtest imkânsız), kaskad anında slipaj modeli iyimser |
| **P5 account-ratio fade** | "Kalabalığa karşı erken durmak" — trendli piyasada kalabalık uzun süre haklı kalır; S3'ün ölüm şekli buydu. Kanıt fiilen sıfır | Düşük öncelik; ancak S8-örtüşme ölçümü sonrası ve küçük tavanla |
| **S-ATT3 Fear & Greed** | Piyasa-geneli kontraryan; 2018/2022 tipi ayıda "korku haklıydı" | Fiilen eleme: hakemli kanıt aleyhte + küme=episod ile 50 küme YILLAR alır — ölçüm çerçevesiyle yapısal uyumsuz |
| **MID-FADE** | Görünüşte S3'ün ta kendisi (aşırılığı söndür). Gerçek fark: çapa DIŞSAL (çok-borsalı spot endeksi), dönüş hedefi tanımlı, 24s zaman-stopu var — S3'ü öldüren "sürünen aşırılık" kipine panzehir | İkinci dalga adayı olarak meşru; ama ana risk ciddi: perp fiyat keşfinde ÖNDEDİR (Alexander ve ark., JFM 2020) — sapma bilgili akışsa fade sistematik kanar |
| **V4 / k-sigma aşırı-gün** | Ölüm şekli değil ama ölüm ORTAMI ortak: çırpıntılı yatay rejimde seri zarar, S3'ün kanadığı koşul | MAX seçimiyle zaten listeden düştüler |

Genel ilke: bu depoda dönüş/fade fikri ancak **(a) dışsal veya yapısal bir çapa, (b) tanımlı dönüş hedefi, (c) sıkı zaman-stopu, (d) ön-kayıtta S3/S6'dan farklılaşma gerekçesi** dördünü birden taşıyorsa aday olabilir.

---

## 6. Önerilen yürütme sırası (özet)

1. **Hemen:** Meta Faz A (korelasyon aleti) + GECE ön-kayıt ve canlıya alma (toplam ~2 gün). GECE 2.5 ayda ilk hükmü verir.
2. **Hafta 1-2:** OI toplama + P1 backtest → sonuç pozitifse P1+P4 ön-kayıt (tek veri yatırımı, iki aday).
3. **Hafta 2-3:** 52w-HIGH ve S-ATT1 ön-kayıt (uzun soluklu, erken başlamalı — hükümleri 6-12 ay).
4. **Sonra:** DD-alarm katmanı; ikinci dalga (V1, PB-MOM, MID-FADE, L1/L3) roster kapasitesi ve Faz A örtüşme raporlarına göre.
5. **Şartlı bekleme:** S9-unlock (takvim kaynağı çift-doğrulama vetting'i geçerse), P3/P2/funding-damgası (WS veri yatırımı ancak pozisyonlanma ailesi ilk sınavları geçerse).

Ölçüm şablonuna zorunlu yeni alan (birkaç kolun doğru işaretlediği kritik risk): **küme tanımı** her ön-kayıtta açık yazılmalı — takvim-tetikli ve kesitsel adaylarda küme = GÜN/OLAY/HAFTA, parite değil; aksi halde CI yapay daralır ve sahte hüküm üretir.

---

## 7. Kaynakça

**Hakemli / akademik:**
- Hudson & Urquhart, "Technical Trading and Cryptocurrencies", Annals of Operations Research 2019 — https://link.springer.com/article/10.1007/s10479-019-03357-1
- Hong & Yogo, "What Does Futures Market Interest Tell Us?", JFE 2012 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1364674 · https://www.nber.org/system/files/working_papers/w16712/revisions/w16712.rev1.pdf
- Jia ve ark., 52-week high kripto kesiti, J. Banking & Finance 2026 — https://www.sciencedirect.com/science/article/abs/pii/S0378426625002122
- Ozdamar ve ark., MAX etkisi, Financial Innovation 2021 — https://link.springer.com/article/10.1186/s40854-021-00291-9 · IRFA 2021 — https://ideas.repec.org/a/eee/finana/v77y2021ics1057521921001630.html
- Hoang & Vo, dikkat ve kripto getirileri, JBEF 2024 — https://www.sciencedirect.com/science/article/pii/S2214635024001060
- Maitre ve ark., Twitter dikkati, JBF 2025 — https://www.sciencedirect.com/science/article/pii/S0378426625001384
- Anastasopoulos ve ark., "Order Flow and Cryptocurrency Returns", J. Financial Markets 2026 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5020002
- Jia/Wu/Yan/Yin, "Seesaw Effect", J. Empirical Finance 2023 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3465924
- Boons & Prado, "Basis-Momentum", Journal of Finance 2019 — https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12738
- Burggraf & Rudolf, low-vol anomalisi, FRL 2021 — https://www.sciencedirect.com/science/article/abs/pii/S154461232030667X · Pyo ve ark., "Revisiting…", FRL 2026 — https://www.sciencedirect.com/science/article/abs/pii/S1544612326003818
- Pyo & Lee, FOMC ve BTC, FRL 2020 — https://www.sciencedirect.com/science/article/abs/pii/S154461231930159X · FRBNY karşı-kanıt — https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1052.pdf
- Alexander ve ark., BitMEX fiyat keşfi, JFM 2020 (MID-FADE ana riski) · Cheng ve ark., likidasyonlar, Applied Economics 2021 — https://www.tandfonline.com/doi/abs/10.1080/00036846.2021.1922597 · arXiv kaskad dallanması — https://arxiv.org/html/2608.03616
- Hansen-Kim-Kimbrough, periyodik patlamalar, J. Financial Econometrics 2024 — https://academic.oup.com/jfec/article-abstract/22/1/224/6759403 · Kim & Hansen — https://arxiv.org/abs/2607.09426
- Cakici ve ark., ML ve kripto kesiti, IRFA 2024 — https://www.sciencedirect.com/science/article/abs/pii/S1057521924001765
- Moreira & Muir, "Volatility-Managed Portfolios", JoF 2017 — https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513 · Harvey ve ark. 2018 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538 · Bongaerts ve ark., FAJ 2020 — https://repub.eur.nl/pub/130215/Bongaerts-Kang-van-Dijk-Conditional-volatility-targeting-2020-FAJ.pdf · Cederburg ve ark., JFE 2020 — https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X
- Rej-Seager-Bouchaud, drawdown kuantilleri — https://arxiv.org/abs/1707.01457 · Kaminski & Lo, stop kuralları — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=968338
- Maillard-Roncalli-Teiletche, ERC — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1271972 · DeMiguel ve ark., 1/N, RFS 2009 — https://academic.oup.com/rfs/article-abstract/22/5/1915/1592901 · Ehsani & Linnainmaa, faktör momentumu, JoF 2022 — https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.13131
- Koijen ve ark., "Carry", JFE 2018 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2298565 · BIS "Crypto Carry" WP 1087 — https://www.bis.org/publ/work1087.pdf
- Caporale & Plastun, aşırı-gün, FMPM 2020 — https://link.springer.com/article/10.1007/s11408-020-00357-1
- Smales, dikkat, IRFA 2022 — https://doi.org/10.2139/ssrn.3889923 · Shen/Urquhart/Wang karşı-kanıt, Econ Letters 2019 — https://www.sciencedirect.com/science/article/abs/pii/S016517651830065X

**Pratisyen / endüstri (doğrulanamayan rakamlar işaretli):**
- Vojtko & Javorská, BTC gün-içi mevsimsellik, SSRN 4581124 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4581124 · Quantpedia — https://quantpedia.com/strategies/intraday-seasonality-in-bitcoin · Concretum — https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/
- Glassnode deleveraging — https://insights.glassnode.com/leverage-position-openings-and-closures/
- Keyrock unlock etüdü — https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/ · unlocks.app — https://insights.unlocks.app/do-token-unlocks-crash-prices/ · bağımsız backtest (NO-GO hükmü) — https://medium.com/coinmonks/i-backtested-shorting-token-unlocks-heres-why-i-m-not-trading-it-yet-42e237d40d9a
- Presto, funding öngörü gücü — https://www.prestolabs.io/research/can-funding-rate-predict-price-change

**Veri API'leri:**
- Bybit v5: open-interest — https://bybit-exchange.github.io/docs/v5/market/open-interest · account-ratio — https://bybit-exchange.github.io/docs/v5/market/long-short-ratio · premium-index kline — https://bybit-exchange.github.io/docs/api-explorer/v5/market/premium-index-kline · funding tanımı — https://www.bybit.com/en/help-center/article/Introduction-to-Funding-Rate
- Wikimedia Analytics — https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/getting-started.html · CoinGecko — https://www.coingecko.com/en/api · alternative.me F&G — https://alternative.me/crypto/fear-and-greed-index/ · DefiLlama unlocks — https://defillama.com/unlocks

*Not: SSRN/arXiv PDF'lerinin çoğu bu ortamdan erişim-engelli; "DOĞRULANAMADI" işaretli tüm rakamlar arama-özeti/ikincil kaynak düzeyindedir ve ön-kayıtlarda bu statüleriyle anılmalıdır.*