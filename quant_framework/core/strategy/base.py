"""Base strategy classes for quantitative trading."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class Portfolio:
    """Portfolio state snapshot.

    Attributes:
        cash: Available cash in the portfolio.
        positions: Dictionary mapping stock codes to position details.
        total_value: Total portfolio value (cash + positions).
        history: List of portfolio snapshots over time.
    """

    cash: float = 0.0
    positions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    total_value: float = 0.0
    history: List[Dict[str, Any]] = field(default_factory=list)

    def update_total_value(self, prices: Dict[str, float]) -> float:
        """Update total portfolio value based on current prices.

        Args:
            prices: Dictionary mapping stock codes to current prices.

        Returns:
            Updated total portfolio value.
        """
        position_value = sum(
            pos["shares"] * prices.get(code, pos.get("current_price", 0.0))
            for code, pos in self.positions.items()
        )
        self.total_value = self.cash + position_value
        return self.total_value

    def snapshot(self, trade_date: date) -> Dict[str, Any]:
        """Create a snapshot of the current portfolio state.

        Args:
            trade_date: The date of the snapshot.

        Returns:
            Dictionary containing portfolio state.
        """
        snap = {
            "date": trade_date,
            "cash": self.cash,
            "total_value": self.total_value,
            "positions": {code: dict(pos) for code, pos in self.positions.items()},
        }
        self.history.append(snap)
        return snap


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies.

    Subclasses must implement `get_target_positions` to define
    the strategy's logic for generating target portfolio weights.
    """

    def __init__(self, name: str = "BaseStrategy"):
        """Initialize the strategy.

        Args:
            name: Human-readable name for the strategy.
        """
        self.name = name
        self._params: Dict[str, Any] = {}
        self._initialized = False

    def initialize(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Initialize strategy with configuration parameters.

        Args:
            params: Dictionary of strategy-specific parameters.
        """
        if params is not None:
            self._params.update(params)
        self._initialized = True

    def on_bar(
        self,
        trade_date: date,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> Dict[str, float]:
        """Process a single bar (day) of data and return target positions.

        This is the main entry point called by the backtester each bar.
        It delegates to `get_target_positions` for the actual logic.

        Args:
            trade_date: Current trading date.
            data: Market data DataFrame with columns including at least
                  'code', 'close', and optionally factor columns.
            portfolio: Current portfolio state.

        Returns:
            Dictionary mapping stock codes to target weights (0-1).
        """
        if not self._initialized:
            self.initialize()
        return self.get_target_positions(trade_date, data, portfolio)

    @abstractmethod
    def get_target_positions(
        self,
        trade_date: date,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> Dict[str, float]:
        """Compute target position weights for the current bar.

        Args:
            trade_date: Current trading date.
            data: Market data DataFrame.
            portfolio: Current portfolio state.

        Returns:
            Dictionary mapping stock codes to target weights (0-1).
            Weights should sum to <= 1.0 (remaining is cash).
        """
        ...

    def get_params(self) -> Dict[str, Any]:
        """Return current strategy parameters.

        Returns:
            Copy of the parameter dictionary.
        """
        return dict(self._params)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
