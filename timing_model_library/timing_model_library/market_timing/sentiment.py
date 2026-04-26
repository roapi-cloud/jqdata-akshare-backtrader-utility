# -*- coding: utf-8 -*-
"""
投资者情绪指数模型

综合多个情绪指标构建市场情绪指数。

情绪指标来源:
    - 涨停/跌停家数比
    - 封板率
    - 融资余额变化
    - 换手率
    - 新开户数 (如有)
    - 基金发行规模 (如有)
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import zscore, sma


class SentimentModel(BaseTimingModel):
    """
    投资者情绪指数模型

    参数:
        lookback: 历史参考天数 (默认 250)
        extreme_high: 情绪极度乐观阈值 (默认 0.85)
        extreme_low: 情绪极度悲观阈值 (默认 0.15)
    """

    def __init__(
        self, lookback: int = 250, extreme_high: float = 0.85, extreme_low: float = 0.15
    ):
        super().__init__(name="Sentiment", scope=TimingScope.MARKET)
        self.lookback = lookback
        self.extreme_high = extreme_high
        self.extreme_low = extreme_low

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        """
        Args:
            data: 必须包含以下列中的至少 2 个:
                  - 'limit_up': 涨停家数
                  - 'limit_down': 跌停家数
                  - 'margin_balance': 融资余额
                  - 'turnover_rate': 换手率
                  - 'sealed_rate': 封板率
        """
        available_cols = set(data.columns)
        required = {
            "limit_up",
            "limit_down",
            "margin_balance",
            "turnover_rate",
            "sealed_rate",
        }
        available = available_cols & required

        if len(available) < 2:
            raise ValueError(f"至少需要 2 个情绪指标，当前可用: {available}")

        lookback = kwargs.get("lookback", self.lookback)

        sentiment_score = self._compute_sentiment(data, available, lookback)
        latest_score = sentiment_score.iloc[-1]

        direction = self._evaluate(latest_score)
        strength = np.clip((latest_score - 0.5) * 2, -1.0, 1.0)
        confidence = min(abs(strength), 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=latest_score,
            timestamp=data.index[-1],
            metadata={
                "sentiment_score": latest_score,
                "regime": self._get_regime(latest_score),
            },
        )

    def _compute_sentiment(
        self, data: pd.DataFrame, available: set, lookback: int
    ) -> pd.Series:
        """综合计算情绪分数 [0, 1]"""
        components = []

        if "limit_up" in available and "limit_down" in available:
            ratio = data["limit_up"] / (data["limit_up"] + data["limit_down"]).replace(
                0, np.nan
            )
            components.append(ratio)

        if "margin_balance" in available:
            margin_z = zscore(data["margin_balance"], lookback)
            margin_norm = 1 / (1 + np.exp(-margin_z))
            components.append(margin_norm)

        if "turnover_rate" in available:
            turn_z = zscore(data["turnover_rate"], lookback)
            turn_norm = 1 / (1 + np.exp(-turn_z))
            components.append(turn_norm)

        if "sealed_rate" in available:
            components.append(data["sealed_rate"])

        sentiment = pd.concat(components, axis=1).mean(axis=1)
        return sentiment

    def _evaluate(self, score: float) -> SignalDirection:
        if score > self.extreme_high:
            return SignalDirection.SELL
        elif score < self.extreme_low:
            return SignalDirection.BUY
        else:
            return SignalDirection.HOLD

    def _get_regime(self, score: float) -> str:
        if score > 0.9:
            return "极度狂热-顶部风险"
        elif score > self.extreme_high:
            return "过热-谨慎"
        elif score > 0.6:
            return "乐观"
        elif score > 0.4:
            return "中性"
        elif score > self.extreme_low:
            return "悲观-关注"
        else:
            return "极度悲观-底部机会"

    def get_params(self) -> Dict[str, Any]:
        return {
            "lookback": self.lookback,
            "extreme_high": self.extreme_high,
            "extreme_low": self.extreme_low,
        }
