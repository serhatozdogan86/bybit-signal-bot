"""Teyit laboratuvari - degismezlik testleri.

En kritik ikisi:
- test_frequency_scan_never_reports_returns: siklik karari GETIRIDEN
  BAGIMSIZ verilmelidir; getiri alani bulunmamali ki kimse "hangi (W,K)
  daha cok kazandirmis" diye secmesin.
- test_backtest_can_only_kill_never_bless: merdiven, teyitli kohort daha
  iyi ciktiginda bile KANIT vermez (P4 dersi).
"""
from __future__ import annotations

from app.services import agreement_lab as al

_H = 3_600_000


def _sig(strategy, pair, direction, hour, net=0.0):
    return {"strategy": strategy, "pair": pair, "direction": direction,
            "entry_ts": hour * _H, "net": net}


def _net(r):
    return r.get("net")


# --------------------------------------------------------- on-kayit
def test_declared_lists_are_frozen():
    assert al.WINDOWS_H == (1, 4, 12, 24)
    assert al.MIN_ENGINES == (2, 3, 4, 5)
    assert (al.VERDICT_W, al.VERDICT_K) == (4, 3)


# ------------------------------------------------------- gruplama
def test_same_pair_direction_within_window_groups():
    rows = [_sig("S1", "BTCUSDT", "LONG", 0),
            _sig("S2", "BTCUSDT", "LONG", 3),      # 3s sonra -> AYNI grup
            _sig("S8", "BTCUSDT", "LONG", 10)]     # 10s -> YENI grup (W=4)
    g = al.group_signals(rows, 4)
    assert len(g) == 2
    assert g[0]["engines"] == {"S1", "S2"}
    assert g[1]["engines"] == {"S8"}


def test_different_pair_or_direction_never_groups():
    rows = [_sig("S1", "BTCUSDT", "LONG", 0),
            _sig("S2", "BTCUSDT", "SHORT", 1),     # ters yon
            _sig("S8", "ETHUSDT", "LONG", 1)]      # baska parite
    assert len(al.group_signals(rows, 4)) == 3


def test_window_is_measured_from_group_first_not_previous():
    """Pencere grubun ILK girisinden olculur (on-kayitli kural).

    Aksi halde zincirleme kayma olur: her yeni uye pencereyi uzatir ve
    24 saatlik bir grup sonsuza kadar buyuyebilir."""
    rows = [_sig("S1", "BTCUSDT", "LONG", 0),
            _sig("S2", "BTCUSDT", "LONG", 3),
            _sig("S8", "BTCUSDT", "LONG", 6)]      # ilk'ten 6s -> DISARIDA
    g = al.group_signals(rows, 4)
    assert len(g) == 2 and g[0]["engines"] == {"S1", "S2"}


def test_same_engine_twice_counts_once():
    """FARKLI motor sayilir - ayni motorun iki sinyali teyit DEGILDIR."""
    rows = [_sig("S1", "BTCUSDT", "LONG", 0),
            _sig("S1", "BTCUSDT", "LONG", 1),
            _sig("S1", "BTCUSDT", "LONG", 2)]
    g = al.group_signals(rows, 4)
    assert len(g) == 1 and len(g[0]["engines"]) == 1


# ------------------------------------------------------- siklik
def test_frequency_scan_never_reports_returns():
    """Siklik taramasi GETIRI vermez - esik getiriye bakarak secilemez."""
    scan = al.frequency_scan([_sig("S1", "BTCUSDT", "LONG", 0, 5.0)], days=1)
    assert len(scan) == len(al.WINDOWS_H) * len(al.MIN_ENGINES)
    for row in scan:
        assert set(row) == {"window_h", "min_engines", "messages",
                            "trades_covered", "share_of_trades",
                            "messages_per_day"}
        for banned in ("net_r", "e_net", "ci", "gross_r"):
            assert banned not in row


def test_higher_k_never_yields_more_messages():
    """K buyudukce hayatta kalan sinyal ARTAMAZ (monotonluk)."""
    rows = ([_sig(s, "BTCUSDT", "LONG", 0) for s in ("S1", "S2", "S8")]
            + [_sig("S1", "ETHUSDT", "SHORT", 0)])
    scan = {(r["window_h"], r["min_engines"]): r["messages"]
            for r in al.frequency_scan(rows)}
    for w in al.WINDOWS_H:
        vals = [scan[(w, k)] for k in al.MIN_ENGINES]
        assert vals == sorted(vals, reverse=True)


def test_messages_per_day_needs_days():
    scan = al.frequency_scan([_sig("S1", "BTCUSDT", "LONG", 0)], days=None)
    assert all(r["messages_per_day"] is None for r in scan)


# --------------------------------------------------- hukum merdiveni
def test_backtest_can_only_kill_never_bless():
    """Teyitli kohort DAHA IYI olsa bile hukum KANIT DEGILDIR (P4 dersi)."""
    rows = ([_sig(s, "BTCUSDT", "LONG", 0, 2.0)
             for s in ("S1", "S2", "S8")]                 # teyitli, iyi
            + [_sig("S1", "ETHUSDT", "LONG", 0, -1.0)])   # teyitsiz, kotu
    rep = al.verdict_reading(rows, _net)
    assert rep["confirmed"]["e_net"] > rep["unconfirmed"]["e_net"]
    assert rep["verdict"] == "KANIT DEGIL - ILERI PENCERE ISTER"


def test_ladder_kills_when_confirmed_is_not_better():
    """Teyitli <= teyitsiz -> ELENDI (on-kayitli merdiven)."""
    rows = ([_sig(s, "BTCUSDT", "LONG", 0, -1.0)
             for s in ("S1", "S2", "S8")]
            + [_sig("S1", "ETHUSDT", "LONG", 0, 2.0)])
    assert al.verdict_reading(rows, _net)["verdict"] == \
        "ELENDI (teyit katki vermiyor)"


def test_equal_cohorts_also_kill():
    """ESITLIK de ELEMEDIR - merdiven '<=' der, '<' demez."""
    rows = ([_sig(s, "BTCUSDT", "LONG", 0, 1.0)
             for s in ("S1", "S2", "S8")]
            + [_sig("S1", "ETHUSDT", "LONG", 0, 1.0)])
    assert "ELENDI" in al.verdict_reading(rows, _net)["verdict"]


def test_empty_cohort_gives_no_verdict():
    rows = [_sig("S1", "BTCUSDT", "LONG", 0, 1.0)]   # teyitli kohort BOS
    assert al.verdict_reading(rows, _net)["verdict"] == \
        "ORNEKLEM YETERSIZ (hukum yok)"


# ------------------------------------------------------------ rapor
def test_report_carries_backtest_warning_and_filters_members():
    rows = [_sig("S1", "BTCUSDT", "LONG", 0, 1.0),
            _sig("YABANCI", "BTCUSDT", "LONG", 0, 9.0)]
    rep = al.build_report(rows, _net, ["S1"], days=10)
    assert rep["signals_total"] == 1                 # uye olmayan DISARIDA
    assert "OLDUREBILIR, KUTSAYAMAZ" in rep["backtest_warning"]
    assert "KANITLAMAZ" in rep["backtest_warning"]
    assert "getiriye bakarak" in rep["frequency_note"]
