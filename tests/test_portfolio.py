"""Portfoy olcum aleti - degismezlik testleri.

En kritik ikisi:
- test_member_rule_never_reads_returns: uye kurali GETIRIYE BAKMAZ.
- test_same_day_same_direction_merges_into_one_cluster: iki motorun ayni
  gun ayni yondeki islemi TEK bahistir. Bu birlestirme olmazsa portfoy
  sirf ayni bahsi bes kez sayarak yapay daralma uretirdi.
"""
from __future__ import annotations

from app.services import measurement, portfolio

_DAY = 86_400_000


def _row(strategy, direction, day, r_mult, *, outcome=None, regime=2,
         status="CLOSED"):
    return {"strategy": strategy, "direction": direction,
            "entry_ts": day * _DAY + 3_600_000, "r_multiple": r_mult,
            "status": status, "regime": regime,
            "outcome": outcome or ("WIN" if r_mult > 0 else "LOSS")}


def _net(r):
    return r["r_multiple"] - 0.02         # sabit maliyet: elle dogrulanabilir


def _stats(**kw):
    return {"strategies": kw}


# ----------------------------------------------------------- uye kurali
def test_member_rule_never_reads_returns():
    """Kural YALNIZ maliyet + kume sayisi + emeklilik okur.

    Net EKSI olan bir aday, kurali sagliyorsa SECILIR. 'Iyi gorunenleri
    sec' tam olarak kacindigimiz secici okumadir."""
    st = _stats(
        IYI={"cost_per_trade": 0.02, "clusters": 100, "net_r": +50.0},
        KOTU={"cost_per_trade": 0.02, "clusters": 100, "net_r": -50.0},
    )
    assert portfolio.select_members(st) == ["IYI", "KOTU"]


def test_member_rule_excludes_expensive_small_and_retired():
    st = _stats(
        UCUZ={"cost_per_trade": 0.05, "clusters": 60},       # sinir: GIRER
        PAHALI={"cost_per_trade": 0.051, "clusters": 500},   # butce disi
        KUCUK={"cost_per_trade": 0.01, "clusters": 49},      # orneklem az
        EMEKLI={"cost_per_trade": 0.01, "clusters": 500,
                "retired_utc": "2026-08-12"},
        MALIYETSIZ={"cost_per_trade": None, "clusters": 500},
    )
    assert portfolio.select_members(st) == ["UCUZ"]
    # RETIRED sozlugu ile de dislanir (iki kaynak da gecerli)
    st2 = _stats(A={"cost_per_trade": 0.01, "clusters": 500})
    assert portfolio.select_members(st2, {"A": "2026-08-12"}) == []


def test_member_rule_constants_are_declared():
    assert portfolio.MEMBER_MAX_COST_PER_TRADE == 0.05
    assert portfolio.MEMBER_MIN_CLUSTERS == measurement.FAZ1_TARGET_CLUSTERS


# ------------------------------------------------- kume BIRLESTIRME
def test_same_day_same_direction_merges_into_one_cluster():
    """Iki motor ayni gun ayni yonde actiysa TEK bagimsiz bahistir."""
    rows = [_row("A", "LONG", 100, 1.0), _row("B", "LONG", 100, 1.0)]
    rep = portfolio.build_report(rows, ["A", "B"], _net, 2)
    assert rep["clusters"] == 1          # iki motor, TEK blok
    assert rep["trades"] == 2
    assert rep["merged_overlaps"] == 1


def test_opposite_direction_or_other_day_stays_separate():
    rows = [_row("A", "LONG", 100, 1.0),
            _row("B", "SHORT", 100, 1.0),     # ayni gun, TERS yon
            _row("A", "LONG", 101, 1.0)]      # ayni yon, BASKA gun
    rep = portfolio.build_report(rows, ["A", "B"], _net, 2)
    assert rep["clusters"] == 3
    assert rep["merged_overlaps"] == 0


def test_daily_bucket_is_coarser_than_engine_4h_bucket():
    """Gunluk kova KASITLI muhafazakardir: ayni gunun farkli 4s
    dilimlerindeki islemler de TEK bloga duser (daha genis CI)."""
    a = _row("A", "LONG", 100, 1.0)
    b = _row("B", "LONG", 100, 1.0)
    b["entry_ts"] = 100 * _DAY + 20 * 3_600_000      # 19 saat sonra
    rep = portfolio.build_report([a, b], ["A", "B"], _net, 2)
    assert rep["clusters"] == 1


# ------------------------------------------------------- kohort filtresi
def test_only_members_regime_and_measured_outcomes_count():
    rows = [_row("A", "LONG", 100, 1.0),
            _row("YABANCI", "LONG", 101, 5.0),           # uye degil
            _row("A", "LONG", 102, 5.0, regime=1),       # eski rejim
            _row("A", "LONG", 103, 5.0, outcome="NOT_FILLED"),
            _row("A", "LONG", 104, 5.0, status="OPEN")]
    rep = portfolio.build_report(rows, ["A"], _net, 2)
    assert rep["trades"] == 1 and rep["clusters"] == 1


def test_expired_counts_like_everywhere_else():
    """Portfoy de ortak olcum nufusunu kullanir (09-20 birlesimi)."""
    rows = [_row("A", "LONG", 100, 0.5, outcome="EXPIRED")]
    assert portfolio.build_report(rows, ["A"], _net, 2)["trades"] == 1


# ------------------------------------------------------------ planlama
def test_required_clusters_arithmetic():
    """z*sigma/sqrt(n) < e_net -> n. Saf aritmetik, kural DEGIL."""
    # (1.96/0.0292)^2 = 4505.5 -> tam ustu 4506
    assert portfolio.required_clusters(0.0292, 1.0) == 4506
    # kenar durumlar: kenar sifir/eksi ise sayi ANLAMSIZ -> None
    assert portfolio.required_clusters(0.0, 1.0) is None
    assert portfolio.required_clusters(-0.1, 1.0) is None
    assert portfolio.required_clusters(0.05, 0.0) is None


def test_report_carries_verdict_warning_and_rule_flag():
    """Rapor, HUKUM olmadigini kendi icinde yazar (yanlis okunmasin)."""
    rep = portfolio.build_report([_row("A", "LONG", 100, 1.0)], ["A"],
                                 _net, 2)
    assert "GECTI MI" in rep["verdict_warning"]
    assert rep["member_rule"]["reads_returns"] is False


def test_gate_needs_both_clusters_and_positive_ci_low():
    """Kapi: >=50 kume VE CI alt > 0. Tek basina hicbiri yetmez."""
    rows = [_row("A", "LONG", 100 + i, 1.0) for i in range(10)]
    rep = portfolio.build_report(rows, ["A"], _net, 2)
    assert rep["clusters"] == 10
    assert rep["gate_met"] is False        # 10 < 50, CI artida olsa bile
