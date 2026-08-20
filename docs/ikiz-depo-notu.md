# İkiz Depo Notu — midas ↔ bybit

> Bu dosyanın ikizi `bybit-signal-bot/docs/ikiz-depo-notu.md` içindedir ve
> aynı içeriği taşır. Biri değişirse diğeri de güncellenir.
>
> Oluşturma: 2026-08-12, iki depoyu birlikte inceleyen dış oturum.

## Neden bu dosya var

`midas-signal-bot`, `bybit-signal-bot` iskeletinden doğdu. İkisi aynı boru
hattını (rejim → yapı → kurulum → hacim → risk/ödül → sinyal), aynı gölge
defter mantığını ve aynı ön-kayıt kültürünü paylaşıyor.

Bunun pratik sonucu şu: **birinde bulunan bir kusur, diğerinde de aday
kusurdur.** Ama bu bugüne kadar tek yönlü işledi — bybit'ten midas'a bilgi
taşındı, midas'ta öğrenilenler bybit'e geri taşınmadı.

### Kanıt: retest kusuru

`detect_breakout_retest` içinde kırılım sonrası dilimler `break_i`'den
başlıyordu. Kırılım mumunun kapanışı tanımı gereği seviyenin doğru
tarafındadır, ve o mum seviyeyi aşağıdan geçtiği için low'u neredeyse her
zaman tolerans altındadır. Sonuç: acceptance sayacı 2 yerine fiilen 1, ve
**retest şartı tamamen boş** — yani "breakout+retest", retestsiz kovalama
girişi.

| | |
|---|---|
| midas'ta düzeltildi | 2026-08-08 (v4.23) |
| midas'taki faturası | kilit-1 defterinin 16/17 işlemi, −12R |
| bybit'te düzeltildi | 2026-08-12 (KİLİT-2) — **dört gün sonra** |

Dört gün boyunca aynı kusur, aynı kod, ikinci depoda canlı kaldı. Kimse
bakmadığı için değil; **bakılacak bir yer olmadığı için.**

## Kural: çift yönlü aktarım

Bir depoda şu üç şeyden biri olduğunda, diğer depoda karşılığı **açıkça
kontrol edilir ve sonuç bu dosyaya yazılır** (bulunmasa bile):

1. **Kanıtlı mekanizma hatası** (kilit açan türden)
2. **Ölçüm/muhasebe düzeltmesi** (defterin sayıları değişiyorsa)
3. **Yeni ölçüm veya deney aleti**

Kontrol "okudum, yok" ile kapanmaz — ikizde aynı davranışı tetikleyen bir
test yazılır. Retest kusuru sentetik veriyle böyle kanıtlanmıştı: fiyatın
seviyeyi kırıp bir daha hiç dönmediği seride eski kod setup üretiyor,
düzeltilmiş kod üretmiyordu.

## Yetenek envanteri (2026-08-12)

Örüntü: **midas deney altyapısında, bybit ölçüm altyapısında öne geçmiş.**

| Yetenek | midas | bybit |
|---|---|---|
| Bağımsız sonuç denetçisi (`verifier.py`) | **yok** | var |
| Küme-blok bootstrap güven aralığı | **yok** | var |
| NOT_FILLED anatomisi (`nf_anatomy`) | **yok** | var |
| Kayma senaryolu hayalet R | **yok** | var |
| Güven etiketi permütasyon testi | **yok** | var |
| Önceden ilan edilmiş alarm kaydı | kısmen (`self_audit`) | var (`alarms.py`) |
| Aday strateji yarışı | **yok** | var (`challengers.py`) |
| Çıkış varyantı laboratuvarı | var (`exit_lab`) | **yok** |
| Giriş stratejisi laboratuvarı | var (`strategy_lab`) | **yok** |
| Hipotez kohortu (blocked=5) | var (`hypo_lab`) | **yok** |
| Öz-denetim değişmezleri | var (`self_audit`) | **yok** |
| Bağımsız dolum doğrulama (kâğıt hesap) | var ama **kapalı** (`alpaca_mirror`) | **yok** |

## Açık maddeler — midas tarafı

