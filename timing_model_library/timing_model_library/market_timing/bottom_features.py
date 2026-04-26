# -*- coding: utf-8 -*-
"""
市场底部特征模型

综合多个底部信号判断市场是否处于底部区域。

底部特征:
    1. 成交量萎缩到极值 (地量见地价)
    2. 波动率从高位回落
    3. 市场宽度极低后开始回升
    4. 跌停家数减少
    5. 指数偏离长期均线过远 (超跌)
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import sma, realized_volatility, zscore, rolling_rank


class BottomFeaturesModel(BaseTimingModel):
    """
    市场底部特征模型

    参数:
        vol_ma_period: 成交量均线周期 (默认 60)
        vol_extreme_threshold: 地量阈值 (默认 0.3)
        ma_long_period: 长期均线周期 (默认 250)
        ma_deviation_threshold: 均线偏离阈值 (默认 -0.25)
        signal_count_threshold: 底部信号数量阈值 (默认 3)
    """

    def __init__(
        self,
        vol_ma_period: int = 60,
        vol_extreme_threshold: float = 0.3,
        ma_long_period: int = 250,
        ma_deviation_threshold: float = -0.25,
        signal_count_threshold: int = 3,
    ):
        super().__init__(name="Bottom-Features", scope=TimingScope.MARKET)
        self.vol_ma_period = vol_ma_period
        self.vol_extreme_threshold = vol_extreme_threshold
        self.ma_long_period = ma_long_period
        self.ma_deviation_threshold = ma_deviation_threshold
        self.signal_count_threshold = signal_count_threshold

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        """
        Args:
            data: 必须包含 'close', 'volume'
                  可选: 'limit_down', 'up_count', 'down_count'
        """
        self._validate_data(data, ["close", "volume"])

        signals = {}

        signals["volume_shrink"] = self._check_volume_shrink(data)
        signals["vol_decline"] = self._check_volatility_decline(data)
        signals["ma_deviation"] = self._check_ma_deviation(data)
        signals["breadth_recovery"] = self._check_breadth_recovery(data)
        signals["limit_down_reduce"] = self._check_limit_down(data)

        signal_count = sum(1 for v in signals.values() if v)
        bottom_score = signal_count / len(signals)

        if signal_count >= self.signal_count_threshold:
            direction = SignalDirection.BUY
        elif signal_count >= 2:
            direction = SignalDirection.HOLD
        else:
            direction = SignalDirection.SELL

        strength = np.clip((bottom_score - 0.5) * 2, -1.0, 1.0)
        confidence = min(bottom_score, 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=bottom_score,
            timestamp=data.index[-1],
            metadata={
                "signal_count": signal_count,
                "total_signals": len(signals),
                "signals": signals,
            },
        )

    def _check_volume_shrink(self, data: pd.DataFrame) -> bool:
        """地量信号: 成交量 < 60日均量的 30%"""
        vol_ma = sma(data["volume"], self.vol_ma_period)
        vol_ratio = data["volume"] / vol_ma.replace(0, np.nan)
        return vol_ratio.iloc[-1] < self.vol_extreme_threshold

    def _check_volatility_decline(self, data: pd.DataFrame) -> bool:
        """波动率从高位回落"""
        vol = realized_volatility(data["close"], window=20)
        vol_rank = vol.rolling(250).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )
        return vol_rank.iloc[-1] < 0.3

    def _check_ma_deviation(self, data: pd.DataFrame) -> bool:
        """超跌信号: 价格偏离 250 日均线超过阈值"""
        ma_long = sma(data["close"], self.ma_long_period)
        deviation = (data["close"] - ma_long) / ma_long.replace(0, np.nan)
        return deviation.iloc[-1] < self.ma_deviation_threshold

    def _check_breadth_recovery(self, data: pd.DataFrame) -> bool:
        """市场宽度回升"""
        if "up_count" not in data.columns or "down_count" not in data.columns:
            return False
        total = data["up_count"] + data["down_count"]
        breadth = data["up_count"] / total.replace(0, np.nan)
        breadth_ma = sma(breadth, 10)
        return breadth_ma.iloc[-1] > breadth_ma.iloc[-5] and breadth.iloc[-1] > 0.4

    def _check_limit_down(self, data: pd.DataFrame) -> bool:
        """跌停家数减少"""
        if "limit_down" not in data.columns:
            return False
        return (
            data["limit_down"].iloc[-1] < data["limit_down"].rolling(20).mean().iloc[-1]
        )

    def get_params(self) -> Dict[str, Any]:
        return {
            "vol_ma_period": self.vol_ma_period,
            "vol_extreme_threshold": self.vol_extreme_threshold,
            "ma_long_period": self.ma_long_period,
            "ma_deviation_threshold": self.ma_deviation_threshold,
            "signal_count_threshold": self.signal_count_threshold,
        }
