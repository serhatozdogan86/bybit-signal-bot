"""Signal engine testleri - her hard filtre icin en az bir senaryo."""
from __future__ import annotations

from app.config.settings import StrategyParams
from app.models.decision import Bias, DecisionType, Direction, Regime, SetupType
from app.strategies import signal_engine
from tests import fixtures as fx

PARAMS = StrategyParams()


def _long_scenario(volumes=None):
    htf = fx.make_series(fx.bullish_htf_closes(), interval="240", seed=3)
    vols = volumes if volumes is not None else fx.breakout_volumes()
    ltf = fx.make_series(fx.bullish_ltf_closes(), interval="15", volumes=vols, seed=4)
    return htf, ltf


def test_chop_regime_rejected():
    htf = fx.make_series(fx.chop_closes(), interval="240")
    ltf = fx.make_series(fx.chop_closes(seed=8), interval="15")
    d = signal_engine.evaluate("CHOPUSDT", htf, ltf, PARAMS)
    assert d.decision is DecisionType.NO_TRADE
    assert d.regime is Regime.CHOP
    assert "REGIME" in d.failed_filters
    assert d.direction is Direction.NONE


def test_signal_long_full_pipeline():
    htf, ltf = _long_scenario()
    d = signal_engine.evaluate("TRENDUSDT", htf, ltf, PARAMS)
    assert d.decision is DecisionType.SIGNAL
    assert d.direction is Direction.LONG
    assert d.htf_bias is Bias.BULLISH
    assert d.setup_type is SetupType.BREAKOUT_RETEST
    assert d.volume_confirmation is True
    assert d.rr is not None and d.rr >= PARAMS.min_rr
    assert d.entry_zone.min is not None and d.stop_loss is not None
    assert d.stop_loss < d.entry_zone.min          # LONG: stop entry altinda
    assert d.targets.tp1 > d.entry_zone.max        # hedef entry ustunde
    assert d.invalidation


def test_signal_short_mirrored_pipeline():
    htf = fx.make_series(fx.mirror(fx.bullish_htf_closes()), interval="240", seed=3)
    ltf = fx.make_series(fx.mirror(fx.bullish_ltf_closes()), interval="15",
                         volumes=fx.breakout_volumes(), seed=4)
    d = signal_engine.evaluate("BEARUSDT", htf, ltf, PARAMS)
    assert d.decision is DecisionType.SIGNAL
    assert d.direction is Direction.SHORT
    assert d.htf_bias is Bias.BEARISH
    assert d.stop_loss > d.entry_zone.max          # SHORT: stop entry ustunde
    assert d.targets.tp1 < d.entry_zone.min


def test_volume_reject():
    """Ayni yapisal setup, hacim patlamasi yok -> VOLUME hard filter."""
    htf, ltf = _long_scenario(volumes=fx.breakout_volumes(spike=1000.0))
    d = signal_engine.evaluate("NOVOLUSDT", htf, ltf, PARAMS)
    assert d.decision is DecisionType.NO_TRADE
    assert "VOLUME" in d.failed_filters
    assert d.volume_confirmation is False
    assert d.setup_type is SetupType.BREAKOUT_RETEST  # yapi bulundu ama hacim yok


def test_rr_reject_with_high_threshold():
    """Gecerli setup, ama esik cok yuksekse RISK_REWARD filtresi calismali."""
    htf, ltf = _long_scenario()
    strict = StrategyParams(min_rr=50.0)
    d = signal_engine.evaluate("RRUSDT", htf, ltf, strict)
    assert d.decision is DecisionType.NO_TRADE
    assert "RISK_REWARD" in d.failed_filters


def test_data_missing_htf():
    _, ltf = _long_scenario()
    d = signal_engine.evaluate("NODATAUSDT", None, ltf, PARAMS)
    assert d.decision is DecisionType.DATA_MISSING
    assert d.data_missing == ["htf_klines"]
    assert d.failed_filters == ["DATA"]


def test_data_missing_both():
    d = signal_engine.evaluate("NODATAUSDT", None, None, PARAMS)
    assert d.decision is DecisionType.DATA_MISSING
    assert set(d.data_missing) == {"htf_klines", "ltf_klines"}


def test_contract_dict_field_names_are_stable():
    d = signal_engine.evaluate("NODATAUSDT", None, None, PARAMS)
    c = d.contract_dict()
    expected = {
        "schema_version", "pair", "timestamp_utc", "timeframes", "decision",
        "direction", "regime", "htf_bias", "setup_type", "confidence",
        "entry_zone", "stop_loss", "targets", "rr", "invalidation",
        "volume_confirmation", "liquidity_note", "indicator_confluence",
        "failed_filters", "reject_reason", "watch_condition", "data_missing",
        "market_bias", "disclaimer",
    }
    assert set(c.keys()) == expected
    assert c["schema_version"] == "1.2"


