"""Global configuration for the quantitative trading framework.

Provides a dataclass-based configuration system that supports both
programmatic construction and YAML file loading.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class DataSourceConfig:
    """Configuration for market data sources.

    Attributes:
        source_type: Data source backend (akshare, tushare, jqdata).
        tushare_token: API token for Tushare (required if source_type=tushare).
        jqdata_user: Username for JQData (required if source_type=jqdata).
        jqdata_password: Password for JQData (required if source_type=jqdata).
        cache_dir: Directory for caching downloaded data.
        timeout: Request timeout in seconds.
        retry_count: Number of retries on failed requests.
    """

    source_type: str = "akshare"
    tushare_token: Optional[str] = None
    jqdata_user: Optional[str] = None
    jqdata_password: Optional[str] = None
    cache_dir: str = "data_cache"
    timeout: int = 30
    retry_count: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "source_type": self.source_type,
            "tushare_token": self.tushare_token,
            "jqdata_user": self.jqdata_user,
            "jqdata_password": self.jqdata_password,
            "cache_dir": self.cache_dir,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DataSourceConfig:
        """Create instance from a dictionary.

        Args:
            data: Dictionary with configuration keys.

        Returns:
            DataSourceConfig instance.
        """
        return cls(
            source_type=data.get("source_type", "akshare"),
            tushare_token=data.get("tushare_token"),
            jqdata_user=data.get("jqdata_user"),
            jqdata_password=data.get("jqdata_password"),
            cache_dir=data.get("cache_dir", "data_cache"),
            timeout=data.get("timeout", 30),
            retry_count=data.get("retry_count", 3),
        )


@dataclass
class CostConfig:
    """Configuration for transaction cost modeling.

    Attributes:
        commission_rate: Broker commission rate as a fraction.
        min_commission: Minimum commission per trade in currency units.
        stamp_duty_rate: Stamp duty rate (sell only for A-shares).
        transfer_fee_rate: Transfer fee rate.
        slippage_rate: Slippage rate as a fraction.
    """

    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_duty_rate: float = 0.001
    transfer_fee_rate: float = 0.00002
    slippage_rate: float = 0.002

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "commission_rate": self.commission_rate,
            "min_commission": self.min_commission,
            "stamp_duty_rate": self.stamp_duty_rate,
            "transfer_fee_rate": self.transfer_fee_rate,
            "slippage_rate": self.slippage_rate,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CostConfig:
        """Create instance from a dictionary.

        Args:
            data: Dictionary with configuration keys.

        Returns:
            CostConfig instance.
        """
        return cls(
            commission_rate=data.get("commission_rate", 0.0003),
            min_commission=data.get("min_commission", 5.0),
            stamp_duty_rate=data.get("stamp_duty_rate", 0.001),
            transfer_fee_rate=data.get("transfer_fee_rate", 0.00002),
            slippage_rate=data.get("slippage_rate", 0.002),
        )


@dataclass
class BacktestConfig:
    """Configuration for backtest execution.

    Attributes:
        initial_capital: Starting capital for the backtest.
        benchmark: Benchmark index code (e.g., 000300.XSHG for CSI 300).
        frequency: Bar frequency (daily, weekly, monthly).
        max_symbols: Maximum number of symbols to include when auto-selecting.
    """

    initial_capital: float = 1_000_000.0
    benchmark: str = "000300.XSHG"
    frequency: str = "daily"
    max_symbols: int = 30

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "initial_capital": self.initial_capital,
            "benchmark": self.benchmark,
            "frequency": self.frequency,
            "max_symbols": self.max_symbols,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BacktestConfig:
        """Create instance from a dictionary.

        Args:
            data: Dictionary with configuration keys.

        Returns:
            BacktestConfig instance.
        """
        return cls(
            initial_capital=data.get("initial_capital", 1_000_000.0),
            benchmark=data.get("benchmark", "000300.XSHG"),
            frequency=data.get("frequency", "daily"),
            max_symbols=data.get("max_symbols", 30),
        )


@dataclass
class DateRangeConfig:
    """Configuration for the backtest date range.

    Attributes:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
    """

    start_date: str = "2020-01-01"
    end_date: str = "2024-12-31"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DateRangeConfig:
        """Create instance from a dictionary.

        Args:
            data: Dictionary with configuration keys.

        Returns:
            DateRangeConfig instance.
        """
        return cls(
            start_date=data.get("start_date", "2020-01-01"),
            end_date=data.get("end_date", "2024-12-31"),
        )


@dataclass
class LoggingConfig:
    """Configuration for the logging system.

    Attributes:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Path to the log file. None to disable file logging.
        log_dir: Directory for log files.
        max_bytes: Maximum size of a single log file before rotation (bytes).
        backup_count: Number of rotated log files to keep.
        fmt: Log message format string.
        datefmt: Date format string for log timestamps.
    """

    level: str = "INFO"
    log_file: Optional[str] = None
    log_dir: str = "logs"
    max_bytes: int = 10_485_760
    backup_count: int = 5
    fmt: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt: str = "%Y-%m-%d %H:%M:%S"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "level": self.level,
            "log_file": self.log_file,
            "log_dir": self.log_dir,
            "max_bytes": self.max_bytes,
            "backup_count": self.backup_count,
            "fmt": self.fmt,
            "datefmt": self.datefmt,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LoggingConfig:
        """Create instance from a dictionary.

        Args:
            data: Dictionary with configuration keys.

        Returns:
            LoggingConfig instance.
        """
        return cls(
            level=data.get("level", "INFO"),
            log_file=data.get("log_file"),
            log_dir=data.get("log_dir", "logs"),
            max_bytes=data.get("max_bytes", 10_485_760),
            backup_count=data.get("backup_count", 5),
            fmt=data.get("fmt", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
            datefmt=data.get("datefmt", "%Y-%m-%d %H:%M:%S"),
        )


@dataclass
class StrategyConfig:
    """Configuration for a trading strategy.

    Attributes:
        name: Strategy class name.
        module: Module path for custom strategy (optional).
        params: Strategy-specific parameters.
    """

    name: str = "DefaultStrategy"
    module: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "module": self.module,
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StrategyConfig:
        """Create instance from a dictionary.

        Args:
            data: Dictionary with configuration keys.

        Returns:
            StrategyConfig instance.
        """
        return cls(
            name=data.get("name", "DefaultStrategy"),
            module=data.get("module"),
            params=data.get("params", {}),
        )


@dataclass
class SignalConfig:
    """Configuration for signal generation.

    Attributes:
        upper_threshold: Threshold for long/buy signals.
        lower_threshold: Threshold for short/sell signals.
    """

    upper_threshold: float = 0.7
    lower_threshold: float = 0.3

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "upper_threshold": self.upper_threshold,
            "lower_threshold": self.lower_threshold,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SignalConfig:
        """Create instance from a dictionary.

        Args:
            data: Dictionary with configuration keys.

        Returns:
            SignalConfig instance.
        """
        return cls(
            upper_threshold=data.get("upper_threshold", 0.7),
            lower_threshold=data.get("lower_threshold", 0.3),
        )


@dataclass
class OptimizeConfig:
    """Configuration for parameter optimization.

    Attributes:
        param_grid: Dictionary mapping parameter names to lists of values to test.
    """

    param_grid: Dict[str, List[Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {"param_grid": dict(self.param_grid)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OptimizeConfig:
        """Create instance from a dictionary.

        Args:
            data: Dictionary with configuration keys.

        Returns:
            OptimizeConfig instance.
        """
        return cls(param_grid=data.get("param_grid", {}))


@dataclass
class Settings:
    """Top-level configuration container for the quantitative trading framework.

    Combines all sub-configurations into a single object that can be
    constructed programmatically or loaded from a YAML file.

    Attributes:
        data_source: Data source configuration.
        backtest: Backtest execution configuration.
        date_range: Date range configuration.
        logging: Logging configuration.
        cost: Transaction cost configuration.
        strategy: Strategy configuration.
        signals: Signal generation configuration.
        optimize: Parameter optimization configuration.
        symbols: List of stock symbols to trade (empty = auto-fetch).
        factors: List of factor names to calculate.
    """

    data_source: DataSourceConfig = field(default_factory=DataSourceConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    date_range: DateRangeConfig = field(default_factory=DateRangeConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    signals: SignalConfig = field(default_factory=SignalConfig)
    optimize: OptimizeConfig = field(default_factory=OptimizeConfig)
    symbols: List[str] = field(default_factory=list)
    factors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert all settings to a nested dictionary.

        Returns:
            Dictionary suitable for YAML serialization or pipeline consumption.
        """
        result: Dict[str, Any] = {
            "data_source": self.data_source.source_type,
            "data": self.date_range.to_dict(),
            "initial_capital": self.backtest.initial_capital,
            "max_symbols": self.backtest.max_symbols,
            "benchmark": self.backtest.benchmark,
            "symbols": list(self.symbols),
            "factors": list(self.factors),
            "strategy": self.strategy.to_dict(),
            "signals": self.signals.to_dict(),
            "cost": self.cost.to_dict(),
            "logging": self.logging.to_dict(),
        }
        if self.optimize.param_grid:
            result["optimize"] = self.optimize.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Settings:
        """Create Settings from a flat or nested dictionary.

        Supports both the nested structure produced by ``to_dict()`` and
        the flat structure commonly found in YAML strategy files.

        Args:
            data: Configuration dictionary.

        Returns:
            Settings instance.
        """
        ds_raw = data.get("data_source", {})
        if isinstance(ds_raw, str):
            data_source = DataSourceConfig(source_type=ds_raw)
        elif isinstance(ds_raw, dict):
            data_source = DataSourceConfig.from_dict(ds_raw)
        else:
            data_source = DataSourceConfig()

        date_data = data.get("data", {})
        date_range = DateRangeConfig(
            start_date=date_data.get("start_date", "2020-01-01"),
            end_date=date_data.get("end_date", "2024-12-31"),
        )

        backtest = BacktestConfig(
            initial_capital=data.get("initial_capital", 1_000_000.0),
            benchmark=data.get("benchmark", "000300.XSHG"),
            max_symbols=data.get("max_symbols", 30),
        )

        cost = CostConfig.from_dict(data.get("cost", {}))
        strategy = StrategyConfig.from_dict(data.get("strategy", {}))
        signals = SignalConfig.from_dict(data.get("signals", {}))
        logging_cfg = LoggingConfig.from_dict(data.get("logging", {}))
        optimize = OptimizeConfig.from_dict(data.get("optimize", {}))

        return cls(
            data_source=data_source,
            backtest=backtest,
            date_range=date_range,
            logging=logging_cfg,
            cost=cost,
            strategy=strategy,
            signals=signals,
            optimize=optimize,
            symbols=data.get("symbols", []),
            factors=data.get("factors", []),
        )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> Settings:
        """Load settings from a YAML configuration file.

        Args:
            yaml_path: Path to the YAML file.

        Returns:
            Settings instance populated from the YAML file.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
            ValueError: If the YAML content is invalid.
        """
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

        with open(path, "r", encoding="utf-8") as fh:
            try:
                data = yaml.safe_load(fh)
            except yaml.YAMLError as exc:
                raise ValueError(f"Invalid YAML in {yaml_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError(
                f"YAML file must contain a mapping at the top level, "
                f"got {type(data).__name__}"
            )

        logger.info(f"Loaded configuration from {yaml_path}")
        return cls.from_dict(data)

    def to_yaml(self, yaml_path: str) -> None:
        """Save settings to a YAML configuration file.

        Args:
            yaml_path: Destination path for the YAML file.
        """
        path = Path(yaml_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(
                self.to_dict(),
                fh,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

        logger.info(f"Saved configuration to {yaml_path}")

    def to_pipeline_config(self) -> Dict[str, Any]:
        """Convert settings to the flat dictionary format expected by QuantPipeline.

        Returns:
            Dictionary compatible with QuantPipeline and load_config().
        """
        return {
            "data_source": self.data_source.source_type,
            "data": self.date_range.to_dict(),
            "initial_capital": self.backtest.initial_capital,
            "max_symbols": self.backtest.max_symbols,
            "symbols": list(self.symbols),
            "factors": list(self.factors),
            "strategy": self.strategy.to_dict(),
            "signals": self.signals.to_dict(),
            "cost": self.cost.to_dict(),
            "optimize": self.optimize.to_dict() if self.optimize.param_grid else {},
        }
