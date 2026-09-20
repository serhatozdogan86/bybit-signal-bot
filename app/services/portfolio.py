"""PORTFOY OLCUM ALETI (Faz B) — birlesik defterin resmi CI'si.

NEDEN (2026-09-20, config-lock): dort motor kucuk-ama-pozitif ve maliyet
butcesi icinde; hicbiri TEK BASINA sinavi gecemiyor cunku gurultu
kenardan buyuk. Tez: ortusmuyorlarsa birlesik defterin gurultusu azalir
ve CI daralir. Bu alet o tezi TAHMINLE degil OLCUMLE sinar.

UYE KURALI GETIRIYE BAKMAZ (p-hacking kapisi): emekli olmayan +
maliyet/islem <= 0.05R + >= 50 kume. Bugun bu kural net EKSI olan
S12'yi de secer - kurali durust yapan tam olarak budur. Kural
sabitlerde yasar; getiriye bakan bir eleme eklemek testi kirar.

⭐ KUME BIRLESTIRME (bu aletin en kritik tasarim karari):
Portfoy kumesi = YON + TAKVIM GUNU. Yani iki motor ayni gun ayni yonde
islem actiysa bu TEK bir bagimsiz bahistir, iki degil. Gerekce: kume
mantiginin tum amaci BAGIMLI islemleri tek bloga koymaktir; motorlar
arasi ortusmeyi saymazsak portfoy, sirf ayni bahsi bes kez sayarak
yapay bir daralma uretir - projenin en tehlikeli ozaldatmacasi olurdu.
Gunluk kova, motorlarin kendi 4 SAATLIK kovasindan KABADIR; yani bu
secim KASITLI OLARAK MUHAFAZAKARDIR (daha az blok -> daha GENIS CI ->
gecmek daha ZOR). Portfoy asla muhasebe secimiyle iyi gorunmemelidir.
(S12 zaten gunluk kova kullaniyordu; birlestirme onu da kapsar.)

NE URETMEZ: hukum, esik, agirlik. Bu bir OLCUMDUR. Portfoy hukmu ancak
ILAN EDILMIS bir pencerede, ilandan SONRAKI veriyle verilir - gecmis
defterden okunan CI "kurulabilir mi" sorusunu cevaplar, "gecti mi"
sorusunu DEGIL. Rapor bunu kendi icinde yazar.

Kural uyumu: salt-okur; motor davranisina sifir dokunus.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.services import correlation, measurement

# --- UYE KURALI (getiriye BAKMAZ) ---
MEMBER_MAX_COST_PER_TRADE = 0.05          # v2 GIRDI 0 butcesi
MEMBER_MIN_CLUSTERS = measurement.FAZ1_TARGET_CLUSTERS   # 50

_DAY_MS = 86_400_000


def select_members(stats: dict, retired: dict | None = None) -> list[str]:
    """Uye listesi. YALNIZ maliyet + orneklem buyuklugu + emeklilik bakar.

    Bilincli olarak getiri/CI OKUNMAZ: "iyi gorunenleri sec" tam olarak
    kacindigimiz secici okumadir."""
    retired = retired or {}
    out = []
    for name, v in (stats.get("strategies") or {}).items():
        if name in retired or v.get("retired_utc"):
            continue
        cpt = v.get("cost_per_trade")
        if cpt is None or cpt > MEMBER_MAX_COST_PER_TRADE:
            continue
        if (v.get("clusters") or 0) < MEMBER_MIN_CLUSTERS:
            continue
        out.append(name)
    return sorted(out)


def portfolio_cluster_id(direction: str, ts_ms: int) -> str:
    """YON + TAKVIM GUNU. Motorlar arasi ortusme TEK bloga duser."""
    return "%s_D%d" % ((direction or "?")[0], int(ts_ms) // _DAY_MS)


def required_clusters(e_net: float, sigma: float,
                      z: float = 1.96) -> int | None:
    """CI alt siniri > 0 olmasi icin gereken (etkin) kume sayisi.

    Saf aritmetik: z*sigma/sqrt(n) < e_net. Bir KURAL degil, planlama
    sayisidir - "bu tempoda ne kadar surer" sorusunu cevaplar."""
    if e_net is None or sigma is None or e_net <= 0 or sigma <= 0:
        return None
    return int((z * sigma / e_net) ** 2) + 1


def build_report(rows: list[dict], members: list[str], net_fn,
                 sampling_regime: int) -> dict:
    """rows = challenger_signals kayitlari (salt okuma)."""
    used = [r for r in rows
            if r.get("strategy") in members
            and (r.get("regime") or 1) == sampling_regime
            and r.get("status") == "CLOSED"
            and r.get("outcome") in measurement.MEASURED_OUTCOMES]

    clusters: dict[str, list[float]] = {}
    per_member: dict[str, dict] = {}
    series: dict[str, dict[str, float]] = {}
    merged_hits = 0
    for r in used:
        net = net_fn(r)
        if net is None:
            continue
        ts = r.get("entry_ts") or 0
        if ts <= 0:
            continue
        cid = portfolio_cluster_id(r.get("direction") or "?", ts)
        if cid in clusters:
            merged_hits += 1
        clusters.setdefault(cid, []).append(net)
        m = per_member.setdefault(r["strategy"],
                                  {"trades": 0, "net_r": 0.0})
        m["trades"] += 1
        m["net_r"] += net
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%d")
        s = series.setdefault(r["strategy"], {})
        s[day] = s.get(day, 0.0) + float(r.get("r_multiple") or 0.0)

    boot = measurement.cluster_bootstrap(clusters)
    for v in per_member.values():
        v["net_r"] = round(v["net_r"], 2)

    # bagimsizlik YALNIZ uyeler arasinda - manset N_eff emeklileri ve
    # sampiyonu da katip sayiyi yapay sisirir (2026-09-20 dersi)
    matrix = correlation.correlation_matrix(series)
    indep = correlation.effective_bets(matrix, len(series))

    e_net = (boot or {}).get("e_net")
    n_cl = len(clusters)
    ci_low = (boot or {}).get("ci_low")
    ci_high = (boot or {}).get("ci_high")
    sigma = None
    if ci_low is not None and n_cl > 1:
        sigma = round(((ci_high - ci_low) / 2) * (n_cl ** 0.5) / 1.96, 3)
    need = required_clusters(e_net, sigma) if sigma else None

    return {
        "note": ("PORTFOY OLCUMU - salt rapor. Portfoy kumesi = YON + "
                 "TAKVIM GUNU: iki motor ayni gun ayni yonde actiysa TEK "
                 "bagimsiz bahistir. Bu kova motorlarin 4 saatlik "
                 "kovasindan KABADIR - kasitli olarak muhafazakar "
                 "(daha az blok -> daha genis CI -> gecmek daha ZOR)."),
        "verdict_warning": ("Bu CI 'KURULABILIR MI' sorusunu cevaplar, "
                            "'GECTI MI' sorusunu DEGIL. Portfoy hukmu "
                            "ancak ILAN EDILMIS bir pencerede, ilandan "
                            "SONRAKI veriyle verilir (Kural 4)."),
        "member_rule": {
            "max_cost_per_trade": MEMBER_MAX_COST_PER_TRADE,
            "min_clusters": MEMBER_MIN_CLUSTERS,
            "reads_returns": False,
        },
        "members": sorted(members),
        "trades": sum(v["trades"] for v in per_member.values()),
        "clusters": n_cl,
        "merged_overlaps": merged_hits,
        "net_r": round(sum(x for v in clusters.values() for x in v), 2),
        "e_net": e_net,
        "ci": ([ci_low, ci_high] if ci_low is not None else None),
        "gate_met": (n_cl >= measurement.FAZ1_TARGET_CLUSTERS
                     and ci_low is not None and ci_low > 0),
        "sigma_per_cluster": sigma,
        "required_clusters_for_ci_low_gt_0": need,
        "per_member": {k: per_member[k] for k in sorted(per_member)},
        "independence_members_only": indep,
    }
