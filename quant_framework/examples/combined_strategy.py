# -*- coding: utf-8 -*-
"""
Combined Strategy: Timing + Factor + Volatility Position Sizing
===============================================================

Strategy Logic:
    1. Timing signal: Uses RSRS or breadth to determine market exposure (0% or 100%)
    2. Factor signal: Multi-factor ranking selects top-N stocks
    3. Position sizing: Volatility-targeted sizing adjusts individual weights

    Flow:
        timing_signal -> market_on/off
        factor_signal -> stock selection
        volatility    -> position sizing

Parameters:
    --- Timing Parameters ---
    timing_method: Timing method ('rsrs' or 'breadth')
    rsrs_N: RSRS regression window (default 18)
    rsrs_M: RSRS Z-Score lookback (default 600)
    rsrs_buy_threshold: RSRS buy threshold (default 0.7)
    rsrs_sell_threshold: RSRS sell threshold (default -0.7)
    breadth_ma_fast: Breadth fast MA period (default 10)
    breadth_ma_slow: Breadth slow MA period (default 30)

    --- Factor Parameters ---
    top_n: Number of stocks to select (default 10)
    rebalance_days: Rebalance interval (default 20)
    momentum_period: Momentum lookback (default 60)
    momentum_skip: Momentum skip days (default 5)

    --- Position Sizing Parameters ---
    target_volatility: Target annualized portfolio volatility (default 0.15)
    vol_lookback: Volatility estimation lookback (default 60)
    max_single_weight: Maximum weight for any single stock (default 0.15)
    cash_reserve: Cash reserve fraction (default 0.0)
"""

from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from quant_framework.core.strategy.base import BaseStrategy, Portfolio
from quant_framework.core.strategy.position import VolatilityTargetSizer


