from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from ml_quant_framework.core.config import DataConfig

from .akshare import AkShareDataSource
from .base import DataSource
from .cache import DataCache
from .jqdata import JQDataSource


class DataManager:
    """数据管理器 - 统一数据访问门面。

    封装数据源和缓存层，提供统一的数据访问接口。
    支持多种数据源 (JQData, AkShare) 的注册和切换，
    并自动处理数据缓存以减少重复 API 调用。
    """

    _sources: Dict[str, type] = {
        "jqdata": JQDataSource,
        "akshare": AkShareDataSource,
    }

    @classmethod
    def register(cls, name: str, source_class: type) -> None:
        """注册新的数据源。

        Args:
            name: 数据源名称标识。
            source_class: 数据源类，需继承 DataSource。
        """
        cls._sources[name] = source_class

    def __init__(self, config: DataConfig, use_cache: bool = True):
        """初始化数据管理器。

        Args:
            config: 数据配置对象，包含数据源类型等。
            use_cache: 是否启用缓存。
        """
        self.config = config
        source_class = self._sources.get(config.source)
        if source_class is None:
            raise ValueError(
                f"Unknown data source: {config.source}. Available: {list(self._sources.keys())}"
            )
        self.source: DataSource = source_class(config)
        self.cache = DataCache() if use_cache else None

    def _with_cache(self, method_name: str, **kwargs: Any) -> Any:
        """带缓存的方法调用。

        先尝试从缓存获取数据，如果缓存不存在或已过期，
        则调用数据源方法获取数据并保存到缓存。

        Args:
            method_name: 数据源方法名。
            **kwargs: 方法参数。

        Returns:
            方法返回结果。
        """
        if self.cache:
            result = self.cache.get(method_name, **kwargs)
            if result is not None:
                return result

        result = getattr(self.source, method_name)(**kwargs)

        if self.cache:
            self.cache.put(method_name, result, **kwargs)

        return result

    def get_stock_list(self, index: str, date: date) -> List[str]:
        """获取指数成分股列表。

        Args:
            index: 指数代码。
            date: 查询日期。

        Returns:
            成分股代码列表。
        """
        return self._with_cache("get_stock_list", index=index, date=date)

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
            fields: 需要获取的字段列表。
            frequency: 数据频率。

        Returns:
            行情数据 DataFrame。
        """
        return self._with_cache(
            "get_price",
            stocks=stocks,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            frequency=frequency,
        )

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
            fields: 需要获取的字段列表。

        Returns:
            基本面数据 DataFrame。
        """
        return self._with_cache(
            "get_fundamentals", stocks=stocks, date=date, fields=fields
        )

    def get_factor_values(
        self,
        stocks: List[str],
        factors: List[str],
        date: date,
    ) -> pd.DataFrame:
        """获取因子值。

        Args:
            stocks: 股票代码列表。
            factors: 因子名称列表。
            date: 查询日期。

        Returns:
            因子值 DataFrame。
        """
        return self._with_cache(
            "get_factor_values", stocks=stocks, factors=factors, date=date
        )

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
            classification: 行业分类标准。

        Returns:
            股票到行业代码的映射字典。
        """
        return self._with_cache(
            "get_industry", stocks=stocks, date=date, classification=classification
        )

    def get_extras(
        self,
        field: str,
        stocks: List[str],
        date: date,
    ) -> Dict[str, bool]:
        """获取额外信息。

        Args:
            field: 字段名称。
            stocks: 股票代码列表。
            date: 查询日期。

        Returns:
            股票到额外信息的映射字典。
        """
        return self._with_cache("get_extras", field=field, stocks=stocks, date=date)

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
            frequency: 频率。

        Returns:
            交易日列表。
        """
        return self._with_cache(
            "get_trade_days",
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
        )

    def get_security_info(self, stock: str) -> dict:
        """获取证券信息。

        Args:
            stock: 股票代码。

        Returns:
            证券信息字典。
        """
        return self._with_cache("get_security_info", stock=stock)

    def clear_cache(self) -> None:
        """清空数据缓存。"""
        if self.cache:
            self.cache.clear()

    def invalidate_cache(self, method_name: str, **kwargs: Any) -> None:
        """使特定缓存失效。

        Args:
            method_name: 方法名。
            **kwargs: 方法参数。
        """
        if self.cache:
            self.cache.invalidate(method_name, **kwargs)
