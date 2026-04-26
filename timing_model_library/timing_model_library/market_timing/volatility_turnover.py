# -*- coding: utf-8 -*-
"""
波动率 + 换手率 牛熊指标

源自华泰证券研报，通过大盘波动率和换手率综合判断市场牛熊状态。

核心逻辑:
    1. 计算 N 日已实现波动率 (年化)
    2. 计算 N 日市场换手率
    3. 波动率和换手率同时处于高位 → 熊市 (情绪过热)
    4. 波动率和换手率同时处于低位 → 牛市初期 (情绪冰点)
    5. 波动率下降 + 换手率上升 → 牛市中期
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import realized_volatility, zscore


class VolatilityTurnoverBullBear(BaseTimingModel):
    """
    波动率 + 换手率 牛熊指标

    参数:
        vol_window: 波动率计算窗口 (默认 20)
        turnover_window: 换手率计算窗口 (默认 20)
        lookback: Z-Score 参考历史天数 (默认 250)
        vol_high_threshold: 波动率高位 Z-Score 阈值 (默认 1.0)
        vol_low_threshold: 波动率低位 Z-Score 阈值 (默认 -1.0)
        turnover_high_threshold: 换手率高位 Z-Score 阈值 (默认 1.0)
        turnover_low_threshold: 换手率低位 Z-Score 阈值 (默认 -1.0)
    """

    def __init__(
        self,
        vol_window: int = 20,
        turnover_window: int = 20,
        lookback: int = 250,
        vol_high_threshold: float = 1.0,
        vol_low_threshold: float = -1.0,
        turnover_high_threshold: float = 1.0,
        turnover_low_threshold: float = -1.0,
    ):
        super().__init__(name="Vol-Turnover-BullBear", scope=TimingScope.MARKET)
        self.vol_window = vol_window
        self.turnover_window = turnover_window
        self.lookback = lookback
        self.vol_high_threshold = vol_high_threshold
        self.vol_low_threshold = vol_low_threshold
        self.turnover_high_threshold = turnover_high_threshold
        self.turnover_low_threshold = turnover_low_threshold

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        self._validate_data(data, ["close", "volume"])

        vol_window = kwargs.get("vol_window", self.vol_window)
        turnover_window = kwargs.get("turnover_window", self.turnover_window)
        lookback = kwargs.get("lookback", self.lookback)

        vol = realized_volatility(data["close"], window=vol_window)
        vol_z = zscore(vol, lookback=lookback)

        turnover = data["volume"].rolling(window=turnover_window).mean()
        turnover_z = zscore(turnover, lookback=lookback)

        latest_vol_z = vol_z.iloc[-1]
        latest_turnover_z = turnover_z.iloc[-1]

        direction, regime = self._classify_regime(latest_vol_z, latest_turnover_z)

        strength = self._compute_strength(latest_vol_z, latest_turnover_z)
        confidence = min(abs(strength), 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=strength,
            timestamp=data.index[-1],
            metadata={
                "vol_z": latest_vol_z,
                "turnover_z": latest_turnover_z,
                "regime": regime,
                "vol_annualized": vol.iloc[-1],
            },
        )

    def _classify_regime(self, vol_z: float, turnover_z: float) -> tuple:
        """
        牛熊状态分类

        Returns:
            (SignalDirection, regime_name)
        """
        vol_high = vol_z > self.vol_high_threshold
        vol_low = vol_z < self.vol_low_threshold
        turn_high = turnover_z > self.turnover_high_threshold
        turn_low = turnover_z < self.turnover_low_threshold

        if vol_high and turn_high:
            return SignalDirection.SELL, "熊市-过热"
        elif vol_low and turn_low:
            return SignalDirection.BUY, "牛市初期-冰点"
        elif vol_low and turn_high:
            return SignalDirection.BUY, "牛市中期-温和"
        elif vol_high and turn_low:
            return SignalDirection.HOLD, "震荡-恐慌"
        else:
            return SignalDirection.HOLD, "中性"

    def _compute_strength(self, vol_z: float, turnover_z: float) -> float:
        """
        计算综合强度分数 [-1, 1]
        负值 = 熊市信号, 正值 = 牛市信号
        """
        vol_signal = -vol_z
        turnover_signal = -turnover_z
        return np.clip((vol_signal + turnover_signal) / 2.0, -1.0, 1.0)

    def get_params(self) -> Dict[str, Any]:
        return {
            "vol_window": self.vol_window,
            "turnover_window": self.turnover_window,
            "lookback": self.lookback,
            "vol_high_threshold": self.vol_high_threshold,
            "vol_low_threshold": self.vol_low_threshold,
            "turnover_high_threshold": self.turnover_high_threshold,
            "turnover_low_threshold": self.turnover_low_threshold,
        }
