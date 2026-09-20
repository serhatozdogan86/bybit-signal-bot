"""SAMPIYON ve ADAYLAR ayni olcum nufusunu kullanir (2026-09-20 bulgusu).

BULGU: challengers.stats() kendi notunda "sampiyonla ayni kume-CI
standardi, ayni 50-kume esigi" diyordu ama DEGILDI:
  sampiyon : outcome IN ('WIN','LOSS')            -> EXPIRED DISARIDA
  adaylar  : outcome IN ('WIN','LOSS','EXPIRED')  -> EXPIRED ICERIDE

Olculen etki (09-20): S11 91 kume / 42 karar -> orneklemin yarisindan
fazlasi EXPIRED. Aday kohortlari 50-kume kapisina sampiyondan CABUK
variyordu.

NEDEN "ICERIDE" DOGRU OLAN: EXPIRED, sure dolunca GERCEK bir fiyattan
kapanan GERCEK bir pozisyondur ve gercek bir R uretir; o parayi
kazanir ya da kaybedersin. Dahasi bazi adaylarda (S12: TP_RISK=100,
yani hedefsiz) zaman-cikisi motorun ASIL cikis bicimidir - onu atmak
stratejinin ana sonucunu defterden silmek olurdu. Korelasyon aleti de
(correlation.py) sampiyonun EXPIRED'ini zaten sayiyordu; tutarsiz olan
TEK yer sampiyonun stats()'iydi.

Bu testler o sinifi kapatir: duzeltmeden ONCE kirmizi verirler.
"""
from __future__ import annotations

from app.services import measurement
from app.services.signal_tracker import cost_r
from tests.test_signal_tracker import _make_tracker


def _closed(db, pair, outcome, r_mult, cid, created="2026-08-20T00:00:00Z"):
    """Kapanmis bir sampiyon kaydi ekle (kilit penceresi icinde)."""
    db.execute(
        "INSERT INTO signals(pair,direction,created_utc,closed_utc,status,"
        "outcome,entry_min,entry_max,stop_loss,fill_price,r_multiple,"
        "cluster_id,blocked,market_bias) VALUES(?,'LONG',?,?,'CLOSED',?,"
        "100.0,100.0,98.0,100.0,?,?,0,'bull')",
        (pair, created, "2026-08-20T06:00:00Z", outcome, r_mult, cid))


# ------------------------------------------------------- ortak sozlesme
def test_measured_outcomes_is_a_single_shared_constant():
    """Olcum nufusu TEK yerde tanimli olmali - iki taraf ayrisamasin."""
    assert measurement.MEASURED_OUTCOMES == ("WIN", "LOSS", "EXPIRED")


def test_champion_and_challenger_use_the_same_cohort():
    """Iki taraf da AYNI sabiti kullanir (kod duzeyinde baglanti)."""
    from app.services import challengers
    assert challengers.MEASURED_OUTCOMES is measurement.MEASURED_OUTCOMES


# ------------------------------------------------------ davranis: maliyet
def test_cost_is_computed_for_expired_trades():
    """EXPIRED islemin de maliyeti vardir (giris+cikis ucreti + funding).

    Stop kaymasi YOKTUR - pozisyon stopa carpmadi, sure doldu."""
    row = {"outcome": "EXPIRED", "direction": "LONG", "fill_price": 100.0,
           "entry_min": 100.0, "entry_max": 100.0, "stop_loss": 98.0,
           "created_utc": "2026-08-20T00:00:00Z",
           "closed_utc": "2026-08-20T06:00:00Z"}
    cost = cost_r(row)
    assert cost is not None and cost > 0
    # ayni kayit LOSS olsaydi stop kaymasi eklenir, maliyet ARTARDI
    loss = cost_r({**row, "outcome": "LOSS"})
    assert loss > cost
    # NOT_FILLED hic acilmamis pozisyondur - maliyeti YOKTUR
    assert cost_r({**row, "outcome": "NOT_FILLED"}) is None


# --------------------------------------------- davranis: kume/CI/faz1
def test_expired_trades_count_toward_clusters_and_faz1(tmp_path):
    """EXPIRED kayitlar sampiyonun kume sayisina ve Faz-1 kapisina GIRER.

    Bu testin duzeltme ONCESI kirmizi vermesi gerekir: eski kod EXPIRED'i
    tumuyle disarida birakiyordu."""
    tracker, db = _make_tracker(tmp_path)
    _closed(db, "AUSDT", "WIN", 1.0, "L100")
    _closed(db, "BUSDT", "EXPIRED", 0.4, "L101")
    _closed(db, "CUSDT", "EXPIRED", -0.3, "L102")
    meas = tracker.stats()["measurement"]
    assert meas["faz1"]["clusters_since_lock"] == 3      # eski kod: 1
    assert meas["bootstrap_since_lock"]["n_trades"] == 3


def test_expired_trades_count_toward_max_drawdown(tmp_path):
    """maksDD de EXPIRED'i gorur - yanlislama #2 ayni nufustan okunur."""
    tracker, db = _make_tracker(tmp_path)
    _closed(db, "AUSDT", "EXPIRED", -5.0, "L200")
    assert tracker.max_drawdown_r() > 0                  # eski kod: 0.0


def test_expired_trades_appear_in_anatomy(tmp_path):
    """Anatomi raporu da ayni nufusu kullanir (tek gercek kaynak)."""
    tracker, db = _make_tracker(tmp_path)
    _closed(db, "AUSDT", "WIN", 1.0, "L300")
    _closed(db, "BUSDT", "EXPIRED", 0.5, "L301")
    assert tracker.anatomy_report()["trades"] == 2       # eski kod: 1


def test_not_filled_still_excluded_everywhere(tmp_path):
    """DOLMAYAN kayit hicbir yerde sayilmaz - hic pozisyon acilmadi.

    Bu, duzeltmenin fazla genis olmadiginin kanitidir: kapiyi yalniz
    EXPIRED'e actik, herkese degil."""
    tracker, db = _make_tracker(tmp_path)
    _closed(db, "AUSDT", "WIN", 1.0, "L400")
    _closed(db, "BUSDT", "NOT_FILLED", None, "L401")
    _closed(db, "CUSDT", "AMBIGUOUS", 0.2, "L402")
    meas = tracker.stats()["measurement"]
    assert meas["faz1"]["clusters_since_lock"] == 1
    assert tracker.anatomy_report()["trades"] == 1