Aşağıdakiler 2026-08-12 itibarıyla **açık**. Hiçbiri motora dokunmaz;
üçü ölçüm katmanı, biri belge tutarlılığı.

### M1 — Go-live eşiği tesadüfe açık ✔ KAPANDI (v4.30, 2026-08-12)

**Durum: çözüldü.** `v4.30` go-live'a altıncı şartı ekledi: işlem başına net
beklentinin küme-blok bootstrap güven aralığının alt sınırı > 0
(`signal_tracker.cluster_bootstrap_ci`, eşikler `GOLIVE_CI_*`, rapor
`golive_status.criteria.ci_low_r`; 10.000 tur, %95, sabit tohum).
Kapıyı yalnızca sıkılaştırdığı için KİLİT-2 sayacı sıfırlanmadı.
Aşağıdaki ölçüm, o kararın gerekçesi olarak kayıtta kalıyor.



`docs/go-live-kriteri.md` beş şart sayıyor ama hiçbiri **istatistiksel
anlamlılık** istemiyor. bybit'in Faz-1 kapısı istiyor: *≥50 küme VE
küme-bootstrap CI alt sınırı > 0.*

Gerçek defterden ölçüm (22 sonuçlanmış işlem, 2026-08-11):

- işlem başına net-R standart sapması: **1,112**
- 60 işlemde ortalamanın standart hatası: **0,144R**
- yani `GOLIVE_MIN_EXPECTANCY_R = 0.15` eşiği ≈ **1,0 standart hata**

20.000 denemelik bootstrap, gerçek üstünlük = 0 varsayımıyla:

| Gözlem birimi | Tesadüfen ≥ +0,15R çıkma olasılığı |
|---|---|
| 60 işlem | **%15,3** |
| 25 bağımsız küme | **%24,6** |

Yani hiçbir üstünlüğü olmayan bir motor bu kapıdan dörtte bir ihtimalle
geçebilir — ve geçtiği gün gerçek para konur.

**Öneri:** bybit'in `measurement.cluster_bootstrap` fonksiyonu midas'a
taşınsın ve go-live'a altıncı şart eklensin: *küme-CI alt sınırı > 0.*
Bu bir **sıkılaştırmadır**; `config-lock.md` gevşetmeyi yasaklar,
sıkılaştırmayı serbest bırakır. Eşik değerleri değişmediği için kohort
sıfırlanmaz.

### M2 — Bağımsız sonuç denetçisi yok (öncelik: yüksek; `docs/ideas.md`'ye ön-kayıt yapıldı 2026-08-12)

bybit'teki `verifier.py`'nin gerekçesi: *"Tracker'ın kendi değerlendirme
döngüsünü tekrar kullanan bir denetim, o döngüdeki hatayı göremez — hata
kendini doğrular."* Sonucu mumlardan sıfırdan, ayrı bir uygulamayla
yeniden türetip kayıtla karşılaştırır. bybit'te canlı sonuç: 291 kayıt
denetlendi, 0 uyuşmazlık.

midas'ta karşılığı yok — oysa midas'ın gölge muhasebesinde **tek bir
sürümde (v4.22) dört ayrı hata** düzeltildi: gap sırası, dolum barı,
time-stop çapası, net-DD. Yani daha çok hata çıkarmış bir muhasebe ve onu
bağımsız kontrol eden hiçbir şey yok.

**Öneri:** `verifier.py` midas'a uyarlansın (1h bar + gap muhasebesi
farkıyla). Salt ölçüm katmanı, kilit ihlali değil.

### M3 — Dolum kuralı her işleme peşin zarar yazıyor (öncelik: orta, ölçüm gerekli)

`signal_tracker._evaluate_signal`, LONG için:

```python
touched    = c["low"] <= sig["entry_min"]   # TETİK: bölgenin DİBİ
fill_price = sig["entry_max"]               # FİYAT: bölgenin TEPESİ
```

Yani bir işlem ancak fiyat bölgenin dibine indiğinde "girildi" sayılıyor,
ama giriş fiyatı bölgenin tepesi yazılıyor. İşlem defterde doğduğu anda
bölge genişliği kadar zararda başlıyor.

