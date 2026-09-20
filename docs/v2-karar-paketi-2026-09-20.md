# V2 KARAR PAKETİ — Serhat'ın kararı için tam dosya (2026-09-20)

Bu dosya bir KARAR ÖNCESİ brifingtir. Kural değildir, ön-kayıt değildir.
Kararlar verildikten sonra kural olacaklar docs/ideas.md'ye ÖN-KAYITLA
girer; tutanak config-lock.md'ye yazılır.

---

## 1. TEK CÜMLE

v1 bir kenar bulamadı ama kenar kaybetmedi de — brüt olarak tam
yazı-turaydı; onu öldüren **her işlemde ödediği 0.185R maliyetti**, ve
bu maliyet neredeyse tamamen **stopun çok dar olmasından** geliyor.

---

## 2. MÜHÜRLÜ GERÇEKLER (tartışma dışı, ölçülmüş)

| # | Gerçek | Kaynak |
|---|---|---|
| 1 | ≥50 kümeye ulaşan **her** motor sınavı geçemedi. İstisna yok. | config-lock 09-18 |
| 2 | v1 şampiyon: 429 işlem / 197 küme, **brüt −3.52R**, maliyet **−79.33R**, net **−82.85R** | /anatomy 09-18 |
| 3 | Maliyet/işlem **0.185R** — bütçemizin (0.05R) 3.7 katı | /anatomy |
| 4 | Stop mesafesi medyanı **%1.4** | /anatomy |
| 5 | Kayıp **geniş tabanlı**: en kötü 5 küme toplamın 1/3'ü; kalan 192 küme hâlâ −55.6R | /anatomy |
| 6 | Yön ile rejim **aynı değişken**: SHORT=bear (59/27), LONG=bull+nötr (370/170) birebir. v1 zaten rejim uyumlu. | /anatomy |
| 7 | P4 (OI kapısı): backtest çarpıcı fark gösterdi, canlı **tersini** verdi → ELENDİ | config-lock 08-30 |
| 8 | Çıkış lab ara okuması: 1×R iz süren çıkış trend/kırılım ailesinde **geri tepiyor**; tüm fark-CI'ler sıfırı içeriyor | 09-05, hüküm değil |

**6 numara özellikle önemli:** Ağustos'ta "v2'nin iskeleti rejim uyumu
olmalı" demiştik. Yanlıştı — zaten öyleydi. O eksene harcanacak emek
boşa giderdi. Bunu 61 işlemlik kısmi okumadan çıkarmıştım; tam defter
çürüttü.

---

## 3. MERKEZDEKİ DENKLEM

```
maliyet (R cinsinden) = (giriş ücreti + çıkış ücreti + kayma + funding) / stop mesafesi
```

R birimimiz stop mesafesi olduğu için, **stop daraldıkça maliyet
büyür.** Dar stop = büyük pozisyon = büyük komisyon.

### Kaldıraç 1: STOP MESAFESİ
Maliyet modeli v0 (kilitli) ile, 0.05R bütçesine girmek için:

| Kayıp oranı | Tutuş | Gereken stop |
|---|---|---|
| %50 | 6 saat | ≥ %2.85 |
| %50 | 24 saat | ≥ **%3.30** |
| %50 | 48 saat | ≥ %3.90 |

v1 medyanının **2–3 katı**. Bu bir tercih değil, aritmetik.

### Kaldıraç 2: EMİR TİPİ (bunu hiç konuşmadık)
Model v0 giriş ve çıkışın ikisini de **taker** (piyasa emri) sayıyor.
Ama `breakout_retest` girişi doğası gereği bir **limit** emridir —
fiyatın geri gelmesini bekliyoruz. Limit emir "maker" ücretine tabidir
ve Bybit'te maker, taker'ın yaklaşık **üçte biri** kadardır.

Maliyet/işlem (24s tutuş, %50 kayıp oranı; ★ = bütçe içinde):

| stop | taker+taker (MODEL v0) | maker giriş + taker çıkış | maker+maker |
|---|---|---|---|
| %1.4 | 0.118 | 0.093 | 0.068 |
| %2.0 | 0.083 | 0.065 | **0.048 ★** |
| %2.5 | 0.066 | 0.052 | **0.038 ★** |
| %3.0 | 0.055 | **0.043 ★** | **0.032 ★** |
| %3.5 | **0.047 ★** | **0.037 ★** | **0.027 ★** |

Bütçeye giren en dar stop:
- taker+taker (bugünkü model): **%3.30**
- maker giriş + taker çıkış: **%2.60**
- maker + maker: **%1.90**

