"""DOLUM LABORATUVARI — limit emir gercekten dolar miydi? (salt olcum)

ON-KAYIT: docs/ideas.md "H-FILL" (2026-09-22). Esikler ve hukum merdiveni
bu alet YAZILMADAN ve hicbir sayiya BAKILMADAN donduruldu (Kural 4).

SORU: maliyet modeli v0 girisi de cikisi da TAKER sayar. Oysa motorun
girisi dogasi geregi LIMIT emirdir - fiyatin geri gelip giris bolgemize
degmesini bekliyoruz. Limit emir maker tarifesine girer ve maliyet
modelinin kendi notu "limit varsayimi KANITLANANA KADAR taker" der.
Bu alet o kaniti arar.

BASTAN KABUL EDILEN SINIR (rapora da basilir): mum verisi KUYRUK
pozisyonunu gostermez. Fiyat seviyemize sadece DEGIP donerse emrimiz
siranin arkasinda kalmis olabilir. Ama fiyat seviyemizin ICINDEN
gectiyse dinlenen emir neredeyse kesin dolar. Bu, kanitin kendisi
degil, mum verisiyle ulasilabilecek EN GUCLU VEKILIDIR.

NE URETMEZ: maliyet sabiti degisikligi. Hukum DESTEKLENDI cikarsa bile
model v0 kilitli kalir; degisiklik ayri karar toplantisi + Serhat onayi
+ config-lock tutanagi ister (on-kayitta yazili).

Kural uyumu: salt-okur; motor davranisina sifir dokunus.
"""
from __future__ import annotations

# --- ON-KAYITLI SABITLER (docs/ideas.md H-FILL, 2026-09-22) ---
SAFE_BPS = 5.0            # gecis derinligi bu kadarsa dinlenen emir dolardi
MIN_FILLS = 200           # hukum icin gereken en az dolmus islem
SAFE_SHARE = 0.90         # hukum icin gereken GUVENLI payi

SINIFLAR = ("GUVENLI", "SINIRDA", "VERI_HATASI")


def penetration_bps(direction: str, edge: float, bar_low: float,
                    bar_high: float) -> float | None:
    """Limit emrin durdugu seviyeden fiyat NE KADAR ICERI girdi (bps)?

    LONG'da emir entry_max'ta dinlenir; mumun DIBI ne kadar altina
    indiyse o kadar derin gecmistir. SHORT'ta tersi.
    """
    if edge is None or edge <= 0:
        return None
    if direction == "LONG":
        if bar_low is None:
            return None
        deep = edge - bar_low
    else:
        if bar_high is None:
            return None
        deep = bar_high - edge
    return round(deep / edge * 10_000, 2)


def classify(bps: float | None) -> str | None:
    """On-kayitli siniflandirma. Esik SABIT - sonradan oynatilamaz."""
    if bps is None:
        return None
    if bps < 0:
        return "VERI_HATASI"      # dolmamis olmaliydi; sessizce atilmaz
    return "GUVENLI" if bps >= SAFE_BPS else "SINIRDA"


def verdict(n_fills: int, safe: int) -> str:
    """ON-KAYITLI MERDIVEN (sayi gorulmeden donduruldu).

    DESTEKLENDI  : >=200 dolmus islem VE GUVENLI payi >= %90
    DESTEKLENMEDI: diger her durum
    """
    if n_fills < MIN_FILLS:
        return "ORNEKLEM YETERSIZ (hukum yok)"
    return ("DESTEKLENDI" if safe / n_fills >= SAFE_SHARE
            else "DESTEKLENMEDI")


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return round(s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2, 2)


def _pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    i = max(0, min(len(s) - 1, int(q * (len(s) - 1))))
    return round(s[i], 2)


def build_report(rows: list[dict], bar_lookup) -> dict:
    """rows = dolmus sampiyon sinyalleri; bar_lookup(pair, ts) -> mum|None."""
    counts = {k: 0 for k in SINIFLAR}
    bps_all: list[float] = []
    eksik_mum = 0
    ornekler: dict[str, list[dict]] = {k: [] for k in SINIFLAR}

    for r in rows:
        is_long = r.get("direction") == "LONG"
        edge = r.get("entry_max") if is_long else r.get("entry_min")
        ts = r.get("fill_ts")
        if edge is None or ts is None:
            eksik_mum += 1
            continue
        bar = bar_lookup(r.get("pair"), ts)
        if not bar:
            eksik_mum += 1
            continue
        bps = penetration_bps(r.get("direction"), edge,
                              bar.get("low"), bar.get("high"))
        cls = classify(bps)
        if cls is None:
            eksik_mum += 1
            continue
        counts[cls] += 1
        bps_all.append(bps)
        if len(ornekler[cls]) < 5:
            ornekler[cls].append({"id": r.get("id"), "pair": r.get("pair"),
                                  "direction": r.get("direction"),
                                  "edge": edge, "bps": bps})

    n = sum(counts.values())
    safe = counts["GUVENLI"]
    return {
        "note": ("DOLUM LABORATUVARI - salt olcum. Esikler ve hukum "
                 "merdiveni docs/ideas.md H-FILL'de, bu olcum yapilmadan "
                 "ONCE donduruldu (Kural 4)."),
        "limitation": ("Mum verisi KUYRUK pozisyonunu gostermez; bu yuzden "
                       "tam kanit degil, EN GUCLU VEKILDIR. Fiyat "
                       "seviyemizin icinden gectiyse dinlenen emir "
                       "neredeyse kesin dolardi; sadece degip dondiyse "
                       "belirsizdir ve SINIRDA sayilir."),
        "prereg": {"safe_bps": SAFE_BPS, "min_fills": MIN_FILLS,
                   "safe_share": SAFE_SHARE},
        "fills_measured": n,
        "counts": counts,
        "safe_share": (round(safe / n, 4) if n else None),
        "penetration_bps": {
            "median": _median(bps_all),
            "p10": _pct(bps_all, 0.10),
            "p25": _pct(bps_all, 0.25),
            "p75": _pct(bps_all, 0.75),
        },
        "bars_missing": eksik_mum,
        "examples": ornekler,
        "verdict": verdict(n, safe),
        "if_supported": ("Maliyet modeli KENDILIGINDEN DEGISMEZ (v0 "
                         "kilitli). Yalniz GIRIS ayagi icin maker "
                         "tartisilir; cikislar piyasa olayidir, taker "
                         "KALIR. Muhurlu hukumler ACILMAZ."),
    }
