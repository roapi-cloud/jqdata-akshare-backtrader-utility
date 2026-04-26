"""Transaction cost modeling for A-share backtesting."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TradeCost:
    """Detailed breakdown of trade costs."""

    commission: float
    stamp_duty: float
    transfer_fee: float
    slippage_cost: float
    total: float


class CostModel(ABC):
    """Base class for transaction cost models."""

    @abstractmethod
    def calculate_cost(
        self,
        price: float,
        quantity: int,
        is_buy: bool,
    ) -> TradeCost:
        """Calculate total transaction cost for a trade.

        Args:
            price: Execution price per share.
            quantity: Number of shares.
            is_buy: True for buy, False for sell.

        Returns:
            TradeCost with detailed cost breakdown.
        """
        ...

    @abstractmethod
    def get_effective_price(
        self,
        price: float,
        quantity: int,
        is_buy: bool,
    ) -> float:
        """Get the effective price after costs.

        For buys: price + cost per share (you pay more).
        For sells: price - cost per share (you receive less).

        Args:
            price: Base execution price.
            quantity: Number of shares.
            is_buy: True for buy, False for sell.

        Returns:
            Effective price per share after costs.
        """
        ...


class AStockCostModel(CostModel):
    """A-share specific transaction cost model.

    Costs (as of typical A-share rules):
        - Commission: 0.03% (min 5 yuan)
        - Stamp duty: 0.1% (sell only)
        - Transfer fee: 0.002%
        - Slippage: configurable (default 0.002 = 0.2%)
    """

    def __init__(
        self,
        commission_rate: float = 0.0003,
        min_commission: float = 5.0,
        stamp_duty_rate: float = 0.001,
        transfer_fee_rate: float = 0.00002,
        slippage_rate: float = 0.002,
    ):
        """Initialize A-share cost model.

        Args:
            commission_rate: Broker commission rate (default 0.03%).
            min_commission: Minimum commission per trade (default 5 yuan).
            stamp_duty_rate: Stamp duty rate, sell only (default 0.1%).
            transfer_fee_rate: Transfer fee rate (default 0.002%).
            slippage_rate: Slippage as fraction of price (default 0.2%).
        """
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.stamp_duty_rate = stamp_duty_rate
        self.transfer_fee_rate = transfer_fee_rate
        self.slippage_rate = slippage_rate

    def calculate_cost(
        self,
        price: float,
        quantity: int,
        is_buy: bool,
    ) -> TradeCost:
        """Calculate total transaction cost for an A-share trade.

        Args:
            price: Execution price per share.
            quantity: Number of shares.
            is_buy: True for buy, False for sell.

        Returns:
            TradeCost with detailed breakdown.
        """
        turnover = price * quantity

        # Commission: rate * turnover, with minimum
        commission = max(turnover * self.commission_rate, self.min_commission)

        # Stamp duty: only on sells
        stamp_duty = turnover * self.stamp_duty_rate if not is_buy else 0.0

        # Transfer fee: both directions
        transfer_fee = turnover * self.transfer_fee_rate

        # Slippage cost
        slippage_cost = turnover * self.slippage_rate

        total = commission + stamp_duty + transfer_fee + slippage_cost

        return TradeCost(
            commission=commission,
            stamp_duty=stamp_duty,
            transfer_fee=transfer_fee,
            slippage_cost=slippage_cost,
            total=total,
        )

    def get_effective_price(
        self,
        price: float,
        quantity: int,
        is_buy: bool,
    ) -> float:
        """Get effective price after all costs.

        Args:
            price: Base execution price.
            quantity: Number of shares.
            is_buy: True for buy, False for sell.

        Returns:
            Effective price per share.
        """
        cost = self.calculate_cost(price, quantity, is_buy)
        cost_per_share = cost.total / quantity

        if is_buy:
            return price + cost_per_share
        return price - cost_per_share
