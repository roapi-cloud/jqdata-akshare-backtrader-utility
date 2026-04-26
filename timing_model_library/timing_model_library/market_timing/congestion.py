# -*- coding: utf-8 -*-
"""
拥挤率指标 (Congestion Rate)

用于判断大盘/行业交易拥挤程度，辅助顶底判断。

核心逻辑:
    - 拥挤度高 → 交易过度集中 → 潜在顶部
    - 拥挤度低 → 交易清淡 → 潜在底部
    - 拥挤度快速上升 → 趋势加速 → 警惕反转
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import zscore, rolling_rank


class CongestionModel(BaseTimingModel):
    """
    拥挤率指标

    参数:
        window: 计算窗口 (默认 60)
        lookback: 历史参考天数 (默认 250)
        high_threshold: 高拥挤阈值 (默认 0.8)
        low_threshold: 低拥挤阈值 (默认 0.2)
    """

    def __init__(
        self,
        window: int = 60,
        lookback: int = 250,
        high_threshold: float = 0.8,
        low_threshold: float = 0.2,
    ):
        super().__init__(name="Congestion", scope=TimingScope.MARKET)
        self.window = window
        self.lookback = lookback
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        """
        Args:
            data: 必须包含 'volume', 'amount', 'close'
        """
        self._validate_data(data, ["volume", "amount", "close"])

        window = kwargs.get("window", self.window)
        lookback = kwargs.get("lookback", self.lookback)

        congestion = self._compute_congestion(data, window)
        congestion_rank = rolling_rank(congestion, lookback=lookback)

        latest_congestion = congestion.iloc[-1]
        latest_rank = congestion_rank.iloc[-1]

        direction = self._evaluate(latest_rank)
        strength = np.clip((0.5 - latest_rank) * 2, -1.0, 1.0)
        confidence = min(abs(strength), 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=latest_rank,
            timestamp=data.index[-1],
            metadata={
                "congestion": latest_congestion,
                "congestion_percentile": latest_rank,
                "regime": self._get_regime(latest_rank),
            },
        )

    def _compute_congestion(self, data: pd.DataFrame, window: int) -> pd.Series:
        """
        拥挤度 = 成交量 / 流通市值 (代理)
        或用: 成交额占比 / 市值占比
        """
        avg_volume = data["volume"].rolling(window=window).mean()
        avg_amount = data["amount"].rolling(window=window).mean()

        turnover_velocity = avg_volume / avg_volume.rolling(window=window).mean()
        amount_velocity = avg_amount / avg_amount.rolling(window=window).mean()

        congestion = (turnover_velocity + amount_velocity) / 2
        return congestion

    def _evaluate(self, congestion_rank: float) -> SignalDirection:
        if congestion_rank > self.high_threshold:
            return SignalDirection.SELL
        elif congestion_rank < self.low_threshold:
            return SignalDirection.BUY
        else:
            return SignalDirection.HOLD

    def _get_regime(self, rank: float) -> str:
        if rank > 0.9:
            return "极度拥挤-顶部风险"
        elif rank > self.high_threshold:
            return "拥挤-谨慎"
        elif rank > 0.5:
            return "正常"
        elif rank > self.low_threshold:
            return "冷清-关注"
        else:
            return "极度冷清-底部机会"

    def get_params(self) -> Dict[str, Any]:
        return {
            "window": self.window,
            "lookback": self.lookback,
            "high_threshold": self.high_threshold,
            "low_threshold": self.low_threshold,
        }
