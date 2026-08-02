"""v3.6 guvenlik/dayaniklilik: tarama kilidi, auth katmani, HTTP metotlari."""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from app.scheduler import ScanBusy, Scheduler
from app.server import create_app


def _store():
    return MagicMock(get_meta=lambda: {"last_scan_utc": None},
                     get_results=lambda: {})


# ------------------------------------------------------- tarama kilidi
def _scheduler(delay=0.0):
    from app.config.settings import Settings
    md = MagicMock()
    md.get_series.return_value = None          # BTC yok -> halt, hizli tur
    s = Scheduler(Settings(TELEGRAM_ENABLED=False, SYMBOLS="AUSDT",
                           SYMBOL_PAUSE_SEC=delay),
                  md, MagicMock(), MagicMock())
    return s


def test_concurrent_scan_rejected_not_queued():
    """Ikinci tarama BEKLEMEZ, reddedilir: kuyruk gecikmeyi buyutur,
    es zamanlilik olcum verisini bozar."""
    sch = _scheduler()
    started = threading.Event()
    release = threading.Event()

    def slow(_send):
        started.set()
        release.wait(timeout=5)
        return []
    sch._scan_all_locked = slow

    t = threading.Thread(target=lambda: sch.scan_all(), daemon=True)
    t.start()
    assert started.wait(timeout=5)
    assert sch.scan_in_progress() is True
    with pytest.raises(ScanBusy):
        sch.scan_all()                          # ikinci cagri aninda reddedilir
    release.set()
    t.join(timeout=5)
    assert sch.scan_in_progress() is False
    sch.scan_all()                              # kilit birakildi -> yeniden calisir


def test_scan_lock_released_on_error():
    """Tarama patlarsa kilit ASILI KALMAMALI (yoksa bot kalici olarak susar)."""
    sch = _scheduler()

    def boom(_send):
        raise ValueError("tarama patladi")
    sch._scan_all_locked = boom
    with pytest.raises(ValueError):
        sch.scan_all()
    assert sch.scan_in_progress() is False


def test_scan_route_returns_409_when_busy():
    sch = MagicMock()
    sch.scan_all.side_effect = ScanBusy("busy")
    client = create_app(_store(), sch, None).test_client()
    r = client.post("/scan")
    assert r.status_code == 409 and r.get_json()["error"] == "scan_in_progress"


# ------------------------------------------------- HTTP metot semantigi
def test_mutating_routes_are_post_only():
    """GET ile durum degistirilemez: tarayici prefetch/crawler kazara
    tarama veya gist yazimi tetiklemesin."""
    gist = MagicMock(); gist.sync.return_value = True; gist.info.return_value = {}
    client = create_app(_store(), MagicMock(), None, gist).test_client()
    assert client.get("/scan").status_code == 405
    assert client.get("/scan/dry").status_code == 405
    assert client.get("/backup/now").status_code == 405
    assert client.post("/backup/now").status_code == 200
    assert client.get("/backup/info").status_code == 200   # okuma GET kalir


# --------------------------------------------------------- auth katmani
def test_auth_disabled_when_token_empty():
    """Jeton yoksa davranis eskisiyle AYNI - kazara kilitlenme olmaz."""
    client = create_app(_store(), MagicMock(), None).test_client()
    assert client.get("/status").status_code == 200
    assert client.get("/").status_code == 200


def test_auth_required_when_token_set():
    app = create_app(_store(), MagicMock(), None, auth_token="gizli")
    c = app.test_client()
    assert c.get("/status").status_code == 401
    assert c.get("/status", headers={"X-Auth-Token": "gizli"}).status_code == 200
    assert c.get("/status?k=gizli").status_code == 200
    assert c.get("/status?k=yanlis").status_code == 401


def test_health_stays_public_under_auth():
    """Dead-man's switch izlemesi jetonla kirilmamali."""
    c = create_app(_store(), MagicMock(), None, auth_token="gizli").test_client()
    assert c.get("/health").status_code in (200, 503)
    assert c.get("/healthz").status_code == 200
    assert c.get("/manifest.webmanifest").status_code == 200


def test_token_handoff_sets_cookie_and_cleans_url():
    """?k=... ile gelen tarayici cereze gecer; jeton URL'de kalmaz."""
    c = create_app(_store(), MagicMock(), None, auth_token="gizli").test_client()
    r = c.get("/?k=gizli")
    assert r.status_code == 302 and r.headers["Location"] == "/"
    assert "k=gizli" in r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in r.headers.get("Set-Cookie", "")
    assert c.get("/status").status_code == 200      # cerez sonrasi XHR calisir
