"""
Signal engine - pipeline orkestrasyonu. SAF FONKSIYON:
I/O yok, global state yok, zaman disaridan enjekte edilebilir (now parametresi).
Girdi: KlineSeries'ler + StrategyParams -> Cikti: Decision.

Sira sabittir; ilk fail'de kisa devre yapilir (hard filters):
1. DATA        veri eksik              -> DATA_MISSING
2. REGIME      chop                    -> NO_TRADE
3. STRUCTURE   HTF bias belirsiz       -> NO_TRADE
4. EXECUTION   LTF setup yok           -> NO_TRADE
5. VOLUME      hacim teyidi yok        -> NO_TRADE
6. (confluence - filtre degil, sadece confidence girdisi)
7. RISK_REWARD RR < esik / plan yok    -> NO_TRADE
8. SIGNAL
"""
from __future__ import annotations

from datetime import datetime

from app.config.settings import StrategyParams
from app.models.candle import KlineSeries
from app.models.decision import (
    Bias, Confidence, Decision, DecisionType, Direction, EntryZone, Regime,
    SetupType, Targets,
)
from app.strategies import indicator_confluence, regime_detector, structure_analyzer
from app.strategies.risk_manager import build_trade_plan
from app.strategies.volume_analyzer import validate_event_volume


def _fmt(v: float) -> str:
    return f"{v:.6g}"


def evaluate(pair: str, htf_series: KlineSeries | None, ltf_series: KlineSeries | None,
             params: StrategyParams, now: datetime | None = None) -> Decision:
    d = Decision.base(pair, params.htf, params.ltf, now)

    # 1. DATA
    missing = [name for name, s in (("htf_klines", htf_series), ("ltf_klines", ltf_series))
               if s is None or len(s) < params.min_bars]
    if missing:
        d.decision = DecisionType.DATA_MISSING
        d.data_missing = missing
        d.failed_filters = ["DATA"]
        d.reject_reason = "insufficient data"
        return d

    htf = htf_series.to_dataframe()
    ltf = ltf_series.to_dataframe()

    # 2. REGIME
    regime, adx_val = regime_detector.classify_regime(htf, params)
    d.regime = regime
    if regime is Regime.CHOP:
        d.failed_filters = ["REGIME"]
        d.reject_reason = f"chop regime (ADX {adx_val:.0f} < {params.adx_chop_threshold:.0f})"
        d.watch_condition = "ADX expansion + clean HTF structure break"
        return d

    # 3. STRUCTURE / BIAS
    bias, _, _ = structure_analyzer.classify_htf_bias(htf, params)
    d.htf_bias = bias
    if bias is Bias.NEUTRAL:
        d.failed_filters = ["STRUCTURE"]
        d.reject_reason = "HTF structure unclear / conflicting"
        d.watch_condition = "wait for HH/HL or LH/LL sequence to form"
        return d
    direction = Direction.LONG if bias is Bias.BULLISH else Direction.SHORT

    # 4. EXECUTION (LTF setup)
    setup = structure_analyzer.detect_setup(ltf, direction, params)
    if setup is None:
        d.failed_filters = ["EXECUTION"]
        d.reject_reason = "no valid LTF setup (no confirmed breakout/retest or sweep/reclaim)"
        d.watch_condition = (f"{direction.value} setup: volume-confirmed break + retest "
                             f"in HTF bias direction")
        return d
    d.setup_type = setup.setup_type

    # 5. VOLUME
    vol_ok, vol_ratio = validate_event_volume(ltf, setup.event_index, params)
    d.volume_confirmation = vol_ok
    d.liquidity_note = (f"{setup.setup_type.value} @ {_fmt(setup.level)} "
                        f"(vol {vol_ratio:.2f}x avg)")
    if not vol_ok:
        d.failed_filters = ["VOLUME"]
        d.reject_reason = (f"no volume confirmation on trigger bar "
                           f"({vol_ratio:.2f}x < {params.volume_mult:.2f}x avg)")
        d.watch_condition = "same setup with participation expansion"
        return d

    # 6. CONFLUENCE (filtre degil)
    conf = indicator_confluence.collect(ltf, htf, direction)
    d.indicator_confluence = conf

    # 7. RISK / REWARD
    plan = build_trade_plan(ltf, htf, direction, setup.level, params)
    if plan is None or plan.rr < params.min_rr:
        rr_txt = f"{plan.rr:.2f}" if plan else "n/a"
        d.failed_filters = ["RISK_REWARD"]
        d.reject_reason = f"RR {rr_txt} < min {params.min_rr:.1f}"
        d.watch_condition = "deeper retest for better entry location"
        return d

    # 8. SIGNAL
    d.decision = DecisionType.SIGNAL
    d.direction = direction
    d.entry_zone = EntryZone(min=plan.entry_min, max=plan.entry_max)
    d.stop_loss = plan.stop_loss
    d.targets = Targets(tp1=plan.tp1, tp2=plan.tp2)
    d.rr = plan.rr
    d.confidence = (Confidence.HIGH if len(conf) >= 3
                    else Confidence.MEDIUM if len(conf) == 2 else Confidence.LOW)
    side = "below" if direction is Direction.LONG else "above"
    d.invalidation = (f"LTF close {side} {_fmt(plan.stop_loss)} or acceptance back "
                      f"{side} {_fmt(setup.level)}")
    return d
