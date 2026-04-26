"""Simple script to run a backtest with minimal configuration.

Usage:
    python run_backtest.py
    python run_backtest.py --config config/strategies.yaml
    python run_backtest.py --start 2020-01-01 --end 2023-12-31 --symbols 000001,000002
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from quant_framework.core.data.source import AkShareDataSource
from quant_framework.core.strategy.base import BaseStrategy, Portfolio
from quant_framework.pipeline import QuantPipeline

logger = logging.getLogger("run_backtest")


class SimpleMomentumStrategy(BaseStrategy):
    """Simple momentum-based strategy for demonstration.

    Selects stocks with the highest recent returns and holds them
    with equal weights.

    Args:
        name: Strategy name.
        top_n: Number of top stocks to hold.
        lookback: Number of days to look back for momentum calculation.
    """

    def __init__(
        self,
        name: str = "SimpleMomentum",
        top_n: int = 10,
        lookback: int = 20,
    ):
        super().__init__(name=name)
        self.top_n = top_n
        self.lookback = lookback

    def initialize(self, params: Optional[dict] = None) -> None:
        """Initialize with optional parameter overrides."""
        super().initialize(params)
        if "top_n" in self._params:
            self.top_n = int(self._params["top_n"])
        if "lookback" in self._params:
            self.lookback = int(self._params["lookback"])

    def get_target_positions(
        self,
        trade_date,
        data,
        portfolio: Portfolio,
    ) -> dict:
        """Select top-N stocks by recent momentum.

        Args:
            trade_date: Current trading date.
            data: Market data DataFrame.
            portfolio: Current portfolio state.

        Returns:
            Dictionary mapping stock codes to target weights.
        """
        if data.empty:
            return {}

        code_col = "code" if "code" in data.columns else "symbol"
        if code_col not in data.columns:
            return {}

        codes = data[code_col].unique()
        if len(codes) == 0:
            return {}

        momentum = {}
        for code in codes:
            stock_data = data[data[code_col] == code].sort_values("date")
            if len(stock_data) >= self.lookback:
                old_close = stock_data.iloc[-self.lookback]["close"]
                new_close = stock_data.iloc[-1]["close"]
                if old_close > 0:
                    momentum[code] = (new_close - old_close) / old_close
                else:
                    momentum[code] = 0.0
            else:
                momentum[code] = 0.0

        sorted_codes = sorted(momentum, key=momentum.get, reverse=True)
        selected = sorted_codes[: self.top_n]

        if not selected:
            return {}

        weight = 1.0 / len(selected)
        return {code: weight for code in selected}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run a simple backtest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to YAML config file (optional)",
    )
    parser.add_argument(
        "--start",
        "-s",
        type=str,
        default="2022-01-01",
        help="Start date YYYY-MM-DD (default: 2022-01-01)",
    )
    parser.add_argument(
        "--end",
        "-e",
        type=str,
        default=None,
        help="End date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated list of stock symbols",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of stocks to hold (default: 10)",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=20,
        help="Momentum lookback days (default: 20)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=1_000_000,
        help="Initial capital (default: 1,000,000)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="output",
        help="Output directory (default: output)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


def load_config_if_available(config_path: Optional[str]) -> dict:
    """Load config from file if available, otherwise return defaults."""
    if config_path is None:
        return {}

    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return {}

    import yaml

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger.info(f"Loaded config from {config_path}")
    return config


def main() -> int:
    """Run the backtest and display results."""
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    end_date = args.end or datetime.now().strftime("%Y-%m-%d")

    config = load_config_if_available(args.config)

    if args.symbols:
        config["symbols"] = [s.strip() for s in args.symbols.split(",")]

    config["initial_capital"] = args.capital
    config["factors"] = config.get("factors", [])

    strategy = SimpleMomentumStrategy(
        top_n=args.top_n,
        lookback=args.lookback,
    )
    strategy.initialize({"top_n": args.top_n, "lookback": args.lookback})

    data_source = AkShareDataSource()

    pipeline = QuantPipeline(
        data_source=data_source,
        strategy=strategy,
        config=config,
    )

    logger.info(f"Starting backtest: {args.start} to {end_date}")
    logger.info(
        f"Strategy: {strategy.name} (top_n={args.top_n}, lookback={args.lookback})"
    )
    logger.info(f"Initial capital: {args.capital:,.0f}")

    try:
        result = pipeline.run(args.start, end_date)

        print("\n" + result.summary())

        metrics = pipeline.analyze(result)
        print("\n" + metrics.summary())

        report = pipeline.report(result, args.output)
        print(f"\nReport saved to: {report.output_path}")

        return 0

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
