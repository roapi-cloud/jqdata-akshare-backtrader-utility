# -*- coding: utf-8 -*-
"""
仓位管理模块

根据择时信号计算建议仓位。

仓位管理方法:
    1. 固定比例: 信号 BUY=100%, SELL=0%, HOLD=50%
    2. 信号强度比例: 仓位 = (strength + 1) / 2
    3. Kelly 公式: 仓位 = (p * b - q) / b
    4. 波动率调整: 根据市场波动率动态调整仓位
    5. 分层仓位: 大盘择时控制总仓位，个股择时控制个股权重
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from ..base import TimingResult, TimingSignal, SignalDirection


class PositionManager:
    """
    仓位管理器

    参数:
        method: 仓位计算方法 (fixed/strength/kelly/volatility/hierarchical)
        max_position: 最大仓位 (默认 1.0)
        min_position: 最小仓位 (默认 0.0)
        volatility_target: 目标波动率 (默认 0.15)
        kelly_fraction: Kelly 分数 (默认 0.25, 即 1/4 Kelly)
    """

    def __init__(
        self,
        method: str = "strength",
        max_position: float = 1.0,
        min_position: float = 0.0,
        volatility_target: float = 0.15,
        kelly_fraction: float = 0.25,
    ):
        self.method = method
        self.max_position = max_position
        self.min_position = min_position
        self.volatility_target = volatility_target
        self.kelly_fraction = kelly_fraction

    def compute_position(
        self,
        result: TimingResult,
        market_vol: Optional[float] = None,
        win_rate: Optional[float] = None,
        win_loss_ratio: Optional[float] = None,
    ) -> float:
        """
        计算建议仓位

        Args:
            result: 择时结果
            market_vol: 市场波动率 (年化)
            win_rate: 历史胜率
            win_loss_ratio: 历史盈亏比
        """
        if self.method == "fixed":
            return self._fixed_position(result)
        elif self.method == "strength":
            return self._strength_position(result)
        elif self.method == "kelly":
            return self._kelly_position(result, win_rate, win_loss_ratio)
        elif self.method == "volatility":
            return self._volatility_position(result, market_vol)
        elif self.method == "hierarchical":
            return self._hierarchical_position(result, market_vol)
        else:
            return self._strength_position(result)

    def _fixed_position(self, result: TimingResult) -> float:
        if result.composite_direction == SignalDirection.BUY:
            return self.max_position
        elif result.composite_direction == SignalDirection.SELL:
            return self.min_position
        else:
            return (self.max_position + self.min_position) / 2

    def _strength_position(self, result: TimingResult) -> float:
        strength = result.composite_strength
        position = (strength + 1) / 2
        return np.clip(
            position * (self.max_position - self.min_position) + self.min_position,
            self.min_position,
            self.max_position,
        )

    def _kelly_position(
        self,
        result: TimingResult,
        win_rate: Optional[float] = None,
        win_loss_ratio: Optional[float] = None,
    ) -> float:
        if win_rate is None or win_loss_ratio is None:
            return self._strength_position(result)

        q = 1 - win_rate
        kelly = (win_rate * win_loss_ratio - q) / win_loss_ratio
        kelly = kelly * self.kelly_fraction

        if result.composite_direction == SignalDirection.SELL:
            return self.min_position

        return np.clip(
            kelly * (result.composite_strength + 1) / 2,
            self.min_position,
            self.max_position,
        )

    def _volatility_position(
        self, result: TimingResult, market_vol: Optional[float] = None
    ) -> float:
        base_position = self._strength_position(result)

        if market_vol is None or market_vol == 0:
            return base_position

        vol_ratio = self.volatility_target / market_vol
        adjusted = base_position * vol_ratio

        return np.clip(adjusted, self.min_position, self.max_position)

    def _hierarchical_position(
        self, result: TimingResult, market_vol: Optional[float] = None
    ) -> float:
        base_position = self._strength_position(result)

        market_strength = result.metadata.get("market_strength", 0)
        stock_strength = result.metadata.get("stock_strength", 0)

        if market_strength < -0.3:
            market_position = 0.0
        elif market_strength < 0:
            market_position = 0.3
        elif market_strength < 0.3:
            market_position = 0.5
        else:
            market_position = 1.0

        stock_position = (stock_strength + 1) / 2

        final_position = market_position * 0.6 + stock_position * 0.4

        if market_vol and market_vol > 0:
            vol_ratio = self.volatility_target / market_vol
            final_position *= vol_ratio

        return np.clip(final_position, self.min_position, self.max_position)

    def compute_individual_weights(
        self, signals: list, total_position: float
    ) -> Dict[str, float]:
        """
        计算个股权重分配

        Args:
            signals: 个股择时信号列表
            total_position: 总仓位

        Returns:
            {stock_code: weight}
        """
        if not signals:
            return {}

        positive_signals = [s for s in signals if s.is_buy or s.is_hold]
        if not positive_signals:
            return {}

        total_strength = sum(max(s.strength, 0) + 0.1 for s in positive_signals)

        weights = {}
        for s in positive_signals:
            weight = ((s.strength + 0.1) / total_strength) * total_position
            weights[s.metadata.get("stock_code", s.model_name)] = weight

        return weights
