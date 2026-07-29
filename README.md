# Bybit Signal Engine → Telegram Bot

Conservative swing, structure-first, volume-confirmed, risk-first kripto futures sinyal motoru.

## v3.0 — Veriyle kazanılmış filtreler
İlk 49 sonuçlanmış gölge sinyalin kanıtlarıyla eklendi:
- **Market gate:** BTC 4H EMA200 rejimi karşıtı sinyaller bloklanır
  (`MARKET_GATE_ENABLED`, varsayılan açık; ±%0.25 nötr bant; BTC verisi
  alınamazsa fail-open). Gerekçe: ayı rejiminde LONG 4W/16L (−6.99R) vs
  SHORT 16W/13L (+28.75R).
- **RR tavanı:** plan RR > `RISK_REWARD_MAX` (varsayılan 6.0) → NO_TRADE
  "stop too tight". Gerekçe: RR≥6 planlı 4 sinyalin 4'ü de LOSS.
- **Orphan eval:** günlük evren yenilemesinde liste dışına düşen paritelerin
  açık sinyalleri her tur sonunda ayrıca değerlendirilir (zombi-PENDING
  vakası düzeltmesi).
Bybit v5 public API'den veri çeker, sabit filtre hattından geçirir; yalnızca geçerli setup'larda
Telegram'a **SIGNAL** gönderir, aksi halde **NO_TRADE** veya **DATA_MISSING** üretir.

> ⚠️ **Uyarı:** Bu bot karar desteğidir, finansal tavsiye değildir. Emir **göndermez**
> (yalnızca public market data okur; API key gerekmez ve yüklenmez). İşlem kararı ve risk
> yönetimi size aittir. Kaldıraçlı futures yüksek risk içerir; canlı kullanım öncesi
> sinyalleri 1–2 hafta gölge modda doğrulamanız önerilir.

## Mimari

```
[Scheduler loop] ──> [MarketDataService] ──> [BybitClient (REST)]
        │                                     (Phase 2: WSClient aynı arayüzü implemente eder)
        ▼
[SignalEngine]  regime → structure → execution → volume → confluence → risk → decision
        │  Decision (pydantic, schema v1.1)
        ▼
[StateStore (abstract)]  cooldown / dedup / son sonuçlar   ← MVP: InMemory, sonra Redis/SQLite
        │
        ├─> [TelegramFormatter] ─> [TelegramNotifier]  (plain text, retry'lı)
        └─> [Flask]  /healthz /status /scan /scan/dry
```

Engine katmanı **saf fonksiyondur**: I/O yapmaz, global state kullanmaz, zaman enjekte
edilebilir — bu sayede sentetik veriyle deterministik test edilir (`tests/`).

## Karar hattı (hard filters — ilk fail'de kısa devre)

| # | Filtre | Fail sonucu |
|---|---|---|
| 1 | DATA — kline eksik/yetersiz (<60 bar) | `DATA_MISSING` (tahmin üretilmez) |
| 2 | REGIME — ADX < `ADX_CHOP` → chop | `NO_TRADE` |
| 3 | STRUCTURE — HH/HL veya LH/LL yok | `NO_TRADE` |
| 4 | EXECUTION — teyitli breakout+retest / sweep+reclaim yok | `NO_TRADE` |
| 5 | VOLUME — tetik mumu hacmi < `VOLUME_MULT`×SMA20 | `NO_TRADE` |
| 6 | (confluence — filtre değil, yalnızca confidence girdisi) | — |
| 7 | RISK_REWARD — RR < `RISK_REWARD_MIN` veya hedef yok | `NO_TRADE` |
| 8 | Hepsi geçti | `SIGNAL` |

## Repo yapısı

