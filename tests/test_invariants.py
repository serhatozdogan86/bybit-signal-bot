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


def test_news_titles_escaped_before_innerhtml():
    """HATA SINIFI (v3.7): DIS kaynak metni escape'siz innerHTML'e girerse
    pano XSS'e acilir. Haber basliklari RSS'ten AYNEN gelir (market_info
    bunu belgeler); kotu niyetli bir feed girdisi <img onerror=...> ile
    DASHBOARD_TOKEN tasiyan oturumda script calistirabilir. Kural: haber
    render'i baslik/kaynak icin esc(), URL icin sema dogrulamasi kullanir."""
    import re as _re
    from app.dashboard import DASHBOARD_HTML
    js = max(_re.findall(r"<script>(.*?)</script>", DASHBOARD_HTML, _re.S),
             key=len)
    news = js[js.index("function renderNews"):]
    news = news[:news.index("\n}") + 2]
    assert "esc(it.title)" in news, "haber basligi escape edilmiyor (XSS)"
    assert "esc(it.source)" in news, "haber kaynagi escape edilmiyor"
    assert "${it.title}" not in news, "ham baslik interpolasyonu kalmis"
    assert "safeUrl(it.url)" in news, "URL sema dogrulamasi yok (javascript:)"


def test_ru_dictionary_has_no_conflicting_duplicate_keys():
    """HATA SINIFI (v3.7): JS nesne literalinde ayni anahtar iki kez FARKLI
    degerle tanimlanirsa sonraki sessizce kazanir - onceki ceviri niyeti
    kaybolur ('açık': 'открыто' vs 'откр.' vakasi). Ayni degerli tekrar
    zararsizdir; farkli degerli tekrar yasaktir."""
    import re as _re
    from app.dashboard import DASHBOARD_HTML
    js = max(_re.findall(r"<script>(.*?)</script>", DASHBOARD_HTML, _re.S),
             key=len)
    ru_src = js[js.index("const RU={"):]
    ru_src = ru_src[:ru_src.index("\n};")]
    pairs = _re.findall(r'"((?:[^"\\]|\\.)+)"\s*:\s*\n?\s*"((?:[^"\\]|\\.)*)"',
                        ru_src)
    seen: dict[str, str] = {}
    conflicts = []
    for k, v in pairs:
        if k in seen and seen[k] != v:
            conflicts.append(f"{k!r}: {seen[k]!r} vs {v!r}")
        seen[k] = v
    assert not conflicts, f"RU sozlugunde celisen tekrar anahtar: {conflicts}"


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


def test_declared_alarms_can_actually_fire(tmp_path):
    """HATA SINIFI (v3.8): alarm kosulu, stats()'in GERCEKTE urettigi
    anahtarla eslesmiyorsa alarm sessizce OLU dogar - MAX_DD boyle bulundu
    (deger measurement icinde, alarm ust duzeyde ariyordu; 35.6R'lik ihlali
    insan yakaladi, alarm hic otmedi). Kural: ilan edilmis her alarm, GERCEK
    tracker.stats() ciktisiyla uctan uca ateslenebildigini kanitlamali."""
    from app.services import alarms
    from app.services.database import Database
    from app.services.signal_tracker import SignalTracker
    db = Database(str(tmp_path / "al.db"))
    tr = SignalTracker(db, "15")
    ins = ("INSERT INTO signals(pair,direction,created_utc,closed_utc,"
           "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,outcome,"
           "fill_price,r_multiple,cluster_id,blocked) VALUES(?,?,?,?,100,"
           "101,98,106,110,2,'CLOSED',?,101,?,?,0)")
    # 25 ayri kumede -1R: hem maksDD>20R hem kume-CI ust siniri<0 uretir
    # tarihler AKTIF kilit (kilit-2) SONRASI: since-lock sayaclari
    # kilit-2'den okur; kilit-1 kohortu arsivdir
    for i in range(25):
        db.execute(ins, (f"L{i:02d}USDT", "LONG", "2026-08-14T00:00:00Z",
                         "2026-08-14T01:00:00Z", "LOSS", -1.0, f"L{700+i}"))
    # etiketsiz kapanmis kayit -> UNCLUSTERED kosulu
    db.execute(ins, ("UNCUSDT", "LONG", "2026-08-14T02:00:00Z",
                     "2026-08-14T03:00:00Z", "WIN", 2.0, ""))
    st = tr.stats()
    rep = alarms.evaluate(
        st, {"outcome_audit": {"checked": 10, "mismatches": 2}}, None,
        last_scan_utc="2026-08-01T00:00:00Z",     # cok eski -> SCAN_STALLED
        last_backup_utc="2026-08-01T00:00:00Z")   # cok eski -> BACKUP_STALE
    codes = {a["code"] for a in rep["alarms"]}
    for beklenen in ("MAX_DD", "EDGE_DEATH", "UNCLUSTERED",
                     "AUDIT_MISMATCH", "SCAN_STALLED", "BACKUP_STALE"):
        assert beklenen in codes, (
            f"{beklenen} alarmi gercek stats() ciktisiyla ateslenemiyor - "
            f"olu alarm (gelenler: {sorted(codes)})")


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


