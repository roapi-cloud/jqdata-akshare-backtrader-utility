# -*- coding: utf-8 -*-
"""
MACD 择时模型

包含 3 种子模型:
    1. 月线 MACD: 用月线数据判断大周期趋势
    2. 日线 MACD: 标准 MACD 择时
    3. 快线 MACD (EMA2-EMA4): 超短期趋势过滤
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import macd, ema


class MACDTimingModel(BaseTimingModel):
    """
    MACD 择时模型

    参数:
        variant: 变体类型 (monthly/daily/fast)
        fast: 快线周期 (默认 12)
        slow: 慢线周期 (默认 26)
        signal: 信号线周期 (默认 9)
    """

    def __init__(
        self, variant: str = "daily", fast: int = 12, slow: int = 26, signal: int = 9
    ):
        super().__init__(name=f"MACD-{variant}", scope=TimingScope.MARKET)
        self.variant = variant
        self.fast = fast
        self.slow = slow
        self.signal_period = signal

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        self._validate_data(data, ["close"])

        fast = kwargs.get("fast", self.fast)
        slow = kwargs.get("slow", self.slow)
        signal_period = kwargs.get("signal", self.signal_period)

        close = data["close"]

        if self.variant == "monthly":
            close_monthly = close.resample("ME").last()
            dif, dea, macd_hist = macd(close_monthly, fast, slow, signal_period)
            latest_macd = macd_hist.iloc[-1] * 2
        elif self.variant == "fast":
            ema2 = ema(close, 2)
            ema4 = ema(close, 4)
            dif = ema2 - ema4
            dea = ema(dif, 4)
            latest_macd = (dif - dea).iloc[-1]
        else:
            dif, dea, macd_hist = macd(close, fast, slow, signal_period)
            latest_macd = macd_hist.iloc[-1]

        direction = self._evaluate(latest_macd)
        strength = np.clip(latest_macd / (abs(latest_macd) + 1e-10), -1.0, 1.0)
        confidence = min(abs(strength), 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=latest_macd,
            timestamp=data.index[-1],
            metadata={
                "variant": self.variant,
                "macd_value": latest_macd,
            },
        )

    def _evaluate(self, macd_value: float) -> SignalDirection:
        if macd_value > 0:
            return SignalDirection.BUY
        elif macd_value < 0:
            return SignalDirection.SELL
        else:
            return SignalDirection.HOLD

    def get_params(self) -> Dict[str, Any]:
        return {
            "variant": self.variant,
            "fast": self.fast,
            "slow": self.slow,
            "signal": self.signal_period,
        }
