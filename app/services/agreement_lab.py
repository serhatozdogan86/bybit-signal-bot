"""TEYIT LABORATUVARI — "kac motor ayni seyi soyluyor?" (salt olcum).

ON-KAYIT: docs/ideas.md "H-TEYIT" (2026-09-28, Serhat'in fikri). Tanim,
taranan liste ve hukum merdiveni bu alet YAZILMADAN ve hicbir sayiya
BAKILMADAN donduruldu (Kural 4).

FIKIR: portfoyun 5 uyesinden en az K'si ayni sinyali veriyorsa bot
yayinlasin. Amac hem daraltma (gunde ~105 sinyal takip edilemez) hem de
teyit beklentisi.

ONCEDEN YAZILAN KUSKU: korelasyon olcumu (09-20) S1/S2/S11/S12'nin
buyuk olcude AYNI bahis oldugunu gosterdi (0.49-0.66). "3 motor ayni
fikirde" cogu zaman BAGIMSIZ teyit degil, ayni fikrin uc kez sayilmasi
olabilir.

⚠️ EN KRITIK SOZLESME — BACKTEST YALNIZ OLDUREBILIR, KUTSAYAMAZ:
P4'te gecmise bakan analiz carpici bir fark gosterdi, canli veri
TERSINI verdi. Bu yuzden gecmis getiri YALNIZ budama amaclidir:
teyitli kohort DAHA IYI cikarsa bu HICBIR SEYI KANITLAMAZ (ileri
pencere ister); DAHA KOTU ya da ESIT cikarsa fikir DUSER.
Rapor bu cumleyi kendi icinde tasir ve testle zorlanir.

SIKLIK KARARI GETIRIDEN BAGIMSIZDIR: hangi (W,K) ile yayin yapilacagi
YALNIZ sinyal sayisina bakilarak secilir.

Kural uyumu: salt-okur; motor davranisina sifir dokunus.
"""
from __future__ import annotations

from app.services import measurement

# --- ON-KAYITLI SABIT LISTE (ideas.md H-TEYIT) ---
WINDOWS_H = (1, 4, 12, 24)        # teyit penceresi (saat)
MIN_ENGINES = (2, 3, 4, 5)        # gereken FARKLI motor sayisi
# Hukum merdiveninin okundugu nokta (on-kayitta ilan edildi)
VERDICT_W, VERDICT_K = 4, 3

_MS_H = 3_600_000


def group_signals(rows: list[dict], window_h: int) -> list[dict]:
    """(parite, yon) icinde zaman pencerelerine gore grupla.

    Deterministik kural (on-kayitli): girisler zamana gore siralanir;
    ilk giris grubu ACAR, W saat icindekiler gruba KATILIR, disindaki
    ilk giris YENI grup acar.
    """
    buckets: dict[tuple, list[dict]] = {}
    for r in rows:
        ts = r.get("entry_ts")
        if ts is None:
            continue
        buckets.setdefault((r.get("pair"), r.get("direction")), []).append(r)

    out: list[dict] = []
    span = window_h * _MS_H
    for (pair, direction), rs in buckets.items():
        rs.sort(key=lambda x: x["entry_ts"])
        grup: dict | None = None
        for r in rs:
            if grup is None or r["entry_ts"] - grup["first_ts"] > span:
                grup = {"pair": pair, "direction": direction,
                        "first_ts": r["entry_ts"], "rows": [],
                        "engines": set()}
                out.append(grup)
            grup["rows"].append(r)
            grup["engines"].add(r.get("strategy"))
    return out


def frequency_scan(rows: list[dict], days: float | None = None) -> list[dict]:
    """ASIL AMAC: her (W,K) icin kac sinyal hayatta kalir?

    GETIRI RAPORLAMAZ - siklik karari getiriden bagimsiz verilmelidir
    (testle zorlanir)."""
    total = len(rows)
    out: list[dict] = []
    for w in WINDOWS_H:
        gruplar = group_signals(rows, w)
        for k in MIN_ENGINES:
            kalan = [g for g in gruplar if len(g["engines"]) >= k]
            n_sig = len(kalan)                      # yayinlanacak MESAJ sayisi
            n_trade = sum(len(g["rows"]) for g in kalan)
            out.append({
                "window_h": w, "min_engines": k,
                "messages": n_sig,
                "trades_covered": n_trade,
                "share_of_trades": (round(n_trade / total, 4)
                                    if total else None),
                "messages_per_day": (round(n_sig / days, 2)
                                     if days else None),
            })
    return out


