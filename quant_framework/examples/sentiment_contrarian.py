# -*- coding: utf-8 -*-
"""
Sentiment Contrarian Strategy
==============================

Strategy Logic:
    - Buy when market sentiment is extremely pessimistic (contrarian buy at bottom)
    - Sell when market sentiment is extremely optimistic (contrarian sell at top)
    - Uses GSISI (Guosen Sentiment Index) + turnover rate as sentiment proxies
    - Sentiment extremes are identified via Z-Score over a lookback window

Parameters:
    gsis_lookback: Lookback window for GSISI Z-Score (default 250)
    turnover_lookback: Lookback window for turnover Z-Score (default 250)
    extreme_low_threshold: Z-Score threshold for extreme pessimism (default -1.5)
    extreme_high_threshold: Z-Score threshold for extreme optimism (default 1.5)
    gsis_weight: Weight for GSISI in composite sentiment (default 0.6)
    turnover_weight: Weight for turnover in composite sentiment (default 0.4)
    target_code: Target ETF code (default '510300')
    cooldown_days: Minimum days between signals (default 10)
"""

from datetime import date
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from quant_framework.core.strategy.base import BaseStrategy, Portfolio
from quant_framework.core.factors.sentiment import GSISIFactor, TurnoverSentimentFactor


class SentimentContrarianStrategy(BaseStrategy):
    """
    Contrarian strategy based on market sentiment extremes.

    Buys when sentiment is extremely pessimistic,
    sells when sentiment is extremely optimistic.
    """

    def __init__(
        self,
        gsis_lookback: int = 250,
        turnover_lookback: int = 250,
        extreme_low_threshold: float = -1.5,
        extreme_high_threshold: float = 1.5,
        gsis_weight: float = 0.6,
        turnover_weight: float = 0.4,
        target_code: str = "510300",
        cooldown_days: int = 10,
    ):
        super().__init__(name="SentimentContrarian")
        self.gsis_lookback = gsis_lookback
        self.turnover_lookback = turnover_lookback
        self.extreme_low_threshold = extreme_low_threshold
        self.extreme_high_threshold = extreme_high_threshold
        self.gsis_weight = gsis_weight
        self.turnover_weight = turnover_weight
        self.target_code = target_code
        self.cooldown_days = cooldown_days

        self._gsis_factor = GSISIFactor()
        self._turnover_factor = TurnoverSentimentFactor()
        self._position = 0.0
        self._last_signal_date: Optional[date] = None
        self._sentiment_history: list[float] = []

    def initialize(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().initialize(params)
        self._position = 0.0
        self._last_signal_date = None
        self._sentiment_history = []

    def get_target_positions(
        self,
        trade_date: date,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> Dict[str, float]:
        """
        Generate target positions based on contrarian sentiment signals.

        Parameters:
            trade_date: Current trading date
            data: DataFrame with columns: close, volume, turnover
            portfolio: Current portfolio state

        Returns:
            Dict mapping target_code to weight (0.0 or 1.0)
        """
        if self._last_signal_date is not None:
            days_since = (trade_date - self._last_signal_date).days
            if days_since < self.cooldown_days:
                if self._position > 0:
                    return {self.target_code: 1.0}
                return {}

        signal, sentiment = self._compute_sentiment_signal(data)

        if signal == 1:
            self._position = 1.0
            self._last_signal_date = trade_date
        elif signal == -1:
            self._position = 0.0
            self._last_signal_date = trade_date

        if self._position > 0:
            return {self.target_code: 1.0}
        return {}

    def _compute_sentiment_signal(self, data: pd.DataFrame) -> tuple[int, float]:
        """
        Compute contrarian signal from composite sentiment.

        Parameters:
            data: DataFrame with close, volume, turnover columns

        Returns:
            Tuple of (signal, sentiment_score)
            signal: 1 = buy (extreme pessimism), -1 = sell (extreme optimism), 0 = hold
            sentiment_score: Composite sentiment Z-Score
        """
        gsis_z = self._compute_gsis_z(data)
        turnover_z = self._compute_turnover_z(data)

        if np.isnan(gsis_z) and np.isnan(turnover_z):
            return 0, 0.0

        weights_sum = 0.0
        composite = 0.0

        if not np.isnan(gsis_z):
            composite += self.gsis_weight * gsis_z
            weights_sum += self.gsis_weight

        if not np.isnan(turnover_z):
            composite += self.turnover_weight * turnover_z
            weights_sum += self.turnover_weight

        if weights_sum > 0:
            sentiment_score = composite / weights_sum
        else:
            sentiment_score = 0.0

        self._sentiment_history.append(sentiment_score)

        if sentiment_score < self.extreme_low_threshold:
            return 1, sentiment_score
        elif sentiment_score > self.extreme_high_threshold:
            return -1, sentiment_score

        return 0, sentiment_score

    def _compute_gsis_z(self, data: pd.DataFrame) -> float:
        """Compute GSISI Z-Score."""
        required = {"close", "volume", "turnover"}
        if not required.issubset(set(data.columns)):
            return np.nan

        result = self._gsis_factor.calculate(
            data,
            short_period=5,
            long_period=20,
            vol_lookback=self.gsis_lookback,
        )

        if result.is_empty():
            return np.nan

        values = result.values
        if isinstance(values, pd.Series):
            gsi = values.iloc[-1]
        else:
            gsi = values.iloc[-1, 0]

        if np.isnan(gsi):
            return np.nan

        if len(values) < self.gsis_lookback:
            return gsi

        recent = values.iloc[-self.gsis_lookback :]
        mean = recent.mean()
        std = recent.std()

        if std == 0 or np.isnan(std):
            return 0.0

        return (gsi - mean) / std

    def _compute_turnover_z(self, data: pd.DataFrame) -> float:
        """Compute turnover rate Z-Score."""
        if "turnover" not in data.columns:
            return np.nan

        result = self._turnover_factor.calculate(data, lookback=self.turnover_lookback)

        if result.is_empty():
            return np.nan

        values = result.values
        if isinstance(values, pd.Series):
            z = values.iloc[-1]
        else:
            z = values.iloc[-1, 0]

        return z if not np.isnan(z) else np.nan

    def get_params(self) -> Dict[str, Any]:
        return {
            "gsis_lookback": self.gsis_lookback,
            "turnover_lookback": self.turnover_lookback,
            "extreme_low_threshold": self.extreme_low_threshold,
            "extreme_high_threshold": self.extreme_high_threshold,
            "gsis_weight": self.gsis_weight,
            "turnover_weight": self.turnover_weight,
            "target_code": self.target_code,
            "cooldown_days": self.cooldown_days,
        }


def run_example():
    """Run a simple example with synthetic data."""
    np.random.seed(42)
    n_days = 500

    dates = pd.bdate_range("2022-01-01", periods=n_days)

    close = 100 * np.cumprod(1 + np.random.normal(0.0002, 0.015, n_days))
    volume = np.random.exponential(1e7, n_days) * (
        1 + 0.5 * np.sin(np.arange(n_days) / 50)
    )
    turnover = volume / 1e9 * 100

    data = pd.DataFrame(
        {
            "close": close,
            "volume": volume,
            "turnover": turnover,
            "high": close * 1.01,
            "low": close * 0.99,
            "open": close,
        },
        index=dates,
    )

    strategy = SentimentContrarianStrategy(
        gsis_lookback=250,
        turnover_lookback=250,
        extreme_low_threshold=-1.5,
        extreme_high_threshold=1.5,
        gsis_weight=0.6,
        turnover_weight=0.4,
        target_code="510300",
        cooldown_days=10,
    )

    portfolio = Portfolio(cash=1_000_000.0)
    params = strategy.get_params()
    print(f"Strategy: {strategy.name}")
    print(f"Parameters: {params}")

    signal_dates = []
    for dt in dates:
        bar = data.loc[[dt]]
        targets = strategy.on_bar(dt.date(), bar, portfolio)
        if targets and (not signal_dates or dt.date() != signal_dates[-1][0]):
            signal_dates.append((dt.date(), "BUY" if targets else "SELL"))
            print(
                f"  {dt.date()}: BUY signal, sentiment={strategy._sentiment_history[-1]:.4f}"
            )
        elif (
            not targets
            and strategy._position == 0
            and strategy._last_signal_date == dt.date()
        ):
            signal_dates.append((dt.date(), "SELL"))
            print(
                f"  {dt.date()}: SELL signal, sentiment={strategy._sentiment_history[-1]:.4f}"
            )

    print(f"\nTotal signals: {len(signal_dates)}")
    print(f"Sentiment scores recorded: {len(strategy._sentiment_history)}")
    print("Example completed successfully.")


if __name__ == "__main__":
    run_example()
