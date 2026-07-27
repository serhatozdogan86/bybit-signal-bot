"""Pipeline adim 4: hacim / katilim dogrulamasi. Saf fonksiyon."""
from __future__ import annotations

import pandas as pd

from app.config.settings import StrategyParams

_VOL_SMA_WINDOW = 20


def validate_event_volume(ltf: pd.DataFrame, event_index: int,
                          params: StrategyParams) -> tuple[bool, float]:
    """
    Setup'in tetik mumu (kirilim / reclaim) hacmini ortalama hacimle kiyaslar.
    Kosul: event hacmi >= volume_mult x SMA20(hacim).
    Donus: (teyit_var_mi, oran). Ortalama hesaplanamiyorsa (False, 0.0).
    """
    avg = ltf["volume"].rolling(_VOL_SMA_WINDOW).mean().iloc[-2]
    if pd.isna(avg) or avg <= 0:
        return False, 0.0
    ratio = float(ltf["volume"].iloc[event_index] / avg)
    return ratio >= params.volume_mult, round(ratio, 2)
