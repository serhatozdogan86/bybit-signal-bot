"""
Output contract - schema v1.2.
Alan isimleri SABITTIR; entegrasyonlar bu sozlesmeye gore parse eder.
decision enum: SIGNAL | NO_TRADE | DATA_MISSING
v1.2 (2026-08-05): market_bias eklendi - karar aninda gecerli BTC piyasa
rejimi (bull/bear/neutral/halt). Geriye uyumlu: alan eklemesi, degisiklik yok.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.2"
DISCLAIMER = "Decision support only. Not financial advice."


class DecisionType(str, Enum):
    SIGNAL = "SIGNAL"
    NO_TRADE = "NO_TRADE"
    DATA_MISSING = "DATA_MISSING"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


class Regime(str, Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    CHOP = "chop"
    TRANSITIONAL = "transitional"
    UNKNOWN = "unknown"


class Bias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SetupType(str, Enum):
    BREAKOUT_RETEST = "breakout_retest"
    SWEEP_RECLAIM = "sweep_reclaim"
    TREND_PULLBACK = "trend_pullback"
    NONE = "none"


class Confidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TimeFrames(BaseModel):
    htf: str
    ltf: str


class EntryZone(BaseModel):
    min: float | None = None
    max: float | None = None


class Targets(BaseModel):
    tp1: float | None = None
    tp2: float | None = None


class Decision(BaseModel):
    """SIGNAL / NO_TRADE / DATA_MISSING kararlarinin tamami icin tek model."""

    schema_version: str = SCHEMA_VERSION
    pair: str
    timestamp_utc: str
    timeframes: TimeFrames
    decision: DecisionType = DecisionType.NO_TRADE
    direction: Direction = Direction.NONE
    regime: Regime = Regime.UNKNOWN
    htf_bias: Bias = Bias.NEUTRAL
    setup_type: SetupType = SetupType.NONE
    confidence: Confidence = Confidence.LOW
    entry_zone: EntryZone = Field(default_factory=EntryZone)
    stop_loss: float | None = None
    targets: Targets = Field(default_factory=Targets)
    rr: float | None = None
    invalidation: str | None = None
    volume_confirmation: bool = False
    liquidity_note: str = ""
    indicator_confluence: list[str] = Field(default_factory=list)
    failed_filters: list[str] = Field(default_factory=list)
    reject_reason: str | None = None
    watch_condition: str | None = None
    data_missing: list[str] = Field(default_factory=list)
    # v1.2: karar aninda gecerli BTC piyasa rejimi. Decision.regime sembolun
    # kendi rejimidir ve her SIGNAL tanim geregi trending'dir; otopside
    # "hangi piyasa rejiminde dogdu" analizi bu alana dayanir.
    market_bias: str = "neutral"
    disclaimer: str = DISCLAIMER

    def contract_dict(self) -> dict:
        """Makinece parse edilebilir sabit JSON temsili."""
        return self.model_dump(mode="json")

    @classmethod
    def base(cls, pair: str, htf: str, ltf: str, now: datetime | None = None) -> "Decision":
        now = now or datetime.now(timezone.utc)
        return cls(
            pair=pair,
            timestamp_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            timeframes=TimeFrames(htf=htf, ltf=ltf),
        )
