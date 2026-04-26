"""动量类因子扩展"""

import pandas as pd
import numpy as np
from .base import FactorCatalog, BaseFactor


@FactorCatalog.register("momentum_regression")
class MomentumRegression(BaseFactor):
    """线性回归斜率动量因子"""

    name = "momentum_regression"
    requires = ["close"]

    def compute(
        self, data: pd.DataFrame, date: str, period: int = 60, **kwargs
    ) -> pd.Series:
        """计算对数收益率的线性回归斜率

        Args:
            data: 包含close列的DataFrame
            date: 当前日期
            period: 回归窗口大小，默认60
            **kwargs: 其他参数

        Returns:
            以code为索引的回归斜率动量因子Series
        """
        df = data.copy()
        if len(df) < period:
            return pd.Series(dtype=float)

        log_close = np.log(df["close"] + 1e-8)
        x = np.arange(len(log_close))

        slope = log_close.rolling(period).apply(
            lambda y: (
                np.polyfit(np.arange(len(y)), y, 1)[0] if len(y) == period else np.nan
            )
        )

        df["momentum_reg"] = slope
        return df.set_index("code")["momentum_reg"].dropna()


@FactorCatalog.register("bias")
class Bias(BaseFactor):
    """偏离度因子（价格相对均线的偏离）"""

    name = "bias"
    requires = ["close"]

    def compute(
        self, data: pd.DataFrame, date: str, period: int = 20, **kwargs
    ) -> pd.Series:
        """计算价格相对均线的偏离度

        Args:
            data: 包含close列的DataFrame
            date: 当前日期
            period: 均线周期，默认20
            **kwargs: 其他参数

        Returns:
            以code为索引的偏离度因子Series
        """
        df = data.copy()
        ma = df["close"].rolling(period).mean()
        df["bias"] = (df["close"] - ma) / (ma + 1e-8)
        return df.set_index("code")["bias"].dropna()


@FactorCatalog.register("max_drawdown")
class MaxDrawdown(BaseFactor):
    """最大回撤因子（过去N日）"""

    name = "max_drawdown"
    requires = ["close"]

    def compute(
        self, data: pd.DataFrame, date: str, period: int = 60, **kwargs
    ) -> pd.Series:
        """计算过去period日的最大回撤

        Args:
            data: 包含close列的DataFrame
            date: 当前日期
            period: 回撤计算窗口，默认60
            **kwargs: 其他参数

        Returns:
            以code为索引的最大回撤因子Series
        """
        df = data.copy()
        rolling_max = df["close"].rolling(period).max()
        df["mdd"] = (df["close"] - rolling_max) / (rolling_max + 1e-8)
        return df.set_index("code")["mdd"].dropna()
