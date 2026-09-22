# TASLAK — PORTFÖY ÖN-KAYDI (⚠️ MÜHÜRLENMEDİ)

**Bu dosya bir TASLAKTIR. Hiçbir maddesi yürürlükte değildir.**
Serhat "mühürle" derse içeriği config-lock.md'ye tutanak, kural kısmı
docs/ideas.md'ye ön-kayıt olarak geçer ve bu dosya arşivlenir.

Hazırlayan: Claude · 2026-09-22

---

## 0. NEDEN İKİYE BÖLÜNMÜŞ BİR MÜHÜR?

Serhat'ın 2026-09-21 uyarısı: *"bu bot üzerine 2 aydır uğraşıyoruz;
mühürlemeden önce bu gerçekliği göz önünde bulundur."* Uyarı yerinde ve
taslağın şeklini belirledi.

İki gerçek yan yana duruyor:

1. **Ölçüm kurallarını şimdi mühürlemezsek sonuç güvenilmez olur.**
   Üyeyi sonradan seçmek, kümeyi sonradan incelmek, kapıyı sonradan
   gevşetmek — hepsi bu projenin tek değerli şeyini yok eder.
2. **Altyapı henüz oturmadı.** Bu haftanın kendisi kanıt: 13 günlük
   yedek arızası (09-18) ve şampiyon/aday muhasebe uyuşmazlığı (09-20).
   İkisi de 2 aylık bir projenin normal çocukluk hastalıkları. 3 yıllık
   katı bir mühür, bozuk bir muhasebeyi de 3 yıl boyunca çivilerdi.

Çözüm: **taraflı olabileceğimiz her şey mühürlenir, taraflı
olamayacağımız şeyler açık kalır.** Ölçüt ve seçim mühürlü; takvim ve
altyapı onarımı açık — ama onarım için katı bir usul var (Madde 8).

---

## 1. MÜHÜRLENEN — ÜYE LİSTESİ (donmuş)

Üye kuralı (getiriye BAKMAZ): emekli olmayan **+** maliyet/işlem
≤ 0.05R **+** ≥ 50 kapanmış küme.

Bu kural 2026-09-20 ölçümünde şu beş motoru seçti ve liste **pencere
açılışında DONAR**:

| Üye | Küme | Net R | Maliyet/işlem |
|---|---|---|---|
| S1_TSMOM | 445 | +78.16 | 0.037 |
| S2_DONCHIAN | 417 | +39.94 | 0.041 |
| S8_FUNDSQUEEZE | 218 | +5.40 | 0.019 |
| S11_SQUEEZE | 91 | +10.47 | 0.022 |
| S12_RELVOL | 70 | **−15.26** | 0.048 |

**S12 net EKSİ olduğu hâlde listededir.** Kuralı dürüst yapan tam olarak
budur: seçim getiriye bakmıyor.

### ⚠️ EN ÖNEMLİ MADDE: ölen üye ÇIKARILMAZ
Pencere boyunca bir üye kenar ölümüne girse bile portföyden
**çıkarılmaz.** Kaybettiğini gördükten sonra birini listeden atmak,
hayatta kalma yanlılığıdır ve portföyü yapay olarak şişirir. Liste
açılışta ne ise kapanışta odur.

Aynı sebeple: pencere sırasında kurala uyar hâle gelen YENİ bir motor
bu portföye **katılamaz.** Katılmak isterse o ayrı bir portföydür ve
kendi ön-kaydını ister.

---

## 2. MÜHÜRLENEN — PORTFÖY KÜMESİ TANIMI

**Portföy kümesi = YÖN + TAKVİM GÜNÜ**, motorlar arası birleşik.
İki üye aynı gün aynı yönde işlem açtıysa bu **tek bağımsız bahistir.**

