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


# ------------------------------------- v3.6 duzeltme: kume etiketi kurtarma
def test_cluster_backfill_matches_live_labeling(tmp_path):
    """Geriye donuk etiket, canli yolun urettigi etiketle AYNI olmali."""
    tracker, db = _make_tracker(tmp_path)
    d = _signal()
    ltf = fx.make_series(np.full(70, 101.5))
    ltf.candles[-1].ts = 1_000_000_000
    tracker.maybe_track(d, ltf)
    live = db.query_one("SELECT cluster_id FROM signals")["cluster_id"]
    # etiketi sil -> eski/gist kaydini taklit et
    db.execute("UPDATE signals SET cluster_id=NULL")
    assert tracker._backfill_cluster_ids() == 1
    assert db.query_one("SELECT cluster_id FROM signals")["cluster_id"] == live


def test_cluster_backfill_uses_created_utc_when_no_candle_ts(tmp_path):
    tracker, db = _make_tracker(tmp_path)
    db.execute(
        "INSERT INTO signals(pair,direction,created_utc,entry_min,entry_max,"
        "stop_loss,tp1,tp2,rr) VALUES('XUSDT','SHORT','2026-07-30T09:00:00Z',"
        "10,11,12,8,7,2.0)")
    assert tracker._backfill_cluster_ids() == 1
    cid = db.query_one("SELECT cluster_id FROM signals")["cluster_id"]
    from app.services.signal_tracker import _cluster_key
    ms = 1785402000000  # 2026-07-30T09:00:00Z
    assert cid == _cluster_key("SHORT", ms) and cid.startswith("S")


def test_cluster_backfill_idempotent_and_skips_timeless(tmp_path):
    tracker, db = _make_tracker(tmp_path)
    db.execute(
        "INSERT INTO signals(pair,direction,created_utc,entry_candle_ts) "
        "VALUES('AUSDT','LONG','2026-07-30T09:00:00Z',1785402000000)")
    db.execute("INSERT INTO signals(pair,direction) VALUES('BUSDT','LONG')")
    assert tracker._backfill_cluster_ids() == 1      # zamansiz kayit atlanir
    assert tracker._backfill_cluster_ids() == 0      # ikinci tur: is yok
    left = db.query_one("SELECT cluster_id FROM signals WHERE pair='BUSDT'")
    assert left["cluster_id"] is None                # uydurma etiket yok


def test_unlabeled_rows_excluded_not_counted_as_clusters(tmp_path):
    """Etiketsiz kayit 'kendi basina kume' SAYILMAZ; sayisi raporlanir."""
    tracker, db = _make_tracker(tmp_path)
    for i in range(3):
        db.execute(
            "INSERT INTO signals(pair,direction,created_utc,entry_min,"
            "entry_max,stop_loss,tp1,tp2,rr,status,outcome,fill_price,"
            "r_multiple,closed_utc,blocked) VALUES(?,'LONG',"
            "'2026-07-30T09:00:00Z',100,101,98,106,110,2.0,'CLOSED','WIN',"
            "101,1.67,'2026-07-30T12:00:00Z',0)", (f"P{i}USDT",))
    db.execute("UPDATE signals SET cluster_id=NULL")   # etiketleri sil
    m = tracker.stats()["measurement"]
    assert m["unclustered_excluded"] == 3
    assert m["bootstrap_all"] is None                 # gecerli kume yok
    assert m["faz1"]["clusters_since_lock"] == 0
    assert m["faz1"]["gate_met"] is False
    # etiketler geri kazanilinca: 3 islem TEK kumede toplanir (ayni 4H, LONG)
    tracker._backfill_cluster_ids()
    m2 = tracker.stats()["measurement"]
    assert m2["unclustered_excluded"] == 0
    assert m2["bootstrap_all"]["n_clusters"] == 1
    assert m2["bootstrap_all"]["n_trades"] == 3


