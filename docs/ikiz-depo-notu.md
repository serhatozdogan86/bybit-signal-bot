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

2026-08-12 itibarıyla, o incelemenin bulduğu üç madde de **kapandı**.
**2026-08-16 eki:** midas'tan taşınan kontrolle yeni bir madde açıldı (B1, aşağıda).


| Bulgu | Durum |
|---|---|
| Retest kusuru | ✔ KİLİT-2 (2026-08-12) ile düzeltildi, sayaçlar 08-13'ten sıfırdan |
| Ölü maksimum düşüş alarmı | ✔ `d198aac` (2026-08-12) ile düzeltildi |
| S1_TSMOM örnekleminin tavanla boğulması | ✔ tavan 40 → 70, bütçe devri (toplam sabit) |

Kalan tek yapısal madde: midas'taki deney altyapısının (çıkış/giriş
laboratuvarı, hipotez kohortu, öz-denetim değişmezleri) bybit'te karşılığı
yok. Öncelik düşük — bybit'in asıl darboğazı ölçüm değil, kenar bulmak.

### B1 — Dolum/izleme penceresi mum sayısına bağlı, duvar saatine değil (kanıtlı; şu an gizil)

**Kaynak:** midas, 2026-08-16. İki sinyal (DAL, UAL) 29 Temmuz'da PENDING
doğdu ve time-stop tarihinden **9 gün sonra** hâlâ açıktı; portföy
tavanından slot yiyorlardı. Sebep: `_evaluate_signal` içinde dolum
penceresi sayacı **mum listesinin indeksi**. Sembol günlük filtrelerden
düştüğü için saatlik mumları çekilmiyordu; mum gelmeyince sayaç ilerlemedi
ve `NOT_FILLED` asla yazılmadı. midas bunu `v4.32` ile kapattı
(`close_expired_pending`: mum gerektirmeyen, `time_stop_date` tabanlı
süpürme).

**bybit'te karşılığı: VAR.** `app/services/signal_tracker.py`,
`_evaluate_signal` içinde:

```python
if not touched:
    if i + 1 >= self._fill_window:      # i = MUM LİSTESİ İNDEKSİ
        self._close(sig["id"], "NOT_FILLED", None, 0.0)
```

Aynı şekil izleme penceresinde de var: `if bars_held >= self._max_track`
(satır ~653) ve `elif i >= self._max_track` (satır ~537). Her ikisi de
mum akışına bağlı.

#### Kanıt (koşturuldu, 4/4 geçti)

`tests/test_ikiz_pencere_sayaci.py` — üretim venv'inde, gerçek
`SignalTracker` ile:

| Test | Ne gösteriyor | Sonuç |
|---|---|---|
| A — eksik mum | pencereden (24) az mum gelirse, fiyat giriş bölgesine hiç girmese bile `NOT_FILLED` yazılmaz | PENDING'de kalıyor |
| B — hiç mum yok | `evaluate_open` içindeki `if candles:` sessizce atlıyor; mumsuz süpürge yok | PENDING'de kalıyor |
| C — bedeli | sıkışan kayıt `heat_check`'te açık sayılıyor; **küme tavanı (2)** kalıcı kapanıyor | tavan kapandı |
| D — kontrol (kapsam sınırı) | mum akışı sağlamken (pencere+2 mum) pencere doğru kapanıyor | `NOT_FILLED` |

D testi önemli: sorun pencere *mantığında* değil, mum yokken hiç
çalışmamasında. Kusurun sınırını bu çiziyor.

#### İki depo arasındaki fark — bybit daha korumasız

| Emniyet | midas | bybit |
|---|---|---|
| Kayıt başına duvar saati son tarihi | var (`time_stop_date`, v4.22) | **yok** (şemada sütun yok) |
| Mum gerektirmeyen süpürme | var (`close_expired_pending`, v4.32) | **yok** |
| Evren dışı kayıt için mum çekip değerlendirme | var (orphan eval) | var (v3.0, IONQ vakası) |

