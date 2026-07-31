# Oracle Always Free Taşınma Runbook'u

## A. Hesap (bir kez, ~15 dk)
1. signup.oraclecloud.com → kayıt. Home Region: **Germany Central (Frankfurt)**
   öner (Render'la aynı bölge; kapasite yoksa B planı: Amsterdam/Paris/Zurich).
2. Kart doğrulaması geçici ~1$ blokaj koyar, ücret kesilmez.
3. (Opsiyonel, önerilen) Billing → Upgrade to **Pay As You Go**: Always Free
   yine 0$, ama VM geri-alım muafiyeti + ARM kapasitesi rahatlar.
4. Sigorta: Billing → Budgets → aylık 1$, eşik %1 e-posta alarmı.

## B. VM oluşturma (~10 dk)
Compute → Instances → **Create Instance**:
- Image: **Ubuntu 24.04** (aarch64)
- Shape: **VM.Standard.A1.Flex** → 2 OCPU / 12 GB yeter ("Always Free eligible"
  etiketini gör). "Out of capacity" hatası: OCPU'yu 1'e düşür VEYA farklı
  Availability Domain dene VEYA PAYG'a yükselt VEYA bölge değiştir.
  Hiçbiri olmazsa: VM.Standard.E2.1.Micro (x86, her zaman bulunur, bota yeter).
- SSH key: "Generate" de, private key'i indir (bir daha verilmez!).
- Networking: varsayılan VCN; **Public IP: Assign**.
Oluşunca: Instance sayfası → Public IP'yi not et.
Subnet → Security List → **Add Ingress Rule**: Source 0.0.0.0/0, TCP, Port **8080**.

## C. Kurulum (~15 dk)
```
ssh -i indirdigin_key ubuntu@PUBLIC_IP
git clone https://github.com/serhatozdogan86/bybit-signal-bot  # HATA VERIR (private) -- normal:
# once kurulum dosyalarini tek basina indir:
curl -sO https://raw.githubusercontent.com/serhatozdogan86/bybit-signal-bot/main/deploy/oracle/setup.sh  # bu da private -> alternatif:
```
Private repo olduğu için ilk dosyayı elle taşı: bilgisayarında repo'dan
`deploy/oracle/setup.sh`'ı aç, kopyala; VM'de `nano setup.sh` → yapıştır →
kaydet. Sonra:
```
sudo bash setup.sh
```
Betik sırasıyla: paketleri kurar → **deploy public key basar** (GitHub →
repo → Settings → Deploy keys → Add: yapıştır, read-only) → enter'a bas →
repo klonlanır → `nano /etc/bybit-bot.env` ile **GITHUB_TOKEN** doldur
(Render paneli → Environment → GITHUB_TOKEN değerini kopyala) →
servisler başlar.

## D. Doğrulama
```
systemctl status bybit-bot         # active (running)
curl -s localhost:8080/healthz     # {"status":"ok",...}
journalctl -u bybit-bot -f         # canli log: restore + ilk tarama
```
Tarayıcıdan: http://PUBLIC_IP:8080 → pano açılmalı; gist restore sayaçları
Render'daki son değerlerle birebir olmalı (86 sonuçlanan vb.).

## E. Geçiş anı (çakışma olmasın)
1. Render Dashboard → servis → **Suspend** (zaten askıda ise dokunma).
   İki kopya AYNI ANDA çalışmamalı (gist'e çift yazar, sinyalleri çiftler).
2. UptimeRobot → monitörün URL'sini http://PUBLIC_IP:8080/health yap.
3. 1 saat sonra gist updated_at ilerliyor mu bak → taşınma tamam.

## F. İşletme notları
- Deploy akışı: Claude main'e push eder → VM 2 dk içinde çekip yeniden başlar.
- Ubuntu güvenlik yamaları otomatik (unattended-upgrades).
- DB artık kalıcı: /opt/bybit-signal-bot/data/bot.db (gist = felaket sigortası).
- VM yeniden başlarsa her şey otomatik ayağa kalkar (systemd enable).
