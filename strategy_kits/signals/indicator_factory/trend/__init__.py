"""
Trend Following Signals

趋势跟踪类信号：鳄鱼线、AO动量、MACD、ICU均线等
"""

from .alligator import AlligatorSignal, calculate_alligator_indicator
from .macd import MACDSignal
from .quality_momentum import QualityMomentumSignal, calculate_quality_momentum

__all__ = [
    "MACDSignal",
    "AlligatorSignal",
    "calculate_alligator_indicator",
    "QualityMomentumSignal",
    "calculate_quality_momentum",
    # "AOMomentumSignal",
    # "ICUMASignal",
]
