"""CIKIS LABORATUVARI — salt olcum aleti (on-kayit ideas.md 2026-08-17).

SORU: ayni girislerle cikis kurali degisseydi ne olurdu? Kapanmis aday
sinyalleri mum arsivinden YENIDEN oynatilir:
- V0_SABIT: motorun mevcut kurali BIREBIR (stop/hedef/zaman asimi).
  Sadakat sarti: defterdeki kayitli sonucu uretmek ZORUNDA; uyumsuzluk
  sayisi raporda gorunur (olcum durustlugu sinyali).
- V1_IZ: iz suren cikis (Chandelier tarzi) — hedef yok, stop kar
  buyudukce fiyati 1 x baslangic-risk mesafesiyle takip eder. Muhafazakar
  sira: her mumda ONCE stop kontrolu, SONRA stop yukseltme (ayni mumdaki
  yeni tepe o mumun stopunu kurtaramaz).

HUKUM KURALI (onceden ilan, ideas.md): sinyal basina fark d = V1_net -
V0_net, kume = sinyalin cluster_id'si; >=50 kume VE fark kume-CI alt
siniri > 0 -> V1 o strateji icin ustun (v2 TASARIM girdisi). Ust < 0 ->
V0 ustun. Arada -> belirsiz.

Kural uyumu: SALT-OKUR (yalniz SELECT); sampiyon davranisina ve aday
defterine sifir dokunus; verifier'dan bagimsiz (import etmez). Maliyet
modeli v0 sabitleri motorla AYNI kaynaktan (signal_tracker).
"""
from __future__ import annotations

from app.services import measurement
from app.services.signal_tracker import FUNDING_8H, STOP_SLIP, TAKER_FEE

VARIANTS = ("V0_SABIT", "V1_IZ")
TRAIL_RISK_MULT = 1.0    # V1 iz mesafesi = 1 x baslangic risk (ON-KAYIT;
                         # baska katsayi denemek yeni on-kayit ister)
FIDELITY_TOL = 0.02      # V0 sadakat karsilastirma toleransi (R)
MIN_CLUSTERS = 50        # hukum esigi (sampiyonla ayni Faz-1 standardi)


def replay_v0(direction: str, entry: float, stop: float, tp: float,
              timeout_bars: int, candles: list[dict]) -> dict | None:
    """Motorun _evaluate_one kurali BIREBIR (sadakat kiyasi icin).

    Donen: {r, hold_bars, outcome, stop_exit, ambiguous} | None (mum
    bitti, pozisyon hala acik olurdu -> rapor disi)."""
    is_long = direction == "LONG"
    risk = (entry - stop) if is_long else (stop - entry)
    if risk <= 0:
        return {"r": 0.0, "hold_bars": 0, "outcome": "AMBIGUOUS",
                "stop_exit": False, "ambiguous": 1}
    for i, c in enumerate(candles):
        hit_stop = (c["low"] <= stop) if is_long else (c["high"] >= stop)
        hit_tp = (c["high"] >= tp) if is_long else (c["low"] <= tp)
        if hit_stop and hit_tp:
            return {"r": -1.0, "hold_bars": i + 1, "outcome": "LOSS",
                    "stop_exit": True, "ambiguous": 1}
        if hit_stop:
            return {"r": -1.0, "hold_bars": i + 1, "outcome": "LOSS",
                    "stop_exit": True, "ambiguous": 0}
        if hit_tp:
            rr = (tp - entry) if is_long else (entry - tp)
            return {"r": round(rr / risk, 2), "hold_bars": i + 1,
                    "outcome": "WIN", "stop_exit": False, "ambiguous": 0}
        if i + 1 >= timeout_bars:
            pnl = (c["close"] - entry) if is_long else (entry - c["close"])
            return {"r": round(pnl / risk, 2), "hold_bars": i + 1,
                    "outcome": "EXPIRED", "stop_exit": False, "ambiguous": 0}
    return None


def replay_v1(direction: str, entry: float, stop0: float,
              timeout_bars: int, candles: list[dict]) -> dict | None:
    """V1_IZ: hedefsiz, iz suren stop (on-kayit kurali birebir).

    Sira her mumda: (1) mevcut stop vuruldu mu -> stoptan cik;
    (2) sonra stop cekilir (LONG: max(stop, high - iz), SHORT ayna).
    Zaman asimi kayitli timeout_bars ile ayni (kapanistan, EXPIRED)."""
    is_long = direction == "LONG"
    risk = (entry - stop0) if is_long else (stop0 - entry)
    if risk <= 0:
        return {"r": 0.0, "hold_bars": 0, "outcome": "AMBIGUOUS",
                "stop_exit": False, "ambiguous": 1}
    trail = TRAIL_RISK_MULT * risk
    stop = stop0
    for i, c in enumerate(candles):
        hit = (c["low"] <= stop) if is_long else (c["high"] >= stop)
        if hit:
            pnl = (stop - entry) if is_long else (entry - stop)
            return {"r": round(pnl / risk, 2), "hold_bars": i + 1,
                    "outcome": "TRAIL_STOP", "stop_exit": True,
                    "ambiguous": 0}
        stop = (max(stop, c["high"] - trail) if is_long
                else min(stop, c["low"] + trail))
        if i + 1 >= timeout_bars:
            pnl = (c["close"] - entry) if is_long else (entry - c["close"])
            return {"r": round(pnl / risk, 2), "hold_bars": i + 1,
                    "outcome": "EXPIRED", "stop_exit": False, "ambiguous": 0}
    return None