Gerçek defterden ölçüm (26 dolmuş işlem):

| Sonuç | n | Ortalama peşin zarar (bölge/risk) |
|---|---|---|
| WIN | 4 | 0,15R |
| LOSS | 16 | 0,28R |
| EXPIRED | 2 | 1,06R |
| **tümü** | **26** | **0,33R** |

Net beklenti −0,50R iken peşin zarar 0,33R — açığın üçte ikisi buradan.
Ayrıca bölge genişledikçe sonuç kötüleşiyor.

Mevcut korumalar bunu yakalamıyor: `MAX_ENTRY_ZONE_ATR` ve
`WORST_FILL_TP1_R_MIN` bölgeyi **ATR'ye** oranlıyor, **riske**
oranlamıyor. Stop yapısal olduğunda risk 1,2 ATR'den küçük olabiliyor ve
bölge/risk oranı 1,0'ı aşabiliyor (defterde GM 1,10 · V 1,02).

**Uyarı — bu gerçek bir strateji kusuru DA olabilir, ölçüm aracının fazla
kötümser olması DA.** Dolum kuralı bilinçli konmuş (2 Ağu, konsey 5/5;
emirler elle giriliyor, 30-60 sn gecikme). Kodla ayırt edilemez.
Ayırt etmenin tek yolu `alpaca_mirror` — zaten bunun için yazılmış,
4 adımlık planın 2. adımında, şu an kapalı.

**Önerilen hipotez (karar kuralı önceden yazıldı, `research-log.md`
yöntemi):** Kilit-2 kohortu 40 sonuçlanan işleme ulaştığında, bölge/risk
oranı medyanın üstündeki ve altındaki işlemlerin net-R beklentileri
karşılaştırılır. Üst dilim alt dilimden en az **0,20R kötüyse** ve işaret
iki yarı dönemde aynıysa, bölge/risk tavanı (öneri: 0,25R) motora eklenir.
Aksi halde hipotez yanlışlanmış sayılır ve kayda geçer.

### M4 — Rejim filtresinin fırsat maliyeti ölçülmüyor (öncelik: düşük; `docs/ideas.md`'ye ön-kayıt yapıldı 2026-08-12)

bybit'te piyasa kapısı boru hattının **sonunda**: engellenen karar tam
plan seviyeleri taşır ve `blocked=1` karşı-olgu kohortuna yazılır, böylece
kapının koruma mı fırsat maliyeti mi olduğu ölçülebilir.

midas'ta `MARKET_REGIME` **2. sırada** sert kesiyor; plan hiç kurulmuyor,
dolayısıyla filtrenin kaç iyi işlemi engellediği bilinemiyor. İlginç olan:
aynı prensip midas'ta kill-switch (`blocked=3`) ve açılış penceresi
(`blocked=4`) için zaten uygulanmış — sadece ana rejim filtresine
uygulanmamış.

### M5 — Belge kodla çelişiyor (öncelik: düşük, dakikalık iş)

`signal_tracker` docstring'i hâlâ *"Fill fiyati: bölgenin ilk değen
kenarı"* diyor. Bu **bybit'in davranışının tarifi**; midas'ın kendi kodu
tam katetme istiyor (M3). `stats()` içindeki not doğru
("conservative fills (full zone traversal)"), docstring güncellenmemiş.

## Açık maddeler — bybit tarafı

2026-08-12 itibarıyla, bu incelemenin bulduğu üç madde de **kapandı**:

| Bulgu | Durum |
|---|---|
| Retest kusuru | ✔ KİLİT-2 (2026-08-12) ile düzeltildi, sayaçlar 08-13'ten sıfırdan |
| Ölü maksimum düşüş alarmı | ✔ `d198aac` (2026-08-12) ile düzeltildi |
| S1_TSMOM örnekleminin tavanla boğulması | ✔ tavan 40 → 70, bütçe devri (toplam sabit) |

Kalan tek yapısal madde: midas'taki deney altyapısının (çıkış/giriş
laboratuvarı, hipotez kohortu, öz-denetim değişmezleri) bybit'te karşılığı
yok. Öncelik düşük — bybit'in asıl darboğazı ölçüm değil, kenar bulmak.