def _cohort(gruplar: list[dict], k: int, net_fn):
    """Teyitli / teyitsiz kohortlari (kume haritasi + net) olarak ayir."""
    tey: dict[str, list[float]] = {}
    tey_n = 0
    tey_sum = 0.0
    dis: dict[str, list[float]] = {}
    dis_n = 0
    dis_sum = 0.0
    for g in gruplar:
        confirmed = len(g["engines"]) >= k
        cid = "%s_%s_%d" % (g["pair"], (g["direction"] or "?")[0],
                            g["first_ts"] // 86_400_000)
        for r in g["rows"]:
            net = net_fn(r)
            if net is None:
                continue
            if confirmed:
                tey.setdefault(cid, []).append(net)
                tey_n += 1
                tey_sum += net
            else:
                dis.setdefault(cid, []).append(net)
                dis_n += 1
                dis_sum += net
    return (tey, tey_n, tey_sum), (dis, dis_n, dis_sum)


def verdict_reading(rows: list[dict], net_fn) -> dict:
    """ON-KAYITLI merdiven noktasi (W=4s, K=3) — BUDAMA amacli.

    Merdiven (ideas.md H-TEYIT, sayi gorulmeden donduruldu):
      ELENDI      : teyitli E_net <= teyitsiz E_net
      KANIT DEGIL : teyitli daha iyi -> ILERI pencere ister
    """
    gruplar = group_signals(rows, VERDICT_W)
    (tey, tn, tsum), (dis, dn, dsum) = _cohort(gruplar, VERDICT_K, net_fn)
    e_tey = round(tsum / tn, 4) if tn else None
    e_dis = round(dsum / dn, 4) if dn else None
    if e_tey is None or e_dis is None:
        hukum = "ORNEKLEM YETERSIZ (hukum yok)"
    elif e_tey <= e_dis:
        hukum = "ELENDI (teyit katki vermiyor)"
    else:
        hukum = "KANIT DEGIL - ILERI PENCERE ISTER"
    return {
        "window_h": VERDICT_W, "min_engines": VERDICT_K,
        "confirmed": {"trades": tn, "clusters": len(tey), "net_r":
                      round(tsum, 2), "e_net": e_tey,
                      "ci": _ci(tey)},
        "unconfirmed": {"trades": dn, "clusters": len(dis), "net_r":
                        round(dsum, 2), "e_net": e_dis,
                        "ci": _ci(dis)},
        "verdict": hukum,
    }


def _ci(clusters: dict[str, list[float]]):
    boot = measurement.cluster_bootstrap(clusters)
    if not boot or boot.get("ci_low") is None:
        return None
    return [boot["ci_low"], boot["ci_high"]]


def build_report(rows: list[dict], net_fn, members: list[str],
                 days: float | None = None) -> dict:
    used = [r for r in rows if r.get("strategy") in members]
    return {
        "note": ("TEYIT LABORATUVARI - salt olcum. Tanim ve taranan "
                 "liste docs/ideas.md H-TEYIT'te, bu olcum yapilmadan "
                 "ONCE donduruldu (Kural 4)."),
        "backtest_warning": ("GECMIS GETIRI YALNIZ BUDAMA AMACLIDIR. "
                             "Teyitli kohort DAHA IYI cikarsa bu HICBIR "
                             "SEYI KANITLAMAZ - on-kayitli ILERI pencere "
                             "ister (P4 dersi: backtest carpici bir fark "
                             "gosterdi, canli veri TERSINI verdi). "
                             "Backtest OLDUREBILIR, KUTSAYAMAZ."),
        "frequency_note": ("Yayin icin (W,K) secimi YALNIZ siklia "
                           "bakilarak yapilir; getiriye bakarak esik "
                           "secmek kacindigimiz hatadir."),
        "members": sorted(members),
        "signals_total": len(used),
        "days": days,
        "frequency_scan": frequency_scan(used, days),
        "verdict_reading": verdict_reading(used, net_fn),
    }
