"""Piyasa verisi modelleri."""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field


class Candle(BaseModel):
    """Tek OHLCV mumu (Bybit v5 kline satiri)."""

    ts: int = Field(description="Acilis zamani (ms epoch)")
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float = 0.0


class KlineSeries(BaseModel):
    """Kronolojik (eski -> yeni) mum serisi."""

    symbol: str
    interval: str
    candles: list[Candle]

    def __len__(self) -> int:
        return len(self.candles)

    def to_dataframe(self) -> pd.DataFrame:
        """Engine'in kullandigi DataFrame temsili (kolonlar sabit)."""
        return pd.DataFrame([c.model_dump() for c in self.candles])

    @classmethod
    def from_bybit_rows(cls, symbol: str, interval: str, rows: list[list[str]]) -> "KlineSeries":
        """
        Bybit v5 kline satirlarini modele cevirir.
        Bybit yeniden -> eskiye dondurur; burada ters cevrilir.
        """
        candles = [
            Candle(
                ts=int(r[0]), open=float(r[1]), high=float(r[2]),
                low=float(r[3]), close=float(r[4]),
                volume=float(r[5]), turnover=float(r[6]) if len(r) > 6 else 0.0,
            )
            for r in reversed(rows)
        ]
        return cls(symbol=symbol, interval=interval, candles=candles)