```
app/
├── main.py                    # entrypoint + dependency wiring (composition root)
├── server.py                  # Flask: /healthz /status /scan /scan/dry
├── scheduler.py               # polling döngüsü, hata izolasyonu, cooldown, dispatch
├── logging_setup.py           # structured logging (key=value)
├── config/settings.py         # env → typed Settings + StrategyParams
├── models/candle.py           # Candle, KlineSeries
├── models/decision.py         # Decision output contract (schema v1.1)
├── integrations/bybit_client.py       # REST + retry/backoff
├── integrations/telegram_notifier.py  # sendMessage + timeout/retry/429
├── services/market_data_service.py    # veri kaynağı soyutlaması (WS'e hazır)
├── services/state_store.py            # abstract StateStore + InMemory impl
├── strategies/                # saf analiz modülleri
│   ├── indicators.py  regime_detector.py  structure_analyzer.py
│   ├── volume_analyzer.py  indicator_confluence.py  risk_manager.py
│   └── signal_engine.py       # pipeline orkestrasyonu
└── formatting/telegram_formatter.py   # plain text (rich mod Phase 2)
tests/                         # pytest: her hard filtre + LONG/SHORT + contract
```

## Kurulum

### 1) Telegram botu
1. **@BotFather** → `/newbot` → **token**'ı kaydet.
2. Botunla sohbet başlat, bir mesaj gönder.
3. `https://api.telegram.org/bot<TOKEN>/getUpdates` → `"chat":{"id": ...}` → **chat id**.
   (Grup için botu gruba ekle; id `-100...` ile başlar.)

### 2) Lokal çalıştırma
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # token ve chat_id'yi doldur
python -m app.main
# testler:
pip install -r requirements-dev.txt && pytest
```

### 3) GitHub
```bash
git init && git add . && git commit -m "bybit signal bot v1"
git branch -M main
git remote add origin https://github.com/<kullanici>/<repo>.git
git push -u origin main
```

### 4) Render deploy
1. render.com → **New +** → **Web Service** → repoyu seç
   (repoda `render.yaml` var; **Blueprint** ile de kurulabilir).
2. Build: `pip install -r requirements.txt` — Start: `python -m app.main`
3. **Environment** sekmesinde en az `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` gir.
4. Deploy sonrası bot "Signal engine online" mesajı atar.
5. Doğrulama: `https://<app>.onrender.com/scan/dry` → tam contract JSON.

**Free plan notu:** Render free web servisleri 15 dk istek gelmezse uyur → döngü durur.
Çözüm: UptimeRobot ile `/healthz`'e 5 dk'da bir ping, veya Starter plana geçiş.

**In-memory state notu (önemli):** MVP `StateStore` bellek içidir. Her **restart, redeploy
veya free-plan uyku/uyanma** döngüsünde cooldown ve son sonuçlar **sıfırlanır** — yani aynı
sinyal, cooldown süresi dolmamış olsa bile restart sonrası tekrar gönderilebilir. Bu MVP'de
bilinçli bir ödünleşimdir; kalıcılık için `StateStore` arayüzünü implemente eden bir
Redis/SQLite sınıfı yazıp `app/main.py`'de tek satır değiştirmek yeterlidir.

## Deploy sonrası doğrulama checklist'i

1. Render dashboard → servis **Live** ve loglarda `event=scheduler_start` görünüyor.
2. Telegram'a **"Signal engine online"** açılış mesajı düştü (token + chat_id doğru demektir).
3. `GET /healthz` → `{"status": "ok", ...}` dönüyor.
4. `GET /scan/dry` → tüm semboller için tam contract JSON dönüyor; `decision` alanları
   `SIGNAL / NO_TRADE / DATA_MISSING`'den biri ve `schema_version` = `1.1`.
5. `/scan/dry` çıktısında hiçbir sembol `DATA_MISSING` değil (Bybit bağlantısı sağlıklı).
6. `GET /status` → `meta.scan_count` birkaç dakika arayla artıyor (döngü canlı).
7. `GET /scan` bir kez çağrıldığında sonuç Telegram'a düşüyor (SEND_NO_TRADE=false ise
   yalnızca SIGNAL durumunda mesaj gelir — NO_TRADE dönerse mesaj gelmemesi normaldir).
