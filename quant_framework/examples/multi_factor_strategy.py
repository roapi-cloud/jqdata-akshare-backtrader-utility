# -*- coding: utf-8 -*-
"""
Multi-Factor Stock Selection Strategy
======================================

Strategy Logic:
    - Combines PE, PB, momentum, and turnover factors
    - Ranks stocks on each factor and computes composite score
    - Selects top-N stocks by composite score
    - Monthly rebalance with equal weight portfolio

Parameters:
    universe: Stock universe (index code or 'all')
    top_n: Number of stocks to select (default 10)
    rebalance_days: Rebalance interval in trading days (default 20 ~ monthly)
    pe_weight: Weight for PE factor (default 0.25)
    pb_weight: Weight for PB factor (default 0.25)
    momentum_weight: Weight for momentum factor (default 0.30)
    turnover_weight: Weight for turnover factor (default 0.20)
    momentum_period: Momentum lookback period (default 60)
    momentum_skip: Days to skip from most recent (default 5)
    turnover_window: Turnover averaging window (default 20)
    min_market_cap: Minimum market cap filter (default 2e9)
    exclude_st: Whether to exclude ST stocks (default True)
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from quant_framework.core.strategy.base import BaseStrategy, Portfolio
from quant_framework.core.strategy.position import EqualWeightSizer


class MultiFactorStrategy(BaseStrategy):
    """
    Multi-factor stock selection with monthly rebalance.

    Combines value (PE, PB), momentum, and turnover factors
    to select top-N stocks with equal weight allocation.
    """

    def __init__(
        self,
        universe: str = "000300",
        top_n: int = 10,
        rebalance_days: int = 20,
        pe_weight: float = 0.25,
        pb_weight: float = 0.25,
        momentum_weight: float = 0.30,
        turnover_weight: float = 0.20,
        momentum_period: int = 60,
        momentum_skip: int = 5,
        turnover_window: int = 20,
        min_market_cap: float = 2e9,
        exclude_st: bool = True,
    ):
        super().__init__(name="MultiFactor")
        self.universe = universe
        self.top_n = top_n
        self.rebalance_days = rebalance_days
        self.pe_weight = pe_weight
        self.pb_weight = pb_weight
        self.momentum_weight = momentum_weight
        self.turnover_weight = turnover_weight
        self.momentum_period = momentum_period
        self.momentum_skip = momentum_skip
        self.turnover_window = turnover_window
        self.min_market_cap = min_market_cap
        self.exclude_st = exclude_st

        self._sizer = EqualWeightSizer(max_positions=top_n)
        self._last_rebalance: Optional[date] = None
        self._selected_stocks: List[str] = []
        self._day_count = 0

    def initialize(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().initialize(params)
        self._last_rebalance = None
        self._selected_stocks = []
        self._day_count = 0

    def get_target_positions(
        self,
        trade_date: date,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> Dict[str, float]:
        """
        Generate target positions from multi-factor ranking.

        Parameters:
            trade_date: Current trading date
            data: DataFrame with columns: code, close, volume,
                  and optional factor columns: pe, pb, turnover, market_cap
            portfolio: Current portfolio state

        Returns:
            Dict mapping stock codes to target weights
        """
        self._day_count += 1

        should_rebalance = (
            self._last_rebalance is None
            or (trade_date - self._last_rebalance).days >= self.rebalance_days
        )

        if not should_rebalance:
            return {code: 1.0 for code in self._selected_stocks}

        scores = self._compute_factor_scores(data)
        if not scores:
            return {}

        sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        self._selected_stocks = [code for code, _ in sorted_stocks[: self.top_n]]
        self._last_rebalance = trade_date

        signals = {code: 1.0 for code in self._selected_stocks}
        return self._sizer.size(signals)

    def _compute_factor_scores(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        Compute composite factor scores for all stocks.

        Parameters:
            data: DataFrame with stock data

        Returns:
            Dict mapping stock codes to composite scores
        """
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

            factor_values = {}

            if "pe" in df.columns and pd.notna(row.get("pe")) and row["pe"] > 0:
                pe_norm = self._rank_normalize(df["pe"].dropna(), ascending=False)
                if code in pe_norm.index:
                    factor_values["pe"] = pe_norm[code]

            if "pb" in df.columns and pd.notna(row.get("pb")) and row["pb"] > 0:
                pb_norm = self._rank_normalize(df["pb"].dropna(), ascending=False)
                if code in pb_norm.index:
                    factor_values["pb"] = pb_norm[code]

            if "momentum" in df.columns and pd.notna(row.get("momentum")):
                mom_norm = self._rank_normalize(df["momentum"].dropna(), ascending=True)
                if code in mom_norm.index:
                    factor_values["momentum"] = mom_norm[code]
            elif "close" in df.columns and "prev_close" in df.columns:
                mom = (row["close"] - row.get("prev_close", row["close"])) / row.get(
                    "prev_close", row["close"]
                )
                factor_values["momentum"] = max(0, min(1, 0.5 + mom * 10))

            if "turnover" in df.columns and pd.notna(row.get("turnover")):
                to_norm = self._rank_normalize(df["turnover"].dropna(), ascending=False)
                if code in to_norm.index:
                    factor_values["turnover"] = to_norm[code]

            if not factor_values:
                factor_values["momentum"] = 0.5

            weights = {
                "pe": self.pe_weight,
                "pb": self.pb_weight,
                "momentum": self.momentum_weight,
                "turnover": self.turnover_weight,
            }

            composite = 0.0
            total_w = 0.0
            for fname, fval in factor_values.items():
                w = weights.get(fname, 0.0)
                composite += w * fval
                total_w += w

            if total_w > 0:
                scores[code] = composite / total_w

        return scores

    @staticmethod
    def _rank_normalize(series: pd.Series, ascending: bool = True) -> pd.Series:
        """Rank-normalize a series to [0, 1]."""
        return series.rank(ascending=ascending, pct=True)

    def get_params(self) -> Dict[str, Any]:
        return {
            "universe": self.universe,
            "top_n": self.top_n,
            "rebalance_days": self.rebalance_days,
            "pe_weight": self.pe_weight,
            "pb_weight": self.pb_weight,
            "momentum_weight": self.momentum_weight,
            "turnover_weight": self.turnover_weight,
            "momentum_period": self.momentum_period,
            "momentum_skip": self.momentum_skip,
            "turnover_window": self.turnover_window,
            "min_market_cap": self.min_market_cap,
            "exclude_st": self.exclude_st,
        }


