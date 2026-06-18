"""Tiny logging setup built on rich (falls back to stdlib if rich is absent)."""

from __future__ import annotations

import logging
import os


def get_logger(name: str = "jarvis") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = os.getenv("JARVIS_LOG_LEVEL", "INFO").upper()
    logger.setLevel(level)

    try:
        from rich.logging import RichHandler

        handler: logging.Handler = RichHandler(rich_tracebacks=True, show_path=False)
        fmt = "%(message)s"
    except ImportError:  # pragma: no cover - rich is a core dep but be safe
        handler = logging.StreamHandler()
        fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"

    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
