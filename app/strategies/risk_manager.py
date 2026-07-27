"""
Pipeline adim 7: risk / reward. Saf fonksiyon.
Entry = setup seviyesi bolgesi; Stop = seviye -/+ ATR x carpan;
Hedefler = HTF pivot seviyeleri (entry'ye 1 ATR'den yakin pivotlar gurultu sayilir).
RR esigi signal_engine'de uygulanir; burada yalnizca hesap yapilir.
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel

from app.config.settings import StrategyParams
from app.models.decision import Direction
from app.strategies.indicators import atr, find_pivots


class TradePlan(BaseModel):
    entry_min: float
    entry_max: float
    stop_loss: float
    tp1: float
    tp2: float
    rr: float


def build_trade_plan(ltf: pd.DataFrame, htf: pd.DataFrame, direction: Direction,
                     level: float, params: StrategyParams) -> TradePlan | None:
    """Plan kurulamazsa (hedef yok / risk<=0) None -> NO_TRADE."""
    a = float(atr(ltf).iloc[-1])
    close = float(ltf["close"].iloc[-1])
    ph, pl = find_pivots(htf, params.pivot_lookback, params.pivot_lookback)

    if direction is Direction.LONG:
        entry_min, entry_max = level, min(close, level + 0.5 * a)
        stop = level - params.atr_stop_mult * a
        targets = sorted({p[1] for p in ph if p[1] > entry_max + a})
        if not targets:
            return None
        tp1 = targets[0]
        tp2 = targets[1] if len(targets) > 1 else tp1 + (tp1 - entry_max)
        mid = (entry_min + entry_max) / 2
        risk, reward = mid - stop, tp1 - mid
    else:
        entry_min, entry_max = max(close, level - 0.5 * a), level
        stop = level + params.atr_stop_mult * a
        targets = sorted({p[1] for p in pl if p[1] < entry_min - a}, reverse=True)
        if not targets:
            return None
        tp1 = targets[0]
        tp2 = targets[1] if len(targets) > 1 else tp1 - (entry_min - tp1)
        mid = (entry_min + entry_max) / 2
        risk, reward = stop - mid, mid - tp1

    if risk <= 0:
        return None
    return TradePlan(
        entry_min=round(min(entry_min, entry_max), 6),
        entry_max=round(max(entry_min, entry_max), 6),
        stop_loss=round(stop, 6),
        tp1=round(tp1, 6),
        tp2=round(tp2, 6),
        rr=round(reward / risk, 2),
    )
