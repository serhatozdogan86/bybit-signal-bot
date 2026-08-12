# Hata Önleme Çerçevesi (2026-08-02)

Bir günde dört ölçüm hatası bulundu. Dördüncüsünü kod değil **insan** yakaladı.
Bu dosya, o dördünün ortak köklerini ve her kökü kapatan yapısal kuralı yazar.
Amaç "daha dikkatli olacağım" değil; **dikkatsizliğin sonuç doğurmasını
engelleyen** testler.

## Bulunan dört hata ve gerçek kökleri

| # | Hata | Kök |
|---|------|-----|
| 1 | Etiketsiz kayıt "kendi başına küme" sayıldı (16 → 53) | Eksik veriyi uydurma bir kimlikle doldurmak |
| 2 | MFE/MAE doluş öncesi mumları saydı | Durum taşıyan değerlendiricinin "ikinci tur" hâli modellenmemiş |
| 3 | Ölçüm kolonları yedeğe girmedi, her restore'da silindi | Yazma yolu ile okuma yolunun ayrışması |
| 4 | Doluş öncesi mumlar WIN/LOSS kararını verdi | #2'nin aynısı — örnek düzeltildi, **sınıf** düzeltilmedi |

Dördü de aynı üst-hatanın türevi: **kendi zihinsel modelime göre yazdığım
sentetik testlerle, kendi zihinsel modelimin yanlış olduğunu bulamam.**

## Kalıcı kurallar (tests/test_invariants.py ile zorlanır)

1. **Eksik veri eksik kalır.** Hiçbir yerde uydurma varsayılan üretilmez;
   eksik kayıt hesaptan çıkarılır ve *sayısı raporlanır*. Sessiz hariç tutma
   da sessiz uydurma kadar kötüdür.
   → `test_no_synthetic_identity_fallbacks_in_stats`

2. **Her kolon yedekten sağ çıkar.** Tabloya eklenen her alan, yedek
   payload'ında görünmek zorunda; görünmüyorsa gerekçesi dosyaya yazılır.
   Bu test şemayı okur, unutmayı imkânsız kılar.
   → `test_every_signal_column_survives_backup_restore`

3. **Değerlendirme tekrar edilebilir olmalı.** Aynı mumlarla ikinci, üçüncü
   kez çalıştırmak sonucu değiştirmemeli. Durum taşıyan her işlev en az iki
   turlu testle sınanır — tek turluk test "devam etme" hâlini hiç görmez.
   → `test_evaluation_is_idempotent_across_rounds`

4. **Karar satırları filtreden sonra gelir.** Sonuç kontrolü doluş kapısının
   ardında durur; kod düzeni testle sabitlenir.
   → `test_outcome_decision_never_reads_pre_fill_candles`

5. **Denetçi bağımsız kalır.** `verifier.py` tracker mantığını içe aktarmaz.
   Aynı kodu tekrar kullanan denetim, kendi hatasını doğrular.
   → `test_verifier_does_not_import_tracker_logic`

6. **Örneği değil sınıfı düzelt.** Bir hata bulunduğunda önce aynı kalıp tüm
   kod tabanında aranır, sonra düzeltme yapılır. #4, bu kural olmadığı için
   #2'nin on satır aşağısında sağ kaldı.

7. **Test önce hatayı yakalamalı.** Yeni regresyon testi, düzeltme geri
   alındığında KIRMIZI verdiği gösterilmeden kabul edilmez. Bugün iki test
   ilk hâlinde hatayı yakalamıyordu; ikisi de bu kuralla düzeltildi.

8. **Rakam iddiası ham veriye dayanır.** Performans hakkında söylenen her şey
   ya bağımsız denetimden ya ham mum arşivinden gelir; "testler geçti" bir
   doğruluk kanıtı değildir.

## İnsanın rolü

Serhat'ın ekran görüntüsüyle hata bulması **güvenlik ağı değil, örnekleme
denetimi** olmalı. Ağ artık `/verify` ve 6 saatlik otomatik denetimdir.
İnsan denetimi bulduğunda soru şudur: *bu hatayı hangi otomatik kontrol
yakalamalıydı ve neden yoktu?* Cevap bu dosyaya yeni bir kural olarak yazılır.

