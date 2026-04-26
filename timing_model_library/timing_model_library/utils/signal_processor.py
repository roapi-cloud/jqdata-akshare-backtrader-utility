# -*- coding: utf-8 -*-
"""
信号处理工具: 平滑、过滤、共振检测
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Tuple
from ..base import TimingSignal, SignalDirection, TimingResult


def signal_smoothing(
    signals: List[float], method: str = "ema", span: int = 5
) -> pd.Series:
    """
    信号平滑

    Args:
        signals: 原始信号序列
        method: 平滑方法 (ema/sma/median)
        span: 平滑窗口
    """
    s = pd.Series(signals)
    if method == "ema":
        return s.ewm(span=span, adjust=False).mean()
    elif method == "sma":
        return s.rolling(window=span).mean()
    elif method == "median":
        return s.rolling(window=span).median()
    return s


def cooldown_filter(
    current_signal: SignalDirection,
    last_signal: SignalDirection,
    min_hold_days: int,
    days_since_change: int,
) -> SignalDirection:
    """
    冷却期过滤: 避免频繁切换

    Args:
        current_signal: 当前信号
        last_signal: 上次信号
        min_hold_days: 最小持有天数
        days_since_change: 距上次信号变化天数
    """
    if current_signal != last_signal and days_since_change < min_hold_days:
        return last_signal
    return current_signal


def trend_filter(signal: float, trend_strength: float, threshold: float = 0.3) -> float:
    """
    趋势过滤: 在弱趋势中降低信号强度

    Args:
        signal: 原始信号强度
        trend_strength: 趋势强度 [0, 1]
        threshold: 趋势强度阈值
    """
    if trend_strength < threshold:
        return signal * (trend_strength / threshold)
    return signal


def detect_resonance(
    signals: List[TimingSignal], min_agreement: float = 0.6
) -> Tuple[SignalDirection, float]:
    """
    信号共振检测: 多个模型信号一致时增强

    Args:
        signals: 各模型信号
        min_agreement: 最小一致比例

    Returns:
        (共振方向, 共振强度)
    """
    if not signals:
        return SignalDirection.HOLD, 0.0

    buy_count = sum(1 for s in signals if s.is_buy)
    sell_count = sum(1 for s in signals if s.is_sell)
    total = len(signals)

    buy_ratio = buy_count / total
    sell_ratio = sell_count / total

    if buy_ratio >= min_agreement:
        avg_strength = np.mean([s.strength for s in signals if s.is_buy])
        return SignalDirection.BUY, avg_strength * buy_ratio
    elif sell_ratio >= min_agreement:
        avg_strength = np.mean([s.strength for s in signals if s.is_sell])
        return SignalDirection.SELL, avg_strength * sell_ratio
    else:
        return SignalDirection.HOLD, 0.0


def weighted_average_signal(
    signals: List[TimingSignal], weights: Optional[dict] = None
) -> TimingSignal:
    """
    加权平均信号

    Args:
        signals: 各模型信号
        weights: 模型名称 -> 权重映射
    """
    if not signals:
        return None

    if weights is None:
        weights = {s.model_name: 1.0 for s in signals}

    total_weight = sum(weights.get(s.model_name, 1.0) for s in signals)

    weighted_strength = (
        sum(s.strength * weights.get(s.model_name, 1.0) for s in signals) / total_weight
    )

    weighted_confidence = (
        sum(s.confidence * weights.get(s.model_name, 1.0) for s in signals)
        / total_weight
    )

    if weighted_strength > 0.2:
        direction = SignalDirection.BUY
    elif weighted_strength < -0.2:
        direction = SignalDirection.SELL
    else:
        direction = SignalDirection.HOLD

    return TimingSignal(
        model_name="composite",
        scope=signals[0].scope,
        direction=direction,
        strength=weighted_strength,
        confidence=weighted_confidence,
        raw_score=weighted_strength,
        timestamp=signals[0].timestamp,
        metadata={"individual_signals": [s.model_name for s in signals]},
    )


def hysteresis_filter(
    current_score: float,
    prev_direction: SignalDirection,
    buy_threshold: float,
    sell_threshold: float,
) -> SignalDirection:
    """
    滞回滤波: 买入和卖出使用不同阈值，避免震荡

    Args:
        current_score: 当前分数
        prev_direction: 上次信号方向
        buy_threshold: 买入阈值
        sell_threshold: 卖出阈值
    """
    if prev_direction == SignalDirection.SELL:
        if current_score > buy_threshold:
            return SignalDirection.BUY
        return SignalDirection.SELL
    elif prev_direction == SignalDirection.BUY:
        if current_score < sell_threshold:
            return SignalDirection.SELL
        return SignalDirection.BUY
    else:
        if current_score > buy_threshold:
            return SignalDirection.BUY
        elif current_score < sell_threshold:
            return SignalDirection.SELL
        return SignalDirection.HOLD