def net_r(entry: float, stop0: float, r: float, stop_exit: bool,
          hold_bars: int) -> float | None:
    """Maliyet modeli v0 — motorun _net_r formulu ile ayni sabitler.
    Slip STOP cikislarinda uygulanir (iz suren stop karda da stop-emridir)."""
    if not entry:
        return None
    stop_frac = abs(entry - stop0) / entry
    if stop_frac <= 0:
        return None
    fee = 2 * TAKER_FEE / stop_frac
    slip = (STOP_SLIP / stop_frac) if stop_exit else 0.0
    funding = FUNDING_8H * (hold_bars * 0.25 / 8.0) / stop_frac
    return r - fee - slip - funding


def verdict(n_clusters: int, ci_low: float | None,
            ci_high: float | None) -> str:
    """On-kayitli hukum kurali (fark serisi d = V1_net - V0_net uzerinde)."""
    if n_clusters < MIN_CLUSTERS or ci_low is None or ci_high is None:
        return "VERI_BIRIKIYOR"
    if ci_low > 0:
        return "V1_USTUN"
    if ci_high < 0:
        return "V0_USTUN"
    return "BELIRSIZ"


def build_report(db, sampling_regime: int, ltf: str = "15") -> dict:
    """Canli DB baglantisindan (salt SELECT) tam rapor uret."""
    per: dict[str, dict] = {}
    v0_mismatch = 0
    incomplete = 0
    replayed = 0
    rows = db.query(
        "SELECT * FROM challenger_signals WHERE status='CLOSED'")
    for r in rows:
        if (r.get("regime") or 1) != sampling_regime:
            continue
        if r["outcome"] not in ("WIN", "LOSS", "EXPIRED") \
                or r.get("r_multiple") is None or not r.get("entry"):
            continue
        candles = db.query(
            "SELECT ts,high,low,close FROM candles WHERE symbol=? AND "
            "interval=? AND ts>? ORDER BY ts ASC LIMIT ?",
            (r["pair"], ltf, r["entry_ts"], int(r["timeout_bars"] or 0)))
        v0 = replay_v0(r["direction"], r["entry"], r["stop"], r["tp"],
                       r["timeout_bars"], candles)
        v1 = replay_v1(r["direction"], r["entry"], r["stop"],
                       r["timeout_bars"], candles)
        if v0 is None or v1 is None:
            incomplete += 1          # mum arsivi eksik: durustce sayilir
            continue
        replayed += 1
        if v0["outcome"] != r["outcome"] \
                or abs(v0["r"] - r["r_multiple"]) > FIDELITY_TOL:
            v0_mismatch += 1
        n0 = net_r(r["entry"], r["stop"], v0["r"], v0["stop_exit"],
                   v0["hold_bars"])
        n1 = net_r(r["entry"], r["stop"], v1["r"], v1["stop_exit"],
                   v1["hold_bars"])
        if n0 is None or n1 is None:
            continue
        s = per.setdefault(r["strategy"], {
            "n": 0, "v0_net": 0.0, "v1_net": 0.0,
            "v0_cl": {}, "v1_cl": {}, "d_cl": {}})
        s["n"] += 1
        s["v0_net"] += n0
        s["v1_net"] += n1
        cid = r["cluster_id"] or "?"
        s["v0_cl"].setdefault(cid, []).append(n0)
        s["v1_cl"].setdefault(cid, []).append(n1)
        s["d_cl"].setdefault(cid, []).append(n1 - n0)

    strategies: dict[str, dict] = {}
    for strat, s in sorted(per.items()):
        b0 = measurement.cluster_bootstrap(s["v0_cl"])
        b1 = measurement.cluster_bootstrap(s["v1_cl"])
        bd = measurement.cluster_bootstrap(s["d_cl"])
        ci_low = bd.get("ci_low") if bd else None
        ci_high = bd.get("ci_high") if bd else None
        strategies[strat] = {
            "n": s["n"], "clusters": len(s["d_cl"]),
            "V0_SABIT": {"net_r": round(s["v0_net"], 2),
                         "e_net": b0["e_net"] if b0 else None},
            "V1_IZ": {"net_r": round(s["v1_net"], 2),
                      "e_net": b1["e_net"] if b1 else None},
            "fark_v1_eksi_v0": {
                "e": bd["e_net"] if bd else None,
                "ci": ([ci_low, ci_high] if ci_low is not None else None),
            },
            "hukum": verdict(len(s["d_cl"]), ci_low, ci_high),
        }
    return {
        "note": ("CIKIS LABORATUVARI — salt olcum, hicbir karari "
                 "degistirmez (on-kayit ideas.md 2026-08-17). Kapanmis "
                 "aday sinyalleri mum arsivinden yeniden oynatilir: "
                 "V0_SABIT = motor kurali birebir (sadakat kiyasi), "
                 "V1_IZ = hedefsiz iz suren stop (iz = 1 x baslangic "
                 "risk). Hukum fark serisinin (V1_net - V0_net) kume-CI'si "
                 f"ile, >= {MIN_CLUSTERS} kumede. V1 ustun cikarsa v2 "
                 "TASARIM girdisi olur; motora asla dogrudan girmez. "
                 "Yatirim tavsiyesi degildir."),
        "variants": list(VARIANTS),
        "trail_risk_mult": TRAIL_RISK_MULT,
        "min_clusters": MIN_CLUSTERS,
        "replayed": replayed,
        "incomplete_candles": incomplete,
        "v0_fidelity_mismatch": v0_mismatch,
        "strategies": strategies,
    }
