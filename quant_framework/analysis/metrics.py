"""Comprehensive performance metrics for quantitative strategy evaluation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd


class PerformanceMetrics:
    """Calculate a full suite of performance metrics from an equity curve.

    Args:
        equity_curve: DataFrame with a DatetimeIndex and a ``total_value`` column
                      (or any single numeric column if ``total_value`` is absent).
        benchmark: Optional Series/DataFrame with benchmark values aligned to the
                   same index.  Used for information ratio, alpha, and beta.
        trades: Optional list of trade dicts/objects with at least ``pnl`` and
                ``hold_days`` attributes (or dict keys).
        risk_free_rate: Annual risk-free rate (default 0.03 = 3 %).
        trading_days: Number of trading days per year (default 252).
    """

    def __init__(
        self,
        equity_curve: pd.DataFrame,
        benchmark: Optional[Union[pd.Series, pd.DataFrame]] = None,
        trades: Optional[Sequence[Any]] = None,
        risk_free_rate: float = 0.03,
        trading_days: int = 252,
    ) -> None:
        self.equity_curve = equity_curve.copy()
        self.equity_curve.index = pd.to_datetime(self.equity_curve.index)
        self.equity_curve.sort_index(inplace=True)

        self.benchmark = benchmark
        if self.benchmark is not None:
            if isinstance(self.benchmark, pd.DataFrame):
                self.benchmark = self.benchmark.iloc[:, 0]
            self.benchmark = self.benchmark.copy()
            self.benchmark.index = pd.to_datetime(self.benchmark.index)
            self.benchmark.sort_index(inplace=True)

        self.trades = trades
        self.risk_free_rate = risk_free_rate
        self.trading_days = trading_days

        self._values = self._resolve_values()
        self.daily_returns = self._calc_daily_returns()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_values(self) -> pd.Series:
        """Return the equity Series from the DataFrame."""
        if "total_value" in self.equity_curve.columns:
            return self.equity_curve["total_value"]
        return self.equity_curve.iloc[:, 0]

    def _calc_daily_returns(self) -> pd.Series:
        """Calculate daily percentage returns."""
        return self._values.pct_change().dropna()

    def _benchmark_returns(self) -> pd.Series:
        """Aligned benchmark daily returns."""
        if self.benchmark is None:
            return pd.Series(dtype=float)
        b = self.benchmark.reindex(self._values.index).dropna()
        return b.pct_change().dropna()

    @staticmethod
    def _safe_div(num: float, den: float, default: float = 0.0) -> float:
        """Division with zero-denominator protection."""
        if den == 0 or np.isnan(den) or np.isinf(den):
            return default
        return num / den

    # ------------------------------------------------------------------
    # Return metrics
    # ------------------------------------------------------------------

    def total_return(self) -> float:
        """Total return over the entire period."""
        if len(self._values) < 2:
            return 0.0
        return self._safe_div(
            self._values.iloc[-1] - self._values.iloc[0], self._values.iloc[0]
        )

    def annualized_return(self) -> float:
        """Compound annual growth rate (CAGR)."""
        total = self.total_return()
        n = len(self.daily_returns)
        if n == 0:
            return 0.0
        years = n / self.trading_days
        if years <= 0:
            return 0.0
        return (1 + total) ** (1 / years) - 1

    # ------------------------------------------------------------------
    # Risk metrics
    # ------------------------------------------------------------------

    def volatility(self) -> float:
        """Annualized volatility of daily returns."""
        if len(self.daily_returns) < 2:
            return 0.0
        return float(self.daily_returns.std() * np.sqrt(self.trading_days))

    def downside_deviation(self) -> float:
        """Annualized downside deviation (returns below zero)."""
        if len(self.daily_returns) < 2:
            return 0.0
        negative = self.daily_returns[self.daily_returns < 0]
        if len(negative) == 0:
            return 0.0
        return float(np.sqrt((negative**2).mean()) * np.sqrt(self.trading_days))

    def semi_volatility(self) -> float:
        """Alias for downside_deviation."""
        return self.downside_deviation()

    # ------------------------------------------------------------------
    # Risk-adjusted ratios
    # ------------------------------------------------------------------

    def sharpe_ratio(self) -> float:
        """Annualized Sharpe ratio."""
        vol = self.volatility()
        return self._safe_div(self.annualized_return() - self.risk_free_rate, vol)

    def sortino_ratio(self) -> float:
        """Annualized Sortino ratio (downside deviation in denominator)."""
        dd = self.downside_deviation()
        return self._safe_div(self.annualized_return() - self.risk_free_rate, dd)

    def calmar_ratio(self) -> float:
        """Calmar ratio = annualized return / max drawdown."""
        mdd = self.max_drawdown()
        return self._safe_div(self.annualized_return(), mdd)

    def omega_ratio(self, threshold: float = 0.0) -> float:
        """Omega ratio = sum of gains above threshold / sum of losses below threshold.

        Args:
            threshold: Daily return threshold (default 0).
        """
        if len(self.daily_returns) == 0:
            return 1.0
        gains = self.daily_returns[self.daily_returns > threshold].sum()
        losses = abs(self.daily_returns[self.daily_returns <= threshold].sum())
        return self._safe_div(gains, losses, default=1.0)

    # ------------------------------------------------------------------
    # Drawdown metrics
    # ------------------------------------------------------------------

    def drawdown_series(self) -> pd.Series:
        """Drawdown at each point in time (negative values)."""
        running_max = self._values.cummax()
        return (self._values - running_max) / running_max

    def max_drawdown(self) -> float:
        """Maximum drawdown as a positive fraction."""
        dd = self.drawdown_series()
        if len(dd) == 0:
            return 0.0
        return abs(dd.min())

    def max_drawdown_duration(self) -> int:
        """Longest drawdown duration in trading days."""
        dd = self.drawdown_series()
        if len(dd) == 0:
            return 0
        underwater = dd < 0
        if not underwater.any():
            return 0
        # Count consecutive True values
        groups = (~underwater).cumsum()
        durations = underwater.groupby(groups).sum()
        return int(durations.max())

    def avg_drawdown_duration(self) -> float:
        """Average drawdown duration in trading days."""
        dd = self.drawdown_series()
        if len(dd) == 0:
            return 0.0
        underwater = dd < 0
        if not underwater.any():
            return 0.0
        groups = (~underwater).cumsum()
        durations = underwater.groupby(groups).sum()
        durations = durations[durations > 0]
        if len(durations) == 0:
            return 0.0
        return float(durations.mean())

    # ------------------------------------------------------------------
    # Trade-level metrics
    # ------------------------------------------------------------------

    def _extract_pnl(self) -> List[float]:
        """Extract PnL values from the trade list."""
        if not self.trades:
            return []
        pnls = []
        for t in self.trades:
            if isinstance(t, dict):
                pnls.append(t.get("pnl", 0.0))
            else:
                pnls.append(getattr(t, "pnl", 0.0))
        return pnls

    def win_rate(self) -> float:
        """Fraction of trades that are profitable."""
        pnls = self._extract_pnl()
        if not pnls:
            return 0.0
        wins = sum(1 for p in pnls if p > 0)
        return self._safe_div(wins, len(pnls))

    def loss_rate(self) -> float:
        """Fraction of trades that are losing."""
        return 1 - self.win_rate()

    def profit_loss_ratio(self) -> float:
        """Average profit / average loss (absolute)."""
        pnls = self._extract_pnl()
        if not pnls:
            return 0.0
        profits = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
        avg_profit = np.mean(profits) if profits else 0.0
        avg_loss = np.mean(losses) if losses else 0.0
        return self._safe_div(avg_profit, avg_loss)

    def profit_factor(self) -> float:
        """Gross profit / gross loss."""
        pnls = self._extract_pnl()
        if not pnls:
            return 0.0
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        return self._safe_div(
            gross_profit, gross_loss, default=float("inf") if gross_profit > 0 else 0.0
        )

    def avg_trade_pnl(self) -> float:
        """Average PnL per trade."""
        pnls = self._extract_pnl()
        if not pnls:
            return 0.0
        return float(np.mean(pnls))

    def expectancy(self) -> float:
        """Expected value per trade = win_rate * avg_win - loss_rate * avg_loss."""
        pnls = self._extract_pnl()
        if not pnls:
            return 0.0
        wr = self.win_rate()
        profits = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
        avg_win = np.mean(profits) if profits else 0.0
        avg_loss = np.mean(losses) if losses else 0.0
        return wr * avg_win - (1 - wr) * avg_loss

    # ------------------------------------------------------------------
    # Holding period & turnover
    # ------------------------------------------------------------------

    def _extract_hold_days(self) -> List[float]:
        """Extract holding-period days from trades."""
        if not self.trades:
            return []
        days = []
        for t in self.trades:
            if isinstance(t, dict):
                days.append(t.get("hold_days", 0))
            else:
                days.append(getattr(t, "hold_days", 0))
        return days

    def average_holding_period(self) -> float:
        """Average holding period in trading days."""
        days = self._extract_hold_days()
        if not days:
            return 0.0
        return float(np.mean(days))

    def turnover_rate(self) -> float:
        """Annualized turnover rate.

        Estimated as 2 * min(buy_value, sell_value) / avg_portfolio_value
        over the period, then annualized by trading days.
        """
        if not self.trades or len(self._values) < 2:
            return 0.0
        buy_volume = 0.0
        sell_volume = 0.0
        for t in self.trades:
            if isinstance(t, dict):
                side = t.get("side", "").upper()
                amount = t.get("amount", abs(t.get("pnl", 0)))
            else:
                side = getattr(t, "side", "").upper()
                amount = getattr(t, "amount", abs(getattr(t, "pnl", 0)))
            if side == "BUY":
                buy_volume += amount
            elif side == "SELL":
                sell_volume += amount
        avg_value = self._values.mean()
        if avg_value == 0:
            return 0.0
        n_days = len(self.daily_returns)
        if n_days == 0:
            return 0.0
        turnover = self._safe_div(min(buy_volume, sell_volume), avg_value)
        return turnover * (self.trading_days / n_days)

    # ------------------------------------------------------------------
    # Benchmark-relative metrics
    # ------------------------------------------------------------------

    def information_ratio(self) -> float:
        """Information ratio = mean(active return) / std(active return)."""
        strat_ret = self.daily_returns
        bench_ret = self._benchmark_returns()
        if len(strat_ret) == 0 or len(bench_ret) == 0:
            return 0.0
        common_idx = strat_ret.index.intersection(bench_ret.index)
        if len(common_idx) < 2:
            return 0.0
        active = strat_ret.loc[common_idx] - bench_ret.loc[common_idx]
        tracking_error = active.std() * np.sqrt(self.trading_days)
        excess_annual = active.mean() * self.trading_days
        return self._safe_div(excess_annual, tracking_error)

    def tracking_error(self) -> float:
        """Annualized tracking error vs benchmark."""
        strat_ret = self.daily_returns
        bench_ret = self._benchmark_returns()
        if len(strat_ret) == 0 or len(bench_ret) == 0:
            return 0.0
        common_idx = strat_ret.index.intersection(bench_ret.index)
        if len(common_idx) < 2:
            return 0.0
        active = strat_ret.loc[common_idx] - bench_ret.loc[common_idx]
        return float(active.std() * np.sqrt(self.trading_days))

    def beta(self) -> float:
        """CAPM beta vs benchmark."""
        strat_ret = self.daily_returns
        bench_ret = self._benchmark_returns()
        if len(strat_ret) < 2 or len(bench_ret) < 2:
            return 1.0
        common_idx = strat_ret.index.intersection(bench_ret.index)
        if len(common_idx) < 2:
            return 1.0
        s = strat_ret.loc[common_idx]
        b = bench_ret.loc[common_idx]
        cov = s.cov(b)
        var = b.var()
        return self._safe_div(cov, var, default=1.0)

    def alpha(self) -> float:
        """Jensen's alpha (annualized)."""
        strat_ann = self.annualized_return()
        bench_series = self.benchmark
        if bench_series is None or len(self._values) < 2:
            return 0.0
        bench_aligned = bench_series.reindex(self._values.index).dropna()
        if len(bench_aligned) < 2:
            return 0.0
        bench_total = self._safe_div(
            bench_aligned.iloc[-1] - bench_aligned.iloc[0], bench_aligned.iloc[0]
        )
        n = len(bench_aligned.pct_change().dropna())
        if n == 0:
            return 0.0
        bench_ann = (1 + bench_total) ** (self.trading_days / n) - 1
        b = self.beta()
        return strat_ann - (self.risk_free_rate + b * (bench_ann - self.risk_free_rate))

    def treynor_ratio(self) -> float:
        """Treynor ratio = (annualized return - risk_free) / beta."""
        b = self.beta()
        return self._safe_div(self.annualized_return() - self.risk_free_rate, b)

    # ------------------------------------------------------------------
    # Monthly / periodic returns
    # ------------------------------------------------------------------

    def monthly_returns(self) -> pd.DataFrame:
        """DataFrame of monthly returns with columns: year, month, return."""
        if len(self.daily_returns) == 0:
            return pd.DataFrame(columns=["year", "month", "return"])
        monthly = (1 + self.daily_returns).resample("ME").prod() - 1
        monthly = monthly.dropna()
        result = pd.DataFrame(
            {
                "year": monthly.index.year,
                "month": monthly.index.month,
                "return": monthly.values,
            }
        )
        return result

    def rolling_returns(self, window: int = 20) -> pd.Series:
        """Rolling annualized returns over a given window."""
        if len(self.daily_returns) < window:
            return pd.Series(dtype=float)
        return (
            (1 + self.daily_returns)
            .rolling(window)
            .apply(lambda x: (x.prod()) ** (self.trading_days / window) - 1)
        )

    def rolling_volatility(self, window: int = 20) -> pd.Series:
        """Rolling annualized volatility."""
        if len(self.daily_returns) < window:
            return pd.Series(dtype=float)
        return self.daily_returns.rolling(window).std() * np.sqrt(self.trading_days)

    # ------------------------------------------------------------------
    # Composite
    # ------------------------------------------------------------------

    def all_metrics(self) -> Dict[str, Any]:
        """Return every available metric as a dictionary."""
        return {
            # Returns
            "total_return": self.total_return(),
            "annualized_return": self.annualized_return(),
            # Risk
            "volatility": self.volatility(),
            "downside_deviation": self.downside_deviation(),
            # Risk-adjusted
            "sharpe_ratio": self.sharpe_ratio(),
            "sortino_ratio": self.sortino_ratio(),
            "calmar_ratio": self.calmar_ratio(),
            "omega_ratio": self.omega_ratio(),
            "treynor_ratio": self.treynor_ratio(),
            # Drawdown
            "max_drawdown": self.max_drawdown(),
            "max_drawdown_duration": self.max_drawdown_duration(),
            "avg_drawdown_duration": self.avg_drawdown_duration(),
            # Trade stats
            "win_rate": self.win_rate(),
            "loss_rate": self.loss_rate(),
            "profit_loss_ratio": self.profit_loss_ratio(),
            "profit_factor": self.profit_factor(),
            "avg_trade_pnl": self.avg_trade_pnl(),
            "expectancy": self.expectancy(),
            # Holding / turnover
            "average_holding_period": self.average_holding_period(),
            "turnover_rate": self.turnover_rate(),
            # Benchmark-relative
            "information_ratio": self.information_ratio(),
            "tracking_error": self.tracking_error(),
            "alpha": self.alpha(),
            "beta": self.beta(),
        }