## Kaynak

Bu notu üreten inceleme: her iki botun karar üreten katmanlarının satır
satır okunması + canlı uçlardan (`/performance`, `/signals`, `/diag`,
`/alarms`, `/challengers`) doğrulama + iki koşturulmuş kanıt testi
(retest kusuru, ölü alarm). 2026-08-11/12.

## S8 Fonlama Sıkışması — ikiz kontrolü (2026-08-13)

**Sonuç: UYGULANAMAZ (N/A) — gerekçeli.** bybit'e S8_FUNDSQUEEZE adayı
eklendi (aşırı funding + fiyat teyidi, S4'ten derin eşik). midas'ta
karşılığı ARANDI:

- midas bir **ABD hisse** botudur (Alpaca; earnings/fundamentals/premarket/
  market_calendar servisleri). Hisse senedinde **funding oranı YOKTUR** —
  funding perpetual-futures'a özgü bir mekanizmadır.
- midas'ta tek "funding" geçişi bir yorum satırıdır: "funding yerine not"
  (app/server.py) — yani midas funding kavramını bilinçle YOKA sayar.
- Dolayısıyla S8'in midas'ta ne karşılığı ne de "aynı davranışı tetikleyen
  test"i mümkün: tetikleyecek girdi (funding) o evrende mevcut değil.

**Karar:** S8 crypto-perp'e özgüdür; ikiz aktarımı gerekmez. Bu, Kural 3b'nin
"bulunmasa bile yaz" gereğidir — kontrol yapıldı, uygulanamaz olduğu
gerekçesiyle kapandı (S4_CARRY için de aynı mantık geçerlidir; midas'ta
funding ailesi yoktur).

## Korelasyon ölçüm aleti — ikiz kontrolü (2026-08-13)

**Sonuç: TAŞINABİLİR — midas'ta AÇIK İŞ.** bybit'e çoklu-strateji
korelasyon/örtüşme aleti eklendi (app/services/correlation.py + /correlation;
Faz A salt-rapor: çift korelasyonu, N_eff, aynı-gün-aynı-yön oranı).
midas'ta karşılığı arandı: **StrategyLab çoklu paralel strateji işletiyor**
(Trade.strategy alanı, strateji bazlı defter) ve korelasyon/örtüşme ölçümü
YOK (grep: 'correlation/korelasyon' sıfır sonuç). Yani alet ikize birebir
taşınabilir ve StrategyLab varyantlarının bağımsızlığını ölçer.
Bu oturumun midas'a yazma erişimi yok → **midas oturumuna açık iş**:
correlation.py'nin uyarlanması + ölçüm-only anahtar testi. (S9_GECE
stratejisi ise 3b kapsamı DIŞI — mekanizma hatası/ölçüm düzeltmesi değil,
yeni bahis; ayrıca hisse piyasası gece kapalıyken kriptonun 21–23 UTC
penceresi midas evreninde tanımsız.)

## P4 OI-kohort aleti + S10 52w-HIGH — ikiz kontrolü (2026-08-16)

**P4 (OI gölge-kohort etiketi): UYGULANAMAZ (N/A).** Open interest bir
türev-piyasa (perp/futures) kavramıdır; midas ABD spot hisse botudur ve
Alpaca verisinde OI yoktur (S8/S4 funding kararıyla aynı gerekçe sınıfı).
Kontrol edildi, karşılık yok.

**S10 (52-hafta zirvesi): TAŞINABİLİR — midas'ta AÇIK İŞ (güçlü aday).**
52w-high çapası ASLEN hisse senedi anomalisidir (George-Hwang 2004, 20 yıl
hakemli literatür) — kripto uyarlamasını biz yaptık; midas'ın kendi
evreninde uygulanması daha da doğal. midas StrategyLab'i çoklu strateji
işletiyor; 52w-high haftalık LONG sepeti oraya aday olarak eklenebilir.
Bu oturumun midas'a yazma erişimi yok → midas oturumuna açık iş olarak
kaydedildi (weekly_52w_selection saf fonksiyonu birebir taşınabilir).

