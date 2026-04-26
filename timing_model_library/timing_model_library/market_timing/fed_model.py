# -*- coding: utf-8 -*-
"""
FED 模型 + 格雷厄姆指数

大周期顶底判断工具，用于判断股市相对于债市的估值高低。

核心逻辑:
    FED 模型:
        - 股市收益率 (1/PE) vs 10 年期国债收益率
        - 当 1/PE > 国债收益率 + 风险溢价 → 股市低估 → 买入
        - 当 1/PE < 国债收益率 → 股市高估 → 卖出

    格雷厄姆指数:
        - (1/PE) / 国债收益率
        - > 2 → 股市极具投资价值
        - < 1 → 股市高估
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope


class FEDModel(BaseTimingModel):
    """
    FED 模型 + 格雷厄姆指数

    参数:
        risk_premium: 风险溢价 (默认 0.02, 即 2%)
        strong_buy_threshold: 格雷厄姆指数强买阈值 (默认 2.0)
        buy_threshold: 格雷厄姆指数买阈值 (默认 1.5)
        sell_threshold: 格雷厄姆指数卖阈值 (默认 1.0)
    """

    def __init__(
        self,
        risk_premium: float = 0.02,
        strong_buy_threshold: float = 2.0,
        buy_threshold: float = 1.5,
        sell_threshold: float = 1.0,
    ):
        super().__init__(name="FED-Model", scope=TimingScope.MARKET)
        self.risk_premium = risk_premium
        self.strong_buy_threshold = strong_buy_threshold
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        """
        Args:
            data: 必须包含 'pe_ratio' (市盈率) 和 'bond_yield' (10Y国债收益率)
        """
        required = ["pe_ratio", "bond_yield"]
        self._validate_data(data, required)

        pe = data["pe_ratio"].iloc[-1]
        bond_yield = data["bond_yield"].iloc[-1]

        if pe <= 0:
            return self._invalid_signal(data.index[-1])

        earnings_yield = 1.0 / pe
        graham_ratio = earnings_yield / bond_yield if bond_yield > 0 else 0
        fed_spread = earnings_yield - bond_yield

        direction = self._evaluate(earnings_yield, bond_yield, graham_ratio)
        strength = self._compute_strength(graham_ratio, fed_spread)
        confidence = min(abs(strength), 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=graham_ratio,
            timestamp=data.index[-1],
            metadata={
                "pe_ratio": pe,
                "earnings_yield": earnings_yield,
                "bond_yield": bond_yield,
                "graham_ratio": graham_ratio,
                "fed_spread": fed_spread,
                "regime": self._get_regime(graham_ratio),
            },
        )

    def _evaluate(
        self, earnings_yield: float, bond_yield: float, graham_ratio: float
    ) -> SignalDirection:
        if graham_ratio >= self.strong_buy_threshold:
            return SignalDirection.BUY
        elif graham_ratio >= self.buy_threshold:
            return SignalDirection.BUY
        elif graham_ratio <= self.sell_threshold:
            return SignalDirection.SELL
        else:
            return SignalDirection.HOLD

    def _compute_strength(self, graham_ratio: float, fed_spread: float) -> float:
        normalized = (graham_ratio - 1.0) / 2.0
        return np.clip(normalized, -1.0, 1.0)

    def _get_regime(self, graham_ratio: float) -> str:
        if graham_ratio >= self.strong_buy_threshold:
            return "极度低估-强买"
        elif graham_ratio >= self.buy_threshold:
            return "低估-买入"
        elif graham_ratio >= 1.0:
            return "合理"
        elif graham_ratio >= self.sell_threshold:
            return "偏高-谨慎"
        else:
            return "高估-卖出"

    def _invalid_signal(self, timestamp: pd.Timestamp) -> TimingSignal:
        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=SignalDirection.HOLD,
            strength=0.0,
            confidence=0.0,
            raw_score=0.0,
            timestamp=timestamp,
            metadata={"error": "PE <= 0, invalid data"},
        )

    def get_params(self) -> Dict[str, Any]:
        return {
            "risk_premium": self.risk_premium,
            "strong_buy_threshold": self.strong_buy_threshold,
            "buy_threshold": self.buy_threshold,
            "sell_threshold": self.sell_threshold,
        }