Yani bybit'in tek savunması orphan eval; o da `get_series` veri
döndürmezse (parite borsadan kalkar, işlem durur, API boş döner) çalışmaz.
O durumda kaydı kapatacak **hiçbir** mekanizma kalmıyor.

#### Kilit açısından: bu bir uyum düzeltmesidir, parametre değişikliği değil

`config-lock.md` gölge kuralını **duvar saatiyle** ilan ediyor:
*"giriş 6sa / izleme 48sa"*. Kod bunu mum sayısıyla uyguluyor
(24 × 15dk = 6sa, 192 × 15dk = 48sa) — mum akışı kesilmediği sürece ikisi
aynı şey. Kesildiğinde kod **ilan edilen kuralı çiğniyor**: 6 saatlik giriş
penceresi 30 saate uzuyor. Zaman tabanlı bir süpürge eşikleri
değiştirmez, ilan edilen eşiği *uygular*. Kilit kapsamında "yalnız kritik
bug fix istisna, o da bu dosyaya tarihli not düşülerek" maddesine girer.

#### Şu an ısırıyor mu? Hayır — gizil

Canlı defterde 26 açık kayıt var, hepsi **1 günden yeni**; pencere altında
görünen dördü sıkışmış değil, sadece genç (mumlar birikiyor). Sebep yapısal:
kripto 7/24 işlem görüyor, 15 dakikalık mum günde 96 tane birikiyor, yani
24 barlık pencere 6 saatte doluyor. midas'ta pencere ancak ABD borsası
açıkken doluyordu — bu yüzden orada patladı, burada patlamadı.

#### Geçmişte ısırmış olabilir (temiz atıf yapılamıyor)

1336 kapalı kaydın 295'i `NOT_FILLED`. Normalde ~6 saatte kapanmaları
gerekir. Üç kayıt aşırı uzun kalmış:

| Parite | id | Süre | Arşivdeki mum | Giriş bölgesine temas |
|---|---|---|---|---|
| MSFTUSDT | 4 | 32,8 sa | 132 | hiç |
| BANKUSDT | 129 | 31,4 sa | 127 | hiç |
| GRAMUSDT | 122 | 29,2 sa | 118 | 39. mumda |

Üçü de 2026-07-31 17:36–17:37'de, yani **aynı dakikalarda toplu** kapandı —
`c2ac0f6` deploy'undan (17:33) ~3 dakika sonra. Bu, tek tek zaman aşımının
değil, servis yeniden başlayıp dolu arşivle yeniden değerlendirmenin
imzası: kayıtlar 30 saat boyunca değerlendirilmemiş, restart onları
kurtarmış.

**Ama temiz atıf yapılmıyor:** o tarih aynı zamanda Oracle taşınma
penceresi (`d9ae8f4`, 31 Tem 06:26). Bot o aralıkta duruyor da olabilir.
Bu üç vaka kusurla *tutarlı* bir izdir, kanıtı değildir. Kusurun kanıtı
yukarıdaki testtir.

#### Önerilen düzeltme (uygulanmadı — karar bekliyor)

midas `v4.32`'nin karşılığı: `signals` tablosuna duvar saati son tarihi
(giriş için +6sa, izleme için +48sa) ve tarama sonunda mum gerektirmeyen
bir süpürme. Not: midas'ta bu süpürge yazıldı ama **sahada hiç
tetiklenmedi** — DAL/UAL'i kurtaran orphan eval oldu. Yani süpürge iki
depoda da hâlâ denenmemiş bir emniyet freni; yazılırsa testle
tetiklenmesi gerekir.

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

2026-08-16 eki (B1): midas v4.32/v4.33 dağıtımı sırasında yapılan ikiz kontrolü — bybit `signal_tracker` okuması, üretim venv'inde koşturulan 4 kanıt testi, canlı defterden 26 açık kayıt ve 1336 kapalı kaydın süre analizi.
