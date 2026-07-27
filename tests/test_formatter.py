"""Formatter testleri - uc karar tipi de plain-text olarak render edilmeli."""
from __future__ import annotations

from app.config.settings import StrategyParams
from app.formatting import telegram_formatter as tf
from app.strategies import signal_engine
from tests import fixtures as fx

PARAMS = StrategyParams()


def test_render_signal_contains_all_operational_fields():
    htf = fx.make_series(fx.bullish_htf_closes(), interval="240", seed=3)
    ltf = fx.make_series(fx.bullish_ltf_closes(), interval="15",
                         volumes=fx.breakout_volumes(), seed=4)
    d = signal_engine.evaluate("TRENDUSDT", htf, ltf, PARAMS)
    text = tf.render(d)
    for token in ("SIGNAL | TRENDUSDT | LONG", "Entry:", "Stop:", "TP1:",
                  "RR:", "Invalidation:", "Not financial advice"):
        assert token in text
    assert "*" not in text and "_" not in text.replace("breakout_retest", "")  # plain text


def test_render_no_trade():
    htf = fx.make_series(fx.chop_closes(), interval="240")
    ltf = fx.make_series(fx.chop_closes(seed=8), interval="15")
    d = signal_engine.evaluate("CHOPUSDT", htf, ltf, PARAMS)
    text = tf.render(d)
    assert text.startswith("NO TRADE | CHOPUSDT")
    assert "Reason:" in text and "Failed: REGIME" in text


def test_render_data_missing():
    d = signal_engine.evaluate("NODATAUSDT", None, None, PARAMS)
    text = tf.render(d)
    assert text.startswith("DATA MISSING | NODATAUSDT")
    assert "htf_klines" in text and "ltf_klines" in text
    assert "no assumption made" in text
