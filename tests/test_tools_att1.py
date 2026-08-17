"""S-ATT1 araclari testleri (on-kayit 2026-08-16 + uygulama eki 08-17).

Kanit yuku: z-skoru dogru sok yakalar; 24s getiri filtresi iki yonde de
keser; giris T+1 ACILISTAN; 7 gun yeniden-giris yasagi; stop/zaman-cikisi
R muhasebesi; esleme tablosu tekrarsiz; indirici URL/ayiklama saf
fonksiyonlari dogru.
"""
from __future__ import annotations

import math
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from tools import backtest_att1 as bt          # noqa: E402
from tools import download_wiki_views as dl    # noqa: E402

DAY = 86_400_000
STEP = bt.STEP_MS
D0 = date(2026, 5, 1).toordinal()              # test evreninin ilk gunu


def _flat_views(days=120, level=1000):
    return {D0 + i: level for i in range(days)}


def _bars_flat(days=130, price=100.0, lo_off=0.5, hi_off=0.5):
    """Gun basina 6 x 4H mum, duz fiyat."""
    bars = {}
    t0 = bt.day_to_ms(D0)
    for i in range(days * 6):
        t = t0 + i * STEP
        bars[t] = (price, price + hi_off, price - lo_off, price)
    return bars


# ------------------------------------------------------------- z-skoru
def test_zscore_detects_planted_spike_and_flat_is_none():
    # gercekci taban: hafif dalgali (gercek goruntuleme hic sabit degildir)
    v = {D0 + i: 1000 + (i % 7) * 3 for i in range(120)}
    spike_day = D0 + 100
    v[spike_day] = 100_000                     # ~x100 sok
    z = bt.zscore_day(v, spike_day)
    assert z is not None and z >= 2.0
    # siradan gun sok degildir
    z99 = bt.zscore_day(v, D0 + 99)
    assert z99 is not None and z99 < 2.0
    # OLU-DUZ taban: sapma 0 -> z tanimsiz -> sinyal yok (on-kayit eki);
    # kayan-nokta artigi (~1e-28 varyans) muhafizla yutulur
    flat = _flat_views()
    assert bt.zscore_day(flat, D0 + 99) is None
    # yetersiz taban (ilk gunlerde 90 gun yok) -> None
    assert bt.zscore_day(v, D0 + 10) is None


def test_zscore_min_base_days():
    v = {D0 + i: 1000 + (i % 7) for i in range(120)}   # hafif dalgali
    # 90 gunluk tabandan 15 gun sil -> 75 < 81 -> None
    for i in range(30, 45):
        del v[D0 + 100 - 90 + i - 30]  # taban icinden 15 ardisik gun
    day = D0 + 100
    assert bt.zscore_day(v, day) is None


# ------------------------------------------------- sinyal + giris kurgusu
def _views_with_spike(spike_day, days=130):
    v = {D0 + i: 1000 + (i % 5) for i in range(days)}  # sapma > 0
    v[spike_day] = 80_000
    return v


def test_signal_enters_next_day_open_and_time_exit():
    spike = D0 + 100
    bars = _bars_flat()
    # gun D getirisi +%5 olsun: D gununun 6 mumunun kapanisi 105
    for k in range(6):
        t = bt.day_to_ms(spike) + k * STEP
        bars[t] = (105.0, 105.5, 104.5, 105.0)
    # D+1 ilk mum ACILISI 106 (giris buradan olmali)
    for i in range(6 * 4):                     # D+1'den itibaren 4 gun
        t = bt.day_to_ms(spike + 1) + i * STEP
        bars[t] = (106.0, 106.5, 105.5, 106.0)
    rep = bt.run_backtest({"AUSDT": bars}, {"AUSDT": _views_with_spike(spike)})
    assert rep["signals"] == 1 and rep["entries"] == 1
    assert rep["losses"] == 0 and rep["time_exits"] == 1
    # duz seride zaman-cikisi ~0R (giris 106 acilis, cikis 106 kapanis)
    assert abs(rep["gross_r_sum"]) < 0.01
    assert rep["net_r_sum"] < 0                # maliyet dusuldu
    assert rep["clusters"] == 1                # kume = sinyal gunu


