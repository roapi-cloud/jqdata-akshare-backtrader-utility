"""Event-driven backtest engine for A-share strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Protocol

import pandas as pd

from .broker import Fill, Order, OrderSide, OrderStatus, OrderType, SimulatedBroker
from .cost import AStockCostModel, CostModel


class StrategyProtocol(Protocol):
    """Protocol that strategies must implement."""

    def on_bar(self, data: Dict[str, Any], broker: SimulatedBroker) -> None:
        """Called for each bar with market data.

        Args:
            data: Dict mapping symbol to bar data (OHLCV).
            broker: Broker instance to submit orders.
        """
        ...

    def on_init(self, broker: SimulatedBroker) -> None:
        """Called once at the start of backtest.

        Args:
            broker: Broker instance.
        """
        ...


@dataclass
class DividendEvent:
    """Represents a dividend or corporate action."""

    date: date
    symbol: str
    cash_dividend: float = 0.0  # Per share cash dividend
    stock_dividend: float = 0.0  # Bonus shares per share (e.g., 0.2 = 2 for 10)
    split_ratio: float = 1.0  # Split factor (e.g., 2.0 = 2-for-1 split)


@dataclass
class BacktestResult:
    """Container for backtest results."""

    daily_values: pd.DataFrame = field(default_factory=pd.DataFrame)
    trade_log: List[Dict[str, Any]] = field(default_factory=list)
    position_log: List[Dict[str, Any]] = field(default_factory=list)
    benchmark_values: pd.Series = field(default_factory=pd.Series)
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_return: float = 0.0
    benchmark_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0

    def summary(self) -> str:
        """Generate a text summary of results.

        Returns:
            Formatted summary string.
        """
        lines = [
            "=" * 50,
            "BACKTEST RESULTS",
            "=" * 50,
            f"Initial Capital:    {self.initial_capital:,.2f}",
            f"Final Capital:     {self.final_capital:,.2f}",
            f"Total Return:      {self.total_return:.2%}",
            f"Benchmark Return:  {self.benchmark_return:.2%}",
            f"Max Drawdown:      {self.max_drawdown:.2%}",
            f"Sharpe Ratio:      {self.sharpe_ratio:.4f}",
            f"Total Trades:      {self.total_trades}",
            f"Win Rate:          {self.win_rate:.2%}",
            "=" * 50,
        ]
        return "\n".join(lines)


class BacktestEngine:
    """Event-driven backtest engine.

    Processes daily bars sequentially, integrating strategy signals
    with a simulated broker for realistic execution.

    Features:
        - Daily bar processing
        - Strategy integration via protocol
        - Broker integration for order management
        - Trade and position history recording
        - Dividend and corporate action handling
        - Benchmark comparison
    """

    def __init__(
        self,
        strategy: StrategyProtocol,
        initial_cash: float = 1_000_000.0,
        cost_model: Optional[CostModel] = None,
        benchmark_data: Optional[pd.DataFrame] = None,
        dividends: Optional[List[DividendEvent]] = None,
    ):
        """Initialize the backtest engine.

        Args:
            strategy: Strategy instance implementing StrategyProtocol.
            initial_cash: Starting capital (default 1M yuan).
            cost_model: Transaction cost model (default AStockCostModel).
            benchmark_data: DataFrame with 'date' and 'close' columns
                           for benchmark comparison.
            dividends: List of dividend/corporate action events.
        """
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.cost_model = cost_model or AStockCostModel()
        self.broker = SimulatedBroker(
            initial_cash=initial_cash,
            cost_model=self.cost_model,
        )
        self.benchmark_data = benchmark_data
        self.dividends = dividends or []
        self._dividend_index: Dict[date, List[DividendEvent]] = {}

        # Results storage
        self._daily_records: List[Dict[str, Any]] = []
        self._trade_log: List[Dict[str, Any]] = []
        self._position_log: List[Dict[str, Any]] = []

    def _index_dividends(self) -> None:
        """Index dividends by date for fast lookup."""
        self._dividend_index = {}
        for div in self.dividends:
            self._dividend_index.setdefault(div.date, []).append(div)

    def _process_dividends(self, current_date: date) -> None:
        """Process any dividends or corporate actions for the given date.

        Args:
            current_date: Current simulation date.
        """
        events = self._dividend_index.get(current_date, [])
        for event in events:
            pos = self.broker.positions.get(event.symbol)
            if pos is None:
                continue

            # Cash dividend
            if event.cash_dividend > 0:
                cash_amount = pos.quantity * event.cash_dividend
                self.broker.cash += cash_amount

            # Stock dividend (bonus shares)
            if event.stock_dividend > 0:
                bonus_shares = int(pos.quantity * event.stock_dividend)
                # Bonus shares are not available until next day (T+1)
                pos.quantity += bonus_shares

            # Stock split
            if event.split_ratio > 1.0:
                old_quantity = pos.quantity
                new_quantity = int(pos.quantity * event.split_ratio)
                # Adjust average cost to keep market value constant
                if new_quantity > 0:
                    pos.avg_cost = (pos.avg_cost * old_quantity) / new_quantity
                pos.quantity = new_quantity
                pos.available_quantity = (
                    old_quantity  # Original shares remain available
                )

    def run(
        self,
        bar_data: pd.DataFrame,
    ) -> BacktestResult:
        """Run the backtest.

        Args:
            bar_data: DataFrame with columns:
                - 'date': Trading date
                - 'symbol': Stock symbol
                - 'open', 'high', 'low', 'close', 'volume': OHLCV data
                Optional: 'adj_close' for adjusted close prices.

        Returns:
            BacktestResult with full results.
        """
        self._index_dividends()

        # Initialize strategy
        self.strategy.on_init(self.broker)

        # Group data by date
        dates = sorted(bar_data["date"].unique())

        for current_date in dates:
            day_data = bar_data[bar_data["date"] == current_date]

            # Set broker date (updates T+1 availability)
            self.broker.set_current_date(current_date)

            # Process dividends
            self._process_dividends(current_date)

            # Build data dict for strategy: {symbol: bar_dict}
            data_dict: Dict[str, Dict[str, Any]] = {}
            price_dict: Dict[str, float] = {}

            for _, row in day_data.iterrows():
                symbol = row["symbol"]
                data_dict[symbol] = {
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                    "adj_close": row.get("adj_close", row["close"]),
                }
                price_dict[symbol] = row["close"]

            # Call strategy to generate orders
            self.strategy.on_bar(data_dict, self.broker)

            # Execute active orders
            active_orders = self.broker.get_active_orders()
            for order in active_orders:
                symbol_data = data_dict.get(order.symbol)
                if symbol_data is None:
                    # Symbol not trading today (suspended)
                    continue

                fills = self.broker.try_execute_order(
                    order=order,
                    bar_price=symbol_data["close"],
                    bar_volume=symbol_data["volume"],
                )

                # Record fills
                for fill in fills:
                    self._trade_log.append(
                        {
                            "date": current_date,
                            "order_id": fill.order_id,
                            "fill_id": fill.fill_id,
                            "symbol": fill.symbol,
                            "side": fill.side.value,
                            "quantity": fill.quantity,
                            "price": fill.price,
                            "cost": fill.cost.total,
                            "commission": fill.cost.commission,
                            "stamp_duty": fill.cost.stamp_duty,
                            "transfer_fee": fill.cost.transfer_fee,
                            "slippage": fill.cost.slippage_cost,
                        }
                    )

            # Record daily portfolio value
            portfolio_value = self.broker.get_portfolio_value(price_dict)

            # Get benchmark value
            benchmark_value = self._get_benchmark_value(current_date)

            # Record position snapshot
            for symbol, pos in self.broker.positions.items():
                current_price = price_dict.get(symbol, pos.avg_cost)
                self._position_log.append(
                    {
                        "date": current_date,
                        "symbol": symbol,
                        "quantity": pos.quantity,
                        "available": pos.available_quantity,
                        "avg_cost": pos.avg_cost,
                        "current_price": current_price,
                        "market_value": pos.quantity * current_price,
                        "unrealized_pnl": (current_price - pos.avg_cost) * pos.quantity,
                    }
                )

            self._daily_records.append(
                {
                    "date": current_date,
                    "cash": self.broker.cash,
                    "portfolio_value": portfolio_value,
                    "benchmark_value": benchmark_value,
                    "num_positions": len(self.broker.positions),
                }
            )

        return self._build_result()

    def _get_benchmark_value(self, current_date: date) -> Optional[float]:
        """Get benchmark value for a given date.

        Args:
            current_date: The date to look up.

        Returns:
            Benchmark close value, or None if not available.
        """
        if self.benchmark_data is None:
            return None

        row = self.benchmark_data[self.benchmark_data["date"] == current_date]
        if row.empty:
            return None
        return float(row.iloc[0]["close"])

    def _build_result(self) -> BacktestResult:
        """Build the final BacktestResult object.

        Returns:
            Complete BacktestResult with all metrics.
        """
        daily_df = pd.DataFrame(self._daily_records)

        if daily_df.empty:
            return BacktestResult(initial_capital=self.initial_cash)

        # Calculate returns
        final_value = daily_df["portfolio_value"].iloc[-1]
        initial_value = self.initial_cash
        total_return = (final_value - initial_value) / initial_value

        # Benchmark return
        benchmark_series = daily_df["benchmark_value"].dropna()
        benchmark_return = 0.0
        if len(benchmark_series) >= 2:
            benchmark_return = (
                benchmark_series.iloc[-1] - benchmark_series.iloc[0]
            ) / benchmark_series.iloc[0]

        # Max drawdown
        peak = daily_df["portfolio_value"].cummax()
        drawdown = (daily_df["portfolio_value"] - peak) / peak
        max_drawdown = drawdown.min()

        # Sharpe ratio (annualized, assuming 252 trading days)
        daily_returns = daily_df["portfolio_value"].pct_change().dropna()
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * (252**0.5)
        else:
            sharpe_ratio = 0.0

        # Trade statistics
        total_trades = len(self._trade_log)
        win_rate = 0.0
        if total_trades > 0:
            sell_trades = [t for t in self._trade_log if t["side"] == "SELL"]
            if sell_trades:
                # A trade is a "win" if sell price > avg buy cost
                wins = 0
                for sell in sell_trades:
                    pos_key = sell["symbol"]
                    # Find corresponding buy trades
                    buy_trades = [
                        t
                        for t in self._trade_log
                        if t["symbol"] == pos_key and t["side"] == "BUY"
                    ]
                    if buy_trades:
                        avg_buy_price = sum(
                            t["price"] * t["quantity"] for t in buy_trades
                        ) / sum(t["quantity"] for t in buy_trades)
                        if sell["price"] > avg_buy_price:
                            wins += 1
                win_rate = wins / len(sell_trades)

        return BacktestResult(
            daily_values=daily_df,
            trade_log=self._trade_log,
            position_log=self._position_log,
            benchmark_values=benchmark_series,
            initial_capital=initial_value,
            final_capital=final_value,
            total_return=total_return,
            benchmark_return=benchmark_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            total_trades=total_trades,
            win_rate=win_rate,
        )
