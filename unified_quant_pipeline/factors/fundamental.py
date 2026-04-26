"""基本面因子 - 基于财务数据计算"""

import pandas as pd
import numpy as np
from .base import FactorCatalog, BaseFactor


@FactorCatalog.register("pe")
class PE(BaseFactor):
    """市盈率因子（倒数，值越大越便宜）"""

    name = "pe"
    requires = ["pe_ratio"]

    def compute(self, data: pd.DataFrame, date: str, **kwargs) -> pd.Series:
        """计算市盈率倒数因子

        Args:
            data: 包含pe_ratio列的DataFrame
            date: 当前日期
            **kwargs: 其他参数

        Returns:
            以code为索引的PE因子Series
        """
        df = data.copy()
        if "pe_ratio" not in df.columns:
            return pd.Series(dtype=float)
        df["value"] = 1 / (df["pe_ratio"] + 1e-8)
        return df.set_index("code")["value"].dropna()


@FactorCatalog.register("pb")
class PB(BaseFactor):
    """市净率因子（倒数）"""

    name = "pb"
    requires = ["pb_ratio"]

    def compute(self, data: pd.DataFrame, date: str, **kwargs) -> pd.Series:
        """计算市净率倒数因子

        Args:
            data: 包含pb_ratio列的DataFrame
            date: 当前日期
            **kwargs: 其他参数

        Returns:
            以code为索引的PB因子Series
        """
        df = data.copy()
        if "pb_ratio" not in df.columns:
            return pd.Series(dtype=float)
        df["value"] = 1 / (df["pb_ratio"] + 1e-8)
        return df.set_index("code")["value"].dropna()


@FactorCatalog.register("roe")
class ROE(BaseFactor):
    """ROE因子"""

    name = "roe"
    requires = ["roe"]

    def compute(self, data: pd.DataFrame, date: str, **kwargs) -> pd.Series:
        """获取ROE因子值

        Args:
            data: 包含roe列的DataFrame
            date: 当前日期
            **kwargs: 其他参数

        Returns:
            以code为索引的ROE因子Series
        """
        df = data.copy()
        if "roe" not in df.columns:
            return pd.Series(dtype=float)
        return df.set_index("code")["roe"].dropna()


@FactorCatalog.register("dividend_yield")
class DividendYield(BaseFactor):
    """股息率因子"""

    name = "dividend_yield"
    requires = ["dividend_yield"]

    def compute(self, data: pd.DataFrame, date: str, **kwargs) -> pd.Series:
        """获取股息率因子值

        Args:
            data: 包含dividend_yield列的DataFrame
            date: 当前日期
            **kwargs: 其他参数

        Returns:
            以code为索引的股息率因子Series
        """
        df = data.copy()
        if "dividend_yield" not in df.columns:
            return pd.Series(dtype=float)
        return df.set_index("code")["dividend_yield"].dropna()


@FactorCatalog.register("revenue_growth")
class RevenueGrowth(BaseFactor):
    """营收增速因子"""

    name = "revenue_growth"
    requires = ["revenue_growth"]

    def compute(self, data: pd.DataFrame, date: str, **kwargs) -> pd.Series:
        """获取营收增速因子值

        Args:
            data: 包含revenue_growth列的DataFrame
            date: 当前日期
            **kwargs: 其他参数

        Returns:
            以code为索引的营收增速因子Series
        """
        df = data.copy()
        if "revenue_growth" not in df.columns:
            return pd.Series(dtype=float)
        return df.set_index("code")["revenue_growth"].dropna()


@FactorCatalog.register("profit_growth")
class ProfitGrowth(BaseFactor):
    """利润增速因子"""

    name = "profit_growth"
    requires = ["profit_growth"]

    def compute(self, data: pd.DataFrame, date: str, **kwargs) -> pd.Series:
        """获取利润增速因子值

        Args:
            data: 包含profit_growth列的DataFrame
            date: 当前日期
            **kwargs: 其他参数

        Returns:
            以code为索引的利润增速因子Series
        """
        df = data.copy()
        if "profit_growth" not in df.columns:
            return pd.Series(dtype=float)
        return df.set_index("code")["profit_growth"].dropna()
