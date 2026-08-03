"""YAPISAL GUVENCELER - hata SINIFLARINI kapatan testler.

Buradaki testler tek bir hatayi degil, ayni hatanin tekrar dogmasini
engeller. Bugun bulunan dort olcum hatasinin ucu bu tur bir testle
DOGARKEN yakalanirdi. Kural: yeni bir hata bulundugunda once burada
sinifini kapatan bir test yazilir, sonra hata duzeltilir.
"""
from __future__ import annotations

import inspect
import re

import numpy as np

from app.services.database import Database
from app.services.signal_tracker import SignalTracker
from tests import fixtures as fx
from tests.test_signal_tracker import _feed, _make_tracker, _signal

# Yedege girmesi ANLAMSIZ olan kolonlar - her biri GEREKCELI:
#   id              : hedef DB kendi id'sini uretir
#   contract_json   : 0_decisions.json'da ayrica yedeklenir
#   prefill_repaired: onarim isareti; restore sonrasi yeniden hesaplanir
#   blocked/block_reason: temiz kohort payloadi zaten blocked=0 filtreler;
#                     bu iki alan bloklu kohort yedeginde tasinir
_BACKUP_EXEMPT = {"id", "contract_json", "prefill_repaired",
                  "blocked", "block_reason"}


def test_every_signal_column_survives_backup_restore(tmp_path):
    """HATA SINIFI: yeni kolon eklenir, yedek payloadina eklenmez ->
    her restore'da SESSIZCE silinir (v3.6'da hypo/nf/mfe/funding boyle
    kayboluyordu). Bu test kolonu unutmayi imkansiz kilar."""
    db = Database(str(tmp_path / "a.db"))
    tracker = SignalTracker(db, "15")
    cols = {r["name"] for r in db.query("PRAGMA table_info(signals)")}
    eksik = cols - _BACKUP_EXEMPT
    db.execute("INSERT INTO signals(pair,direction,created_utc) "
               "VALUES('AUSDT','LONG','2026-08-01T00:00:00Z')")
    payload = set(tracker.recent_signals(1)[0].keys())
    kayip = sorted(eksik - payload)
    assert not kayip, (
        f"Bu kolonlar yedege girmiyor, restore'da kaybolur: {kayip}. "
        "recent_signals() ve import_signals() guncellenmeli.")


def test_blocked_cohort_backup_matches_signal_backup(tmp_path):
    """Bloklu kohort da degerlendiriliyor; yedegi gercek kohorttan geri
    kalmamali (aksi halde ayni sessiz kayip orada olur)."""
    db = Database(str(tmp_path / "b.db"))
    tracker = SignalTracker(db, "15")
    db.execute("INSERT INTO signals(pair,direction,created_utc,blocked) "
               "VALUES('AUSDT','LONG','2026-08-01T00:00:00Z',1)")
    db.execute("INSERT INTO signals(pair,direction,created_utc) "
               "VALUES('BUSDT','LONG','2026-08-01T00:00:00Z')")
    olcum = {"fill_ts", "ambiguous", "hypo_r", "hypo_done", "mfe_r", "mae_r",
             "nf_gap_r", "nf_touch_bars", "nf_crossed", "nf_done",
             "funding_r_real", "funding_done"}
    kayip = sorted(olcum - set(tracker.blocked_signals(1)[0].keys()))
    assert not kayip, f"bloklu kohort yedeginde eksik: {kayip}"


def test_evaluation_is_idempotent_across_rounds(tmp_path):
    """HATA SINIFI: durum tasiyan degerlendirici ikinci turda farkli
    davranir (fill_price DB'den gelince dongu bastan tarardi -> uydurma
    WIN ve sisirilmis MFE). Ayni mumlarla tekrar calistirmak sonucu
    DEGISTIRMEMELI."""
    tracker, db = _make_tracker(tmp_path)
    ltf = fx.make_series(np.full(70, 101.5))
    ltf.candles[-1].ts = 1_000_000
    tracker.maybe_track(_signal(), ltf)
    args = dict(closes=[100.8, 100.2, 106.2], lows=[100.5, 99.9, 105.5],
                highs=[101.2, 100.6, 106.5], start_ts=1_000_000)
    _feed(tracker, **args)
    tracker.evaluate_open("TESTUSDT")
    ilk = db.query_one("SELECT outcome,r_multiple,mfe_r,mae_r,fill_ts "
                       "FROM signals")
    for _ in range(3):
        _feed(tracker, **args)
        tracker.evaluate_open("TESTUSDT")
    son = db.query_one("SELECT outcome,r_multiple,mfe_r,mae_r,fill_ts "
                       "FROM signals")
    assert ilk == son, f"tekrar degerlendirme sonucu degistirdi: {ilk} -> {son}"


def test_no_synthetic_identity_fallbacks_in_stats():
    """HATA SINIFI: eksik veriyi uydurma bir kimlikle doldurmak. cluster_id
    bos oldugunda 'solo<id>' uretilmesi, bagimsiz kanit sayisini 16'dan
    53'e sisirmisti. Eksik veri EKSIK kalmali ve raporlanmali."""
    from app.services import signal_tracker as st
    src = inspect.getsource(st)
    kotu = re.findall(r'cluster_id[^\n]*\bor\s+f?["\']solo', src)
    assert not kotu, f"uydurma kume kimligi kalintisi: {kotu}"
    assert "unclustered_excluded" in src, (
        "etiketsiz kayit sayisi raporlanmali - sessiz haric tutma olmaz")


def test_outcome_decision_never_reads_pre_fill_candles():
    """HATA SINIFI: karar satirlari dolus filtresinden ONCE gelirse dolus
    oncesi mumlar sonucu belirler. Kod duzeninin bu sirayi korudugunu
    dogrular (v3.6-kritik hatasi tam olarak buydu)."""
    from app.services import signal_tracker as st
    src = inspect.getsource(st.SignalTracker._evaluate_signal)
    guard = src.index("if not at_or_after_fill")
    assert guard < src.index("hit_stop ="), "stop kontrolu dolus filtresinden once"
    assert guard < src.index("hit_tp ="), "tp kontrolu dolus filtresinden once"


def test_verifier_does_not_import_tracker_logic():
    """Bagimsiz denetci gercekten bagimsiz olmali: tracker'in degerlendirme
    kodunu kullanirsa ayni hatayi paylasir ve denetim degersizlesir."""
    from app.services import verifier
    src = inspect.getsource(verifier)
    assert "signal_tracker" not in src, "denetci tracker'a bagimli hale gelmis"
    kod = src.split('"""')[2]                     # docstring sonrasi govde
    disari = [l for l in kod.splitlines()
              if l.startswith("import ") or l.startswith("from ")]
    assert disari == ["from __future__ import annotations"], (
        f"denetci disaridan mantik cekiyor: {disari}")
