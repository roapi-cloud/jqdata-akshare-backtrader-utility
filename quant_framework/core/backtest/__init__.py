"""Backtest engine for running strategies on historical data."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from quant_framework.core.strategy.base import BaseStrategy, Portfolio


@dataclass
class Trade:
    """Record of a single trade execution."""

    date: date
    code: str
    direction: str  # "BUY" or "SELL"
    shares: int
    price: float
    commission: float
    slippage: float
    total_cost: float


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003  # 0.03%
    slippage_rate: float = 0.001  # 0.1%
    min_trade_shares: int = 100  # A-share lot size
    stamp_tax_rate: float = 0.001  # 0.1% sell-side only


class BacktestEngine:
    """Event-driven backtest engine.

    Args:
        strategy: Trading strategy to run.
        config: Backtest configuration.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        config: Optional[BacktestConfig] = None,
    ) -> None:
        self.strategy = strategy
        self.config = config or BacktestConfig()
        self.portfolio = Portfolio(cash=self.config.initial_capital)
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict[str, Any]] = []

    def _calculate_cost(
        self,
        price: float,
        shares: int,
        direction: str,
    ) -> tuple[float, float, float]:
        """Calculate transaction costs.

        Returns:
            Tuple of (commission, slippage, total_cost).
        """
        notional = price * shares
        commission = max(notional * self.config.commission_rate, 5.0)  # min 5 yuan
        slippage = notional * self.config.slippage_rate
        stamp_tax = (
            notional * self.config.stamp_tax_rate if direction == "SELL" else 0.0
        )
        total_cost = commission + slippage + stamp_tax
        return commission, slippage, total_cost

    def _execute_order(
        self,
        trade_date: date,
        code: str,
        direction: str,
        target_shares: int,
        current_shares: int,
        price: float,
    ) -> Optional[Trade]:
        """Execute a buy/sell order to reach target shares.

        Returns:
            Trade record if executed, None if no action needed.
        """
        delta = target_shares - current_shares
        if delta == 0:
            return None

        # Round down to lot size
        trade_shares = (
            abs(delta) // self.config.min_trade_shares
        ) * self.config.min_trade_shares
        if trade_shares == 0:
            return None

        if delta > 0:
            actual_direction = "BUY"
        else:
            actual_direction = "SELL"
            trade_shares = min(trade_shares, current_shares)
            if trade_shares == 0:
                return None

        commission, slippage, total_cost = self._calculate_cost(
            price, trade_shares, actual_direction
        )

        if actual_direction == "BUY":
            cash_needed = price * trade_shares + total_cost
            if cash_needed > self.portfolio.cash:
                affordable_shares = int((self.portfolio.cash - total_cost) // price)
                affordable_shares = (
                    affordable_shares // self.config.min_trade_shares
                ) * self.config.min_trade_shares
                if affordable_shares == 0:
                    return None
                trade_shares = affordable_shares
                cash_needed = price * trade_shares + total_cost

            self.portfolio.cash -= cash_needed
            if code not in self.portfolio.positions:
                self.portfolio.positions[code] = {
                    "shares": 0,
                    "avg_cost": 0.0,
                    "current_price": price,
                }
            pos = self.portfolio.positions[code]
            total_cost_old = pos["shares"] * pos["avg_cost"]
            pos["shares"] += trade_shares
            pos["avg_cost"] = (total_cost_old + price * trade_shares) / pos["shares"]
            pos["current_price"] = price
        else:
            self.portfolio.cash += price * trade_shares - total_cost
            if code in self.portfolio.positions:
                self.portfolio.positions[code]["shares"] -= trade_shares
                self.portfolio.positions[code]["current_price"] = price
                if self.portfolio.positions[code]["shares"] <= 0:
                    del self.portfolio.positions[code]

        trade = Trade(
            date=trade_date,
            code=code,
            direction=actual_direction,
            shares=trade_shares,
            price=price,
            commission=commission,
            slippage=slippage,
            total_cost=total_cost,
        )
        self.trades.append(trade)
        return trade

    def run(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Run the backtest on historical data.

        Args:
            data: DataFrame with a MultiIndex (date, code) or columns
                  including 'date' and 'code' with OHLCV data.

        Returns:
            Dictionary with backtest results.
        """
        if "date" in data.columns:
            data = data.set_index("date")

        dates = sorted(data.index.unique())

        for trade_date in dates:
            bar_data = (
                data.loc[[trade_date]]
                if hasattr(data.index, "nlevels")
                else data.loc[trade_date]
            )
            if isinstance(bar_data, pd.Series):
                bar_data = bar_data.to_frame().T

            # Update current prices
            prices = {}
            if "code" in bar_data.columns:
                for _, row in bar_data.iterrows():
                    prices[row["code"]] = row["close"]
            elif hasattr(bar_data, "close"):
                prices["default"] = (
                    bar_data["close"]
                    if isinstance(bar_data, pd.DataFrame)
                    else bar_data.close
                )

            self.portfolio.update_total_value(prices)

            # Get target positions from strategy
            target_weights = self.strategy.on_bar(trade_date, bar_data, self.portfolio)

            # Calculate target shares and execute orders
            total_value = self.portfolio.total_value
            for code, weight in target_weights.items():
                target_value = total_value * weight
                price = prices.get(code, 0)
                if price <= 0:
                    continue
                target_shares = int(target_value / price)
                target_shares = (
                    target_shares // self.config.min_trade_shares
                ) * self.config.min_trade_shares
                current_shares = self.portfolio.positions.get(code, {}).get("shares", 0)

                self._execute_order(
                    trade_date,
                    code,
                    "BUY" if target_shares > current_shares else "SELL",
                    target_shares,
                    current_shares,
                    price,
                )

            # Record equity
            self.portfolio.update_total_value(prices)
            self.equity_curve.append(self.portfolio.snapshot(trade_date))

        return self._build_results()

    def _build_results(self) -> Dict[str, Any]:
        """Build final results dictionary."""
        equity_df = pd.DataFrame(self.equity_curve)
        if equity_df.empty:
            return {"equity_curve": equity_df, "trades": self.trades}

        initial = equity_df["total_value"].iloc[0]
        final = equity_df["total_value"].iloc[-1]
        total_return = (final - initial) / initial

        return {
            "equity_curve": equity_df,
            "trades": self.trades,
            "total_return": total_return,
            "initial_capital": initial,
            "final_value": final,
            "num_trades": len(self.trades),
        }
