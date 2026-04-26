"""Shared logging helpers for strategy_kits."""
from __future__ import annotations

import logging
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Get module logger with a predictable namespace."""
    return logging.getLogger(f"strategy_kits.{name}")


def log_kv(logger: logging.Logger, level: int, event: str, **kwargs: Any) -> None:
    """Log key-value events in a compact, grep-friendly format."""
    if kwargs:
        payload = " ".join(f"{k}={kwargs[k]}" for k in sorted(kwargs))
        logger.log(level, "%s | %s", event, payload)
        return
    logger.log(level, event)

