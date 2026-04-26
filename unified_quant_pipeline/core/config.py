"""
Configuration system for the unified quantitative pipeline.

This module provides dataclass-based configuration objects that support
YAML serialization and deserialization for easy persistence and sharing.
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class DataConfig:
    """Data source configuration.

    Attributes:
        source: Data source provider ('akshare' or 'jqdata').
        index: Stock pool benchmark index code.
        start_date: Start date for data fetching.
        end_date: End date for data fetching (empty means latest).
        frequency: Data frequency ('daily', 'weekly', or 'monthly').
        cache_dir: Directory for caching downloaded data.
        force_update: Whether to force re-download cached data.
    """

    source: str = "akshare"
    index: str = "000300"
    start_date: str = "2020-01-01"
    end_date: str = ""
    frequency: str = "daily"
    cache_dir: str = "./data_cache"
    force_update: bool = False


@dataclass
class FactorConfig:
    """Factor configuration.

    Attributes:
        factors: List of factor names to compute.
        params: Factor-specific parameters {factor_name: {param: value}}.
    """

    factors: List[str] = field(default_factory=lambda: ["momentum", "value", "quality"])
    params: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class PreprocessConfig:
    """Preprocessing configuration.

    Attributes:
        winsorize_method: Method for winsorization ('mad' or 'quantile').
        winsorize_n: Threshold parameter for winsorization.
        fill_na_method: Method for filling missing values ('median', 'mean', or 'zero').
        standardize_method: Method for standardization ('zscore').
        neutralize_by: Column name for industry neutralization (None to skip).
    """

    winsorize_method: str = "mad"
    winsorize_n: float = 3.0
    fill_na_method: str = "median"
    standardize_method: str = "zscore"
    neutralize_by: Optional[str] = None


@dataclass
class LabelConfig:
    """Label construction configuration.

    Attributes:
        method: Label type ('classification' or 'regression').
        top_pct: Top percentile threshold for positive samples in classification.
        holding_period: Holding period in trading days.
        benchmark: Benchmark index code for excess return calculation.
    """

    method: str = "classification"
    top_pct: float = 0.3
    holding_period: int = 5
    benchmark: str = "000300"


@dataclass
class ModelConfig:
    """Machine learning model configuration.

    Attributes:
        name: Model type name.
        params: Model-specific hyperparameters.
        train_window: Training window size in trading days.
        retrain_freq: Model retraining frequency ('daily', 'weekly', or 'monthly').
        cv_folds: Number of cross-validation folds.
    """

    name: str = "random_forest"
    params: Dict[str, Any] = field(
        default_factory=lambda: {"n_estimators": 200, "max_depth": 5}
    )
    train_window: int = 252
    retrain_freq: str = "monthly"
    cv_folds: int = 5


@dataclass
class TimingConfig:
    """Market timing configuration.

    Attributes:
        enabled: Whether market timing is active.
        models: List of timing model names.
        fusion_method: Method to combine timing signals ('weighted', 'vote', or 'resonance').
        position_method: Method to determine position size ('strength').
    """

    enabled: bool = False
    models: List[str] = field(default_factory=lambda: ["rsrs", "sentiment"])
    fusion_method: str = "weighted"
    position_method: str = "strength"


@dataclass
class PortfolioConfig:
    """Portfolio construction configuration.

    Attributes:
        n_stocks: Target number of stocks in the portfolio.
        weight_method: Weighting method ('equal', 'market_cap', or 'score').
        max_single_weight: Maximum weight for a single stock.
        max_turnover: Maximum portfolio turnover rate.
        min_stocks: Minimum number of stocks required.
    """

    n_stocks: int = 10
    weight_method: str = "equal"
    max_single_weight: float = 0.15
    max_turnover: float = 0.5
    min_stocks: int = 5


@dataclass
class BacktestConfig:
    """Backtesting configuration.

    Attributes:
        initial_capital: Starting capital for the backtest.
        commission: Commission rate per trade.
        slippage: Slippage rate per trade.
        benchmark: Benchmark index code for performance comparison.
        rebalance_freq: Portfolio rebalancing frequency ('daily', 'weekly', or 'monthly').
    """

    initial_capital: float = 1_000_000
    commission: float = 0.0003
    slippage: float = 0.002
    benchmark: str = "000300"
    rebalance_freq: str = "weekly"


@dataclass
class RiskConfig:
    """Risk management configuration.

    Attributes:
        max_drawdown_limit: Maximum allowed drawdown threshold.
        stop_loss_pct: Stop-loss percentage per position.
        max_position_pct: Maximum position size as percentage.
        volatility_target: Target portfolio volatility (None to disable).
    """

    max_drawdown_limit: float = 0.20
    stop_loss_pct: float = 0.08
    max_position_pct: float = 0.15
    volatility_target: Optional[float] = None


@dataclass
class PipelineConfig:
    """Top-level pipeline configuration.

    Aggregates all sub-configurations for the quantitative pipeline.

    Attributes:
        data: Data source configuration.
        factors: Factor computation configuration.
        preprocess: Data preprocessing configuration.
        label: Label construction configuration.
        model: Machine learning model configuration.
        timing: Market timing configuration.
        portfolio: Portfolio construction configuration.
        backtest: Backtesting configuration.
        risk: Risk management configuration.
        random_seed: Random seed for reproducibility.
        log_level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR').
    """

    data: DataConfig = field(default_factory=DataConfig)
    factors: FactorConfig = field(default_factory=FactorConfig)
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)
    label: LabelConfig = field(default_factory=LabelConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    random_seed: int = 42
    log_level: str = "INFO"

    @classmethod
    def from_yaml(cls, path: str) -> "PipelineConfig":
        """Load configuration from a YAML file.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            PipelineConfig instance loaded from the file.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls._from_dict(data)

    def to_yaml(self, path: str) -> None:
        """Save configuration to a YAML file.

        Args:
            path: Path to save the YAML configuration file.
        """
        data = asdict(self)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "PipelineConfig":
        """Construct a PipelineConfig from a dictionary.

        Args:
            data: Dictionary containing configuration values.

        Returns:
            PipelineConfig instance.
        """
        return cls(
            data=DataConfig(**data.get("data", {})),
            factors=FactorConfig(**data.get("factors", {})),
            preprocess=PreprocessConfig(**data.get("preprocess", {})),
            label=LabelConfig(**data.get("label", {})),
            model=ModelConfig(**data.get("model", {})),
            timing=TimingConfig(**data.get("timing", {})),
            portfolio=PortfolioConfig(**data.get("portfolio", {})),
            backtest=BacktestConfig(**data.get("backtest", {})),
            risk=RiskConfig(**data.get("risk", {})),
            random_seed=data.get("random_seed", 42),
            log_level=data.get("log_level", "INFO"),
        )
