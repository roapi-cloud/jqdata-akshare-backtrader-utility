"""Logging utilities for the quantitative trading framework.

Provides a configurable logging system with console and file output,
log rotation, and per-module log level control.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: str = "logs",
    max_bytes: int = 10_485_760,
    backup_count: int = 5,
    fmt: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt: str = "%Y-%m-%d %H:%M:%S",
) -> logging.Logger:
    """Configure and return the root logger for the framework.

    Sets up console logging (stdout) and optional file logging with
    size-based rotation. Existing handlers on the root logger are
    removed to prevent duplicate output.

    Args:
        level: Logging level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Name of the log file. If None, file logging is disabled.
        log_dir: Directory where log files are stored.
        max_bytes: Maximum size of a single log file before rotation.
        backup_count: Number of rotated log files to retain.
        fmt: Log record format string.
        datefmt: Date/time format string for log timestamps.

    Returns:
        Configured root logger for the quant_framework.

    Example:
        >>> logger = setup_logging(level="DEBUG", log_file="quant.log")
        >>> logger.info("Framework initialized")
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger("quant_framework")
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates on re-initialization
    root_logger.handlers.clear()

    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_file:
        log_path = Path(log_dir) / log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    for noisy_logger in ("urllib3", "requests", "matplotlib"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance as a child of the framework root logger.

    Args:
        name: Logger name, typically ``__name__`` of the calling module.

    Returns:
        Logger instance that inherits handlers from the root logger.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.debug("Debug message from this module")
    """
    if not name.startswith("quant_framework"):
        name = f"quant_framework.{name}"
    return logging.getLogger(name)


def set_module_level(module_name: str, level: str) -> None:
    """Set the logging level for a specific module.

    Useful for enabling verbose logging in a single component without
    changing the global level.

    Args:
        module_name: Module name (e.g., "quant_framework.core.backtest").
        level: Logging level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Example:
        >>> set_module_level("quant_framework.core.backtest.engine", "DEBUG")
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger(module_name).setLevel(numeric_level)


def add_file_handler(
    log_file: str,
    log_dir: str = "logs",
    level: str = "INFO",
    max_bytes: int = 10_485_760,
    backup_count: int = 5,
    fmt: Optional[str] = None,
    datefmt: str = "%Y-%m-%d %H:%M:%S",
) -> RotatingFileHandler:
    """Add an additional file handler to the root logger.

    Useful for directing specific log levels or modules to separate files.

    Args:
        log_file: Name of the log file.
        log_dir: Directory where log files are stored.
        level: Logging level for this handler.
        max_bytes: Maximum size before rotation.
        backup_count: Number of backup files to keep.
        fmt: Custom format string (uses root logger format if None).
        datefmt: Date format string.

    Returns:
        The created RotatingFileHandler instance.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    log_path = Path(log_dir) / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt is None:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    handler = RotatingFileHandler(
        filename=str(log_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(numeric_level)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger("quant_framework")
    root_logger.addHandler(handler)

    return handler