def test_maxdd_metric_matches_declared_scope(tmp_path):
    """HATA SINIFI: ilan edilen kriteri OLCERKEN kapsami kaydirmak.
    config-lock.md #2: 'GERCEK KOHORTTA maksDD > 20R' -> kilit sonrasi.
    Tum zamanlari olcup kriteri o rakamla degerlendirmek sapmadir."""
    from app.services import measurement
    from app.services.database import Database
    from app.services.signal_tracker import SignalTracker
    db = Database(str(tmp_path / "d.db"))
    tr = SignalTracker(db, "15")
    ins = ("INSERT INTO signals(pair,direction,created_utc,closed_utc,"
           "entry_min,entry_max,stop_loss,tp1,tp2,rr,status,outcome,"
           "fill_price,r_multiple,blocked) VALUES('AUSDT','LONG',?,?,100,"
           "101,98,106,110,2.0,'CLOSED',?,101,?,0)")
    # kilit ONCESI buyuk dususu var: +20R sonra -15R
    db.execute(ins, ("2026-07-01T00:00:00Z", "2026-07-01T01:00:00Z", "WIN", 20.0))
    db.execute(ins, ("2026-07-02T00:00:00Z", "2026-07-02T01:00:00Z", "LOSS", -15.0))
    # kilit SONRASI kucuk: +2R sonra -3R  -> kohort DD ~3, tum zaman DD ~16
    db.execute(ins, (measurement.ACTIVE_LOCK_UTC, "2026-08-14T01:00:00Z", "WIN", 2.0))
    db.execute(ins, ("2026-08-14T02:00:00Z", "2026-08-14T03:00:00Z", "LOSS", -3.0))
    kohort = tr.max_drawdown_r()          # varsayilan = ilan edilen kapsam
    tumu = tr.max_drawdown_r(False)
    assert kohort < tumu, "varsayilan kapsam gercek kohort olmali"
    assert 2.5 < kohort < 4.5, f"gercek kohort DD beklenmedik: {kohort}"
    assert tumu > 14.0, f"tum-zaman DD beklenmedik: {tumu}"
    st = tr.stats()["measurement"]
    assert st["max_drawdown_r"] == kohort
    assert st["max_drawdown_r_all"] == tumu


# ------------------------------------ saglayici SESSIZ kirpmasi (ikiz 3b)
# Kaynak: midas-signal-bot v4.40 (2026-08-18). Finnhub takvim ucu ~1500
# satirda SESSIZCE kirpiyordu: HTTP 200, hata yok, eksik veri TAM sanildi.
# Kirpilan uc ESKI uctu - yani "en eski veri sessizce dusuyor".
#
# Ikiz kontrolu (VM'den canli olcum, 2026-08-18):
#   /v5/market/kline           limit=1500 istendi -> retCode=0, 1000 satir
#   /v5/market/funding/history 200 gun istendi    -> retCode=0, 66.3 gun
# Ikisinde de retCode=0. Saglayici "eksik verdim" DEMIYOR.
#
# Funding tavani parite basina degisir (824 paritede olculdu):
#   8 saatlik funding (374 parite) -> 200 kayit =  66.7 gun
#   4 saatlik funding (408 parite) -> 200 kayit =  33.3 gun
#   1 saatlik funding (  2 parite) -> 200 kayit =   8.3 gun
# Yani evrenin YARISINDAN fazlasi 33 gunluk pencereyle sinirli.
#
# Bu bir MUHASEBE hatasidir (Kural 3b/2): _backfill_funding eksik topladigi
# funding'i `funding_r_real` olarak deftere yazar; maliyet oldugundan KUCUK,
# net-R oldugundan IYI gorunur - ve go-live kapisi (kume-CI) o sayilardan
# hesaplanir. Sessiz eksiklik, kapiyi yanlis yonde acar.
#
# Degismezlik: saglayici tavanina DAYANAN yanit TAM sayilamaz. Ya sayfalanip
# tamamlanir ya da acikca eksik bildirilir; sessizce kabul EDILEMEZ.


