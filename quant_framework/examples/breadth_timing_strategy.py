# -*- coding: utf-8 -*-
"""
Market Breadth Timing Strategy
==============================

Strategy Logic:
    - Uses Above-MA ratio + volume shrinkage for market timing
    - Buy signal: breadth ratio improves (above MA golden cross) AND volume shrinks
      (indicating selling exhaustion at market bottom)
    - Sell signal: breadth ratio deteriorates (above MA death cross) AND volume expands
      (indicating distribution at market top)
    - Target: CSI 300 ETF (510300)

Parameters:
    ma_breadth_period: Window for breadth ratio MA (default 10)
    ma_breadth_slow: Slow MA for breadth ratio trend (default 30)
    vol_short_period: Short window for volume MA (default 5)
    vol_long_period: Long window for volume MA (default 20)
    vol_shrink_threshold: Volume shrinkage ratio threshold for buy (default 0.8)
    vol_expand_threshold: Volume expansion ratio threshold for sell (default 1.2)
    breadth_buy_threshold: Minimum breadth ratio for buy confirmation (default 0.5)
"""

from datetime import date
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from quant_framework.core.strategy.base import BaseStrategy, Portfolio
from quant_framework.core.factors.breadth import AboveMARatioFactor
from quant_framework.core.factors.sentiment import VolumeShrinkageFactor


