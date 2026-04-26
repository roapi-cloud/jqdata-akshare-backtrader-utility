"""Symbol normalization primitives shared by gateways and runtimes."""
from __future__ import annotations

import re
from typing import Final

_KNOWN_SH_INDEXES: Final[set[str]] = {
    "000001",
    "000016",
    "000300",
    "000688",
    "000852",
    "000903",
    "000905",
    "000906",
    "000978",
}


def format_stock_symbol(symbol: str | None) -> str | None:
    """Normalize a symbol-like input to its 6-digit numeric body."""
    if symbol is None:
        return None

    raw = str(symbol).strip()
    if not raw:
        return None

    if len(raw) >= 8 and raw[:2].lower() in {"sh", "sz"} and raw[2:].isdigit():
        return raw[2:].zfill(6)

    if "." in raw:
        head = raw.split(".", 1)[0]
        if head.isdigit():
            return head.zfill(6)

    if raw.isdigit():
        return raw.zfill(6)

    matched = re.search(r"(\d{6})", raw)
    if matched:
        return matched.group(1)

    return None


def _infer_exchange(code: str) -> str:
    """Infer exchange from a bare code when no suffix/prefix is provided."""
    if code in _KNOWN_SH_INDEXES:
        return "XSHG"
    if code.startswith("399"):
        return "XSHE"
    if code.startswith(("5", "6", "9")) or code[:2] in {"11", "13"}:
        return "XSHG"
    return "XSHE"


def to_jq(code: str) -> str:
    """
    Convert common symbol formats to JoinQuant style.

    Supported examples:
    - ``sh600000`` / ``SH600000``
    - ``600000.XSHG`` / ``600000.SH``
    - ``000001.XSHE`` / ``000001.SZ``
    - ``600000`` / ``000001``
    """
    raw = str(code).strip()
    if not raw:
        raise ValueError("empty symbol is not allowed")

    lowered = raw.lower()
    if len(raw) >= 8 and lowered[:2] in {"sh", "sz"} and raw[2:].isdigit():
        exchange = "XSHG" if lowered.startswith("sh") else "XSHE"
        return f"{raw[2:].zfill(6)}.{exchange}"

    if "." in raw:
        body, suffix = raw.split(".", 1)
        body = body.zfill(6)
        upper_suffix = suffix.upper()
        if upper_suffix in {"XSHG", "SH", "SS"}:
            return f"{body}.XSHG"
        if upper_suffix in {"XSHE", "SZ"}:
            return f"{body}.XSHE"

    numeric = format_stock_symbol(raw)
    if numeric is None:
        raise ValueError(f"unable to normalize symbol: {code}")
    return f"{numeric}.{_infer_exchange(numeric)}"


def to_ak(code: str) -> str:
    """Convert to AkShare style: ``sh600000`` / ``sz000001``."""
    jq = to_jq(code)
    numeric, exchange = jq.split(".", 1)
    prefix = "sh" if exchange == "XSHG" else "sz"
    return f"{prefix}{numeric}"


def to_ts(code: str) -> str:
    """Convert to TuShare style: ``600000.SH`` / ``000001.SZ``."""
    jq = to_jq(code)
    numeric, exchange = jq.split(".", 1)
    suffix = "SH" if exchange == "XSHG" else "SZ"
    return f"{numeric}.{suffix}"


def to_qlib(code: str) -> str:
    """Convert to Qlib style: ``SH600000`` / ``SZ000001``."""
    jq = to_jq(code)
    numeric, exchange = jq.split(".", 1)
    prefix = "SH" if exchange == "XSHG" else "SZ"
    return f"{prefix}{numeric}"


def normalize_symbol(symbol: str | None) -> str | None:
    """Backward-compatible alias returning the 6-digit numeric body."""
    return format_stock_symbol(symbol)


def get_symbol_prefix(symbol: str) -> str:
    """Return ``sh`` or ``sz`` according to the canonical exchange."""
    return "sh" if to_jq(symbol).endswith(".XSHG") else "sz"


def is_valid_stock_code(symbol: str | None) -> bool:
    """Return whether the input looks like a stock/index code we can normalize."""
    if symbol is None:
        return False
    raw = str(symbol).strip()
    if not raw:
        return False
    return (
        re.fullmatch(r"[sS][hHzZ]\d{6}", raw) is not None
        or re.fullmatch(r"\d{6}", raw) is not None
        or re.fullmatch(r"\d{6}\.(XSHG|XSHE|SH|SZ|xshg|xshe|sh|sz)", raw) is not None
    )


def canonicalize(code: str) -> str:
    """Return the package-wide canonical symbol format (JoinQuant style)."""
    return to_jq(code)


jq_code_to_ak = to_ak
ak_code_to_jq = to_jq
format_stock_symbol_for_akshare = format_stock_symbol

__all__ = [
    "format_stock_symbol",
    "format_stock_symbol_for_akshare",
    "normalize_symbol",
    "canonicalize",
    "to_jq",
    "to_ak",
    "to_ts",
    "to_qlib",
    "jq_code_to_ak",
    "ak_code_to_jq",
    "get_symbol_prefix",
    "is_valid_stock_code",
]
