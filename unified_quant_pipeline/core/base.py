"""
Base component abstractions for the unified quantitative pipeline.

This module defines the abstract base classes for all pipeline components:
- BaseComponent: Root abstract class for all components
- BaseFactor: Factor computation base class
- BasePreprocessor: Data preprocessing base class
- BaseLabelBuilder: Label construction base class
- BaseModel: Machine learning model base class
- BaseStrategy: Quantitative strategy base class
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class BaseComponent(ABC):
    """Abstract base class for all pipeline components.

    All components in the pipeline inherit from this class and must implement
    fit, transform, and predict methods.
    """

    name: str = "base"

    @abstractmethod
    def fit(self, data: Any, **kwargs: Any) -> None:
        """Fit/train the component on data.

        Args:
            data: Input data for fitting.
            **kwargs: Additional keyword arguments.
        """
        pass

    @abstractmethod
    def transform(self, data: Any, **kwargs: Any) -> Any:
        """Transform/process the data.

        Args:
            data: Input data to transform.
            **kwargs: Additional keyword arguments.

        Returns:
            Transformed data.
        """
        pass

    @abstractmethod
    def predict(self, data: Any, **kwargs: Any) -> Any:
        """Generate predictions or outputs.

        Args:
            data: Input data for prediction.
            **kwargs: Additional keyword arguments.

        Returns:
            Prediction results.
        """
        pass

    def get_params(self) -> Dict[str, Any]:
        """Return component parameters.

        Returns:
            Dictionary of component parameters.
        """
        return {}

    def set_params(self, **params: Any) -> "BaseComponent":
        """Set component parameters.

        Args:
            **params: Keyword arguments of parameter names and values.

        Returns:
            Self for method chaining.
        """
        for k, v in params.items():
            if hasattr(self, k):
                setattr(self, k, v)
        return self


class BaseFactor(BaseComponent):
    """Base class for factor computation.

    Factors are used to compute alpha signals from market data. Each factor
    operates on cross-sectional data and returns factor values per stock.
    """

    name: str = "factor"
    requires: List[str] = []

    @abstractmethod
    def compute(self, data: pd.DataFrame, date: str, **kwargs: Any) -> pd.Series:
        """Compute factor values for a given date.

        Args:
            data: Cross-sectional data containing a date column.
            date: Current rebalancing date.
            **kwargs: Additional keyword arguments.

        Returns:
            Series with stock codes as index and factor values as values.
        """
        pass

    def fit(self, data: Any, **kwargs: Any) -> None:
        """Fit the factor (no-op by default)."""
        pass

    def transform(self, data: Any, **kwargs: Any) -> Any:
        """Transform data (delegates to compute for factors)."""
        return data

    def predict(self, data: Any, **kwargs: Any) -> Any:
        """Predict factor values (delegates to compute for factors)."""
        return data


class BasePreprocessor(BaseComponent):
    """Base class for data preprocessing.

    Preprocessors handle data cleaning operations such as winsorization,
    missing value imputation, and standardization.
    """

    name: str = "preprocessor"

    @abstractmethod
    def process(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Process the data (winsorize, fill NA, standardize, etc.).

        Args:
            data: Input DataFrame to process.
            **kwargs: Additional keyword arguments.

        Returns:
            Processed DataFrame.
        """
        pass

    def winsorize(
        self, series: pd.Series, method: str = "mad", n: float = 3.0
    ) -> pd.Series:
        """Winsorize extreme values in a series.

        Args:
            series: Input series.
            method: Winsorization method ('mad' or 'quantile').
            n: Number of MADs or quantile threshold.

        Returns:
            Winsorized series.
        """
        if method == "mad":
            median = series.median()
            mad = (series - median).abs().median()
            lower = median - n * mad
            upper = median + n * mad
        elif method == "quantile":
            lower = series.quantile(n / 100)
            upper = series.quantile(1 - n / 100)
        else:
            raise ValueError(f"Unknown winsorize method: {method}")
        return series.clip(lower=lower, upper=upper)

    def fill_na(self, series: pd.Series, method: str = "median") -> pd.Series:
        """Fill missing values in a series.

        Args:
            series: Input series.
            method: Fill method ('median', 'mean', or 'zero').

        Returns:
            Series with missing values filled.
        """
        if method == "median":
            return series.fillna(series.median())
        elif method == "mean":
            return series.fillna(series.mean())
        elif method == "zero":
            return series.fillna(0.0)
        else:
            raise ValueError(f"Unknown fill_na method: {method}")

    def standardize(self, series: pd.Series) -> pd.Series:
        """Z-Score standardization.

        Args:
            series: Input series.

        Returns:
            Standardized series with mean 0 and std 1.
        """
        std = series.std()
        if std == 0:
            return series - series.mean()
        return (series - series.mean()) / std

    def fit(self, data: Any, **kwargs: Any) -> None:
        """Fit the preprocessor (no-op by default)."""
        pass

    def transform(self, data: Any, **kwargs: Any) -> Any:
        """Transform data (delegates to process for preprocessors)."""
        return data

    def predict(self, data: Any, **kwargs: Any) -> Any:
        """Predict (not applicable for preprocessors)."""
        return data


