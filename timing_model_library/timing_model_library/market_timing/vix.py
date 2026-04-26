# -*- coding: utf-8 -*-
"""
C-VIX 恐慌指数模型

中国版 VIX 编制:
    1. 基于期权隐含波动率 (如果有期权数据)
    2. 或用已实现波动率 + 市场情绪代理构建

核心逻辑:
    - VIX 高位 → 市场恐慌 → 潜在底部信号
    - VIX 低位 → 市场贪婪 → 潜在顶部信号
    - VIX 急剧上升 → 恐慌加剧 → 卖出
    - VIX 从高位回落 → 恐慌消退 → 买入
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import realized_volatility, zscore, rolling_rank


class CVIXModel(BaseTimingModel):
    """
    C-VIX 恐慌指数模型

    参数:
        vol_window: 波动率计算窗口 (默认 20)
        lookback: 历史参考天数 (默认 250)
        panic_threshold: 恐慌阈值 (Z-Score, 默认 1.5)
        greed_threshold: 贪婪阈值 (Z-Score, 默认 -1.0)
    """

    def __init__(
        self,
        vol_window: int = 20,
        lookback: int = 250,
        panic_threshold: float = 1.5,
        greed_threshold: float = -1.0,
    ):
        super().__init__(name="C-VIX", scope=TimingScope.MARKET)
        self.vol_window = vol_window
        self.lookback = lookback
        self.panic_threshold = panic_threshold
        self.greed_threshold = greed_threshold

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        self._validate_data(data, ["close"])

        vol_window = kwargs.get("vol_window", self.vol_window)
        lookback = kwargs.get("lookback", self.lookback)

        vol = realized_volatility(data["close"], window=vol_window)
        vol_z = zscore(vol, lookback=lookback)
        vol_rank = rolling_rank(vol, lookback=lookback)

        latest_vol_z = vol_z.iloc[-1]
        latest_vol = vol.iloc[-1]
        latest_rank = vol_rank.iloc[-1]

        direction = self._evaluate(latest_vol_z, latest_rank)
        strength = np.clip(-latest_vol_z / 3.0, -1.0, 1.0)
        confidence = min(abs(latest_vol_z) / 3.0, 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=latest_vol_z,
            timestamp=data.index[-1],
            metadata={
                "vol_z": latest_vol_z,
                "vol_annualized": latest_vol,
                "vol_percentile": latest_rank,
                "regime": self._get_regime(latest_vol_z),
            },
        )

    def _evaluate(self, vol_z: float, vol_rank: float) -> SignalDirection:
        """
        VIX 信号逻辑:
            - 极度恐慌 (Z > panic_threshold) → 逆向买入 (别人恐惧我贪婪)
            - 极度贪婪 (Z < greed_threshold) → 卖出
            - VIX 从高位快速回落 → 买入
        """
        if vol_z > self.panic_threshold:
            return SignalDirection.BUY
        elif vol_z < self.greed_threshold:
            return SignalDirection.SELL
        else:
            return SignalDirection.HOLD

    def _get_regime(self, vol_z: float) -> str:
        if vol_z > 2.0:
            return "极度恐慌"
        elif vol_z > self.panic_threshold:
            return "恐慌"
        elif vol_z > 0.5:
            return "谨慎"
        elif vol_z > self.greed_threshold:
            return "中性"
        elif vol_z > -1.5:
            return "乐观"
        else:
            return "极度贪婪"

    def get_params(self) -> Dict[str, Any]:
        return {
            "vol_window": self.vol_window,
            "lookback": self.lookback,
            "panic_threshold": self.panic_threshold,
            "greed_threshold": self.greed_threshold,
        }
