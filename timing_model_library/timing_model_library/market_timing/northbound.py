# -*- coding: utf-8 -*-
"""
北向资金择时模型

通过北向资金净流入/流出判断大盘方向。

核心逻辑:
    - 北向资金持续净流入 → 外资看好 → 买入信号
    - 北向资金持续净流出 → 外资看空 → 卖出信号
    - 结合布林带判断资金流向的极端值
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import sma


class NorthboundModel(BaseTimingModel):
    """
    北向资金择时模型

    参数:
        window: 布林带计算窗口 (默认 90)
        stdev_n: 标准差倍数 (默认 2.0)
        flow_ma: 资金流均线周期 (默认 5)
    """

    def __init__(self, window: int = 90, stdev_n: float = 2.0, flow_ma: int = 5):
        super().__init__(name="Northbound", scope=TimingScope.MARKET)
        self.window = window
        self.stdev_n = stdev_n
        self.flow_ma = flow_ma

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        """
        Args:
            data: 必须包含 'north_net' (北向资金净流入)
                  可选: 'close' (用于计算相关性)
        """
        self._validate_data(data, ["north_net"])

        window = kwargs.get("window", self.window)
        stdev_n = kwargs.get("stdev_n", self.stdev_n)
        flow_ma = kwargs.get("flow_ma", self.flow_ma)

        net_flow = data["north_net"]
        flow_ma_series = sma(net_flow, flow_ma)

        mid = sma(net_flow, window)
        std = net_flow.rolling(window=window).std()
        upper = mid + stdev_n * std
        lower = mid - stdev_n * std

        latest_flow = flow_ma_series.iloc[-1]
        latest_upper = upper.iloc[-1]
        latest_lower = lower.iloc[-1]

        direction = self._evaluate(latest_flow, latest_upper, latest_lower)
        strength = self._compute_strength(latest_flow, mid.iloc[-1], std.iloc[-1])
        confidence = min(abs(strength), 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=latest_flow,
            timestamp=data.index[-1],
            metadata={
                "net_flow_ma": latest_flow,
                "boll_upper": latest_upper,
                "boll_lower": latest_lower,
                "boll_mid": mid.iloc[-1],
            },
        )

    def _evaluate(self, flow: float, upper: float, lower: float) -> SignalDirection:
        if flow > upper:
            return SignalDirection.BUY
        elif flow < lower:
            return SignalDirection.SELL
        else:
            return SignalDirection.HOLD

    def _compute_strength(self, flow: float, mid: float, std: float) -> float:
        if std == 0:
            return 0.0
        normalized = (flow - mid) / std
        return np.clip(normalized / 3.0, -1.0, 1.0)

    def get_params(self) -> Dict[str, Any]:
        return {
            "window": self.window,
            "stdev_n": self.stdev_n,
            "flow_ma": self.flow_ma,
        }
