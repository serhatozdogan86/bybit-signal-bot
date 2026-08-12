# CLAUDE.md — Bu depoda çalışan her Claude oturumu önce bunu okur

## Proje
Bybit perpetual gölge sinyal botu. GERÇEK PARA YOK — tüm işlemler kâğıt
üzerinde ölçüm. Amaç: istatistiksel kanıt eşiğini (≥50 kapanmış küme +
küme-CI alt sınırı > 0) geçen bir motor bulmak. Dil: Türkçe, sade.

## İLETİŞİM (2026-08-06, Serhat'ın isteği)
Serhat yazılımcı DEĞİL. Ona yazarken:
- Sade Türkçe, jargonsuz. Teknik terim kaçınılmazsa tek cümleyle tanımla
  (örn. "VM = internette kiralık, hep açık bilgisayar").
- Yapılacak adımları kopyala-yapıştır komut olarak ver; her komutun ne işe
  yaradığını bir cümleyle söyle. Mümkünse adımları TEK komutta birleştir.
- Rapor/özetlerde önce sonuç, sonra kısa gerekçe; uzun teknik döküm yalnız
  istenirse.

## DURUM (2026-08-05)
- Şampiyon (breakout_retest) kilit-1'i GEÇEMEDİ (yanlışlama #2 + CI);
  hüküm arşivlendi. KİLİT-2 (2026-08-12): retest düzeltmeli motor,
  sayaçlar 2026-08-13'ten SIFIRDAN — config-lock.md sonu.
- S3/S6 kenar ölümüyle EMEKLİ (2026-08-12); S1 tavanı 40→70 (bütçe
  devri, toplam sabit). Ölü maksDD alarmı düzeltildi (Kural 10).
- 6 aday gölge yarışta (app/services/challengers.py), rejim-2 örneklemesi.
  S7 (Wyckoff) 2026-08-06'da yarışa girdi (tetik: S6 sınavını doldurdu).
  S5 beklemede — tetikleyicisi docs/challengers-design.md.
- v2 şampiyon henüz TASARLANMADI; tasarlanırsa ÖN-KAYITLA yeni aday olur.
- S1 seçim penceresi doldu (50 küme, CI alt −0.05): KIL PAYI GEÇEMEDİ.
  2026-08-12: ön-kayıtlı DOĞRULAMA penceresi açıldı (yeni 50 küme,
  aynı kurallar) — challengers-design.md sonu.

## DEĞİŞTİRİLEMEZ KURALLAR
1. `app/strategies/` DONMUŞTUR (KİLİT-2, 2026-08-12: retest düzeltmesi
   kilit ilanının parçası olarak yapıldı; o commit'ten itibaren donma
   YENİDEN başlar). Davranışı etkileyen tek satır bile yasak.
   KAYITLI İSTİSNA (2026-08-05, f61333e): karar davranışını DEĞİŞTİRMEYEN
   salt-metadata enstrümantasyonu, (a) davranış-kimliği kanıtı (aynı girdi
   → market_bias hariç bayt-bayt aynı karar, üç senaryoda doğrulandı) ve
   (b) inceleme kaydı ile kabul edilebilir. Örnek: `d.market_bias = ...`.
   Eşik/filtre/hesap değişikliği bu istisnaya GİRMEZ.
2. PUSH KAPISI: `python -m pytest tests/ -q` yeşil değilse push YOK.
   Komut zincirine kapı koy (`&&` veya rc kontrolü) — 853927e'nin dersi.
3. Yeni hata bulunca: önce SINIFINI kapatan değişmezlik testi
   (tests/test_invariants.py), test hatalı kodda KIRMIZI vermeli, sonra
   düzeltme. docs/error-prevention.md'deki 9 kural bağlayıcıdır.
3b. İKİZ DEPO: bu bot ile midas-signal-bot aynı iskeletten doğdu. Kanıtlı
   mekanizma hatası, ölçüm/muhasebe düzeltmesi veya yeni ölçüm aleti
   çıktığında **ikizde karşılığı açıkça kontrol edilir** ve sonuç
   docs/ikiz-depo-notu.md'ye yazılır (bulunmasa bile). Kontrol "okudum,
   yok" ile kapanmaz; ikizde aynı davranışı tetikleyen test yazılır.
   Gerekçe: retest kusuru midas'ta 08-08'de düzeltilmişti, burada
   08-12'ye kadar canlı kaldı — bakılacak bir yer olmadığı için.
4. Ölçüm eşikleri / maliyet sabitleri / karar kuralları veriden türetilip
   doğrudan kural yapılamaz — önce docs/ideas.md'ye ÖN-KAYIT (H-1 örneği),
   GELECEK veride test.
5. Veride otomatik kalıp arama YOK (p-hacking). Alarm koşulları önceden
   ilan edilir: app/services/alarms.py (testi bunu zorlar).
6. app/services/verifier.py tracker'dan BAĞIMSIZ kalır — import etmez.
7. Aday motoru şampiyon tablolarına yazamaz; bayt-bayt izolasyon testlidir.

## OPERASYON
- Canlı: Oracle VM 132.145.247.85:8080; main'e push → ~2 dk'da autodeploy.
  VM'deki autodeploy çalışma ağacında ELLE ÇALIŞMA — ayrı clone kullan.
- Canlı SQLite'a yazan sorgu YASAK; denetim için önce dosyayı kopyala.
- Uzaktan durum: gist 7841e94325309e69812439897a0c186c
  (codeload.github.com/gist/<id>/tar.gz/HEAD; 0_performance.json,
  0_signals.json, 0_challengers.json, candles_*.csv).
- Rotalar: /verify /alarms /measurement /challengers (DASHBOARD_TOKEN'lı).
- Bybit API bazı ortamlardan coğrafi engelli; VM'den erişilir.

## ŞERİTLER (iki Claude çakışmasın)
- **Denetim şeridi** (Claude Code dahil herkes): oku, doğrula, yeniden
  oynat, rapor et. Serbest.
- **Değişiklik şeridi**: TEK yazar. Değişiklik yapacaksan önce açık PR /
  bekleyen iş var mı bak (git log + son commit mesajları), kurallar
  yukarıda. Uyuşmazlık bulursan kod değiştirmeden önce rapor et.
