# -*- coding: utf-8 -*-
"""
顶底判断模型 (MACD 背离 + EMA 通道)

源自"神虽顶底"策略，通过 MACD 背离结构和 EMA 通道判断顶底。

核心逻辑:
    1. MACD 红柱期间:
       - 顶背离: DIF 不创新高但价格创新高 → 顶部结构
    2. MACD 绿柱期间:
       - 底背离: DIF 不创新低但价格创新低 → 底部结构
    3. EMA 通道仓位管理:
       - 价格在 EMA(25) 高/低 和 EMA(90) 高/低 之间 → 不同仓位
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import macd, ema


class TopBottomModel(BaseTimingModel):
    """
    顶底判断模型

    参数:
        fast: MACD 快线 (默认 12)
        slow: MACD 慢线 (默认 26)
        signal: MACD 信号线 (默认 9)
        short_period: 短期 EMA 周期 (默认 25)
        long_period: 长期 EMA 周期 (默认 90)
    """

    def __init__(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        short_period: int = 25,
        long_period: int = 90,
    ):
        super().__init__(name="TopBottom", scope=TimingScope.MARKET)
        self.fast = fast
        self.slow = slow
        self.signal_period = signal
        self.short_period = short_period
        self.long_period = long_period

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        self._validate_data(data, ["close", "high", "low"])

        close = data["close"]
        high = data["high"]
        low = data["low"]

        dif, dea, macd_hist = macd(close, self.fast, self.slow, self.signal_period)

        short_high = ema(high, self.short_period)
        short_low = ema(low, self.short_period)
        long_high = ema(high, self.long_period)
        long_low = ema(low, self.long_period)

        latest_close = close.iloc[-1]
        latest_macd = macd_hist.iloc[-1]

        top_structure = self._detect_top_structure(dif, macd_hist, close)
        bottom_structure = self._detect_bottom_structure(dif, macd_hist, close)

        direction, position = self._evaluate_position(
            latest_close,
            short_high.iloc[-1],
            short_low.iloc[-1],
            long_high.iloc[-1],
            long_low.iloc[-1],
            top_structure,
            bottom_structure,
        )

        strength = (position - 0.5) * 2
        confidence = 0.7 if top_structure or bottom_structure else 0.4

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=position,
            timestamp=data.index[-1],
            metadata={
                "position_pct": position,
                "top_structure": top_structure,
                "bottom_structure": bottom_structure,
                "macd": latest_macd,
            },
        )

    def _detect_top_structure(
        self, dif: pd.Series, macd_hist: pd.Series, close: pd.Series
    ) -> bool:
        """检测顶部背离结构"""
        if len(macd_hist) < 30:
            return False

        red_mask = macd_hist > 0
        if not red_mask.iloc[-1]:
            return False

        current_red = self._get_current_red_period(macd_hist)
        if len(current_red) < 3:
            return False

        prev_red = self._get_previous_red_period(macd_hist, current_red)
        if prev_red is None or len(prev_red) < 3:
            return False

        dif_current = dif.iloc[current_red[-1]]
        dif_prev = dif.iloc[prev_red[-1]]
        price_current = close.iloc[current_red[-1]]
        price_prev = close.iloc[prev_red[-1]]

        return dif_current < dif_prev and price_current > price_prev

    def _detect_bottom_structure(
        self, dif: pd.Series, macd_hist: pd.Series, close: pd.Series
    ) -> bool:
        """检测底部背离结构"""
        if len(macd_hist) < 30:
            return False

        green_mask = macd_hist < 0
        if not green_mask.iloc[-1]:
            return False

        current_green = self._get_current_green_period(macd_hist)
        if len(current_green) < 3:
            return False

        prev_green = self._get_previous_green_period(macd_hist, current_green)
        if prev_green is None or len(prev_green) < 3:
            return False

        dif_current = dif.iloc[current_green[-1]]
        dif_prev = dif.iloc[prev_green[-1]]
        price_current = close.iloc[current_green[-1]]
        price_prev = close.iloc[prev_green[-1]]

        return dif_current > dif_prev and price_current < price_prev

    def _get_current_red_period(self, macd_hist: pd.Series) -> list:
        indices = []
        for i in range(len(macd_hist) - 1, -1, -1):
            if macd_hist.iloc[i] > 0:
                indices.append(i)
            else:
                break
        return list(reversed(indices))

    def _get_previous_red_period(
        self, macd_hist: pd.Series, current: list
    ) -> Optional[list]:
        start = current[0] - 1
        indices = []
        for i in range(start, -1, -1):
            if macd_hist.iloc[i] > 0:
                indices.append(i)
            elif len(indices) > 0:
                break
        return list(reversed(indices)) if indices else None

    def _get_current_green_period(self, macd_hist: pd.Series) -> list:
        indices = []
        for i in range(len(macd_hist) - 1, -1, -1):
            if macd_hist.iloc[i] < 0:
                indices.append(i)
            else:
                break
        return list(reversed(indices))

    def _get_previous_green_period(
        self, macd_hist: pd.Series, current: list
    ) -> Optional[list]:
        start = current[0] - 1
        indices = []
        for i in range(start, -1, -1):
            if macd_hist.iloc[i] < 0:
                indices.append(i)
            elif len(indices) > 0:
                break
        return list(reversed(indices)) if indices else None

    def _evaluate_position(
        self,
        close: float,
        short_high: float,
        short_low: float,
        long_high: float,
        long_low: float,
        top_structure: bool,
        bottom_structure: bool,
    ) -> tuple:
        if top_structure:
            return SignalDirection.SELL, 0.0

        if bottom_structure:
            return SignalDirection.BUY, 1.0

        if close > short_high and close > long_high:
            return SignalDirection.BUY, 1.0
        elif close > short_high and close < long_low:
            return SignalDirection.HOLD, 0.6
        elif close < short_low and close > long_high:
            return SignalDirection.HOLD, 0.4
        elif close < short_low and close < long_low:
            return SignalDirection.SELL, 0.0
        else:
            return SignalDirection.HOLD, 0.5

    def get_params(self) -> Dict[str, Any]:
        return {
            "fast": self.fast,
            "slow": self.slow,
            "signal": self.signal_period,
            "short_period": self.short_period,
            "long_period": self.long_period,
        }