class CombinedStrategy(BaseStrategy):
    """
    Combined strategy integrating timing, factor selection, and volatility sizing.

    Uses a timing signal to control overall market exposure,
    multi-factor ranking for stock selection, and
    volatility-targeted position sizing for risk management.
    """

    def __init__(
        self,
        timing_method: str = "rsrs",
        rsrs_N: int = 18,
        rsrs_M: int = 600,
        rsrs_buy_threshold: float = 0.7,
        rsrs_sell_threshold: float = -0.7,
        breadth_ma_fast: int = 10,
        breadth_ma_slow: int = 30,
        top_n: int = 10,
        rebalance_days: int = 20,
        momentum_period: int = 60,
        momentum_skip: int = 5,
        target_volatility: float = 0.15,
        vol_lookback: int = 60,
        max_single_weight: float = 0.15,
        cash_reserve: float = 0.0,
    ):
        super().__init__(name="Combined")
        self.timing_method = timing_method
        self.rsrs_N = rsrs_N
        self.rsrs_M = rsrs_M
        self.rsrs_buy_threshold = rsrs_buy_threshold
        self.rsrs_sell_threshold = rsrs_sell_threshold
        self.breadth_ma_fast = breadth_ma_fast
        self.breadth_ma_slow = breadth_ma_slow
        self.top_n = top_n
        self.rebalance_days = rebalance_days
        self.momentum_period = momentum_period
        self.momentum_skip = momentum_skip
        self.target_volatility = target_volatility
        self.vol_lookback = vol_lookback
        self.max_single_weight = max_single_weight
        self.cash_reserve = cash_reserve

        self._sizer = VolatilityTargetSizer(
            max_weight=max_single_weight,
            target_volatility=target_volatility,
            lookback=vol_lookback,
            cash_reserve=cash_reserve,
        )
        self._market_on = True
        self._selected_stocks: List[str] = []
        self._last_rebalance: Optional[date] = None
        self._day_count = 0
        self._price_history: Dict[str, List[float]] = {}

    def initialize(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().initialize(params)
        self._market_on = True
        self._selected_stocks = []
        self._last_rebalance = None
        self._day_count = 0
        self._price_history = {}

    def get_target_positions(
        self,
        trade_date: date,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> Dict[str, float]:
        """
        Generate target positions using timing + factor + volatility sizing.

        Parameters:
            trade_date: Current trading date
            data: DataFrame with OHLCV data and optional factor columns
            portfolio: Current portfolio state

        Returns:
            Dict mapping stock codes to target weights
        """
        self._day_count += 1

        market_signal = self._compute_timing_signal(data)
        if market_signal == -1:
            self._market_on = False
        elif market_signal == 1:
            self._market_on = True

        if not self._market_on:
            return {}

        should_rebalance = (
            self._last_rebalance is None
            or (trade_date - self._last_rebalance).days >= self.rebalance_days
        )

        if should_rebalance:
            scores = self._compute_factor_scores(data)
            if scores:
                sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                self._selected_stocks = [
                    code for code, _ in sorted_stocks[: self.top_n]
                ]
                self._last_rebalance = trade_date

        self._update_price_history(data)

        if not self._selected_stocks:
            return {}

        signals = {code: 1.0 for code in self._selected_stocks}

        returns_hist = self._build_returns_history()
        weights = self._sizer.size(signals, returns_history=returns_hist)

        return weights

    def _compute_timing_signal(self, data: pd.DataFrame) -> int:
        """
        Compute market timing signal.

        Returns:
            1 = bullish (market on), -1 = bearish (market off), 0 = hold
        """
        if self.timing_method == "rsrs":
            return self._rsrs_signal(data)
        elif self.timing_method == "breadth":
            return self._breadth_signal(data)
        return 0

    def _rsrs_signal(self, data: pd.DataFrame) -> int:
        """RSRS-based timing signal."""
        if "high" not in data.columns or "low" not in data.columns:
            return 0

        high = data["high"].astype(float)
        low = data["low"].astype(float)

        if len(high) < self.rsrs_N + 10:
            return 0

        slopes, r2_values = self._compute_slope_r2(low, high, self.rsrs_N)

        valid_slopes = slopes.dropna()
        if len(valid_slopes) < self.rsrs_M:
            return 0

        latest_slope = valid_slopes.iloc[-1]
        slope_mean = valid_slopes.iloc[-self.rsrs_M :].mean()
        slope_std = valid_slopes.iloc[-self.rsrs_M :].std()

        if slope_std == 0 or np.isnan(slope_std):
            return 0

        z_score = (latest_slope - slope_mean) / slope_std
        latest_r2 = r2_values.iloc[-1]

        if not np.isnan(latest_r2):
            rsrs_score = z_score * latest_r2
        else:
            rsrs_score = z_score

        if rsrs_score > self.rsrs_buy_threshold:
            return 1
        elif rsrs_score < self.rsrs_sell_threshold:
            return -1

        return 0

    def _breadth_signal(self, data: pd.DataFrame) -> int:
        """Breadth-based timing signal."""
        if "close" not in data.columns:
            return 0

        close = data["close"].astype(float)
        if len(close) < self.breadth_ma_slow + 5:
            return 0

        ma_fast = close.rolling(
            window=self.breadth_ma_fast, min_periods=self.breadth_ma_fast
        ).mean()
        ma_slow = close.rolling(
            window=self.breadth_ma_slow, min_periods=self.breadth_ma_slow
        ).mean()

        if len(ma_fast) < 2:
            return 0

        prev_fast = ma_fast.iloc[-2]
        prev_slow = ma_slow.iloc[-2]
        curr_fast = ma_fast.iloc[-1]
        curr_slow = ma_slow.iloc[-1]

        golden = prev_fast <= prev_slow and curr_fast > curr_slow
        death = prev_fast >= prev_slow and curr_fast < curr_slow

        if golden:
            return 1
        elif death:
            return -1

        if curr_fast > curr_slow:
            return 1
        return -1

    @staticmethod
    def _compute_slope_r2(
        low: pd.Series, high: pd.Series, window: int
    ) -> tuple[pd.Series, pd.Series]:
        """Compute rolling OLS slope and R-squared of high ~ low."""
        slopes = []
        r2_values = []

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

    def _compute_factor_scores(self, data: pd.DataFrame) -> Dict[str, float]:
        """Compute composite factor scores for stock selection."""
        if data.empty:
            return {}

        df = data.copy()
        if "date" in df.columns:
            latest_date = df["date"].max()
            df = df[df["date"] == latest_date]

        if "code" not in df.columns:
            return {}

        scores: Dict[str, float] = {}

        for _, row in df.iterrows():
            code = row.get("code")
            if not code:
                continue

            score = 0.0

            if "momentum" in df.columns and pd.notna(row.get("momentum")):
                mom_norm = self._rank_normalize(df["momentum"].dropna(), ascending=True)
                if code in mom_norm.index:
                    score += 0.4 * mom_norm[code]

            if "turnover" in df.columns and pd.notna(row.get("turnover")):
                to_norm = self._rank_normalize(df["turnover"].dropna(), ascending=False)
                if code in to_norm.index:
                    score += 0.3 * to_norm[code]

            if "pe" in df.columns and pd.notna(row.get("pe")) and row["pe"] > 0:
                pe_norm = self._rank_normalize(df["pe"].dropna(), ascending=False)
                if code in pe_norm.index:
                    score += 0.3 * pe_norm[code]

            if score > 0:
                scores[code] = score

        return scores

    @staticmethod
    def _rank_normalize(series: pd.Series, ascending: bool = True) -> pd.Series:
        """Rank-normalize a series to [0, 1]."""
        return series.rank(ascending=ascending, pct=True)

    def _update_price_history(self, data: pd.DataFrame) -> None:
        """Update price history for volatility estimation."""
        if "code" not in data.columns or "close" not in data.columns:
            return

        for _, row in data.iterrows():
            code = row.get("code")
            close = row.get("close")
            if code and pd.notna(close):
                if code not in self._price_history:
                    self._price_history[code] = []
                self._price_history[code].append(float(close))

    def _build_returns_history(self) -> Optional[pd.DataFrame]:
        """Build returns history DataFrame for position sizing."""
        if not self._price_history:
            return None

        max_len = max(len(v) for v in self._price_history.values())
        if max_len < 10:
            return None

        records = {}
        for code, prices in self._price_history.items():
            padded = [np.nan] * (max_len - len(prices)) + prices
            series = pd.Series(padded)
            records[code] = series.pct_change()

        return pd.DataFrame(records).dropna()

    def get_params(self) -> Dict[str, Any]:
        return {
            "timing_method": self.timing_method,
            "rsrs_N": self.rsrs_N,
            "rsrs_M": self.rsrs_M,
            "rsrs_buy_threshold": self.rsrs_buy_threshold,
            "rsrs_sell_threshold": self.rsrs_sell_threshold,
            "breadth_ma_fast": self.breadth_ma_fast,
            "breadth_ma_slow": self.breadth_ma_slow,
            "top_n": self.top_n,
            "rebalance_days": self.rebalance_days,
            "momentum_period": self.momentum_period,
            "momentum_skip": self.momentum_skip,
            "target_volatility": self.target_volatility,
            "vol_lookback": self.vol_lookback,
            "max_single_weight": self.max_single_weight,
            "cash_reserve": self.cash_reserve,
        }


def run_example():
    """Run a simple example with synthetic data."""
    np.random.seed(42)
    n_days = 300

    dates = pd.bdate_range("2023-01-01", periods=n_days)
    codes = [f"stock_{i:04d}" for i in range(30)]

    rows = []
    for dt in dates:
        for code in codes:
            pe = np.random.exponential(15) + 5
            momentum = np.random.normal(0.05, 0.15)
            turnover = np.random.exponential(0.03) + 0.005
            close = np.random.uniform(10, 50)
            volume = np.random.exponential(1e6)

            rows.append(
                {
                    "date": dt,
                    "code": code,
                    "close": close,
                    "volume": volume,
                    "high": close * 1.02,
                    "low": close * 0.98,
                    "open": close,
                    "pe": pe,
                    "momentum": momentum,
                    "turnover": turnover,
                }
            )

    data = pd.DataFrame(rows)

    strategy = CombinedStrategy(
        timing_method="breadth",
        rsrs_N=18,
        rsrs_M=600,
        rsrs_buy_threshold=0.7,
        rsrs_sell_threshold=-0.7,
        breadth_ma_fast=10,
        breadth_ma_slow=30,
        top_n=10,
        rebalance_days=20,
        momentum_period=60,
        momentum_skip=5,
        target_volatility=0.15,
        vol_lookback=60,
        max_single_weight=0.15,
        cash_reserve=0.0,
    )

    portfolio = Portfolio(cash=1_000_000.0)
    params = strategy.get_params()
    print(f"Strategy: {strategy.name}")
    print(f"Parameters: {params}")

    active_days = 0
    rebalance_count = 0
    for dt in dates:
        day_data = data[data["date"] == dt]
        if day_data.empty:
            continue
        targets = strategy.on_bar(dt.date(), day_data, portfolio)
        if targets:
            active_days += 1
        if strategy._last_rebalance == dt.date():
            rebalance_count += 1
            print(
                f"  {dt.date()}: market_on={strategy._market_on}, "
                f"selected={len(targets)} stocks"
            )

    print(f"\nActive days: {active_days}/{n_days}")
    print(f"Rebalances: {rebalance_count}")
    print("Example completed successfully.")


if __name__ == "__main__":
    run_example()
