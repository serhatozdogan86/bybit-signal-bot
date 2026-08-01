

def test_kitap_routes_serve_docs(tmp_path):
    """Ders kitabi rotalari docs/ altindan HTML ve PDF servis eder."""
    from unittest.mock import MagicMock
    from app.server import create_app

    app = create_app(MagicMock(get_meta=lambda: {"last_scan_utc": None}),
                     MagicMock(), None)
    client = app.test_client()
    html = client.get("/kitap")
    assert html.status_code == 200
    assert html.mimetype == "text/html"
    assert b"Ders Kitab" in html.data
    pdf = client.get("/kitap.pdf")
    assert pdf.status_code == 200
    assert pdf.mimetype == "application/pdf"
    assert pdf.data[:4] == b"%PDF"


def test_signal_chart_route(tmp_path):
    """Kanit paketi rotasi: mumlar + plan + teyitler doner."""
    from unittest.mock import MagicMock
    from app.server import create_app

    tracker = MagicMock()
    tracker.signal_chart.return_value = {
        "signal": {"id": 1, "pair": "XUSDT", "direction": "SHORT"},
        "candles": [{"ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5,
                     "volume": 10}],
        "evidence": {"liquidity": "breakout_retest @ 1.0"},
    }
    app = create_app(MagicMock(get_meta=lambda: {"last_scan_utc": None}),
                     MagicMock(), tracker)
    client = app.test_client()
    ok = client.get("/signal/1/chart")
    assert ok.status_code == 200
    assert ok.get_json()["candles"][0]["close"] == 1.5
    tracker.signal_chart.return_value = None
    assert client.get("/signal/999/chart").status_code == 404