8. UptimeRobot monitörü **Up** ve 15+ dk sonra servis hâlâ tarama yapıyor.
9. Loglarda `event=telegram_failed` veya `event=bybit_failed` tekrarı yok.

## Telegram notifier davranış özeti

| Durum | Davranış |
|---|---|
| Başarılı (`ok: true`) | `True` döner |
| Timeout / bağlantı hatası | 1s → 2s backoff ile toplam 3 deneme; hepsi biterse ERROR log + `False` |
| HTTP 5xx | Timeout ile aynı retry politikası |
| HTTP 429 | Yanıttaki `retry_after` kadar bekler (üst sınır 30s), **deneme hakkı yakmadan** tekrar dener (en çok 2 bekleme) |
| HTTP 4xx (yanlış chat_id vb.) | Kalıcı hata: **retry edilmez**, ERROR log + `False` |
| Token/chat_id boş | WARNING log + `False` (servis çalışmaya devam eder, `/scan/dry` kullanılabilir) |
| Her durumda | Bildirim hatası servisi **asla düşürmez** |

## Environment variables

| Değişken | Default | Açıklama |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | **Zorunlu.** BotFather token |
| `TELEGRAM_CHAT_ID` | — | **Zorunlu.** Hedef chat/grup |
| `BYBIT_BASE_URL` | `https://api.bybit.com` | Testnet: `https://api-testnet.bybit.com` |
| `BYBIT_API_KEY` / `SECRET` | boş | MVP'de kullanılmaz (rezerve) |
| `SYMBOLS` | `BTCUSDT,ETHUSDT,SOLUSDT` | Virgülle ayrık linear perp |
| `HTF` / `LTF` | `240` / `15` | Bybit interval formatı |
| `SCAN_INTERVAL` | `900` | Tarama periyodu (sn) |
| `RISK_REWARD_MIN` | `2.0` | Min RR |
| `ADX_CHOP` | `20` | Regime eşiği |
| `VOLUME_MULT` | `1.5` | Hacim teyit çarpanı |
| `PIVOT_LOOKBACK` | `3` | Fractal pivot penceresi |
| `ATR_STOP_MULT` | `1.2` | Stop mesafe çarpanı |
| `SEND_NO_TRADE` | `false` | NO_TRADE mesajları da gönderilsin mi |
| `SEND_DATA_MISSING` | `false` | DATA_MISSING mesajları gönderilsin mi |
| `SIGNAL_COOLDOWN_SEC` | `14400` | Aynı sembol+yön tekrar bekleme |
| `LOG_LEVEL` | `INFO` | |

## Endpoint'ler

| URL | İşlev |
|---|---|
| `GET /healthz` | Health check (Render + UptimeRobot hedefi) |
| `GET /status` | Son sonuçlar + meta (sabit contract JSON) |
| `GET /scan` | Manuel tarama, Telegram'a gönderir, özet döner |
| `GET /scan/dry` | Manuel tarama, Telegram'a **göndermez**, tam JSON döner |

## Output contract (schema v1.1)

`decision`: `SIGNAL | NO_TRADE | DATA_MISSING`. Alan isimleri sabittir; tam şema
`app/models/decision.py` içindedir ve `tests/test_signal_engine.py::test_contract_dict_field_names_are_stable`
ile korunur.

## Roadmap

- ~~**Phase 2:** WebSocket kline adapter, orderbook likidite haritası, MarkdownV2 rich
  formatter, SQLite kalıcı state, gölge takip~~ ✅ **Tamamlandı (v2)** — aşağıya bakın.
- **Phase 3:** Sinyal performans dashboard'u, funding/OI verisi, harici DB (Postgres/Redis),
  gerçek backtest motoru (arşivlenen veriyle).

## Phase 2 — Gölge Takip & Yeni Modüller (v2)

### Gölge takip (SHADOW_TRACKING=true, varsayılan açık)