class BaseLabelBuilder(BaseComponent):
    """Base class for label construction.

    Label builders construct training labels from future returns,
    supporting both classification and regression tasks.
    """

    name: str = "label"

    @abstractmethod
    def build(
        self, data: pd.DataFrame, date: str, holding_period: int = 5, **kwargs: Any
    ) -> pd.Series:
        """Build labels from data.

        Args:
            data: Data containing future returns.
            date: Current date.
            holding_period: Holding period in trading days.
            **kwargs: Additional keyword arguments.

        Returns:
            Series with stock codes as index and labels (0/1 or returns) as values.
        """
        pass

    def fit(self, data: Any, **kwargs: Any) -> None:
        """Fit the label builder (no-op by default)."""
        pass

    def transform(self, data: Any, **kwargs: Any) -> Any:
        """Transform data (delegates to build for label builders)."""
        return data

    def predict(self, data: Any, **kwargs: Any) -> Any:
        """Predict (not applicable for label builders)."""
        return data


class BaseModel(BaseComponent):
    """Base class for machine learning models.

    Models provide training, prediction, evaluation, and persistence
    capabilities for the quantitative pipeline.
    """

    name: str = "model"

    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs: Any) -> None:
        """Train the model.

        Args:
            X: Feature matrix.
            y: Target labels.
            **kwargs: Additional keyword arguments.
        """
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame, **kwargs: Any) -> np.ndarray:
        """Generate predictions.

        Args:
            X: Feature matrix.
            **kwargs: Additional keyword arguments.

        Returns:
            Prediction array.
        """
        pass

    def evaluate(
        self, X: pd.DataFrame, y: pd.Series, **kwargs: Any
    ) -> Dict[str, float]:
        """Evaluate the model.

        Args:
            X: Feature matrix.
            y: True labels.
            **kwargs: Additional keyword arguments.

        Returns:
            Dictionary of evaluation metrics.
        """
        return {}

    def feature_importance(self) -> Dict[str, float]:
        """Get feature importance.

        Returns:
            Dictionary mapping feature names to importance scores.
        """
        return {}

    def save(self, path: str) -> None:
        """Save the model to disk.

        Args:
            path: File path to save the model.
        """
        import joblib

        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str) -> "BaseModel":
        """Load a model from disk.

        Args:
            path: File path to load the model from.

        Returns:
            Loaded model instance.
        """
        import joblib

        return joblib.load(path)

    def fit(self, data: Any, **kwargs: Any) -> None:
        """Fit the model (delegates to train for models)."""
        pass

    def transform(self, data: Any, **kwargs: Any) -> Any:
        """Transform data (not applicable for models)."""
        return data


class BaseStrategy(BaseComponent):
    """Base class for quantitative strategies.

    Strategies define stock selection, weighting, and rebalancing logic
    for portfolio construction.
    """

    name: str = "strategy"

    @abstractmethod
    def select_stocks(self, data: pd.DataFrame, date: str, **kwargs: Any) -> List[str]:
        """Select stocks for the portfolio.

        Args:
            data: Input data with factor scores and other signals.
            date: Current rebalancing date.
            **kwargs: Additional keyword arguments.

        Returns:
            List of selected stock codes.
        """
        pass

    def compute_weights(
        self, data: pd.DataFrame, selected: List[str], **kwargs: Any
    ) -> Dict[str, float]:
        """Compute portfolio weights for selected stocks.

        Args:
            data: Input data.
            selected: List of selected stock codes.
            **kwargs: Additional keyword arguments.

        Returns:
            Dictionary mapping stock codes to weights.
        """
        return {s: 1.0 / len(selected) for s in selected}

    def rebalance(
        self,
        current_holdings: Dict[str, float],
        target_weights: Dict[str, float],
        **kwargs: Any,
    ) -> List[tuple]:
        """Generate rebalancing instructions.

        Args:
            current_holdings: Current portfolio holdings {stock: weight}.
            target_weights: Target portfolio weights {stock: weight}.
            **kwargs: Additional keyword arguments.

        Returns:
            List of (stock_code, target_amount) tuples.
        """
        pass

    def fit(self, data: Any, **kwargs: Any) -> None:
        """Fit the strategy (no-op by default)."""
        pass

    def transform(self, data: Any, **kwargs: Any) -> Any:
        """Transform data (not applicable for strategies)."""
        return data

    def predict(self, data: Any, **kwargs: Any) -> Any:
        """Predict (delegates to select_stocks for strategies)."""
        return data
