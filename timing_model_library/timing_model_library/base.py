# -*- coding: utf-8 -*-
"""
择时模型抽象基类

所有择时模型继承此基类，统一信号输出格式。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np


class SignalDirection(Enum):
    """信号方向"""

    BUY = 1
    HOLD = 0
    SELL = -1


class TimingScope(Enum):
    """择时适用范围"""

    MARKET = "market"  # 大盘择时
    SECTOR = "sector"  # 行业/板块择时
    STOCK = "stock"  # 个股择时
    ETF = "etf"  # ETF择时


@dataclass
class TimingSignal:
    """择时信号统一输出格式"""

    model_name: str
    scope: TimingScope
    direction: SignalDirection
    strength: float  # 信号强度 [-1.0, 1.0]
    confidence: float  # 置信度 [0.0, 1.0]
    raw_score: float  # 原始分数 (模型特定)
    timestamp: pd.Timestamp
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_buy(self) -> bool:
        return self.direction == SignalDirection.BUY

    @property
    def is_sell(self) -> bool:
        return self.direction == SignalDirection.SELL

    @property
    def is_hold(self) -> bool:
        return self.direction == SignalDirection.HOLD


@dataclass
class TimingResult:
    """择时结果 (包含多个信号的综合结果)"""

    signals: List[TimingSignal]
    composite_direction: SignalDirection
    composite_strength: float
    composite_position: float  # 建议仓位 [0.0, 1.0]
    timestamp: pd.Timestamp
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTimingModel(ABC):
    """择时模型抽象基类"""

    def __init__(self, name: str, scope: TimingScope):
        self.name = name
        self.scope = scope
        self._state: Dict[str, Any] = {}

    @abstractmethod
    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        """
        计算择时信号

        Args:
            data: 行情数据，必须包含 OHLCV 列
            **kwargs: 模型特定参数

        Returns:
            TimingSignal: 择时信号
        """
        pass

    @abstractmethod
    def get_params(self) -> Dict[str, Any]:
        """返回模型当前参数"""
        pass

    def set_params(self, **kwargs) -> None:
        """设置模型参数"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self._state[key] = value

    def reset(self) -> None:
        """重置模型状态"""
        self._state.clear()

    def _validate_data(self, data: pd.DataFrame, required_columns: List[str]) -> None:
        """验证数据完整性"""
        missing = [col for col in required_columns if col not in data.columns]
        if missing:
            raise ValueError(f"数据缺少必要列: {missing}")
        if len(data) < 60:
            raise ValueError(f"数据量不足，至少需要60条，当前{len(data)}条")


class BaseCompositeModel:
    """组合择时模型基类 (多模型融合)"""

    def __init__(self, name: str, models: List[BaseTimingModel]):
        self.name = name
        self.models = models
        self._weights: Dict[str, float] = {m.name: 1.0 for m in models}

    def set_weights(self, weights: Dict[str, float]) -> None:
        """设置模型权重"""
        self._weights.update(weights)

    @abstractmethod
    def fuse(self, signals: List[TimingSignal]) -> TimingResult:
        """
        融合多个信号

        Args:
            signals: 各模型的择时信号

        Returns:
            TimingResult: 综合择时结果
        """
        pass

    def compute_all(self, data: pd.DataFrame, **kwargs) -> List[TimingSignal]:
        """计算所有模型的信号"""
        signals = []
        for model in self.models:
            try:
                signal = model.compute(data, **kwargs)
                signals.append(signal)
            except Exception as e:
                print(f"模型 {model.name} 计算失败: {e}")
        return signals