Bot **sessizce** (Telegram'a ek mesaj atmadan) şunları yapar:

1. **Karar arşivi:** Her tarama kararı (SIGNAL/NO_TRADE/DATA_MISSING, sebepleriyle)
   `decisions` tablosuna yazılır — backtest'te "hangi koşulda ne karar verildi" etiketi.
2. **OHLCV arşivi:** Her taramada kapanmış mumlar `candles` tablosunda birikir
   (tekrarsız) — backtest için ham veri seti.
3. **Sinyal sonuçlandırma:** Her SIGNAL izlenir ve sonraki mumlarla otomatik kapanır:

| Sonuç | Koşul | R katkısı |
|---|---|---|
| `WIN` | TP1'e değdi (stop'tan önce) | +reward/risk |
| `LOSS` | Stop'a değdi | −1.0 |
| `NOT_FILLED` | Fiyat fill penceresi içinde entry bölgesine hiç girmedi | 0 (orana dahil değil) |
| `EXPIRED` | Max izleme süresi doldu | kapanışa göre ± |
| `AMBIGUOUS` | Aynı mumda hem stop hem TP kesildi (sıra bilinemez) | 0 (orana dahil değil) |

Varsayımlar dürüstçe muhafazakârdır: fill = entry bölgesinin ilk değen kenarı,
slippage yok. Bu **tahmini gölge muhasebesidir**, gerçek işlem sonucu değildir.

### Yeni endpoint'ler

| URL | İşlev |
|---|---|
| `GET /performance` | Başarı oranı, decided trade sayısı, toplam R, parite kırılımı, veri seti boyutu |
| `GET /signals?limit=50` | İzlenen sinyallerin listesi (durum/sonuç/R ile) |
| `GET /export/candles.csv?symbol=BTCUSDT&interval=15` | Arşivlenen OHLCV — backtest yedeği |
| `GET /export/decisions.json` | Sinyal kayıtları yedeği |
| `GET /backup/info` | Gist yedekleme durumu (gist_url, son sync) |
| `GET /backup/now` | Manuel gist sync tetikle |

### ⚠️ Kalıcılık — Render free plan kısıtı ve çözümü: Gist yedekleme

