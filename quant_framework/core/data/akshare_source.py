"""AkShare-based data source implementation for Chinese A-share market."""

import logging
import time
from datetime import date, datetime
from typing import List, Optional

import pandas as pd

from core.data.base import DataSource
from core.data.cache import DataCache

logger = logging.getLogger(__name__)


class AkShareSource(DataSource):
    """Data source implementation using the akshare library.

    Fetches Chinese A-share market data from various free endpoints
    (East Money, Sina, Baidu) via akshare. Results are cached on disk
    to avoid repeated API calls.

    Attributes:
        cache: DataCache instance for disk-based caching.
        cache_enabled: Whether caching is active.
        request_delay: Seconds to sleep between API calls to avoid rate limits.
    """

    def __init__(
        self,
        cache_dir: str = ".cache/data",
        ttl_seconds: int = 86400,
        cache_enabled: bool = True,
        request_delay: float = 0.3,
    ) -> None:
        """Initialize the AkShare data source.

        Args:
            cache_dir: Directory for disk cache files.
            ttl_seconds: Cache time-to-live in seconds (default 24h).
            cache_enabled: Enable/disable caching.
            request_delay: Delay between API calls in seconds.
        """
        self.cache = DataCache(
            cache_dir=cache_dir,
            ttl_seconds=ttl_seconds,
            format="parquet",
        )
        self.cache_enabled = cache_enabled
        self.request_delay = request_delay
        self._trade_days_cache: Optional[List[date]] = None

    @staticmethod
    def _normalize_date(d: str) -> str:
        """Convert date string to YYYYMMDD format.

        Args:
            d: Date string in "YYYYMMDD" or "YYYY-MM-DD" format.

        Returns:
            Normalized date string in "YYYYMMDD" format.
        """
        return d.replace("-", "")

    def _sleep(self) -> None:
        """Sleep to avoid rate limiting."""
        if self.request_delay > 0:
            time.sleep(self.request_delay)

    def get_index_prices(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV prices for a market index.

        Uses akshare's stock_zh_index_daily_em which sources data from
        East Money. Index codes should be prefixed appropriately:
        - "sh" for Shanghai indices (e.g. "sh000001")
        - "sz" for Shenzhen indices (e.g. "sz399001")
        - "csi" for CSI indices (e.g. "csi000300")

        Args:
            index_code: Index identifier (e.g. "000300", "sh000001").
            start_date: Start date in "YYYYMMDD" or "YYYY-MM-DD" format.
            end_date: End date in "YYYYMMDD" or "YYYY-MM-DD" format.

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount.
            Returns empty DataFrame on error.
        """
        import akshare as ak

        start = self._normalize_date(start_date)
        end = self._normalize_date(end_date)

        code = index_code.strip()
        symbol = self._resolve_index_symbol(code)

        def _fetch() -> pd.DataFrame:
            try:
                self._sleep()
                df = ak.stock_zh_index_daily_em(
                    symbol=symbol,
                    start_date=start,
                    end_date=end,
                )
                if df is None or df.empty:
                    logger.warning("No data returned for index %s", code)
                    return pd.DataFrame()

                df = df.rename(
                    columns={
                        "date": "date",
                        "open": "open",
                        "high": "high",
                        "low": "low",
                        "close": "close",
                        "volume": "volume",
                        "turnover": "amount",
                    }
                )

                col_map = {}
                for col in df.columns:
                    if "\u65e5\u671f" in col or col == "date":
                        col_map[col] = "date"
                    elif "\u5f00\u76d8" in col or col == "open":
                        col_map[col] = "open"
                    elif "\u6700\u9ad8" in col or col == "high":
                        col_map[col] = "high"
                    elif "\u6700\u4f4e" in col or col == "low":
                        col_map[col] = "low"
                    elif "\u6536\u76d8" in col or col == "close":
                        col_map[col] = "close"
                    elif "\u6210\u4ea4\u91cf" in col or col == "volume":
                        col_map[col] = "volume"
                    elif (
                        "\u6210\u4ea4\u989d" in col
                        or col == "turnover"
                        or col == "amount"
                    ):
                        col_map[col] = "amount"

                df = df.rename(columns=col_map)

                required = {"date", "open", "high", "low", "close", "volume"}
                if not required.issubset(set(df.columns)):
                    logger.warning(
                        "Index data missing columns. Got: %s", list(df.columns)
                    )

                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date").reset_index(drop=True)

                numeric_cols = ["open", "high", "low", "close", "volume"]
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                if "amount" in df.columns:
                    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

                df["code"] = code
                return df

            except Exception as e:
                logger.error("Failed to fetch index prices for %s: %s", code, e)
                return pd.DataFrame()

        if self.cache_enabled:
            return self.cache.get_or_compute(
                _fetch, index_code, start_date, end_date, fmt="parquet"
            )
        return _fetch()

    def get_stock_prices(
        self,
        stock_codes: List[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV prices for one or more stocks.

        Uses akshare's stock_zh_a_hist with forward-adjusted (qfq) prices.

        Args:
            stock_codes: List of 6-digit stock codes (e.g. ["000001", "600000"]).
            start_date: Start date in "YYYYMMDD" or "YYYY-MM-DD" format.
            end_date: End date in "YYYYMMDD" or "YYYY-MM-DD" format.

        Returns:
            DataFrame with columns: code, date, open, high, low, close, volume, amount.
            Returns empty DataFrame if all fetches fail.
        """
        import akshare as ak

        start = self._normalize_date(start_date)
        end = self._normalize_date(end_date)
        frames: list[pd.DataFrame] = []

        for code in stock_codes:
            code = code.strip().zfill(6)

            def _fetch_single(c: str = code) -> pd.DataFrame:
                try:
                    self._sleep()
                    df = ak.stock_zh_a_hist(
                        symbol=c,
                        period="daily",
                        start_date=start,
                        end_date=end,
                        adjust="qfq",
                    )
                    if df is None or df.empty:
                        return pd.DataFrame()

                    df = df.rename(
                        columns={
                            "\u65e5\u671f": "date",
                            "\u5f00\u76d8": "open",
                            "\u6700\u9ad8": "high",
                            "\u6700\u4f4e": "low",
                            "\u6536\u76d8": "close",
                            "\u6210\u4ea4\u91cf": "volume",
                            "\u6210\u4ea4\u989d": "amount",
                        }
                    )

                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)

                    for col in ["open", "high", "low", "close", "volume"]:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors="coerce")
                    if "amount" in df.columns:
                        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

                    df["code"] = c
                    return df

                except Exception as e:
                    logger.error("Failed to fetch prices for %s: %s", c, e)
                    return pd.DataFrame()

            if self.cache_enabled:
                df = self.cache.get_or_compute(
                    _fetch_single, code, start_date, end_date, fmt="parquet"
                )
            else:
                df = _fetch_single()

            if df is not None and not df.empty:
                frames.append(df)

        if not frames:
            return pd.DataFrame()

        result = pd.concat(frames, ignore_index=True)
        return result

    def get_index_stocks(
        self,
        index_code: str,
        date: str,
    ) -> List[str]:
        """Get constituent stocks for an index.

        Uses akshare's index_stock_cons which sources from Sina Finance.
        Note: akshare does not support historical constituents, so this
        returns the current list regardless of the date parameter.

        Args:
            index_code: Index code (e.g. "000300", "000905").
            date: Date string (currently ignored; returns current list).

        Returns:
            List of 6-digit stock codes. Empty list on error.
        """
        import akshare as ak

        code = index_code.strip()

        def _fetch() -> List[str]:
            try:
                self._sleep()
                df = ak.index_stock_cons(symbol=code)
                if df is None or df.empty:
                    logger.warning("No constituents for index %s", code)
                    return []

                for col in df.columns:
                    if "\u4ee3\u7801" in col or "code" in col.lower():
                        return df[col].astype(str).str.zfill(6).tolist()

                logger.warning(
                    "Could not find code column in index constituents. Columns: %s",
                    list(df.columns),
                )
                return []

            except Exception as e:
                logger.error("Failed to fetch index constituents for %s: %s", code, e)
                return []

        if self.cache_enabled:
            result = self.cache.get_or_compute(_fetch, index_code, date, fmt="pickle")
            return result if result is not None else []
        return _fetch()

    def get_all_stocks(
        self,
        date: str,
    ) -> List[str]:
        """Get all listed A-share stocks.

        Uses akshare's stock_zh_a_spot_em which returns the current
        real-time snapshot of all A-shares.

        Args:
            date: Date string (currently ignored; returns current list).

        Returns:
            List of 6-digit stock codes. Empty list on error.
        """
        import akshare as ak

        def _fetch() -> List[str]:
            try:
                self._sleep()
                df = ak.stock_zh_a_spot_em()
                if df is None or df.empty:
                    return []

                for col in df.columns:
                    if "\u4ee3\u7801" in col or "code" in col.lower():
                        codes = df[col].astype(str).str.zfill(6).tolist()
                        return codes

                return []

            except Exception as e:
                logger.error("Failed to fetch all stocks: %s", e)
                return []

        if self.cache_enabled:
            result = self.cache.get_or_compute(_fetch, date, fmt="pickle")
            return result if result is not None else []
        return _fetch()

    def get_trade_days(
        self,
        start_date: str,
        end_date: str,
    ) -> List[date]:
        """Get trading days in a date range.

        Uses akshare's tool_trade_date_hist_sina which returns the full
        history of trading days from Sina Finance.

        Args:
            start_date: Start date in "YYYYMMDD" or "YYYY-MM-DD" format.
            end_date: End date in "YYYYMMDD" or "YYYY-MM-DD" format.

        Returns:
            Sorted list of Python date objects.
        """
        import akshare as ak

        start = self._normalize_date(start_date)
        end = self._normalize_date(end_date)

        if self._trade_days_cache is None:

            def _fetch_all() -> List[date]:
                try:
                    self._sleep()
                    df = ak.tool_trade_date_hist_sina()
                    if df is None or df.empty:
                        return []

                    date_col = df.columns[0]
                    dates = pd.to_datetime(df[date_col]).dt.date.tolist()
                    return sorted(dates)

                except Exception as e:
                    logger.error("Failed to fetch trade days: %s", e)
                    return []

            if self.cache_enabled:
                cached = self.cache.get("trade_days_all", fmt="pickle")
                if cached is not None:
                    self._trade_days_cache = cached
                else:
                    self._trade_days_cache = _fetch_all()
                    if self._trade_days_cache:
                        self.cache.put(
                            "trade_days_all", self._trade_days_cache, fmt="pickle"
                        )
            else:
                self._trade_days_cache = _fetch_all()

        if not self._trade_days_cache:
            return []

        start_d = datetime.strptime(start, "%Y%m%d").date()
        end_d = datetime.strptime(end, "%Y%m%d").date()

        return [d for d in self._trade_days_cache if start_d <= d <= end_d]

    def get_valuation(
        self,
        stock_codes: List[str],
        date: str,
    ) -> pd.DataFrame:
        """Fetch valuation metrics for stocks.

        Uses akshare's stock_zh_a_spot_em which includes real-time
        valuation data (PE, PB, market cap). Note: this returns current
        valuation, not historical.

        Args:
            stock_codes: List of 6-digit stock codes.
            date: Date string (currently returns latest available data).

        Returns:
            DataFrame with columns: code, pe_ratio, pb_ratio,
            market_cap, circ_market_cap. Empty DataFrame on error.
        """
        import akshare as ak

        def _fetch() -> pd.DataFrame:
            try:
                self._sleep()
                df = ak.stock_zh_a_spot_em()
                if df is None or df.empty:
                    return pd.DataFrame()

                code_col = None
                for col in df.columns:
                    if "\u4ee3\u7801" in col:
                        code_col = col
                        break

                if code_col is None:
                    logger.warning("Could not find code column in spot data")
                    return pd.DataFrame()

                df = df[
                    df[code_col]
                    .astype(str)
                    .str.zfill(6)
                    .isin([c.strip().zfill(6) for c in stock_codes])
                ]

                result = pd.DataFrame()
                result["code"] = df[code_col].astype(str).str.zfill(6)

                col_mapping = {
                    "\u603b\u5e02\u503c": "market_cap",
                    "\u6d41\u901a\u5e02\u503c": "circ_market_cap",
                    "\u5e02\u76c8\u7387(\u52a8\u6001)": "pe_ratio",
                    "\u5e02\u76c8\u7387(TTM)": "pe_ratio_ttm",
                    "\u5e02\u51c0\u7387": "pb_ratio",
                }

                for cn_name, en_name in col_mapping.items():
                    if cn_name in df.columns:
                        result[en_name] = pd.to_numeric(df[cn_name], errors="coerce")

                if (
                    "pe_ratio" not in result.columns
                    and "pe_ratio_ttm" in result.columns
                ):
                    result["pe_ratio"] = result["pe_ratio_ttm"]

                for col in ["pe_ratio", "pb_ratio", "market_cap", "circ_market_cap"]:
                    if col not in result.columns:
                        result[col] = float("nan")

                return result.reset_index(drop=True)

            except Exception as e:
                logger.error("Failed to fetch valuation data: %s", e)
                return pd.DataFrame()

        if self.cache_enabled:
            sorted_codes = tuple(sorted(stock_codes))
            return self.cache.get_or_compute(
                _fetch, "valuation", sorted_codes, date, fmt="parquet"
            )
        return _fetch()

    def get_industry_stocks(
        self,
        industry_code: str,
        date: str,
    ) -> List[str]:
        """Get stocks belonging to an industry sector.

        Uses akshare's stock_board_industry_cons_em which sources from
        East Money. The industry_code should be the industry name in
        Chinese (e.g. "\u9152\u5e97\u9910\u996e") or the industry code.

        Args:
            industry_code: Industry name or code.
            date: Date string (currently ignored; returns current list).

        Returns:
            List of 6-digit stock codes. Empty list on error.
        """
        import akshare as ak

        def _fetch() -> List[str]:
            try:
                self._sleep()
                df = ak.stock_board_industry_cons_em(symbol=industry_code)
                if df is None or df.empty:
                    logger.warning("No stocks for industry %s", industry_code)
                    return []

                for col in df.columns:
                    if "\u4ee3\u7801" in col or "code" in col.lower():
                        return df[col].astype(str).str.zfill(6).tolist()

                logger.warning(
                    "Could not find code column in industry data. Columns: %s",
                    list(df.columns),
                )
                return []

            except Exception as e:
                logger.error(
                    "Failed to fetch industry stocks for %s: %s",
                    industry_code,
                    e,
                )
                return []

        if self.cache_enabled:
            result = self.cache.get_or_compute(
                _fetch, industry_code, date, fmt="pickle"
            )
            return result if result is not None else []
        return _fetch()

    @staticmethod
    def _resolve_index_symbol(index_code: str) -> str:
        """Resolve a raw index code to the format expected by akshare.

        AkShare's stock_zh_index_daily_em expects symbols prefixed with
        the exchange: "sh" (Shanghai), "sz" (Shenzhen), or "csi" (CSI).

        Args:
            index_code: Raw index code (e.g. "000300", "sh000001").

        Returns:
            Properly prefixed symbol string.
        """
        code = index_code.strip().lower()

        if code.startswith(("sh", "sz", "csi")):
            return code

        if code.startswith("000") or code.startswith("880"):
            return f"sh{code}"

        if code.startswith("399"):
            return f"sz{code}"

        return f"csi{code}"
