"""技术因子模块。

包含基于价格和成交量计算的技术指标因子。
"""

from typing import List
import numpy as np
import pandas as pd
from datetime import date

from ml_quant_framework.core.registry import FACTOR_REGISTRY
from .base import Factor


@FACTOR_REGISTRY.register("RSI")
class RSIFactor(Factor):
    """相对强弱指标 (Relative Strength Index)。

    衡量价格变动速度和幅度的动量振荡器，用于判断超买超卖状态。
    """

    def __init__(self, period: int = 20, name: str = None, params: dict = None):
        default_params = {"period": period}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.period = period

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        from jqlib.technical_analysis import RSI

        result = RSI(stocks, date, N1=self.period)
        return pd.Series(result)


@FACTOR_REGISTRY.register("MACD_DIF")
class MACDDIFFactor(Factor):
    """MACD DIF线 (快线)。

    DIF = EMA(CLOSE, SHORT) - EMA(CLOSE, LONG)，反映短期与长期趋势的差值。
    """

    def __init__(
        self, short: int = 12, long: int = 26, name: str = None, params: dict = None
    ):
        default_params = {"short": short, "long": long}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.short = short
        self.long = long

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        from jqlib.technical_analysis import MACD

        dif, dea, macd = MACD(stocks, date, SHORT=self.short, LONG=self.long)
        return pd.Series(dif)


@FACTOR_REGISTRY.register("MACD_DEA")
class MACDDEAFactor(Factor):
    """MACD DEA线 (慢线/信号线)。

    DEA = EMA(DIF, MID)，是DIF的移动平均线，用于产生交易信号。
    """

    def __init__(
        self,
        short: int = 12,
        long: int = 26,
        mid: int = 9,
        name: str = None,
        params: dict = None,
    ):
        default_params = {"short": short, "long": long, "mid": mid}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.short = short
        self.long = long
        self.mid = mid

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        from jqlib.technical_analysis import MACD

        dif, dea, macd = MACD(
            stocks, date, SHORT=self.short, LONG=self.long, MID=self.mid
        )
        return pd.Series(dea)


@FACTOR_REGISTRY.register("MACD")
class MACDFactor(Factor):
    """MACD柱 (MACD Histogram)。

    MACD柱 = 2 * (DIF - DEA)，反映DIF与DEA的偏离程度。
    """

    def __init__(
        self,
        short: int = 12,
        long: int = 26,
        mid: int = 9,
        name: str = None,
        params: dict = None,
    ):
        default_params = {"short": short, "long": long, "mid": mid}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.short = short
        self.long = long
        self.mid = mid

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        from jqlib.technical_analysis import MACD

        dif, dea, macd = MACD(
            stocks, date, SHORT=self.short, LONG=self.long, MID=self.mid
        )
        return pd.Series(macd)


@FACTOR_REGISTRY.register("BIAS")
class BIASFactor(Factor):
    """乖离率 (Bias Ratio)。

    衡量股价偏离移动平均线的程度，用于判断超买超卖。
    BIAS = (CLOSE - MA) / MA * 100
    """

    def __init__(self, period: int = 20, name: str = None, params: dict = None):
        default_params = {"period": period}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.period = period

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        from jqlib.technical_analysis import BIAS

        result = BIAS(stocks, date, N1=self.period)
        return pd.Series(result)


@FACTOR_REGISTRY.register("ATR")
class ATRFactor(Factor):
    """平均真实波动范围 (Average True Range)。

    衡量价格波动性的指标，常用于止损和仓位管理。
    """

    def __init__(self, period: int = 14, name: str = None, params: dict = None):
        default_params = {"period": period}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.period = period

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        from jqlib.technical_analysis import ATR

        result = ATR(stocks, date, N1=self.period)
        return pd.Series(result)


@FACTOR_REGISTRY.register("VOL_Ratio")
class VOLRatioFactor(Factor):
    """量比 = 5日均量 / 20日均量。

    衡量当前成交量相对于历史平均成交量的放大程度，反映市场活跃度。
    """

    def __init__(
        self, short: int = 5, long: int = 20, name: str = None, params: dict = None
    ):
        default_params = {"short": short, "long": long}
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.short = short
        self.long = long

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_price(
            stocks,
            end_date=date,
            count=max(self.short, self.long) + 20,
            fields=["volume"],
        )
        volumes = df["volume"].unstack(level=1)
        short_ma = volumes.tail(self.short).mean()
        long_ma = volumes.tail(self.long).mean()
        long_ma = long_ma.replace(0, np.nan)
        return short_ma / long_ma


@FACTOR_REGISTRY.register("Turnover")
class TurnoverFactor(Factor):
    """换手率 (Turnover Rate)。

    衡量股票流通股份的换手频率，反映市场交易活跃度和流动性。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(stocks, date, fields=["turnover_ratio"])
        return df["turnover_ratio"]