SQLite dosyası free planda **ephemeral disktedir** (redeploy'da silinir). Bot bunu
**kendi kendine çözer** — `GITHUB_TOKEN` verildiğinde:

1. **Otomatik sync:** Saatte bir `performance.json`, `signals.json`, `decisions.json`
   ve `candles_*.csv` dosyaları secret bir GitHub Gist'e yazılır. Gist her yazımda
   revizyon tutar → istatistik geçmişi otomatik arşivlenir.
2. **Self-restore:** Her açılışta DB boşsa (redeploy olmuş demektir) bot gist'i
   bulur ve mum arşivi + sinyal kayıtlarını geri yükler — takip kaldığı yerden
   devam eder. **İnsan müdahalesi gerekmez.**

Kurulum (tek seferlik, 2 dk):
1. github.com → sağ üst profil → **Settings** → **Developer settings** →
   **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**
2. Note: `signal-bot-gist` — Expiration: `No expiration` — Scope: **yalnızca `gist`**
   işaretle (repo erişimi VERME) → Generate → token'ı kopyala.
3. Render → servis → Environment → `GITHUB_TOKEN` = token → Save (redeploy tetiklenir).
4. Doğrulama: `/backup/info` → `gist_url` dolu; o URL'de dosyaları görebilirsin.

Gist "secret"tir (listelenmez) ama URL'yi bilen görebilir; içerikte API key/secret
yoktur, yalnızca sinyal istatistiği ve OHLCV vardır. Alternatif kalıcı çözüm hâlâ
geçerli: paid instance + Disk (`DB_PATH=/data/bot.db`).

### Diğer Phase 2 modülleri (bayrakla açılır)

| Özellik | Env | Varsayılan | Not |
|---|---|---|---|
| Kalıcı cooldown/state | `STATE_BACKEND=sqlite` | açık | `memory` ile eski davranış |
| Orderbook duvar notu | `ORDERBOOK_ENRICH=true` | kapalı | SIGNAL'in Volume satırına "bid wall 120 @ 42000" ekler; filtre DEĞİL, bilgi notudur |
| MarkdownV2 rich mesaj | `TELEGRAM_PARSE_MODE=MarkdownV2` | kapalı (plain) | Bold başlık + monospace seviyeler, tam escape'li |
| WebSocket kline cache | `USE_WEBSOCKET=true` | kapalı | **Deneysel.** REST bootstrap + canlı WS güncellemesi; kopunca otomatik REST fallback. 15m/4h taramada REST zaten yeterli — açmak zorunlu değil |

## Sessiz mod & Dashboard (v2.8.1)

`TELEGRAM_ENABLED=false` (render.yaml'da varsayılan) ile **hiçbir Telegram mesajı
gönderilmez** — sinyal üretimi, gölge takip ve gist yedekleme aynen sürer. Takip,
botun kök adresindeki operasyon konsolundan yapılır:

**`https://<app>.onrender.com/`** → Dashboard (v2.8 — sıcak tema + tıklanabilir paneller):
- **Portföy Simülasyonu** (sol sütun): panodan düzenlenebilir başlangıç $ +
  işlem başına risk %; R sonuçları bileşik dolar bakiyesine çevrilir; bugün /
  7 gün / 30 gün kâr-zarar satırları (kapanan+açılan sayılarıyla). Girdiler
  tarayıcıda saklanır (localStorage). Gölge simülasyondur, gerçek para değildir.
- Sıcak "linen" zemin (#F5F1E8) — bembeyaz parlamaz, uzun bakışta yormaz
- Derinlikli equity: gölgeli çizgi + katmanlı gradyan + beyaz halkalı WIN/LOSS noktaları
- Tıklanabilir: KPI kartları tabloyu filtreler · boru hattı aşaması → elenen
  pariteler modali · sinyal satırı → tam detay kartı (tp2/fill/exit/gerçekleşen R,
  aktifse invalidasyon+likidite+confluence) · yön bilançosu → LONG/SHORT filtresi ·
  market movers → Bybit işlem sayfası
- 1920×1080 hedef, 1440×900 uyumlu, sayfa scroll'u yok (iç panel kaydırmaları hariç)
- Palet: yeşil #16A34A · kırmızı #DC2626 · amber #F59E0B · mavi #2563EB, zemin #F5F7FA
- Header: logo+durum | canlı özet cümle | yenileme kontrolleri
- Sol 220px: strateji + kırmızı→yeşil skalalı filtre boru hattı + özet stacked bar
- Orta: 5 KPI (trend oklarıyla) + Chart.js equity (CDN yoksa SVG fallback) +
  LONG/SHORT karşılıklı çubuk + iç kaydırmalı sıkı sinyal tablosu
- Sağ 300px: Piyasa Nabzı (BTC/ETH + F&G gauge + pulse) + Saatlik Değerlendirme
  (6 satır clamp + "devamını gör") + 4 başlıklı haber akışı
- Sol sidebar: strateji sözleşmesi kartı + canlı **pipeline** kartı (motorun
  7 aşamalı filtre boru hattı; son taramada her aşamanın kaç pariteyi elediği,
  aşama açıklamalarıyla — "neden sinyal yok?"un cevabı) + sistem bilgisi
- Market paneli: BTC/ETH + **Korku & Açgözlülük endeksi** (alternative.me,
  1 sa önbellek) + piyasa genişliği (likit evrende ▲/▼) + **market pulse**
  (kural tabanlı anlık piyasa okuması; şablon üretimidir, böyle etiketlenir)
- Tam genişlik tek-ekran yerleşim (masaüstünde kaydırma yok)
- Masaüstünde sayfa kaydırma yok: 100vh grid; uzun listeler kendi paneli içinde kayar
- `hourly_review`: motorun saatte bir ürettiği kural-tabanlı değerlendirme
  (CommentaryService — LLM değildir; analiz şablonları koddadır, /commentary)
- `market`: BTC/ETH fiyat + 24s değişim + funding, likit evrende 24s en çok
  yükselen/düşenler (/market, Bybit ticker'ları, 60 sn önbellek)
- `news`: kripto haber başlıklarının birleşik akışı (/news, RSS/Atom,
  NEWS_FEEDS ile özelleştirilebilir, 10 dk önbellek, yorum içermez)
- Tek cümlelik özet: motor sağlığı + toplam R + win rate'in başabaş eşiğine göre konumu
- Kümülatif R eğrisi (equity curve) — nokta renkleri WIN/LOSS, üzerine gelince detay
- LONG / SHORT yön bilançosu ve sonuç dağılımı çubuğu
- Giriş isabeti (fill oranı) KPI'ı — NOT_FILLED izleme metriği
- Sinyal tablosunda durum filtreleri (Tümü/Açık/Sonuçlanan/Dolmayan) ve açık
  sinyaller için yaş / pencere göstergesi
- "Nasıl okunur?" açılır rehberi (R, başabaş, durum akışı, gölge muhasebe uyarısı)
- KPI panosu: win rate, toplam R, açık sinyal, evren boyutu, tarama sayacı, arşiv boyutu
- Gölge takipteki tüm sinyaller (durum/sonuç/R ile, renk kodlu)
- Son tarama dağılımı (SIGNAL / NO_TRADE / DATA_MISSING oran çubuğu) + aktif
  SIGNAL kararları + en sık ret nedenleri
- Sistem satırı: evren modu, gist bağlantısı, son sync
- 30 sn / 60 sn / 5 dk aralıkla kendini yeniler; harici bağımlılık yok, veriyi
  botun kendi JSON endpoint'lerinden çeker.

Telegram'ı geri açmak: Render → Environment → `TELEGRAM_ENABLED=true`.
İnce ayar alternatifi: Telegram açıkken yalnızca sinyal almak zaten varsayılandır
(`SEND_NO_TRADE=false`); tamamen susturma bu bayrakladır.

## Parite evreni (v2.2) — dinamik top-150

`SYMBOLS_MODE=top` (render.yaml'da varsayılan) ile bot izleyeceği listeyi **kendisi
seçer**: Bybit linear USDT perp'lerini 24s ciroya göre sıralar, ilk `SYMBOLS_TOP_N`
(150) tanesini alır, listeyi günde bir yeniler. Delist olan düşer, hacim kazanan
kendiliğinden girer; stable-stable çiftleri (`SYMBOLS_EXCLUDE`) elenir. Ticker
çekimi başarısız olursa son iyi liste, o da yoksa `SYMBOLS` static listesi kullanılır.

- Anlık listeyi görmek: `GET /universe` (mod, sayı, tam sembol listesi).
- 150 sembol × 2 TF ≈ tarama başına ~300 REST çağrısı, `SYMBOL_PAUSE_SEC=0.3` ile
  tarama ~2.5-3 dk sürer — 15 dk'lık `SCAN_INTERVAL` içinde rahatça biter.
- Ölçekte gist payload kontrolü: `GIST_CANDLE_MODE=signals` ile mum arşivi yalnızca
  sinyal üretmiş pariteler için sync edilir (istatistik/sinyal/karar dosyaları her
  zaman tam sync olur); `all` tüm evreni yazar, `off` kapatır. CSV başına son
  `GIST_CANDLE_MAX_ROWS` (5000) mum tutulur. SQLite'taki yerel arşiv sınırsızdır ve
  `/export/candles.csv` her parite için tam veriyi verir.
- Eski davranışa dönüş: `SYMBOLS_MODE=static`.

## Ayar önerileri

- Daha seçici: `RISK_REWARD_MIN=2.5`, `VOLUME_MULT=1.8`, `ADX_CHOP=22`
- Günlük swing: `HTF=D`, `LTF=60`, `SCAN_INTERVAL=3600`
