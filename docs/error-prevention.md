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
