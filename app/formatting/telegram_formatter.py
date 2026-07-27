"""
Telegram plain-text formatter (MVP: parse_mode YOK, escape derdi yok).
Uc karar tipi de tam desteklenir. Rich formatting (MarkdownV2) Phase 2'de
yalnizca bu modul degistirilerek eklenir; notifier ve engine degismez.
"""
from __future__ import annotations

from app.models.decision import Decision, DecisionType

_SEP = "---------------------------"


def _n(v: float | None) -> str:
    return f"{v:.6g}" if v is not None else "-"


def render_signal(d: Decision) -> str:
    conf = "\n".join(f"  + {c}" for c in d.indicator_confluence) or "  -"
    return (
        f"SIGNAL | {d.pair} | {d.direction.value}\n"
        f"{_SEP}\n"
        f"Regime: {d.regime.value} | Bias: {d.htf_bias.value}\n"
        f"Setup: {d.setup_type.value} | Conf: {d.confidence.value}\n"
        f"Entry: {_n(d.entry_zone.min)} - {_n(d.entry_zone.max)}\n"
        f"Stop: {_n(d.stop_loss)}\n"
        f"TP1: {_n(d.targets.tp1)} | TP2: {_n(d.targets.tp2)} | RR: {_n(d.rr)}\n"
        f"Invalidation: {d.invalidation}\n"
        f"Volume: {d.liquidity_note}\n"
        f"Confluence:\n{conf}\n"
        f"{_SEP}\n"
        f"TF: {d.timeframes.htf}/{d.timeframes.ltf} | {d.timestamp_utc}\n"
        f"Not financial advice. Manage your own risk."
    )


def render_no_trade(d: Decision) -> str:
    return (
        f"NO TRADE | {d.pair}\n"
        f"{_SEP}\n"
        f"Regime: {d.regime.value}\n"
        f"Reason: {d.reject_reason or '-'}\n"
        f"Failed: {', '.join(d.failed_filters) or '-'}\n"
        f"Watch: {d.watch_condition or '-'}\n"
        f"{_SEP}\n"
        f"TF: {d.timeframes.htf}/{d.timeframes.ltf} | {d.timestamp_utc}"
    )


def render_data_missing(d: Decision) -> str:
    return (
        f"DATA MISSING | {d.pair}\n"
        f"{_SEP}\n"
        f"Missing: {', '.join(d.data_missing) or '-'}\n"
        f"Action: no assumption made, no signal produced\n"
        f"{_SEP}\n"
        f"TF: {d.timeframes.htf}/{d.timeframes.ltf} | {d.timestamp_utc}"
    )


def render(d: Decision) -> str:
    if d.decision is DecisionType.SIGNAL:
        return render_signal(d)
    if d.decision is DecisionType.DATA_MISSING:
        return render_data_missing(d)
    return render_no_trade(d)