def test_market_bias_recorded_in_contract():
    """v1.2: sinyal aninda gecerli BTC piyasa rejimi sozlesmeye yazilir.

    Otopside 'hangi rejimde dogdu' analizi bu alana dayanir; onceden hicbir
    yere kaydedilmiyordu (Decision.regime sembol rejimidir ve her SIGNAL
    tanim geregi trending'dir - ayristirmaz).
    """
    htf, ltf = _long_scenario()
    d = signal_engine.evaluate("BIASUSDT", htf, ltf, PARAMS, market_bias="bull")
    assert d.decision is DecisionType.SIGNAL
    assert d.market_bias == "bull"
    assert d.contract_dict()["market_bias"] == "bull"
    # NO_TRADE/DATA_MISSING kararlarinda da tasinir (karar arsivi icin)
    d2 = signal_engine.evaluate("BIASUSDT", None, None, PARAMS,
                                market_bias="bear")
    assert d2.contract_dict()["market_bias"] == "bear"


def test_breakout_retest_requires_actual_retest():
    """KILIT-2 (2026-08-12, Bulgu 1): retest/acceptance dilimleri kirilim
    mumunun KENDISINDEN basliyordu; kirilim mumunun dibi seviyenin altinda
    kaldigi icin 'geri test' sarti fiilen BOSTU - motor kirilimi gorur
    gormez kovaliyordu. Kural: fiyat kirip HIC geri donmuyorsa kurulum YOK.
    (midas'ta ayni hata 8 Agu'da kanitlanip duzeltildi; kilit-1 defterinin
    16/17 islemi bu setup ve -12R idi.)"""
    import numpy as np
    import pandas as pd
    from app.strategies.structure_analyzer import detect_breakout_retest

    # Duz zemin (100.0) + idx 60'ta tek igne pivot (100.5). idx 100'de
    # kirilim mumu seviyeyi ARALIGI ICINDEN gecer (low 100.4, close 101) -
    # eski kod bu mumun kendi dibini 'retest' sayardi. Sonrasi monoton
    # ralli: hicbir mum seviyeye geri DONMEZ -> dogru cevap: kurulum yok.
    n = 120
    close = np.concatenate([np.full(100, 100.0), np.linspace(101, 112, 20)])
    high = close + 0.05
    low = close - 0.05
    high[60] = 100.5                     # pivot tepe
    low[100] = 100.4                     # kirilim mumu seviyeden geciyor
    df = pd.DataFrame({"close": close, "low": low, "high": high,
                       "open": close, "volume": 1000.0})
    assert detect_breakout_retest(df, Direction.LONG, PARAMS) is None, (
        "geri test HIC olmadan kurulum bulundu - retest sarti bos")
    # asiri sikilastirma kontrolu: GERCEK retest'li fixture hala bulunmali
    ltf = fx.make_series(fx.bullish_ltf_closes(), interval="15",
                         volumes=fx.breakout_volumes(), seed=4)
    real = detect_breakout_retest(ltf.to_dataframe(), Direction.LONG, PARAMS)
    assert real is not None and real.setup_type is SetupType.BREAKOUT_RETEST


# ------------------------------------------------------------- v3.0
def test_market_gate_blocks_counter_regime_long():
    htf, ltf = _long_scenario()
    d = signal_engine.evaluate("GATEUSDT", htf, ltf, PARAMS, market_bias="bear")
    assert d.decision is DecisionType.NO_TRADE
    assert "MARKET_GATE" in d.failed_filters
    assert "counter-regime long" in d.reject_reason
    # v3.4: bloklanan karar tam plan seviyeleri tasimali (karsi-olgu takibi)
    assert d.rr is not None and d.entry_zone.min is not None
    assert d.stop_loss is not None and d.direction is Direction.LONG
    # ayni senaryo bull/neutral bias'ta SIGNAL olmali (kapi tek tarafli)
    assert signal_engine.evaluate("GATEUSDT", htf, ltf, PARAMS,
                                  market_bias="bull").decision is DecisionType.SIGNAL
    assert signal_engine.evaluate("GATEUSDT", htf, ltf, PARAMS,
                                  market_bias="neutral").decision is DecisionType.SIGNAL


def test_market_gate_disabled_passes():
    htf, ltf = _long_scenario()
    p = PARAMS.model_copy(update={"market_gate": False})
    d = signal_engine.evaluate("GATEUSDT", htf, ltf, p, market_bias="bear")
    assert d.decision is DecisionType.SIGNAL


def test_rr_max_rejects_tight_stop_plans():
    htf, ltf = _long_scenario()
    p = PARAMS.model_copy(update={"rr_max": 0.5})   # her plani tavana takar
    d = signal_engine.evaluate("TIGHTUSDT", htf, ltf, p)
    assert d.decision is DecisionType.NO_TRADE
    assert "RISK_REWARD_MAX" in d.failed_filters
    assert "max" in d.reject_reason
