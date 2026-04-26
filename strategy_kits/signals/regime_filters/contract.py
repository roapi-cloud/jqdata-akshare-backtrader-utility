"""
统一数据契约
"""
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional
from enum import Enum


class RegimeState(Enum):
    ALLOWED = "allowed"      # 允许正常执行 alpha
    REDUCE = "reduce"        # 建议降仓
    HOLD = "hold"            # 建议观望/空仓
    WARNING = "warning"      # 风险预警


@dataclass
class SubSignal:
    """单个原始子信号"""
    name: str
    value: float
    direction: Literal["bullish", "bearish", "neutral", "extreme"]
    weight: float = 1.0
    meta: Dict = field(default_factory=dict)


@dataclass
class RiskFlag:
    """风险标志位"""
    name: str
    triggered: bool
    severity: Literal["low", "medium", "high"]
    suggestion: str = ""


@dataclass
class RegimeFilterOutput:
    """总闸门输出"""
    date: str
    regime_state: RegimeState
    sub_signals: List[SubSignal]
    risk_flags: List[RiskFlag]
    raw_scores: Dict[str, float]
    config_snapshot: Dict
