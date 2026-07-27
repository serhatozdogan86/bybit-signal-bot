"""
Orderbook likidite haritasi (Phase 2, ORDERBOOK_ENRICH=true ile aktif).
Saf fonksiyon: Bybit orderbook snapshot'indan buyuk bid/ask duvarlarini bulur.
SADECE bilgilendirme notudur - karar filtresi DEGILDIR (structure-first ilkesi).
"""
from __future__ import annotations

_PROXIMITY = 0.02  # mid fiyata %2 mesafedeki seviyeler incelenir
_WALL_MULT = 3.0   # ortalama seviyenin 3 kati -> duvar sayilir


def orderbook_note(orderbook: dict) -> str:
    """
    Bybit /v5/market/orderbook result formati: {"b": [[price,size],...], "a": [...]}
    Donus: "bid wall 120.5 @ 42000 | ask wall 98.2 @ 43500" veya "".
    """
    try:
        bids = [(float(p), float(s)) for p, s in orderbook.get("b", [])]
        asks = [(float(p), float(s)) for p, s in orderbook.get("a", [])]
        if not bids or not asks:
            return ""
        mid = (bids[0][0] + asks[0][0]) / 2
        notes: list[str] = []
        for side, levels in (("bid", bids), ("ask", asks)):
            near = [(p, s) for p, s in levels if abs(p - mid) / mid <= _PROXIMITY]
            if len(near) < 3:
                continue
            price, size = max(near, key=lambda x: x[1])
            others = [s for p, s in near if (p, s) != (price, size)]
            avg = sum(others) / len(others) if others else 0.0
            if avg > 0 and size >= _WALL_MULT * avg:
                notes.append(f"{side} wall {size:.4g} @ {price:.6g}")
        return " | ".join(notes)
    except (ValueError, TypeError, IndexError):
        return ""
