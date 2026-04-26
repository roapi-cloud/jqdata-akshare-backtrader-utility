"""Pipeline orchestrator for the quantitative trading framework."""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from quant_framework.core.backtest.engine import BacktestEngine, BacktestResult
from quant_framework.core.backtest.cost import AStockCostModel
from quant_framework.core.data.source import BaseDataSource
from quant_framework.core.factors.base import Factor, FactorRegistry, FactorResult
from quant_framework.core.signals import SignalGenerator, Signal
from quant_framework.core.strategy.base import BaseStrategy, Portfolio

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics from a backtest.

    Attributes:
        total_return: Total return over the backtest period.
        annual_return: Annualized return.
        max_drawdown: Maximum drawdown.
        sharpe_ratio: Annualized Sharpe ratio.
        sortino_ratio: Annualized Sortino ratio.
        calmar_ratio: Calmar ratio (annual return / max drawdown).
        win_rate: Percentage of winning trades.
        profit_factor: Gross profit / gross loss.
        total_trades: Number of executed trades.
        avg_trade_return: Average return per trade.
        trading_days: Number of trading days in the backtest.
        benchmark_return: Benchmark return over the same period.
        alpha: Excess return over benchmark.
        beta: Sensitivity to benchmark movements.
        information_ratio: Alpha / tracking error.
        daily_returns: Daily return series.
        equity_curve: Portfolio value over time.
    """

    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_trade_return: float = 0.0
    trading_days: int = 0
    benchmark_return: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    information_ratio: float = 0.0
    daily_returns: pd.Series = field(default_factory=pd.Series)
    equity_curve: pd.Series = field(default_factory=pd.Series)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to a dictionary."""
        return {
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "avg_trade_return": self.avg_trade_return,
            "trading_days": self.trading_days,
            "benchmark_return": self.benchmark_return,
            "alpha": self.alpha,
            "beta": self.beta,
            "information_ratio": self.information_ratio,
        }

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            "=" * 50,
            "PERFORMANCE METRICS",
            "=" * 50,
            f"Total Return:      {self.total_return:.2%}",
            f"Annual Return:     {self.annual_return:.2%}",
            f"Max Drawdown:      {self.max_drawdown:.2%}",
            f"Sharpe Ratio:      {self.sharpe_ratio:.4f}",
            f"Sortino Ratio:     {self.sortino_ratio:.4f}",
            f"Calmar Ratio:      {self.calmar_ratio:.4f}",
            f"Win Rate:          {self.win_rate:.2%}",
            f"Profit Factor:     {self.profit_factor:.4f}",
            f"Total Trades:      {self.total_trades}",
            f"Benchmark Return:  {self.benchmark_return:.2%}",
            f"Alpha:             {self.alpha:.4f}",
            f"Beta:              {self.beta:.4f}",
            f"Information Ratio: {self.information_ratio:.4f}",
            "=" * 50,
        ]
        return "\n".join(lines)


