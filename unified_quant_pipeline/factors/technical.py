"""技术因子 - 基于量价数据计算"""

import pandas as pd
import numpy as np
from .base import FactorCatalog, BaseFactor


@FactorCatalog.register("momentum_20")
class Momentum20(BaseFactor):
    """20日动量因子"""

    name = "momentum_20"
    requires = ["close"]

    def compute(
        self, data: pd.DataFrame, date: str, period: int = 20, **kwargs
    ) -> pd.Series:
        """计算20日收益率作为动量

        Args:
            data: 包含close列的DataFrame
            date: 当前日期
            period: 动量计算周期，默认20
            **kwargs: 其他参数

        Returns:
            以code为索引的动量因子Series
        """
        df = data.copy()
        df["momentum"] = df["close"].pct_change(period)
        return df.set_index("code")["momentum"].dropna()


@FactorCatalog.register("momentum_60")
class Momentum60(BaseFactor):
    """60日动量因子"""

    name = "momentum_60"
    requires = ["close"]

    def compute(
        self, data: pd.DataFrame, date: str, period: int = 60, **kwargs
    ) -> pd.Series:
        """计算60日收益率作为动量

        Args:
            data: 包含close列的DataFrame
            date: 当前日期
            period: 动量计算周期，默认60
            **kwargs: 其他参数

        Returns:
            以code为索引的动量因子Series
        """
        df = data.copy()
        df["momentum"] = df["close"].pct_change(period)
        return df.set_index("code")["momentum"].dropna()


@FactorCatalog.register("volatility")
class Volatility(BaseFactor):
    """波动率因子（20日）"""

    name = "volatility"
    requires = ["close"]

    def compute(
        self, data: pd.DataFrame, date: str, period: int = 20, **kwargs
    ) -> pd.Series:
        """计算20日滚动波动率

        Args:
            data: 包含close列的DataFrame
            date: 当前日期
            period: 波动率计算窗口，默认20
            **kwargs: 其他参数

        Returns:
            以code为索引的波动率因子Series
        """
        df = data.copy()
        df["vol"] = df["close"].pct_change().rolling(period).std()
        return df.set_index("code")["vol"].dropna()


@FactorCatalog.register("turnover")
class TurnoverRate(BaseFactor):
    """换手率因子"""

    name = "turnover"
    requires = ["volume", "close"]

    def compute(
        self, data: pd.DataFrame, date: str, period: int = 20, **kwargs
    ) -> pd.Series:
        """计算period日平均换手率

        Args:
            data: 包含volume和close列的DataFrame
            date: 当前日期
            period: 平均窗口，默认20
            **kwargs: 其他参数

        Returns:
            以code为索引的换手率因子Series
        """
        df = data.copy()
        df["turnover"] = df["volume"] / (df["close"] + 1e-8)
        df["turnover_mean"] = df["turnover"].rolling(period).mean()
        return df.set_index("code")["turnover_mean"].dropna()


@FactorCatalog.register("volume_ratio")
class VolumeRatio(BaseFactor):
    """量比因子（5日均量/20日均量）"""

    name = "volume_ratio"
    requires = ["volume"]

    def compute(self, data: pd.DataFrame, date: str, **kwargs) -> pd.Series:
        """计算量比因子

        Args:
            data: 包含volume列的DataFrame
            date: 当前日期
            **kwargs: 其他参数

        Returns:
            以code为索引的量比因子Series
        """
        df = data.copy()
        vol_5 = df["volume"].rolling(5).mean()
        vol_20 = df["volume"].rolling(20).mean()
        df["volume_ratio"] = vol_5 / (vol_20 + 1e-8)
        return df.set_index("code")["volume_ratio"].dropna()


@FactorCatalog.register("rsrs")
class RSRSScore(BaseFactor):
    """RSRS因子（阻力支撑相对强度）"""

    name = "rsrs"
    requires = ["high", "low"]

    def compute(
        self, data: pd.DataFrame, date: str, window: int = 18, **kwargs
    ) -> pd.Series:
        """计算RSRS因子

        Args:
            data: 包含high和low列的DataFrame
            date: 当前日期
            window: 回归窗口大小，默认18
            **kwargs: 其他参数

        Returns:
            以code为索引的RSRS因子Series
        """
        df = data.copy()
        slopes = []
        r2s = []

        for i in range(window, len(df)):
            low_window = df["low"].iloc[i - window : i].values
            high_window = df["high"].iloc[i - window : i].values

            if len(low_window) > 1 and np.std(low_window) > 0:
                slope, intercept = np.polyfit(low_window, high_window, 1)
                r2 = np.corrcoef(low_window, high_window)[0, 1] ** 2
            else:
                slope, r2 = 0, 0

            slopes.append(slope)
            r2s.append(r2)

        df = df.iloc[window:].copy()
        df["slope"] = slopes
        df["r2"] = r2s

        slope_mean = df["slope"].rolling(20).mean()
        slope_std = df["slope"].rolling(20).std()
        df["rsrs"] = (df["slope"] - slope_mean) / (slope_std + 1e-8) * df["r2"]

        return df.set_index("code")["rsrs"].dropna()
