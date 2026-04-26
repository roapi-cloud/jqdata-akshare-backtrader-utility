"""Data source abstractions for market data retrieval."""

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

import pandas as pd


class BaseDataSource(ABC):
    """Abstract base class for data sources."""

    @abstractmethod
    def get_daily_bars(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV bars for a symbol.

        Args:
            symbol: Stock code / ticker.
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount.
        """
        ...

    @abstractmethod
    def get_symbol_list(self) -> list[str]:
        """Return list of available symbols."""
        ...


class AkShareDataSource(BaseDataSource):
    """Data source using AkShare library for Chinese A-share market data."""

    def __init__(self) -> None:
        self._cache: dict[str, pd.DataFrame] = {}

    def get_daily_bars(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        import akshare as ak

        cache_key = f"{symbol}_{start_date}_{end_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq",
        )

        df = df.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
            }
        )
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        df["code"] = symbol

        self._cache[cache_key] = df
        return df

    def get_symbol_list(self) -> list[str]:
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        return df["代码"].tolist()
