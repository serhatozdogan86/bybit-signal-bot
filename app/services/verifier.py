"""
BAGIMSIZ SONUC DENETCISI (v3.6).

Neden ayri bir dosya ve ayri bir implementasyon:
Tracker'in kendi degerlendirme dongusunu tekrar kullanan bir denetim,
o dongudeki hatayi goremez - hata kendini dogrular. Bu modul sonucu
mumlardan SIFIRDAN, sade kurallarla yeniden turetir ve kayitla karsilastirir.
Iki bagimsiz yol ayni cevabi vermiyorsa en az biri yanlistir; denetci
kimin yanildigini soylemez, sadece "uyusmazlik" der ve insana getirir.

Kural seti (kasten en sade hali):
  1. entry_candle_ts'ten itibaren fill_window mum icinde giris bolgesine
     dokunuldu mu? Hayir -> NOT_FILLED.
  2. Dolus mumundan ITIBAREN (oncesi asla sayilmaz): once STOP mu TP mi?
     Ayni mumda ikisi de -> AMBIGUOUS (yol bilinemez).
  3. max_track mum icinde ikisi de olmadi -> EXPIRED.
Bu, mum-ici yol bilgisi olmadan verilebilecek en muhafazakar karardir.
"""
from __future__ import annotations


def replay(sig: dict, candles: list[dict], fill_window: int,
           max_track: int) -> dict:
    """Sinyali mumlardan yeniden oynat. Donen: {outcome, fill_ts, r, reason}."""
    is_long = sig["direction"] == "LONG"
    entry = sig["entry_max"] if is_long else sig["entry_min"]
    stop, tp1 = sig["stop_loss"], sig["tp1"]
    if entry is None or stop is None or tp1 is None:
        return {"outcome": None, "reason": "plan eksik"}
    seq = [c for c in candles if c["ts"] >= sig["entry_candle_ts"]]
    if not seq:
        return {"outcome": None, "reason": "mum yok"}

    # --- 1) dolus ---
    fill_idx = None
    for i, c in enumerate(seq[:fill_window]):
        if (c["low"] <= entry) if is_long else (c["high"] >= entry):
            fill_idx = i
            break
    if fill_idx is None:
        if len(seq) < fill_window:
            return {"outcome": None, "reason": "dolus penceresi tamamlanmadi"}
        return {"outcome": "NOT_FILLED", "fill_ts": None, "r": 0.0,
                "reason": f"{fill_window} mumda bolgeye dokunulmadi"}

    risk = (entry - stop) if is_long else (stop - entry)
    if risk <= 0:
        return {"outcome": "AMBIGUOUS", "r": 0.0, "reason": "risk<=0"}
    fill_ts = seq[fill_idx]["ts"]

    # --- 2) sonuc: YALNIZ dolus mumu ve sonrasi ---
    for j, c in enumerate(seq[fill_idx:]):
        hit_stop = (c["low"] <= stop) if is_long else (c["high"] >= stop)
        hit_tp = (c["high"] >= tp1) if is_long else (c["low"] <= tp1)
        if hit_stop and hit_tp:
            return {"outcome": "AMBIGUOUS", "fill_ts": fill_ts, "r": -1.0,
                    "reason": "ayni mumda TP ve STOP - yol bilinemez"}
        if hit_stop:
            return {"outcome": "LOSS", "fill_ts": fill_ts, "r": -1.0,
                    "reason": f"stop, dolustan {j} mum sonra"}
        if hit_tp:
            reward = (tp1 - entry) if is_long else (entry - tp1)
            return {"outcome": "WIN", "fill_ts": fill_ts,
                    "r": round(reward / risk, 2),
                    "reason": f"tp1, dolustan {j} mum sonra"}
        if j >= max_track:
            return {"outcome": "EXPIRED", "fill_ts": fill_ts, "r": None,
                    "reason": "izleme suresi doldu"}
    return {"outcome": None, "fill_ts": fill_ts, "reason": "hala acik"}


def compare(sig: dict, replayed: dict) -> dict | None:
    """Kayit ile yeniden oynatma uyusuyor mu? Uyusmazlik varsa rapor doner."""
    if replayed.get("outcome") is None:
        return None                       # denetlenemez (veri yetersiz)
    stored = sig.get("outcome")
    if stored is None:
        return None                       # kayit henuz acik
    problems = []
    if stored != replayed["outcome"]:
        problems.append(f"sonuc: kayit={stored} denetci={replayed['outcome']}")
    if (sig.get("fill_ts") and replayed.get("fill_ts")
            and sig["fill_ts"] != replayed["fill_ts"]):
        problems.append("dolus ani farkli")
    r_s, r_v = sig.get("r_multiple"), replayed.get("r")
    if r_s is not None and r_v is not None and abs(r_s - r_v) > 0.05:
        problems.append(f"R: kayit={r_s} denetci={r_v}")
    if not problems:
        return None
    return {"id": sig.get("id"), "pair": sig.get("pair"),
            "direction": sig.get("direction"), "problems": problems,
            "verifier_reason": replayed.get("reason")}
