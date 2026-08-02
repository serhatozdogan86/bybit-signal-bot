"""v3.6 Olcum Paketi testleri - bootstrap, NF anatomisi, MFE/MAE, permutasyon."""
from __future__ import annotations

import numpy as np

from app.services import measurement
from app.services.database import Database
from app.services.signal_tracker import SignalTracker
from tests import fixtures as fx
from tests.test_signal_tracker import _feed, _make_tracker, _signal


# ------------------------------------------------------------- bootstrap
def test_cluster_bootstrap_deterministic_and_sane():
    clusters = {"L1": [0.5, -1.0, 2.0], "L2": [-1.0, -1.0],
                "S1": [2.2, 1.8, -1.0], "S2": [0.3]}
    a = measurement.cluster_bootstrap(clusters, n_boot=500, seed=36)
    b = measurement.cluster_bootstrap(clusters, n_boot=500, seed=36)
    assert a == b                                # ayni seed -> ayni CI
    assert a["n_clusters"] == 4 and a["n_trades"] == 9
    assert a["ci_low"] <= a["e_net"] <= a["ci_high"]


def test_cluster_bootstrap_wider_than_trade_level_when_correlated():
    """Kume ici tam bagimlilik: blok CI, islem-duzeyi CI'den dar OLMAMALI."""
    import random
    from statistics import mean
    clusters = {"A": [1.0] * 10, "B": [-1.0] * 10,
                "C": [0.8] * 10, "D": [-0.6] * 10}
    blok = measurement.cluster_bootstrap(clusters, n_boot=800, seed=7)
    # islem-duzeyi naif bootstrap (kiyas icin)
    flat = [x for v in clusters.values() for x in v]
    rng = random.Random(7)
    means = sorted(mean(rng.choices(flat, k=len(flat))) for _ in range(800))
    naive_width = means[779] - means[20]
    blok_width = blok["ci_high"] - blok["ci_low"]
    assert blok_width >= naive_width  # otokorelasyon CI'yi genisletir


def test_cluster_bootstrap_degenerate():
    assert measurement.cluster_bootstrap({}) is None
    one = measurement.cluster_bootstrap({"A": [1.0, 2.0]})
    assert one["ci_low"] is None and "tek kume" in one["note"]


# --------------------------------------------------------- NF anatomisi
def _nf_sig(direction="LONG"):
    return {"direction": direction, "entry_min": 100.0, "entry_max": 101.0,
            "stop_loss": 98.0 if direction == "LONG" else 103.0}


def test_nf_anatomy_gap_touch_crossed():
    sig = _nf_sig()          # kenar 101, risk 3
    # pencere (3 bar): low'lar 101.9 / 101.05 / 102.5 -> min bosluk 0.05
    window = [{"low": 101.9, "high": 103.0},
              {"low": 101.05, "high": 102.4},   # 0.05 <= %0.1*101 -> temas
              {"low": 102.5, "high": 104.0}]
    later = [{"low": 99.5, "high": 102.0}]      # sonradan uzak kenari gecti
    a = measurement.nf_anatomy(sig, window + later, fill_window=3)
    assert abs(a["gap_r"] - 0.05 / 3.0) < 1e-3
    assert a["touch_bars"] == 1
    assert a["crossed"] == 1
    # gecis olmadan
    b = measurement.nf_anatomy(sig, window, fill_window=3)
    assert b["crossed"] == 0


def test_nf_anatomy_short_side():
    sig = _nf_sig("SHORT")   # kenar 100, risk 3
    candles = [{"low": 97.0, "high": 99.7},
               {"low": 96.0, "high": 98.0}]
    a = measurement.nf_anatomy(sig, candles, fill_window=2)
    assert abs(a["gap_r"] - 0.3 / 3.0) < 1e-3 and a["crossed"] == 0


# --------------------------------------------- kaymali hayalet R ozeti
def test_hypo_slip_summary_reduces_ideal():
    rows = [{"direction": "LONG", "entry_min": 100.0, "entry_max": 101.0,
             "stop_loss": 98.0, "hypo_r": 2.0},
            {"direction": "SHORT", "entry_min": 50.0, "entry_max": 51.0,
             "stop_loss": 52.5, "hypo_r": 1.5}]
    s = measurement.hypo_slip_summary(rows)
    assert s["n"] == 2 and s["sum_r_ideal"] == 3.5
    assert (s["sum_r_slip_10bps"] > s["sum_r_slip_30bps"]
            > s["sum_r_slip_50bps"])
    assert s["sum_r_slip_10bps"] < s["sum_r_ideal"]


# -------------------------------------------------------- permutasyon
def test_permutation_pvalue():
    same = measurement.permutation_pvalue([1, 2, 3, 4], [2, 3, 1, 4])
    assert same["p_value"] > 0.5                 # ayirt edici bilgi yok
    apart = measurement.permutation_pvalue(
        [5.0] * 8, [-5.0] * 8)
    assert apart["p_value"] < 0.05               # net ayrisma
    assert measurement.permutation_pvalue([1, 2], [3, 4, 5]) is None


