"""Data loader with AkShare API integration and local pickle caching."""

from __future__ import annotations

import hashlib
import pickle
import time
import warnings
from pathlib import Path
from typing import Optional

import pandas as pd

# AkShare column mapping: Chinese -> English
_STOCK_COL_MAP = {
    "日期": "datetime",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "money",
}

_INDEX_COL_MAP = {
    "date": "datetime",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "amount": "money",
}

_FREQ_MAP = {
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
    "1d": "daily",
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "60m": "60m",
}

_REQUIRED_COLS = {"datetime", "open", "high", "low", "close", "volume", "money"}


class DataLoader:
    """Fetch A-share stock and index data from AkShare with local caching.

    Args:
        cache_dir: Directory for pickle cache files. Defaults to ``.cache/signal_pipeline``.
        max_retries: Maximum retry attempts on API failure. Defaults to 3.
        retry_delay: Base delay (seconds) between retries. Defaults to 2.
        ttl_hours: Cache time-to-live in hours. Defaults to 24.
    """

    def __init__(
        self,
        cache_dir: str = ".cache/signal_pipeline",
        max_retries: int = 3,
        retry_delay: float = 2.0,
        ttl_hours: float = 24.0,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.ttl_hours = ttl_hours

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_stock(
        self,
        symbol: str,
        start: str,
        end: str,
        freq: str = "daily",
    ) -> pd.DataFrame:
        """Fetch daily (or intraday) OHLCV for a single A-share stock.

        Args:
            symbol: Stock code, e.g. ``"000001"`` or ``"000001.SZ"``.
            start: Start date, ``"YYYY-MM-DD"``.
            end: End date, ``"YYYY-MM-DD"``.
            freq: Data frequency. Supports ``daily``, ``weekly``, ``monthly``,
                  and intraday ``1m``, ``5m``, ``15m``, ``30m``, ``60m``.

        Returns:
            DataFrame with columns
            ``[datetime, open, high, low, close, volume, money]``,
            sorted by datetime ascending.
        """
        cache_key = self._cache_key("stock", symbol, start, end, freq)
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        code = self._strip_suffix(symbol)
        ak_freq = _FREQ_MAP.get(freq, "daily")

        df = self._retry_call(self._fetch_stock_impl, code, start, end, ak_freq)

        if df is not None and not df.empty:
            df = self._standardize(df, _STOCK_COL_MAP)
            self._put_cache(cache_key, df)

        return df if df is not None else pd.DataFrame(columns=list(_REQUIRED_COLS))

    def fetch_index(
        self,
        symbol: str,
        start: str,
        end: str,
        freq: str = "daily",
    ) -> pd.DataFrame:
        """Fetch daily OHLCV for a market index.

        Args:
            symbol: Index code, e.g. ``"000300"`` (CSI 300).
            start: Start date, ``"YYYY-MM-DD"``.
            end: End date, ``"YYYY-MM-DD"``.
            freq: Data frequency (currently only daily is reliable).

        Returns:
            DataFrame with columns
            ``[datetime, open, high, low, close, volume, money]``,
            sorted by datetime ascending.
        """
        cache_key = self._cache_key("index", symbol, start, end, freq)
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        df = self._retry_call(self._fetch_index_impl, symbol, start, end)

        if df is not None and not df.empty:
            df = self._standardize(df, _INDEX_COL_MAP)
            self._put_cache(cache_key, df)

        return df if df is not None else pd.DataFrame(columns=list(_REQUIRED_COLS))

    def clear_cache(self) -> None:
        """Remove all cached pickle files."""
        for p in self.cache_dir.glob("*.pkl"):
            p.unlink()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_suffix(symbol: str) -> str:
        """Remove exchange suffix like ``.SZ`` / ``.SH``."""
        return symbol.split(".")[0].zfill(6)

    def _cache_key(
        self, kind: str, symbol: str, start: str, end: str, freq: str
    ) -> str:
        raw = f"{kind}_{symbol}_{start}_{end}_{freq}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.pkl"

    def _get_cache(self, key: str) -> Optional[pd.DataFrame]:
        path = self._cache_path(key)
        if not path.exists():
            return None
        age_hours = (time.time() - path.stat().st_mtime) / 3600
        if age_hours > self.ttl_hours:
            path.unlink()
            return None
        with open(path, "rb") as f:
            return pickle.load(f)

    def _put_cache(self, key: str, df: pd.DataFrame) -> None:
        path = self._cache_path(key)
        with open(path, "wb") as f:
            pickle.dump(df, f)

    def _retry_call(self, func, *args, **kwargs):
        """Call *func* with exponential-backoff retry on failure."""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                result = func(*args, **kwargs)
                # Respect AkShare rate limit: brief pause after each call
                time.sleep(0.5)
                return result
            except Exception as exc:
                last_exc = exc
                delay = self.retry_delay * (2**attempt)
                warnings.warn(
                    f"AkShare call failed (attempt {attempt + 1}/{self.max_retries}): "
                    f"{exc}. Retrying in {delay:.1f}s ..."
                )
                time.sleep(delay)
        raise RuntimeError(
            f"AkShare call failed after {self.max_retries} retries"
        ) from last_exc

    @staticmethod
    def _fetch_stock_impl(code: str, start: str, end: str, freq: str) -> pd.DataFrame:
        import akshare as ak

        start_fmt = start.replace("-", "")
        end_fmt = end.replace("-", "")

        if freq in ("1m", "5m", "15m", "30m", "60m"):
            # Intraday: use spot-minute API (returns recent data only)
            df = ak.stock_zh_a_hist_min_em(symbol=code, period=freq)
        else:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period=freq,
                start_date=start_fmt,
                end_date=end_fmt,
                adjust="qfq",
            )

        if df is None or df.empty:
            return pd.DataFrame()
        return df

    @staticmethod
    def _fetch_index_impl(symbol: str, start: str, end: str) -> pd.DataFrame:
        import akshare as ak

        df = ak.stock_zh_index_daily(
            symbol=f"sh{symbol}" if symbol.startswith("0") else f"sz{symbol}"
        )
        if df is None or df.empty:
            return pd.DataFrame()

        df["date"] = pd.to_datetime(df["date"])
        mask = (df["date"] >= start) & (df["date"] <= end)
        return df.loc[mask].copy()

    @staticmethod
    def _standardize(df: pd.DataFrame, col_map: dict[str, str]) -> pd.DataFrame:
        """Rename columns, parse datetime, ensure required cols, sort ascending."""
        df = df.rename(columns=col_map)

        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])

        # Ensure all required columns exist
        for col in _REQUIRED_COLS:
            if col not in df.columns:
                df[col] = 0.0 if col in ("volume", "money") else float("nan")

        df = df[list(_REQUIRED_COLS)].copy()
        df = df.sort_values("datetime").reset_index(drop=True)
        return df
