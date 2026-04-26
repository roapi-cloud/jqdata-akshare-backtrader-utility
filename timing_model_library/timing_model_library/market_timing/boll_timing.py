# -*- coding: utf-8 -*-
"""
布林带择时模型

用布林带判断大盘超买超卖状态。

核心逻辑:
    - 价格触及上轨 → 超买 → 卖出
    - 价格触及下轨 → 超卖 → 买入
    - 布林带收窄 → 即将变盘 → 关注
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import boll


class BOLLTimingModel(BaseTimingModel):
    """
    布林带择时模型

    参数:
        period: 布林带周期 (默认 20)
        std_dev: 标准差倍数 (默认 2.0)
        overbought_threshold: 超买位置阈值 (默认 0.9)
        oversold_threshold: 超卖位置阈值 (默认 0.1)
    """

    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        overbought_threshold: float = 0.9,
        oversold_threshold: float = 0.1,
    ):
        super().__init__(name="BOLL-Timing", scope=TimingScope.MARKET)
        self.period = period
        self.std_dev = std_dev
        self.overbought_threshold = overbought_threshold
        self.oversold_threshold = oversold_threshold

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        self._validate_data(data, ["close"])

        period = kwargs.get("period", self.period)
        std_dev = kwargs.get("std_dev", self.std_dev)

        upper, mid, lower = boll(data["close"], period, std_dev)

        close = data["close"].iloc[-1]
        latest_upper = upper.iloc[-1]
        latest_mid = mid.iloc[-1]
        latest_lower = lower.iloc[-1]

        position = (
            (close - latest_lower) / (latest_upper - latest_lower)
            if latest_upper != latest_lower
            else 0.5
        )

        direction = self._evaluate(position)
        strength = np.clip((0.5 - position) * 2, -1.0, 1.0)
        confidence = min(abs(strength), 1.0)

        bandwidth = (latest_upper - latest_lower) / latest_mid
        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=position,
            timestamp=data.index[-1],
            metadata={
                "position_in_band": position,
                "upper": latest_upper,
                "mid": latest_mid,
                "lower": latest_lower,
                "bandwidth": bandwidth,
            },
        )

    def _evaluate(self, position: float) -> SignalDirection:
        if position > self.overbought_threshold:
            return SignalDirection.SELL
        elif position < self.oversold_threshold:
            return SignalDirection.BUY
        else:
            return SignalDirection.HOLD

    def get_params(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "std_dev": self.std_dev,
            "overbought_threshold": self.overbought_threshold,
            "oversold_threshold": self.oversold_threshold,
        }
