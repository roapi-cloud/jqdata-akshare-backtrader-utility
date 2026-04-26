"""Helper utilities for the quantitative trading framework.

Provides common functions for date parsing, data validation,
symbol normalization, and other shared operations.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd


def parse_date(date_str: str) -> date:
    """Parse a date string into a date object.

    Supports the formats YYYY-MM-DD, YYYY/MM/DD, and YYYYMMDD.

    Args:
        date_str: Date string to parse.

    Returns:
        Parsed date object.

    Raises:
        ValueError: If the date string cannot be parsed.

    Example:
        >>> parse_date("2023-01-15")
        datetime.date(2023, 1, 15)
        >>> parse_date("20230115")
        datetime.date(2023, 1, 15)
    """
    date_str = date_str.strip()

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    raise ValueError(
        f"Unable to parse date '{date_str}'. "
        f"Supported formats: YYYY-MM-DD, YYYY/MM/DD, YYYYMMDD"
    )


def format_date(d: Union[date, datetime, str], fmt: str = "%Y-%m-%d") -> str:
    """Format a date object or string into the specified format.

    Args:
        d: Date object, datetime object, or date string.
        fmt: Output format string (default: %Y-%m-%d).

    Returns:
        Formatted date string.

    Raises:
        ValueError: If the input cannot be formatted.
    """
    if isinstance(d, str):
        d = parse_date(d)
    elif isinstance(d, datetime):
        d = d.date()

    if not isinstance(d, date):
        raise ValueError(f"Expected date, datetime, or str, got {type(d).__name__}")

    return d.strftime(fmt)


def validate_date_range(
    start: Union[date, str], end: Union[date, str]
) -> tuple[date, date]:
    """Validate and normalize a date range.

    Args:
        start: Start date (date object or string).
        end: End date (date object or string).

    Returns:
        Tuple of (start_date, end_date) as date objects.

    Raises:
        ValueError: If dates are invalid or start >= end.
    """
    if isinstance(start, str):
        start = parse_date(start)
    if isinstance(end, str):
        end = parse_date(end)

    if start >= end:
        raise ValueError(
            f"start_date ({start}) must be strictly before end_date ({end})"
        )

    return start, end


def normalize_symbol(symbol: str) -> str:
    """Normalize a stock symbol to a standard format.

    Converts various symbol formats to the canonical format used
    internally (e.g., "000001.SZ" or "000001.XSHE").

    Args:
        symbol: Raw stock symbol string.

    Returns:
        Normalized symbol string.

    Example:
        >>> normalize_symbol("000001")
        '000001.XSHE'
        >>> normalize_symbol("600000.SH")
        '600000.XSHG'
    """
    symbol = symbol.strip().upper()

    # Already in exchange format
    if "." in symbol:
        code, exchange = symbol.split(".", 1)
        code = code.zfill(6)
        if exchange in ("SH", "XSHG", "SSE"):
            return f"{code}.XSHG"
        elif exchange in ("SZ", "XSHE", "SZSE"):
            return f"{code}.XSHE"
        return f"{code}.{exchange}"

    # Pure numeric code - infer exchange from first digit
    if symbol.isdigit():
        code = symbol.zfill(6)
        if code.startswith(("6", "9")):
            return f"{code}.XSHG"
        elif code.startswith(("0", "3")):
            return f"{code}.XSHE"
        return f"{code}.XSHG"

    return symbol


def validate_dataframe(
    df: pd.DataFrame,
    required_columns: Optional[List[str]] = None,
    allow_empty: bool = False,
) -> bool:
    """Validate that a DataFrame meets basic requirements.

    Args:
        df: DataFrame to validate.
        required_columns: List of column names that must be present.
        allow_empty: If False, raises an error on empty DataFrames.

    Returns:
        True if validation passes.

    Raises:
        TypeError: If the input is not a DataFrame.
        ValueError: If required columns are missing or DataFrame is empty.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df).__name__}")

    if not allow_empty and df.empty:
        raise ValueError("DataFrame is empty")

    if required_columns:
        missing = set(required_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

    return True


def ensure_ohlcv_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure a DataFrame has standard OHLCV columns with correct types.

    Normalizes column names (e.g., "close" / "Close" / "CLOSE") and
    coerces numeric columns to float.

    Args:
        df: DataFrame with price/volume data.

    Returns:
        DataFrame with normalized OHLCV columns.

    Raises:
        ValueError: If required OHLCV columns cannot be found.
    """
    df = df.copy()

    # Normalize column names to lowercase
    df.columns = [col.strip().lower() for col in df.columns]

    required = ["open", "high", "low", "close", "volume"]
    missing = set(required) - set(df.columns)

    # Try common alternative names
    aliases = {
        "open": ["open", "open_price"],
        "high": ["high", "high_price"],
        "low": ["low", "low_price"],
        "close": ["close", "close_price", "price"],
        "volume": ["volume", "vol", "turnover"],
    }

    for col in list(missing):
        for alias in aliases.get(col, []):
            if alias in df.columns and alias != col:
                df.rename(columns={alias: col}, inplace=True)
                missing.discard(col)
                break

    if missing:
        raise ValueError(f"Cannot resolve OHLCV columns, missing: {sorted(missing)}")

    # Coerce numeric columns
    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def calculate_returns(prices: pd.Series) -> pd.Series:
    """Calculate daily simple returns from a price series.

    Args:
        prices: Series of prices indexed by date.

    Returns:
        Series of daily returns (first value is NaN).
    """
    return prices.pct_change()


def calculate_log_returns(prices: pd.Series) -> pd.Series:
    """Calculate daily log returns from a price series.

    Args:
        prices: Series of prices indexed by date.

    Returns:
        Series of daily log returns (first value is NaN).
    """
    return (prices / prices.shift(1)).apply(
        lambda x: __import__("math").log(x) if x > 0 else float("nan")
    )


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning a default on division by zero.

    Args:
        numerator: The numerator.
        denominator: The denominator.
        default: Value to return if denominator is zero.

    Returns:
        The quotient, or default if denominator is zero.
    """
    if denominator == 0:
        return default
    return numerator / denominator


def truncate_dict_values(data: Dict[str, Any], max_length: int = 100) -> Dict[str, Any]:
    """Truncate list and string values in a dictionary for logging.

    Useful for safely printing large configuration dictionaries
    without flooding the log output.

    Args:
        data: Dictionary to truncate.
        max_length: Maximum length for list/string values.

    Returns:
        New dictionary with truncated values.
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, list) and len(value) > max_length:
            result[key] = value[:max_length] + [f"... ({len(value) - max_length} more)"]
        elif isinstance(value, str) and len(value) > max_length:
            result[key] = value[:max_length] + "..."
        elif isinstance(value, dict):
            result[key] = truncate_dict_values(value, max_length)
        else:
            result[key] = value
    return result


def is_trading_day_check_enabled() -> bool:
    """Return whether trading day checks are enabled.

    Reads the environment variable QUANT_ENABLE_TRADING_DAY_CHECK.

    Returns:
        True if trading day validation should be performed.
    """
    import os

    return os.environ.get("QUANT_ENABLE_TRADING_DAY_CHECK", "0").lower() in (
        "1",
        "true",
        "yes",
    )