@dataclass
class Report:
    """Backtest report with metrics, signals, and diagnostics.

    Attributes:
        metrics: PerformanceMetrics object.
        config: Configuration used for the backtest.
        backtest_result: Raw BacktestResult from the engine.
        factor_stats: Statistics for each factor used.
        signal_summary: Summary of signals generated.
        generated_at: Timestamp when the report was created.
        output_path: Path where the report was saved.
    """

    metrics: PerformanceMetrics
    config: Dict[str, Any]
    backtest_result: BacktestResult
    factor_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    signal_summary: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    output_path: Optional[str] = None

    def save(self, output_dir: str) -> str:
        """Save the report to disk as YAML and CSV files.

        Args:
            output_dir: Directory to save report files.

        Returns:
            Path to the main report YAML file.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        report_data = {
            "generated_at": self.generated_at.isoformat(),
            "config": self.config,
            "metrics": self.metrics.to_dict(),
            "factor_stats": self.factor_stats,
            "signal_summary": self.signal_summary,
            "backtest_summary": {
                "initial_capital": self.backtest_result.initial_capital,
                "final_capital": self.backtest_result.final_capital,
                "total_return": self.backtest_result.total_return,
                "benchmark_return": self.backtest_result.benchmark_return,
                "max_drawdown": self.backtest_result.max_drawdown,
                "sharpe_ratio": self.backtest_result.sharpe_ratio,
                "total_trades": self.backtest_result.total_trades,
                "win_rate": self.backtest_result.win_rate,
            },
        }

        report_path = out / "report.yaml"
        with open(report_path, "w", encoding="utf-8") as f:
            yaml.dump(report_data, f, default_flow_style=False, allow_unicode=True)

        if not self.backtest_result.daily_values.empty:
            csv_path = out / "daily_values.csv"
            self.backtest_result.daily_values.to_csv(csv_path, index=False)

        if self.backtest_result.trade_log:
            trades_path = out / "trades.csv"
            pd.DataFrame(self.backtest_result.trade_log).to_csv(
                trades_path, index=False
            )

        if (
            self.metrics.daily_returns is not None
            and not self.metrics.daily_returns.empty
        ):
            returns_path = out / "daily_returns.csv"
            self.metrics.daily_returns.to_csv(returns_path, header=["return"])

        self.output_path = str(report_path)
        logger.info(f"Report saved to {report_path}")
        return str(report_path)


class QuantPipeline:
    """Pipeline orchestrator that ties all framework components together.

    The pipeline executes the full quantitative trading workflow:
    1. Load configuration
    2. Initialize data source
    3. Calculate factors
    4. Generate signals
    5. Run backtest
    6. Calculate performance metrics
    7. Generate report

    Args:
        data_source: Data source instance for fetching market data.
        strategy: Strategy instance implementing the trading logic.
        config: Configuration dictionary with pipeline parameters.

    Example:
        >>> data_source = AkShareDataSource()
        >>> strategy = MyStrategy()
        >>> config = {"factors": ["MA", "RSI"], "initial_capital": 1000000}
        >>> pipeline = QuantPipeline(data_source, strategy, config)
        >>> result = pipeline.run("2020-01-01", "2023-12-31")
    """

    def __init__(
        self,
        data_source: BaseDataSource,
        strategy: BaseStrategy,
        config: Dict[str, Any],
    ) -> None:
        self.data_source = data_source
        self.strategy = strategy
        self.config = config

        self.factor_registry = FactorRegistry()
        self.factors: List[Factor] = []
        self.signal_generator: Optional[SignalGenerator] = None
        self._all_signals: List[Signal] = []
        self._factor_results: Dict[str, FactorResult] = {}

        self._setup_pipeline()

    def _setup_pipeline(self) -> None:
        """Initialize pipeline components from configuration."""
        logger.info("Setting up pipeline components...")

        factor_names = self.config.get("factors", [])
        for name in factor_names:
            if self.factor_registry.has(name):
                factor = self.factor_registry.get(name)
                self.factors.append(factor)
                logger.info(f"  Registered factor: {name}")
            else:
                logger.warning(f"  Factor '{name}' not found in registry, skipping")

        signal_config = self.config.get("signals", {})
        if signal_config:
            self.signal_generator = SignalGenerator(
                upper_threshold=signal_config.get("upper_threshold", 0.7),
                lower_threshold=signal_config.get("lower_threshold", 0.3),
            )
            logger.info("  Signal generator initialized")

        logger.info(
            f"Pipeline setup complete: {len(self.factors)} factors, "
            f"signal_generator={'yes' if self.signal_generator else 'no'}"
        )

    def run(self, start_date: str | date, end_date: str | date) -> BacktestResult:
        """Execute the full backtest pipeline.

        Args:
            start_date: Start date as string (YYYY-MM-DD) or date object.
            end_date: End date as string (YYYY-MM-DD) or date object.

        Returns:
            BacktestResult with complete backtest results.

        Raises:
            ValueError: If dates are invalid or data is unavailable.
            RuntimeError: If the backtest engine fails.
        """
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        if start_date >= end_date:
            raise ValueError(
                f"start_date ({start_date}) must be before end_date ({end_date})"
            )

        logger.info("=" * 60)
        logger.info("QUANT PIPELINE START")
        logger.info(f"  Strategy: {self.strategy.name}")
        logger.info(f"  Period: {start_date} to {end_date}")
        logger.info("=" * 60)

        try:
            logger.info("Step 1: Fetching market data...")
            bar_data = self._fetch_data(start_date, end_date)
            if bar_data.empty:
                raise ValueError("No market data available for the specified period")
            logger.info(
                f"  Fetched {len(bar_data)} bars for "
                f"{bar_data['symbol'].nunique()} symbols"
            )

            logger.info("Step 2: Calculating factors...")
            self._calculate_factors(bar_data)
            logger.info(f"  Calculated {len(self._factor_results)} factors")

            logger.info("Step 3: Generating signals...")
            self._generate_signals(bar_data)
            logger.info(f"  Generated {len(self._all_signals)} signals")

            logger.info("Step 4: Running backtest...")
            result = self._run_backtest(bar_data)
            logger.info(
                f"  Backtest complete: {result.total_trades} trades, "
                f"return={result.total_return:.2%}"
            )

            logger.info("=" * 60)
            logger.info("QUANT PIPELINE COMPLETE")
            logger.info("=" * 60)

            return result

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            logger.debug(traceback.format_exc())
            raise RuntimeError(f"Pipeline execution failed: {e}") from e

    def _fetch_data(self, start_date: date, end_date: date) -> pd.DataFrame:
        """Fetch market data from the data source.

        Args:
            start_date: Start date.
            end_date: End date.

        Returns:
            DataFrame with columns: date, symbol, open, high, low, close, volume.
        """
        symbols = self.config.get("symbols", [])

        if not symbols:
            symbols = self.data_source.get_symbol_list()
            max_symbols = self.config.get("max_symbols", 50)
            symbols = symbols[:max_symbols]
            logger.info(f"  Using {len(symbols)} symbols from data source")

        all_bars = []
        for symbol in symbols:
            try:
                df = self.data_source.get_daily_bars(symbol, start_date, end_date)
                if df.empty:
                    continue
                df = df.reset_index()
                if "symbol" not in df.columns and "code" in df.columns:
                    df = df.rename(columns={"code": "symbol"})
                if "symbol" not in df.columns:
                    df["symbol"] = symbol
                all_bars.append(df)
            except Exception as e:
                logger.warning(f"  Failed to fetch data for {symbol}: {e}")

        if not all_bars:
            return pd.DataFrame()

        combined = pd.concat(all_bars, ignore_index=True)

        required_cols = {"date", "symbol", "open", "high", "low", "close", "volume"}
        available_cols = set(combined.columns)
        missing = required_cols - available_cols
        if missing:
            logger.warning(f"  Missing columns {missing}, filling with defaults")
            for col in missing:
                if col == "date":
                    combined["date"] = pd.Timestamp.today().date()
                elif col == "symbol":
                    combined["symbol"] = "UNKNOWN"
                else:
                    combined[col] = 0.0

        combined["date"] = pd.to_datetime(combined["date"]).dt.date
        combined = combined.sort_values(["date", "symbol"]).reset_index(drop=True)

        return combined

    def _calculate_factors(self, bar_data: pd.DataFrame) -> None:
        """Calculate all registered factors.

        Args:
            bar_data: Market data DataFrame.
        """
        self._factor_results = {}

        for symbol in bar_data["symbol"].unique():
            symbol_data = bar_data[bar_data["symbol"] == symbol].copy()
            symbol_data = symbol_data.set_index("date").sort_index()

            for factor in self.factors:
                try:
                    factor.validate_data(
                        symbol_data, ["open", "high", "low", "close", "volume"]
                    )
                    result = factor.calculate(symbol_data)
                    if not result.is_empty():
                        key = f"{symbol}_{factor.name}"
                        self._factor_results[key] = result
                except Exception as e:
                    logger.warning(f"  Factor {factor.name} failed for {symbol}: {e}")

        logger.info(
            f"  Successfully calculated {len(self._factor_results)} factor results"
        )

    def _generate_signals(self, bar_data: pd.DataFrame) -> None:
        """Generate trading signals from factor values.

        Args:
            bar_data: Market data DataFrame.
        """
        self._all_signals = []

        if not self.signal_generator:
            logger.info("  No signal generator configured, skipping signal generation")
            return

        latest_date = bar_data["date"].max()
        latest_data = bar_data[bar_data["date"] == latest_date]

        for symbol in latest_data["symbol"].unique():
            for factor_name in set(f.name for f in self.factors):
                key = f"{symbol}_{factor_name}"
                if key in self._factor_results:
                    factor_result = self._factor_results[key]
                    if isinstance(factor_result.values, pd.Series):
                        factor_values = factor_result.values
                    else:
                        factor_values = (
                            factor_result.values.iloc[-1]
                            if not factor_result.values.empty
                            else pd.Series(dtype=float)
                        )

                    if not factor_values.empty:
                        signals = self.signal_generator.generate_from_factor(
                            factor_values, date=pd.Timestamp(latest_date)
                        )
                        self._all_signals.extend(signals)

        logger.info(f"  Generated {len(self._all_signals)} signals")

    def _run_backtest(self, bar_data: pd.DataFrame) -> BacktestResult:
        """Run the backtest using the backtest engine.

        Args:
            bar_data: Market data DataFrame.

        Returns:
            BacktestResult with complete results.
        """
        initial_capital = self.config.get("initial_capital", 1_000_000.0)
        cost_config = self.config.get("cost", {})

        cost_model = AStockCostModel(
            commission_rate=cost_config.get("commission_rate", 0.0003),
            min_commission=cost_config.get("min_commission", 5.0),
            stamp_duty_rate=cost_config.get("stamp_duty_rate", 0.001),
            transfer_fee_rate=cost_config.get("transfer_fee_rate", 0.00002),
            slippage_rate=cost_config.get("slippage_rate", 0.002),
        )

        benchmark_data = self.config.get("benchmark_data", None)

        engine = BacktestEngine(
            strategy=self.strategy,
            initial_cash=initial_capital,
            cost_model=cost_model,
            benchmark_data=benchmark_data,
        )

        result = engine.run(bar_data)
        return result

    def analyze(self, result: BacktestResult) -> PerformanceMetrics:
        """Calculate detailed performance metrics from backtest results.

        Args:
            result: BacktestResult from a completed backtest.

        Returns:
            PerformanceMetrics with comprehensive metrics.
        """
        logger.info("Calculating performance metrics...")

        daily_values = result.daily_values
        if daily_values.empty:
            logger.warning("No daily values available, returning empty metrics")
            return PerformanceMetrics()

        portfolio_values = daily_values["portfolio_value"]
        daily_returns = portfolio_values.pct_change().dropna()

        trading_days = len(daily_returns)
        total_return = result.total_return

        years = trading_days / 252.0 if trading_days > 0 else 1.0
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0

        max_drawdown = result.max_drawdown

        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * (252**0.5)
        else:
            sharpe_ratio = 0.0

        downside_returns = daily_returns[daily_returns < 0]
        if len(downside_returns) > 1 and downside_returns.std() > 0:
            sortino_ratio = (daily_returns.mean() / downside_returns.std()) * (252**0.5)
        else:
            sortino_ratio = 0.0

        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0.0

        win_rate = result.win_rate

        profit_factor = 0.0
        if result.trade_log:
            gross_profit = 0.0
            gross_loss = 0.0
            for trade in result.trade_log:
                if trade.get("side") == "SELL":
                    pnl = trade.get("price", 0) - trade.get("avg_cost", 0)
                    if pnl > 0:
                        gross_profit += pnl
                    else:
                        gross_loss += abs(pnl)
            profit_factor = (
                gross_profit / gross_loss
                if gross_loss > 0
                else float("inf")
                if gross_profit > 0
                else 0.0
            )

        benchmark_return = result.benchmark_return
        alpha = total_return - benchmark_return

        beta = 0.0
        information_ratio = 0.0
        if not daily_values.empty and "benchmark_value" in daily_values.columns:
            benchmark_series = daily_values["benchmark_value"].dropna()
            if len(benchmark_series) > 1:
                benchmark_returns = benchmark_series.pct_change().dropna()
                common_index = daily_returns.index.intersection(benchmark_returns.index)
                if len(common_index) > 1:
                    strat_ret = daily_returns.loc[common_index]
                    bench_ret = benchmark_returns.loc[common_index]
                    covariance = strat_ret.cov(bench_ret)
                    bench_variance = bench_ret.var()
                    beta = covariance / bench_variance if bench_variance > 0 else 0.0

                    tracking_error = (strat_ret - bench_ret).std()
                    if tracking_error > 0:
                        information_ratio = (
                            (strat_ret.mean() - bench_ret.mean())
                            / tracking_error
                            * (252**0.5)
                        )

        metrics = PerformanceMetrics(
            total_return=total_return,
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=result.total_trades,
            avg_trade_return=total_return / result.total_trades
            if result.total_trades > 0
            else 0.0,
            trading_days=trading_days,
            benchmark_return=benchmark_return,
            alpha=alpha,
            beta=beta,
            information_ratio=information_ratio,
            daily_returns=daily_returns,
            equity_curve=portfolio_values,
        )

        logger.info(f"  Total Return: {total_return:.2%}")
        logger.info(f"  Sharpe Ratio: {sharpe_ratio:.4f}")
        logger.info(f"  Max Drawdown: {max_drawdown:.2%}")

        return metrics

    def report(
        self,
        result: BacktestResult,
        output_dir: str = "output",
    ) -> Report:
        """Generate and save a comprehensive backtest report.

        Args:
            result: BacktestResult from a completed backtest.
            output_dir: Directory to save report files.

        Returns:
            Report object with all results and saved file paths.
        """
        logger.info(f"Generating report to {output_dir}...")

        metrics = self.analyze(result)

        factor_stats = {}
        for key, factor_result in self._factor_results.items():
            if isinstance(factor_result.values, pd.Series):
                stats = {
                    "mean": float(factor_result.values.mean()),
                    "std": float(factor_result.values.std()),
                    "min": float(factor_result.values.min()),
                    "max": float(factor_result.values.max()),
                    "count": int(factor_result.values.count()),
                }
            else:
                stats = {"count": len(factor_result.values)}
            factor_stats[key] = stats

        signal_summary = {
            "total_signals": len(self._all_signals),
            "long_signals": sum(
                1 for s in self._all_signals if s.signal_type.value == 1
            ),
            "short_signals": sum(
                1 for s in self._all_signals if s.signal_type.value == -1
            ),
            "hold_signals": sum(
                1 for s in self._all_signals if s.signal_type.value == 0
            ),
        }

        rep = Report(
            metrics=metrics,
            config=self.config,
            backtest_result=result,
            factor_stats=factor_stats,
            signal_summary=signal_summary,
        )

        rep.save(output_dir)

        logger.info("Report generation complete")
        return rep


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the config file is invalid YAML.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}") from e

    if not isinstance(config, dict):
        raise ValueError("Config file must contain a YAML mapping")

    logger.info(f"Configuration loaded from {config_path}")
    return config
