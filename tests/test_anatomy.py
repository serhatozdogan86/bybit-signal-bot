"""Olum sonrasi anatomi aleti - degismezlik testleri.

En onemlisi test_anatomy_sections_are_declared: raporun bolum listesi
DONMUSTUR. Yeni bolum eklemek = veriye yeni bir soru sormak; Kural 5
bunu on-ilan olmadan yasaklar. Test, sessizce bolum eklenmesini kirar.
"""
from __future__ import annotations

from app.services import anatomy, measurement


def _row(rid, direction, cid, r_mult, *, pair="BTCUSDT", bias="BULL",
         entry=100.0, stop=98.0, created="2026-08-20T00:00:00Z",
         outcome=None):
    return {
        "id": rid, "direction": direction, "cluster_id": cid,
        "r_multiple": r_mult, "pair": pair, "market_bias": bias,
        "fill_price": entry, "entry_min": entry, "entry_max": entry,
        "stop_loss": stop, "created_utc": created,
        "closed_utc": "2026-08-20T06:00:00Z",
        "outcome": outcome or ("WIN" if r_mult > 0 else "LOSS"),
    }


def _cost(_r):
    return 0.10          # sabit maliyet: aritmetigi elle dogrulanabilir yapar


# --------------------------------------------------------------- Kural 5
def test_anatomy_sections_are_declared():
    """Bolumler sabit; sessizce yeni soru sorulamaz (p-hacking kapisi)."""
    assert anatomy.SECTIONS == ("by_direction", "by_regime", "cost",
                                "concentration")
    rep = anatomy.build_report([_row(1, "LONG", "L1", 1.0)], _cost)
    for s in anatomy.SECTIONS:
        assert s in rep
    # rapor, ILAN EDILEN bolumlerin DISINDA bir analiz bolumu tasimaz
    extra = set(rep) - set(anatomy.SECTIONS) - {
        "note", "window", "lock_utc", "trades", "min_clusters_for_claim",
        "reading_warning"}
    assert extra == set(), f"ilan edilmemis bolum: {extra}"


def test_small_subgroup_is_never_called_evidence():
    """3 kumelik bir alt grup carpici gorunse bile KANIT sayilmaz.

    Bu, raporun en kritik davranisi: 'SHORT artida' okumasinin kendi
    basina hukum olmasini engeller (secici okuma / alt-grup tuzagi)."""
    rows = [_row(i, "SHORT", f"S{i}", 5.0) for i in range(3)]
    rep = anatomy.build_report(rows, _cost)
    short = rep["by_direction"]["SHORT"]
    assert short["net_r"] > 0                      # gorunuste harika
    assert short["clusters"] < anatomy.MIN_CLUSTERS_FOR_CLAIM
    assert short["claim"] == "ORNEKLEM YETERSIZ (kanit degil)"


def test_direction_split_uses_cluster_ci_not_trade_ci():
    """Alt grup ozeti resmi standarda (kume-blok bootstrap) uyar."""
    rows = ([_row(i, "LONG", f"L{i}", -1.0) for i in range(60)]
            + [_row(100 + i, "SHORT", f"S{i}", 1.0) for i in range(60)])
    rep = anatomy.build_report(rows, _cost)
    lng, sht = rep["by_direction"]["LONG"], rep["by_direction"]["SHORT"]
    assert lng["clusters"] == 60 and sht["clusters"] == 60
    assert lng["ci"] is not None and lng["ci"][1] < 0      # CI ust < 0
    assert lng["claim"] == "KANITLI EKSI (CI ust < 0)"
    assert sht["claim"] == "KANITLI ARTI (CI alt > 0)"
    # maliyet her iki tarafta da dusulmus olmali (net < brut)
    assert sht["net_r"] < sht["gross_r"]


def test_cost_flags_gross_positive_net_negative():
    """Projenin en pahali dersi tek bayrakta: ham arti, net eksi."""
    # brut +1.0 toplam; 20 islem x 0.10 maliyet = 2.0 -> net -1.0
    rows = [_row(i, "LONG", f"L{i}", 0.05) for i in range(20)]
    rep = anatomy.build_report(rows, _cost)
    c = rep["cost"]
    assert c["gross_r"] > 0 and c["net_r"] < 0
    assert c["gross_positive_net_negative"] is True
    assert c["cost_per_trade"] == 0.1
    assert c["over_budget"] is True                # 0.10 > 0.05 butcesi


def test_cost_budget_boundary_is_not_over():
    """Butce SINIRI ihlal degildir (<= 0.05R kuralı); kenar durum."""
    rep = anatomy.build_report([_row(1, "LONG", "L1", 1.0)],
                               lambda _r: 0.05)
    assert rep["cost"]["cost_per_trade"] == 0.05
    assert rep["cost"]["over_budget"] is False


def test_window_excludes_pre_lock_rows():
    """KILIT-2 oncesi kayitlar kilit penceresine SIZAMAZ."""
    rows = [_row(1, "LONG", "L1", 1.0, created="2026-07-01T00:00:00Z"),
            _row(2, "LONG", "L2", 1.0, created="2026-08-20T00:00:00Z")]
    assert anatomy.build_report(rows, _cost)["trades"] == 1
    assert anatomy.build_report(rows, _cost, since_lock=False)["trades"] == 2
    assert measurement.ACTIVE_LOCK_UTC.startswith("2026-08-13")


def test_unclustered_rows_do_not_inflate_evidence():
    """Kumesiz kayit bagimsiz kanit sayisini sisirmez (v3.6 dersi)."""
    rows = [_row(1, "LONG", "L1", 1.0), _row(2, "LONG", None, 1.0)]
    d = anatomy.build_report(rows, _cost)["by_direction"]["LONG"]
    assert d["clusters"] == 1 and d["trades"] == 1


def test_concentration_reports_worst_without_recommending():
    """En kotu kumeler raporlanir ama bir kural ONERISI olarak degil."""
    rows = ([_row(i, "LONG", f"L{i}", 0.5) for i in range(10)]
            + [_row(99, "LONG", "BAD", -30.0)])
    con = anatomy.build_report(rows, _cost)["concentration"]
    assert con["worst_clusters"][0]["cluster_id"] == "BAD"
    assert con["net_r"] < 0 < con["net_r_without_worst"]
    # oneri olmadigi RAPORDA yazili olmali (okuyan yanlis anlamasin)
    assert "ON-KAYIT" in con["note"] and "DEGILDIR" in con["note"]


def test_regime_split_ignores_unlabeled_rows():
    """market_bias etiketi olmayan kayit rejim kirilimina girmez."""
    rows = [_row(1, "LONG", "L1", 1.0, bias="BULL"),
            _row(2, "LONG", "L2", 1.0, bias=None)]
    reg = anatomy.build_report(rows, _cost)["by_regime"]
    assert set(reg) == {"BULL"}


def test_report_carries_reading_warning():
    """Alt-grup tuzagi uyarisi rapordan SILINEMEZ (okuyan insan icin)."""
    rep = anatomy.build_report([_row(1, "LONG", "L1", 1.0)], _cost)
    assert "KANIT DEGILDIR" in rep["reading_warning"]
    assert "ON-KAYIT" in rep["note"]
