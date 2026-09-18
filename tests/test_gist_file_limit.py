"""Gist yedegi DOSYA SAYISI siniri (2026-09-18 arizasi).

ARIZA: 2026-09-05'ten 09-18'e kadar 13 gun yedek yazilamadi. Log:
  gist_update_error error=422 Client Error: Unprocessable Entity
Sebep OLCULDU (VM'den): gist'te 300 dosya vardi - GitHub'in gist basina
SERT siniri tam 300. Bot 7 istatistik + 150 parite x 2 zaman dilimi =
307 dosya gondermeye calisiyordu -> her PATCH reddedildi.

SOZLESME (bu testler onu zorlar):
1. Mum yedegi YALNIZ en ince zaman dilimini tasir (degerlendirme ve
   restore onu kullanir; HTF her taramada canli cekilir).
2. Toplam dosya sayisi MAX_GIST_FILES'i ASLA gecmez - evren buyuse bile.
3. Artik gonderilmeyen eski mum dosyalari BUDANIR (None = sil); aksi
   halde evren donusu yeni adlar ekleyip sayiyi yeniden 300'e tirmandirir.
4. Budama yalniz candles_* dosyalarina dokunur - istatistik dosyalari
   asla silinmez.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.gist_backup import GistBackup, MAX_GIST_FILES
from tests.test_signal_tracker import _make_tracker


def _backup(tmp_path, symbols, intervals=("240", "15"), client=None):
    tracker, db = _make_tracker(tmp_path)
    # her parite/dilim icin birkac mum: export_candles bos donmesin
    for sym in symbols:
        for iv in intervals:
            db.executemany(
                "INSERT OR IGNORE INTO candles(symbol,interval,ts,open,high,"
                "low,close,volume) VALUES(?,?,?,1,1,1,1,1)",
                [(sym, iv, 1000 + i) for i in range(3)])
    gb = GistBackup(client or MagicMock(), tracker, symbols=list(symbols),
                    intervals=list(intervals))
    return gb, db


def test_only_finest_interval_is_backed_up(tmp_path):
    """4H dosyalari yedege GIRMEZ: 150 parite x 2 dilim = 300 dosya
    sinirin ta kendisiydi. Degerlendirme ve restore 15dk kullanir."""
    gb, _ = _backup(tmp_path, ["AUSDT", "BUSDT"], intervals=("240", "15"))
    files = gb.build_files()
    assert "candles_AUSDT_15.csv" in files
    assert "candles_BUSDT_15.csv" in files
    assert not [n for n in files if n.endswith("_240.csv")]


def test_file_count_never_exceeds_limit(tmp_path):
    """Evren buyuse bile tavan asilmaz (arizanin sinifini kapatir)."""
    syms = [f"P{i}USDT" for i in range(MAX_GIST_FILES + 50)]
    gb, _ = _backup(tmp_path, syms, intervals=("15",))
    files = gb.build_files()
    assert len(files) <= MAX_GIST_FILES
    # istatistik dosyalari BUDANMAZ - once onlar girer
    for must in ("0_performance.json", "0_challengers.json",
                 "0_exitlab.json", "README.md"):
        assert must in files


def test_sync_prunes_orphan_candle_files(tmp_path):
    """Evren donusu / dilim degisimi ile artik gonderilmeyen mum dosyalari
    SILINIR; istatistik dosyalarina dokunulmaz."""
    client = MagicMock()
    client.list_gist_files.return_value = [
        "0_performance.json", "0_signals.json",
        "candles_AUSDT_15.csv",      # hala gonderiliyor -> kalir
        "candles_AUSDT_240.csv",     # artik yok -> SILINMELI
        "candles_ESKIUSDT_15.csv",   # evrenden dustu -> SILINMELI
    ]
    client.update_gist.return_value = True
    gb, _ = _backup(tmp_path, ["AUSDT"], intervals=("240", "15"),
                    client=client)
    gb._gist_id = "g1"
    assert gb.sync() is True
    sent = client.update_gist.call_args[0][1]
    assert sent.get("candles_AUSDT_240.csv") is None      # silme emri
    assert sent.get("candles_ESKIUSDT_15.csv") is None    # silme emri
    assert sent.get("candles_AUSDT_15.csv") is not None   # duruyor
    # istatistik dosyalari ASLA silinmez
    assert sent.get("0_signals.json") is not None
    # toplam istek yine tavanin altinda
    assert len(sent) <= MAX_GIST_FILES


def test_list_gist_files_is_metadata_only():
    """Dosya adlarini almak icin 33 MB icerik indirilmez (fetch_gist
    pahalidir); yalniz meta okunur."""
    from app.integrations.gist_client import GistClient
    c = GistClient("tok")
    resp = MagicMock()
    resp.json.return_value = {"files": {"a.csv": {"size": 10},
                                        "b.json": {"size": 20}}}
    resp.raise_for_status.return_value = None
    c._session = MagicMock()
    c._session.get.return_value = resp
    assert sorted(c.list_gist_files("g1")) == ["a.csv", "b.json"]
    # icerik indiren raw_url cagrisi YAPILMAZ
    assert c._session.get.call_count == 1
