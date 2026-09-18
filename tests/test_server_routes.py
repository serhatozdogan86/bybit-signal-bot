

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


def test_pwa_manifest_and_icons():
    """PWA: manifest ve ikonlar servis edilir (ana ekrana kurulabilirlik)."""
    from unittest.mock import MagicMock
    from app.server import create_app

    client = create_app(MagicMock(get_meta=lambda: {"last_scan_utc": None}),
                        MagicMock(), None).test_client()
    man = client.get("/manifest.webmanifest")
    assert man.status_code == 200
    data = man.get_json()
    assert data["display"] == "standalone"
    assert any(i["sizes"] == "512x512" for i in data["icons"])
    icon = client.get("/icon-192.png")
    assert icon.status_code == 200 and icon.data[:4] == b"\x89PNG"


def test_anatomy_route_serves_declared_sections():
    """/anatomy rotasi ILAN EDILMIS bolumleri doner; tracker yoksa 404.

    ?all=1 tum deftere gecer - kilit penceresiyle karistirilmasin diye
    rota hangi pencerede oldugunu cevabinda YAZAR."""
    from unittest.mock import MagicMock
    from app.server import create_app
    from app.services import anatomy

    tracker = MagicMock()
    tracker.anatomy_report.side_effect = lambda since_lock=True: {
        "window": ("KILIT-2 sonrasi" if since_lock else "tum defter"),
        **{s: {} for s in anatomy.SECTIONS}}
    app = create_app(MagicMock(get_meta=lambda: {"last_scan_utc": None}),
                     MagicMock(), tracker)
    client = app.test_client()
    body = client.get("/anatomy")
    assert body.status_code == 200
    for s in anatomy.SECTIONS:
        assert s in body.get_json()
    assert body.get_json()["window"] == "KILIT-2 sonrasi"
    assert client.get("/anatomy?all=1").get_json()["window"] == "tum defter"

    # golge takip kapaliysa sessiz bos cevap degil, acik 404
    app2 = create_app(MagicMock(get_meta=lambda: {"last_scan_utc": None}),
                      MagicMock(), None)
    assert app2.test_client().get("/anatomy").status_code == 404
