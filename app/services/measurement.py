"""
v3.6 OLCUM PAKETI - kume istatistigi ve teshis fonksiyonlari.

Konsey 2. tur hukmu (docs/council-review-2026-07.md): "olcum borcu var" -
mevcut islem-duzeyi CI otokorelasyonu yok sayar ve yaniltici dardir (5/5 oy).
Bu modul YALNIZ olcum yapar; motor davranisina, esiklere ve kilide DOKUNMAZ.

Icerik (konsey P0):
1. cluster_bootstrap  - kume-blok bootstrap %95 CI(E_net). Gozlem birimi
   islem degil KUMEDIR (ayni yon + ayni 4H penceresi = tek fikir).
   Raporlarda ve panoda SADECE bu CI kullanilir.
2. nf_anatomy         - NOT_FILLED sinyal anatomisi: fiyat giris kenarina
   ne kadar yaklasti (R cinsinden bosluk), kac bar temas mesafesindeydi,
   bolgeyi sonradan gecti mi.
3. hypo_slip_summary  - hayalet R'nin kayma senaryolariyla yeniden hesabi
   (%0.1 / %0.3 / %0.5). "Ideal dolus" yanilsamasina sayisal panzehir.
4. permutation_pvalue - guven etiketi bilgi tasiyor mu? (P1-7; negatifse
   etiket kilit-v2'de kaldirilir.)

Tum fonksiyonlar saf ve deterministiktir (sabit seed) -> test edilebilir,
her cagrida ayni veriyle ayni CI.
"""
from __future__ import annotations

import random
from statistics import mean, median

# Kilit ani (docs/config-lock.md): Faz-1 sayaclari bu andan baslar.
LOCK_UTC = "2026-07-29T00:00:00Z"

# Faz-1 kapisi (2026-08-02 sikilastirmasi, konsey medyani):
# >=50 bagimsiz KAPANMIS kume VE kume-CI alt siniri > 0.
FAZ1_TARGET_CLUSTERS = 50

# Hayalet R kayma senaryolari (giris kenarindan sapma orani)
SLIP_SCENARIOS = (0.001, 0.003, 0.005)


# ------------------------------------------------------------------ bootstrap
def cluster_bootstrap(clusters: dict[str, list[float]],
                      n_boot: int = 3000, seed: int = 36,
                      alpha: float = 0.05) -> dict | None:
    """Kume-blok bootstrap: kumeler (icindeki tum islemlerle) yerine koyarak
    yeniden orneklenir; istatistik = orneklemdeki islemlerin ortalama net R'si.

    Ayni kumedeki islemler bagimli oldugundan islem-duzeyi bootstrap CI'yi
    yapay daraltir; blok yontemi bagimliligi korur (konsey 5/5).
    Donen CI yuzdelik yontemidir; seed sabit -> deterministik.
    """
    blocks = [v for v in clusters.values() if v]
    all_vals = [x for v in blocks for x in v]
    if not all_vals:
        return None
    result = {
        "method": "cluster-block bootstrap, percentile CI",
        "n_clusters": len(blocks),
        "n_trades": len(all_vals),
        "n_boot": n_boot,
        "seed": seed,
        "e_net": round(mean(all_vals), 3),
        "ci_low": None,
        "ci_high": None,
    }
    if len(blocks) < 2:
        result["note"] = "tek kume: CI hesaplanamaz (n_clusters<2)"
        return result
    rng = random.Random(seed)
    k = len(blocks)
    boot_means: list[float] = []
    for _ in range(n_boot):
        flat: list[float] = []
        for _ in range(k):
            flat.extend(blocks[rng.randrange(k)])
        boot_means.append(sum(flat) / len(flat))
    boot_means.sort()
    lo_i = max(0, int((alpha / 2) * n_boot))
    hi_i = min(n_boot - 1, int((1 - alpha / 2) * n_boot) - 1)
    result["ci_low"] = round(boot_means[lo_i], 3)
    result["ci_high"] = round(boot_means[hi_i], 3)
    return result