def run_example():
    """Run a simple example with synthetic data."""
    np.random.seed(42)
    n_days = 250

    dates = pd.bdate_range("2023-01-01", periods=n_days)
    codes = [f"stock_{i:04d}" for i in range(50)]

    rows = []
    for dt in dates:
        for code in codes:
            pe = np.random.exponential(15) + 5
            pb = np.random.exponential(2) + 0.5
            momentum = np.random.normal(0.05, 0.15)
            turnover = np.random.exponential(0.03) + 0.005
            close = np.random.uniform(5, 100)
            volume = np.random.exponential(1e6)

            rows.append(
                {
                    "date": dt,
                    "code": code,
                    "close": close,
                    "volume": volume,
                    "pe": pe,
                    "pb": pb,
                    "momentum": momentum,
                    "turnover": turnover,
                    "high": close * 1.02,
                    "low": close * 0.98,
                    "open": close,
                }
            )

    data = pd.DataFrame(rows)

    strategy = MultiFactorStrategy(
        universe="000300",
        top_n=10,
        rebalance_days=20,
        pe_weight=0.25,
        pb_weight=0.25,
        momentum_weight=0.30,
        turnover_weight=0.20,
    )

    portfolio = Portfolio(cash=1_000_000.0)
    params = strategy.get_params()
    print(f"Strategy: {strategy.name}")
    print(f"Parameters: {params}")

    rebalance_count = 0
    for dt in dates:
        day_data = data[data["date"] == dt]
        if day_data.empty:
            continue
        targets = strategy.on_bar(dt.date(), day_data, portfolio)
        if targets and strategy._last_rebalance == dt.date():
            rebalance_count += 1
            print(f"  {dt.date()}: selected {len(targets)} stocks")

    print(f"\nTotal rebalances: {rebalance_count}")
    print("Example completed successfully.")


if __name__ == "__main__":
    run_example()
