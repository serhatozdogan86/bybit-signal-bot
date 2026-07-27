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
                 candle_mode: str = "all", candle_max_rows: int = 5000) -> None:
        self._client = client
        self._tracker = tracker
        self._symbols = symbols if callable(symbols) else (lambda: list(symbols))
        self._intervals = intervals
        self._candle_mode = candle_mode      # all | signals | off
        self._candle_max_rows = candle_max_rows
        self._interval = sync_interval_sec
        self._gist_id: str | None = pinned_gist_id or None
        self._last_sync: float = 0.0
        self._last_sync_utc: str | None = None

    # ------------------------------------------------------------- durum
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
        files = {
            "README.md": (f"# bybit-signal-bot data\nAuto-synced: {now}\n\n"
                          "Shadow-tracking stats and backtest dataset. "
                          "Managed by the bot - do not edit manually.\n"),
            "performance.json": json.dumps(self._tracker.stats(), indent=2),
            "signals.json": json.dumps(self._tracker.recent_signals(500), indent=2),
            "decisions.json": json.dumps(self._tracker.recent_decisions(2000), indent=2),
        }
        if self._candle_mode == "off":
            return files
        if self._candle_mode == "signals":
            pairs = self._tracker.signal_pairs()   # yalnizca sinyal ureten pariteler
        else:
            pairs = self._symbols()
        for symbol in pairs:
            for interval in self._intervals:
                rows = self._tracker.export_candles(symbol, interval)
                files[f"candles_{symbol}_{interval}.csv"] = _candles_csv(
                    rows[-self._candle_max_rows:])
        return files

    def sync(self) -> bool:
        files = self.build_files()
        if self._gist_id is None:
            self._gist_id = self._client.find_gist(MARKER)
        if self._gist_id is None:
            self._gist_id = self._client.create_gist(MARKER, files)
            ok = self._gist_id is not None
        else:
            ok = self._client.update_gist(self._gist_id, files)
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
        if "signals.json" in files:
            try:
                signals_total = self._tracker.import_signals(
                    json.loads(files["signals.json"]))
            except (json.JSONDecodeError, TypeError):
                log.warning(kv(event="gist_restore_signals_parse_error"))
        log.info(kv(event="gist_restore_ok", gist_id=self._gist_id,
                    candles=candles_total, signals=signals_total))
        return True