Gerekçe: küme mantığının tüm amacı bağımlı işlemleri tek bloğa
koymaktır. Motorlar arası örtüşmeyi saymazsak portföy, aynı bahsi beş
kez sayarak yapay bir daralma üretir — bu projenin yapabileceği en
tehlikeli özaldatmaca olurdu. Ölçüldü: 4.324 işlem → 96 blok.

Günlük kova, motorların kendi 4 saatlik kovasından **kabadır**; yani
seçim kasıtlı olarak muhafazakârdır (daha az blok → daha geniş aralık →
geçmek daha ZOR). **Bu tanım pencere boyunca incelemez.** Kovayı
sonradan daraltmak, geçmeyi kolaylaştırmak demektir.

---

## 3. MÜHÜRLENEN — KAPI ve DEĞERLENDİRME ANI

**Kapı koşulu:** portföyün küme-CI **alt sınırı > 0**. (Değişmedi;
veriden türetilmiş yeni bir eşik YOK.)

**Değerlendirme TEK BİR İLAN EDİLMİŞ TARİHTE yapılır:**

> ### 2029-09-30
> (bugünden 1.104 gün)

Tarih neden bu: güç hesabı, bugünkü beklenti ve oynaklıkla kapının
açılabilmesi için ~1.062 gün gerektiğini söylüyor (2029-08-19); yuvarlak
ay sonuna çekildi. **Bu bir tahmindir, kural değildir** — kural yalnız
"o tarihte, bir kez bakılır".

### Neden tek tarih: sürekli bakış yasağı
Her ay "geçti mi?" diye bakıp ilk artı çıktığında mühürlemek, klasik
p-hacking'dir (isteğe bağlı durdurma). Yeterince sık bakarsan gürültü er
geç sana istediğini gösterir. O yüzden **lehte hüküm yalnız bu tarihte
verilebilir.**

---

## 4. MÜHÜRLENEN — ERKEN ÇIKIŞ YALNIZ ALEYHTE (asimetrik)

- **Lehte erken bitiş YOK.** Aralık ara dönemde artıya geçse bile hüküm
  verilmez; 2029-09-30 beklenir.
- **Aleyhte erken bitiş VAR.** Portföyün küme-CI **üst sınırı < 0**
  olursa (kenar ölümü) pencere o anda kapanır ve hüküm GEÇEMEDİ olur.

Bu asimetri bilinçlidir: kendi lehimize erken durmak yanlılıktır,
aleyhimize erken durmak dürüstlüktür.

---

## 5. MÜHÜRLENEN — HÜKÜM KANALI

Hüküm YALNIZ önceden ilan edilmiş alarm kanalından okunur
(`app/services/alarms.py`). **Pano kartları ara göstergedir, hüküm
değildir** — 2026-08-20 dersi: kilit hükmünü pano kartından okumuş,
yanılmıştım.

Panodaki portföy kartı bu uyarıyı kendi içinde taşır ve testle zorlanır.

---

## 6. MÜHÜRLENEN — ARA OKUMALAR HÜKÜM DEĞİLDİR

3 yıl boyunca panoya sık bakacağız. Her bakış bir ara okumadır.
Ara okumadan hüküm çıkarmak bu projede iki kez oldu (çıkış lab 09-01,
yön/rejim premisi 08-20) ve ikisi de yanlış çıktı. Ara okuma; rapor,
sohbet ve tutanakta **hüküm değil** diye etiketlenir.

---

## 7. MÜHÜRLENEN — MALİYET MODELİ v0 GEVŞETİLMEZ

Taker varsayımı, stop kayması ve funding sabitleri pencere boyunca
değişmez. Maker (limit emir) varsayımına geçmek modeli gevşetmektir ve
ancak dolum oranı KANITLANIRSA, ayrı bir ön-kayıtla tartışılır.

---

## 8. AÇIK KALAN — ALTYAPI ONARIMI (katı usulle)

