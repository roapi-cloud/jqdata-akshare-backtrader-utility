"""
Indicator Factory

可拼装信号工厂，支持像积木一样组合单指标/单信号模块。

Usage:
    # 单信号使用
    from strategy_kits.signals.indicator_factory import SignalRegistry

    signal = SignalRegistry.create("macd", {"fastperiod": 12})
    result = signal.compute(price_df=close_df)
    signal_df = result["signal_df"]

    # 批量信号计算
    from strategy_kits.signals.indicator_factory import SignalFactory

    factory = SignalFactory()
    factory.add_signal("macd", {})
    factory.add_signal("alligator", {"periods": (13, 8, 5)})
    results = factory.compute_all(price_df=close_df)

    # 信号组合
    from strategy_kits.signals.indicator_factory import SignalComposer

    combined = SignalComposer.equal_weight(signals_df)
"""

from .base import BaseSignal, BinarySignal, ContinuousSignal, DiscreteSignal
from .factory import SignalComposer, SignalFactory
from .registry import SignalRegistry, register_signal
from .utils import (
    alignment_signal,
    calc_beta,
    calc_corrcoef,
    calc_zscore,
    ffill_fillna,
    sliding_window,
    trigger_signal,
)

__all__ = [
    # 基础类
    "BaseSignal",
    "DiscreteSignal",
    "ContinuousSignal",
    "BinarySignal",
    # 注册
    "SignalRegistry",
    "register_signal",
    # 工厂
    "SignalFactory",
    "SignalComposer",
    # 工具
    "sliding_window",
    "alignment_signal",
    "trigger_signal",
    "calc_zscore",
    "calc_beta",
    "calc_corrcoef",
    "ffill_fillna",
]

__version__ = "0.1.0"
