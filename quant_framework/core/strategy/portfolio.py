"""Portfolio management with position tracking and rebalancing."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class Position:
    """Represents a single stock position.

    Attributes:
        code: Stock code / ticker.
        shares: Number of shares held.
        cost: Average cost per share.
        current_price: Latest market price.
    """

    code: str
    shares: float = 0.0
    cost: float = 0.0
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        """Current market value of the position."""
        return self.shares * self.current_price

    @property
    def cost_value(self) -> float:
        """Total cost basis of the position."""
        return self.shares * self.cost

    @property
    def pnl(self) -> float:
        """Realized + unrealized P&L for this position."""
        return self.market_value - self.cost_value

    @property
    def pnl_pct(self) -> float:
        """P&L as a percentage of cost."""
        if self.cost_value == 0:
            return 0.0
        return self.pnl / self.cost_value

    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary."""
        return {
            "code": self.code,
            "shares": self.shares,
            "cost": self.cost,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "cost_value": self.cost_value,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
        }


@dataclass
class Trade:
    """Represents a single trade execution.

    Attributes:
        code: Stock code.
        direction: 'buy' or 'sell'.
        shares: Number of shares traded.
        price: Execution price.
        commission: Transaction commission cost.
        date: Trade date.
    """

    code: str
    direction: str
    shares: float
    price: float
    commission: float = 0.0
    date: Optional[date] = None

    @property
    def notional(self) -> float:
        """Total notional value of the trade."""
        return self.shares * self.price

    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary."""
        return {
            "code": self.code,
            "direction": self.direction,
            "shares": self.shares,
            "price": self.price,
            "commission": self.commission,
            "notional": self.notional,
            "date": self.date,
        }


class PortfolioManager:
    """Manages portfolio state, position tracking, and rebalancing.

    Handles position constraints including maximum weight per position
    and maximum number of positions.

    Attributes:
        cash: Available cash balance.
        positions: Dictionary of code -> Position.
        trades: List of executed trades.
        commission_rate: Commission rate per trade (e.g. 0.001).
        max_weight: Maximum weight for any single position.
        max_positions: Maximum number of positions allowed.
        history: Portfolio snapshots over time.
    """

    def __init__(
        self,
        initial_cash: float = 1_000_000.0,
        commission_rate: float = 0.001,
        max_weight: float = 0.10,
        max_positions: int = 50,
        min_trade_value: float = 100.0,
    ):
        """Initialize the portfolio manager.

        Args:
            initial_cash: Starting cash amount.
            commission_rate: Commission rate for each trade.
            max_weight: Maximum portfolio weight for any single position.
            max_positions: Maximum number of concurrent positions.
            min_trade_value: Minimum trade notional value to execute.
        """
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.commission_rate = commission_rate
        self.max_weight = max_weight
        self.max_positions = max_positions
        self.min_trade_value = min_trade_value
        self.history: List[Dict[str, Any]] = []
        self._total_value = initial_cash

    @property
    def total_value(self) -> float:
        """Total portfolio value (cash + all positions at current prices)."""
        position_value = sum(p.market_value for p in self.positions.values())
        return self.cash + position_value

    @property
    def position_count(self) -> int:
        """Number of open positions."""
        return len(self.positions)

    def get_position_weight(self, code: str) -> float:
        """Get the current weight of a position.

        Args:
            code: Stock code.

        Returns:
            Weight as a fraction of total portfolio value.
        """
        tv = self.total_value
        if tv == 0:
            return 0.0
        pos = self.positions.get(code)
        if pos is None:
            return 0.0
        return pos.market_value / tv

    def update_prices(self, prices: Dict[str, float]) -> None:
        """Update current prices for all positions.

        Args:
            prices: Dictionary mapping stock codes to current prices.
        """
        for code, price in prices.items():
            if code in self.positions:
                self.positions[code].current_price = price

    def _calculate_commission(self, notional: float) -> float:
        """Calculate commission for a trade.

        Args:
            notional: Trade notional value.

        Returns:
            Commission amount.
        """
        return max(notional * self.commission_rate, 5.0)

    def _apply_constraints(
        self,
        target_weights: Dict[str, float],
        current_prices: Dict[str, float],
    ) -> Dict[str, float]:
        """Apply position constraints to target weights.

        Enforces max_weight and max_positions limits.

        Args:
            target_weights: Raw target weights from strategy.
            current_prices: Current prices for all stocks.

        Returns:
            Constrained target weights.
        """
        constrained = {}

        # Filter out stocks with zero/negative weights or no price
        valid = {
            code: w
            for code, w in target_weights.items()
            if w > 0 and code in current_prices and current_prices[code] > 0
        }

        if not valid:
            return constrained

        # Apply max weight constraint
        for code, w in valid.items():
            constrained[code] = min(w, self.max_weight)

        # Apply max positions constraint - keep highest weights
        if len(constrained) > self.max_positions:
            sorted_items = sorted(constrained.items(), key=lambda x: x[1], reverse=True)
            constrained = dict(sorted_items[: self.max_positions])

        # Normalize weights to sum to at most 1.0
        total = sum(constrained.values())
        if total > 1.0:
            constrained = {code: w / total for code, w in constrained.items()}

        return constrained

    def rebalance(
        self,
        target_weights: Dict[str, float],
        current_prices: Dict[str, float],
        trade_date: Optional[date] = None,
    ) -> List[Trade]:
        """Rebalance portfolio to match target weights.

        Computes the trades needed to move from current positions to
        target weights and executes them.

        Args:
            target_weights: Target weight for each stock (0-1).
            current_prices: Current market prices.
            trade_date: Date of the rebalance.

        Returns:
            List of executed trades.
        """
        # Apply constraints
        constrained = self._apply_constraints(target_weights, current_prices)

        tv = self.total_value
        executed_trades: List[Trade] = []

        # Determine all codes involved
        all_codes = set(list(constrained.keys()) + list(self.positions.keys()))

        for code in all_codes:
            target_w = constrained.get(code, 0.0)
            target_value = tv * target_w
            price = current_prices.get(code, 0.0)

            if price <= 0:
                continue

            current_pos = self.positions.get(code)
            current_shares = current_pos.shares if current_pos else 0.0
            current_value = current_shares * price

            target_shares = target_value / price
            delta_shares = target_shares - current_shares

            # Round to lot size (100 shares for A-shares)
            delta_shares = round(delta_shares / 100.0) * 100.0

            if abs(delta_shares) * price < self.min_trade_value:
                continue

            if delta_shares > 0:
                # Buy
                notional = delta_shares * price
                commission = self._calculate_commission(notional)
                cost = notional + commission

                if cost > self.cash:
                    # Scale down to available cash
                    available = self.cash
                    delta_shares = available / (price * (1 + self.commission_rate))
                    delta_shares = round(delta_shares / 100.0) * 100.0
                    if delta_shares <= 0:
                        continue
                    notional = delta_shares * price
                    commission = self._calculate_commission(notional)

                trade = Trade(
                    code=code,
                    direction="buy",
                    shares=delta_shares,
                    price=price,
                    commission=commission,
                    date=trade_date,
                )
                self._execute_buy(trade)
                executed_trades.append(trade)

            elif delta_shares < 0:
                # Sell
                sell_shares = min(-delta_shares, current_shares)
                if sell_shares <= 0:
                    continue

                notional = sell_shares * price
                commission = self._calculate_commission(notional)

                trade = Trade(
                    code=code,
                    direction="sell",
                    shares=sell_shares,
                    price=price,
                    commission=commission,
                    date=trade_date,
                )
                self._execute_sell(trade)
                executed_trades.append(trade)

        self.trades.extend(executed_trades)
        return executed_trades

    def _execute_buy(self, trade: Trade) -> None:
        """Execute a buy trade.

        Args:
            trade: Trade object with buy details.
        """
        cost = trade.notional + trade.commission
        self.cash -= cost

        if trade.code in self.positions:
            pos = self.positions[trade.code]
            total_cost = pos.cost * pos.shares + trade.notional
            pos.shares += trade.shares
            if pos.shares > 0:
                pos.cost = total_cost / pos.shares
            pos.current_price = trade.price
        else:
            self.positions[trade.code] = Position(
                code=trade.code,
                shares=trade.shares,
                cost=trade.price,
                current_price=trade.price,
            )

    def _execute_sell(self, trade: Trade) -> None:
        """Execute a sell trade.

        Args:
            trade: Trade object with sell details.
        """
        proceeds = trade.notional - trade.commission
        self.cash += proceeds

        if trade.code in self.positions:
            pos = self.positions[trade.code]
            pos.shares -= trade.shares
            pos.current_price = trade.price

            if pos.shares <= 0:
                del self.positions[trade.code]

    def snapshot(self, trade_date: date) -> Dict[str, Any]:
        """Record a portfolio snapshot.

        Args:
            trade_date: Date of the snapshot.

        Returns:
            Snapshot dictionary.
        """
        snap = {
            "date": trade_date,
            "cash": self.cash,
            "total_value": self.total_value,
            "position_count": self.position_count,
            "positions": {code: pos.to_dict() for code, pos in self.positions.items()},
        }
        self.history.append(snap)
        return snap

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get a summary of the current portfolio state.

        Returns:
            Dictionary with portfolio summary statistics.
        """
        tv = self.total_value
        position_values = {
            code: pos.market_value for code, pos in self.positions.items()
        }
        weights = {
            code: mv / tv if tv > 0 else 0.0 for code, mv in position_values.items()
        }

        total_pnl = sum(pos.pnl for pos in self.positions.values())
        total_cost = sum(pos.cost_value for pos in self.positions.values())

        return {
            "total_value": tv,
            "cash": self.cash,
            "cash_weight": self.cash / tv if tv > 0 else 0.0,
            "position_value": tv - self.cash,
            "position_count": self.position_count,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl / total_cost if total_cost > 0 else 0.0,
            "weights": weights,
            "total_trades": len(self.trades),
        }

    def get_trade_log(self) -> pd.DataFrame:
        """Return trade history as a DataFrame.

        Returns:
            DataFrame with all executed trades.
        """
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([t.to_dict() for t in self.trades])

    def get_history(self) -> pd.DataFrame:
        """Return portfolio history as a DataFrame.

        Returns:
            DataFrame with portfolio snapshots over time.
        """
        if not self.history:
            return pd.DataFrame()
        records = []
        for snap in self.history:
            records.append(
                {
                    "date": snap["date"],
                    "cash": snap["cash"],
                    "total_value": snap["total_value"],
                    "position_count": snap["position_count"],
                }
            )
        return pd.DataFrame(records)
