"""基本面因子模块。

包含估值因子、质量因子、成长因子、杠杆因子和市值因子。
"""

from typing import List
import numpy as np
import pandas as pd
from datetime import date

from ml_quant_framework.core.registry import FACTOR_REGISTRY
from .base import Factor


# ========== 估值因子 ==========


@FACTOR_REGISTRY.register("EP")
class EPFactor(Factor):
    """盈利收益率 (Earnings/Price = 1/PE)。

    衡量股票盈利能力的估值指标，值越高表示相对越便宜。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(stocks, date, fields=["pe_ratio"])
        return 1 / df["pe_ratio"]


@FACTOR_REGISTRY.register("BP")
class BPFactor(Factor):
    """账面市值比 (Book/Price = 1/PB)。

    衡量股票账面价值相对于市值的比率，价值投资常用指标。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(stocks, date, fields=["pb_ratio"])
        return 1 / df["pb_ratio"]


@FACTOR_REGISTRY.register("SP")
class SPFactor(Factor):
    """销售市值比 (Sales/Price = 1/PS)。

    衡量销售收入相对于市值的比率，适用于评估成长型公司。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(stocks, date, fields=["ps_ratio"])
        return 1 / df["ps_ratio"]


@FACTOR_REGISTRY.register("CFP")
class CFPFactor(Factor):
    """现金流市值比 (CashFlow/Price = 1/PCF)。

    衡量经营现金流相对于市值的比率，反映真实现金流创造能力。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(stocks, date, fields=["pcf_ratio"])
        return 1 / df["pcf_ratio"]


# ========== 质量因子 ==========


@FACTOR_REGISTRY.register("ROE")
class ROEFactor(Factor):
    """净资产收益率 (TTM)。

    衡量公司利用股东权益创造利润的效率，是质量因子的核心指标。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(stocks, date, fields=["roe_ratio"])
        return df["roe_ratio"]


@FACTOR_REGISTRY.register("ROA")
class ROAFactor(Factor):
    """总资产收益率 (TTM)。

    衡量公司利用全部资产创造利润的效率。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(stocks, date, fields=["roa_ratio"])
        return df["roa_ratio"]


@FACTOR_REGISTRY.register("GPM")
class GPMFactor(Factor):
    """销售毛利率。

    衡量公司产品或服务的盈利能力，反映定价权和成本控制能力。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(stocks, date, fields=["gross_profit_margin"])
        return df["gross_profit_margin"]


@FACTOR_REGISTRY.register("NI")
class NIFactor(Factor):
    """净利润率。

    衡量公司最终盈利能力，反映整体经营效率。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(stocks, date, fields=["net_profit_margin"])
        return df["net_profit_margin"]


# ========== 成长因子 ==========


@FACTOR_REGISTRY.register("Revenue_Growth")
class RevenueGrowthFactor(Factor):
    """营业收入增长率。

    衡量公司营业收入的同比增长速度，反映业务扩张能力。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(
            stocks, date, fields=["inc_revenue_year_on_year"]
        )
        return df["inc_revenue_year_on_year"]


@FACTOR_REGISTRY.register("Profit_Growth")
class ProfitGrowthFactor(Factor):
    """净利润增长率。

    衡量公司净利润的同比增长速度，反映盈利能力的提升。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(
            stocks, date, fields=["inc_net_profit_year_on_year"]
        )
        return df["inc_net_profit_year_on_year"]


# ========== 杠杆因子 ==========


@FACTOR_REGISTRY.register("Financial_Leverage")
class FinancialLeverageFactor(Factor):
    """财务杠杆 = 总资产/净资产。

    衡量公司财务风险水平，杠杆越高财务风险越大。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(
            stocks, date, fields=["total_assets", "total_holders_equity"]
        )
        equity = df["total_holders_equity"]
        equity = equity.replace(0, np.nan)
        return df["total_assets"] / equity


@FACTOR_REGISTRY.register("Debt_Equity")
class DebtEquityFactor(Factor):
    """产权比率 = 非流动负债/净资产。

    衡量公司长期偿债能力，反映资本结构稳定性。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(
            stocks, date, fields=["non_current_liability", "total_holders_equity"]
        )
        equity = df["total_holders_equity"]
        equity = equity.replace(0, np.nan)
        return df["non_current_liability"] / equity


@FACTOR_REGISTRY.register("Current_Ratio")
class CurrentRatioFactor(Factor):
    """流动比率 = 流动资产/流动负债。

    衡量公司短期偿债能力，通常大于1表示短期偿债能力良好。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(stocks, date, fields=["current_ratio"])
        return df["current_ratio"]


# ========== 市值因子 ==========


@FACTOR_REGISTRY.register("Market_Cap")
class MarketCapFactor(Factor):
    """总市值 (对数)。

    衡量公司规模的对数市值因子，小市值效应是经典异象之一。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(stocks, date, fields=["market_cap"])
        return np.log(df["market_cap"])


@FACTOR_REGISTRY.register("Circulating_Market_Cap")
class CirculatingMarketCapFactor(Factor):
    """流通市值。

    衡量公司实际可交易部分的价值，影响股票的流动性。
    """

    def __init__(self, name: str = None, params: dict = None):
        super().__init__(name=name, params=params)

    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        df = data_manager.get_fundamentals(
            stocks, date, fields=["circulating_market_cap"]
        )
        return df["circulating_market_cap"]