## S11 sıkışma-kırılımı + S12 hacim-kapılı seans kırılımı — ikiz kontrolü (2026-08-17)

Not: ikisi de YENİ BAHİS (mekanizma hatası/ölçüm düzeltmesi değil), yani
Kural 3b'nin zorunlu kapsamı dışında; kayıt gönüllü bilgilendirmedir.

**S11 (sıkışma-kırılımı): TAŞINABİLİR — midas'a aday olabilir.** TTM
Squeeze aslen hisse senedi aracıdır (John Carter); BB/KC hesabı günlük
hisse mumlarında birebir çalışır. `squeeze_run` / `squeeze_momentum` saf
fonksiyonları taşınabilir. midas oturumuna açık iş olarak not edildi.

**S12 (göreli-hacim seans kırılımı): TAŞINABİLİR — midas'ta DAHA DA
DOĞAL.** Zarattini-Aziz bulgusu zaten ABD hisse ORB'udur (gerçek açılış
çanı var); kripto tarafındaki 00:00 UTC çapası bizim uyarlamamızdır.
midas'ta orijinal haliyle (09:30 ET açılış aralığı + göreli hacim
kapısı) uygulanması kripto versiyonundan daha sadıktır. Açık iş.

## Çıkış laboratuvarı (V0/V1) — ikiz kontrolü (2026-08-17)

**Kaynak bu kez İKİZİN KENDİSİ:** midas 2026-08-17'de V4_IZ (iz süren
çıkış varyantı) ile çıkış laboratuvarını genişletti ve "çıkış tasarımı
girişten belirleyici" bulgusunu raporladı. Kural 3b'nin ters yönlü
işleyişi: ikizde doğan yeni ÖLÇÜM ALETİ burada karşılıksızdı → karşılığı
kuruldu: app/services/exit_lab.py + /exitlab (ön-kayıt ideas.md
2026-08-17). Varyant tanımı hizalı: V1_IZ = iz süren stop, iz mesafesi
1 × başlangıç riski (midas V4_IZ ile aynı mekanizma sınıfı) — iki botun
çıkış karneleri artık karşılaştırılabilir. Hüküm kuralı iki tarafta da
kendi verisinden, bağımsız verilir.

## Sağlayıcı sessiz kırpması — ikiz kontrolü (2026-08-18) · **BULUNDU**

**Kaynak: midas v4.40.** Finnhub bilanço takvimi ucu ~1500 satırda
**sessizce** kırpıyordu: HTTP 200, `retCode` yok, hata yok — eksik veri tam
sanıldı. Düşen uç **eski** uçtu. midas düzeltmesi: pencereyi 3 günlük
dilimlere böl + 1400 satırlık kırpma kanaryası (`cap_suspect`, denetim
kırmızı yakar).

Kural 3b gereği bybit'te karşılığı arandı. **Kalıp bulundu** — üç uç
VM'den canlı ölçüldü (2026-08-18):

| Uç | İstendi | Geldi | Hata verdi mi? |
|---|---|---|---|
| `/v5/market/kline` | limit=1500 | **1000 satır** | hayır, `retCode=0` |
| `/v5/market/funding/history` | 200 gün | **66.3 gün** (200 satır) | hayır, `retCode=0` |
| `/v5/market/tickers` | tümü | 829 sembol, cursor yok | — (kırpma yok) |

`instruments-info` tek sayfada 824 sembol döndü (cursor YOK), tickers'ta
eksik yok — **enstrüman listesinde kırpma yok**. Sayfalama gerekmedi ama
sınır yakın (829/1000): evren büyürse cursor gerekecek.

### Asıl bulgu: funding geçmişi bir MUHASEBE hatası

`signal_tracker._backfill_funding` kapanmış her işlem için gerçek funding
maliyetini toplayıp `funding_r_real` olarak deftere yazıyor. Uç tek istekte
en çok 200 kayıt ve **yalnız en yeni uçtan** veriyor; `startTime` ne kadar
geriye verilirse verilsin eskiler sessizce düşüyor. Sonuç zinciri:

> eksik funding → maliyet olduğundan **küçük** → net-R olduğundan **iyi**
> → küme-CI olduğundan **yüksek** → **go-live kapısı yanlış yönde açılır**

