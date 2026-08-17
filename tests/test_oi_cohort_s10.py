"""P4 golge-kohort (S2 dOI etiketi) + S10 52w-HIGH canli entegrasyonu.

Iki dalganin davranis testleri (on-kayitlar: docs/ideas.md 2026-08-16):
- OI etiketi SALT metadata'dir: karar yolu okumaz, stats kohort blogu
  yalniz olcum raporlar.
- S10 secimi saf fonksiyondadir; haftalik gecit Pazartesi + haftada bir;
  kume = hafta.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from app.config.settings import Settings
from app.scheduler import Scheduler
from app.services.challengers import (ChallengerEngine, S2_OI_RISE,
                                      weekly_52w_selection)
from app.services.database import Database
from app.services.state_store import InMemoryStateStore
from tests import fixtures as fx

DAY = 86_400_000


def _eng(tmp_path):
    db = Database(str(tmp_path / "c.db"))
    return ChallengerEngine(db, "15"), db


def _s2_fire(eng):
    """S2 kirilimi uret (test_s2_donchian... ile ayni kurgu)."""
    htf = fx.make_series(np.full(60, 100.0), interval="240")
    closes = np.concatenate([np.full(98, 100.0), [100.0, 106.0]])
    ltf = fx.make_series(closes)
    assert eng.on_scan("AUSDT", htf, ltf, None) >= 1


# ------------------------------------------------------- P4 golge-kohort
def test_s2_doi_tag_flow_and_cohort_stats(tmp_path):
    eng, db = _eng(tmp_path)
    _s2_fire(eng)
    sid = eng.untagged_s2("AUSDT")
    assert sid is not None                      # taze S2 etiket bekliyor
    eng.set_doi(sid, 0.07)                      # esik ustu -> artisli
    assert eng.untagged_s2("AUSDT") is None     # bir kez etiketlenir
    # kapat (WIN) ve kohort istatistigini dogrula
    row = db.query_one("SELECT * FROM challenger_signals WHERE id=?", (sid,))
    db.executemany(
        "INSERT OR IGNORE INTO candles(symbol,interval,ts,open,high,low,"
        "close,volume) VALUES('AUSDT','15',?,?,?,?,?,1000)",
        [(row["entry_ts"] + 900_000, row["entry"], row["tp"] + 1,
          row["entry"] - 0.1, row["tp"])])
    eng.evaluate_open("AUSDT")
    s2 = eng.stats()["strategies"]["S2_DONCHIAN"]
    coh = s2["oi_cohorts"]
    assert coh["threshold"] == S2_OI_RISE
    assert coh["oi_artisli"]["closed"] == 1
    assert coh["oi_artisli"]["clusters"] == 1
    assert coh["oi_artissiz"]["closed"] == 0
    assert coh["unlabeled_closed"] == 0


def test_untagged_s2_age_limit(tmp_path):
    """Inceleme 2026-08-16: etiket YALNIZ dogum taramasinda yazilabilir.
    Yaslanan (dogum aninda OI'si alinamayan / deploy oncesi) kayit sonradan
    etiketlenemez - kohort 'dogum ani dOI'si' olarak kalir."""
    eng, db = _eng(tmp_path)
    _s2_fire(eng)
    db.execute("UPDATE challenger_signals "
               "SET created_utc='2026-08-01T00:00:00Z'")
    assert eng.untagged_s2("AUSDT") is None


def test_s2_unlabeled_closed_counted(tmp_path):
    eng, db = _eng(tmp_path)
    _s2_fire(eng)
    row = db.query_one("SELECT * FROM challenger_signals")
    db.executemany(
        "INSERT OR IGNORE INTO candles(symbol,interval,ts,open,high,low,"
        "close,volume) VALUES('AUSDT','15',?,?,?,?,?,1000)",
        [(row["entry_ts"] + 900_000, row["entry"], row["tp"] + 1,
          row["entry"] - 0.1, row["tp"])])
    eng.evaluate_open("AUSDT")
    coh = eng.stats()["strategies"]["S2_DONCHIAN"]["oi_cohorts"]
    assert coh["unlabeled_closed"] == 1         # etiketsiz DURUSTCE sayilir
    assert coh["oi_artisli"]["closed"] == 0


def test_doi_metadata_does_not_change_decisions(tmp_path):
    """Etiket SALT metadata: ayni girdiyle uretim/degerlendirme ayni."""
    eng, db = _eng(tmp_path)
    _s2_fire(eng)
    before = db.query_one("SELECT direction,entry,stop,tp,timeout_bars "
                          "FROM challenger_signals")
    sid = eng.untagged_s2("AUSDT")
    eng.set_doi(sid, -0.5)
    after = db.query_one("SELECT direction,entry,stop,tp,timeout_bars "
                         "FROM challenger_signals")
    assert dict(before) == dict(after)


# ------------------------------------------------------- S10 secim (saf)
def _daily(n, start=100.0, step=0.5, t0=1_000_000 * DAY):
    return [[t0 + i * DAY, start + i * step, (start + i * step) * 1.005,
             (start + i * step) * 0.995, start + i * step]
            for i in range(n)]


def test_weekly_52w_selection_two_conditions(tmp_path):
    daily = {"TOPUSDT": _daily(120)}            # yukselen: yakinlik ~1
    for j in range(10):                          # dolgu: yakinlik ~0.77
        bars = _daily(120, start=100.0, step=0.0)
        for b in bars[:5]:
            b[4] = 130.0                        # eski zirve
        daily[f"MID{j}USDT"] = bars
    sel = weekly_52w_selection(daily)
    assert len(sel) == 1 and sel[0][1] == "TOPUSDT"
    prox, sym, entry, stop, last_ts = sel[0]
    assert prox >= 0.90 and stop < entry
    # kisa gecmis elenir
    assert weekly_52w_selection({"NEWUSDT": _daily(50)}) == []


def test_weekly_52w_selection_drops_stale_symbols(tmp_path):
    """Inceleme 2026-08-16: kline'i geride kalmis (duraklamis) parite sepete
    GIREMEZ - gunler oncesinin fiyatiyla geriye donuk giris yazilirdi."""
    fresh = _daily(120)
    stale = _daily(120)[:-3]                    # 3 gun geride
    sel = weekly_52w_selection({"FRESHUSDT": fresh, "STALEUSDT": stale})
    assert [s[1] for s in sel] == ["FRESHUSDT"]


def test_s10_on_weekly_writes_once_per_week(tmp_path):
    eng, db = _eng(tmp_path)
    daily = {"TOPUSDT": _daily(120)}
    assert eng.on_weekly_52w(daily, "2026-W34") == 1
    row = db.query_one("SELECT * FROM challenger_signals WHERE "
                       "strategy='S10_52WHIGH'")
    assert row["direction"] == "LONG"
    # kume = GECIDIN hafta anahtari (per-sembol ts degil - inceleme bulgusu)
    assert row["cluster_id"] == "S10_52WHIGH:L2026-W34"
    assert row["timeout_bars"] == 672
    assert row["entry_ts"] == _daily(120)[-1][0] + DAY   # Pazartesi 00:00
    # ayni hafta tekrar -> dedup (kume ayni)
    assert eng.on_weekly_52w(daily, "2026-W34") == 0
    n = db.query_one("SELECT COUNT(*) n FROM challenger_signals")["n"]
    assert n == 1


def test_s10_week_meta_flag(tmp_path):
    eng, _ = _eng(tmp_path)
    assert not eng.weekly_52w_done("2026-W34")
    eng.mark_weekly_52w("2026-W34")
    assert eng.weekly_52w_done("2026-W34")
    assert not eng.weekly_52w_done("2026-W35")


# ------------------------------------------- market data yardimcilari
class _FakeClient:
    def __init__(self, oi_rows=None, kline_rows=None):
        self._oi, self._kline = oi_rows, kline_rows

    def get_open_interest_rows(self, symbol, limit=25):
        return self._oi

    def get_kline_rows(self, symbol, interval, limit=200):
        return self._kline


def test_md_oi_change_24h():
    from app.services.market_data_service import MarketDataService
    rows = [{"openInterest": "110", "timestamp": str(1000 + i)}
            for i in range(25)]
    rows[-1]["openInterest"] = "100"            # en eski (24s once)
    md = MarketDataService(_FakeClient(oi_rows=rows))
    assert abs(md.get_oi_change_24h("X") - 0.10) < 1e-9
    # eksik/bozuk veri -> None (etiket bos kalir)
    assert MarketDataService(_FakeClient(oi_rows=rows[:5])) \
        .get_oi_change_24h("X") is None
    assert MarketDataService(_FakeClient(oi_rows=None)) \
        .get_oi_change_24h("X") is None
    bad = [dict(r) for r in rows]
    bad[-1]["openInterest"] = "0"
    assert MarketDataService(_FakeClient(oi_rows=bad)) \
        .get_oi_change_24h("X") is None


def test_md_daily_closed_bars_drops_only_forming():
    """Inceleme 2026-08-16: kosulsuz son-bar atmak yerine ZAMAN kontrolu.
    Olusan (bugunku) mum atilir; hepsi kapanmissa hicbiri atilmaz."""
    import time as _t

    from app.services.market_data_service import MarketDataService
    today = (int(_t.time() * 1000) // DAY) * DAY
    # en yeni bar bugunku (olusan) -> atilmali
    kline = [[str(today - i * DAY), "100", "101", "99", "100", "1", "1"]
             for i in range(5)]
    bars = MarketDataService(_FakeClient(kline_rows=kline)) \
        .get_daily_closed_bars("X")
    assert len(bars) == 4
    assert bars[-1][0] == today - DAY            # son KAPANMIS gun
    assert bars[0][0] < bars[-1][0]              # artan sira
    # duraklamis parite: tum barlar eski (hepsi kapanmis) -> HICBIRI atilmaz
    old = [[str(today - (10 + i) * DAY), "100", "101", "99", "100", "1", "1"]
           for i in range(5)]
    bars2 = MarketDataService(_FakeClient(kline_rows=old)) \
        .get_daily_closed_bars("X")
    assert len(bars2) == 5


# --------------------------------------------- scheduler haftalik gecidi
class _StubMD:
    """Sabit seriler + gunluk mumlar + OI donduren sahte veri servisi."""

    def __init__(self):
        self.daily_calls = 0

    def get_series(self, symbol, interval):
        return fx.make_series(np.full(60, 100.0), symbol, interval)

    def get_all_tickers(self):
        return []

    def get_daily_closed_bars(self, symbol, limit=380):
        self.daily_calls += 1
        return _daily(120)

    def get_oi_change_24h(self, symbol):
        return 0.07


def _sched(tmp_path):
    from app.services.signal_tracker import SignalTracker
    settings = Settings(TELEGRAM_ENABLED=False, SYMBOLS="TOPUSDT",
                        SHADOW_TRACKING=True,
                        DB_PATH=str(tmp_path / "s.db"))
    md = _StubMD()
    tracker = SignalTracker(Database(str(tmp_path / "s.db")), "15")
    sched = Scheduler(settings, md, InMemoryStateStore(), None,
                      tracker=tracker)
    return sched, md


def test_scheduler_weekly_pass_monday_gate(tmp_path):
    sched, md = _sched(tmp_path)
    assert sched.challengers is not None
    monday = datetime(2026, 8, 17, 1, 0, tzinfo=timezone.utc)   # Pazartesi
    tuesday = datetime(2026, 8, 18, 1, 0, tzinfo=timezone.utc)
    # Sali: hicbir sey yapmaz
    sched._s10_weekly_pass(now=tuesday)
    assert md.daily_calls == 0
    # Pazartesi: sepet yazilir + meta isaretlenir
    sched._s10_weekly_pass(now=monday)
    assert md.daily_calls == 1
    assert sched.challengers.weekly_52w_done("2026-W34")
    # ayni gun ikinci tarama: tekrar CEKMEZ (haftada bir)
    sched._s10_weekly_pass(now=monday)
    assert md.daily_calls == 1
