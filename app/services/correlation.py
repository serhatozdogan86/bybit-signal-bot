"""Coklu-strateji defteri KORELASYON/ORTUSME olcum aleti (Faz A — salt rapor).

Arastirma 2026-08-13 (docs/aile-arastirmasi-2026-08-13.md, meta-katman #1):
"strateji-cifti R korelasyon matrisi, etkin bagimsiz bahis sayisi,
ayni-gun-ayni-yon cakisma orani. Hicbir karar degistirmez."

NE YAPAR: sampiyon + aday stratejilerin kapanmis islemlerini gunluk R
serilerine cevirir ve cift cift karsilastirir. Yeni aday on-kayitlarinin
sart kostugu ortusme olcumlerinin (S8<->PREM-DIV vb.) altyapisidir.

NE YAPMAZ: esik/karar/agirlik URETMEZ (Faz B ayri on-kayit ister).
Korelasyon BRUT R uzerinden hesaplanir — maliyet, islem basina yaklasik
sabit bir kaydirma oldugundan korelasyon YAPISINI degistirmez; bu bilinçli
sadelestirme raporda acikca yazilir.

Kural uyumu: salt-okur olcum aleti; sampiyon davranisina sifir dokunus;
verifier'dan bagimsiz (import etmez).
"""
from __future__ import annotations

from datetime import datetime, timezone

MIN_DAYS = 10          # bir cift icin korelasyon raporlamanin alt esigi
_BAR_MS = 900_000      # 15dk


def _day_from_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d")


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Klasik Pearson; n<2 veya sifir varyans -> None."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / (sxx * syy) ** 0.5


def pair_days(a: dict[str, float], b: dict[str, float]) -> tuple[list, list]:
    """Iki gunluk seriyi hizala: EN AZ BIRININ islem yaptigi gunler
    (ikisinin de bos oldugu gunler korelasyonu yapay sisirirdi)."""
    days = sorted(set(a) | set(b))
    return ([a.get(d, 0.0) for d in days], [b.get(d, 0.0) for d in days])


def correlation_matrix(series: dict[str, dict[str, float]],
                       min_days: int = MIN_DAYS) -> dict:
    """{'A|B': {'corr': r|None, 'days': n}} — alfabetik cift anahtari."""
    out: dict[str, dict] = {}
    names = sorted(series)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            xs, ys = pair_days(series[a], series[b])
            # esik: HER IKI serinin de kendi basina yeterli aktif gunu olmali
            # (tek islemlik seri, birlesik gun sayisini gecse de anlamsizdir)
            enough = (len(series[a]) >= min_days
                      and len(series[b]) >= min_days)
            r = pearson(xs, ys) if enough else None
            out[f"{a}|{b}"] = {
                "corr": (round(r, 3) if r is not None else None),
                "days": len(xs),
            }
    return out


def effective_bets(matrix: dict, n: int) -> dict:
    """N_eff = N / (1 + (N-1) * ort_korelasyon). Kac BAGIMSIZ bahsimiz var?
    Tum ciftler ayni yonde hareket ediyorsa (ort~1) tek bahis var demektir.

    EVREN TUTARLILIGI (inceleme 2026-08-13, MAJOR): ortalama korelasyon
    yalniz OLCULEN ciftlerden gelir; N de ayni evrenden sayilmali —
    olculen ciftlerde gecen FARKLI strateji sayisi (n_measured). Aksi
    halde olculmemis stratejiler N_eff'i temelsizce sisirir."""
    measured = {k: v for k, v in matrix.items() if v["corr"] is not None}
    names: set[str] = set()
    for k in measured:
        a, b = k.split("|", 1)
        names.update((a, b))
    n_measured = len(names)
    vals = [v["corr"] for v in measured.values()]
    if n_measured < 2 or not vals:
        return {"n_strategies": n, "n_measured": n_measured,
                "avg_pairwise_corr": None, "effective_bets": None,
                "pairs_measured": len(vals)}
    avg = sum(vals) / len(vals)
    denom = 1 + (n_measured - 1) * avg
    n_eff = n_measured / denom if denom > 0 else float(n_measured)
    return {"n_strategies": n, "n_measured": n_measured,
            "avg_pairwise_corr": round(avg, 3),
            "effective_bets": round(
                min(max(n_eff, 1.0), float(n_measured)), 2),
            "pairs_measured": len(vals)}


