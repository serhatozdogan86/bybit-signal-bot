"""YEDEK KAPSAMI — yedek, kurtarma icin GEREKEN her seyi tasir mi?

ARIZA (2026-09-28, bu testlerin dogum sebebi): VM Oracle'da durdu ve
kapasite yoklugundan acilmadi. O anda yedegin kapsami denetlendi ve
soyle cikti:
  - aday motorlarin islemleri: yalnizca SON 200 (toplam ~4300)
  - aday islemlerini GERI YUKLEYEN fonksiyon: YOK
  - sampiyon sinyalleri: yalnizca son 500
Yani portfoy olcumunun %95'i SADECE VM diskinde duruyordu. 18 Eylul'de
yedegin dosya-sayisi arizasi duzeltilmis ve "yedek calisiyor" denmisti;
duzeltilen sey dosya SAYISIYDI, KAPSAM denetlenmemisti.

DERS (kurallastirildi): "yedek calisiyor" demek yetmez; yedegin NEYI
kapsadigi ayrica denetlenir. Bu testler o denetimi otomatiklestirir.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.services.gist_backup import GistBackup
from tests.test_signal_tracker import _make_tracker


def _engine_with_rows(db, n=5):
    """challenger_signals tablosuna n kayit koy ve sahte motor dondur."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS challenger_signals("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "strategy TEXT, pair TEXT, direction TEXT, created_utc TEXT,"
        "entry_ts INTEGER, entry REAL, stop REAL, tp REAL,"
        "timeout_bars INTEGER, status TEXT DEFAULT 'OPEN',"
        "outcome TEXT, exit_price REAL, exit_ts INTEGER,"
        "r_multiple REAL, hold_bars INTEGER, cluster_id TEXT,"
        "ambiguous INTEGER DEFAULT 0, regime INTEGER DEFAULT 1,"
        "doi_24h REAL)")
    for i in range(n):
        db.execute(
            "INSERT INTO challenger_signals(strategy,pair,direction,"
            "created_utc,entry_ts,entry,stop,tp,timeout_bars,status,outcome,"
            "r_multiple,cluster_id,regime) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("S1_TSMOM", f"P{i}USDT", "LONG", f"2026-09-0{i%9}T00:00:00Z",
             1_000_000 + i, 100.0, 98.0, 104.0, 8, "CLOSED", "WIN",
             1.5, f"S1_TSMOM:L{i}", 2))
    eng = MagicMock()
    eng._db = db
    eng.stats.return_value = {"strategies": {}}
    eng.recent.return_value = []
    # gercek motorun yaptigini yap: ham kayitlari DB'den oku
    eng.export_rows.side_effect = lambda: db.query(
        "SELECT * FROM challenger_signals ORDER BY id")
    return eng


# ------------------------------------------------- ADAY ISLEMLERI: yedek
def test_all_challenger_rows_are_backed_up_not_just_recent(tmp_path):
    """Aday islemlerinin TAMAMI yedege girer - son N tanesi degil.

    Duzeltme oncesi KIRMIZI: yedekte yalnizca stats + recent(200) vardi."""
    tracker, db = _make_tracker(tmp_path)
    eng = _engine_with_rows(db, n=5)
    gb = GistBackup(MagicMock(), tracker, symbols=[], intervals=["15"])
    gb.set_challengers(eng)
    files = gb.build_files()
    assert "0_challenger_rows.json" in files, \
        "aday ham kayitlari yedekte YOK - kurtarilamaz"
    rows = json.loads(files["0_challenger_rows.json"])
    assert len(rows) == 5
    # ham alanlar tasinir (ozet degil): geri yukleme icin gerekli
    for alan in ("strategy", "pair", "direction", "entry_ts", "entry",
                 "stop", "tp", "status", "outcome", "r_multiple",
                 "cluster_id", "regime"):
        assert alan in rows[0], f"ham alan eksik: {alan}"


# ---------------------------------------------- ADAY ISLEMLERI: geri yukle
def test_challenger_rows_can_be_restored(tmp_path):
    """Yedekten aday islemleri GERI YUKLENEBILIR.

    Duzeltme oncesi KIRMIZI: import fonksiyonu hic yoktu."""
    from app.services.challengers import ChallengerEngine
    _, db = _make_tracker(tmp_path)
    src = _engine_with_rows(db, n=3)
    # yedekten donen sey JSON'dan gecer; ayni yolu izleyelim
    payload = json.loads(json.dumps(
        src._db.query("SELECT * FROM challenger_signals")))

    _, db2 = _make_tracker(tmp_path / "ikinci")
    eng2 = ChallengerEngine(db2)
    n = eng2.import_rows(payload)
    assert n == 3
    geri = db2.query("SELECT * FROM challenger_signals")
    assert len(geri) == 3
    assert {r["pair"] for r in geri} == {"P0USDT", "P1USDT", "P2USDT"}