class _FakeResp:
    status_code = 200

    def __init__(self, payload: dict) -> None:
        self._p = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._p


class _CappedFundingSession:
    """Bybit'i taklit eder: her istekte EN COK 200 kayit, EN YENI uctan.

    Gercek uc de boyle davranir (olculdu): startTime cok geriye verilse
    bile yalniz son 200 kayit doner, eskiler SESSIZCE dusurulur.
    """

    CAP = 200

    def __init__(self, all_rows: list[dict]) -> None:
        self._all = all_rows
        self.calls: list[dict] = []

    def get(self, url, params=None, timeout=None):  # noqa: ANN001
        self.calls.append(dict(params or {}))
        start = int((params or {}).get("startTime", 0))
        end = int((params or {}).get("endTime", 10 ** 18))
        sel = [r for r in self._all
               if start <= int(r["fundingRateTimestamp"]) <= end]
        sel.sort(key=lambda r: int(r["fundingRateTimestamp"]))
        sel = sel[-self.CAP:]          # tavan: eski uc sessizce duser
        sel.reverse()                  # Bybit sirasi: yeniden eskiye
        return _FakeResp({"retCode": 0, "result": {"list": sel}})


def _funding_rows(n: int, t0: int, step_ms: int) -> list[dict]:
    return [{"fundingRate": "0.0001",
             "fundingRateTimestamp": str(t0 + i * step_ms)} for i in range(n)]


def test_funding_history_completes_range_despite_provider_cap():
    """HATA SINIFI: saglayici tavanina dayanan yaniti TAM sanmak.

    4 saatlik funding'li bir paritede 45 gunluk bir islem 270 kayit eder;
    tavan 200'dur. Tek istek en yeni 200'u getirir, ilk 70 kayit SESSIZCE
    duser -> funding maliyeti eksik toplanir. Istemci araligi tamamlamali.
    """
    from app.integrations.bybit_client import BybitClient
    step = 4 * 3600 * 1000                     # 4 saat: evrenin yarisi
    n = 270                                    # tavanin (200) UZERINDE
    t0 = 1_700_000_000_000
    rows = _funding_rows(n, t0, step)
    c = BybitClient("https://ornek")
    c._session = _CappedFundingSession(rows)
    got = c.get_funding_history("BTCUSDT", t0, t0 + (n - 1) * step)
    assert got is not None, "hata yok, None donmemeli"
    assert len(got) == n, (
        f"aralik tamamlanmadi: {len(got)}/{n} kayit. Saglayici tavani "
        f"sessizce kabul edildi - funding maliyeti eksik toplanir.")
    ts = [int(r["fundingRateTimestamp"]) for r in got]
    assert ts == sorted(ts), "kayitlar zaman sirasinda olmali"
    assert len(set(ts)) == n, "sayfalama mukerrer kayit uretmemeli"
    assert ts[0] == t0, "EN ESKI kayit dusmus - kirpilan uc tam da bu"


def test_funding_history_single_page_makes_one_call():
    """Sayfalama, tavana DAYANMAYAN yaniti bosuna tekrar cekmemeli."""
    from app.integrations.bybit_client import BybitClient
    step = 8 * 3600 * 1000
    t0 = 1_700_000_000_000
    rows = _funding_rows(12, t0, step)         # tavanin cok altinda
    c = BybitClient("https://ornek")
    sess = _CappedFundingSession(rows)
    c._session = sess
    got = c.get_funding_history("BTCUSDT", t0, t0 + 11 * step)
    assert got is not None and len(got) == 12
    assert len(sess.calls) == 1, (
        f"gereksiz sayfalama: {len(sess.calls)} istek atildi")


