"""
Pipeline adim 2-3-5: HTF structure/bias + LTF execution setup + likidite davranisi.
Saf fonksiyonlar - I/O yok.

MVP'de likidite haritasi = swing seviyeleri + sweep/reclaim davranisi.
(Orderbook-tabanli likidite duvarlari Phase 2.)

Hacim kontrolu BILINCLI olarak burada YOK: structure adayi bulur,
volume_analyzer dogrular, signal_engine karari verir (tek sorumluluk).
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel

from app.config.settings import StrategyParams
from app.models.decision import Bias, Direction, SetupType
from app.strategies.indicators import Pivot, ema, find_pivots

_RETEST_TOL = 0.002        # seviyeye %0.2 yaklasma retest sayilir
_MAX_BREAK_AGE = 60        # kirilim en fazla 60 bar once olmali
_MIN_ACCEPTANCE = 2        # kirilim sonrasi dogru tarafta min kapanis
_SWEEP_WINDOW = 12         # sweep son 12 bar icinde aranir


class SetupCandidate(BaseModel):
    """Structure katmaninin ciktisi; hacim dogrulamasi signal_engine'de yapilir."""

    setup_type: SetupType
    level: float
    event_index: int  # kirilim / reclaim mumu (hacim bu barda olculur)


def classify_htf_bias(htf: pd.DataFrame,
                      params: StrategyParams) -> tuple[Bias, list[Pivot], list[Pivot]]:
    """HH/HL + EMA200 ustu -> BULLISH; LH/LL + EMA200 alti -> BEARISH; aksi NEUTRAL."""
    ph, pl = find_pivots(htf, params.pivot_lookback, params.pivot_lookback)
    if len(ph) < 2 or len(pl) < 2:
        return Bias.NEUTRAL, ph, pl

    hh, hl = ph[-1][1] > ph[-2][1], pl[-1][1] > pl[-2][1]
    lh, ll = ph[-1][1] < ph[-2][1], pl[-1][1] < pl[-2][1]
    close = float(htf["close"].iloc[-1])
    e200 = float(ema(htf["close"], 200).iloc[-1])

    if hh and hl and close > e200:
        return Bias.BULLISH, ph, pl
    if lh and ll and close < e200:
        return Bias.BEARISH, ph, pl
    return Bias.NEUTRAL, ph, pl


def detect_breakout_retest(ltf: pd.DataFrame, direction: Direction,
                           params: StrategyParams) -> SetupCandidate | None:
    """
    Kosullar (hepsi zorunlu):
    - LTF swing seviyesi kirilmis ve kirilim son _MAX_BREAK_AGE bar icinde
    - Acceptance: kirilim sonrasi >= _MIN_ACCEPTANCE kapanis dogru tarafta
    - Retest: fiyat seviyeye geri dokunmus
    - Son kapanis hala seviyenin dogru tarafinda (seviye geri kaybedilmemis)
    """
    ph, pl = find_pivots(ltf, params.pivot_lookback, params.pivot_lookback)
    closes, lows, highs = ltf["close"].values, ltf["low"].values, ltf["high"].values
    n = len(ltf)
    pivots = ph if direction is Direction.LONG else pl
    candidates = [p for p in pivots if p[0] < n - 6]

    for idx, level in reversed(candidates):
        break_i: int | None = None
        for i in range(idx + 1, n - 3):
            crossed = closes[i] > level if direction is Direction.LONG else closes[i] < level
            if crossed:
                break_i = i
                break
        if break_i is None:
            continue
        if break_i < n - _MAX_BREAK_AGE:
            continue

        # KILIT-2 (2026-08-12): dilimler break_i+1'den baslar. Kirilim
        # mumunun kendisi 'geri test' SAYILMAZ - o mum seviyeyi zaten
        # icinden gectigi icin dibi/tepesi tolerans bandindadir ve retest
        # sartini bosaltiyordu (kilit-1 otopsisi + dis denetim Bulgu 1;
        # kirmizi test: test_breakout_retest_requires_actual_retest).
        after = closes[break_i + 1:n]
        accepted = (after > level) if direction is Direction.LONG else (after < level)
        if int(accepted.sum()) < _MIN_ACCEPTANCE:
            continue

        if direction is Direction.LONG:
            touched = (lows[break_i + 1:n] <= level * (1 + _RETEST_TOL)).any()
            still_ok = closes[-1] > level
        else:
            touched = (highs[break_i + 1:n] >= level * (1 - _RETEST_TOL)).any()
            still_ok = closes[-1] < level
        if not touched or not still_ok:
            continue

        return SetupCandidate(setup_type=SetupType.BREAKOUT_RETEST,
                              level=float(level), event_index=break_i)
    return None


def detect_sweep_reclaim(ltf: pd.DataFrame, direction: Direction,
                         params: StrategyParams) -> SetupCandidate | None:
    """
    Kosullar (hepsi zorunlu):
    - Son _SWEEP_WINDOW bar icinde fitil onceki swing low/high otesine tasmis (sweep)
    - Ayni mumun kapanisi seviyenin dogru tarafina donmus (reclaim)
    - Reclaim sonrasi TUM kapanislar yonu teyit ediyor (yon teyidi hard filter)
    """
    ph, pl = find_pivots(ltf, params.pivot_lookback, params.pivot_lookback)
    closes, lows, highs = ltf["close"].values, ltf["low"].values, ltf["high"].values
    n = len(ltf)
    pivots = pl if direction is Direction.LONG else ph
    candidates = [p for p in pivots if p[0] < n - _SWEEP_WINDOW]
    if not candidates:
        return None
    level = candidates[-1][1]

    for i in range(n - _SWEEP_WINDOW, n - 1):
        swept = lows[i] < level if direction is Direction.LONG else highs[i] > level
        reclaimed = closes[i] > level if direction is Direction.LONG else closes[i] < level
        if not (swept and reclaimed):
            continue
        after = closes[i + 1:n]
        if len(after) == 0:
            return None
        confirmed = (after > level).all() if direction is Direction.LONG else (after < level).all()
        if not confirmed:
            return None  # sweep sonrasi yon teyidi yok -> hard reject
        return SetupCandidate(setup_type=SetupType.SWEEP_RECLAIM,
                              level=float(level), event_index=i)
    return None


def detect_setup(ltf: pd.DataFrame, direction: Direction,
                 params: StrategyParams) -> SetupCandidate | None:
    """Oncelik: breakout_retest > sweep_reclaim."""
    return (detect_breakout_retest(ltf, direction, params)
            or detect_sweep_reclaim(ltf, direction, params))
