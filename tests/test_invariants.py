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


def test_expiry_counts_bars_from_fill_not_from_signal(tmp_path):
    """HATA SINIFI (kural 6): 'dolus oncesi bulasma' sadece MFE ve sonuc
    kararinda degil, IZLEME SURESI sayiminda da vardi. Gecikmeli dolan
    sinyal, ikinci turda degerlendirilince suresi sinyal anindan sayilip
    erken EXPIRED oluyordu."""
    tracker, db = _make_tracker(tmp_path, max_track=3)
    ltf = fx.make_series(np.full(70, 108.0))
    ltf.candles[-1].ts = 1_000_000
    tracker.maybe_track(_signal(), ltf)          # entry 100-101, stop 98, tp 106
    # tur A: 3 mum bolgeye inmez (dolus yok)
    ust = dict(closes=[107.0] * 3, lows=[106.0] * 3, highs=[107.5] * 3)
    _feed(tracker, **ust, start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")
    assert db.query_one("SELECT status FROM signals")["status"] == "PENDING"
    # tur B: 4. mumda dolar
    _feed(tracker, closes=[107.0] * 3 + [100.9], lows=[106.0] * 3 + [100.2],
          highs=[107.5] * 3 + [101.2], start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")
    assert db.query_one("SELECT status FROM signals")["status"] == "FILLED"
    # tur C: dolustan sonra 2 mum daha (toplam tutus 2 < max_track 3)
    _feed(tracker, closes=[107.0] * 3 + [100.9, 100.8, 100.7],
          lows=[106.0] * 3 + [100.2, 100.3, 100.4],
          highs=[107.5] * 3 + [101.2, 101.0, 100.9], start_ts=1_000_000)
    tracker.evaluate_open("TESTUSDT")
    row = db.query_one("SELECT status,outcome FROM signals")
    assert row["outcome"] is None, (
        f"erken EXPIRED: sure sinyal aninden sayilmis ({row['outcome']})")


def test_legacy_filled_rows_without_fill_ts_cannot_become_zombies(tmp_path):
    """HATA SINIFI: 'dolus oncesi' kapisini fill_ts'e baglamak, fill_ts
    kolonundan ONCE dolmus eski kayitlari sonsuz zombiye cevirdi (#57, #6:
    kapi hic acilmiyor, hicbir mum sayilmiyor, sinyal asla kapanmiyor).
    Kural: eksik alan turetilebiliyorsa ham veriden turetilir (kume
    backfill ilkesi); turetilemese bile degerlendirme kilitlenemez."""
    tracker, db = _make_tracker(tmp_path)
    # fill_ts YOK ama fill_price VAR olan eski usul dolmus kayit
    db.execute(
        "INSERT INTO signals(pair,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,fill_price) "
        "VALUES('ESKIUSDT','LONG','2026-07-28T00:00:00Z',1000000,100,101,"
        "98,106,110,2.0,'FILLED',101)")
    mum = [(1000000, 103.0, 100.5),   # dolus temasi (low<=101)
           (1900000, 103.0, 100.8),
           (2800000, 101.0, 97.5)]    # stop
    for ts, hi, lo in mum:
        db.execute("INSERT INTO candles(symbol,interval,ts,open,high,low,"
                   "close,volume) VALUES('ESKIUSDT','15',?,102,?,?,100,1)",
                   (ts, hi, lo))
    # yol 1: migration backfill'i fill_ts'i mumlardan turetir
    assert tracker._backfill_fill_ts() == 1
    assert db.query_one("SELECT fill_ts FROM signals")["fill_ts"] == 1000000
    tracker.evaluate_open("ESKIUSDT")
    row = db.query_one("SELECT status,outcome,r_multiple FROM signals")
    assert row["outcome"] == "LOSS", f"zombi kaldi: {dict(row)}"
    # yol 2: backfill hic kosmasa bile degerlendirici kilitlenmemeli
    db.execute("DELETE FROM signals")
    db.execute(
        "INSERT INTO signals(pair,direction,created_utc,entry_candle_ts,"
        "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,fill_price) "
        "VALUES('ESKIUSDT','LONG','2026-07-28T00:00:00Z',1000000,100,101,"
        "98,106,110,2.0,'FILLED',101)")
    tracker.evaluate_open("ESKIUSDT")
    row = db.query_one("SELECT status,outcome,fill_ts FROM signals")
    assert row["outcome"] == "LOSS" and row["fill_ts"] == 1000000, (
        f"yuruyus-ici turetme calismadi: {dict(row)}")


def test_chart_never_clamps_offscreen_exit_to_edge():
    """HATA SINIFI: pencere disindaki olayi kenara yapistirmak, fiyat o
    seviyeye HIC gelmemis gibi gosterir (JTOUSDT #489, SLXUSDT #475:
    'stop cizgisine gelmemis ki'). Cikis pencerede degilse nokta
    CIZILMEZ; kac mum uzakta oldugu yaziyla soylenir."""
    import re as _re
    from app.dashboard import DASHBOARD_HTML
    js = max(_re.findall(r"<script>(.*?)</script>", DASHBOARD_HTML, _re.S),
             key=len)
    mark = js[js.index("const mark=("):]
    mark = mark[:mark.index("/* Dolus ani")]
    assert "pencere dışı" in mark or "вне окна" in mark, (
        "mark() pencere disi durumunu bildirmiyor")
    # kenara yapistirma yalniz PENCERE ICI dalinda kalmali
    disari = mark.index("ts>last.ts||ts<first.ts")
    clamp = mark.index("idx=cs.length-1")
    assert disari < clamp, "kenara yapistirma pencere-disi kontrolunden once"


def test_chart_window_autosizes_to_include_exit():
    """Sabit dar pencere, saatlerce tutulan islemin cikisini ekran disinda
    birakiyordu. Kapanmis sinyalde pencere cikisi KAPSAMALI."""
    import re as _re
    from app.dashboard import DASHBOARD_HTML
    js = max(_re.findall(r"<script>(.*?)</script>", DASHBOARD_HTML, _re.S),
             key=len)
    assert "closed_utc&&sg.entry_candle_ts" in js, "otomatik pencere yok"
    assert "Math.min(80,Math.max(12,bars+3))" in js, "kapsama hesabi yok"


def test_alarm_registry_has_no_search_logic():
    """HATA SINIFI: veride kalip ARAYAN otomatik dongu, 150 sinyal ve
    onlarca bolme varken tesadufen 'anlamli' bir sey mutlaka bulur -
    p-hacking'in sanayilesmesi. Alarm kaydi yalniz ONCEDEN ILAN EDILMIS
    kosullari kontrol etmeli."""
    import inspect

    from app.services import alarms
    src = inspect.getsource(alarms)
    yasak = ("itertools", "combinations", "permutations", "corr",
             "p_value", "scan_thresholds", "grid")
    bulunan = [k for k in yasak if k in src]
    assert not bulunan, f"alarm kaydinda arama/tarama izi: {bulunan}"
    # her alarm kodunun bir gerekce referansi olmali (ref veya aciklama)
    assert "ONCEDEN" in src.upper() and "ARAMAZ" in src.upper()


def test_audit_summary_reaches_backup_payload(tmp_path):
    """HATA SINIFI: denetim calisir ama sonucu disariya ULASMAZ - agac
    ormanda devrilir. Ozet stats()'a, dolayisiyla gist yedegine girmeli."""
    from app.services.database import Database
    from app.services.signal_tracker import SignalTracker
    db = Database(str(tmp_path / "a.db"))
    tr = SignalTracker(db, "15")
    st = tr.stats()
    assert "outcome_audit" in st["measurement"], "denetim ozeti stats'ta yok"
    assert "max_drawdown_r" in st["measurement"], "maksDD yanlislama icin yok"
