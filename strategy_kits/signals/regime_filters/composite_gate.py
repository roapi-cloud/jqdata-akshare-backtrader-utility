"""
状态合成与路由

职责：
- 解析 risk_flags 规则，直接路由到 WARNING / REDUCE
- 基于 sub_signals 投票计算综合得分，映射到 RegimeState
"""
from typing import Dict, List

from .contract import RegimeState, SubSignal, RiskFlag


def route_regime(
    sub_signals: List[SubSignal],
    risk_flags: List[RiskFlag],
    rules: Dict,
) -> RegimeState:
    """根据子信号和风险标志合成最终市场状态"""

    # 1. 风险标志直接路由
    high_flags = [f for f in risk_flags if f.triggered and f.severity == "high"]
    if rules.get("any_high_risk_to_warning", True) and high_flags:
        return RegimeState.WARNING

    medium_flags = [f for f in risk_flags if f.triggered and f.severity == "medium"]
    threshold = rules.get("medium_risk_count_to_reduce", 2)
    if len(medium_flags) >= threshold:
        return RegimeState.REDUCE

    # 2. 子信号投票路由
    weights = rules.get("vote_weights", {})
    total_weight = sum(weights.values())
    score = 0.0
    dir_map = {
        "bullish": 1.0,
        "neutral": 0.0,
        "bearish": -1.0,
        "extreme": -1.0,
    }
    for sig in sub_signals:
        if sig.name in weights:
            score += dir_map.get(sig.direction, 0.0) * weights[sig.name]
    score = score / total_weight if total_weight > 0 else 0.0

    th = rules.get("thresholds", {})
    if score <= th.get("hold", -0.6):
        return RegimeState.HOLD
    elif score <= th.get("reduce", -0.3):
        return RegimeState.REDUCE
    elif score >= th.get("allowed", 0.2):
        return RegimeState.ALLOWED
    else:
        return RegimeState.WARNING
