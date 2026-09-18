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
- (2026-08-13) VM'de çalıştırılacak her komut tarifinde ÖNCE bağlantı
  adımını hatırlat: PowerShell'e
  `ssh -i C:\Users\serha\Downloads\ssh-key-2026-07-31.key ubuntu@132.145.247.85`
  yapıştırılır; satır başı `ubuntu@bybit-bot:~$` olunca VM'desin, komutlar
  oraya. (`PS C:\...` görünüyorsa hâlâ kendi bilgisayarındasın.)

## DURUM (2026-08-05)
- Şampiyon (breakout_retest) kilit-1'i GEÇEMEDİ (yanlışlama #2 + CI);
  hüküm arşivlendi. KİLİT-2 (2026-08-12): retest düzeltmeli motor,
  sayaçlar 2026-08-13'ten SIFIRDAN — config-lock.md sonu.
- S3/S6 kenar ölümüyle EMEKLİ (2026-08-12); S1 tavanı 40→70 (bütçe
  devri, toplam sabit). Ölü maksDD alarmı düzeltildi (Kural 10).
- Canlı adaylar (2026-08-18): S1, S2, S8 (funding sıkışma), S9_GECE
  (takvim), S10 (52w zirve, haftalık), S11 (sıkışma-kırılımı), S12
  (hacim-kapılı seans kırılımı) — rejim-2 örneklemesi. EMEKLİ: S3/S6
  (08-12) + S4/S7 (08-18, CHALLENGER_DEAD; slot devri YOK — config-lock
  08-18 tutanağı). KİLİT-2 HÜKMÜ (2026-08-20): GEÇEMEDİ — yanlışlama #2
  (kilit penceresi maksDD 20.15R > 20R; tutanak config-lock.md). Üçüncü
  kilit YOK; şampiyon VERİ KAYNAĞI statüsünde koşar.
  ŞAMPİYON v1 DOSYASI KAPANDI (2026-09-18 mühür, config-lock.md):
  yanlışlama #1 KENAR ÖLÜMÜ tetiklendi — kilit kohortunda 197 küme,
  küme-CI ÜST sınırı −0.028 < 0; maksDD 100.6R (tavan 20R'nin 5 katı).
  Hüküm ön-kayıtlı alarm kanalından okundu. Motor durmaz, umut statüsü
  SIFIR; hiçbir v2 bileşeni canlı sonuçlarına dayandırılamaz.
  v2 tasarımı artık TEK gündem: docs/v2-tasarim.md (çıkış-lab girdi).
  S2: seçim sınavını 08-21'de GEÇTİ (projede ilk) ama DOĞRULAMA
  penceresinde GEÇEMEDİ (08-30 mühür: 54 küme, net −77.3R, CI
  [−0.63,−0.30] — üst sınır bile eksi; ralli eseriydi). Üçüncü pencere
  YOK; emekli değil. P4 (OI-onay filtresi) ELENDİ (08-29: artışlı E_net
  −0.078 ≤ artışsız +0.078, backtest'in TERSİ) — v2'nin OI kapısı düştü,
  hacim ayağı (S12) yaşıyor. ≥50 kümeye ulaşan HER motor sınavı geçemedi
  (09-05: S11 de 50 kümede geçemedi); sınava girmemiş TEK aday S12.
  ÇIKIŞ LAB ARA OKUMASI (09-05, hüküm DEĞİL): 1×R iz süren çıkış
  trend/kırılım ailesinde geri tepiyor (S2 +30.6 → −30.1); tüm fark-CI'ler
  sıfırı içeriyor. Tek iz mesafesi ölçüldü — başkası YENİ ön-kayıt ister.
  Perakende araştırması: docs/perakende-arastirmasi-2026-08-17.md.
  S5+TSM momentum ailesi RAFTA (90g backtest kenar yok; raftan çıkma
  tetiği docs/ideas.md). S-ATT1 (Wikipedia dikkat) backtestte ELENDİ
  (2026-08-17: net −22R, küme-CI üst < 0 — ideas.md). Aile araştırması: docs/aile-arastirmasi-2026-08-13.md.
  Korelasyon aleti (Faz A): /correlation, app/services/correlation.py.
  Çıkış laboratuvarı (V0 sabit / V1 iz süren; salt ölçüm): /exitlab,
  app/services/exit_lab.py — hüküm kuralı ön-kayıtlı (ideas.md 08-17).
  MALİYET DAYANIKLILIĞI (08-27, ölçüldü + ön-kayıt): ölen motorların
  çoğu HAM olarak artıdaydı; net'i maliyet öldürdü (dar stop → büyük
  pozisyon → büyük komisyon). v2 kısıtı: maliyet/işlem ≤ 0.05R, dar
  stop yasak — v2-tasarim.md "GİRDİ 0". Maliyet modeli v0 GEVŞETİLMEZ.
- v2 şampiyon henüz TASARLANMADI; tasarlanırsa ÖN-KAYITLA yeni aday olur.
- S1: seçim penceresi kıl payı geçemedi (CI alt −0.05); DOĞRULAMA
  penceresi de doldu ve GEÇEMEDİ (2026-08-20: 90 küme, net −24.4R,
  CI alt −0.25). Üçüncü pencere YOK; S1 emekli değil, ölçüm için koşar.

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
  0_signals.json, 0_challengers.json, 0_exitlab.json, candles_*.csv).
  GITHUB SERT SINIRI: gist başına 300 dosya. 2026-09-18'de tam bu sınır
  aşıldı (307 dosya → HTTP 422 → 13 gün yedeksiz). Düzeltme: mum yedeği
  yalnız EN İNCE dilim + MAX_GIST_FILES=280 bütçesi + artık
  gönderilmeyen candles_* dosyalarının budanması.
- Rotalar: /verify /alarms /measurement /challengers /correlation
  /exitlab (DASHBOARD_TOKEN'lı).
- Bybit API bazı ortamlardan coğrafi engelli; VM'den erişilir.

## ŞERİTLER (iki Claude çakışmasın)
- **Denetim şeridi** (Claude Code dahil herkes): oku, doğrula, yeniden
  oynat, rapor et. Serbest.
- **Değişiklik şeridi**: TEK yazar. Değişiklik yapacaksan önce açık PR /
  bekleyen iş var mı bak (git log + son commit mesajları), kurallar
  yukarıda. Uyuşmazlık bulursan kod değiştirmeden önce rapor et.
