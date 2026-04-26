# -*- coding: utf-8 -*-
"""
因子择时模型

根据因子有效性周期调整因子权重。

核心逻辑:
    - 跟踪各因子 (价值/动量/质量/小市值) 的历史表现
    - 当因子 IC 下降或回撤过大时降低权重
    - 当因子 IC 回升时增加权重
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope


class FactorTimingModel(BaseTimingModel):
    """
    因子择时模型

    参数:
        lookback: 因子表现回看窗口 (默认 60)
        ic_threshold: IC 阈值 (默认 0.02)
        drawdown_threshold: 最大回撤阈值 (默认 -0.15)
    """

    def __init__(
        self,
        lookback: int = 60,
        ic_threshold: float = 0.02,
        drawdown_threshold: float = -0.15,
    ):
        super().__init__(name="Factor-Timing", scope=TimingScope.STOCK)
        self.lookback = lookback
        self.ic_threshold = ic_threshold
        self.drawdown_threshold = drawdown_threshold

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        """
        Args:
            data: 必须包含因子 IC 序列或因子收益序列
                  columns: 'value_ic', 'momentum_ic', 'quality_ic', 'size_ic'
                  或: 'value_ret', 'momentum_ret', 'quality_ret', 'size_ret'
        """
        ic_cols = [c for c in data.columns if c.endswith("_ic")]
        ret_cols = [c for c in data.columns if c.endswith("_ret")]

        if ic_cols:
            factor_scores = self._evaluate_ic(data[ic_cols])
        elif ret_cols:
            factor_scores = self._evaluate_returns(data[ret_cols])
        else:
            raise ValueError("数据必须包含 IC 列或收益列")

        avg_score = np.mean(list(factor_scores.values()))
        active_factors = sum(1 for s in factor_scores.values() if s > self.ic_threshold)

        if avg_score > self.ic_threshold and active_factors >= 2:
            direction = SignalDirection.BUY
        elif avg_score < -self.ic_threshold:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        strength = np.clip(avg_score * 10, -1.0, 1.0)
        confidence = min(active_factors / len(factor_scores), 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=avg_score,
            timestamp=data.index[-1],
            metadata={
                "factor_scores": factor_scores,
                "active_factors": active_factors,
                "avg_ic": avg_score,
            },
        )

    def _evaluate_ic(self, ic_data: pd.DataFrame) -> Dict[str, float]:
        scores = {}
        for col in ic_data.columns:
            factor_name = col.replace("_ic", "")
            recent_ic = ic_data[col].iloc[-self.lookback :].mean()
            ic_std = ic_data[col].iloc[-self.lookback :].std()
            ir = recent_ic / ic_std if ic_std > 0 else 0
            scores[factor_name] = ir
        return scores

    def _evaluate_returns(self, ret_data: pd.DataFrame) -> Dict[str, float]:
        scores = {}
        for col in ret_data.columns:
            factor_name = col.replace("_ret", "")
            cum_ret = (1 + ret_data[col]).cumprod()
            peak = cum_ret.cummax()
            drawdown = (cum_ret - peak) / peak
            recent_ret = ret_data[col].iloc[-self.lookback :].mean()
            max_dd = drawdown.iloc[-1]
            score = recent_ret + max_dd
            scores[factor_name] = score
        return scores

    def get_params(self) -> Dict[str, Any]:
        return {
            "lookback": self.lookback,
            "ic_threshold": self.ic_threshold,
            "drawdown_threshold": self.drawdown_threshold,
        }
