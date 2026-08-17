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

from pathlib import Path

from flask import Flask, Response, jsonify, redirect, request

from app.dashboard import DASHBOARD_HTML
from app.scheduler import ScanBusy, Scheduler
from app.services.signal_tracker import SignalTracker
from app.services.state_store import StateStore


def _read_doc(name: str) -> str | None:
    path = Path(__file__).resolve().parent.parent / "docs" / name
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _send_doc(name: str, mimetype: str):
    """docs/ altindaki dokumani servis et; yoksa 404 (kilit disi, saf sunum)."""
    path = Path(__file__).resolve().parent.parent / "docs" / name
    if not path.is_file():
        return jsonify({"error": f"{name} bulunamadi"}), 404
    return Response(path.read_bytes(), mimetype=mimetype)


# Jeton olsa bile daima acik kalan rotalar: izleme zinciri kirilmamali
# (UptimeRobot /health'i yoklar; 503 = alarm) ve PWA kabugu kimliksiz yuklenir.
_PUBLIC_PATHS = frozenset({"/health", "/healthz", "/manifest.webmanifest"})


def create_app(store: StateStore, scheduler: Scheduler,
               tracker: SignalTracker | None = None,
               gist_backup=None, universe=None,
               market_info=None, commentary=None,
               auth_token: str = "") -> Flask:
    app = Flask(__name__)
    token = (auth_token or "").strip()

    def _authorized() -> bool:
        """Jeton bos -> auth kapali (geriye donuk uyumlu, kilitlenme yok)."""
        if not token:
            return True
        given = (request.headers.get("X-Auth-Token")
                 or request.args.get("k")
                 or request.cookies.get("k") or "")
        # sabit sureli karsilastirma: jeton uzunlugu sizmasin
        import hmac
        return hmac.compare_digest(given, token)

    @app.before_request
    def _guard():
        if not token or request.path in _PUBLIC_PATHS:
            return None
        if request.path.startswith("/icon-"):
            return None
        if _authorized():
            return None
        return jsonify({"error": "unauthorized",
                        "hint": "X-Auth-Token basligi veya ?k= parametresi"}), 401

    @app.get("/")
    def dashboard():
        """Operasyon konsolu - sinyaller ve performans buradan izlenir."""
        resp = app.response_class(DASHBOARD_HTML, mimetype="text/html")
        if token and request.args.get("k"):
            # ?k=... ile gelindi: cereze yaz ve URL'yi temizle ki jeton
            # tarayici gecmisinde/ekran goruntusunde dolasmasin
            resp = redirect("/")
            resp.set_cookie("k", token, max_age=60 * 60 * 24 * 365,
                            httponly=True, samesite="Lax",
                            secure=request.is_secure)
        return resp

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", **store.get_meta()})

    @app.get("/manifest.webmanifest")
    def manifest():
        """PWA manifesti: pano ana ekrana kurulabilir uygulama olur."""
        return jsonify({
            "name": "signal-engine · gölge takip",
            "short_name": "signal-engine",
            "description": "Bybit gölge sinyal motoru operasyon panosu",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#F6F4FB",
            "theme_color": "#6D28D9",
            "icons": [
                {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png",
                 "purpose": "any"},
                {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png",
                 "purpose": "any maskable"},
            ],
        })

    @app.get("/icon-<int:size>.png")
    def app_icon(size: int):
        path = (Path(__file__).resolve().parent / "static" / f"icon-{size}.png")
        if not path.is_file():
            return jsonify({"error": "icon not found"}), 404
        return Response(path.read_bytes(), mimetype="image/png")

    @app.get("/signal/<int:sig_id>/chart")
    def signal_chart(sig_id: int):
        """Sinyalin kanit paketi (mumlar + plan + teyitler)."""
        if tracker is None:
            return jsonify({"error": "shadow tracking disabled"}), 404
        before = min(max(int(request.args.get("before", 24)), 8), 80)
        after = min(max(int(request.args.get("after", 24)), 8), 80)
        data = tracker.signal_chart(sig_id, before=before, after=after)
        if data is None:
            return jsonify({"error": "signal not found"}), 404
        return app.response_class(json.dumps(data, indent=2),
                                  mimetype="application/json")

    @app.get("/kitap")
    def kitap():
        """Ders kitabi (HTML). ?lang=ru varsa Rusca surum (hazir degilse TR)."""
        if request.args.get("lang") == "ru":
            ru = Path(__file__).resolve().parent.parent / "docs" / "ders-kitabi-ru.html"
            if ru.is_file():
                return Response(ru.read_bytes(), mimetype="text/html; charset=utf-8")
            # RU surumu hazirlaninca otomatik devreye girer; simdilik TR + not
            html = _read_doc("ders-kitabi.html")
            if html is None:
                return jsonify({"error": "kitap bulunamadi"}), 404
            banner = ("<div style=\"background:#EAF0FB;border:1px solid #2563EB;"
                      "border-radius:10px;padding:12px 16px;margin:0 0 20px;"
                      "font-family:Inter,sans-serif;font-size:13.5px;color:#2A241B\">"
                      "\u0420\u0443\u0441\u0441\u043a\u0430\u044f \u0432\u0435\u0440\u0441\u0438\u044f "
                      "\u0443\u0447\u0435\u0431\u043d\u0438\u043a\u0430 \u0433\u043e\u0442\u043e\u0432\u0438\u0442\u0441\u044f. "
                      "\u041d\u0438\u0436\u0435 \u2014 \u0442\u0443\u0440\u0435\u0446\u043a\u0430\u044f "
                      "\u0432\u0435\u0440\u0441\u0438\u044f.</div>")
            html = html.replace('<div class="page">', '<div class="page">' + banner, 1)
            return Response(html, mimetype="text/html; charset=utf-8")
        return _send_doc("ders-kitabi.html", "text/html; charset=utf-8")

    @app.get("/kitap.pdf")
    def kitap_pdf():
        """Ders kitabinin basiliya hazir A4 surumu (?lang=ru destekli)."""
        if request.args.get("lang") == "ru":
            ru = Path(__file__).resolve().parent.parent / "docs" / "ders-kitabi-ru.pdf"
            if ru.is_file():
                return Response(ru.read_bytes(), mimetype="application/pdf")
        return _send_doc("ders-kitabi.pdf", "application/pdf")

    @app.get("/health")
    def health():
        """v3.5-P1 dead-man's switch: son tarama 40 dk'dan eskiyse 503.

        UptimeRobot bu rotayi 5 dk'da bir yoklar; 503 -> alarm. Yan fayda:
        duzenli ping Render free katmanini uyanik tutar.
        """
        from datetime import datetime, timezone
        meta = store.get_meta()
        last = meta.get("last_scan_utc") or meta.get("last_scan")
        age = None
        ok = False
        if last:
            try:
                t = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc)
                age = int((datetime.now(timezone.utc) - t).total_seconds())
                ok = age < 2400
            except ValueError:
                pass
        code = 200 if ok else 503
        return jsonify({"ok": ok, "last_scan_utc": last,
                        "age_sec": age}), code

    @app.get("/status")
    def status():
        payload = {"meta": store.get_meta(), "results": store.get_results()}
        return app.response_class(json.dumps(payload, indent=2),
                                  mimetype="application/json")

    @app.post("/scan")
    def scan():
        """Manuel tarama. POST: durum degistirir (GET degil - onbellek/prefetch
        kazara tetiklemesin). Arka plan taramasi surerken 409 doner."""
        try:
            results = scheduler.scan_all(send_telegram=True)
        except ScanBusy:
            return jsonify({"error": "scan_in_progress",
                            "hint": "arka plan taramasi suruyor"}), 409
        return jsonify([
            {"pair": d.pair, "decision": d.decision.value,
             "direction": d.direction.value, "reason": d.reject_reason}
            for d in results
        ])

    @app.post("/scan/dry")
    def scan_dry():
        try:
            results = scheduler.scan_all(send_telegram=False)
        except ScanBusy:
            return jsonify({"error": "scan_in_progress"}), 409
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

    @app.get("/measurement")
    def measurement_view():
        """v3.6 teshis paketi: kume P&L, kohort dagilimlari, NF anatomisi,
        MFE/MAE, guven permutasyonu, funding v1 onizleme, kapi gunlugu."""
        if tracker is None:
            return jsonify({"error": "shadow tracking disabled"}), 404
        return app.response_class(
            json.dumps(tracker.diagnostics(), indent=2),
            mimetype="application/json")

    @app.get("/verify")
    def verify_view():
        """Bagimsiz sonuc denetimi: kayitlar mum arsiviyle celisiyor mu?"""
        if tracker is None:
            return jsonify({"error": "shadow tracking disabled"}), 404
        return app.response_class(
            json.dumps(tracker.verify_outcomes(), indent=2),
            mimetype="application/json")

    @app.get("/alarms")
    def alarms_view():
        """Onceden ilan edilmis alarm kosullari (kalip aramaz)."""
        rep = getattr(scheduler, "_alarm_report", None)
        if rep is None and hasattr(scheduler, "_evaluate_alarms"):
            rep = scheduler._evaluate_alarms()
        return app.response_class(json.dumps(rep or {}, indent=2),
                                  mimetype="application/json")

    @app.get("/challengers")
    def challengers_view():
        """Aday stratejilerin golge performansi (Faz B)."""
        eng = getattr(scheduler, "challengers", None)
        if eng is None:
            return jsonify({"error": "challengers disabled"}), 404
        data = eng.stats()
        # 200: detay penceresi strateji basina son 15 islemi gosterebilsin
        data["recent"] = eng.recent(200)
        # v1.2: aciklama+parametreler TEK kaynaktan (STRATEGY_INFO) gelir;
        # arayuz bunlari elle yazmaz - suruklenme yasagi
        data["strategy_info"] = eng.strategy_info()
        return app.response_class(json.dumps(data, indent=2),
                                  mimetype="application/json")

    @app.get("/correlation")
    def correlation_view():
        """Faz A olcum aleti: strateji-cifti gunluk R korelasyonu, etkin
        bagimsiz bahis sayisi, ayni-gun-ayni-yon cakisma orani. Salt rapor;
        karar/esik uretmez (docs/aile-arastirmasi-2026-08-13.md)."""
        eng = getattr(scheduler, "challengers", None)
        if eng is None or tracker is None:
            return jsonify({"error": "correlation needs tracker+challengers"}), 404
        from app.services import correlation
        from app.services.challengers import RETIRED, SAMPLING_REGIME
        rep = correlation.build_report(eng._db, SAMPLING_REGIME, RETIRED)
        return app.response_class(json.dumps(rep, indent=2),
                                  mimetype="application/json")

    @app.get("/exitlab")
    def exitlab_view():
        """Cikis laboratuvari: kapanmis aday sinyalleri V0 (mevcut sabit
        cikis) ve V1 (iz suren stop) ile yeniden oynatir. Salt olcum;
        hicbir karari degistirmez (on-kayit ideas.md 2026-08-17)."""
        eng = getattr(scheduler, "challengers", None)
        if eng is None:
            return jsonify({"error": "exitlab needs challengers"}), 404
        from app.services import exit_lab
        from app.services.challengers import SAMPLING_REGIME
        rep = exit_lab.build_report(eng._db, SAMPLING_REGIME)
        return app.response_class(json.dumps(rep, indent=2),
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

    # ------------------------------------------- v2.5: yorum / market / haber
    @app.get("/commentary")
    def commentary_feed():
        if commentary is None:
            return jsonify({"error": "commentary disabled"}), 404
        limit = min(int(request.args.get("limit", 5)), 48)
        return app.response_class(
            json.dumps(commentary.recent(limit), indent=2),
            mimetype="application/json")

    @app.get("/market")
    def market_metrics():
        if market_info is None:
            return jsonify({"error": "market info disabled"}), 404
        return app.response_class(json.dumps(market_info.metrics(), indent=2),
                                  mimetype="application/json")

    @app.get("/prices")
    def live_prices():
        if market_info is None:
            return jsonify({"error": "market info disabled"}), 404
        return app.response_class(json.dumps(market_info.prices()),
                                  mimetype="application/json")

    @app.get("/news")
    def market_news():
        if market_info is None:
            return jsonify({"error": "market info disabled"}), 404
        return app.response_class(json.dumps(market_info.news(), indent=2),
                                  mimetype="application/json")

    # ----------------------------------------------- Phase 2: gist yedekleme
    @app.get("/backup/info")
    def backup_info():
        if gist_backup is None:
            return jsonify({"error": "gist sync disabled (GITHUB_TOKEN not set)"}), 404
        return jsonify(gist_backup.info())

    @app.post("/backup/now")
    def backup_now():
        """Manuel gist senkronu - durum degistirir, bu yuzden POST."""
        if gist_backup is None:
            return jsonify({"error": "gist sync disabled (GITHUB_TOKEN not set)"}), 404
        ok = gist_backup.sync()
        return jsonify({"synced": ok, **gist_backup.info()}), (200 if ok else 502)

    return app
