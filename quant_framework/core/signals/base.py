"""Base classes for signal generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import pandas as pd


class SignalType(Enum):
    """Enumeration of possible signal types.

    Attributes:
        BUY: Open or add to long position.
        SELL: Close or reduce long position.
        HOLD: No action, maintain current position.
        REDUCE: Partially decrease position size.
        INCREASE: Partially increase position size.
    """

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    REDUCE = "reduce"
    INCREASE = "increase"


@dataclass
class SignalResult:
    """Container for signal generation results.

    Attributes:
        date: The date the signal was generated.
        signal_type: The type of signal (BUY, SELL, HOLD, etc.).
        strength: Signal strength in range [0.0, 1.0].
        stocks: Optional list of stock codes targeted by this signal.
        metadata: Additional context such as reason, factor values, etc.
    """

    date: pd.Timestamp
    signal_type: SignalType
    strength: float
    stocks: Optional[list[str]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_actionable(self) -> bool:
        """Return True if the signal requires a trade action."""
        return self.signal_type != SignalType.HOLD and self.strength > 0.0

    def stock_count(self) -> int:
        """Return the number of stocks in the signal."""
        return len(self.stocks) if self.stocks else 0


class Signal(ABC):
    """Abstract base class for all signal generators.

    Subclasses implement `generate()` to produce SignalResult objects
    from factor values and optional parameters.

    Signals bridge the factor layer and the strategy/execution layer
    by converting raw factor outputs into actionable trading signals.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this signal generator."""
        ...

    @abstractmethod
    def generate(
        self,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        params: Optional[dict[str, Any]] = None,
    ) -> SignalResult:
        """Generate a trading signal from factor values.

        Args:
            factor_values: Dictionary mapping factor names to their
                           DataFrame or Series values.
            params: Optional signal-specific parameters to override defaults.

        Returns:
            SignalResult containing the signal type, strength, and target stocks.
        """
        ...

    def _merge_params(
        self, defaults: dict[str, Any], params: Optional[dict[str, Any]]
    ) -> dict[str, Any]:
        """Merge default parameters with user-provided overrides.

        Args:
            defaults: Default parameter values.
            params: User-provided overrides (may be None).

        Returns:
            Merged parameter dictionary.
        """
        if params is None:
            return dict(defaults)
        merged = dict(defaults)
        merged.update(params)
        return merged

    @staticmethod
    def _normalize_strength(
        value: float, min_val: float = 0.0, max_val: float = 1.0
    ) -> float:
        """Normalize a strength value to [0.0, 1.0] range.

        Args:
            value: Raw strength value.
            min_val: Expected minimum of the raw value.
            max_val: Expected maximum of the raw value.

        Returns:
            Normalized strength clamped to [0.0, 1.0].
        """
        if max_val == min_val:
            return 0.5
        normalized = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, normalized))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
