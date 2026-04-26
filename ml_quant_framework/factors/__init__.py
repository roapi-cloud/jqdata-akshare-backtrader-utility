"""因子计算模块。

导出所有因子类、基类和辅助工具函数。
"""

from .base import Factor
from .fundamental import (
    EPFactor,
    BPFactor,
    SPFactor,
    CFPFactor,
    ROEFactor,
    ROAFactor,
    GPMFactor,
    NIFactor,
    RevenueGrowthFactor,
    ProfitGrowthFactor,
    FinancialLeverageFactor,
    DebtEquityFactor,
    CurrentRatioFactor,
    MarketCapFactor,
    CirculatingMarketCapFactor,
)
from .technical import (
    RSIFactor,
    MACDDIFFactor,
    MACDDEAFactor,
    MACDFactor,
    BIASFactor,
    ATRFactor,
    VOLRatioFactor,
    TurnoverFactor,
)
from .custom import (
    SkewnessFactor,
    VolatilityFactor,
    MomentumFactor,
    MARatioFactor,
    PricePositionFactor,
    VolumeChangeFactor,
)
from .registry_helpers import get_factor, compute_factors, list_available_factors

__all__ = [
    "Factor",
    "EPFactor",
    "BPFactor",
    "SPFactor",
    "CFPFactor",
    "ROEFactor",
    "ROAFactor",
    "GPMFactor",
    "NIFactor",
    "RevenueGrowthFactor",
    "ProfitGrowthFactor",
    "FinancialLeverageFactor",
    "DebtEquityFactor",
    "CurrentRatioFactor",
    "MarketCapFactor",
    "CirculatingMarketCapFactor",
    "RSIFactor",
    "MACDDIFFactor",
    "MACDDEAFactor",
    "MACDFactor",
    "BIASFactor",
    "ATRFactor",
    "VOLRatioFactor",
    "TurnoverFactor",
    "SkewnessFactor",
    "VolatilityFactor",
    "MomentumFactor",
    "MARatioFactor",
    "PricePositionFactor",
    "VolumeChangeFactor",
    "get_factor",
    "compute_factors",
    "list_available_factors",
]
