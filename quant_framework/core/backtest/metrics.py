"""Performance metrics for evaluating backtest results."""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class PerformanceMetrics:
    """Calculate performance metrics from an equity curve.

    Args:
        equity_curve: DataFrame with 'date' and 'total_value' columns.
        risk_free_rate: Annual risk-free rate (default 0.03 = 3%).
        trading_days: Number of trading days per year (default 252).
    """

    def __init__(
        self,
        equity_curve: pd.DataFrame,
        risk_free_rate: float = 0.03,
        trading_days: int = 252,
    ) -> None:
        self.equity_curve = equity_curve.copy()
        self.risk_free_rate = risk_free_rate
        self.trading_days = trading_days
        self.daily_returns = self._calc_daily_returns()

    def _calc_daily_returns(self) -> pd.Series:
        """Calculate daily returns from equity curve."""
        values = self.equity_curve["total_value"]
        return values.pct_change().dropna()

    def total_return(self) -> float:
        """Total return over the period."""
        values = self.equity_curve["total_value"]
        if len(values) < 2:
            return 0.0
        return (values.iloc[-1] - values.iloc[0]) / values.iloc[0]

    def annualized_return(self) -> float:
        """Annualized return."""
        total = self.total_return()
        n_days = len(self.daily_returns)
        if n_days == 0:
            return 0.0
        return (1 + total) ** (self.trading_days / n_days) - 1

    def volatility(self) -> float:
        """Annualized volatility of daily returns."""
        if len(self.daily_returns) < 2:
            return 0.0
        return self.daily_returns.std() * np.sqrt(self.trading_days)

    def sharpe_ratio(self) -> float:
        """Sharpe ratio (annualized)."""
        vol = self.volatility()
        if vol == 0:
            return 0.0
        return (self.annualized_return() - self.risk_free_rate) / vol

    def max_drawdown(self) -> float:
        """Maximum drawdown (as a positive fraction)."""
        values = self.equity_curve["total_value"]
        running_max = values.cummax()
        drawdown = (values - running_max) / running_max
        return abs(drawdown.min())

    def calmar_ratio(self) -> float:
        """Calmar ratio = annualized return / max drawdown."""
        mdd = self.max_drawdown()
        if mdd == 0:
            return 0.0
        return self.annualized_return() / mdd

    def win_rate(self, trades: Optional[List] = None) -> float:
        """Win rate from trade list if available."""
        if not trades:
            return 0.0
        wins = sum(1 for t in trades if getattr(t, "pnl", 0) > 0)
        return wins / len(trades)

    def profit_factor(self, trades: Optional[List] = None) -> float:
        """Profit factor = gross profit / gross loss."""
        if not trades:
            return 0.0
        gross_profit = sum(max(getattr(t, "pnl", 0), 0) for t in trades)
        gross_loss = abs(sum(min(getattr(t, "pnl", 0), 0) for t in trades))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    def all_metrics(self, trades: Optional[List] = None) -> Dict[str, float]:
        """Return all metrics as a dictionary."""
        return {
            "total_return": self.total_return(),
            "annualized_return": self.annualized_return(),
            "volatility": self.volatility(),
            "sharpe_ratio": self.sharpe_ratio(),
            "max_drawdown": self.max_drawdown(),
            "calmar_ratio": self.calmar_ratio(),
            "win_rate": self.win_rate(trades),
            "profit_factor": self.profit_factor(trades),
        }
