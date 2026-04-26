"""Abstract base class for quantitative trading data sources."""

from abc import ABC, abstractmethod
from datetime import date
from typing import List

import pandas as pd


class DataSource(ABC):
    """Abstract base class defining the interface for all data sources.

    All concrete data source implementations (AkShare, JQData, etc.)
    must inherit from this class and implement every abstract method.

    The interface is designed around Chinese A-share market data,
    returning consistently named pandas DataFrames.
    """

    @abstractmethod
    def get_index_prices(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV prices for a market index.

        Args:
            index_code: Index identifier (e.g. "000300" for CSI 300).
            start_date: Start date in "YYYYMMDD" or "YYYY-MM-DD" format.
            end_date: End date in "YYYYMMDD" or "YYYY-MM-DD" format.

        Returns:
            DataFrame with columns:
                - date (datetime): Trading date
                - open (float): Opening price
                - high (float): Highest price
                - low (float): Lowest price
                - close (float): Closing price
                - volume (float): Trading volume
                - amount (float): Trading amount / turnover
        """
        ...

    @abstractmethod
    def get_stock_prices(
        self,
        stock_codes: List[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV prices for one or more stocks.

        Args:
            stock_codes: List of stock codes (e.g. ["000001", "600000"]).
            start_date: Start date in "YYYYMMDD" or "YYYY-MM-DD" format.
            end_date: End date in "YYYYMMDD" or "YYYY-MM-DD" format.

        Returns:
            DataFrame with columns:
                - code (str): Stock code
                - date (datetime): Trading date
                - open (float): Opening price
                - high (float): Highest price
                - low (float): Lowest price
                - close (float): Closing price
                - volume (float): Trading volume
                - amount (float): Trading amount / turnover
        """
        ...

    @abstractmethod
    def get_index_stocks(
        self,
        index_code: str,
        date: str,
    ) -> List[str]:
        """Get the list of constituent stocks for an index on a given date.

        Args:
            index_code: Index identifier (e.g. "000300" for CSI 300).
            date: Date in "YYYYMMDD" or "YYYY-MM-DD" format.

        Returns:
            List of stock codes that are members of the index.
        """
        ...

    @abstractmethod
    def get_all_stocks(
        self,
        date: str,
    ) -> List[str]:
        """Get the list of all tradable A-share stocks on a given date.

        Args:
            date: Date in "YYYYMMDD" or "YYYY-MM-DD" format.

        Returns:
            List of all stock codes currently listed.
        """
        ...

    @abstractmethod
    def get_trade_days(
        self,
        start_date: str,
        end_date: str,
    ) -> List[date]:
        """Get the list of trading days in a date range.

        Args:
            start_date: Start date in "YYYYMMDD" or "YYYY-MM-DD" format.
            end_date: End date in "YYYYMMDD" or "YYYY-MM-DD" format.

        Returns:
            Sorted list of Python date objects representing trading days.
        """
        ...

    @abstractmethod
    def get_valuation(
        self,
        stock_codes: List[str],
        date: str,
    ) -> pd.DataFrame:
        """Fetch valuation metrics for stocks on a given date.

        Args:
            stock_codes: List of stock codes.
            date: Date in "YYYYMMDD" or "YYYY-MM-DD" format.

        Returns:
            DataFrame with columns:
                - code (str): Stock code
                - pe_ratio (float): Price-to-earnings ratio (TTM)
                - pb_ratio (float): Price-to-book ratio
                - market_cap (float): Total market capitalization (yuan)
                - circ_market_cap (float): Circulating market cap (yuan)
        """
        ...

    @abstractmethod
    def get_industry_stocks(
        self,
        industry_code: str,
        date: str,
    ) -> List[str]:
        """Get the list of stocks belonging to an industry sector.

        Args:
            industry_code: Industry identifier (name or code).
            date: Date in "YYYYMMDD" or "YYYY-MM-DD" format.

        Returns:
            List of stock codes in the specified industry.
        """
        ...
