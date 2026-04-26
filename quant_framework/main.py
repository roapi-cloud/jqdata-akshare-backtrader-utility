"""Main entry point for the quantitative trading framework.

Usage examples:
    python main.py --config config/strategies.yaml --mode backtest
    python main.py --config config/strategies.yaml --mode analyze --start 2020-01-01 --end 2023-12-31
    python main.py --config config/strategies.yaml --mode optimize --output results/
"""

from __future__ import annotations

import argparse
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from quant_framework.core.data.source import AkShareDataSource, BaseDataSource
from quant_framework.core.strategy.base import BaseStrategy
from quant_framework.pipeline import (
    QuantPipeline,
    PerformanceMetrics,
    Report,
    load_config,
)

logger = logging.getLogger("quant_framework")


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """Configure logging for the framework.

    Args:
        verbose: If True, set log level to DEBUG. Otherwise INFO.
        log_file: Optional file path to write logs to.
    """
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Quantitative Trading Framework - Main Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --config config/strategies.yaml --mode backtest
  python main.py --config config/strategies.yaml --mode backtest --start 2020-01-01 --end 2023-12-31
  python main.py --config config/strategies.yaml --mode analyze --output results/
  python main.py --config config/strategies.yaml --mode optimize --n-trials 50
        """,
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        required=True,
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        choices=["backtest", "analyze", "optimize"],
        default="backtest",
        help="Execution mode (default: backtest)",
    )
    parser.add_argument(
        "--start",
        "-s",
        type=str,
        default=None,
        help="Start date YYYY-MM-DD (overrides config)",
    )
    parser.add_argument(
        "--end",
        "-e",
        type=str,
        default=None,
        help="End date YYYY-MM-DD (overrides config)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="output",
        help="Output directory for results (default: output)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=20,
        help="Number of optimization trials (default: 20)",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default=None,
        help="Strategy class name to use (overrides config)",
    )

    return parser.parse_args(argv)


def resolve_dates(config: Dict[str, Any], args: argparse.Namespace) -> tuple[str, str]:
    """Resolve start and end dates from config and CLI args.

    CLI args take precedence over config values.

    Args:
        config: Configuration dictionary.
        args: Parsed CLI arguments.

    Returns:
        Tuple of (start_date, end_date) as strings.
    """
    start = args.start
    end = args.end

    if start is None:
        data_config = config.get("data", {})
        start = data_config.get("start_date", "2020-01-01")

    if end is None:
        data_config = config.get("data", {})
        end = data_config.get("end_date", datetime.now().strftime("%Y-%m-%d"))

    return start, end


def create_data_source(config: Dict[str, Any]) -> BaseDataSource:
    """Create and return a data source instance based on config.

    Args:
        config: Configuration dictionary.

    Returns:
        Initialized data source instance.
    """
    source_type = config.get("data_source", "akshare")

    if source_type == "akshare":
        logger.info("Initializing AkShare data source...")
        return AkShareDataSource()
    else:
        logger.warning(f"Unknown data source '{source_type}', defaulting to AkShare")
        return AkShareDataSource()


def create_strategy(
    config: Dict[str, Any], strategy_name: Optional[str] = None
) -> BaseStrategy:
    """Create and return a strategy instance based on config.

    Args:
        config: Configuration dictionary.
        strategy_name: Optional strategy name override.

    Returns:
        Initialized strategy instance.

    Raises:
        ImportError: If the strategy module cannot be imported.
        ValueError: If the strategy class is not found.
    """
    strategy_config = config.get("strategy", {})
    name = strategy_name or strategy_config.get("name", "DefaultStrategy")
    module_path = strategy_config.get("module", None)

    if module_path:
        try:
            import importlib

            module = importlib.import_module(module_path)
            strategy_cls = getattr(module, name, None)
            if strategy_cls is None:
                raise ValueError(
                    f"Strategy class '{name}' not found in module '{module_path}'"
                )
            strategy = strategy_cls(name=name)
            params = strategy_config.get("params", {})
            if params:
                strategy.initialize(params)
            logger.info(f"Loaded strategy '{name}' from module '{module_path}'")
            return strategy
        except ImportError as e:
            raise ImportError(
                f"Cannot import strategy module '{module_path}': {e}"
            ) from e

    from quant_framework.core.strategy.base import BaseStrategy as _BaseStrategy

    class DefaultStrategy(_BaseStrategy):
        """Default fallback strategy that holds equal-weight positions."""

        def __init__(self, name: str = "DefaultStrategy"):
            super().__init__(name=name)
            self._top_n = 10

        def get_target_positions(self, trade_date, data, portfolio):
            if data.empty:
                return {}
            codes = (
                data["code"].unique() if "code" in data.columns else data.index.unique()
            )
            n = min(self._top_n, len(codes))
            selected = list(codes)[:n]
            weight = 1.0 / n if n > 0 else 0.0
            return {code: weight for code in selected}

    strategy = DefaultStrategy(name=name)
    params = strategy_config.get("params", {})
    if params:
        strategy.initialize(params)

    logger.info(f"Using default strategy '{name}'")
    return strategy


def run_backtest_mode(
    pipeline: QuantPipeline, start: str, end: str, output_dir: str
) -> None:
    """Execute the backtest mode.

    Args:
        pipeline: Configured QuantPipeline instance.
        start: Start date string.
        end: End date string.
        output_dir: Output directory for results.
    """
    logger.info(f"Running BACKTEST mode: {start} to {end}")

    result = pipeline.run(start, end)

    print("\n" + result.summary())

    report = pipeline.report(result, output_dir)
    print(f"\nReport saved to: {report.output_path}")

    metrics = pipeline.analyze(result)
    print("\n" + metrics.summary())


def run_analyze_mode(
    pipeline: QuantPipeline, start: str, end: str, output_dir: str
) -> None:
    """Execute the analyze mode (backtest + detailed analysis).

    Args:
        pipeline: Configured QuantPipeline instance.
        start: Start date string.
        end: End date string.
        output_dir: Output directory for results.
    """
    logger.info(f"Running ANALYZE mode: {start} to {end}")

    result = pipeline.run(start, end)
    metrics = pipeline.analyze(result)
    report = pipeline.report(result, output_dir)

    print("\n" + "=" * 60)
    print("DETAILED ANALYSIS")
    print("=" * 60)
    print("\n" + metrics.summary())

    if report.factor_stats:
        print("\nFactor Statistics:")
        print("-" * 40)
        for key, stats in report.factor_stats.items():
            print(f"  {key}:")
            for k, v in stats.items():
                print(f"    {k}: {v}")

    if report.signal_summary:
        print("\nSignal Summary:")
        print("-" * 40)
        for k, v in report.signal_summary.items():
            print(f"  {k}: {v}")

    print(f"\nFull report saved to: {report.output_path}")


def run_optimize_mode(
    pipeline: QuantPipeline,
    start: str,
    end: str,
    output_dir: str,
    n_trials: int,
) -> None:
    """Execute the optimize mode (parameter sweep).

    Performs a grid search over key strategy parameters and reports
    the best configuration by Sharpe ratio.

    Args:
        pipeline: Configured QuantPipeline instance.
        start: Start date string.
        end: End date string.
        output_dir: Output directory for results.
        n_trials: Number of optimization trials.
    """
    logger.info(f"Running OPTIMIZE mode with {n_trials} trials")

    param_grid = pipeline.config.get("optimize", {}).get("param_grid", {})

    if not param_grid:
        param_grid = {
            "top_n": [5, 10, 20, 30],
            "commission_rate": [0.0001, 0.0003, 0.0005],
            "slippage_rate": [0.001, 0.002, 0.003],
        }

    import itertools

    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combinations = list(itertools.product(*values))

    if n_trials and len(combinations) > n_trials:
        import random

        random.seed(42)
        combinations = random.sample(combinations, n_trials)

    logger.info(f"Testing {len(combinations)} parameter combinations...")

    results = []
    for i, combo in enumerate(combinations):
        params = dict(zip(keys, combo))
        logger.info(f"Trial {i + 1}/{len(combinations)}: {params}")

        try:
            test_config = dict(pipeline.config)
            cost_cfg = test_config.get("cost", {})
            if "commission_rate" in params:
                cost_cfg["commission_rate"] = params["commission_rate"]
            if "slippage_rate" in params:
                cost_cfg["slippage_rate"] = params["slippage_rate"]
            test_config["cost"] = cost_cfg

            strategy_params = test_config.get("strategy", {}).get("params", {})
            if "top_n" in params:
                strategy_params["top_n"] = params["top_n"]
            test_config.setdefault("strategy", {})["params"] = strategy_params

            test_pipeline = QuantPipeline(
                data_source=pipeline.data_source,
                strategy=pipeline.strategy,
                config=test_config,
            )

            result = test_pipeline.run(start, end)
            metrics = test_pipeline.analyze(result)

            results.append(
                {
                    "params": params,
                    "total_return": result.total_return,
                    "sharpe_ratio": metrics.sharpe_ratio,
                    "max_drawdown": result.max_drawdown,
                    "total_trades": result.total_trades,
                }
            )

            logger.info(
                f"  Return: {result.total_return:.2%}, "
                f"Sharpe: {metrics.sharpe_ratio:.4f}, "
                f"DD: {result.max_drawdown:.2%}"
            )

        except Exception as e:
            logger.warning(f"  Trial {i + 1} failed: {e}")
            results.append(
                {
                    "params": params,
                    "total_return": 0.0,
                    "sharpe_ratio": 0.0,
                    "max_drawdown": 0.0,
                    "total_trades": 0,
                    "error": str(e),
                }
            )

    best = max(results, key=lambda r: r["sharpe_ratio"])

    print("\n" + "=" * 60)
    print("OPTIMIZATION RESULTS")
    print("=" * 60)
    print(f"\nBest configuration (by Sharpe ratio):")
    print(f"  Parameters: {best['params']}")
    print(f"  Total Return: {best['total_return']:.2%}")
    print(f"  Sharpe Ratio: {best['sharpe_ratio']:.4f}")
    print(f"  Max Drawdown: {best['max_drawdown']:.2%}")
    print(f"  Total Trades: {best['total_trades']}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    opt_results_path = output_path / "optimization_results.yaml"

    with open(opt_results_path, "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "best_params": best["params"],
                "best_metrics": {
                    "total_return": best["total_return"],
                    "sharpe_ratio": best["sharpe_ratio"],
                    "max_drawdown": best["max_drawdown"],
                    "total_trades": best["total_trades"],
                },
                "all_trials": results,
            },
            f,
            default_flow_style=False,
            allow_unicode=True,
        )

    print(f"\nOptimization results saved to: {opt_results_path}")


def main(argv: Optional[list] = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Optional argument list (for testing).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    args = parse_args(argv)
    setup_logging(verbose=args.verbose, log_file=args.log_file)

    logger.info("Quantitative Trading Framework starting...")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Config: {args.config}")

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Failed to load config: {e}")
        return 1

    start, end = resolve_dates(config, args)
    logger.info(f"Date range: {start} to {end}")

    try:
        data_source = create_data_source(config)
    except Exception as e:
        logger.error(f"Failed to create data source: {e}")
        return 1

    try:
        strategy = create_strategy(config, args.strategy)
    except (ImportError, ValueError) as e:
        logger.error(f"Failed to create strategy: {e}")
        return 1

    pipeline = QuantPipeline(
        data_source=data_source,
        strategy=strategy,
        config=config,
    )

    try:
        if args.mode == "backtest":
            run_backtest_mode(pipeline, start, end, args.output)
        elif args.mode == "analyze":
            run_analyze_mode(pipeline, start, end, args.output)
        elif args.mode == "optimize":
            run_optimize_mode(pipeline, start, end, args.output, args.n_trials)
        else:
            logger.error(f"Unknown mode: {args.mode}")
            return 1

        logger.info("Pipeline completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        if args.verbose:
            logger.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
