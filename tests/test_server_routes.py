

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
