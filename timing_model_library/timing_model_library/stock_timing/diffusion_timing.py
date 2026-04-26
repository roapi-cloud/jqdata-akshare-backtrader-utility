# -*- coding: utf-8 -*-
"""
个股扩散指数择时模型

用于微盘股/小市值股票的择时。

核心逻辑:
    - 计算股票池内 ROC > 0 的股票占比
    - 用 EMA 交叉判断趋势
    - 扩散指数极低 → 超卖 → 买入
    - 扩散指数极高 → 超买 → 卖出
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import ema, diffusion_index


class StockDiffusionTimingModel(BaseTimingModel):
    """
    个股扩散指数择时模型

    参数:
        roc_period: ROC 周期 (默认 20)
        ema_fast: 快速 EMA (默认 6)
        ema_slow: 慢速 EMA (默认 28)
    """

    def __init__(self, roc_period: int = 20, ema_fast: int = 6, ema_slow: int = 28):
        super().__init__(name="Stock-Diffusion", scope=TimingScope.STOCK)
        self.roc_period = roc_period
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        """
        Args:
            data: 多股票收盘价 DataFrame (columns=stocks, index=dates)
        """
        roc_period = kwargs.get("roc_period", self.roc_period)
        ema_fast = kwargs.get("ema_fast", self.ema_fast)
        ema_slow = kwargs.get("ema_slow", self.ema_slow)

        returns = data.pct_change(roc_period)
        di = diffusion_index(returns)

        ema_fast_series = ema(di, ema_fast)
        ema_slow_series = ema(di, ema_slow)

        latest_di = di.iloc[-1]
        latest_ema_fast = ema_fast_series.iloc[-1]
        latest_ema_slow = ema_slow_series.iloc[-1]

        if latest_ema_fast > latest_ema_slow:
            direction = SignalDirection.BUY
        else:
            direction = SignalDirection.SELL

        strength = np.clip((latest_di - 0.5) * 2, -1.0, 1.0)
        confidence = min(abs(latest_ema_fast - latest_ema_slow) * 5, 1.0)

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
                "ema_fast": latest_ema_fast,
                "ema_slow": latest_ema_slow,
                "cross": "golden" if latest_ema_fast > latest_ema_slow else "death",
            },
        )

    def get_params(self) -> Dict[str, Any]:
        return {
            "roc_period": self.roc_period,
            "ema_fast": self.ema_fast,
            "ema_slow": self.ema_slow,
        }
