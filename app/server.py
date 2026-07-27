"""
Flask HTTP katmani.
Cekirdek: /healthz /status /scan /scan/dry
Phase 2:  /performance /signals /export/candles.csv /export/decisions.json
          /backup/info /backup/now  (gist yedekleme durumu + manuel tetik)
Export endpoint'leri ephemeral disk riskine karsi manuel yedek imkani da saglar;
otomatik yedek zaten GistBackup tarafindan yapilir.
"""
from __future__ import annotations

import io
import json

from flask import Flask, jsonify, request

from app.scheduler import Scheduler
from app.services.signal_tracker import SignalTracker
from app.services.state_store import StateStore


def create_app(store: StateStore, scheduler: Scheduler,
               tracker: SignalTracker | None = None,
               gist_backup=None, universe=None) -> Flask:
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", **store.get_meta()})

    @app.get("/status")
    def status():
        payload = {"meta": store.get_meta(), "results": store.get_results()}
        return app.response_class(json.dumps(payload, indent=2),
                                  mimetype="application/json")

    @app.get("/scan")
    def scan():
        results = scheduler.scan_all(send_telegram=True)
        return jsonify([
            {"pair": d.pair, "decision": d.decision.value,
             "direction": d.direction.value, "reason": d.reject_reason}
            for d in results
        ])

    @app.get("/scan/dry")
    def scan_dry():
        results = scheduler.scan_all(send_telegram=False)
        return app.response_class(
            json.dumps([d.contract_dict() for d in results], indent=2),
            mimetype="application/json")

    @app.get("/universe")
    def universe_info():
        """Su an takip edilen parite evreni (mod, sayi, tam liste)."""
        if universe is None:
            return jsonify({"mode": "static", "symbols": None,
                            "note": "universe provider not wired"}), 200
        return app.response_class(json.dumps(universe.describe(), indent=2),
                                  mimetype="application/json")

    # -------------------------------------------------- Phase 2: golge takip
    @app.get("/performance")
    def performance():
        if tracker is None:
            return jsonify({"error": "shadow tracking disabled (SHADOW_TRACKING=false)"}), 404
        return app.response_class(json.dumps(tracker.stats(), indent=2),
                                  mimetype="application/json")

    @app.get("/signals")
    def signals():
        if tracker is None:
            return jsonify({"error": "shadow tracking disabled"}), 404
        limit = min(int(request.args.get("limit", 50)), 500)
        return app.response_class(
            json.dumps(tracker.recent_signals(limit), indent=2),
            mimetype="application/json")

    @app.get("/export/candles.csv")
    def export_candles():
        if tracker is None:
            return jsonify({"error": "shadow tracking disabled"}), 404
        symbol = request.args.get("symbol", "").upper()
        interval = request.args.get("interval", "")
        if not symbol or not interval:
            return jsonify({"error": "usage: /export/candles.csv?symbol=BTCUSDT&interval=15"}), 400
        rows = tracker.export_candles(symbol, interval)
        buf = io.StringIO()
        buf.write("ts,open,high,low,close,volume\n")
        for r in rows:
            buf.write(f"{r['ts']},{r['open']},{r['high']},{r['low']},"
                      f"{r['close']},{r['volume']}\n")
        return app.response_class(
            buf.getvalue(), mimetype="text/csv",
            headers={"Content-Disposition":
                     f"attachment; filename={symbol}_{interval}_candles.csv"})

    @app.get("/export/decisions.json")
    def export_decisions():
        if tracker is None:
            return jsonify({"error": "shadow tracking disabled"}), 404
        rows = tracker.recent_signals(500)
        return app.response_class(json.dumps(rows, indent=2),
                                  mimetype="application/json",
                                  headers={"Content-Disposition":
                                           "attachment; filename=signals_export.json"})

    # ----------------------------------------------- Phase 2: gist yedekleme
    @app.get("/backup/info")
    def backup_info():
        if gist_backup is None:
            return jsonify({"error": "gist sync disabled (GITHUB_TOKEN not set)"}), 404
        return jsonify(gist_backup.info())

    @app.get("/backup/now")
    def backup_now():
        if gist_backup is None:
            return jsonify({"error": "gist sync disabled (GITHUB_TOKEN not set)"}), 404
        ok = gist_backup.sync()
        return jsonify({"synced": ok, **gist_backup.info()}), (200 if ok else 502)

    return app
