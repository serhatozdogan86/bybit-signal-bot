"""OI indirici + P1 OI-Flush backtest araclari.

Indirici: imlec sayfalamasinda ILERLEME KORUMASI (kline indiricisinde
yasanan sonsuz-dongu SINIFI kapali kalmali). Backtest: donmus kurallar
ekilmis senaryolari geri bulmali; kontrol senaryolari islem uretmemeli.
"""
from __future__ import annotations

import csv
import os

from tools.backtest_oi_flush import (DAY, M15, WINDOW, run_backtest,
                                     run_pair)
from tools.download_oi_data import fetch_oi

H1 = 3_600_000
T0 = 1_000_000 * H1                       # saat hizali baslangic


# ------------------------------------------------------------------ indirici
class _Resp:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


class _StuckCursorSession:
    """Imlec donen ama HEP AYNI noktalari getiren API simulasyonu.
    Ilerleme korumasi olmasa dongu _MAX_PAGES'e kadar surerdi."""

    def __init__(self):
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        assert self.calls <= 3, "ilerleme korumasi calismiyor (sonsuz dongu)"
        rows = [{"timestamp": str(T0 + k * H1), "openInterest": "100"}
                for k in range(5)]
        return _Resp({"retCode": 0,
                      "result": {"list": rows, "nextPageCursor": "surekli"}})


class _PagedSession:
    """2 sayfalik normal akis: her sayfa yeni noktalar, sonra imlec biter."""

    def __init__(self):
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        base = T0 + (0 if self.calls == 1 else 5 * H1)
        rows = [{"timestamp": str(base + k * H1), "openInterest": str(100 + k)}
                for k in range(5)]
        cur = "devam" if self.calls == 1 else ""
        return _Resp({"retCode": 0,
                      "result": {"list": rows, "nextPageCursor": cur}})


def test_fetch_oi_progress_guard_breaks_stuck_cursor():
    s = _StuckCursorSession()
    pts = fetch_oi(s, "http://x", "AUSDT", T0, T0 + 100 * H1, 0.0)
    assert pts is not None and len(pts) == 5
    assert s.calls == 2                    # 2. sayfa yeni nokta getirmedi -> dur


def test_fetch_oi_normal_pagination():
    s = _PagedSession()
    pts = fetch_oi(s, "http://x", "AUSDT", T0, T0 + 100 * H1, 0.0)
    assert len(pts) == 10 and s.calls == 2


# ------------------------------------------------------------------ backtest
def _flush_scenario(oi_drop=0.15, stabilize=True, rally=True):
    """24s duz -> 24s dusus -> stabilizasyon -> ralli. OI ayni pencerede
    oi_drop kadar erir. Donen: (bars15, bars4h, oi)."""
    bars15 = []
    n_flat, n_drop = WINDOW + 8, WINDOW           # dusus tam 24s
    price = 100.0
    for i in range(n_flat):
        t = T0 + i * M15
        bars15.append((t, price, price + 0.05, price - 0.05, price))
    for i in range(n_drop):                        # monoton dusus 100 -> 95.2
        t = T0 + (n_flat + i) * M15
        price = 100.0 - (i + 1) * (4.8 / n_drop)
        bars15.append((t, price + 0.02, price + 0.05, price - 0.05, price))
    i_stab = n_flat + n_drop
    stab_close = price + (0.10 if stabilize else -0.10)
    bars15.append((T0 + i_stab * M15, price, stab_close + 0.05,
                   price - 0.06, stab_close))
    post = []
    p = stab_close
    for i in range(TIMEOUT := 120):
        t = T0 + (i_stab + 1 + i) * M15
        p = p + (0.25 if rally else 0.0)
        hi = p + 0.05 if rally else p + 0.01
        post.append((t, p, hi, p - 0.01, p))
    bars15.extend(post)
    # 4H: kucuk ATR'li duz seri ayni zaman araliginda
    bars4h = []
    for i in range((len(bars15) * M15) // 14_400_000 + 16):
        t = T0 - 15 * 14_400_000 + i * 14_400_000
        bars4h.append((t, 100.0, 100.1, 99.9, 100.0))
    # OI: saatlik; dusus penceresi boyunca oi_drop kadar erir
    oi = {}
    total_h = (len(bars15) * M15) // H1 + 30
    drop_start_h = (n_flat * M15) // H1
    drop_len_h = (n_drop * M15) // H1
    for hh in range(-30, total_h):
        t = T0 + hh * H1
        if hh < drop_start_h:
            v = 1000.0
        elif hh < drop_start_h + drop_len_h:
            v = 1000.0 * (1 - oi_drop * (hh - drop_start_h + 1) / drop_len_h)
        elif hh < drop_start_h + drop_len_h + 1:
            v = 1000.0 * (1 - oi_drop)     # stab mumu saati: hala erimis
        else:
            v = 1000.0                     # toparlandi -> yeni tetik yok
        oi[t] = v
    return bars15, bars4h, oi


def test_planted_flush_reversal_recovered_as_win():
    bars15, bars4h, oi = _flush_scenario()
    trades = run_pair(bars15, bars4h, oi)
    assert len(trades) == 1
    tr = trades[0]
    assert tr["outcome"] == "WIN" and abs(tr["gross"] - 2.0) < 0.01
    assert 0 < tr["net"] < tr["gross"]            # maliyet dusuldu


def test_shallow_oi_drop_no_trade():
    bars15, bars4h, oi = _flush_scenario(oi_drop=0.05)
    assert run_pair(bars15, bars4h, oi) == []


def test_no_stabilization_no_trade():
    # stabilizasyon mumu HIC yok (dusus + duz devam) -> islem acilmamali
    bars15, bars4h, oi = _flush_scenario(stabilize=False, rally=False)
    assert run_pair(bars15, bars4h, oi) == []


def test_timeout_expired_r():
    bars15, bars4h, oi = _flush_scenario(rally=False)
    trades = run_pair(bars15, bars4h, oi)
    assert len(trades) == 1
    assert trades[0]["outcome"] == "EXPIRED"
    assert trades[0]["hold"] == 96


def test_run_backtest_counts_missing_inputs(tmp_path):
    data = tmp_path / "kline"
    oid = tmp_path / "oi"
    data.mkdir(), oid.mkdir()
    bars15, bars4h, oi = _flush_scenario()
    for name, rows in (("GOODUSDT_15", bars15), ("GOODUSDT_240", bars4h),
                       ("NOOIUSDT_15", bars15), ("NOOIUSDT_240", bars4h)):
        with open(data / f"{name}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ts", "open", "high", "low", "close", "volume"])
            for b in rows:
                w.writerow([*b, 1.0])
    with open(oid / "GOODUSDT_oi_1h.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open_interest"])
        for t in sorted(oi):
            w.writerow([t, oi[t]])
    rep = run_backtest(str(data), str(oid))
    assert rep["pairs_done"] == 1 and rep["pairs_no_oi"] == 1
    assert rep["trades"] == 1 and rep["wins"] == 1
    assert rep["clusters"] == 1
    assert "YETERSIZ" in rep["verdict"]           # 1 kume < 50