def test_mfe_mae_ignores_pre_fill_candles_on_reevaluation(tmp_path):
    """Onceki turda dolan sinyal yeniden degerlendirilince, dolus ONCESI
    mumlar MFE/MAE'ye karismamali (v3.6 duzeltmesi)."""
    tracker, db = _make_tracker(tmp_path)
    d = _signal()                       # LONG, entry 100-101, stop 98
    ltf = fx.make_series(np.full(70, 101.5))
    ltf.candles[-1].ts = 1_000_000
    tracker.maybe_track(d, ltf)
    # 1. tur: bar0 dolusu tetiklemez (yuksek), bar1 doldurur
    _feed(tracker, closes=[103.0, 100.8],
          lows=[102.5, 100.5], highs=[104.9, 101.2], start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")
    row = db.query_one("SELECT * FROM signals")
    assert row["status"] == "FILLED" and row["fill_ts"] == 1_900_000
    # 2. tur: yeni mum eklenip yeniden degerlendirilir. bar0'in 104.9
    # tepesi dolustan ONCE oldugu icin MFE'ye girmemeli.
    _feed(tracker, closes=[103.0, 100.8, 102.0],
          lows=[102.5, 100.5, 101.5], highs=[104.9, 101.2, 102.6],
          start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")
    row = db.query_one("SELECT * FROM signals")
    # dolus 101, risk 3 -> dogru MFE (102.6-101)/3 = 0.533
    # hatali olsaydi (104.9-101)/3 = 1.30 cikardi
    assert abs(row["mfe_r"] - 0.533) < 0.01
    assert row["mfe_r"] < 1.0


def test_backup_restore_preserves_measurement_columns(tmp_path):
    """Yedek->restore turunda olcum verisi kaybolmamali (v3.6 kapatilan delik).

    Bu kolonlar payload'a girmezse her yeniden baslatmada SESSIZCE silinir
    ve yeniden uretilemez (mumlar arsivden dusmus olabilir).
    """
    from app.services.database import Database
    from app.services.signal_tracker import SignalTracker
    db = Database(str(tmp_path / "a.db"))
    tr = SignalTracker(db, "15")
    db.execute(
        "INSERT INTO signals(pair,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,outcome,fill_price,"
        "r_multiple,closed_utc,fill_ts,ambiguous,mfe_r,mae_r,hypo_r,hypo_done,"
        "nf_gap_r,nf_touch_bars,nf_crossed,nf_done,funding_r_real,funding_done)"
        " VALUES('AUSDT','LONG','2026-07-30T09:00:00Z',1785402000000,100,101,"
        "98,106,110,2.0,'CLOSED','WIN',101,1.67,'2026-07-30T12:00:00Z',"
        "1785402900000,1,1.8,0.4,2.1,1,0.05,3,1,1,0.007,1)")
    payload = tr.recent_signals(500)
    db2 = Database(str(tmp_path / "b.db"))
    tr2 = SignalTracker(db2, "15")
    assert tr2.import_signals(payload) == 1
    a, b = payload[0], tr2.recent_signals(1)[0]
    for k in ("fill_ts", "ambiguous", "mfe_r", "mae_r", "hypo_r", "hypo_done",
              "nf_gap_r", "nf_touch_bars", "nf_crossed", "nf_done",
              "funding_r_real", "funding_done", "r_multiple", "outcome"):
        assert a[k] == b[k], f"{k} restore'da kayboldu: {a[k]} != {b[k]}"


def test_blocked_cohort_backup_carries_measurement_columns(tmp_path):
    tracker, db = _make_tracker(tmp_path)
    db.execute(
        "INSERT INTO signals(pair,direction,created_utc,blocked,mfe_r,hypo_r,"
        "nf_gap_r,funding_r_real) VALUES('BUSDT','SHORT',"
        "'2026-07-30T09:00:00Z',1,0.9,1.2,0.03,-0.004)")
    row = tracker.blocked_signals(10)[0]
    for k in ("mfe_r", "hypo_r", "nf_gap_r", "funding_r_real", "fill_ts",
              "nf_done", "funding_done"):
        assert k in row, k
    assert row["mfe_r"] == 0.9 and row["funding_r_real"] == -0.004


def test_pre_fill_candles_cannot_decide_outcome(tmp_path):
    """UYDURMA WIN testi (v3.6-kritik): fiyat once TP'ye kosar, sonra
    giris bolgesine iner. Dolus o inisde olur. Dolus ONCESI TP dokunusu
    kazanc sayilmamali - o hareketi kacirmisiz demektir.

    Gercek olay: ELSAUSDT #390 (08-03). Duzeltmeden once WIN +1.58R yazildi.
    """
    tracker, db = _make_tracker(tmp_path)
    d = _signal()                    # LONG entry 100-101, stop 98, tp1 106
    ltf = fx.make_series(np.full(70, 108.0))
    ltf.candles[-1].ts = 1_000_000
    tracker.maybe_track(d, ltf)
    # 1. tur: fiyat TP1'in USTUNDE gezinir, bolgeye inmez -> dolus YOK
    _feed(tracker, closes=[107.5, 107.0], lows=[107.0, 106.5],
          highs=[108.5, 107.4], start_ts=1_000_000)   # high 108.5 > tp1 106
    tracker.evaluate_open("TESTUSDT")
    row = db.query_one("SELECT * FROM signals")
    assert row["status"] == "PENDING" and row["outcome"] is None

    # 2. tur: cakilir, bolgeye girer -> dolus 101 (stop 98'e degmedi)
    _feed(tracker, closes=[107.5, 107.0, 100.5],
          lows=[107.0, 106.5, 99.5], highs=[108.5, 107.4, 107.0],
          start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")
    row = db.query_one("SELECT * FROM signals")
    assert row["status"] == "FILLED" and row["fill_ts"] == 2_800_000
    # dolus mumunun tepesi 107 > tp1 ama bu DOLUS ONCESI degil, ayni mum.
    # Muhafazakar davranis: ayni mumda hem tepe hem bolge -> yol bilinemez;
    # burada stop'a deginmediginden WIN yazilabilir. Asil kontrol asagida:
    assert row["outcome"] in (None, "WIN")

    # 3. tur (ASIL TEST): dolus AYRI bir turda kaydedilmeli ki sonraki
    # degerlendirmede fill_price DB'den gelsin ve dongu bastan tarasin -
    # hatanin gercek kosulu budur.
    db.execute("DELETE FROM signals")
    ltf2 = fx.make_series(np.full(70, 108.0)); ltf2.candles[-1].ts = 5_000_000
    tracker.maybe_track(_signal(), ltf2)
    # tur A: TP1'in uzerinde gezinir, bolgeye inmez -> dolus yok
    _feed(tracker, closes=[107.0, 107.0], lows=[106.0, 106.0],
          highs=[110.0, 107.5], start_ts=5_000_000)   # 110 > tp1 106
    tracker.evaluate_open("TESTUSDT")
    assert db.query_one("SELECT * FROM signals")["status"] == "PENDING"
    # tur B: bolgeye iner -> dolus DB'ye yazilir (bu turda filled_at_idx set)
    _feed(tracker, closes=[107.0, 107.0, 100.8],
          lows=[106.0, 106.0, 100.0], highs=[110.0, 107.5, 101.5],
          start_ts=5_000_000)
    tracker.evaluate_open("TESTUSDT")
    row = db.query_one("SELECT * FROM signals")
    assert row["status"] == "FILLED" and row["outcome"] is None
    # tur C: yeni mum gelir, YENIDEN degerlendirilir. Artik fill_price
    # DB'den okunur, filled_at_idx=None, dongu 0. mumdan baslar.
    # HATALI kodda 0. mumun 110 tepesi TP sayilip WIN yazilirdi.
    _feed(tracker, closes=[107.0, 107.0, 100.8, 100.6],
          lows=[106.0, 106.0, 100.0, 100.2],
          highs=[110.0, 107.5, 101.5, 100.9], start_ts=5_000_000)
    tracker.evaluate_open("TESTUSDT")
    row = db.query_one("SELECT * FROM signals")
    assert row["outcome"] is None, f"uydurma sonuc yazildi: {row['outcome']}"
    assert row["status"] == "FILLED"


def test_repair_reopens_contaminated_outcomes(tmp_path):
    """Onarim: dolus oncesi TP dokunusuyla kapatilmis kayit geri acilir;
    temiz kayda dokunulmaz; mumu olmayan kayit '2' ile isaretlenir."""
    tracker, db = _make_tracker(tmp_path)
    base = "INSERT INTO signals(pair,direction,created_utc,entry_candle_ts," \
           "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,outcome," \
           "fill_price,exit_price,r_multiple,closed_utc,fill_ts,blocked) " \
           "VALUES(?,'LONG','2026-08-01T00:00:00Z',?,100,101,98,106,110,2.0," \
           "'CLOSED','WIN',101,106,1.67,'2026-08-01T04:00:00Z',?,0)"
    db.execute(base, ("KIRLIUSDT", 1_000_000, 2_800_000))   # gecikmeli dolus
    db.execute(base, ("TEMIZUSDT", 1_000_000, 2_800_000))
    db.execute(base, ("MUMSUZUSDT", 1_000_000, 2_800_000))
    # KIRLI: dolus oncesi mumda TP'ye degmis (uydurma WIN)
    for ts, hi in ((1_000_000, 107.0), (1_900_000, 103.0)):
        db.execute("INSERT INTO candles(symbol,interval,ts,open,high,low,"
                   "close,volume) VALUES('KIRLIUSDT','15',?,102,?,101.5,102,1)",
                   (ts, hi))
    # TEMIZ: dolus oncesi ne TP ne STOP
    for ts in (1_000_000, 1_900_000):
        db.execute("INSERT INTO candles(symbol,interval,ts,open,high,low,"
                   "close,volume) VALUES('TEMIZUSDT','15',?,102,103,101.5,"
                   "102,1)", (ts,))
    assert tracker._repair_prefill_outcomes() == 1
    kirli = db.query_one("SELECT * FROM signals WHERE pair='KIRLIUSDT'")
    temiz = db.query_one("SELECT * FROM signals WHERE pair='TEMIZUSDT'")
    mumsuz = db.query_one("SELECT * FROM signals WHERE pair='MUMSUZUSDT'")
    assert kirli["outcome"] is None and kirli["status"] == "FILLED"
    assert kirli["r_multiple"] is None and kirli["prefill_repaired"] == 1
    assert temiz["outcome"] == "WIN" and temiz["prefill_repaired"] == 1
    assert mumsuz["outcome"] == "WIN" and mumsuz["prefill_repaired"] == 2
    assert tracker._repair_prefill_outcomes() == 0     # idempotent
