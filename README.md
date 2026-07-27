# Bybit Signal Engine → Telegram Bot

Conservative swing, structure-first, volume-confirmed, risk-first kripto futures sinyal motoru.
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

- **Phase 2:** WebSocket kline adapter (`MarketDataService` arayüzü değişmez),
  orderbook likidite haritası, MarkdownV2 rich formatter.
- **Phase 3:** Redis/SQLite `StateStore`, sinyal performans takibi, funding/OI verisi.

## Ayar önerileri

- Daha seçici: `RISK_REWARD_MIN=2.5`, `VOLUME_MULT=1.8`, `ADX_CHOP=22`
- Günlük swing: `HTF=D`, `LTF=60`, `SCAN_INTERVAL=3600`
