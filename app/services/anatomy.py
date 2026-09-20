"""OLUM SONRASI ANATOMI — sampiyon defterinin ayristirilmasi (salt olcum).

NEDEN (2026-09-18): sampiyonun v1 dosyasi kenar olumuyle kapandi (197 kume,
kume-CI ust siniri -0.028; maksDD 100.6R). "Kenar yok" bir HUKUMDUR;
"NEDEN yok" apayri bir sorudur ve bu proje onu hic sormadi. Bu alet o
soruyu tahminle degil olcumle cevaplar.

KURAL 5 UYUMU (p-hacking yasagi) — BU ALET VERIDE KALIP ARAMAZ:
raporun bolumleri SABITTIR (SECTIONS) ve her biri DAHA ONCE ILAN EDILMIS
bir soruya karsilik gelir:
  - by_direction  -> v2-tasarim.md GIRDI 1 (2026-08-20): "kilit-2 ara
                     verisi LONG -49.3R / SHORT +31.5R; v2'de rejim uyumu
                     suS degil ISKELET olmali." Bu, o iddianin 197 kumelik
                     defterde sinanmasidir.
  - by_regime     -> diagnostics.market_bias_dist (v3.6'dan beri raporlu)
  - cost          -> v2-tasarim.md GIRDI 0 (2026-08-27 on-kayit):
                     "maliyet/islem <= 0.05R, dar stop yasak."
  - concentration -> diagnostics.pair_concentration (v3.6'dan beri raporlu)
Yeni bir bolum eklemek = yeni bir soru sormak; SECTIONS'i degistiren
degisiklik testi kirar (test_anatomy_sections_are_declared). Boylece
"veriye bakip ilginc bir sey bulma" yolu kapalidir.

NE URETMEZ: esik, filtre, karar kurali, agirlik. Buradan cikan HICBIR
sayi dogrudan kural olamaz (Kural 4) — once docs/ideas.md'ye ON-KAYIT,
sonra GELECEK veride sinav.

ONEMLI OKUMA UYARISI (rapora da basilir): bu bir GERIYE bakan
ayristirmadir. Alt gruplar kucuklestikce CI genisler; "SHORT artida"
gibi bir okuma, SHORT'un kendi kume-CI alt siniri sifirin ustunde
degilse KANIT DEGILDIR. Rapor bunu her alt grup icin acikca yazar.

Kural uyumu: salt-okur; sampiyon davranisina sifir dokunus; verifier'dan
bagimsiz (import etmez).
"""
from __future__ import annotations

from app.services import measurement

# Rapor bolumleri DONMUSTUR - her biri onceden ilan edilmis bir soru.
SECTIONS = ("by_direction", "by_regime", "cost", "concentration")

# Bir alt grubun kendi basina "kanit" sayilabilmesi icin gereken en az
# kume sayisi. Faz-1 esigiyle AYNI (50) - alt gruba daha gevsek bir
# esik uygulamak, tam da kacindigimiz secici okuma olurdu.
MIN_CLUSTERS_FOR_CLAIM = measurement.FAZ1_TARGET_CLUSTERS


def _bucket(rows: list[dict], key_fn, cost_fn) -> dict[str, dict]:
    """rows -> {grup: {kume haritasi + brut toplam}} (net R ile)."""
    out: dict[str, dict] = {}
    for r in rows:
        cst = cost_fn(r)
        if cst is None or r.get("r_multiple") is None:
            continue
        cid = r.get("cluster_id")
        if not cid:
            continue                       # kumesiz kayit kanit sayilmaz
        key = key_fn(r)
        if key is None:
            continue
        g = out.setdefault(str(key), {"clusters": {}, "gross": 0.0,
                                      "cost": 0.0, "n": 0})
        g["clusters"].setdefault(cid, []).append(r["r_multiple"] - cst)
        g["gross"] += r["r_multiple"]
        g["cost"] += cst
        g["n"] += 1
    return out