Kırpma eşiği pariteye göre değişiyor (824 paritede ölçüldü):

| Funding aralığı | Parite | 200 kayıt kaç günü kapsar |
|---|---|---|
| 8 saat | 374 | 66,7 gün |
| **4 saat** | **408** | **33,3 gün** |
| 1 saat | 2 | 8,3 gün |

Yani evrenin **yarısından fazlası** 33 günlük pencereyle sınırlıydı.

### Fiilen zarar verdi mi? — HAYIR (ölçüldü)

Canlı defterdeki 305 kapanmış işlem (WIN/LOSS, dolmuş) tarandı:
en uzun işlem **5,79 gün** (VVVUSDT), ortanca 0,14 gün. En dar kırpma
eşiği 8,3 gün. **Hiçbir kayıt etkilenmemiş** — `funding_r_real` sayıları
sağlam, defter yeniden hesaplanmayı gerektirmiyor.

Bu bir **mayın**: motor bugünkü time-stop'uyla eşiğe değmiyor, ama S10
(haftalık 52w sepeti) gibi uzun tutuşlu bir aday veya time-stop'un
gevşetilmesi eşiği aşar ve hata sessizce deftere girer.

### Yapılan

- `tests/test_invariants.py`: sınıfı kapatan üç değişmezlik testi
  (`test_funding_history_completes_range_despite_provider_cap`,
  `test_funding_history_single_page_makes_one_call`,
  `test_kline_request_never_exceeds_provider_cap`). Sahte uç, gerçek
  davranışı taklit ediyor: tavan kadar satır, **en yeni uçtan**.
  Düzeltmesiz kodda ikisi KIRMIZI (200/270 kayıt; `_KLINE_CAP` yok).
- `bybit_client.get_funding_history`: sayfalama — tavana dayanan her
  sayfadan sonra `endTime` en eski kaydın bir öncesine çekilir, aralık
  tamamlanır. Sayfalar arası hata olursa **None** döner (yarım veri
  döndürmek sessiz muhasebe hatasıdır; fail-close 2.2).
- `bybit_client.get_kline_rows`: tavan üstü limit isteği `_KLINE_CAP`'e
  çekilir ve `bybit_limit_capped` uyarısı loglanır.

**Gerçek uçta doğrulandı** (VM, düzeltilmiş istemci): BTCUSDT 200 gün →
**600 kayıt / 199,7 gün** (önce 200 kayıt / 66,3 gün), ETHUSDT 120 gün →
360 kayıt / 119,7 gün; sıralı, mükerrersiz. kline limit=1500 → uyarı
basıldı, 1000'e çekildi.

### Ters yön: midas'a taşınabilir mi?

midas kendi kırpmasını v4.40'ta kapattı, ama oradaki çözüm **takvim ucuna
özel** (dilimleme + kanarya). Buradaki genel ders — *"sağlayıcı tavanına
dayanan yanıt tam sayılamaz"* — midas'ın **diğer** uçları için
kontrol edilmedi: Alpaca bar sayfalaması, `/v2/stocks/bars` limit'i ve
fundamentals uçları aynı sınıfa açık. midas oturumuna **açık iş**.

## S-ATT1 (Wikipedia dikkat şoku) — ikiz kontrolü (2026-08-17)

Kripto backtest hükmü: **ELENDİ** (net −22R, küme-CI üst < 0; ideas.md).
İkiz için not: dikkat-anomalisi literatürünün asıl güçlü olduğu yer ABD
HİSSE piyasasıdır (Da-Engelberg-Gao "attention" ailesi) — midas kendi
evreninde AYRI ön-kayıtla test etmek isterse bizim hüküm ona engel
değildir (farklı evren, farklı veri). Araç zinciri (Wikimedia indirici +
z-skor + T+1 disiplini) birebir taşınabilir. Açık iş DEĞİL; yalnız
bilgilendirme.

## Gap dolumu ve R paydası — ikiz kontrolü (2026-08-21)

