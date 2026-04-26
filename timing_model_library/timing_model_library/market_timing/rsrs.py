# -*- coding: utf-8 -*-
"""
RSRS (Resistance Support Relative Strength) 择时模型家族

RSRS 通过高低点线性回归斜率判断支撑阻力相对强度，是 A 股最有效的大盘择时指标之一。

模型变体:
    1. RSRSModel: 基础 RSRS (斜率 Z-Score × R²)
    2. VolumeWeightedRSRS: 成交量加权 RSRS (4 种子变体)
    3. AdvancedRSRS: 高级 RSRS (斜率趋势 + WR 过滤 + 动量)
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import (
    slope_r2,
    weighted_slope_r2,
    zscore,
    williams_r,
    linear_regression_slope,
)


class RSRSModel(BaseTimingModel):
    """
    基础 RSRS 择时模型

    核心逻辑:
        1. 对 N 日高低点做 OLS 回归: high = slope * low + intercept
        2. 计算斜率的 M 日 Z-Score
        3. 最终分数 = Z-Score × R²

    参数:
        N: 回归窗口 (默认 18)
        M: Z-Score 参考历史天数 (默认 600)
        buy_threshold: 买入阈值 (默认 0.7)
        sell_threshold: 卖出阈值 (默认 -0.7)
    """

    def __init__(
        self,
        N: int = 18,
        M: int = 600,
        buy_threshold: float = 0.7,
        sell_threshold: float = -0.7,
    ):
        super().__init__(name="RSRS", scope=TimingScope.MARKET)
        self.N = N
        self.M = M
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        self._validate_data(data, ["high", "low"])

        N = kwargs.get("N", self.N)
        M = kwargs.get("M", self.M)
        buy_thr = kwargs.get("buy_threshold", self.buy_threshold)
        sell_thr = kwargs.get("sell_threshold", self.sell_threshold)

        slopes, r2_values = slope_r2(data["low"], data["high"], window=N)
        z = zscore(slopes, lookback=M)
        rsrs_score = z * r2_values

        latest_score = rsrs_score.iloc[-1]
        latest_r2 = r2_values.iloc[-1]
        latest_z = z.iloc[-1]

        if latest_score > buy_thr:
            direction = SignalDirection.BUY
        elif latest_score < sell_thr:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        strength = np.clip(latest_score / 2.0, -1.0, 1.0)
        confidence = min(abs(latest_r2), 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=latest_score,
            timestamp=data.index[-1],
            metadata={
                "zscore": latest_z,
                "r2": latest_r2,
                "slope": slopes.iloc[-1],
                "N": N,
                "M": M,
            },
        )

    def get_params(self) -> Dict[str, Any]:
        return {
            "N": self.N,
            "M": self.M,
            "buy_threshold": self.buy_threshold,
            "sell_threshold": self.sell_threshold,
        }


class VolumeWeightedRSRS(BaseTimingModel):
    """
    成交量加权 RSRS 模型 (Vol-RSRS)

    核心改进:
        用成交量作为回归权重，高成交量日的价格关系更可靠

    4 种子变体:
        - right: 右偏 RSRS (zscore × beta × r2)
        - right_dull: 右偏 + 波动率钝化
        - unbiased: 无偏 RSRS (zscore × r2)
        - unbiased_dull: 无偏 + 波动率钝化

    参数:
        N: 回归窗口 (默认 18)
        M: Z-Score 参考天数 (默认 200)
        variant: 变体类型 (right/right_dull/unbiased/unbiased_dull)
    """

    VARIANTS = {
        "right": {"buy": 0.85, "sell": -0.85},
        "right_dull": {"buy": 0.75, "sell": -0.75},
        "unbiased": {"buy": 0.9, "sell": -0.9},
        "unbiased_dull": {"buy": 0.7, "sell": -0.7},
    }

    def __init__(self, N: int = 18, M: int = 200, variant: str = "right"):
        super().__init__(name=f"Vol-RSRS-{variant}", scope=TimingScope.MARKET)
        self.N = N
        self.M = M
        self.variant = variant

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        self._validate_data(data, ["high", "low", "close", "volume"])

        N = kwargs.get("N", self.N)
        M = kwargs.get("M", self.M)
        variant = kwargs.get("variant", self.variant)

        slopes, r2_values = weighted_slope_r2(
            data["low"], data["high"], data["volume"], window=N
        )
        z = zscore(slopes, lookback=M)

        beta = slopes
        std_percent = self._compute_dullness(data["close"], N, M)

        if variant == "right":
            rsrs_score = z * beta * r2_values
        elif variant == "right_dull":
            rsrs_score = z * beta * (r2_values ** (2 * std_percent))
        elif variant == "unbiased":
            rsrs_score = z * r2_values
        elif variant == "unbiased_dull":
            rsrs_score = z * (r2_values ** (2 * std_percent))
        else:
            rsrs_score = z * r2_values

        thresholds = self.VARIANTS.get(variant, {"buy": 0.85, "sell": -0.85})
        buy_thr = kwargs.get("buy_threshold", thresholds["buy"])
        sell_thr = kwargs.get("sell_threshold", thresholds["sell"])

        latest_score = rsrs_score.iloc[-1]

        if latest_score > buy_thr:
            direction = SignalDirection.BUY
        elif latest_score < sell_thr:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        strength = np.clip(latest_score / 2.0, -1.0, 1.0)
        confidence = min(r2_values.iloc[-1], 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=latest_score,
            timestamp=data.index[-1],
            metadata={
                "variant": variant,
                "zscore": z.iloc[-1],
                "r2": r2_values.iloc[-1],
                "dullness": std_percent.iloc[-1],
            },
        )

    def _compute_dullness(self, close: pd.Series, N: int, M: int) -> pd.Series:
        """波动率钝化因子: 当前波动率在历史中的百分位"""
        returns = close.pct_change()
        vol = returns.rolling(window=N).std()
        dullness = vol.rolling(window=M).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )
        return dullness

    def get_params(self) -> Dict[str, Any]:
        return {
            "N": self.N,
            "M": self.M,
            "variant": self.variant,
        }


class AdvancedRSRS(BaseTimingModel):
    """
    高级 RSRS 模型 (RSRS + 斜率趋势 + WR 过滤 + 动量)

    核心逻辑:
        1. 基础 RSRS 分数 (zscore × r2)
        2. RSRS 分数自身的斜率趋势 (K 日线性回归)
        3. 指数 8 日趋势斜率
        4. Williams %R 极端超滤过滤
        5. 动量速度过滤

    信号优先级 (从上到下，命中即返回):
        1. WR >= 97 → 极端超卖，买入
        2. rsrs_slope < 0 AND rsrs_score > 0 → 趋势反转，卖出
        3. idex_slope < 0 AND rsrs_slope > 0 AND rsrs_score < -0.43 → 卖出
        4. idex_slope > 12 AND rsrs_slope > 0 → 强势，买入
        5. rsrs_score > -0.68 → 买入
        6. else → 卖出
    """

    def __init__(
        self,
        N: int = 18,
        M: int = 600,
        K: int = 8,
        score_threshold: float = -0.68,
        score_fall_threshold: float = -0.43,
        idex_slope_threshold: float = 12,
        wr_period: int = 21,
        wr_threshold: float = 97,
    ):
        super().__init__(name="Advanced-RSRS", scope=TimingScope.MARKET)
        self.N = N
        self.M = M
        self.K = K
        self.score_threshold = score_threshold
        self.score_fall_threshold = score_fall_threshold
        self.idex_slope_threshold = idex_slope_threshold
        self.wr_period = wr_period
        self.wr_threshold = wr_threshold

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        self._validate_data(data, ["high", "low", "close"])

        N = kwargs.get("N", self.N)
        M = kwargs.get("M", self.M)
        K = kwargs.get("K", self.K)

        slopes, r2_values = slope_r2(data["low"], data["high"], window=N)
        z = zscore(slopes, lookback=M)
        rsrs_score = z * r2_values

        rsrs_slope = linear_regression_slope(rsrs_score, window=K)
        idex_slope = linear_regression_slope(data["close"], window=8)

        wr = williams_r(data["high"], data["low"], data["close"], period=self.wr_period)
        wr1 = wr.iloc[-1]
        wr2 = wr.iloc[-2] if len(wr) > 1 else wr1

        latest_score = rsrs_score.iloc[-1]
        latest_rsrs_slope = rsrs_slope.iloc[-1]
        latest_idex_slope = idex_slope.iloc[-1]

        direction = self._evaluate_signals(
            wr1, wr2, latest_rsrs_slope, latest_score, latest_idex_slope
        )

        strength = np.clip(latest_score / 2.0, -1.0, 1.0)
        confidence = min(r2_values.iloc[-1], 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=latest_score,
            timestamp=data.index[-1],
            metadata={
                "rsrs_score": latest_score,
                "rsrs_slope": latest_rsrs_slope,
                "idex_slope": latest_idex_slope,
                "wr1": wr1,
                "wr2": wr2,
            },
        )

    def _evaluate_signals(
        self,
        wr1: float,
        wr2: float,
        rsrs_slope: float,
        rsrs_score: float,
        idex_slope: float,
    ) -> SignalDirection:
        """按优先级评估信号"""
        if wr1 >= self.wr_threshold and wr2 >= self.wr_threshold:
            return SignalDirection.BUY

        if rsrs_slope < 0 and rsrs_score > 0:
            return SignalDirection.SELL

        if idex_slope < 0 and rsrs_slope > 0 and rsrs_score < self.score_fall_threshold:
            return SignalDirection.SELL

        if idex_slope > self.idex_slope_threshold and rsrs_slope > 0:
            return SignalDirection.BUY

        if rsrs_score > self.score_threshold:
            return SignalDirection.BUY

        return SignalDirection.SELL

    def get_params(self) -> Dict[str, Any]:
        return {
            "N": self.N,
            "M": self.M,
            "K": self.K,
            "score_threshold": self.score_threshold,
            "score_fall_threshold": self.score_fall_threshold,
            "idex_slope_threshold": self.idex_slope_threshold,
        }
