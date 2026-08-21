"""
ALARM KAYDI - onceden ilan edilmis kosullar, surekli otomatik kontrol.

FELSEFE: Bu dosya kalip ARAMAZ. Veride arama yapan bir dongu, 148 sinyal ve
onlarca olasi bolme varken tesadufen "anlamli" bir sey MUTLAKA bulur; bu
p-hacking'i sanayilestirmek olur. Burada yalnizca ONCEDEN yazilmis, tek tek
gerekcelendirilmis kosullar kontrol edilir. Yeni bir alarm eklemek, kodu
degistirmek ve gerekcesini yazmak demektir - kesfetmek degil.

Kaynaklar: docs/config-lock.md (yanlislama kriterleri), docs/go-live-criteria.md
(Faz-1 kapisi), docs/error-prevention.md (yapisal kurallar).

Seviyeler:
  KRITIK - veri butunlugu veya guvenlik; derhal insan mudahalesi
  UYARI   - hipotez/kapi esigi tetiklendi; karar gerektirir
  BILGI   - izleme notu
"""
from __future__ import annotations

from datetime import datetime, timezone

CRITICAL, WARNING, INFO = "KRITIK", "UYARI", "BILGI"

# Yanlislama esikleri (config-lock.md'den; SIKILASTIRMA serbest, gevsetme yasak)
MAX_DD_LIMIT_R = 20.0          # kenar olumu: maksimum dusus tavani
STARVATION_MIN_FILLS = 40      # 30 gunde bu sayinin altinda dolus = aclik
STALE_BACKUP_HOURS = 3.0       # yedek bayatligi (senk periyodu 1 saat)
STALE_SCAN_MINUTES = 45.0      # tarama durmasi (periyot 15 dk)


