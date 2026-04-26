# -*- coding: utf-8 -*-
"""
RSRS (Resistance Support Relative Strength) Timing Strategy
============================================================

Strategy Logic:
    - Uses passive RSRS indicator for market timing
    - Computes N-day high-low regression slope and its Z-Score
    - RSRS score = Z-Score x R-squared
    - Buy when RSRS score exceeds buy_threshold
    - Sell when RSRS score falls below sell_threshold
    - Applied to index ETF (CSI 300 ETF: 510300)

Parameters:
    N: Regression window for high-low slope (default 18)
    M: Z-Score lookback window (default 600)
    buy_threshold: RSRS score buy threshold (default 0.7)
    sell_threshold: RSRS score sell threshold (default -0.7)
    target_code: Target ETF code (default '510300')
    use_r2_weight: Whether to weight by R-squared (default True)
"""

from datetime import date
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from quant_framework.core.strategy.base import BaseStrategy, Portfolio


class RSRSTimingStrategy(BaseStrategy):
    """
    RSRS timing strategy for index ETF trading.

    Uses high-low regression slope Z-Score to identify
    support/resistance strength shifts for buy/sell signals.
    """

    def __init__(
        self,
        N: int = 18,
        M: int = 600,
        buy_threshold: float = 0.7,
        sell_threshold: float = -0.7,
        target_code: str = "510300",
        use_r2_weight: bool = True,
    ):
        super().__init__(name="RSRS-Timing")
        self.N = N
        self.M = M
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.target_code = target_code
        self.use_r2_weight = use_r2_weight

        self._position = 0.0
        self._rsrs_scores: list[float] = []
        self._slopes: list[float] = []
        self._r2_values: list[float] = []

    def initialize(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().initialize(params)
        self._position = 0.0
        self._rsrs_scores = []
        self._slopes = []
        self._r2_values = []

    def get_target_positions(
        self,
        trade_date: date,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> Dict[str, float]:
        """
        Generate target position based on RSRS signal.

        Parameters:
            trade_date: Current trading date
            data: DataFrame with columns: high, low, close
            portfolio: Current portfolio state

        Returns:
            Dict mapping target_code to weight (0.0 or 1.0)
        """
        signal = self._compute_rsrs_signal(data)

        if signal == 1:
            self._position = 1.0
        elif signal == -1:
            self._position = 0.0

        if self._position > 0:
            return {self.target_code: 1.0}
        return {}

    def _compute_rsrs_signal(self, data: pd.DataFrame) -> int:
        """
        Compute RSRS timing signal.

        Parameters:
            data: DataFrame with high, low columns

        Returns:
            1 = buy, -1 = sell, 0 = hold
        """
        if "high" not in data.columns or "low" not in data.columns:
            return 0

        high = data["high"].astype(float)
        low = data["low"].astype(float)

        if len(high) < self.N + 10:
            return 0

        slopes, r2_values = self._compute_slope_r2(low, high, self.N)

        if len(slopes) < self.M:
            return 0

        valid_slopes = slopes.dropna()
        if len(valid_slopes) < self.M:
            return 0

        latest_slope = valid_slopes.iloc[-1]
        slope_mean = valid_slopes.iloc[-self.M :].mean()
        slope_std = valid_slopes.iloc[-self.M :].std()

        if slope_std == 0 or np.isnan(slope_std):
            return 0

        z_score = (latest_slope - slope_mean) / slope_std
        latest_r2 = r2_values.iloc[-1]

        if self.use_r2_weight and not np.isnan(latest_r2):
            rsrs_score = z_score * latest_r2
        else:
            rsrs_score = z_score

        self._rsrs_scores.append(rsrs_score)
        self._slopes.append(latest_slope)
        self._r2_values.append(latest_r2)

        if rsrs_score > self.buy_threshold:
            return 1
        elif rsrs_score < self.sell_threshold:
            return -1

        return 0

    @staticmethod
    def _compute_slope_r2(
        low: pd.Series, high: pd.Series, window: int
    ) -> tuple[pd.Series, pd.Series]:
        """
        Compute rolling OLS slope and R-squared of high ~ low.

        Parameters:
            low: Low price series
            high: High price series
            window: Rolling window size

        Returns:
            Tuple of (slopes, r2_values) as Series
        """
        slopes = []
        r2_values = []
        x = np.arange(window)

        for i in range(len(low)):
            if i < window - 1:
                slopes.append(np.nan)
                r2_values.append(np.nan)
                continue

            y = high.iloc[i - window + 1 : i + 1].values
            x_win = low.iloc[i - window + 1 : i + 1].values

            coeffs = np.polyfit(x_win, y, 1)
            slope = coeffs[0]
            intercept = coeffs[1]

            y_pred = slope * x_win + intercept
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

            slopes.append(slope)
            r2_values.append(r2)

        return pd.Series(slopes, index=low.index), pd.Series(r2_values, index=low.index)

    def get_params(self) -> Dict[str, Any]:
        return {
            "N": self.N,
            "M": self.M,
            "buy_threshold": self.buy_threshold,
            "sell_threshold": self.sell_threshold,
            "target_code": self.target_code,
            "use_r2_weight": self.use_r2_weight,
        }


def run_example():
    """Run a simple example with synthetic data."""
    np.random.seed(42)
    n_days = 700

    dates = pd.bdate_range("2021-01-01", periods=n_days)

    close = 100 * np.cumprod(1 + np.random.normal(0.0003, 0.015, n_days))
    high = close * (1 + np.abs(np.random.normal(0, 0.008, n_days)))
    low = close * (1 - np.abs(np.random.normal(0, 0.008, n_days)))
    volume = np.random.exponential(1e7, n_days)

    data = pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )

    strategy = RSRSTimingStrategy(
        N=18,
        M=600,
        buy_threshold=0.7,
        sell_threshold=-0.7,
        target_code="510300",
        use_r2_weight=True,
    )

    portfolio = Portfolio(cash=1_000_000.0)
    params = strategy.get_params()
    print(f"Strategy: {strategy.name}")
    print(f"Parameters: {params}")

    buy_count = 0
    sell_count = 0
    for dt in dates:
        bar = data.loc[[dt]]
        targets = strategy.on_bar(dt.date(), bar, portfolio)
        if targets:
            buy_count += 1
        elif strategy._position == 0 and dt > dates[100]:
            sell_count += 1

    print(f"\nBuy signals: {buy_count}")
    print(f"RSRS scores recorded: {len(strategy._rsrs_scores)}")
    if strategy._rsrs_scores:
        print(f"Latest RSRS score: {strategy._rsrs_scores[-1]:.4f}")
    print("Example completed successfully.")


if __name__ == "__main__":
    run_example()
