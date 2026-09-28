"""
GistBackup - botun KENDI kayit tutma mekanizmasi. Insan mudahalesi gerektirmez.

Dongu:
1. STARTUP RESTORE: DB bos ise (redeploy/restart sonrasi ephemeral disk sifirlanmis)
   gist'ten mum arsivi + sinyal kayitlari geri yuklenir -> takip kaldigi yerden surer.
2. PERIYODIK SYNC: Her GIST_SYNC_INTERVAL_SEC'te (default 1 saat) guncel
   performance.json, signals.json, decisions.json ve candles_*.csv gist'e yazilir.
   Gist her yazimda revizyon tutar -> istatistik gecmisi otomatik arsivlenir.

Gist, MARKER aciklamasiyla otomatik bulunur/olusturulur; GIST_ID env ile
sabitlemek istege baglidir. Sync hatalari sadece loglanir - taramayi durdurmaz.
"""
from __future__ import annotations

import io
import json
import logging
import time
from datetime import datetime, timezone

from app.integrations.gist_client import GistClient
from app.logging_setup import kv
from app.services.signal_tracker import SignalTracker

log = logging.getLogger("gist_backup")

MARKER = "bybit-signal-bot-data (auto-managed, do not rename)"


# GitHub SERT siniri: gist basina 300 dosya. 2026-09-18 arizasi tam bu
# sinirda yasandi (7 istatistik + 150 parite x 2 dilim = 307 -> 422 ve 13
# gun yedeksizlik). Tavan margin birakilarak 280'e cekildi; mum yedegi de
# yalniz EN INCE dilimi tasir (degerlendirme/restore onu kullanir, HTF her
# taramada canli cekilir) -> tipik yuk 7 + 150 = 157 dosya.
MAX_GIST_FILES = 280
# Yedek dosyasi basina satir tavani. 3 yillik kosuda aday kayitlari
# ~115 bin satira cikar; tek dosyada 30 MB'i asar. Tavan asilirsa
# EN YENILER tutulur ve durum 0_backup_health.json'a YAZILIR - sessiz
# kesinti YOK (2026-09-28 dersi: yedegin kapsami denetlenmeliydi).
MAX_BACKUP_ROWS = 60_000
_PRUNE_PER_SYNC = 60       # tek PATCH'i sismemek icin budama parca parca


def _candles_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    buf.write("ts,open,high,low,close,volume\n")
    for r in rows:
        buf.write(f"{r['ts']},{r['open']},{r['high']},{r['low']},"
                  f"{r['close']},{r['volume']}\n")
    return buf.getvalue()


def _parse_candles_csv(text: str) -> list[tuple]:
    rows: list[tuple] = []
    for line in text.strip().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) == 6:
            try:
                rows.append((int(parts[0]), float(parts[1]), float(parts[2]),
                             float(parts[3]), float(parts[4]), float(parts[5])))
            except ValueError:
                continue
    return rows


