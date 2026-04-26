"""Simulated broker for backtesting with realistic order execution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional

from .cost import CostModel, TradeCost


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(Enum):
    PENDING = "PENDING"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    """Represents a trading order."""

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    limit_price: Optional[float]
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    order_date: Optional[date] = None
    fill_date: Optional[date] = None
    cost: Optional[TradeCost] = None
    reject_reason: Optional[str] = None

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.filled_quantity

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.PARTIAL_FILL)


@dataclass
class Fill:
    """Represents a single fill execution."""

    fill_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    cost: TradeCost
    fill_date: date


@dataclass
class Position:
    """Tracks a position in a single security."""

    symbol: str
    quantity: int = 0
    avg_cost: float = 0.0
    available_quantity: int = (
        0  # T+1: shares bought today are not available until next day
    )

    @property
    def market_value(self) -> float:
        return self.quantity * self.avg_cost if self.quantity > 0 else 0.0

    def update_on_new_day(self) -> None:
        """Make today's purchased shares available for selling (T+1 rule)."""
        self.available_quantity = self.quantity


class SimulatedBroker:
    """Simulated broker with realistic A-share trading rules.

    Features:
        - Market and limit order support
        - Partial fill handling
        - T+1 settlement (shares bought today can't be sold today)
        - No short selling
        - Cost model integration
        - Order status tracking
    """

    def __init__(
        self,
        initial_cash: float,
        cost_model: CostModel,
    ):
        """Initialize the simulated broker.

        Args:
            initial_cash: Starting cash balance.
            cost_model: Transaction cost model to apply.
        """
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.cost_model = cost_model
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.fills: List[Fill] = []
        self._current_date: Optional[date] = None

    def set_current_date(self, current_date: date) -> None:
        """Set the current simulation date.

        Must be called before processing orders for a given day.
        Updates T+1 availability for existing positions.

        Args:
            current_date: The simulation date.
        """
        self._current_date = current_date
        for pos in self.positions.values():
            pos.update_on_new_day()

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
    ) -> Order:
        """Submit a new order.

        Args:
            symbol: Stock symbol (e.g., '000001.XSHE').
            side: BUY or SELL.
            quantity: Number of shares (must be positive).
            order_type: MARKET or LIMIT.
            limit_price: Required for LIMIT orders.

        Returns:
            The created Order object.

        Raises:
            ValueError: If order parameters are invalid.
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if order_type == OrderType.LIMIT and limit_price is None:
            raise ValueError("Limit price required for LIMIT orders")
        if order_type == OrderType.LIMIT and limit_price <= 0:
            raise ValueError("Limit price must be positive")

        order = Order(
            order_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            order_date=self._current_date,
        )
        self.orders[order.order_id] = order
        return order

    def try_execute_order(
        self,
        order: Order,
        bar_price: float,
        bar_volume: int,
    ) -> List[Fill]:
        """Try to execute an order against the current bar.

        Handles partial fills, cost application, and position updates.

        Args:
            order: The order to execute.
            bar_price: Current bar price (close price for market orders,
                       used for limit order comparison).
            bar_volume: Current bar volume (max shares that can trade).

        Returns:
            List of fills generated (empty if order cannot execute).
        """
        if not order.is_active:
            return []

        fills: List[Fill] = []

        # Determine execution price
        if order.order_type == OrderType.MARKET:
            exec_price = bar_price
        else:
            # Limit order: only execute if price is favorable
            if order.side == OrderSide.BUY and bar_price > order.limit_price:
                return []
            if order.side == OrderSide.SELL and bar_price < order.limit_price:
                return []
            exec_price = bar_price

        # Determine executable quantity
        exec_quantity = order.remaining_quantity
        if order.side == OrderSide.SELL:
            pos = self.positions.get(order.symbol)
            if pos is None:
                order.status = OrderStatus.REJECTED
                order.reject_reason = "No position to sell"
                return []
            exec_quantity = min(exec_quantity, pos.available_quantity)
            if exec_quantity <= 0:
                order.status = OrderStatus.REJECTED
                order.reject_reason = "No available shares (T+1 restriction)"
                return []

        # Cap by bar volume (assume we can trade up to 10% of bar volume)
        max_trade_volume = int(bar_volume * 0.1)
        exec_quantity = min(exec_quantity, max_trade_volume)

        if exec_quantity <= 0:
            return []

        # A-share: lot size is 100 shares
        exec_quantity = (exec_quantity // 100) * 100
        if exec_quantity <= 0:
            return []

        # Check cash for buy orders
        if order.side == OrderSide.BUY:
            cost = self.cost_model.calculate_cost(
                exec_price, exec_quantity, is_buy=True
            )
            total_cost = exec_price * exec_quantity + cost.total
            if total_cost > self.cash:
                # Try to afford fewer shares
                effective_price_per_share = self.cost_model.get_effective_price(
                    exec_price, exec_quantity, is_buy=True
                )
                affordable_qty = int(self.cash / effective_price_per_share)
                affordable_qty = (affordable_qty // 100) * 100
                if affordable_qty <= 0:
                    order.status = OrderStatus.REJECTED
                    order.reject_reason = "Insufficient cash"
                    return []
                exec_quantity = affordable_qty
                cost = self.cost_model.calculate_cost(
                    exec_price, exec_quantity, is_buy=True
                )
                total_cost = exec_price * exec_quantity + cost.total
        else:
            cost = self.cost_model.calculate_cost(
                exec_price, exec_quantity, is_buy=False
            )

        # Create fill
        fill = Fill(
            fill_id=str(uuid.uuid4())[:8],
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=exec_quantity,
            price=exec_price,
            cost=cost,
            fill_date=self._current_date,
        )
        fills.append(fill)
        self.fills.append(fill)

        # Update order
        total_filled = order.filled_quantity + exec_quantity
        order.avg_fill_price = (
            order.avg_fill_price * order.filled_quantity + exec_price * exec_quantity
        ) / total_filled
        order.filled_quantity = total_filled
        order.cost = cost
        order.fill_date = self._current_date

        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIAL_FILL

        # Update position and cash
        self._update_position(fill)

        return fills

    def _update_position(self, fill: Fill) -> None:
        """Update position and cash based on a fill.

        Args:
            fill: The fill to process.
        """
        symbol = fill.symbol
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)

        pos = self.positions[symbol]

        if fill.side == OrderSide.BUY:
            total_cost = fill.price * fill.quantity + fill.cost.total
            new_avg = (pos.avg_cost * pos.quantity + total_cost) / (
                pos.quantity + fill.quantity
            )
            pos.quantity += fill.quantity
            pos.avg_cost = new_avg
            self.cash -= fill.price * fill.quantity + fill.cost.total
        else:
            # Sell: reduce position
            proceeds = fill.price * fill.quantity - fill.cost.total
            pos.quantity -= fill.quantity
            pos.available_quantity -= fill.quantity
            self.cash += proceeds

            # Remove position if fully sold
            if pos.quantity <= 0:
                pos.quantity = 0
                pos.avg_cost = 0.0
                pos.available_quantity = 0
                del self.positions[symbol]

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending or partially filled order.

        Args:
            order_id: The order to cancel.

        Returns:
            True if cancelled successfully.
        """
        order = self.orders.get(order_id)
        if order and order.is_active:
            order.status = OrderStatus.CANCELLED
            return True
        return False

    def get_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value.

        Args:
            prices: Current prices for all held symbols.

        Returns:
            Total portfolio value (cash + positions).
        """
        value = self.cash
        for symbol, pos in self.positions.items():
            price = prices.get(symbol, pos.avg_cost)
            value += pos.quantity * price
        return value

    def get_active_orders(self) -> List[Order]:
        """Get all active (pending or partial fill) orders.

        Returns:
            List of active orders.
        """
        return [o for o in self.orders.values() if o.is_active]
