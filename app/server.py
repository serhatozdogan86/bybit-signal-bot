"""Flask HTTP katmani: healthcheck + durum + manuel tarama endpoint'leri."""
from __future__ import annotations

import json

from flask import Flask, jsonify

from app.scheduler import Scheduler
from app.services.state_store import StateStore


def create_app(store: StateStore, scheduler: Scheduler) -> Flask:
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        """Render health check + keep-alive ping hedefi."""
        meta = store.get_meta()
        return jsonify({"status": "ok", **meta})

    @app.get("/status")
    def status():
        """Son analiz sonuclari - sabit contract JSON (pair -> Decision)."""
        payload = {"meta": store.get_meta(), "results": store.get_results()}
        return app.response_class(json.dumps(payload, indent=2),
                                  mimetype="application/json")

    @app.get("/scan")
    def scan():
        """Manuel tarama; Telegram'a da gonderir. Ozet doner."""
        results = scheduler.scan_all(send_telegram=True)
        return jsonify([
            {"pair": d.pair, "decision": d.decision.value,
             "direction": d.direction.value, "reason": d.reject_reason}
            for d in results
        ])

    @app.get("/scan/dry")
    def scan_dry():
        """Manuel tarama; Telegram'a GONDERMEZ. Tam contract JSON doner (debug)."""
        results = scheduler.scan_all(send_telegram=False)
        return app.response_class(
            json.dumps([d.contract_dict() for d in results], indent=2),
            mimetype="application/json",
        )

    return app
