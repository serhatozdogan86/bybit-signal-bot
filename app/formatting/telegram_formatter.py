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


def render(d: Decision, parse_mode: str = "") -> str:
    if parse_mode == "MarkdownV2":
        return render_rich(d)
    if d.decision is DecisionType.SIGNAL:
        return render_signal(d)
    if d.decision is DecisionType.DATA_MISSING:
        return render_data_missing(d)
    return render_no_trade(d)


# ------------------------------------------------- Phase 2: MarkdownV2 rich mod
_MD_SPECIALS = r"_*[]()~`>#+-=|{}.!"


def escape_md(text: str) -> str:
    """MarkdownV2 ozel karakterlerini kacir (Telegram 400 hatasini onler)."""
    return "".join(f"\\{c}" if c in _MD_SPECIALS else c for c in str(text))


def render_rich(d: Decision) -> str:
    """MarkdownV2: baslik bold, seviyeler monospace. TELEGRAM_PARSE_MODE=MarkdownV2."""
    e = escape_md
    if d.decision is DecisionType.SIGNAL:
        return (
            f"*SIGNAL \\| {e(d.pair)} \\| {e(d.direction.value)}*\n"
            f"Regime: {e(d.regime.value)} \\| Bias: {e(d.htf_bias.value)}\n"
            f"Setup: {e(d.setup_type.value)} \\| Conf: {e(d.confidence.value)}\n"
            f"Entry: `{e(_n(d.entry_zone.min))} \\- {e(_n(d.entry_zone.max))}`\n"
            f"Stop: `{e(_n(d.stop_loss))}`\n"
            f"TP1: `{e(_n(d.targets.tp1))}` \\| TP2: `{e(_n(d.targets.tp2))}` "
            f"\\| RR: `{e(_n(d.rr))}`\n"
            f"Invalidation: {e(d.invalidation or '-')}\n"
            f"Volume: {e(d.liquidity_note)}\n"
            f"TF: {e(d.timeframes.htf)}/{e(d.timeframes.ltf)} \\| {e(d.timestamp_utc)}\n"
            f"_Not financial advice\\. Manage your own risk\\._"
        )
    if d.decision is DecisionType.DATA_MISSING:
        return (f"*DATA MISSING \\| {e(d.pair)}*\n"
                f"Missing: {e(', '.join(d.data_missing) or '-')}")
    return (f"*NO TRADE \\| {e(d.pair)}*\n"
            f"Regime: {e(d.regime.value)}\n"
            f"Reason: {e(d.reject_reason or '-')}\n"
            f"Watch: {e(d.watch_condition or '-')}")
