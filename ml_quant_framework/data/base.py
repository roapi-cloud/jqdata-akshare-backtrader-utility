from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, List, Optional

import pandas as pd


class DataSource(ABC):
    """数据源抽象基类。

    定义统一的数据访问接口，所有具体数据源适配器需继承此类并实现
    相应的抽象方法。支持行情数据、基本面数据、因子数据、行业分类
    等多种数据类型的获取。
    """

    @abstractmethod
    def get_stock_list(self, index: str, date: date) -> List[str]:
        """获取指数成分股列表。

        Args:
            index: 指数代码，如 "000300.XSHG" (沪深300)。
            date: 查询日期。

        Returns:
            股票代码列表。
        """
        ...

    @abstractmethod
    def get_price(
        self,
        stocks: List[str],
        start_date: date,
        end_date: date,
        fields: Optional[List[str]] = None,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """获取行情数据。

        Args:
            stocks: 股票代码列表。
            start_date: 起始日期。
            end_date: 结束日期。
            fields: 需要获取的字段列表，如 ["close", "volume", "open", "high", "low"]。
            frequency: 数据频率，支持 "1d", "1m", "5m", "15m", "30m", "60m"。

        Returns:
            行情数据 DataFrame，包含 MultiIndex (code, date) 或列中包含 code 和 date。
        """
        ...

    @abstractmethod
    def get_fundamentals(
        self,
        stocks: List[str],
        date: date,
        fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """获取财务基本面数据。

        Args:
            stocks: 股票代码列表。
            date: 查询日期。
            fields: 需要获取的字段列表，如 ["pe_ratio", "pb_ratio", "market_cap"]。

        Returns:
            基本面数据 DataFrame，索引为股票代码。
        """
        ...

    @abstractmethod
    def get_factor_values(
        self,
        stocks: List[str],
        factors: List[str],
        date: date,
    ) -> pd.DataFrame:
        """获取因子值。

        Args:
            stocks: 股票代码列表。
            factors: 因子名称列表，如 ["EP", "BP", "ROE"]。
            date: 查询日期。

        Returns:
            因子值 DataFrame，索引为股票代码，列为因子名称。
        """
        ...

    @abstractmethod
    def get_industry(
        self,
        stocks: List[str],
        date: date,
        classification: str = "sw_l1",
    ) -> Dict[str, str]:
        """获取行业分类。

        Args:
            stocks: 股票代码列表。
            date: 查询日期。
            classification: 行业分类标准，支持 "sw_l1", "sw_l2", "zjw"。

        Returns:
            股票到行业代码的映射字典。
        """
        ...

    @abstractmethod
    def get_extras(
        self,
        field: str,
        stocks: List[str],
        date: date,
    ) -> Dict[str, bool]:
        """获取额外信息 (如ST标识、停牌标识等)。

        Args:
            field: 字段名称，如 "is_st", "is_suspended"。
            stocks: 股票代码列表。
            date: 查询日期。

        Returns:
            股票到额外信息的映射字典。
        """
        ...

    @abstractmethod
    def get_trade_days(
        self,
        start_date: date,
        end_date: date,
        frequency: str = "1d",
    ) -> List[date]:
        """获取交易日历。

        Args:
            start_date: 起始日期。
            end_date: 结束日期。
            frequency: 频率，支持 "1d", "weekly", "monthly"。

        Returns:
            交易日列表。
        """
        ...

    @abstractmethod
    def get_security_info(self, stock: str) -> dict:
        """获取证券信息 (上市日期、退市日期、名称等)。

        Args:
            stock: 股票代码。

        Returns:
            证券信息字典。
        """
        ...
