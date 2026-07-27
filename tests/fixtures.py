"""Sentetik veri ureticileri - canli API gerektirmeden engine testi."""
from __future__ import annotations

import numpy as np

from app.models.candle import Candle, KlineSeries


def make_series(closes: np.ndarray, symbol: str = "TESTUSDT", interval: str = "15",
                volumes: np.ndarray | None = None, seed: int = 1) -> KlineSeries:
    rng = np.random.default_rng(seed)
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    high = closes * (1 + rng.uniform(0.001, 0.004, n))
    low = closes * (1 - rng.uniform(0.001, 0.004, n))
    opens = np.roll(closes, 1)
    opens[0] = closes[0]
    vols = volumes if volumes is not None else rng.uniform(900.0, 1100.0, n)
    candles = [
        Candle(ts=i * 60_000, open=float(opens[i]), high=float(high[i]),
               low=float(low[i]), close=float(closes[i]),
               volume=float(vols[i]), turnover=float(vols[i] * closes[i]))
        for i in range(n)
    ]
    return KlineSeries(symbol=symbol, interval=interval, candles=candles)


def chop_closes(n: int = 200, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 100 + np.cumsum(rng.normal(0, 0.08, n))


def bullish_htf_closes() -> np.ndarray:
    """Merdiven yukselis: seyrek pivot, temiz HH/HL, uzak TP hedefi (133)."""
    return np.concatenate([
        np.linspace(100, 110, 45),
        np.linspace(110, 106, 10),
        np.linspace(106, 120, 45),
        np.linspace(120, 114, 10),
        np.linspace(114, 133, 60),
        np.linspace(133, 129, 15),
        np.linspace(129, 131, 15),
    ])


def bullish_ltf_closes() -> np.ndarray:
    """Range (~128.6 tepe) -> kirilim -> acceptance -> retest -> devam."""
    return np.concatenate([
        128 + 0.6 * np.sin(np.linspace(0, 10 * np.pi, 150)),
        np.linspace(128.6, 131.5, 20),
        np.linspace(131.5, 128.8, 15),
        np.linspace(128.9, 131.0, 15),
    ])


def breakout_volumes(n: int = 200, spike_at: slice = slice(150, 156),
                     spike: float = 2600.0) -> np.ndarray:
    vols = np.full(n, 1000.0)
    vols[spike_at] = spike
    return vols


def mirror(closes: np.ndarray, center: float = 120.0) -> np.ndarray:
    """LONG senaryosunu ayni yapiyla SHORT'a cevirir (fiyati merkeze gore yansit)."""
    return 2 * center - closes
