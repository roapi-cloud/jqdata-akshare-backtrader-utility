# -*- coding: utf-8 -*-
"""
市场宽度模型 (Market Breadth)

通过涨跌家数、创新高/新低家数等广度指标判断市场健康程度。

包含:
    1. MarketBreadthModel: 市场宽度 (涨跌家数比 + 创新高比例)
    2. DiffusionIndexModel: 扩散指数 (ROC > 0 的股票占比)
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import diffusion_index, sma


class MarketBreadthModel(BaseTimingModel):
    """
    市场宽度模型

    参数:
        ma_fast: 快速均线周期 (默认 10)
        ma_slow: 慢速均线周期 (默认 30)
        extreme_high: 极端高位阈值 (默认 0.8)
        extreme_low: 极端低位阈值 (默认 0.2)
    """

    def __init__(
        self,
        ma_fast: int = 10,
        ma_slow: int = 30,
        extreme_high: float = 0.8,
        extreme_low: float = 0.2,
    ):
        super().__init__(name="Market-Breadth", scope=TimingScope.MARKET)
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow
        self.extreme_high = extreme_high
        self.extreme_low = extreme_low

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        """
        Args:
            data: 必须包含 'up_count', 'down_count'
                  可选: 'new_high', 'new_low'
        """
        self._validate_data(data, ["up_count", "down_count"])

        ma_fast = kwargs.get("ma_fast", self.ma_fast)
        ma_slow = kwargs.get("ma_slow", self.ma_slow)

        total = data["up_count"] + data["down_count"]
        breadth_ratio = data["up_count"] / total.replace(0, np.nan)

        fast_ma = sma(breadth_ratio, ma_fast)
        slow_ma = sma(fast_ma, ma_slow)

        latest_breadth = breadth_ratio.iloc[-1]
        latest_fast = fast_ma.iloc[-1]
        latest_slow = slow_ma.iloc[-1]

        direction = self._evaluate(latest_fast, latest_slow, latest_breadth)
        strength = np.clip((latest_breadth - 0.5) * 2, -1.0, 1.0)
        confidence = min(abs(strength), 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=latest_breadth,
            timestamp=data.index[-1],
            metadata={
                "breadth_ratio": latest_breadth,
                "fast_ma": latest_fast,
                "slow_ma": latest_slow,
                "ma_cross": "golden" if latest_fast > latest_slow else "death",
            },
        )

    def _evaluate(
        self, fast_ma: float, slow_ma: float, breadth: float
    ) -> SignalDirection:
        if fast_ma > slow_ma and breadth > 0.5:
            return SignalDirection.BUY
        elif fast_ma < slow_ma and breadth < 0.5:
            return SignalDirection.SELL
        else:
            return SignalDirection.HOLD

    def get_params(self) -> Dict[str, Any]:
        return {
            "ma_fast": self.ma_fast,
            "ma_slow": self.ma_slow,
            "extreme_high": self.extreme_high,
            "extreme_low": self.extreme_low,
        }


class DiffusionIndexModel(BaseTimingModel):
    """
    扩散指数模型

    计算 ROC > 0 的股票占比 (可加权)，用双均线判断趋势。

    参数:
        roc_period: ROC 计算周期 (默认 100)
        ma_fast: 快速均线 (默认 90)
        ma_slow: 慢速均线 (默认 30, 对 fast_ma 再做均线)
    """

    def __init__(self, roc_period: int = 100, ma_fast: int = 90, ma_slow: int = 30):
        super().__init__(name="Diffusion-Index", scope=TimingScope.MARKET)
        self.roc_period = roc_period
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        """
        Args:
            data: 多股票收盘价 DataFrame (columns=stocks, index=dates)
                  可选: 'weights' 列指定权重
        """
        roc_period = kwargs.get("roc_period", self.roc_period)
        ma_fast = kwargs.get("ma_fast", self.ma_fast)
        ma_slow = kwargs.get("ma_slow", self.ma_slow)

        returns = data.pct_change(roc_period)
        di = diffusion_index(returns)

        fast_ma = sma(di, ma_fast)
        slow_ma = sma(fast_ma, ma_slow)

        latest_di = di.iloc[-1]
        latest_fast = fast_ma.iloc[-1]
        latest_slow = slow_ma.iloc[-1]

        if latest_fast > latest_slow:
            direction = SignalDirection.BUY
        else:
            direction = SignalDirection.SELL

        strength = np.clip((latest_di - 0.5) * 2, -1.0, 1.0)
        confidence = min(abs(latest_fast - latest_slow) * 5, 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=latest_di,
            timestamp=data.index[-1],
            metadata={
                "diffusion_index": latest_di,
                "fast_ma": latest_fast,
                "slow_ma": latest_slow,
            },
        )

    def get_params(self) -> Dict[str, Any]:
        return {
            "roc_period": self.roc_period,
            "ma_fast": self.ma_fast,
            "ma_slow": self.ma_slow,
        }