# ------------------------------------------------------- NOT_FILLED anatomisi
def nf_anatomy(sig: dict, candles: list[dict],
               fill_window: int) -> dict | None:
    """Dolmayan sinyalin anatomisi (teshis; skora karismaz).

    - gap_r: dolus penceresi icinde fiyatin giris KENARINA kalan en kucuk
      mesafe, R (stop mesafesi) cinsinden. 0'a yakin = kil payi kacti.
    - touch_bars: kenara <= %0.1 yaklasan bar sayisi (temas).
    - crossed: izlenen TUM mumlarda fiyat bolgenin uzak kenarini gecti mi
      (1 = pencere uzasaydi kesin dolardi; ters secim sinyalinin nuvesi).
    """
    is_long = sig["direction"] == "LONG"
    edge = sig["entry_max"] if is_long else sig["entry_min"]
    far = sig["entry_min"] if is_long else sig["entry_max"]
    if edge is None or far is None or sig.get("stop_loss") is None:
        return None
    risk = (edge - sig["stop_loss"]) if is_long else (sig["stop_loss"] - edge)
    if risk <= 0:
        return None
    window = candles[:fill_window]
    if not window:
        return None
    gaps = []
    touch = 0
    for c in window:
        gap = (c["low"] - edge) if is_long else (edge - c["high"])
        gaps.append(gap)
        if gap <= 0.001 * edge:
            touch += 1
    crossed = any((c["low"] <= far) if is_long else (c["high"] >= far)
                  for c in candles)
    return {"gap_r": round(min(gaps) / risk, 3),
            "touch_bars": touch,
            "crossed": int(crossed)}


# ------------------------------------------------- hayalet R kayma senaryolari
def _ghost_slip_cost_r(row: dict, slip_frac: float) -> float | None:
    """Kenar girisine gore kayma maliyeti, R cinsinden."""
    is_long = row["direction"] == "LONG"
    entry = row["entry_max"] if is_long else row["entry_min"]
    if entry is None or row.get("stop_loss") is None or not entry:
        return None
    stop_frac = abs(entry - row["stop_loss"]) / entry
    if stop_frac <= 0:
        return None
    return slip_frac / stop_frac


def hypo_slip_summary(rows: list[dict]) -> dict:
    """NOT_FILLED hayalet R toplamini kayma senaryolariyla yeniden hesaplar.

    hypo_r 'kenardan ideal dolus' varsayar; konsey (5/5) bunun buyuk olcude
    yanilsama oldugunu soyledi. Her senaryo: hypo_r - kayma/stop_mesafesi.
    Sonuclar teshis icindir; giris yontemi OLCMEDEN degistirilmez.
    """
    out = {"n": 0, "sum_r_ideal": 0.0}
    sums = {s: 0.0 for s in SLIP_SCENARIOS}
    for r in rows:
        if r.get("hypo_r") is None:
            continue
        out["n"] += 1
        out["sum_r_ideal"] += r["hypo_r"]
        for s in SLIP_SCENARIOS:
            cost = _ghost_slip_cost_r(r, s)
            sums[s] += r["hypo_r"] - cost if cost is not None else r["hypo_r"]
    out["sum_r_ideal"] = round(out["sum_r_ideal"], 2)
    for s in SLIP_SCENARIOS:
        out[f"sum_r_slip_{int(s * 10000)}bps"] = round(sums[s], 2)
    out["note"] = "ideal-dolus varsayimina kayma duzeltmesi; teshis verisi"
    return out


# --------------------------------------------------------- permutasyon testi
def permutation_pvalue(a: list[float], b: list[float],
                       n_perm: int = 2000, seed: int = 36) -> dict | None:
    """Iki grubun ortalama farki icin cift yonlu permutasyon p-degeri.

    Kullanim: guven etiketi (HIGH vs digerleri) net R'de gercek ayrisma
    sagliyor mu? p yuksekse etiket bilgi tasimiyor demektir (konsey 5/5:
    'karar mekanizmalarinda kullanilmamali').
    """
    if len(a) < 3 or len(b) < 3:
        return None
    obs = mean(a) - mean(b)
    pooled = list(a) + list(b)
    rng = random.Random(seed)
    n_a = len(a)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        diff = mean(pooled[:n_a]) - mean(pooled[n_a:])
        if abs(diff) >= abs(obs):
            hits += 1
    return {"obs_diff": round(obs, 3),
            "p_value": round((hits + 1) / (n_perm + 1), 4),
            "n_a": n_a, "n_b": len(b), "n_perm": n_perm}


# ------------------------------------------------------------ kucuk yardimci
def top_share(values: list[float]) -> dict:
    """Yogunlasma: en buyuk 1 ve 3 katkinin toplam icindeki payi.

    'Bir kume tum kari mi tasiyor?' sorusuna sayisal cevap. Toplam <= 0 ise
    pay anlamsizdir -> None.
    """
    total = sum(values)
    ordered = sorted(values, reverse=True)
    def share(k: int) -> float | None:
        if total <= 0 or not ordered:
            return None
        return round(sum(ordered[:k]) / total, 3)
    return {"total": round(total, 2), "top1_share": share(1),
            "top3_share": share(3)}


def median_or_none(values: list[float]) -> float | None:
    return round(median(values), 3) if values else None