**⚠️ BEDAVA DEĞİL.** Maliyet modeli v0 kilitlidir ve kendi içinde şunu
yazar: *"limit varsayımı kanıtlanana kadar taker."* Yani maker'a geçmek
modeli GEVŞETMEKTİR ve yasaktır — **kanıtlanana kadar.** Kanıt şu
demek: limit emirlerimizin gerçekten dolduğunu ölçmek. Dolmayan emir =
kaçırılan işlem; sadece dolanları saymak defteri kayırır (seçim yanlılığı).
İyi haber: bunu ölçen altyapı **zaten var** — motor NOT_FILLED
kayıtlarını ve dolum anatomisini (nf_anatomy) tutuyor.

### Kaldıraç 3: TUTUŞ SÜRESİ
Funding maliyeti tutuş süresiyle artar, ama küçük bir kalemdir
(48 saatte bile payın ~%15'i). Tek başına kurtarıcı değil.

---

## 4. HENÜZ BİLMEDİĞİMİZ İKİ ŞEY

### (A) ★ KARARIN KİLİDİ: herhangi bir motorun BRÜT kenarı var mı?
Bugüne kadar hep **net**e baktık. Ama net = brüt − maliyet, ve maliyeti
artık düzeltebileceğimizi biliyoruz. Asıl soru şu:

> Dokuz motorumuzdan herhangi biri, **maliyet düşülmeden önce** artıda mı?

- **Evet ise:** v2'nin girişi hazır. O motoru alır, maliyet uyumlu bir
  iskelete oturturuz. Somut, hızlı yol.
- **Hayır ise:** bu evrende ve bu zaman diliminde giriş kalıbı avının
  boşuna olduğu doğrulanır; v2 **zemini** değiştirmeli (zaman dilimi /
  evren), kalıbı değil.

Bu sayı `/challengers` çıktısında hazır bekliyor (`gross_r` sütunu).
Aşağıdaki komut getiriyor. **Karar bu sayıya bağlı.**

### (B) Stop tabanı konursa motor ne kadar yavaşlar?
Yeni yazdığım tarama (`/anatomy` → `cost.stop_floor_scan`) her taban
için kaç işlemin hayatta kalacağını söylüyor.

Bir ipucu şimdiden var: ölçülen ortalama maliyet 0.185R, medyan stop
%1.4 ile beklenenden (0.118R) yüksek. Bu, **çok dar stoplu bir azınlığın**
ortalamayı belirlediği anlamına geliyor (maliyet-ağırlıklı tipik stop
~%0.89). Yani taban kuralı, işlemlerin büyük kısmını eleyebilir.

⚠️ Tarama **getiri raporlamaz** ve raporlamamalı: v1'in geçmişini stop
genişliğine göre süzmek, geniş stoplu bir motoru koşturmakla aynı şey
değildir — öyle bir motor bambaşka girişler seçerdi. Tarama yalnız
**sıklık** ve **maliyet** söyler.

---

## 5. KARAR MASASI — dört eksen

| Eksen | Seçenekler | Bildiğimiz |
|---|---|---|
| **1. Stop tabanı** | %2.5 / %3.0 / %3.5 | Aritmetik: taker modeliyle ≥%3.3 şart. Düşük taban ancak maker kanıtıyla mümkün. |
| **2. Emir tipi** | Taker kalsın / maker'ı kanıtlamaya çalış | Maker, tabanı %3.3'ten %1.9'a indirir — en büyük kaldıraç. Ama önce dolum oranı kanıtı gerek. |
| **3. Zemin** | 15dk + 150 parite (bugünkü) / 4 saat / daha az parite | Geniş stop zaten daha yavaş bir motor demek. 4 saate geçmek stopu doğal olarak genişletir. |
| **4. Giriş mantığı** | Mevcut bir motoru al / sıfırdan tasarla | **(A) sorusunun cevabına bağlı.** |
| **5. Çıkış** | Sabit hedef / iz süren | Çıkış lab: iz süren çıkış bu ailede geri tepiyor, ama fark-CI'ler sıfırı içeriyor → kanıt yok, yeni ön-kayıt ister. |

---

## 6. BENİM ÖNERİM

**Önce (A) sorusunu cevapla, sonra tasarla.** Sebep: eksen 4'ün cevabı
diğer üçünü de belirliyor. Brüt kenarı olan bir motor varsa v2 o
motorun maliyet uyumlu hali olur — aylar kazanırız. Yoksa zemini
değiştirmemiz gerekir ve bu bambaşka bir tasarımdır.

Bunun ardından önerdiğim paket (A'nın cevabına göre ayarlanacak):
1. **Stop tabanı %3.5, sert alt sınır** — altında sinyal üretilmez.
   Ortalama hedefi DEĞİL, sert taban; çünkü ortalamayı dar azınlık
   bozuyor.
2. **Taker modeliyle başla.** Maker'ı ayrı bir ölçüm işi olarak aç
   (dolum oranı kanıtı); kanıtlanırsa taban gevşetilebilir — ama
   v2 maker'a BAĞIMLI tasarlanmaz.
3. **Durma kuralını da ön-kayıtla.** v2'nin kaç penceresi olduğu
   baştan yazılsın. Bu projenin gücü hükmü önceden yazmasından geliyor;
   kendimize de aynı kuralı uygulamalıyız.

---

## 7. DÜRÜST SINIRLAR (kararı verirken bilmen gerekenler)

1. **Geniş stop kazandırmaz.** Maliyet handikabını kaldırır, o kadar.
   Başabaş için gereken brüt kenar 0.185R'den 0.05R'ye iner — hâlâ bir
   kenar gerekiyor, ama artık **mümkün** bir kenar. v1'de mümkün bile
   değildi.
2. **Daha yavaş motor = daha uzun sınav.** Taban ne kadar yüksekse
   50 kümeye o kadar geç varırız. Kaba tahmin: işlemlerin ~%15'i
   kalırsa 50 küme ~2 ay. Kesin sayı taramadan gelecek.
3. **Geçmişi süzmek backtest değildir.** Stop tabanı taraması sıklık
   söyler, kâr söylemez.
4. **S12 hâlâ sınava girmedi.** Sınava girmemiş tek adayımız; v2
   kararından bağımsız olarak koşmaya devam ediyor.
5. **Maliyet modeli v0 gevşetilemez.** Maker cazip ama kanıtsız
   kullanılamaz — P4'ün dersi tam olarak buydu: çarpıcı ve yanlış.

---

## 8. EKSİK VERİYİ GETİREN KOMUT

VM'de (bağlantı: PowerShell'e
`ssh -i C:\Users\serha\Downloads\ssh-key-2026-07-31.key ubuntu@132.145.247.85`;
satır başı `ubuntu@bybit-bot:~$` olunca VM'desin):

```
TOK=$(sudo sed -n 's/^[[:space:]]*\(export[[:space:]]*\)\?DASHBOARD_TOKEN=//p' /etc/bybit-bot.env | head -1 | tr -d '\042\047 '); curl -s "localhost:8080/challengers?k=$TOK" > /tmp/ch.json; curl -s "localhost:8080/anatomy?k=$TOK" > /tmp/an.json; curl -s "localhost:8080/backup/info?k=$TOK" > /tmp/bk.json; python3 - <<'PY'
import json
d=json.load(open('/tmp/ch.json')); s=d.get('strategies',{})
print("=== ADAYLAR: BRUT (maliyetsiz) vs NET ===")
print("STRATEJI          KUME  ISLEM      BRUT       NET  MAL/IS            KUME-CI  DURUM")
tg=tn=0.0
for k,v in sorted(s.items(), key=lambda x:-(x[1].get('clusters') or 0)):
    n=v.get('clusters') or 0; g=v.get('gross_r') or 0.0; net=v.get('net_r') or 0.0
    tg+=g; tn+=net; ci=v.get('ci'); cpt=v.get('cost_per_trade')
    cis="[%+.3f,%+.3f]"%(ci[0],ci[1]) if ci and ci[0] is not None else "-"
    f=[]
    if v.get('retired_utc'): f.append('EMEKLI')
    if n>=50: f.append('SINAV-DOLDU')
    if ci and ci[1] is not None and ci[1]<0 and n>=20: f.append('KENAR-OLU')
    if g>0 and net<0: f.append('BRUT-ARTI/NET-EKSI')
    print("%-16s %5d %6d %+9.2f %+9.2f %7s %18s  %s"%(k,n,v.get('decided') or 0,
          g,net,("%.3f"%cpt) if cpt is not None else "-",cis," ".join(f)))
print("%-16s %5s %6s %+9.2f %+9.2f"%("TOPLAM","","",tg,tn))
a=json.load(open('/tmp/an.json'))
print("\n=== STOP TABANI TARAMASI (siklik+maliyet; GETIRI DEGIL) ===")
print("taban   kalan islem   oran   maliyet/islem  butce-icinde")
for r in (a.get('cost') or {}).get('stop_floor_scan') or []:
    print("%%%-5.2f %11d %7s %14s  %s"%(r['stop_floor']*100, r['trades_kept'],
          r['share_kept'], r['cost_per_trade'], r['within_budget']))
print("\nYEDEK son senk:", json.load(open('/tmp/bk.json')).get('last_sync_utc'))
PY
```

Ne yapıyor: her adayın maliyetsiz (brüt) ve maliyetli (net) sonucunu
yan yana koyuyor, stop tabanı taramasını basıyor, yedeğin çalışıp
çalışmadığını gösteriyor. Hiçbir şeyi değiştirmiyor — salt okuma.
