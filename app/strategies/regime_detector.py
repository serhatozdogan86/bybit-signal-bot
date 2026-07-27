"""Pipeline adim 1: regime siniflandirmasi. Saf fonksiyon."""
from __future__ import annotations

import pandas as pd

from app.config.settings import StrategyParams
from app.models.decision import Regime
from app.strategies.indicators import adx, ema


def classify_regime(htf: pd.DataFrame, params: StrategyParams) -> tuple[Regime, float]:
    """
    ADX + EMA50 egimiyle regime tespiti.
    ADX < esik           -> CHOP     (hard filter: NO_TRADE)
    |EMA50 egimi| ~ 0    -> RANGING
    aksi halde           -> TRENDING
    Donus: (regime, adx_degeri)
    """
    adx_val = float(adx(htf).iloc[-1])
    e50 = ema(htf["close"], 50)
    slope_pct = float((e50.iloc[-1] - e50.iloc[-6]) / e50.iloc[-6] * 100)

    if adx_val < params.adx_chop_threshold:
        return Regime.CHOP, adx_val
    if abs(slope_pct) < 0.05:
        return Regime.RANGING, adx_val
    return Regime.TRENDING, adx_val
