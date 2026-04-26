"""
ML pipeline orchestrator for executing the complete quantitative strategy workflow.

This module provides the MLPipeline class that orchestrates and executes the full
quantitative strategy pipeline: data loading, factor computation, preprocessing,
label construction, model training, prediction, portfolio construction, and backtesting.
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from .config import PipelineConfig
from .context import RunContext
from .registry import (
    DATA_SOURCE_REGISTRY,
    FACTOR_REGISTRY,
    LABEL_REGISTRY,
    MODEL_REGISTRY,
    PREPROCESSOR_REGISTRY,
    STRATEGY_REGISTRY,
)

logger = logging.getLogger(__name__)


class MLPipeline:
    """Quantitative strategy pipeline orchestrator.

    Responsible for orchestrating and executing the complete quantitative
    strategy workflow:
    1. Load configuration
    2. Fetch data
    3. Compute factors
    4. Preprocess data
    5. Build labels
    6. Train model
    7. Predict
    8. Select stocks
    9. Backtest (optional)

    Example:
        config = PipelineConfig.from_yaml('config.yaml')
        pipeline = MLPipeline(config)
        result = pipeline.run()
    """

    def __init__(self, config: PipelineConfig) -> None:
        """Initialize the pipeline.

        Args:
            config: Pipeline configuration object.
        """
        self.config = config
        self.context = RunContext(config=config)
        self._components: Dict[str, Any] = {}

        np.random.seed(config.random_seed)

        logger.info(f"Pipeline initialized with config: {config}")

    def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """Execute the complete pipeline.

        Args:
            dry_run: If True, skip model training and backtesting.

        Returns:
            Dictionary containing run results.

        Raises:
            Exception: If any pipeline step fails.
        """
        start = time.time()
        self.context.run_start_time = pd.Timestamp.now()

        try:
            logger.info("=" * 50)
            logger.info("Starting pipeline run")
            logger.info("=" * 50)

            # Step 1: Get trade calendar and stock pool
            self._get_trade_dates()
            self._get_stock_pool()

            # Step 2: Fetch data
            self._get_data()

            # Step 3: Compute factors
            self._compute_factors()

            # Step 4: Preprocess
            self._preprocess()

            if not dry_run:
                # Step 5: Build labels
                self._build_labels()

                # Step 6: Train model
                self._train_model()

                # Step 7: Predict
                self._predict()

            # Step 8: Build portfolio
            self._build_portfolio()

            if not dry_run:
                # Step 9: Run backtest
                self._run_backtest()

            self.context.run_end_time = pd.Timestamp.now()
            duration = time.time() - start

            logger.info(f"Pipeline completed in {duration:.2f}s")
            logger.info(f"Summary: {self.context.summary()}")

            return self._collect_results()

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise

    def _get_trade_dates(self) -> None:
        """Fetch trading calendar from data source."""
        logger.info("Step 1: Getting trade dates...")
        data_source = DATA_SOURCE_REGISTRY.create(
            self.config.data.source,
            config=self.config.data,
        )
        self.context.trade_dates = data_source.get_trade_dates(
            self.config.data.start_date,
            self.config.data.end_date,
        )
        logger.info(f"Found {len(self.context.trade_dates)} trade dates")

    def _get_stock_pool(self) -> None:
        """Fetch stock pool from index constituents."""
        logger.info("Step 2: Getting stock pool...")
        data_source = DATA_SOURCE_REGISTRY.create(
            self.config.data.source,
            config=self.config.data,
        )
        stock_pool = data_source.get_index_components(
            self.config.data.index,
            date=self.context.trade_dates[-1] if self.context.trade_dates else None,
        )
        self.context.cache["stock_pool"] = stock_pool
        logger.info(f"Stock pool size: {len(stock_pool)}")

    def _get_data(self) -> None:
        """Fetch stock data from data source."""
        logger.info("Step 3: Getting data...")
        data_source = DATA_SOURCE_REGISTRY.create(
            self.config.data.source,
            config=self.config.data,
        )
        self.context.raw_data = data_source.get_stock_data(
            stocks=self.context.cache["stock_pool"],
            dates=self.context.trade_dates,
        )
        logger.info(f"Raw data shape: {self.context.raw_data.shape}")

    def _compute_factors(self) -> None:
        """Compute all configured factors."""
        logger.info("Step 4: Computing factors...")
        factor_dfs = []

        for factor_name in self.config.factors.factors:
            factor_cls = FACTOR_REGISTRY.get(factor_name)
            factor = factor_cls(**self.config.factors.params.get(factor_name, {}))

            for date in self.context.trade_dates:
                cross_section = self.context.raw_data[
                    self.context.raw_data["date"] == date
                ]
                factor_values = factor.compute(cross_section, date)
                factor_values.name = factor_name
                factor_dfs.append(factor_values.reset_index().assign(date=date))

        if factor_dfs:
            self.context.factor_data = pd.concat(factor_dfs, ignore_index=True)
            logger.info(f"Factor data shape: {self.context.factor_data.shape}")

    def _preprocess(self) -> None:
        """Apply preprocessing to factor data."""
        logger.info("Step 5: Preprocessing...")
        processed_chunks = []

        for date in self.context.trade_dates:
            cross_section = self.context.factor_data[
                self.context.factor_data["date"] == date
            ].copy()

            preprocessor_cls = PREPROCESSOR_REGISTRY.get("default")
            preprocessor = preprocessor_cls(**self.config.preprocess.__dict__)
            processed = preprocessor.process(cross_section)

            processed_chunks.append(processed)

        self.context.processed_data = pd.concat(processed_chunks, ignore_index=True)
        logger.info(f"Processed data shape: {self.context.processed_data.shape}")

    def _build_labels(self) -> None:
        """Build labels for supervised learning."""
        logger.info("Step 6: Building labels...")
        label_builder = LABEL_REGISTRY.create(
            self.config.label.method,
            **self.config.label.__dict__,
        )

        labels = []
        for date in self.context.trade_dates[: -self.config.label.holding_period]:
            future_date_idx = (
                self.context.trade_dates.index(date) + self.config.label.holding_period
            )
            if future_date_idx >= len(self.context.trade_dates):
                break

            future_date = self.context.trade_dates[future_date_idx]
            label = label_builder.build(
                self.context.raw_data,
                date,
                holding_period=self.config.label.holding_period,
            )
            label.name = "label"
            labels.append(label.reset_index().assign(date=date))

        if labels:
            self.context.labels = pd.concat(labels, ignore_index=True)
            logger.info(f"Labels shape: {self.context.labels.shape}")

    def _train_model(self) -> None:
        """Train the machine learning model."""
        logger.info("Step 7: Training model...")
        train_data = self.context.processed_data.merge(
            self.context.labels,
            on=["date", "code"],
            how="inner",
        )

        feature_cols = list(self.config.factors.factors)
        X = train_data[feature_cols]
        y = train_data["label"]

        model = MODEL_REGISTRY.create(
            self.config.model.name,
            **self.config.model.params,
        )
        model.train(X, y)

        metrics = model.evaluate(X, y)
        self.context.model = model
        self.context.model_metrics = metrics

        logger.info(f"Model metrics: {metrics}")

    def _predict(self) -> None:
        """Generate predictions using the trained model."""
        logger.info("Step 8: Predicting...")
        feature_cols = list(self.config.factors.factors)
        X = self.context.processed_data[feature_cols]

        predictions = self.context.model.predict(X)
        self.context.predictions = pd.Series(
            predictions,
            index=self.context.processed_data.index,
            name="prediction",
        )
        logger.info(f"Predictions shape: {self.context.predictions.shape}")

    def _build_portfolio(self) -> None:
        """Construct the portfolio from predictions."""
        logger.info("Step 9: Building portfolio...")
        latest_date = self.context.trade_dates[-1]
        latest_preds = self.context.processed_data[
            self.context.processed_data["date"] == latest_date
        ].copy()
        latest_preds["prediction"] = self.context.predictions[
            self.context.processed_data[
                self.context.processed_data["date"] == latest_date
            ].index
        ].values

        # Select stocks
        strategy = STRATEGY_REGISTRY.create("top_n")
        selected = strategy.select_stocks(
            latest_preds,
            latest_date,
            n_stocks=self.config.portfolio.n_stocks,
            min_stocks=self.config.portfolio.min_stocks,
        )
        self.context.selected_stocks = selected

        # Compute weights
        weights = strategy.compute_weights(
            latest_preds,
            selected,
            method=self.config.portfolio.weight_method,
        )
        self.context.weights = weights

        logger.info(f"Selected {len(selected)} stocks")

    def _run_backtest(self) -> None:
        """Run backtest (placeholder, handled by backtest module)."""
        logger.info("Step 10: Running backtest...")
        pass

    def _collect_results(self) -> Dict[str, Any]:
        """Collect and return pipeline results.

        Returns:
            Dictionary containing all pipeline results.
        """
        return {
            "context": self.context,
            "selected_stocks": self.context.selected_stocks,
            "weights": self.context.weights,
            "model_metrics": self.context.model_metrics,
            "performance_metrics": self.context.performance_metrics,
            "summary": self.context.summary(),
        }

    def save(self, path: str) -> None:
        """Save pipeline state to disk.

        Args:
            path: File path to save the pipeline state.
        """
        joblib.dump(
            {
                "config": self.config,
                "model": self.context.model,
                "context": self.context,
            },
            path,
        )
        logger.info(f"Pipeline saved to {path}")

    @classmethod
    def load(cls, path: str) -> "MLPipeline":
        """Load pipeline state from disk.

        Args:
            path: File path to load the pipeline state from.

        Returns:
            MLPipeline instance with loaded state.
        """
        data = joblib.load(path)
        pipeline = cls(data["config"])
        pipeline.context = data["context"]
        pipeline.context.model = data["model"]
        logger.info(f"Pipeline loaded from {path}")
        return pipeline
