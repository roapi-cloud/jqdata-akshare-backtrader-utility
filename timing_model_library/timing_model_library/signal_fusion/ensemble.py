# -*- coding: utf-8 -*-
"""
多信号融合模块

将多个择时模型的信号融合为一个综合信号。

融合方法:
    1. 加权平均: 各模型信号加权求和
    2. 投票法: 多数模型方向决定最终方向
    3. 共振法: 只有当多个模型一致时才产生强信号
    4. 分层融合: 先按类别融合 (大盘/个股)，再综合
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from ..base import (
    TimingSignal,
    TimingResult,
    SignalDirection,
    TimingScope,
    BaseTimingModel,
    BaseCompositeModel,
)
from ..utils.signal_processor import detect_resonance, weighted_average_signal


class SignalEnsemble(BaseCompositeModel):
    """
    多信号融合器

    参数:
        method: 融合方法 (weighted/vote/resonance/hierarchical)
        weights: 模型权重映射
        resonance_threshold: 共振阈值 (默认 0.6)
    """

    def __init__(
        self,
        name: str = "SignalEnsemble",
        models: List[BaseTimingModel] = None,
        method: str = "weighted",
        weights: Dict[str, float] = None,
        resonance_threshold: float = 0.6,
    ):
        super().__init__(name, models or [])
        self.method = method
        self._weights = weights or {m.name: 1.0 for m in self.models}
        self.resonance_threshold = resonance_threshold

    def fuse(self, signals: List[TimingSignal]) -> TimingResult:
        if not signals:
            return TimingResult(
                signals=[],
                composite_direction=SignalDirection.HOLD,
                composite_strength=0.0,
                composite_position=0.5,
                timestamp=pd.Timestamp.now(),
            )

        if self.method == "weighted":
            return self._weighted_fusion(signals)
        elif self.method == "vote":
            return self._vote_fusion(signals)
        elif self.method == "resonance":
            return self._resonance_fusion(signals)
        elif self.method == "hierarchical":
            return self._hierarchical_fusion(signals)
        else:
            return self._weighted_fusion(signals)

    def _weighted_fusion(self, signals: List[TimingSignal]) -> TimingResult:
        total_weight = sum(self._weights.get(s.model_name, 1.0) for s in signals)
        weighted_strength = (
            sum(s.strength * self._weights.get(s.model_name, 1.0) for s in signals)
            / total_weight
        )

        if weighted_strength > 0.15:
            direction = SignalDirection.BUY
        elif weighted_strength < -0.15:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        position = self._strength_to_position(weighted_strength)

        return TimingResult(
            signals=signals,
            composite_direction=direction,
            composite_strength=weighted_strength,
            composite_position=position,
            timestamp=signals[0].timestamp,
            metadata={"method": "weighted"},
        )

    def _vote_fusion(self, signals: List[TimingSignal]) -> TimingResult:
        buy_count = sum(1 for s in signals if s.is_buy)
        sell_count = sum(1 for s in signals if s.is_sell)
        total = len(signals)

        if buy_count > sell_count:
            direction = SignalDirection.BUY
        elif sell_count > buy_count:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        strength = (buy_count - sell_count) / total
        position = self._strength_to_position(strength)

        return TimingResult(
            signals=signals,
            composite_direction=direction,
            composite_strength=strength,
            composite_position=position,
            timestamp=signals[0].timestamp,
            metadata={
                "method": "vote",
                "buy_count": buy_count,
                "sell_count": sell_count,
            },
        )

    def _resonance_fusion(self, signals: List[TimingSignal]) -> TimingResult:
        direction, strength = detect_resonance(signals, self.resonance_threshold)
        position = self._strength_to_position(strength)

        return TimingResult(
            signals=signals,
            composite_direction=direction,
            composite_strength=strength,
            composite_position=position,
            timestamp=signals[0].timestamp,
            metadata={"method": "resonance", "threshold": self.resonance_threshold},
        )

    def _hierarchical_fusion(self, signals: List[TimingSignal]) -> TimingResult:
        market_signals = [s for s in signals if s.scope == TimingScope.MARKET]
        stock_signals = [s for s in signals if s.scope == TimingScope.STOCK]

        market_result = (
            self._weighted_fusion(market_signals) if market_signals else None
        )
        stock_result = self._weighted_fusion(stock_signals) if stock_signals else None

        market_weight = 0.7
        stock_weight = 0.3

        combined_strength = 0.0
        if market_result:
            combined_strength += market_result.composite_strength * market_weight
        if stock_result:
            combined_strength += stock_result.composite_strength * stock_weight

        if combined_strength > 0.15:
            direction = SignalDirection.BUY
        elif combined_strength < -0.15:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        position = self._strength_to_position(combined_strength)

        return TimingResult(
            signals=signals,
            composite_direction=direction,
            composite_strength=combined_strength,
            composite_position=position,
            timestamp=signals[0].timestamp,
            metadata={
                "method": "hierarchical",
                "market_strength": market_result.composite_strength
                if market_result
                else 0,
                "stock_strength": stock_result.composite_strength
                if stock_result
                else 0,
            },
        )

    def _strength_to_position(self, strength: float) -> float:
        if strength > 0.5:
            return 1.0
        elif strength > 0.2:
            return 0.7
        elif strength > 0:
            return 0.5
        elif strength > -0.2:
            return 0.3
        elif strength > -0.5:
            return 0.1
        else:
            return 0.0