**Sonuç: G1 bybit'te BULUNMADI (yapısal olarak bağışık). G2 ters yönde
BULUNDU — midas'ın 2 Ağustos düzeltmesi bybit'e hiç taşınmamış.**

Tetikleyen bulgu: midas kilit-2 kohortunda JNJ **+7,91R**. Dolum bölgenin
altında (256,00 · bölge 258,02–259,03) oluştuğu için R paydası tasarım
riski 4,00 yerine **1,475**'e düştü. Aynı çıkışla bölge içi dolumda
+2,29R, bölgenin kötü ucunda +1,92R olurdu.

### Kural farkı

```python
# midas  signal_tracker._evaluate_signal
touched    = c["low"] <= sig["entry_min"]        # TETİK: bölgenin DİBİ (tam katetme)
fill_price = sig["entry_max"]                    # FİYAT: bölgenin tepesi
if is_long and c["open"] < sig["entry_min"]:     # GAP DALI
    fill_price = c["open"]                       #   → dolum açılıştan

# bybit  signal_tracker._evaluate_signal
touched    = c["low"] <= sig["entry_max"]        # TETİK: bölgenin TEPESİ (tek tık)
fill_price = sig["entry_max"]                    # FİYAT: her zaman kenar — GAP DALI YOK
```

İki bağımsız fark var ve **zıt yönlere** çalışıyorlar: midas tetikte
katı ama fiyatta gap'e açık; bybit tetikte gevşek ama fiyatta sabit.

---

### G1 — Gap dalı: bybit'te YOK, defter temiz

Ölçüm (bybit canlı defteri, kapanmış ve dolmuş 1337 kayıt):

| Kontrol | Sonuç |
|---|---|
| Dolum fiyatı tam bölge kenarında | **1337 / 1337** |
| Bölge dışı dolum | **0** |
| Tasarım riski / fiili risk oranı | min 0,75 · ortanca 0,853 · **maks 1,00** |
| Oranı 1,10'un üstünde olan kayıt | **0** |

Oran hiçbir kayıtta 1,00'ı aşmıyor: bybit'te fiili risk **her zaman**
tasarım riskinden büyük ya da eşit. R paydası kısalamıyor, dolayısıyla
şişme mekanizması burada doğamaz.

**Karşı-olgusal — midas kuralı bu deftere uygulansaydı** (aynı 1337
kayıt, arşivlenmiş 15 dk mumlarla yeniden oynatıldı):

| | n | gerçek R | midas kuralıyla | fark |
|---|---:|---:|---:|---:|
| LOSS | 125 | −125,00 | −111,00 | +14,00 |
| WIN | 48 | +129,03 | **+461,89** | +332,86 |
| **toplam** | **173** (%12,9) | **+4,03** | **+350,89** | **+346,86** |

Beklenti 0,023 R/işlem → **2,028 R/işlem**. Kazananlarda ortalama
2,69R → 9,62R (**3,6 kat**); payda ortalama **3,39 kat** küçülüyor.
Uç örnekler: MRVLUSDT 2,85R → 77,36R · CAPUSDT 4,80R → 64,76R ·
UBUSDT 2,32R → 37,76R.

**Asimetri — asıl mesele bu.** Zarar tanımı gereği stop'a kadardır, yani
dolum nereye kayarsa kaysın ≈ −1R'ye çapalıdır (tabloda 125 zarar
−125,00 → −111,00, neredeyse sabit). Kazanç ise payda küçüldükçe
serbestçe büyür. Kural beklentiyi **yalnızca yukarı** itebilir; gap yoğun
bir kohortta defter yapısal olarak iyimserdir.

**Karşı-olgusalın sınırı (dürüst kayıt):** çıkış fiyatları bybit'in kendi
dolumuyla oluştu. Gerçekte dolum stop'a yaklaşsaydı **daha çok işlem
stop'a çarpardı** ve kazananların bir kısmı hiç hayatta kalmazdı. Yani
+350,89R bir tahmin değil, **üst sınırdır**. Mekanizmanın yönü ve
asimetrisi kesin; büyüklüğü abartılıdır.

