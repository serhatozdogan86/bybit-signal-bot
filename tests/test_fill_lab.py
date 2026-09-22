"""Dolum laboratuvari - degismezlik testleri.

En kritikleri:
- test_prereg_constants_are_frozen: esikler ON-KAYITTAN gelir; sonradan
  "biraz indirelim" yolunu kapatir.
- test_negative_penetration_is_reported_not_dropped: imkansiz kayit
  SESSIZCE atilmaz (v3.6 dersi: sessiz kayip = sisik istatistik).
"""
from __future__ import annotations

from app.services import fill_lab


def _row(rid, direction="LONG", edge=100.0, ts=1000, pair="BTCUSDT"):
    return {"id": rid, "pair": pair, "direction": direction, "fill_ts": ts,
            "entry_max": edge if direction == "LONG" else None,
            "entry_min": None if direction == "LONG" else edge}


def _bars(mapping):
    """(pair,ts) -> {'low':..,'high':..} sozlugunden bar_lookup uretir."""
    return lambda p, t: mapping.get((p, t))


# ------------------------------------------------------------ on-kayit
def test_prereg_constants_are_frozen():
    """Esikler docs/ideas.md H-FILL'den; sonradan oynatilamaz."""
    assert fill_lab.SAFE_BPS == 5.0
    assert fill_lab.MIN_FILLS == 200
    assert fill_lab.SAFE_SHARE == 0.90
    assert fill_lab.SINIFLAR == ("GUVENLI", "SINIRDA", "VERI_HATASI")


def test_verdict_ladder_matches_prereg():
    """DESTEKLENDI = >=200 islem VE >=%90 guvenli. Kenar durumlar dahil."""
    assert fill_lab.verdict(199, 199) == "ORNEKLEM YETERSIZ (hukum yok)"
    assert fill_lab.verdict(200, 180) == "DESTEKLENDI"        # tam %90
    assert fill_lab.verdict(200, 179) == "DESTEKLENMEDI"      # %89.5
    assert fill_lab.verdict(1000, 1000) == "DESTEKLENDI"


# ------------------------------------------------------- gecis derinligi
def test_long_penetration_uses_bar_low():
    """LONG'da emir entry_max'ta dinlenir; mumun DIBI ne kadar altina
    indiyse o kadar derin gecmistir."""
    # kenar 100, dip 99.9 -> 0.1/100 = 10 bps
    assert fill_lab.penetration_bps("LONG", 100.0, 99.9, 101.0) == 10.0
    # tam degip dondu -> 0 bps
    assert fill_lab.penetration_bps("LONG", 100.0, 100.0, 101.0) == 0.0


def test_short_penetration_uses_bar_high():
    """SHORT'ta emir entry_min'de dinlenir; mumun TEPESI olculur."""
    assert fill_lab.penetration_bps("SHORT", 100.0, 99.0, 100.1) == 10.0
    assert fill_lab.penetration_bps("SHORT", 100.0, 99.0, 100.0) == 0.0


def test_classification_threshold_is_exact():
    """5.0 bps SINIRIN KENDISI GUVENLI sayilir (>=), altindaki degil."""
    assert fill_lab.classify(5.0) == "GUVENLI"
    assert fill_lab.classify(4.99) == "SINIRDA"
    assert fill_lab.classify(0.0) == "SINIRDA"
    assert fill_lab.classify(None) is None


def test_negative_penetration_is_reported_not_dropped():
    """bps < 0 = kayit dolmamis olmaliydi. SESSIZCE ATILMAZ.

    Sessiz kayip, istatistigi sisiren en sinsi hatadir (v3.6 dersi:
    kumesiz kayitlar). Boyle bir kayit VERI_HATASI olarak SAYILIR ve
    raporda gorunur."""
    assert fill_lab.classify(-3.0) == "VERI_HATASI"
    rows = [_row(1), _row(2)]
    bars = _bars({("BTCUSDT", 1000): {"low": 100.5, "high": 101.0}})
    rep = fill_lab.build_report(rows, bars)
    assert rep["counts"]["VERI_HATASI"] == 2
    assert rep["fills_measured"] == 2


# ------------------------------------------------------------- rapor
def test_report_counts_and_share():
    rows = [_row(i, ts=1000 + i) for i in range(4)]
    bars = _bars({
        ("BTCUSDT", 1000): {"low": 99.0, "high": 101.0},    # 100 bps GUVENLI
        ("BTCUSDT", 1001): {"low": 99.95, "high": 101.0},   # 5 bps  GUVENLI
        ("BTCUSDT", 1002): {"low": 99.99, "high": 101.0},   # 1 bps  SINIRDA
        ("BTCUSDT", 1003): {"low": 100.0, "high": 101.0},   # 0 bps  SINIRDA
    })
    rep = fill_lab.build_report(rows, bars)
    assert rep["counts"] == {"GUVENLI": 2, "SINIRDA": 2, "VERI_HATASI": 0}
    assert rep["safe_share"] == 0.5
    assert rep["verdict"] == "ORNEKLEM YETERSIZ (hukum yok)"   # 4 < 200
    assert rep["penetration_bps"]["median"] is not None


def test_missing_bars_are_counted_not_silently_skipped():
    """Mumu bulunamayan kayit ayrica sayilir - sessiz kayip yok."""
    rows = [_row(1, ts=1000), _row(2, ts=9999)]
    bars = _bars({("BTCUSDT", 1000): {"low": 99.0, "high": 101.0}})
    rep = fill_lab.build_report(rows, bars)
    assert rep["fills_measured"] == 1
    assert rep["bars_missing"] == 1


def test_report_carries_limitation_and_locked_model_note():
    """Iki uyari rapordan SILINEMEZ: kuyruk sinirlamasi + model kilidi."""
    rep = fill_lab.build_report([], _bars({}))
    assert "KUYRUK" in rep["limitation"]
    assert "KILITLI" in rep["if_supported"].upper()
    assert "ACILMAZ" in rep["if_supported"]
    assert rep["prereg"]["safe_bps"] == fill_lab.SAFE_BPS


def test_empty_book_gives_no_verdict():
    rep = fill_lab.build_report([], _bars({}))
    assert rep["fills_measured"] == 0
    assert rep["safe_share"] is None
    assert rep["verdict"] == "ORNEKLEM YETERSIZ (hukum yok)"
