"""Backtest veri indiricisinin butunluk sayaclari (tools/, salt sayim)."""
from __future__ import annotations

from tools.download_backtest_data import fetch_window, integrity


class _Resp:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


class _ListingSession:
    """T0'da listelenen sembol simulasyonu (Bybit v5: start/end DAHIL).

    end=T0 istegi T0 mumunu TEKRAR dondurur; sayfalama imleci strict
    kucultulmezse dongu sonsuza gider. Cagri siniri bu SINIFI kirmizi yapar
    (2026-08-12 canli vaka: indirici yeni-listelenen paritede 24 saat
    sessiz takildi)."""

    MAX_CALLS = 40

    def __init__(self, t0, step, n, limit):
        self.t0, self.step, self.n, self.limit = t0, step, n, limit
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        assert self.calls <= self.MAX_CALLS, \
            "sayfalama imleci ilerlemiyor (sonsuz dongu sinifi)"
        ts_all = [self.t0 + i * self.step for i in range(self.n)]
        win = [t for t in ts_all if params["start"] <= t <= params["end"]]
        win = sorted(win, reverse=True)[:params["limit"]]   # yeni -> eski
        rows = [[str(t), "1", "1", "1", "1", "1"] for t in win]
        return _Resp({"retCode": 0, "result": {"list": rows}})


def test_fetch_window_terminates_when_history_starts_after_window():
    """Istenen pencere, paritenin ilk mumundan ONCE basliyorsa indirme
    yine de bitmeli ve tum mevcut mumlar eksiksiz donmeli."""
    step = 900_000
    t0 = 10_000 * step                # listelenme ani
    n = 450                           # limit 200 ile 3+ sayfa
    start_ms = t0 - 500 * step        # pencere listelenmeden cok once basliyor
    end_ms = t0 + n * step
    sess = _ListingSession(t0, step, n, limit=200)
    rows = fetch_window(sess, "http://x", "NEWUSDT", "15",
                        start_ms, end_ms, 0.0)
    assert rows is not None
    ts = [int(r[0]) for r in rows]
    assert len(ts) == n              # hicbir mum kaybolmadi, tekrar yok
    assert ts == sorted(ts)


def test_integrity_reports_gaps_and_stays_count_only():
    step = 900_000
    ts = [0, step, 2 * step, 6 * step]        # 2*step sonrasi 3 mum eksik
    rep = integrity(ts, step)
    assert rep["rows"] == 4
    assert rep["gaps"] == 1
    assert rep["gap_details"][0]["missing"] == 3
    assert rep["monotonic"] is True
    # ON-KAYIT kurali: rapor YALNIZ sayim alanlari icerir; istatistik/analiz
    # alani eklenirse bu test bilerek kirilir.
    assert set(rep) == {"rows", "range", "gaps", "gap_details", "monotonic"}


def test_integrity_empty_and_clean_series():
    step = 900_000
    assert integrity([], step)["rows"] == 0
    clean = integrity([i * step for i in range(10)], step)
    assert clean["gaps"] == 0 and clean["monotonic"] is True
    assert clean["range"][0].endswith("Z")
