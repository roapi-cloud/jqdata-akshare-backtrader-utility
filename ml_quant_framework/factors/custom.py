"""自定义/衍生因子模块。

包含基于历史价格数据计算的统计特征因子。
"""

from typing import List
import numpy as np
import pandas as pd
from datetime import date

from ml_quant_framework.core.registry import FACTOR_REGISTRY
from .base import Factor


@FACTOR_REGISTRY.register("Skewness")
class SkewnessFactor(Factor):
    """收益率偏度 (Skewness)。

    衡量收益率分布的不对称性。正偏度表示极端正收益更多，负偏度表示极端负收益更多。
    """

    def __init__(self, window: int = 20, name: str = None, params: dict = None):
        default_params = {"window": window}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.window = window

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_price(stocks, end_date=date, count=self.window + 1, fields=["close"])
        closes = df["close"].unstack(level=1)
        returns = closes.pct_change().dropna()
        return returns.tail(self.window).skew()


@FACTOR_REGISTRY.register("Volatility")
class VolatilityFactor(Factor):
    """历史波动率 (Historical Volatility)。

    衡量收益率的标准差，反映价格波动的剧烈程度。
    """

    def __init__(self, window: int = 20, name: str = None, params: dict = None):
        default_params = {"window": window}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.window = window

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_price(stocks, end_date=date, count=self.window + 1, fields=["close"])
        closes = df["close"].unstack(level=1)
        returns = closes.pct_change().dropna()
        return returns.tail(self.window).std()


@FACTOR_REGISTRY.register("Momentum")
class MomentumFactor(Factor):
    """动量因子 (Momentum)。

    衡量N日收益率，基于动量效应，过去表现好的股票未来可能继续表现好。
    """

    def __init__(self, window: int = 20, name: str = None, params: dict = None):
        default_params = {"window": window}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.window = window

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_price(stocks, end_date=date, count=self.window + 1, fields=["close"])
        closes = df["close"].unstack(level=1)
        return closes.iloc[-1] / closes.iloc[0] - 1


@FACTOR_REGISTRY.register("MA_Ratio")
class MARatioFactor(Factor):
    """均线比值因子 (MA Ratio)。

    短期均线与长期均值的比值，反映趋势强度。大于1表示短期趋势强于长期趋势。
    """

    def __init__(self, short: int = 5, long: int = 20, name: str = None, params: dict = None):
        default_params = {"short": short, "long": long}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.short = short
        self.long = long

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        count = max(self.short, self.long) + 10
        df = data_manager.get_price(stocks, end_date=date, count=count, fields=["close"])
        closes = df["close"].unstack(level=1)
        short_ma = closes.tail(self.short).mean()
        long_ma = closes.tail(self.long).mean()
        long_ma = long_ma.replace(0, np.nan)
        return short_ma / long_ma


@FACTOR_REGISTRY.register("Price_Position")
class PricePositionFactor(Factor):
    """价格位置因子 (Price Position)。

    当前价格在N日高低区间中的相对位置。值越接近1表示价格越接近区间高点。
    Price_Position = (当前价 - N日低) / (N日高 - N日低)
    """

    def __init__(self, window: int = 20, name: str = None, params: dict = None):
        default_params = {"window": window}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.window = window

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_price(stocks, end_date=date, count=self.window, fields=["close"])
        closes = df["close"].unstack(level=1)
        current = closes.iloc[-1]
        high = closes.tail(self.window).max()
        low = closes.tail(self.window).min()
        range_val = high - low
        range_val = range_val.replace(0, np.nan)
        return (current - low) / range_val


@FACTOR_REGISTRY.register("Volume_Change")
class VolumeChangeFactor(Factor):
    """成交量变化率因子 (Volume Change)。

    衡量近期成交量相对于历史平均成交量的变化程度，反映市场关注度的变化。
    Volume_Change = 近N日均量 / 远M日均量 - 1
    """

    def __init__(self, short: int = 5, long: int = 20, name: str = None, params: dict = None):
        default_params = {"short": short, "long": long}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.short = short
        self.long = long

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        count = self.short + self.long + 10
        df = data_manager.get_price(stocks, end_date=date, count=count, fields=["volume"])
        volumes = df["volume"].unstack(level=1)
        short_vol = volumes.tail(self.short).mean()
        long_vol = volumes.tail(self.long).mean()
        long_vol = long_vol.replace(0, np.nan)
        return short_vol / long_vol - 1