**midas tarafı:** bu, M3'ün (dolum kuralı her işleme peşin zarar yazıyor)
**ters bacağıdır**. Aynı kural normal durumda kötümser (bölgenin kötü
ucundan doldurur), gap durumunda iyimser (stop'un dibinden doldurur).
İki bacağın net etkisi ölçülmedi. Kilit-2 kohortunda gap dolumlu tek
kazanan JNJ; o +2,29R olsaydı kohort NET'i −3,43R yerine ≈ −9,05R,
maksimum düşüş 8,90R yerine ≈ 9,05R olurdu (yani 8R aşımı JNJ'ye bağlı
değil, JNJ olmadan **daha derin**).

---

### G2 — Ters yön: tetik kuralı. bybit'te AÇIK MADDE

midas 2 Ağustos'ta (konsey 5/5, "%100 dolum iyimserliği") tetiği bölgenin
dibine çekti: *bölgenin yakın ucuna bir tık dokunmak dolum saymaz;
emirler elle giriliyor, 30–60 sn gecikme var.* **Bu düzeltme bybit'e hiç
taşınmadı** — bybit hâlâ tek tık dokunuşta dolum yazıyor.

Ölçüm (bybit defteri, 1338 kapanmış dolum — G1 koşusundan sonra bir
işlem daha kapandığı için sayı bir fazla):

| | n | toplam R |
|---|---:|---:|
| midas tetiğiyle **dolmayacak** kayıt | **149** (%11,1) | **+178,87** |
| — WIN | 92 | +217,02 |
| — LOSS | 49 | −49,00 |
| — EXPIRED | 8 | +10,85 |

Bu alt küme çıkarılsaydı defter **+6,96R → −171,91R**, beklenti
+0,005 → **−0,145 R/işlem**. Yalnız temiz kohortta (blocked=0): 340 işlem
+64,36R, bunun +66,86R'si bu 45 kayıttan — yani temiz kohort da
**eksiye** düşerdi (≈ −2,50R).

Başka bir deyişle: **bybit defterinin artıda görünmesinin tamamı, midas'ın
üç hafta önce iyimser bulup terk ettiği tetik kuralından geliyor.**

Bu bir hüküm değil, bir soru: bölgeye asılı **duran limit emri** varsa tek
tık dokunuş gerçekten doldurur (borsa emri sırayla eşler). Elle, sinyal
geldikten sonra giriliyorsa doldurmaz. midas'ın konseyi ikincisine karar
vermişti. İki bot da elle giriliyor. **Karar toplantısına.**

---

### Yapılan (kod DEĞİŞTİRİLMEDİ)

- `midas/tests/test_ikiz_gap_dolum.py` — 4 test, davranışı sabitler:
  gap dalının tetiklendiği, paydanın 2,50'den 1,00'a düştüğü, aynı
  çıkışta R'nin 1,00R yerine 5,00R yazıldığı, ve **zarar kolunda iki
  kuralın da tam −1R verdiği** (asimetri kanıtı).
  Kırmızı kanıtı: gap dalı kapatılmış kopyada 2 test KIRILDI
  (`assert 4.0 < 0.01` — R 5,00 yerine 1,00).
- `bybit/tests/test_invariants.py::test_gap_acilisinda_bile_dolum_bolge_kenarindan`
  — dolumun bölge kenarına bağlı kalmasını zorunlu kılar; gap dalının
  sonradan buraya taşınmasını engeller.
  Kırmızı kanıtı: midas gap dalı eklenmiş kopyada test KIRILDI
  (dolum 99,0 geldi, 101,0 bekleniyordu).
- G2 için **test yazılmadı**: orada bir kusur değil, iki meşru kural
  arasında bir **seçim** var. Karar verilmeden değişmezlik yazmak, kararı
  test dosyasına gizlice gömmek olur.

### Açık iş

1. **bybit:** G2 kararı — tetik bölgenin dibine mi çekilecek? Defterin
   tamamının işaretini değiştirdiği için kilit süreci konusudur.
2. **midas:** M3 + G1 birlikte ölçülmeli. Dolum kuralının iki bacağının
   net etkisi bilinmiyor; `alpaca_mirror` tam da bunu ayırt etmek için
   yazılmıştı (13 çift, kademe 1).