def test_top_share():
    c = measurement.top_share([10.0, 1.0, 1.0, -2.0])
    assert c["total"] == 10.0 and c["top1_share"] == 1.0
    assert measurement.top_share([-1.0, -2.0])["top1_share"] is None


# ------------------------------------------- tracker entegrasyonlari
def test_mfe_mae_recorded_on_win(tmp_path):
    tracker, db = _make_tracker(tmp_path)
    d = _signal()                                # entry 100-101, stop 98, tp1 106
    ltf = fx.make_series(np.full(70, 101.5))
    ltf.candles[-1].ts = 1_000_000
    tracker.maybe_track(d, ltf)
    # fill @101 (risk 3); bar2 low 99.5 -> MAE 0.5; bar3 high 106.5 -> WIN
    _feed(tracker, closes=[100.8, 100.0, 106.2],
          lows=[100.5, 99.5, 105.5],
          highs=[101.2, 100.6, 106.5], start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")
    row = db.query_one("SELECT * FROM signals ORDER BY id DESC LIMIT 1")
    assert row["outcome"] == "WIN"
    assert abs(row["mae_r"] - 0.5) < 0.01
    assert row["mfe_r"] >= (106.5 - 101.0) / 3.0 - 0.01


def test_nf_anatomy_persisted_after_not_filled(tmp_path):
    tracker, db = _make_tracker(tmp_path, fill_window=3)
    d = _signal()                                # LONG kenar 101
    ltf = fx.make_series(np.full(70, 103.0))
    ltf.candles[-1].ts = 1_000_000
    tracker.maybe_track(d, ltf)
    _feed(tracker, closes=[103.0, 103.5, 104.0, 104.5],
          lows=[101.4, 102.8, 103.2, 103.9],
          highs=[103.5, 104.0, 104.5, 105.0], start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")            # NOT_FILLED + anatomi
    row = db.query_one("SELECT * FROM signals ORDER BY id DESC LIMIT 1")
    assert row["outcome"] == "NOT_FILLED" and row["nf_done"] == 1
    assert abs(row["nf_gap_r"] - 0.4 / 3.0) < 0.01
    assert row["nf_crossed"] == 0


def test_stats_measurement_block(tmp_path):
    tracker, _ = _make_tracker(tmp_path)
    d = _signal()
    ltf = fx.make_series(np.full(70, 101.5))
    ltf.candles[-1].ts = 1_000_000
    tracker.maybe_track(d, ltf)
    _feed(tracker, closes=[100.8, 106.2], lows=[100.5, 105.5],
          highs=[101.2, 106.5], start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")
    m = tracker.stats()["measurement"]
    assert m["faz1"]["target_clusters"] == measurement.FAZ1_TARGET_CLUSTERS
    assert m["bootstrap_all"]["n_trades"] == 1
    assert m["faz1"]["gate_met"] is False        # 1 kume < 50
    assert "not_filled_hypo_slip" in m


def test_diagnostics_shape(tmp_path):
    tracker, _ = _make_tracker(tmp_path)
    d = _signal()
    ltf = fx.make_series(np.full(70, 101.5))
    ltf.candles[-1].ts = 1_000_000
    tracker.maybe_track(d, ltf)
    _feed(tracker, closes=[100.8, 97.5], lows=[100.5, 97.0],
          highs=[101.2, 100.0], start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")
    tracker.log_gate_event("transition", "neutral->bear votes=bear/bear")
    diag = tracker.diagnostics()
    assert diag["per_cluster_pnl"]["clusters"][0]["n"] == 1
    assert diag["gate_log"]["counts"].get("transition") == 1
    for key in ("heat_blocked_cluster_dist", "gate_blocked_regime_dist",
                "pair_concentration", "holding_hours", "mfe_mae",
                "nf_anatomy", "funding_v1_preview"):
        assert key in diag


def test_backfill_funding_uses_real_rates(tmp_path):
    tracker, db = _make_tracker(tmp_path)
    d = _signal()
    ltf = fx.make_series(np.full(70, 101.5))
    ltf.candles[-1].ts = 1_000_000
    tracker.maybe_track(d, ltf)
    _feed(tracker, closes=[100.8, 106.2], lows=[100.5, 105.5],
          highs=[101.2, 106.5], start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")            # WIN, fill_ts=1_000_000

    class FakeMD:
        def get_funding_history(self, symbol, start_ms, end_ms):
            return [{"fundingRate": "0.0002",
                     "fundingRateTimestamp": str(start_ms + 1000)},
                    {"fundingRate": "0.0001",
                     "fundingRateTimestamp": str(end_ms + 999_999)}]  # disarida

    assert tracker.backfill_funding(FakeMD()) == 1
    row = db.query_one("SELECT * FROM signals ORDER BY id DESC LIMIT 1")
    assert row["funding_done"] == 1
    # LONG oder: +0.0002 / stop_frac(3/101) = +0.00673R
    assert abs(row["funding_r_real"] - 0.0067) < 0.0005