class BreadthTimingStrategy(BaseStrategy):
    """
    Market breadth timing strategy using MA-above ratio and volume shrinkage.

    Buy when breadth improves + volume shrinks (bottom signal).
    Sell when breadth deteriorates + volume expands (top signal).
    """

    def __init__(
        self,
        ma_breadth_period: int = 10,
        ma_breadth_slow: int = 30,
        vol_short_period: int = 5,
        vol_long_period: int = 20,
        vol_shrink_threshold: float = 0.8,
        vol_expand_threshold: float = 1.2,
        breadth_buy_threshold: float = 0.5,
        target_code: str = "510300",
    ):
        super().__init__(name="BreadthTiming")
        self.ma_breadth_period = ma_breadth_period
        self.ma_breadth_slow = ma_breadth_slow
        self.vol_short_period = vol_short_period
        self.vol_long_period = vol_long_period
        self.vol_shrink_threshold = vol_shrink_threshold
        self.vol_expand_threshold = vol_expand_threshold
        self.breadth_buy_threshold = breadth_buy_threshold
        self.target_code = target_code

        self._breadth_factor = AboveMARatioFactor()
        self._volume_factor = VolumeShrinkageFactor()
        self._position = 0.0
        self._breadth_history: list[float] = []
        self._vol_ratio_history: list[float] = []

    def initialize(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().initialize(params)
        self._position = 0.0
        self._breadth_history = []
        self._vol_ratio_history = []

    def get_target_positions(
        self,
        trade_date: date,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> Dict[str, float]:
        """
        Generate target positions based on breadth and volume signals.

        Parameters:
            trade_date: Current trading date
            data: Market data with columns: close, volume
                  For breadth, expects MultiIndex (date, code) with close
            portfolio: Current portfolio state

        Returns:
            Dict mapping target_code to weight (0.0 or 1.0)
        """
        signal = self._compute_signal(data)

        if signal == 1 and self._position == 0:
            self._position = 1.0
        elif signal == -1 and self._position > 0:
            self._position = 0.0

        if self._position > 0:
            return {self.target_code: 1.0}
        return {}

    def _compute_signal(self, data: pd.DataFrame) -> int:
        """
        Compute timing signal from breadth and volume.

        Returns:
            1 = buy, -1 = sell, 0 = hold
        """
        breadth_result = self._breadth_factor.calculate(
            data, period=self.ma_breadth_period
        )
        vol_result = self._volume_factor.calculate(
            data,
            short_period=self.vol_short_period,
            long_period=self.vol_long_period,
        )

        if breadth_result.is_empty() or vol_result.is_empty():
            return 0

        breadth_values = breadth_result.values
        vol_ratio = vol_result.values

        if isinstance(breadth_values, pd.Series):
            breadth_series = breadth_values
        else:
            breadth_series = breadth_values.iloc[:, 0]

        if len(breadth_series) < self.ma_breadth_slow + 5:
            return 0

        breadth_ma_fast = breadth_series.rolling(
            window=self.ma_breadth_period, min_periods=self.ma_breadth_period
        ).mean()
        breadth_ma_slow = breadth_series.rolling(
            window=self.ma_breadth_slow, min_periods=self.ma_breadth_slow
        ).mean()

        latest_breadth = breadth_series.iloc[-1]
        latest_fast = breadth_ma_fast.iloc[-1]
        latest_slow = breadth_ma_slow.iloc[-1]
        prev_fast = breadth_ma_fast.iloc[-2]
        prev_slow = breadth_ma_slow.iloc[-2]

        if isinstance(vol_ratio, pd.Series):
            latest_vol_ratio = vol_ratio.iloc[-1]
        else:
            latest_vol_ratio = vol_ratio.iloc[-1, 0] if len(vol_ratio) > 0 else 1.0

        if np.isnan(latest_vol_ratio):
            latest_vol_ratio = 1.0

        golden_cross = prev_fast <= prev_slow and latest_fast > latest_slow
        death_cross = prev_fast >= prev_slow and latest_fast < latest_slow

        volume_shrink = latest_vol_ratio < self.vol_shrink_threshold
        volume_expand = latest_vol_ratio > self.vol_expand_threshold
        breadth_ok = latest_breadth > self.breadth_buy_threshold

        if golden_cross and volume_shrink and breadth_ok:
            return 1
        elif death_cross and volume_expand:
            return -1

        if latest_fast > latest_slow and breadth_ok:
            return 1
        elif latest_fast < latest_slow and latest_breadth < 0.4:
            return -1

        return 0

    def get_params(self) -> Dict[str, Any]:
        return {
            "ma_breadth_period": self.ma_breadth_period,
            "ma_breadth_slow": self.ma_breadth_slow,
            "vol_short_period": self.vol_short_period,
            "vol_long_period": self.vol_long_period,
            "vol_shrink_threshold": self.vol_shrink_threshold,
            "vol_expand_threshold": self.vol_expand_threshold,
            "breadth_buy_threshold": self.breadth_buy_threshold,
            "target_code": self.target_code,
        }


def run_example():
    """Run a simple example with synthetic data."""
    np.random.seed(42)
    n_days = 500

    dates = pd.bdate_range("2022-01-01", periods=n_days)
    codes = [f"stock_{i:04d}" for i in range(100)]

    rows = []
    for i, dt in enumerate(dates):
        breadth_base = 0.5 + 0.3 * np.sin(i / 60)
        for code in codes:
            ret = np.random.normal(0.0003, 0.02)
            close = 10 * (1 + ret)
            volume = np.random.exponential(1e6) * (1 + 0.5 * np.sin(i / 30))
            rows.append(
                {
                    "date": dt,
                    "code": code,
                    "close": close,
                    "volume": volume,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "open": close,
                }
            )

    data = pd.DataFrame(rows).set_index(["date", "code"])

    strategy = BreadthTimingStrategy(
        ma_breadth_period=10,
        ma_breadth_slow=30,
        vol_short_period=5,
        vol_long_period=20,
        vol_shrink_threshold=0.8,
        vol_expand_threshold=1.2,
        target_code="510300",
    )

    portfolio = Portfolio(cash=1_000_000.0)
    params = strategy.get_params()
    print(f"Strategy: {strategy.name}")
    print(f"Parameters: {params}")

    for dt in dates[-20:]:
        bar = data.loc[[dt]] if dt in data.index.get_level_values(0) else None
        if bar is not None and not bar.empty:
            targets = strategy.on_bar(dt.date(), bar, portfolio)
            if targets:
                print(f"  {dt.date()}: targets={targets}")

    print("\nExample completed successfully.")


if __name__ == "__main__":
    run_example()