def _summarise(group: dict) -> dict:
    """Bir grubu resmi standartla ozetle: kume-blok bootstrap CI."""
    boot = measurement.cluster_bootstrap(group["clusters"])
    net = sum(x for v in group["clusters"].values() for x in v)
    n_cl = len(group["clusters"])
    ci_low = (boot or {}).get("ci_low")
    ci_high = (boot or {}).get("ci_high")
    # Uc durumlu okuma - "artida" ile "KANITLI artida" ayri seylerdir.
    if n_cl < MIN_CLUSTERS_FOR_CLAIM:
        claim = "ORNEKLEM YETERSIZ (kanit degil)"
    elif ci_low is not None and ci_low > 0:
        claim = "KANITLI ARTI (CI alt > 0)"
    elif ci_high is not None and ci_high < 0:
        claim = "KANITLI EKSI (CI ust < 0)"
    else:
        claim = "BELIRSIZ (CI sifiri iceriyor)"
    return {
        "trades": group["n"],
        "clusters": n_cl,
        "gross_r": round(group["gross"], 2),
        "net_r": round(net, 2),
        "cost_r_total": round(group["cost"], 2),
        "cost_per_trade": (round(group["cost"] / group["n"], 3)
                           if group["n"] else None),
        "e_net": (boot or {}).get("e_net"),
        "ci": ([ci_low, ci_high] if ci_low is not None else None),
        "claim": claim,
    }


def by_direction(rows: list[dict], cost_fn) -> dict:
    """GIRDI 1'in sinavi: LONG ve SHORT ayri ayri, resmi CI ile."""
    return {k: _summarise(v)
            for k, v in sorted(_bucket(rows, lambda r: r.get("direction"),
                                       cost_fn).items())}


def by_regime(rows: list[dict], cost_fn) -> dict:
    """Piyasa rejimi (market_bias) kirilimi; etiketsiz kayitlar disarida."""
    return {k: _summarise(v)
            for k, v in sorted(_bucket(rows, lambda r: r.get("market_bias"),
                                       cost_fn).items())}


def cost_anatomy(rows: list[dict], cost_fn) -> dict:
    """GIRDI 0'in sinavi: net'i oldurenin maliyet olup olmadigi.

    'gross_positive_net_negative' bayragi projenin en pahali dersini tek
    satirda gosterir: motor HAM olarak artida, NET olarak eksideyse sorun
    giris kalibi degil, maliyet yapisidir (dar stop -> buyuk pozisyon).
    """
    gross = net = cost_sum = 0.0
    n = 0
    stop_fracs: list[float] = []
    per_trade: list[tuple[float, float]] = []      # (stop_frac, maliyet_R)
    for r in rows:
        cst = cost_fn(r)
        if cst is None or r.get("r_multiple") is None:
            continue
        gross += r["r_multiple"]
        net += r["r_multiple"] - cst
        cost_sum += cst
        n += 1
        entry = r.get("fill_price") or (
            r.get("entry_max") if r.get("direction") == "LONG"
            else r.get("entry_min"))
        stop = r.get("stop_loss")
        if entry and stop:
            frac = abs(entry - stop) / entry
            if frac > 0:
                stop_fracs.append(frac)
                per_trade.append((frac, cst))
    if not n:
        return {"trades": 0, "note": "maliyet hesaplanabilir kayit yok"}
    cpt = cost_sum / n
    return {
        "trades": n,
        "gross_r": round(gross, 2),
        "net_r": round(net, 2),
        "cost_r_total": round(cost_sum, 2),
        "cost_per_trade": round(cpt, 3),
        "cost_budget_v2": 0.05,
        "over_budget": cpt > 0.05,
        "stop_frac_median": measurement.median_or_none(stop_fracs),
        # projenin en pahali dersi, tek bayrakta
        "gross_positive_net_negative": gross > 0 and net < 0,
        "stop_floor_scan": stop_floor_scan(per_trade),
        "note": ("maliyet modeli v0 (kilitli): 2x taker %0.055 + stop "
                 "kaymasi 5bps + funding %0.01/8s. Dar stop, R cinsinden "
                 "maliyeti buyutur - GIRDI 0."),
    }


# Taranan stop tabanlari. ILAN EDILMIS sabit liste - "en iyi tabani bul"
# taramasi DEGILDIR; v2 butcesi (0.05R) etrafindaki aritmetik araligi
# kaplar (bkz. v2-tasarim.md GIRDI 0 tablosu).
STOP_FLOORS = (0.01, 0.02, 0.025, 0.03, 0.035, 0.04, 0.05)


