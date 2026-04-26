"""数据源抽象基类"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
import pandas as pd


class BaseDataSource(ABC):
    """数据源抽象基类

    所有数据源必须实现以下接口。
    支持AKShare、JQData等多种数据源。
    """

    name: str = "base"

    @abstractmethod
    def get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日历

        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            List[str]: 交易日期列表
        """
        pass

    @abstractmethod
    def get_index_components(
        self, index_code: str, date: Optional[str] = None
    ) -> List[str]:
        """获取指数成分股

        Args:
            index_code: 指数代码，如 000300
            date: 日期，None表示最新

        Returns:
            List[str]: 股票代码列表
        """
        pass

    @abstractmethod
    def get_stock_data(
        self, stocks: List[str], dates: List[str], fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """获取股票数据

        Args:
            stocks: 股票代码列表
            dates: 日期列表
            fields: 字段列表，None表示默认字段

        Returns:
            DataFrame: 包含date, code, open, high, low, close, volume等
        """
        pass

    @abstractmethod
    def get_fundamentals(
        self, stocks: List[str], date: str, fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """获取基本面数据

        Args:
            stocks: 股票代码列表
            date: 财报日期
            fields: 字段列表

        Returns:
            DataFrame: 基本面数据
        """
        pass

    def get_price(
        self,
        code: str,
        start_date: str,
        end_date: str,
        frequency: str = "daily",
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取单个股票价格数据（默认实现）

        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            frequency: 数据频率
            adjust: 复权类型

        Returns:
            DataFrame: 价格数据
        """
        return self.get_stock_data([code], self.get_trade_dates(start_date, end_date))
