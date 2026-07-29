

def test_market_bias_hysteresis_and_failclosed(tmp_path):
    """v3.5: 2-mum teyidi olmadan rejim degismez; veri yoksa TTL sonrasi halt."""
    import time as _t
    from unittest.mock import MagicMock
    from app.scheduler import Scheduler as _S
    sch = object.__new__(_S)                 # __init__ atlanir; alanlar elle
    sch._settings = MagicMock(HTF="240")
    sch._md = MagicMock()

    def series_from(closes):
        import numpy as np
        from tests import fixtures as fx
        return fx.make_series(np.array(closes, dtype=float),
                              interval="240", seed=9)
    base = [100.0] * 130                      # EMA ~100
    # tek mum esik ustu (son mum +%2, onceki notr) -> gecis YOK (neutral kalir)
    sch._md.get_series.return_value = series_from(base[:-1] + [102.0])
    assert sch._compute_market_bias() == "neutral"
    # iki ardisik mum esik ustu -> bull
    sch._md.get_series.return_value = series_from(base[:-2] + [102.0, 102.5])
    assert sch._compute_market_bias() == "bull"
    # banda geri sarkma -> onceki rejim korunur (histerezis)
    sch._md.get_series.return_value = series_from(base[:-1] + [100.1])
    assert sch._compute_market_bias() == "bull"
    # veri kesildi: TTL icinde son rejim, TTL asilinca halt (fail-closed)
    sch._md.get_series.side_effect = RuntimeError("api down")
    assert sch._compute_market_bias() == "bull"
    sch._bias_ts = _t.time() - 7300
    assert sch._compute_market_bias() == "halt"
