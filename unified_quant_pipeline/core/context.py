"""
Run context for managing global state during pipeline execution.

This module provides a dataclass-based context object that stores all runtime
state and data flowing through the quantitative pipeline, avoiding the need
to pass data through nested function arguments.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class RunContext:
    """Run context storing all state during pipeline execution.

    Used to pass data and state between pipeline components,
    avoiding passing through function arguments层层.

    Attributes:
        config: PipelineConfig instance.
        raw_data: Raw stock data downloaded from data source.
        factor_data: Computed factor data.
        processed_data: Preprocessed factor data ready for modeling.
        labels: Constructed labels for supervised learning.
        model: Trained machine learning model.
        model_metrics: Model evaluation metrics.
        predictions: Model predictions on latest data.
        timing_signal: Market timing signal dictionary.
        timing_position: Current position ratio from timing (0.0 to 1.0).
        selected_stocks: List of selected stock codes for portfolio.
        weights: Stock weights in the portfolio {code: weight}.
        backtest_result: Backtest result object.
        performance_metrics: Backtest performance metrics.
        current_date: Current processing date.
        trade_dates: List of trading dates in the pipeline range.
        run_start_time: Pipeline run start timestamp.
        run_end_time: Pipeline run end timestamp.
        cache: Intermediate results storage.
    """

    # Configuration
    config: Any = None

    # Data
    raw_data: Optional[pd.DataFrame] = None
    factor_data: Optional[pd.DataFrame] = None
    processed_data: Optional[pd.DataFrame] = None
    labels: Optional[pd.Series] = None

    # Model
    model: Any = None
    model_metrics: Dict[str, float] = field(default_factory=dict)

    # Predictions
    predictions: Optional[pd.Series] = None

    # Market timing
    timing_signal: Optional[Dict] = None
    timing_position: float = 1.0

    # Portfolio
    selected_stocks: List[str] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)

    # Backtest
    backtest_result: Optional[Any] = None
    performance_metrics: Dict[str, float] = field(default_factory=dict)

    # Run state
    current_date: Optional[str] = None
    trade_dates: List[str] = field(default_factory=list)
    run_start_time: Optional[datetime] = None
    run_end_time: Optional[datetime] = None

    # Intermediate storage
    cache: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from cache.

        Args:
            key: Cache key.
            default: Default value if key not found.

        Returns:
            Cached value or default.
        """
        return self.cache.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in cache.

        Args:
            key: Cache key.
            value: Value to store.
        """
        self.cache[key] = value

    def has(self, key: str) -> bool:
        """Check if a key exists in cache.

        Args:
            key: Cache key to check.

        Returns:
            True if key exists, False otherwise.
        """
        return key in self.cache

    def summary(self) -> Dict[str, Any]:
        """Return a summary of the current run state.

        Returns:
            Dictionary containing key run information.
        """
        return {
            "current_date": self.current_date,
            "n_stocks_in_pool": (
                len(self.factor_data) if self.factor_data is not None else 0
            ),
            "n_selected": len(self.selected_stocks),
            "timing_position": self.timing_position,
            "model_metrics": self.model_metrics,
            "performance_metrics": self.performance_metrics,
            "run_duration": (
                str(self.run_end_time - self.run_start_time)
                if self.run_end_time and self.run_start_time
                else None
            ),
        }

    def reset(self) -> None:
        """Reset context to initial state, preserving configuration."""
        config = self.config
        self.__init__(config=config)
