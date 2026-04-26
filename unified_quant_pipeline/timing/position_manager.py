"""仓位管理 - 根据择时信号调整仓位"""

import logging
from typing import Dict, Optional
from .market_timing import TimingSignal

logger = logging.getLogger(__name__)


class PositionManager:
    """仓位管理器

    根据择时信号动态调整目标仓位比例。
    """

    def __init__(self, method: str = "strength", base_position: float = 1.0):
        """初始化仓位管理器

        Args:
            method: 仓位调整方法 ('fixed', 'strength', 'linear')
            base_position: 基础仓位比例 [0, 1]
        """
        self.method = method
        self.base_position = base_position

    def adjust(self, signal: TimingSignal) -> float:
        """根据择时信号调整仓位

        Args:
            signal: 择时信号

        Returns:
            float: 目标仓位比例 [0, 1]
        """
        if self.method == "fixed":
            return self._fixed_position(signal)
        elif self.method == "strength":
            return self._strength_position(signal)
        elif self.method == "linear":
            return self._linear_position(signal)
        else:
            raise ValueError(f"Unknown position method: {self.method}")

    def _fixed_position(self, signal: TimingSignal) -> float:
        """固定仓位 - 买入100%，卖出0%

        Args:
            signal: 择时信号

        Returns:
            float: 目标仓位比例
        """
        if signal.direction > 0:
            return self.base_position
        elif signal.direction < 0:
            return 0.0
        return self.base_position * 0.5

    def _strength_position(self, signal: TimingSignal) -> float:
        """根据信号强度调整仓位

        Args:
            signal: 择时信号

        Returns:
            float: 目标仓位比例
        """
        position = (signal.strength + 1) / 2 * self.base_position
        return max(0.0, min(position, self.base_position))

    def _linear_position(self, signal: TimingSignal) -> float:
        """线性映射仓位

        Args:
            signal: 择时信号

        Returns:
            float: 目标仓位比例
        """
        if signal.direction > 0:
            return self.base_position
        elif signal.direction < 0:
            return self.base_position * 0.3
        return self.base_position * 0.7
