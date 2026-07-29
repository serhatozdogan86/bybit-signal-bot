"""
Config loader - tum ayarlar env'den, tipli ve dogrulanmis.
Engine katmanina Settings degil StrategyParams enjekte edilir (saf/test edilebilir).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class StrategyParams(BaseModel):
    """Signal engine'in ihtiyac duydugu tum esikler. Engine'e bagimlilik olarak gecer."""

    htf: str = "240"
    ltf: str = "15"
    min_rr: float = 2.0
    adx_chop_threshold: float = 20.0
    volume_mult: float = 1.5
    pivot_lookback: int = 3
    atr_stop_mult: float = 1.2
    min_bars: int = 60
    rr_max: float = 6.0        # v3.0: plan RR tavani (asiri dar stop filtresi)
    market_gate: bool = True   # v3.0: rejim karsiti sinyalleri blokla


class Settings(BaseSettings):
    """Env degiskenleri. Alan adi == env adi."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Bybit (public; key MVP'de kullanilmaz, rezerve)
    BYBIT_BASE_URL: str = "https://api.bybit.com"
    BYBIT_API_KEY: str = ""
    BYBIT_API_SECRET: str = ""

    # v2.5: dashboard market/haber/yorum panelleri
    NEWS_FEEDS: str = ("https://www.coindesk.com/arc/outboundfeeds/rss/,"
                       "https://cointelegraph.com/rss")
    NEWS_TTL_SEC: int = 600
    MARKET_TTL_SEC: int = 60
    COMMENT_INTERVAL_SEC: int = 3600

    # Telegram
    TELEGRAM_ENABLED: bool = True   # false -> hicbir mesaj gonderilmez (sinyal uretimi/takip surer)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Tarama & evren secimi
    SYMBOLS: str = "BTCUSDT,ETHUSDT,SOLUSDT"   # static mod listesi + fallback
    SYMBOLS_MODE: str = "static"                # static | top (hacme gore dinamik)
    SYMBOLS_TOP_N: int = 150                    # top modda kac parite izlenecek
    SYMBOLS_EXCLUDE: str = "USDCUSDT,USDEUSDT,FDUSDUSDT"  # stable-stable ciftleri
    UNIVERSE_REFRESH_SEC: int = 86400           # evren listesi yenileme (gunluk)
    SYMBOL_PAUSE_SEC: float = 0.3               # semboller arasi bekleme
    HTF: str = "240"
    LTF: str = "15"
    SCAN_INTERVAL: int = 900

    # Strateji
    RISK_REWARD_MIN: float = 2.0
    RISK_REWARD_MAX: float = 6.0
    MARKET_GATE_ENABLED: bool = True
    ADX_CHOP: float = 20.0
    VOLUME_MULT: float = 1.5
    PIVOT_LOOKBACK: int = 3
    ATR_STOP_MULT: float = 1.2

    # Davranis
    SEND_NO_TRADE: bool = False
    SEND_DATA_MISSING: bool = False
    SIGNAL_COOLDOWN_SEC: int = 14400
    LOG_LEVEL: str = "INFO"

    # Phase 2 - kalicilik & golge takip
    DB_PATH: str = "data/bot.db"
    STATE_BACKEND: str = "sqlite"          # sqlite | memory
    SHADOW_TRACKING: bool = True           # sessiz performans takibi + veri arsivi
    SHADOW_FILL_WINDOW_BARS: int = 24      # entry bolgesine giris icin bekleme (LTF bar)
    SHADOW_MAX_TRACK_BARS: int = 192       # fill sonrasi max izleme (192x15m = 48 saat)

    # Phase 2 - gist yedekleme (botun kendi kayit tutma mekanizmasi)
    GITHUB_TOKEN: str = ""                 # sadece 'gist' scope'lu PAT
    GIST_SYNC: bool = True                 # token varsa saatte bir gist'e yaz + boot'ta restore
    GIST_ID: str = ""                      # bos = marker ile otomatik bul/olustur
    GIST_SYNC_INTERVAL_SEC: int = 3600
    GIST_CANDLE_MODE: str = "signals"      # all | signals | off (150+ sembolde payload kontrolu)
    GIST_CANDLE_MAX_ROWS: int = 5000       # csv basina son N mum

    # Phase 2 - zenginlestirme & format
    ORDERBOOK_ENRICH: bool = False         # SIGNAL'e orderbook duvar notu ekle
    USE_WEBSOCKET: bool = False            # deneysel: WS kline cache (REST fallback'li)
    TELEGRAM_PARSE_MODE: str = ""          # "" (plain) | MarkdownV2

    @property
    def symbols(self) -> list[str]:
        return [s.strip().upper() for s in self.SYMBOLS.split(",") if s.strip()]

    @property
    def strategy_params(self) -> StrategyParams:
        return StrategyParams(
            htf=self.HTF,
            ltf=self.LTF,
            min_rr=self.RISK_REWARD_MIN,
            adx_chop_threshold=self.ADX_CHOP,
            volume_mult=self.VOLUME_MULT,
            pivot_lookback=self.PIVOT_LOOKBACK,
            atr_stop_mult=self.ATR_STOP_MULT,
            rr_max=self.RISK_REWARD_MAX,
            market_gate=self.MARKET_GATE_ENABLED,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