def _age_hours(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        t = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600.0


def _alarm(level: str, code: str, msg: str, ref: str = "") -> dict:
    return {"level": level, "code": code, "message": msg, "ref": ref}


def evaluate(stats: dict, diagnostics: dict | None = None,
             challengers: dict | None = None,
             last_scan_utc: str | None = None,
             last_backup_utc: str | None = None) -> dict:
    """Tum onceden-ilan-edilmis kosullari kontrol et. Saf fonksiyon."""
    out: list[dict] = []
    meas = (stats or {}).get("measurement") or {}
    faz1 = meas.get("faz1") or {}
    boot = meas.get("bootstrap_since_lock") or {}

    # --- 1) VERI BUTUNLUGU (kritik) ---
    if diagnostics:
        audit = diagnostics.get("outcome_audit") or {}
        if audit.get("mismatches"):
            out.append(_alarm(
                CRITICAL, "AUDIT_MISMATCH",
                f"{audit['mismatches']} kayit mum arsiviyle celisiyor "
                f"({audit.get('checked')} denetlendi). /verify incelenmeli.",
                "error-prevention.md kural 8"))
    if meas.get("unclustered_excluded"):
        out.append(_alarm(
            CRITICAL, "UNCLUSTERED",
            f"{meas['unclustered_excluded']} kayit kumesiz - kume sayaci "
            "eksik sayiyor. Geriye donuk etiketleme calismamis olabilir.",
            "config-lock.md kume sayaci duzeltmesi"))

    # --- 2) ISLETIM (kritik) ---
    scan_age = _age_hours(last_scan_utc)
    if scan_age is not None and scan_age * 60 > STALE_SCAN_MINUTES:
        out.append(_alarm(
            CRITICAL, "SCAN_STALLED",
            f"son tarama {scan_age * 60:.0f} dk once (esik "
            f"{STALE_SCAN_MINUTES:.0f} dk) - tarayici durmus olabilir."))
    bk_age = _age_hours(last_backup_utc)
    if bk_age is not None and bk_age > STALE_BACKUP_HOURS:
        out.append(_alarm(
            CRITICAL, "BACKUP_STALE",
            f"son yedek {bk_age:.1f} saat once (esik {STALE_BACKUP_HOURS}) - "
            "VM yeniden baslarsa olcum verisi kaybolur."))

    # --- 3) YANLISLAMA KRITERLERI (uyari; karar gerektirir) ---
    ci_hi = boot.get("ci_high")
    n_cl = boot.get("n_clusters") or 0
    if ci_hi is not None and ci_hi < 0 and n_cl >= 20:
        out.append(_alarm(
            WARNING, "EDGE_DEATH",
            f"kume-CI ust siniri {ci_hi} < 0 ({n_cl} kume) - onceden ilan "
            "edilmis kenar olumu kriteri tetiklendi.",
            "config-lock.md yanlislama"))
    # v3.8 duzeltme: deger stats.measurement ICINDE yasar; ust duzeyde
    # aramak alarmi olu doguruyordu (35.6R ihlalini insan yakaladi, alarm
    # hic otmedi). Sinifi kapatan test: test_declared_alarms_can_actually_fire
    dd = meas.get("max_drawdown_r")
    if dd is not None and abs(dd) > MAX_DD_LIMIT_R:
        out.append(_alarm(
            WARNING, "MAX_DD",
            f"maksimum dusus {abs(dd):.1f}R > {MAX_DD_LIMIT_R}R esigi.",
            "config-lock.md yanlislama"))

    # --- 4) FAZ-1 KAPISI (bilgi/uyari) ---
    if faz1.get("gate_met"):
        out.append(_alarm(
            WARNING, "FAZ1_GATE_MET",
            f"Faz-1 kapisi ACIK: {faz1.get('clusters_since_lock')} kume ve "
            "kume-CI alt siniri > 0. Karar toplantisi gerekiyor.",
            "go-live-criteria.md"))
    elif (faz1.get("clusters_since_lock") or 0) >= faz1.get(
            "target_clusters", 50):
        out.append(_alarm(
            WARNING, "FAZ1_SAMPLE_FULL",
            f"{faz1.get('clusters_since_lock')} kume doldu ama CI kosulu "
            "saglanmadi - hukum: gecemedi. Karar toplantisi gerekiyor.",
            "go-live-criteria.md"))

    # --- 5) ADAY YARISI SAGLIGI (bilgi) ---
    if challengers:
        caps = challengers.get("max_open") or {}
        for name, s in (challengers.get("strategies") or {}).items():
            if s.get("retired_utc"):
                continue   # hukum verilmis emekli aday: alarm gurultusu olmaz
            cap = caps.get(name, 15)
            if (s.get("open") or 0) >= cap:
                out.append(_alarm(
                    INFO, "CHALLENGER_CAPPED",
                    f"{name} acik pozisyon tavaninda ({cap}) - yeni sinyal "
                    "uretemiyor, orneklem yapay kisitlaniyor.",
                    "challengers-design.md rejim-2"))
            ci = s.get("ci")
            if ci and ci[1] is not None and ci[1] < 0 and (
                    s.get("clusters") or 0) >= 20:
                out.append(_alarm(
                    INFO, "CHALLENGER_DEAD",
                    f"{name}: kume-CI ust siniri {ci[1]} < 0 "
                    f"({s.get('clusters')} kume) - aday eleniyor."))
            # dogrulama penceresi hukum ANI (on-kayit 2026-08-21, S1 dersi:
            # hukum insana birakilmaz, 50. kumede bot ilan eder). Muhurlu
            # hukum (verdict dolu) icin susar - hukum verildi, gurultu yok.
            va = s.get("validation")
            if va and not va.get("verdict") and (
                    va.get("clusters") or 0) >= (
                    va.get("target_clusters") or 50):
                vci = va.get("ci") or [None, None]
                if vci[0] is not None and vci[0] > 0:
                    out.append(_alarm(
                        WARNING, "VALIDATION_GATE_MET",
                        f"{name}: dogrulama kohortu doldu "
                        f"({va.get('clusters')} kume) VE kume-CI alt siniri "
                        f"{vci[0]} > 0 - dogrulama GECILDI. Karar "
                        "toplantisi gerekiyor.",
                        "challengers-design.md dogrulama"))
                else:
                    out.append(_alarm(
                        WARNING, "VALIDATION_SAMPLE_FULL",
                        f"{name}: dogrulama kohortu doldu "
                        f"({va.get('clusters')} kume) ama CI kosulu "
                        f"saglanmadi (alt {vci[0]}) - hukum: gecemedi. "
                        "Karar toplantisi gerekiyor.",
                        "challengers-design.md dogrulama"))

    return {
        "checked_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "note": ("Onceden ilan edilmis kosullar; kalip ARANMAZ. Yeni alarm "
                 "eklemek kod degisikligi ve gerekce yazmak demektir."),
        "critical": sum(1 for a in out if a["level"] == CRITICAL),
        "warning": sum(1 for a in out if a["level"] == WARNING),
        "alarms": out,
    }