def stop_floor_scan(per_trade: list[tuple[float, float]]) -> list[dict]:
    """Her stop tabani icin: kac islem HAYATTA KALIRDI ve maliyeti ne olurdu?

    NEDEN: v2'nin stop tabani aritmetikten geliyor, ama "o taban konursa
    motor ne kadar yavaslar" sorusunun cevabi VERIDE. Bu tarama yalniz
    FREKANS ve MALIYET soyler.

    ⚠️ HAYATTA KALMA YANILGISI (rapora da basilir): bu bir BACKTEST
    DEGILDIR. v1'in gecmisini stop genisligine gore suzmek, genis stoplu
    bir motoru KOSTURMAK ile ayni sey degildir - oyle bir motor bambaska
    girisler secerdi. Buradaki getiri sayilari bu yuzden RAPOR EDILMEZ;
    yalnizca islem sayisi ve maliyet verilir. Kenar tahmini YAPILAMAZ.
    """
    total = len(per_trade)
    out: list[dict] = []
    for floor in STOP_FLOORS:
        kept = [(f, c) for f, c in per_trade if f >= floor]
        cpt = (sum(c for _, c in kept) / len(kept)) if kept else None
        out.append({
            "stop_floor": floor,
            "trades_kept": len(kept),
            "share_kept": (round(len(kept) / total, 3) if total else None),
            "cost_per_trade": (round(cpt, 3) if cpt is not None else None),
            "within_budget": (cpt is not None and cpt <= 0.05),
        })
    return out


def concentration(rows: list[dict], cost_fn, top: int = 5) -> dict:
    """Kayip genis tabanli mi, birkac felaket kumeden mi geliyor?

    UYARI (rapora basilir): 'en kotu N cikarilsa' hesabi TARIFSEL bir
    dagilim olcusudur, bir strateji onerisi DEGILDIR. Gecmiste en kotu
    olani gelecekte ayirt edebilecegimiz iddiasi ayri bir hipotezdir ve
    ON-KAYIT ister (Kural 4).
    """
    cl = _bucket(rows, lambda r: "ALL", cost_fn).get("ALL")
    if not cl:
        return {"clusters": 0, "note": "kume yok"}
    sums = sorted(((cid, sum(v)) for cid, v in cl["clusters"].items()),
                  key=lambda x: x[1])
    net = sum(s for _, s in sums)
    worst = sums[:top]
    pair: dict[str, float] = {}
    for r in rows:
        cst = cost_fn(r)
        if cst is None or r.get("r_multiple") is None:
            continue
        pair[r.get("pair") or "?"] = (pair.get(r.get("pair") or "?", 0.0)
                                      + r["r_multiple"] - cst)
    worst_pairs = sorted(pair.items(), key=lambda x: x[1])[:top]
    return {
        "clusters": len(sums),
        "net_r": round(net, 2),
        "worst_clusters": [{"cluster_id": c, "net_r": round(s, 2)}
                           for c, s in worst],
        "worst_clusters_net_r": round(sum(s for _, s in worst), 2),
        "net_r_without_worst": round(net - sum(s for _, s in worst), 2),
        "worst_pairs": [{"pair": p, "net_r": round(s, 2)}
                        for p, s in worst_pairs],
        "note": ("TARIFSEL dagilim olcusu. 'En kotuler cikarilsa' sayisi "
                 "bir kural ONERISI DEGILDIR - gecmiste en kotu olani "
                 "onceden ayirt edebilecegimiz iddiasi ayri bir hipotezdir "
                 "ve ON-KAYIT ister (Kural 4)."),
    }


def build_report(rows: list[dict], cost_fn, since_lock: bool = True) -> dict:
    """Tam anatomi raporu. rows = kapanmis (WIN/LOSS) sampiyon kayitlari."""
    used = [r for r in rows
            if r.get("outcome") in measurement.MEASURED_OUTCOMES
            and (not since_lock
                 or (r.get("created_utc") or "") >= measurement.ACTIVE_LOCK_UTC)]
    return {
        "note": ("OLUM SONRASI ANATOMI - salt olcum. Bolumler SABIT ve "
                 "her biri onceden ilan edilmis bir soruya karsilik gelir "
                 "(Kural 5). Buradan cikan hicbir sayi dogrudan kural "
                 "olamaz - once ON-KAYIT, sonra GELECEK veride sinav "
                 "(Kural 4)."),
        "window": ("KILIT-2 sonrasi" if since_lock else "tum defter"),
        "lock_utc": measurement.ACTIVE_LOCK_UTC,
        "trades": len(used),
        "min_clusters_for_claim": MIN_CLUSTERS_FOR_CLAIM,
        "reading_warning": ("Alt gruplar kuculdukce CI genisler. Bir alt "
                            "grubun 'artida' gorunmesi KANIT DEGILDIR; "
                            "kanit icin kendi kume-CI alt siniri > 0 VE "
                            f">= {MIN_CLUSTERS_FOR_CLAIM} kume gerekir. "
                            "Her grubun 'claim' alani bunu soyler."),
        "by_direction": by_direction(used, cost_fn),
        "by_regime": by_regime(used, cost_fn),
        "cost": cost_anatomy(used, cost_fn),
        "concentration": concentration(used, cost_fn),
    }