def test_restore_is_idempotent_no_duplicates(tmp_path):
    """Ayni yedek iki kez yuklenirse kayit KOPYALANMAZ.

    Kopyalanirsa istatistik sisip hukum bozulur."""
    from app.services.challengers import ChallengerEngine
    tracker, db = _make_tracker(tmp_path)
    src = _engine_with_rows(db, n=3)
    payload = src._db.query("SELECT * FROM challenger_signals")
    _, db2 = _make_tracker(tmp_path / "ikinci")
    eng2 = ChallengerEngine(db2)
    assert eng2.import_rows(payload) == 3
    assert eng2.import_rows(payload) == 0          # ikinci kez: hicbiri
    assert len(db2.query("SELECT * FROM challenger_signals")) == 3


def test_gist_restore_pulls_challenger_rows(tmp_path):
    """restore_if_empty aday kayitlarini da geri yukler."""
    from app.services.challengers import ChallengerEngine
    tracker, db = _make_tracker(tmp_path)
    src = _engine_with_rows(db, n=4)
    payload = src._db.query("SELECT * FROM challenger_signals")

    _, db2 = _make_tracker(tmp_path / "bos")
    tracker2 = _make_tracker(tmp_path / "bos2")[0]
    eng2 = ChallengerEngine(db2)
    client = MagicMock()
    client.find_gist.return_value = "g1"
    client.fetch_gist.return_value = {
        "0_challenger_rows.json": json.dumps(payload)}
    gb = GistBackup(client, tracker2, symbols=[], intervals=["15"])
    gb.set_challengers(eng2)
    gb.restore_if_empty()
    assert len(db2.query("SELECT * FROM challenger_signals")) == 4


# ------------------------------------------- SAMPIYON: 500 siniri kalkti
def test_champion_signal_backup_is_not_capped_at_500(tmp_path):
    """Sampiyon sinyal yedegi son 500'le SINIRLI kalmaz."""
    tracker, db = _make_tracker(tmp_path)
    for i in range(600):
        db.execute(
            "INSERT INTO signals(pair,direction,created_utc,status,outcome) "
            "VALUES(?,?,?,?,?)",
            (f"P{i}USDT", "LONG", f"2026-09-{i%28+1:02d}T00:00:00Z",
             "CLOSED", "WIN"))
    gb = GistBackup(MagicMock(), tracker, symbols=[], intervals=["15"])
    rows = json.loads(gb.build_files()["0_signals.json"])
    assert len(rows) > 500, f"sampiyon yedegi hala kapali: {len(rows)}"


# ------------------------------------------------- KAPSAM GORUNURLUGU
def test_backup_health_file_reports_coverage(tmp_path):
    """Yedek, NEYI kapsadigini kendi icinde yazar.

    '2026-09-18'de yedek calisiyor' demistim ama kapsami denetlememistim.
    Bu dosya o denetimi her senkronda otomatik yapar."""
    tracker, db = _make_tracker(tmp_path)
    eng = _engine_with_rows(db, n=7)
    gb = GistBackup(MagicMock(), tracker, symbols=[], intervals=["15"])
    gb.set_challengers(eng)
    h = json.loads(gb.build_files()["0_backup_health.json"])
    assert h["challenger_rows_total"] == 7
    assert h["challenger_rows_backed_up"] == 7
    assert h["complete"] is True


def test_row_cap_keeps_newest_and_flags_incomplete(tmp_path, monkeypatch):
    """Tavan asilirsa EN YENILER tutulur ve complete=false YAZILIR."""
    from app.services import gist_backup as gbmod
    monkeypatch.setattr(gbmod, "MAX_BACKUP_ROWS", 3)
    tracker, db = _make_tracker(tmp_path)
    eng = _engine_with_rows(db, n=6)
    gb = gbmod.GistBackup(MagicMock(), tracker, symbols=[], intervals=["15"])
    gb.set_challengers(eng)
    files = gb.build_files()
    rows = json.loads(files["0_challenger_rows.json"])
    assert len(rows) == 3
    assert [r["pair"] for r in rows] == ["P3USDT", "P4USDT", "P5USDT"]
    h = json.loads(files["0_backup_health.json"])
    assert h["challenger_rows_total"] == 6
    assert h["challenger_rows_backed_up"] == 3
    assert h["complete"] is False