def test_kline_request_never_exceeds_provider_cap():
    """HATA SINIFI: saglayicinin sessizce kirptigi limiti istemek.

    Olculdu: limit=1500 -> retCode=0, 1000 satir. Hata YOK. Tavanin
    uzerinde limit istemek, 'istedigim kadar geldi' yanilsamasi uretir.
    """
    from app.integrations import bybit_client as bc
    gonderilen: dict = {}

    class _S:
        def get(self, url, params=None, timeout=None):  # noqa: ANN001
            gonderilen.update(params or {})
            n = int((params or {}).get("limit", 0))
            return _FakeResp({"retCode": 0,
                              "result": {"list": [["0"] * 7] * min(n, 1000)}})

    c = bc.BybitClient("https://ornek")
    c._session = _S()
    c.get_kline_rows("BTCUSDT", "D", limit=1500)
    assert gonderilen["limit"] <= bc._KLINE_CAP, (
        f"tavan ustu limit istendi: {gonderilen['limit']} > "
        f"{bc._KLINE_CAP} - saglayici sessizce kirpar")


# --------------------------------------------------------- ikiz: gap dolumu
# IKIZ TARAMASI (2026-08-21). Kaynak: midas kilit-2 kohortunda JNJ +7.91R.
# midas'in `_evaluate_signal` bloğunda bir GAP DALI var: LONG'da mumun
# ACILISI entry_min'in altindaysa dolum acilistan yazilir. Dolum stop'a
# yaklastigi icin R paydasi kuculur ve R sisir. Olculdu (midas): tasarim
# riski 4.00 -> fiili 1.475, R +2.29 yerine +7.91.
#
# Bu depoda o dal YOK: dolum her zaman bolgenin ilk degen kenarindan
# (LONG entry_max, SHORT entry_min). Bybit defterinde 1337 kapanmis dolum
# olculdu, 1337'sinin de dolum fiyati TAM kenarda.
#
# Karsi-olgusal olcum (midas kurali bu deftere uygulansaydi): 1337
# kaydin 173'u (%12.9) gap dalini tetiklerdi, payda ortalama 3.39 kat
# kucuk olurdu, o alt kumenin toplami +4.03R yerine +350.89R cikardi.
#
# Asagidaki test o dalin buraya SONRADAN tasinmasini engeller.
# Ayrinti: docs/ikiz-depo-notu.md, madde G1.

def test_gap_acilisinda_bile_dolum_bolge_kenarindan(tmp_path):
    """HATA SINIFI: dolum fiyatini mumun acilisina baglamak.

    Acilis bolgenin otesine gap yaptiginda 'daha iyi fiyattan dolduk'
    demek defteri kotumser degil IYIMSER yapar: dolum stop'a yaklasir,
    R paydasi kuculur, kazananlar sisir. Zarar tarafi -1R'ye capali
    oldugu icin etki TEK YONLUDUR (beklentiyi yukari iter).

    Bu test dolumun bolge kenarina bagli kalmasini zorunlu kilar.
    """
    tracker, db = _make_tracker(tmp_path)
    d = _signal()                       # LONG, bolge 100-101, stop 98, tp1 106
    ltf = fx.make_series(np.full(70, 101.5))
    ltf.candles[-1].ts = 1_000_000
    assert tracker.maybe_track(d, ltf) is True

    # Mum 1: acilis 99.0 -> bolgenin (100.0) ALTINDA gap. Bolge yine de
    #        katediliyor (high 101.2 >= entry_max 101).
    # Mum 2: tp1 106 gorulur.
    db.executemany(
        "INSERT OR IGNORE INTO candles(symbol,interval,ts,open,high,low,"
        "close,volume) VALUES(?,?,?,?,?,?,?,?)",
        [("TESTUSDT", "15", 1_000_000, 99.0, 101.2, 98.5, 100.5, 1000.0),
         ("TESTUSDT", "15", 1_900_000, 102.0, 106.5, 101.5, 106.2, 1000.0)])
    tracker.evaluate_open("TESTUSDT")

    row = db.query_one("SELECT * FROM signals")
    assert row["fill_price"] == 101.0, (
        f"dolum {row['fill_price']} - bolge kenari 101.0 olmali. Acilisa "
        "(99.0) baglanmis olabilir: midas'in gap dali buraya tasinmis.")
    risk = row["fill_price"] - row["stop_loss"]
    assert abs(risk - 3.0) < 1e-9, f"R paydasi kaydi: {risk} (beklenen 3.0)"
    assert row["outcome"] == "WIN"
    # kenar dolumu: (106-101)/3 = 1.67R | gap dali olsaydi (106-99)/1 = 7.0R
    assert abs(row["r_multiple"] - 1.67) < 0.02, (
        f"R {row['r_multiple']} - gap dali tasinmis olabilir (7.0R'ye yakinsa)")
    assert row["r_multiple"] < 2.0, "R sismis - payda kucultulmus"
