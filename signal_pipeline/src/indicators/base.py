"""Abstract base class for all signal generators (indicators)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from src.core.models import MarketData, Signal


class BaseSignalGenerator(ABC):
    """Abstract base for all technical indicators / signal generators.

    Every indicator must inherit from this class to ensure a uniform interface,
    parameter management, and incremental calculation support.

    Attributes:
        name: Human-readable identifier for the indicator.
        min_history: Minimum number of historical bars required for reliable
            batch calculation. Defaults to 100.
        supports_incremental: Whether the indicator can perform O(1) incremental
            updates via :meth:`update`.
    """

    name: str = "base"
    min_history: int = 100
    supports_incremental: bool = False

    def __init__(self, **params: Any) -> None:
        """Store indicator parameters and initialise internal state.

        Args:
            **params: Arbitrary keyword arguments that configure the indicator
                (e.g. ``period=14`` for RSI).
        """
        self._params: dict[str, Any] = dict(params)
        self._state: dict[str, Any] = {}

    @abstractmethod
    def generate(self, data: List[MarketData]) -> List[Signal]:
        """Batch-compute signals from a list of market data bars.

        Args:
            data: Ordered list of :class:`MarketData` bars (oldest first).

        Returns:
            List of :class:`Signal` objects, one per bar (or sparse subset).

        Raises:
            InsufficientDataError: If ``len(data) < self.min_history``.
        """
        ...

    def update(self, new_bar: MarketData) -> Optional[Signal]:
        """Incrementally update the indicator with a single new bar.

        Subclasses that set ``supports_incremental = True`` **must** override
        this method to provide O(1) update logic.

        Args:
            new_bar: The latest :class:`MarketData` bar.

        Returns:
            A :class:`Signal` if one is produced, otherwise ``None``.

        Raises:
            NotImplementedError: If the subclass does not support incremental
                updates.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support incremental updates. "
            "Override `update()` or set `supports_incremental = False`."
        )

    def get_required_periods(self) -> int:
        """Return the minimum number of historical periods needed."""
        return self.min_history

    def __repr__(self) -> str:
        params_str = ", ".join(f"{k}={v!r}" for k, v in self._params.items())
        return f"{self.__class__.__name__}(name={self.name!r}, {params_str})"
