"""Structured logging - tek satir, sabit alan sirasi: ts | level | module | mesaj."""
from __future__ import annotations

import logging


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    # Gurultulu kutuphaneleri kis
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def kv(**fields: object) -> str:
    """key=value log yardimcisi: log.info(kv(symbol=s, decision=d))"""
    return " ".join(f"{k}={v}" for k, v in fields.items())
