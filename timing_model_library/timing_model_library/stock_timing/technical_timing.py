# -*- coding: utf-8 -*-
"""
个股技术指标择时模型

包含 RSI、MA、BOLL 等技术指标的个股择时。

核心逻辑:
    - RSI 择时: RSI < 50 买入, RSI > 70 卖出
    - MA 择时: 均线金叉买入, 死叉卖出
    - BOLL 择时: 触及下轨买入, 触及上轨卖出
    - 多指标共振: 多个指标一致时增强信号
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import rsi, sma, boll, ema


class TechnicalTimingModel(BaseTimingModel):
    """
    个股技术指标择时模型

    参数:
        indicators: 使用的指标列表 (默认 ['rsi', 'ma', 'boll'])
        rsi_period: RSI 周期 (默认 14)
        rsi_buy: RSI 买入阈值 (默认 50)
        rsi_sell: RSI 卖出阈值 (默认 70)
        ma_fast: 快速均线 (默认 5)
        ma_slow: 慢速均线 (默认 20)
        boll_period: 布林带周期 (默认 20)
        boll_std: 布林带标准差 (默认 2.0)
    """

    def __init__(
        self,
        indicators: List[str] = None,
        rsi_period: int = 14,
        rsi_buy: float = 50,
        rsi_sell: float = 70,
        ma_fast: int = 5,
        ma_slow: int = 20,
        boll_period: int = 20,
        boll_std: float = 2.0,
    ):
        super().__init__(name="Technical-Timing", scope=TimingScope.STOCK)
        self.indicators = indicators or ["rsi", "ma", "boll"]
        self.rsi_period = rsi_period
        self.rsi_buy = rsi_buy
        self.rsi_sell = rsi_sell
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow
        self.boll_period = boll_period
        self.boll_std = boll_std

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        self._validate_data(data, ["close", "high", "low"])

        sub_signals = {}

        if "rsi" in self.indicators:
            sub_signals["rsi"] = self._rsi_signal(data)

        if "ma" in self.indicators:
            sub_signals["ma"] = self._ma_signal(data)

        if "boll" in self.indicators:
            sub_signals["boll"] = self._boll_signal(data)

        if "macd" in self.indicators:
            sub_signals["macd"] = self._macd_signal(data)

        direction, strength = self._combine_signals(sub_signals)
        confidence = len(sub_signals) / len(self.indicators) if self.indicators else 0

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=strength,
            timestamp=data.index[-1],
            metadata={
                "sub_signals": sub_signals,
                "indicators_used": list(sub_signals.keys()),
            },
        )

    def _rsi_signal(self, data: pd.DataFrame) -> Dict:
        rsi_val = rsi(data["close"], self.rsi_period).iloc[-1]
        if rsi_val < self.rsi_buy:
            direction = SignalDirection.BUY
        elif rsi_val > self.rsi_sell:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD
        return {"value": rsi_val, "direction": direction.name}

    def _ma_signal(self, data: pd.DataFrame) -> Dict:
        fast_ma = sma(data["close"], self.ma_fast)
        slow_ma = sma(data["close"], self.ma_slow)
        if fast_ma.iloc[-1] > slow_ma.iloc[-1] and fast_ma.iloc[-2] <= slow_ma.iloc[-2]:
            direction = SignalDirection.BUY
        elif (
            fast_ma.iloc[-1] < slow_ma.iloc[-1] and fast_ma.iloc[-2] >= slow_ma.iloc[-2]
        ):
            direction = SignalDirection.SELL
        elif fast_ma.iloc[-1] > slow_ma.iloc[-1]:
            direction = SignalDirection.BUY
        else:
            direction = SignalDirection.SELL
        return {
            "fast": fast_ma.iloc[-1],
            "slow": slow_ma.iloc[-1],
            "direction": direction.name,
        }

    def _boll_signal(self, data: pd.DataFrame) -> Dict:
        upper, mid, lower = boll(data["close"], self.boll_period, self.boll_std)
        close = data["close"].iloc[-1]
        position = (
            (close - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])
            if upper.iloc[-1] != lower.iloc[-1]
            else 0.5
        )
        if position < 0.1:
            direction = SignalDirection.BUY
        elif position > 0.9:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD
        return {"position": position, "direction": direction.name}

    def _macd_signal(self, data: pd.DataFrame) -> Dict:
        from ..utils.indicators import macd

        dif, dea, macd_hist = macd(data["close"])
        if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
            direction = SignalDirection.BUY
        elif dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]:
            direction = SignalDirection.SELL
        elif dif.iloc[-1] > dea.iloc[-1]:
            direction = SignalDirection.BUY
        else:
            direction = SignalDirection.SELL
        return {"dif": dif.iloc[-1], "dea": dea.iloc[-1], "direction": direction.name}

    def _combine_signals(self, sub_signals: Dict) -> tuple:
        if not sub_signals:
            return SignalDirection.HOLD, 0.0

        buy_count = sum(1 for s in sub_signals.values() if s["direction"] == "BUY")
        sell_count = sum(1 for s in sub_signals.values() if s["direction"] == "SELL")
        total = len(sub_signals)

        if buy_count > sell_count:
            direction = SignalDirection.BUY
        elif sell_count > buy_count:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        strength = (buy_count - sell_count) / total
        return direction, strength

    def get_params(self) -> Dict[str, Any]:
        return {
            "indicators": self.indicators,
            "rsi_period": self.rsi_period,
            "rsi_buy": self.rsi_buy,
            "rsi_sell": self.rsi_sell,
            "ma_fast": self.ma_fast,
            "ma_slow": self.ma_slow,
            "boll_period": self.boll_period,
            "boll_std": self.boll_std,
        }