Ölçüm altyapısındaki **hatalar** düzeltilebilir. Yoksa 3 yıl boyunca
bozuk bir muhasebeye mahkûm oluruz. Ama bu kapı, sonuç beğenilmediğinde
"düzeltme" adı altında kullanılamaz. Usul (2026-09-20'de uygulandı,
işe yaradı, kural yapılıyor):

1. Önce sınıfı kapatan **kırmızı test** (bozuk kodda kırmızı vermeli).
2. Kusur, **sonuçlara etkisinden bağımsız olarak** tarif edilir.
3. **Yeni sayılar GÖRÜLMEDEN önce** tutanağa yazılır: "bu düzeltmeden
   sonra sayı ne çıkarsa çıksın, mühürlü hükümler açılmaz."
4. İkiz depo (midas) kontrol edilir (Kural 3b).

Düzeltme **ileriye dönüktür**; geçmiş mühürlü hükümler yeniden
hesaplanmaz.

---

## 9. AÇIK KALAN — TAAHHÜT, 6 AYDA BİR YENİLENİR

Aşağıdaki tarihlerde durum gözden geçirilir:

| # | Tarih |
|---|---|
| 1 | 2027-03-23 |
| 2 | 2027-09-21 |
| 3 | 2028-03-21 |
| 4 | 2028-09-19 |
| 5 | 2029-03-20 |

**Gözden geçirmenin YAPABİLECEĞİ tek şey: projeyi DURDURMAK.**
Serhat istediği an "yeter" diyebilir; ölçüm durur, defter arşivlenir.

**Gözden geçirmenin YAPAMAYACAKLARI (çubuğu oynatma yasağı):**
- Değerlendirme tarihini ileri almak ("biraz daha bekleyelim, düzelir")
- Değerlendirme tarihini öne almak ("şu an iyi görünüyor, mühürleyelim")
- Kapıyı gevşetmek, kümeyi incelmek, üye listesini değiştirmek

Yani: **durdurabilirsin, ama kolaylaştıramazsın.**

---

## 10. AÇIKÇA KAYDA GEÇEN ZAYIFLIKLAR

Bunlar taslağın kusurları değil; kabul edilmiş sınırlarıdır.

1. **Havuzu geçmiş veriye bakarak tanıyoruz.** Üye kuralı getiriye
   bakmasa bile, bu beş motorun varlığı geçmişte şekillendi. Tek ilaç
   ileriye dönük ölçüm — zaten yapılan bu.
2. **Kenar küçük.** Ölçülen +0.027R/işlem, ima edilen yıllık Sharpe
   ~1.15. Gerçek olsa bile kanıtı 3 yıl sürer.
3. **Rejim değişebilir.** 3 yıl boyunca piyasanın aynı kalacağı
   varsayımı şüphelidir. Eğer kenar rejime bağlıysa, pencere onu
   karışık bir ortalama olarak ölçer.
4. **Sonuç "hâlâ bilmiyoruz" olabilir.** En olası tek sonuç bu değil,
   ama gerçek bir ihtimal. Şimdiden yazıyorum ki 2029'da sürpriz olmasın.
5. **2 aylık bir projede 3 yıllık pencere.** Orantısızlığın farkındayım;
   Madde 9 (6 aylık yenileme) tam da bunun için var.

---

## 11. MÜHÜRLENİRSE YAPILACAK İŞLER

1. `config-lock.md`'ye tarihli tutanak; `ideas.md`'ye kural ön-kaydı.
2. Üye listesi koda **donmuş sabit** olarak girer (canlı kural değil) —
   ölen üyenin listeden düşmediğini zorlayan test.
3. Portföy kapısı ve kenar ölümü için **alarm** eklenir (hüküm kanalı);
   testle zorlanır.
4. Panoya pencere sayacı: "değerlendirme tarihine kalan gün".
5. Panodan bağımsız bildirim yolu (açık madde, 09-18 dersi) — 3 yıllık
   koşuda bu artık lüks değil.
