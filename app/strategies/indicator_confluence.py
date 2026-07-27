"""
Pipeline adim 6: indikator confluence - YALNIZCA teyit notu uretir.
Bu modul karar veremez, filtre uygulayamaz; sadece confidence'a girdi saglar.
"""
from __future__ import annotations

import pandas as pd

from app.models.decision import Direction
from app.strategies.indicators import ema, rsi


def collect(ltf: pd.DataFrame, htf: pd.DataFrame, direction: Direction) -> list[str]:
    notes: list[str] = []
    close = float(ltf["close"].iloc[-1])
    e20 = float(ema(ltf["close"], 20).iloc[-1])
    e50 = float(ema(ltf["close"], 50).iloc[-1])
    r = float(rsi(ltf["close"]).iloc[-1])
    e200h = float(ema(htf["close"], 200).iloc[-1])

    if direction is Direction.LONG:
        if close > e20 > e50:
            notes.append("LTF EMA20>EMA50 aligned")
        if 40 <= r <= 65:
            notes.append(f"RSI {r:.0f} healthy (not overbought)")
        if close > e200h:
            notes.append("Price above HTF EMA200")
    else:
        if close < e20 < e50:
            notes.append("LTF EMA20<EMA50 aligned")
        if 35 <= r <= 60:
            notes.append(f"RSI {r:.0f} healthy (not oversold)")
        if close < e200h:
            notes.append("Price below HTF EMA200")
    return notes