def test_r24_filter_blocks_negative_and_pump():
    spike = D0 + 100
    v = {"AUSDT": _views_with_spike(spike)}
    # negatif 24s getiri: D gunu kapanis 95
    bars = _bars_flat()
    for k in range(6):
        bars[bt.day_to_ms(spike) + k * STEP] = (95.0, 95.5, 94.5, 95.0)
    assert bt.run_backtest({"AUSDT": bars}, v)["signals"] == 0
    # +%30 pump: kovalamaca filtresi keser (>0.25)
    bars2 = _bars_flat()
    for k in range(6):
        bars2[bt.day_to_ms(spike) + k * STEP] = (130.0, 130.5, 129.5, 130.0)
    assert bt.run_backtest({"AUSDT": bars2}, v)["signals"] == 0


def test_stop_hit_is_minus_one_r():
    spike = D0 + 100
    bars = _bars_flat()
    for k in range(6):
        bars[bt.day_to_ms(spike) + k * STEP] = (102.0, 102.5, 101.5, 102.0)
    # D+1: giris 103'ten, ilk mumda dibe cakilma (stop = 103 - 2xATR)
    t1 = bt.day_to_ms(spike + 1)
    bars[t1] = (103.0, 103.2, 80.0, 81.0)
    rep = bt.run_backtest({"AUSDT": bars}, {"AUSDT": _views_with_spike(spike)})
    assert rep["entries"] == 1 and rep["losses"] == 1
    assert abs(rep["gross_r_sum"] + 1.0) < 1e-6
    assert rep["net_r_sum"] < -1.0             # maliyet + slip eklendi


def test_seven_day_reentry_ban():
    bars = _bars_flat(days=140)
    v = {D0 + i: 1000 + (i % 5) for i in range(140)}
    spike1, spike2 = D0 + 100, D0 + 103        # 2. sok yasak penceresinde
    v[spike1] = 80_000
    v[spike2] = 90_000
    for s in (spike1, spike2):                 # her iki gun +%2 getiri
        base = 100.0 if s == spike1 else 100.0
        for k in range(6):
            bars[bt.day_to_ms(s) + k * STEP] = (base * 1.02, base * 1.025,
                                                base * 1.015, base * 1.02)
        # ertesi gunler duz devam etsin (giris/cikis icin veri var)
    rep = bt.run_backtest({"AUSDT": bars}, {"AUSDT": v})
    assert rep["signals"] == 2
    assert rep["entries"] == 1                 # ikincisi yasakla atlandi
    assert rep["skipped_ban"] == 1


def test_mapping_table_loads_unique_nonempty():
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data", "wiki-eslesme.csv")
    rows = dl.load_mapping(path)
    assert len(rows) >= 40
    syms = [s for s, _ in rows]
    assert len(syms) == len(set(syms))         # tekrar yok
    assert all(a.strip() for _, a in rows)     # bos makale yok


def test_downloader_url_and_parse_and_dates():
    url = dl.build_url("Shiba Inu (cryptocurrency)", "20260101", "20260110")
    assert "Shiba_Inu_%28cryptocurrency%29" in url
    assert url.endswith("/daily/20260101/20260110")
    payload = {"items": [
        {"timestamp": "2026010100", "views": 123},
        {"timestamp": "2026010200", "views": "bozuk"},   # atlanir
        {"timestamp": "2026010300", "views": 456},
    ]}
    parsed = dl.parse_views(payload)
    assert parsed == {"20260101": 123, "20260103": 456}
    days = dl.expected_dates("20260130", "20260202")
    assert days == ["20260130", "20260131", "20260201", "20260202"]