## Kural 6'nın ilk uygulaması (2026-08-02, aynı gün)
"Örneği değil sınıfı düzelt" kuralı yazıldıktan sonra aynı bulaşma sınıfı
üçüncü bir yerde daha arandı ve bulundu: **izleme süresi sayımı.** Gecikmeli
dolan bir sinyal ikinci turda değerlendirilirken tutuş süresi doluştan değil
sinyal anından sayılıyordu; bu, izleme penceresini gecikme kadar erken
bitirip haksız EXPIRED üretiyordu. Aynı kök, üçüncü tezahür:
MFE/MAE → sonuç kararı → süre sayımı.
Ders: bir bulaşma bulunduğunda o değişkenin geçtiği TÜM satırlar taranmalı,
sadece hatanın göründüğü satır değil.

## Kural 9 (2026-08-04): görselleştirme de bir iddiadır
JTOUSDT #489 ve SLXUSDT #475 panoda "stop çizgisine gelmemiş ama LOSS"
görünüyordu. Muhasebe DOĞRUYDU (bağımsız denetçi: uyuşmazlık yok; stop
sırasıyla doluştan 27 ve 16 mum sonra gerçekleşti). Hata grafikteydi:
`mark()` fonksiyonu, pencere dışındaki çıkışı `idx=cs.length-1` ile sağ
kenara YAPIŞTIRIYOR ve fiyat o seviyeye hiç gelmemiş gibi gösteriyordu.
Sabit ±12 mumluk "yakın" pencere, saatlerce tutulan işlemin çıkışını
ekran dışında bırakıyordu.

Kural: **grafikte çizilen her işaret, veride karşılığı olan bir noktaya
denk gelmelidir.** Veri pencere dışındaysa işaret çizilmez — durum yazıyla
söylenir. Kenara kırpma (clamping) sessiz bir yalandır.
Düzeltme: pencere dışı çıkış için "→ pencere dışı N mum" etiketi; kapanmış
sinyalde pencere otomatik olarak çıkışı kapsayacak şekilde büyür (tavan 80);
"tam" zoom seçeneği eklendi. İki değişmezlik testi kod düzenini sabitler.

## Denetim döngüsü (2026-08-05): üç katman
Soru: "sürekli denetleyip hata/fikir arayabilir miyiz?" — Cevap ikiye ayrıldı.

**Denetim: evet, kod olarak.** Üç katman kuruldu:
1. **Alarm kaydı** (`app/services/alarms.py`) — her taramada, önceden ilan
   edilmiş koşullar: denetim uyuşmazlığı, kümesiz kayıt, tarama durması,
   yedek bayatlaması, kenar ölümü (CI üst sınırı<0), maksDD>20R, Faz-1
   kapısı, aday tavanı, aday elenmesi. `/alarms` ile okunur; KRİTİK olanlar
   ERROR log'a düşer.
2. **CI** (`.github/workflows/tests.yml`) — her push'ta değişmezlik testleri
   + tüm suite + JS sözdizimi + derleme. Kapının açık kalması artık kimsenin
   hatırlamasına bağlı değil.
3. **Haftalık insan incelemesi** — alarm günlüğü + örnekleme denetimi +
   yeni fikirlerin ÖN-KAYDI.

**Fikir arama: hayır — en azından otomatik hâliyle.** Veride kalıp arayan
bir döngü, ~150 sinyal ve onlarca olası bölme varken tesadüfen "anlamlı" bir
şey MUTLAKA bulur; bu p-hacking'i sanayileştirmektir. Kural: hipotez ÖNCE
yazılır (H-1 gibi), GELECEK veride test edilir, çoklu karşılaştırma sayılır.
`test_alarm_registry_has_no_search_logic` bu sınırı kodda zorlar.

**Ek kapatılan boşluk:** denetim çalışıyordu ama sonucu yedeğe girmiyordu —
"ağaç ormanda devriliyordu". Artık `stats().measurement.outcome_audit` ile
gist'e yazılıyor; uzaktan denetlenebilir. maksDD de eklendi (yanlışlama
kriteri sayısal olarak izlenebilsin diye).


## Kural 10 (2026-08-12): ilan edilmiş alarm, ateşlenebildiğini kanıtlamalı
MAX_DD alarmı ilk yazıldığı günden beri ÖLÜYDÜ: değeri `stats` üst düzeyinde
arıyordu, değer `measurement` içinde yaşıyordu. 35.6R'lik yanlışlama ihlalini
alarm değil İNSAN yakaladı — koruma mekanizması sessizce yoktu. Kusuru dış
denetim (ikinci Claude oturumu, kanıt testiyle) buldu.

Kural: **her ilan edilmiş alarm koşulu, GERÇEK üretici çıktısıyla (sahte
sözlük değil, `tracker.stats()` gibi) uçtan uca ateşlenebildiğini gösteren
bir teste sahip olmalıdır.** Var olması değil, ÖTMESİ test edilir.
→ `test_declared_alarms_can_actually_fire`
