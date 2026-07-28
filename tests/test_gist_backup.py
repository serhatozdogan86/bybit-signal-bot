"""GistBackup - sync payload + redeploy sonrasi restore (self-healing) testleri."""
from __future__ import annotations

import json

import numpy as np

from app.models.decision import (Decision, DecisionType, Direction, EntryZone,
                                 Targets, TimeFrames)
from app.services.database import Database
from app.services.gist_backup import GistBackup, _parse_candles_csv
from app.services.signal_tracker import SignalTracker
from tests import fixtures as fx


class FakeGistClient:
    """API'siz gist simulasyonu: tek gist, dosyalar bellekte."""

    def __init__(self) -> None:
        self.storage: dict[str, dict[str, str]] = {}
        self.marker_index: dict[str, str] = {}
        self._next_id = 1

    def find_gist(self, marker):
        return self.marker_index.get(marker)

    def create_gist(self, marker, files):
        gid = f"fake{self._next_id}"
        self._next_id += 1
        self.storage[gid] = dict(files)
        self.marker_index[marker] = gid
        return gid

    def update_gist(self, gist_id, files):
        self.storage[gist_id] = {n: v for n, v in files.items() if v is not None}
        return True

    def fetch_gist(self, gist_id):
        return self.storage.get(gist_id)

    def gist_url(self, gist_id):
        return f"https://gist.github.com/{gist_id}"


def _tracker(tmp_path, name="a.db"):
    return SignalTracker(Database(str(tmp_path / name)), ltf_interval="15")


def _signal(pair="BTCUSDT"):
    return Decision(
        pair=pair, timestamp_utc="2026-07-27T00:00:00Z",
        timeframes=TimeFrames(htf="240", ltf="15"),
        decision=DecisionType.SIGNAL, direction=Direction.LONG,
        entry_zone=EntryZone(min=100.0, max=101.0), stop_loss=98.0,
        targets=Targets(tp1=106.0, tp2=110.0), rr=2.5)


def test_sync_creates_then_updates_and_payload_complete(tmp_path):
    tracker = _tracker(tmp_path)
    series = fx.make_series(np.linspace(100, 110, 70), symbol="BTCUSDT", interval="15")
    tracker.record_candles(series)
    tracker.record_decision(_signal())
    tracker.maybe_track(_signal(), series)

    client = FakeGistClient()
    backup = GistBackup(client, tracker, ["BTCUSDT"], ["240", "15"],
                        sync_interval_sec=3600)
    assert backup.sync() is True
    gid = backup.info()["gist_id"]
    files = client.storage[gid]
    for expected in ("0_performance.json", "0_signals.json", "0_decisions.json",
                     "candles_BTCUSDT_15.csv", "candles_BTCUSDT_240.csv", "README.md"):
        assert expected in files
    assert json.loads(files["0_performance.json"])["open_signals"] == 1
    assert files["candles_BTCUSDT_15.csv"].count("\n") == 70  # header + 69 kapanmis bar

    # ikinci sync ayni gist'i gunceller, yenisini olusturmaz
    assert backup.sync() is True
    assert len(client.storage) == 1


def test_restore_after_redeploy_resumes_tracking(tmp_path):
    # 1) "eski instance": veri biriktir ve gist'e yaz
    old = _tracker(tmp_path, "old.db")
    series = fx.make_series(np.linspace(100, 110, 70), symbol="BTCUSDT", interval="15")
    old.record_candles(series)
    old.maybe_track(_signal(), series)
    client = FakeGistClient()
    GistBackup(client, old, ["BTCUSDT"], ["15"], 3600).sync()

    # 2) "redeploy": bos DB'li yeni instance ayni gist'ten restore eder
    fresh = _tracker(tmp_path, "fresh.db")
    assert fresh.candles_count() == 0
    backup2 = GistBackup(client, fresh, ["BTCUSDT"], ["15"], 3600)
    assert backup2.restore_if_empty() is True
    assert fresh.candles_count() == 69
    sig = fresh.recent_signals(1)[0]
    assert sig["pair"] == "BTCUSDT" and sig["status"] == "PENDING"

    # 3) veri varken restore tekrar calismaz (uzerine yazma riski yok)
    assert backup2.restore_if_empty() is False
    # 4) restore edilen sinyal tekrar import edilirse coğaltilmaz
    assert fresh.import_signals(old.recent_signals(10)) == 0


def test_parse_candles_csv_ignores_bad_lines():
    text = "ts,open,high,low,close,volume\n1,2,3,4,5,6\nbozuk,satir\n7,8,9,10,11,12\n"
    rows = _parse_candles_csv(text)
    assert rows == [(1, 2.0, 3.0, 4.0, 5.0, 6.0), (7, 8.0, 9.0, 10.0, 11.0, 12.0)]


def test_candle_mode_signals_and_row_cap(tmp_path):
    tracker = _tracker(tmp_path, "modes.db")
    s1 = fx.make_series(np.linspace(100, 110, 70), symbol="BTCUSDT", interval="15")
    s2 = fx.make_series(np.linspace(50, 60, 70), symbol="XRPUSDT", interval="15")
    tracker.record_candles(s1)
    tracker.record_candles(s2)
    tracker.maybe_track(_signal("BTCUSDT"), s1)   # sadece BTC sinyal uretti

    backup = GistBackup(FakeGistClient(), tracker,
                        lambda: ["BTCUSDT", "XRPUSDT"], ["15"], 3600,
                        candle_mode="signals", candle_max_rows=10)
    files = backup.build_files()
    assert "candles_BTCUSDT_15.csv" in files       # sinyal ureten dahil
    assert "candles_XRPUSDT_15.csv" not in files   # uretmeyen haric
    assert files["candles_BTCUSDT_15.csv"].count("\n") == 11  # header + cap 10

    off = GistBackup(FakeGistClient(), tracker, ["BTCUSDT"], ["15"], 3600,
                     candle_mode="off")
    assert not any(n.startswith("candles_") for n in off.build_files())
