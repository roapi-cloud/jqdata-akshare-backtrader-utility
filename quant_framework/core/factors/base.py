"""Base classes for factor calculation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class FactorResult:
    """Container for factor calculation results.

    Attributes:
        name: Factor name identifier.
        values: Series/DataFrame of factor values indexed by date.
        params: Parameters used for calculation.
        metadata: Additional metadata (e.g., warnings, stats).
    """

    name: str
    values: pd.Series | pd.DataFrame
    params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Check if the result contains no valid data."""
        if isinstance(self.values, pd.Series):
            return self.values.empty or self.values.isna().all()
        if isinstance(self.values, pd.DataFrame):
            return self.values.empty or self.values.isna().all().all()
        return True

    def dropna(self) -> "FactorResult":
        """Return a new FactorResult with NaN values removed."""
        if isinstance(self.values, pd.Series):
            cleaned = self.values.dropna()
        else:
            cleaned = self.values.dropna(how="all")
        return FactorResult(
            name=self.name,
            values=cleaned,
            params=self.params,
            metadata=self.metadata,
        )


class Factor(ABC):
    """Abstract base class for all factors.

    Subclasses must implement `calculate()` which receives a DataFrame
    with OHLCV columns and returns a FactorResult.

    Expected DataFrame columns (at minimum):
        - open, high, low, close, volume
    Additional columns may include: amount, turnover, etc.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this factor."""
        ...

    @abstractmethod
    def calculate(self, data: pd.DataFrame, **params) -> FactorResult:
        """Calculate factor values from market data.

        Args:
            data: DataFrame with OHLCV data, indexed by date.
            **params: Factor-specific parameters.

        Returns:
            FactorResult containing computed factor values.
        """
        ...

    def validate_data(self, data: pd.DataFrame, required_cols: list[str]) -> bool:
        """Validate that input data contains required columns.

        Args:
            data: Input DataFrame.
            required_cols: List of column names that must be present.

        Returns:
            True if all required columns exist.
        """
        missing = [c for c in required_cols if c not in data.columns]
        if missing:
            raise ValueError(
                f"Factor '{self.name}' requires columns {missing}, "
                f"but only found: {list(data.columns)}"
            )
        return True

    @staticmethod
    def safe_div(
        numerator: pd.Series | float,
        denominator: pd.Series | float,
        default: float = 0.0,
    ) -> pd.Series | float:
        """Safe division that handles zero denominators.

        Args:
            numerator: Dividend.
            denominator: Divisor.
            default: Value to use when denominator is zero.

        Returns:
            Division result with zeros replaced by default.
        """
        if isinstance(denominator, pd.Series):
            result = numerator / denominator.replace(0, np.nan)
            return result.fillna(default)
        if denominator == 0:
            return default
        return numerator / denominator


class FactorRegistry:
    """Registry for managing and retrieving factor implementations.

    Usage:
        registry = FactorRegistry()
        registry.register(MAFactor)
        factor = registry.get("MA")
    """

    def __init__(self) -> None:
        self._factors: dict[str, type[Factor]] = {}

    def register(self, factor_cls: type[Factor]) -> None:
        """Register a factor class by its name property.

        Args:
            factor_cls: A subclass of Factor.
        """
        if not issubclass(factor_cls, Factor):
            raise TypeError(f"{factor_cls} must be a subclass of Factor")
        instance = factor_cls()
        self._factors[instance.name] = factor_cls

    def get(self, name: str) -> Factor:
        """Instantiate and return a factor by name.

        Args:
            name: Factor name.

        Returns:
            An instance of the requested factor.

        Raises:
            KeyError: If the factor is not registered.
        """
        if name not in self._factors:
            raise KeyError(
                f"Factor '{name}' not found. Available: {list(self._factors.keys())}"
            )
        return self._factors[name]()

    def list_factors(self) -> list[str]:
        """Return list of all registered factor names."""
        return sorted(self._factors.keys())

    def has(self, name: str) -> bool:
        """Check if a factor is registered."""
        return name in self._factors

    def calculate_all(
        self, data: pd.DataFrame, factor_names: list[str] | None = None, **params
    ) -> dict[str, FactorResult]:
        """Calculate multiple factors at once.

        Args:
            data: OHLCV DataFrame.
            factor_names: List of factor names to calculate. None = all.
            **params: Parameters passed to each factor.

        Returns:
            Dict mapping factor name to FactorResult.
        """
        names = factor_names or self.list_factors()
        results: dict[str, FactorResult] = {}
        for name in names:
            factor = self.get(name)
            results[name] = factor.calculate(data, **params)
        return results