def direction_overlap(opens: dict[str, dict[str, set]]) -> dict:
    """Ayni gun sinyal ACAN ciftlerde ayni-yon orani.
    opens: {strateji: {gun: {yonler}}}."""
    out: dict[str, dict] = {}
    names = sorted(opens)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            both = [d for d in opens[a] if d in opens[b]]
            same = sum(1 for d in both if opens[a][d] & opens[b][d])
            out[f"{a}|{b}"] = {
                "both_open_days": len(both), "same_dir_days": same,
                "rate": (round(same / len(both), 3) if both else None),
            }
    return out


def build_report(db, sampling_regime: int, retired: dict) -> dict:
    """Canli DB baglantisindan (salt SELECT) tam rapor uret."""
    series: dict[str, dict[str, float]] = {}
    opens: dict[str, dict[str, set]] = {}

    # --- sampiyon: kapanis gunu + brut R; acilislar created gunu ---
    for r in db.query(
            "SELECT direction, created_utc, closed_utc, r_multiple, outcome "
            "FROM signals WHERE blocked=0"):
        day_open = (r["created_utc"] or "")[:10]
        if day_open:
            opens.setdefault("CHAMPION", {}).setdefault(
                day_open, set()).add(r["direction"])
        # yalniz GERCEK pozisyonlar (stats ile ayni kohort): NOT_FILLED hic
        # acilmamis pozisyondur, r=0.0 ile sahte 'aktif gun' uretirdi
        # (inceleme 2026-08-13, MAJOR); AMBIGUOUS patolojik kapanis da disi.
        if r["outcome"] not in ("WIN", "LOSS", "EXPIRED") \
                or r["r_multiple"] is None:
            continue
        day = (r["closed_utc"] or r["created_utc"] or "")[:10]
        if day:
            s = series.setdefault("CHAMPION", {})
            s[day] = s.get(day, 0.0) + float(r["r_multiple"])

    # --- adaylar: gecerli ornekleme rejimi; kapanis ~ entry_ts + tutus ---
    for r in db.query(
            "SELECT strategy, direction, created_utc, entry_ts, hold_bars, "
            "r_multiple, status, outcome, regime FROM challenger_signals"):
        if (r.get("regime") or 1) != sampling_regime:
            continue
        day_open = (r["created_utc"] or "")[:10]
        if day_open:
            opens.setdefault(r["strategy"], {}).setdefault(
                day_open, set()).add(r["direction"])
        if r["status"] != "CLOSED" or r["r_multiple"] is None \
                or r["outcome"] not in ("WIN", "LOSS", "EXPIRED"):
            continue
        close_ms = (r["entry_ts"] or 0) + (r["hold_bars"] or 0) * _BAR_MS
        if close_ms <= 0:
            continue
        s = series.setdefault(r["strategy"], {})
        d = _day_from_ms(close_ms)
        s[d] = s.get(d, 0.0) + float(r["r_multiple"])

    matrix = correlation_matrix(series)
    return {
        "note": ("Faz A OLCUM ALETI — salt rapor, karar/esik uretmez. "
                 "Korelasyon BRUT gunluk R uzerinden (maliyet ~sabit "
                 "kaydirma, yapiyi degistirmez). Korelasyon icin ciftin "
                 f"HER IKI tarafinda >= {MIN_DAYS} aktif gun ister. "
                 "Kohort: yalniz WIN/LOSS/EXPIRED (gercek pozisyonlar). "
                 "Aday kapanis gunu entry_ts + tutus yaklasik atfidir "
                 "(mum boslugunda gercek kapanistan sapabilir); sampiyonda "
                 "closed_utc kullanilir. N_eff yalniz OLCULEN ciftlerin "
                 "evreninden turetilir (n_measured)."),
        "min_days": MIN_DAYS,
        "basis": "gross_daily_r",
        "strategies": {k: {"active_days": len(v),
                           "retired": retired.get(k)}
                       for k, v in sorted(series.items())},
        "daily_corr": matrix,
        "independence": effective_bets(matrix, len(series)),
        "same_day_same_dir": direction_overlap(opens),
    }
