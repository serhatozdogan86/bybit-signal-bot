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


class Settings(BaseSettings):
    """Env degiskenleri. Alan adi == env adi."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Bybit (public; key MVP'de kullanilmaz, rezerve)
    BYBIT_BASE_URL: str = "https://api.bybit.com"
    BYBIT_API_KEY: str = ""
    BYBIT_API_SECRET: str = ""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Tarama
    SYMBOLS: str = "BTCUSDT,ETHUSDT,SOLUSDT"
    HTF: str = "240"
    LTF: str = "15"
    SCAN_INTERVAL: int = 900

    # Strateji
    RISK_REWARD_MIN: float = 2.0
    ADX_CHOP: float = 20.0
    VOLUME_MULT: float = 1.5
    PIVOT_LOOKBACK: int = 3
    ATR_STOP_MULT: float = 1.2

    # Davranis
    SEND_NO_TRADE: bool = False
    SEND_DATA_MISSING: bool = False
    SIGNAL_COOLDOWN_SEC: int = 14400
    LOG_LEVEL: str = "INFO"

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
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