class GistBackup:
    def __init__(self, client: GistClient, tracker: SignalTracker,
                 symbols, intervals: list[str],
                 sync_interval_sec: int = 3600, pinned_gist_id: str = "",
                 candle_mode: str = "all", candle_max_rows: int = 5000,
                 commentary=None) -> None:
        self._client = client
        self._tracker = tracker
        self._commentary = commentary
        self._symbols = symbols if callable(symbols) else (lambda: list(symbols))
        self._intervals = intervals
        self._candle_mode = candle_mode      # all | signals | off
        self._candle_max_rows = candle_max_rows
        self._interval = sync_interval_sec
        self._gist_id: str | None = pinned_gist_id or None
        self._last_sync: float = 0.0
        self._legacy_cleanup_done: bool = False
        self._last_sync_utc: str | None = None

    # ------------------------------------------------------------- durum
    def set_challengers(self, engine) -> None:
        """Aday motoru sonradan baglanir (scheduler kurar). Yedege
        0_challengers.json olarak girer - izleme boslugu kapanir: aday
        performansi da gist uzerinden bagimsizca denetlenebilir."""
        self._challengers = engine

    def info(self) -> dict:
        return {
            "gist_id": self._gist_id,
            "gist_url": self._client.gist_url(self._gist_id) if self._gist_id else None,
            "last_sync_utc": self._last_sync_utc,
            "sync_interval_sec": self._interval,
        }

    # ------------------------------------------------------------- sync
    def build_files(self) -> dict[str, str]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # "0_" oneki: istatistik dosyalari alfabetik olarak mum CSV'lerinden ONCE
        # gelsin diye. GitHub Gist API buyuk gist'lerde icerik butcesini alfabetik
        # sirayla harcar; stats sona kalirsa API bos icerik dondurur.
        files = {
            "0_performance.json": json.dumps(self._tracker.stats(), indent=2),
            # 2026-09-28: 500 siniri KALKTI - yedek kurtarmaya yetmeliydi
            "0_signals.json": json.dumps(
                self._tracker.recent_signals(100_000), indent=2),
            "0_blocked.json": json.dumps(self._tracker.blocked_signals(300), indent=2),
            "0_decisions.json": json.dumps(self._tracker.recent_decisions(2000), indent=2),
            "0_challengers.json": json.dumps(
                self._challenger_payload(), indent=2),
            # HAM aday kayitlari: ozet degil, KURTARMAYA yeten veri
            # (2026-09-28 dersi - VM diski tek kopyaydi)
            "0_challenger_rows.json": json.dumps(
                self._challenger_rows(), indent=2),
            # cikis laboratuvari (2026-09-01): uzaktan izlenebilsin diye
            # yedege girer - aday verisinde ayni bosluk yasanmisti
            "0_exitlab.json": json.dumps(self._exitlab_payload(), indent=2),
            "0_commentary.json": json.dumps(
                self._commentary.recent(6) if self._commentary else [],
                indent=2),
            "0_backup_health.json": "",      # asagida doldurulur
            "README.md": (f"# bybit-signal-bot data\nAuto-synced: {now}\n\n"
                          "Shadow-tracking stats and backtest dataset. "
                          "Managed by the bot - do not edit manually.\n"),
        }
        # KAPSAM KAYDI: yedegin neyi tasidigi acikca yazilir. "Yedek
        # calisiyor" demek yetmez - NEYI kapsadigi denetlenebilmeli.
        chal_backed = len(json.loads(files["0_challenger_rows.json"]))
        sig_backed = len(json.loads(files["0_signals.json"]))
        chal_total = getattr(self, "_chal_total", chal_backed)
        files["0_backup_health.json"] = json.dumps({
            "generated_utc": now,
            "challenger_rows_total": chal_total,
            "challenger_rows_backed_up": chal_backed,
            "champion_signals_backed_up": sig_backed,
            "row_cap": MAX_BACKUP_ROWS,
            "complete": chal_backed >= chal_total,
            "note": ("complete=false ise en ESKI kayitlar yedege girmedi; "
                     "tavan asildi. Sessiz kesinti yok - burada gorunur."),
        }, indent=2)
        if self._candle_mode == "off":
            return files
        if self._candle_mode == "signals":
            pairs = self._tracker.signal_pairs()   # yalnizca sinyal ureten pariteler
        else:
            pairs = self._symbols()
        # YALNIZ en ince dilim yedeklenir (2026-09-18 arizasi): degerlendirme
        # ve restore LTF mumlarini kullanir; HTF her taramada Bybit'ten taze
        # cekildigi icin arsivi kurtarma acisindan kritik degil.
        iv = self._backup_interval()
        for symbol in pairs:
            if len(files) >= MAX_GIST_FILES:
                log.warning(kv(event="gist_file_budget_hit",
                               limit=MAX_GIST_FILES, pairs=len(pairs),
                               note="fazla parite yedege girmedi"))
                break
            rows = self._tracker.export_candles(symbol, iv)
            files[f"candles_{symbol}_{iv}.csv"] = _candles_csv(
                rows[-self._candle_max_rows:])
        return files

    def _backup_interval(self) -> str:
        """Yedeklenecek mum dilimi: en ince olan (sayisal en kucuk)."""
        return min(self._intervals,
                   key=lambda i: int(i) if str(i).isdigit() else 10**9)

    def _prune_list(self, keep: dict) -> dict[str, None]:
        """Gist'te duran ama artik GONDERILMEYEN mum dosyalari -> silme emri.
        Yalniz candles_* dokunulur; istatistik dosyalari ASLA silinmez.
        Adlar meta-cagriyla alinir (icerik indirilmez); hata -> bos."""
        if self._gist_id is None:
            return {}
        try:
            existing = self._client.list_gist_files(self._gist_id)
        except Exception:
            log.exception(kv(event="gist_prune_list_error"))
            return {}
        stale = [n for n in existing
                 if n.startswith("candles_") and n.endswith(".csv")
                 and n not in keep]
        if not stale:
            return {}
        # butceyi asmamak icin parca parca (kalanlar sonraki senkronda)
        room = max(0, MAX_GIST_FILES - len(keep))
        cut = stale[:min(_PRUNE_PER_SYNC, room)]
        log.info(kv(event="gist_prune", stale=len(stale), removing=len(cut)))
        return {n: None for n in cut}

    def _exitlab_payload(self) -> dict:
        """Cikis lab raporu (V0/V1). Aday motoruyla AYNI DB baglantisini
        kullanir; salt-okur. Hata yedegi COKMEZ (fail-soft, aday deseni)."""
        eng = getattr(self, "_challengers", None)
        if eng is None:
            return {"note": "aday motoru bagli degil"}
        try:
            from app.services import exit_lab
            from app.services.challengers import SAMPLING_REGIME
            return exit_lab.build_report(eng._db, SAMPLING_REGIME)
        except Exception:
            log.exception(kv(event="exitlab_backup_error"))
            return {"note": "cikis lab yedegi hata verdi; sonraki senkronda tekrar"}

    def _challenger_rows(self) -> list[dict]:
        """TUM aday ham kayitlari; motor yoksa/hata verirse bos (fail-soft)."""
        eng = getattr(self, "_challengers", None)
        if eng is None:
            return []
        try:
            rows = eng.export_rows()
        except Exception:
            log.exception(kv(event="challenger_rows_backup_error"))
            return []
        self._chal_total = len(rows)
        if len(rows) > MAX_BACKUP_ROWS:
            log.warning(kv(event="backup_rows_capped", table="challenger",
                           total=len(rows), kept=MAX_BACKUP_ROWS))
            return rows[-MAX_BACKUP_ROWS:]
        return rows

    def _challenger_payload(self) -> dict:
        eng = getattr(self, "_challengers", None)
        if eng is None:
            return {"note": "aday motoru bagli degil"}
        try:
            data = eng.stats()
            data["recent"] = eng.recent(200)
            return data
        except Exception:
            log.exception(kv(event="challenger_backup_error"))
            return {"note": "aday yedegi hata verdi; sonraki senkronda tekrar"}

    def sync(self) -> bool:
        files = self.build_files()
        prune = self._prune_list(files)
        if self._gist_id is None:
            self._gist_id = self._client.find_gist(MARKER)
        if self._gist_id is None:
            self._gist_id = self._client.create_gist(MARKER, files)
            ok = self._gist_id is not None
        else:
            payload = dict(files)
            payload.update(prune)      # artik gonderilmeyen mumlari sil
            if not self._legacy_cleanup_done:
                # eski adsiz-onekli dosyalari bir kez temizle (null = sil)
                for legacy in ("performance.json", "signals.json",
                               "decisions.json"):
                    payload.setdefault(legacy, None)
            ok = self._client.update_gist(self._gist_id, payload)
            if not ok and not self._legacy_cleanup_done:
                # temizlik PATCH'i reddedilmis olabilir; veri sync'ini
                # temizliksiz tekrar dene - yedekleme asla temizlige kurban
                # edilmez
                ok = self._client.update_gist(self._gist_id, dict(files))
            if ok:
                self._legacy_cleanup_done = True
        if ok:
            self._last_sync = time.time()
            self._last_sync_utc = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
            log.info(kv(event="gist_sync_ok", gist_id=self._gist_id,
                        files=len(files)))
        return ok

    def maybe_sync(self) -> None:
        """Scheduler dongusunden cagrilir; araligi dolmadiysa hicbir sey yapmaz."""
        if time.time() - self._last_sync >= self._interval:
            try:
                self.sync()
            except Exception:
                log.exception(kv(event="gist_sync_error"))

    # ----------------------------------------------------------- restore
    def restore_if_empty(self) -> bool:
        """DB bos ise gist'ten geri yukle (redeploy sonrasi self-healing)."""
        if self._tracker.candles_count() > 0:
            return False  # veri zaten var, restore gerekmez
        if self._gist_id is None:
            self._gist_id = self._client.find_gist(MARKER)
        if self._gist_id is None:
            log.info(kv(event="gist_restore_skip", reason="no existing gist"))
            return False
        files = self._client.fetch_gist(self._gist_id)
        if not files:
            return False

        candles_total = 0
        for name, content in files.items():
            if name.startswith("candles_") and name.endswith(".csv"):
                core = name[len("candles_"):-len(".csv")]
                symbol, _, interval = core.rpartition("_")
                if symbol and interval:
                    candles_total += self._tracker.import_candles(
                        symbol, interval, _parse_candles_csv(content))
        signals_total = 0
        sig_file = files.get("0_signals.json") or files.get("signals.json")
        if sig_file:
            try:
                signals_total = self._tracker.import_signals(
                    json.loads(sig_file))
            except (json.JSONDecodeError, TypeError):
                log.warning(kv(event="gist_restore_signals_parse_error"))
        blk_file = files.get("0_blocked.json")
        if blk_file:
            try:
                signals_total += self._tracker.import_signals(
                    json.loads(blk_file))
            except (json.JSONDecodeError, TypeError):
                log.warning(kv(event="gist_restore_blocked_parse_error"))
        # aday ham kayitlari (2026-09-28): portfoy olcumunun tasiyicisi
        chal_total = 0
        chal_file = files.get("0_challenger_rows.json")
        eng = getattr(self, "_challengers", None)
        if chal_file and eng is not None:
            try:
                chal_total = eng.import_rows(json.loads(chal_file))
            except (json.JSONDecodeError, TypeError):
                log.warning(kv(event="gist_restore_challengers_parse_error"))
            except Exception:
                log.exception(kv(event="gist_restore_challengers_error"))
        log.info(kv(event="gist_restore_ok", gist_id=self._gist_id,
                    candles=candles_total, signals=signals_total,
                    challengers=chal_total))
        return True
