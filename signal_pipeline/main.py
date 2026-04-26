"""Main entry point for the signal pipeline — CLI, config, backtest & live modes."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

_MISSING_DEPS: list[str] = []

try:
    import numpy as np
except ImportError:
    _MISSING_DEPS.append("numpy")

try:
    import pandas as pd
except ImportError:
    _MISSING_DEPS.append("pandas")

try:
    import akshare as ak
except ImportError:
    ak = None  # type: ignore[assignment]
    _MISSING_DEPS.append("akshare")

try:
    import backtrader as bt
except ImportError:
    bt = None  # type: ignore[assignment]
    _MISSING_DEPS.append("backtrader")

if _MISSING_DEPS:
    print(
        f"[WARN] Missing optional dependencies: {', '.join(_MISSING_DEPS)}. "
        "Install with: pip install " + " ".join(_MISSING_DEPS),
        file=sys.stderr,
    )

# ---------------------------------------------------------------------------
# Project imports (relative to signal_pipeline/)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent))

from src.core.models import FusedSignal, MarketData, Signal, SignalType
from src.core.exceptions import (
    DataAlignmentError,
    FusionConflictError,
    IndicatorCalculationError,
    InsufficientDataError,
)
from src.fusion.engine import FusionConfig, SignalFusionEngine
from src.indicators.base import BaseSignalGenerator
from src.indicators.registry import IndicatorRegistry, auto_discover_indicators
from src.indicators.spectral import MESAGenerator, TrendMomentumGenerator

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

_BANNER = r"""
  ____  _   _ ___ ____    _    ____ _____
 / ___|| | | |_ _/ ___|  / \  / ___|_   _|
 \___ \| |_| || |\___ \ / _ \ \___ \ | |
  ___) |  _  || | ___) / ___ \ ___) || |
 |____/|_| |_|___|____/_/   \_\____/ |_|

  Multi-Indicator Signal Pipeline v1.0
  Chan Theory · RSRS · MESA · Trend/Momentum · Rounding Bottom
"""

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def setup_logging(log_dir: Path | None = None, verbose: bool = False) -> logging.Logger:
    """Configure logging to both file and console.

    Args:
        log_dir: Directory for log files. Defaults to ``./logs`` next to main.py.
        verbose: If True, set console level to DEBUG.

    Returns:
        Configured root logger for the application.
    """
    if log_dir is None:
        log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"pipeline_{datetime.now():%Y%m%d_%H%M%S}.log"

    root = logging.getLogger("signal_pipeline")
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    root.info("Logging initialized → %s", log_file)
    return root


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_full_config(path: str | Path) -> dict[str, Any]:
    """Load the full nested YAML configuration.

    Args:
        path: Path to config.yaml.

    Returns:
        Raw dict from YAML.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(
            f"Expected YAML mapping at top level, got {type(raw).__name__}"
        )

    return raw


# ---------------------------------------------------------------------------
# Indicator registration
# ---------------------------------------------------------------------------

_BUILTIN_INDICATORS: dict[str, type[BaseSignalGenerator]] = {
    "mesa": MESAGenerator,
    "trend_momentum": TrendMomentumGenerator,
}


def _try_register_optional(registry: IndicatorRegistry, logger: logging.Logger) -> None:
    """Attempt to register indicators whose modules may be missing."""
    # Chan Theory
    try:
        from src.indicators.chan_theory import ChanTheoryGenerator  # noqa: F401

        registry.register("chan_theory", ChanTheoryGenerator)
        logger.info("Registered indicator: chan_theory")
    except ImportError:
        logger.warning("chan_theory module not found — skipping")

    # RSRS
    try:
        from src.indicators.rsrs import RSRSGen  # noqa: F401

        registry.register("rsrs", RSRSGen)
        logger.info("Registered indicator: rsrs")
    except ImportError:
        logger.warning("rsrs module not found — skipping")

    # Rounding Bottom
    try:
        from src.indicators.rounding_bottom import RoundingBottomGenerator  # noqa: F401

        registry.register("rounding_bottom", RoundingBottomGenerator)
        logger.info("Registered indicator: rounding_bottom")
    except ImportError:
        logger.warning("rounding_bottom module not found — skipping")


def register_indicators(
    config: dict[str, Any],
    registry: IndicatorRegistry,
    logger: logging.Logger,
) -> list[tuple[str, dict[str, Any], float]]:
    """Register all indicators specified in config and return (name, params, weight) list.

    Args:
        config: Full nested config dict.
        registry: IndicatorRegistry singleton.
        logger: Application logger.

    Returns:
        List of (indicator_name, params_dict, weight) tuples in config order.
    """
    # Register built-ins
    for name, cls in _BUILTIN_INDICATORS.items():
        registry.register(name, cls)
        logger.debug("Registered built-in indicator: %s", name)

    # Try optional indicators
    _try_register_optional(registry, logger)

    # Auto-discover any additional indicators in the package
    discovered = auto_discover_indicators(registry)
    if discovered:
        logger.info("Auto-discovered %d additional indicator(s)", discovered)

    # Build ordered indicator list from config
    pipeline_cfg = config.get("pipeline", {})
    indicator_specs: list[dict[str, Any]] = pipeline_cfg.get("indicators", [])

    result: list[tuple[str, dict[str, Any], float]] = []
    registered = registry.list_all()

    for spec in indicator_specs:
        name = spec.get("name", "")
        params = spec.get("params", {}) or {}
        weight = spec.get("weight", 1.0)

        if name not in registered:
            logger.warning("Indicator '%s' is not available — skipping", name)
            continue

        result.append((name, params, weight))
        logger.info(
            "Configured indicator: %s (weight=%.2f, params=%s)", name, weight, params
        )

    if not result:
        raise RuntimeError(
            "No valid indicators configured. Check config.yaml and installed modules."
        )

    return result


# ---------------------------------------------------------------------------
# Signal Pipeline
# ---------------------------------------------------------------------------


class SignalPipeline:
    """Orchestrates indicator execution and signal fusion.

    Attributes:
        indicators: Ordered list of (name, instance, weight) tuples.
        fusion_engine: SignalFusionEngine instance.
        market_regime: Current market regime label (default "unknown").
    """

    def __init__(
        self,
        indicators: list[tuple[str, dict[str, Any], float]],
        registry: IndicatorRegistry,
        fusion_cfg: dict[str, Any],
        logger: logging.Logger,
    ) -> None:
        self.logger = logger
        self.indicators: list[tuple[str, BaseSignalGenerator, float]] = []

        for name, params, weight in indicators:
            gen = registry.get(name, **params)
            self.indicators.append((name, gen, weight))

        # Build fusion config
        base_weights = {name: w for name, _, w in self.indicators}
        self.fusion_engine = SignalFusionEngine(
            FusionConfig(
                base_weights=base_weights,
                buy_threshold=fusion_cfg.get("buy_threshold", 0.5),
                sell_threshold=fusion_cfg.get("sell_threshold", -0.5),
                conflict_tolerance=fusion_cfg.get("conflict_tolerance", 0.2),
            )
        )

        self.market_regime: str = "unknown"
        self._signals_history: list[Signal] = []

    def run_batch(self, data: list[MarketData]) -> FusedSignal:
        """Run all indicators on a batch of market data and fuse results.

        Args:
            data: Ordered list of MarketData bars (oldest first).

        Returns:
            FusedSignal with the consensus decision.
        """
        all_signals: list[Signal] = []

        for name, generator, _weight in self.indicators:
            try:
                signals = generator.generate(data)
                all_signals.extend(signals)
                self._signals_history.extend(signals)
                self.logger.debug(
                    "Indicator '%s' produced %d signal(s)", name, len(signals)
                )
            except InsufficientDataError as exc:
                self.logger.debug("Indicator '%s' skipped: %s", name, exc)
            except IndicatorCalculationError as exc:
                self.logger.warning("Indicator '%s' calculation error: %s", name, exc)
            except Exception as exc:
                self.logger.error(
                    "Indicator '%s' unexpected error: %s", name, exc, exc_info=True
                )

        if not all_signals:
            self.logger.warning("No signals produced by any indicator")
            return FusedSignal(
                symbol=data[-1].symbol if data else "",
                timestamp=data[-1].timestamp if data else datetime.now(),
                signal_type=SignalType.HOLD,
                strength=0.0,
                metadata={"reason": "no_signals"},
            )

        try:
            fused = self.fusion_engine.fuse(all_signals, self.market_regime)
        except FusionConflictError as exc:
            self.logger.warning("Fusion conflict: %s", exc)
            fused = self.fusion_engine.fuse(all_signals, "unknown")

        self.logger.info(
            "Fused signal: %s strength=%.3f (buy=%.3f, sell=%.3f, conflict=%s)",
            fused.signal_type.value,
            fused.strength,
            fused.metadata.get("buy_score", 0),
            fused.metadata.get("sell_score", 0),
            fused.metadata.get("is_conflict", False),
        )

        return fused

    def update(self, new_bar: MarketData) -> FusedSignal | None:
        """Incrementally update pipeline with a single new bar.

        Only indicators with ``supports_incremental=True`` will produce signals.

        Args:
            new_bar: Latest MarketData bar.

        Returns:
            FusedSignal if at least one incremental signal was produced, else None.
        """
        incremental_signals: list[Signal] = []

        for name, generator, _weight in self.indicators:
            if not generator.supports_incremental:
                continue
            try:
                sig = generator.update(new_bar)
                if sig is not None:
                    incremental_signals.append(sig)
                    self._signals_history.append(sig)
            except Exception as exc:
                self.logger.warning("Incremental update failed for '%s': %s", name, exc)

        if not incremental_signals:
            return None

        return self.fusion_engine.fuse(incremental_signals, self.market_regime)

    @property
    def signals_history(self) -> list[Signal]:
        return list(self._signals_history)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


def fetch_market_data(
    symbol: str,
    start: str,
    end: str,
    source: str = "akshare",
    cache_dir: Path | None = None,
    logger: logging.Logger | None = None,
) -> list[MarketData]:
    """Fetch historical market data.

    Args:
        symbol: Ticker symbol (e.g. "sh600000").
        start: Start date string (YYYY-MM-DD).
        end: End date string (YYYY-MM-DD).
        source: Data source name. Currently only "akshare" is supported.
        cache_dir: Optional directory for caching data.
        logger: Optional logger.

    Returns:
        List of MarketData bars sorted by timestamp.
    """
    log = logger or logging.getLogger("signal_pipeline.data")

    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{symbol}_{start}_{end}.pkl"
        if cache_file.exists():
            log.info("Loading cached data from %s", cache_file)
            try:
                import pandas as pd

                df = pd.read_pickle(cache_file)
                bars = _df_to_market_data(df, symbol)
                log.info("Loaded %d bars from cache", len(bars))
                return bars
            except Exception as exc:
                log.warning("Cache read failed (%s), fetching fresh data", exc)

    if source == "akshare":
        if ak is None:
            raise ImportError(
                "akshare is required for data fetching. Install: pip install akshare"
            )
        bars = _fetch_akshare(symbol, start, end, log)
    else:
        raise ValueError(f"Unsupported data source: {source}")

    if cache_dir and bars:
        try:
            import pandas as pd

            df = _market_data_to_df(bars)
            cache_file = cache_dir / f"{symbol}_{start}_{end}.pkl"
            df.to_pickle(cache_file)
            log.info("Cached %d bars to %s", len(bars), cache_file)
        except Exception as exc:
            log.warning("Cache write failed: %s", exc)

    return bars


def _fetch_akshare(
    symbol: str, start: str, end: str, logger: logging.Logger
) -> list[MarketData]:
    """Fetch daily bars from akshare."""
    logger.info("Fetching %s from akshare (%s → %s)", symbol, start, end)

    # akshare expects symbols like "600000" for A-shares
    clean_symbol = symbol.replace("sh", "").replace("sz", "")

    try:
        df = ak.stock_zh_a_hist(
            symbol=clean_symbol,
            period="daily",
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""),
            adjust="qfq",
        )
    except Exception as exc:
        raise RuntimeError(f"akshare fetch failed for {symbol}: {exc}") from exc

    if df is None or df.empty:
        raise ValueError(f"No data returned for {symbol} ({start} → {end})")

    logger.info("Fetched %d bars from akshare", len(df))
    return _df_to_market_data(df, symbol)


def _df_to_market_data(df: Any, symbol: str) -> list[MarketData]:
    """Convert a pandas DataFrame to list of MarketData."""
    import pandas as pd

    bars: list[MarketData] = []
    for _, row in df.iterrows():
        ts = row.get("日期") or row.get("date") or row.get("timestamp")
        if isinstance(ts, str):
            ts = pd.to_datetime(ts)
        bars.append(
            MarketData(
                symbol=symbol,
                timestamp=ts,
                open=float(row.get("开盘", row.get("open", 0))),
                high=float(row.get("最高", row.get("high", 0))),
                low=float(row.get("最低", row.get("low", 0))),
                close=float(row.get("收盘", row.get("close", 0))),
                volume=float(row.get("成交量", row.get("volume", 0))),
            )
        )
    return bars


def _market_data_to_df(bars: list[MarketData]) -> Any:
    """Convert list of MarketData to pandas DataFrame."""
    import pandas as pd

    return pd.DataFrame(
        {
            "日期": [b.timestamp for b in bars],
            "开盘": [b.open for b in bars],
            "最高": [b.high for b in bars],
            "最低": [b.low for b in bars],
            "收盘": [b.close for b in bars],
            "成交量": [b.volume for b in bars],
        }
    )


# ---------------------------------------------------------------------------
# Backtest Engine
# ---------------------------------------------------------------------------


class BacktestEngine:
    """Simple event-driven backtest engine.

    Runs the pipeline over historical data and simulates trades based on
    fused signals.
    """

    def __init__(
        self,
        pipeline: SignalPipeline,
        start_cash: float = 1_000_000,
        commission: float = 0.001,
        logger: logging.Logger | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.start_cash = start_cash
        self.commission = commission
        self.logger = logger or logging.getLogger("signal_pipeline.backtest")

        self.cash: float = start_cash
        self.position: int = 0
        self.avg_cost: float = 0.0
        self.trades: list[dict[str, Any]] = []
        self.equity_curve: list[tuple[datetime, float]] = []

    def run(self, data: list[MarketData]) -> dict[str, Any]:
        """Execute backtest over the given data.

        Uses a sliding-window approach: at each bar, runs the pipeline on
        all data up to that point and acts on the fused signal.

        Args:
            data: Historical bars (oldest first).

        Returns:
            Summary dict with performance metrics.
        """
        self.logger.info(
            "Starting backtest: %d bars, cash=%.0f, commission=%.4f",
            len(data),
            self.start_cash,
            self.commission,
        )

        # Determine the minimum history needed across all indicators
        min_history = max(
            (gen.min_history for _, gen, _ in self.pipeline.indicators),
            default=100,
        )

        self.logger.info("Minimum history required: %d bars", min_history)

        for i in range(min_history, len(data)):
            window = data[: i + 1]
            current_bar = data[i]

            try:
                fused = self.pipeline.run_batch(window)
            except Exception as exc:
                self.logger.error("Pipeline failed at bar %d: %s", i, exc)
                self.equity_curve.append(
                    (current_bar.timestamp, self._total_equity(current_bar.close))
                )
                continue

            self._execute_signal(fused, current_bar)
            self.equity_curve.append(
                (current_bar.timestamp, self._total_equity(current_bar.close))
            )

        results = self._compute_results(data)
        self._print_results(results)
        return results

    def _execute_signal(self, fused: FusedSignal, bar: MarketData) -> None:
        """Execute a trade based on the fused signal."""
        buy_threshold = self.pipeline.fusion_engine.config.buy_threshold
        sell_threshold = self.pipeline.fusion_engine.config.sell_threshold

        net = fused.metadata.get("net", 0)

        if net >= buy_threshold and self.position == 0:
            # Buy
            shares = int(self.cash / (bar.close * (1 + self.commission)))
            if shares > 0:
                cost = shares * bar.close * (1 + self.commission)
                self.cash -= cost
                self.position = shares
                self.avg_cost = bar.close
                self.trades.append(
                    {
                        "type": "BUY",
                        "price": bar.close,
                        "shares": shares,
                        "date": bar.timestamp,
                    }
                )
                self.logger.info(
                    "BUY  %d shares @ %.2f (cash=%.0f)", shares, bar.close, self.cash
                )

        elif net <= sell_threshold and self.position > 0:
            # Sell
            proceeds = self.position * bar.close * (1 - self.commission)
            pnl = proceeds - self.position * self.avg_cost
            self.trades.append(
                {
                    "type": "SELL",
                    "price": bar.close,
                    "shares": self.position,
                    "date": bar.timestamp,
                    "pnl": pnl,
                }
            )
            self.logger.info(
                "SELL %d shares @ %.2f (pnl=%.0f, cash=%.0f)",
                self.position,
                bar.close,
                pnl,
                self.cash + proceeds,
            )
            self.cash += proceeds
            self.position = 0
            self.avg_cost = 0.0

    def _total_equity(self, current_price: float) -> float:
        return self.cash + self.position * current_price

    def _compute_results(self, data: list[MarketData]) -> dict[str, Any]:
        """Compute performance summary."""
        if not self.equity_curve:
            return {"error": "No equity data"}

        final_equity = self.equity_curve[-1][1]
        total_return = (final_equity - self.start_cash) / self.start_cash

        # Max drawdown
        peak = self.equity_curve[0][1]
        max_dd = 0.0
        for _, eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd

        # Trade stats
        num_trades = len(self.trades)
        winning = [t for t in self.trades if t.get("pnl", 0) > 0]
        losing = [
            t for t in self.trades if t.get("pnl", 0) <= 0 and t["type"] == "SELL"
        ]

        return {
            "start_cash": self.start_cash,
            "final_equity": round(final_equity, 2),
            "total_return": round(total_return, 4),
            "total_return_pct": round(total_return * 100, 2),
            "max_drawdown": round(max_dd, 4),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "num_trades": num_trades,
            "num_winning": len(winning),
            "num_losing": len(losing),
            "win_rate": round(len(winning) / max(len(winning) + len(losing), 1), 4),
            "final_position": self.position,
            "final_cash": round(self.cash, 2),
        }

    def _print_results(self, results: dict[str, Any]) -> None:
        """Print backtest results summary."""
        self.logger.info("=" * 60)
        self.logger.info("BACKTEST RESULTS")
        self.logger.info("=" * 60)
        for key, val in results.items():
            self.logger.info("  %-20s %s", key, val)
        self.logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Live Mode
# ---------------------------------------------------------------------------


def run_live(
    pipeline: SignalPipeline,
    symbol: str,
    interval: int = 60,
    logger: logging.Logger | None = None,
) -> None:
    """Run the pipeline in live mode, polling for new data.

    Args:
        pipeline: Configured SignalPipeline.
        symbol: Ticker symbol to monitor.
        interval: Seconds between polls.
        logger: Application logger.
    """
    log = logger or logging.getLogger("signal_pipeline.live")
    log.info("Live mode started for %s (interval=%ds)", symbol, interval)
    print(
        f"\n[LIVE] Monitoring {symbol} — polling every {interval}s (Ctrl+C to stop)\n"
    )

    try:
        while True:
            try:
                # Fetch latest bar
                today = datetime.now().strftime("%Y-%m-%d")
                yesterday = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
                data = fetch_market_data(symbol, yesterday, today, logger=log)

                if not data:
                    log.warning("No data fetched for %s", symbol)
                    time.sleep(interval)
                    continue

                latest_bar = data[-1]

                # Try incremental update first, fall back to batch
                fused = pipeline.update(latest_bar)
                if fused is None:
                    # Not enough incremental indicators; run batch on recent data
                    window = data[
                        -max(
                            (gen.min_history for _, gen, _ in pipeline.indicators),
                            default=100,
                        ) :
                    ]
                    if len(window) >= 2:
                        fused = pipeline.run_batch(window)
                    else:
                        log.debug("Insufficient data for batch run")
                        time.sleep(interval)
                        continue

                if fused is not None:
                    _log_live_signal(fused, latest_bar, log)

            except Exception as exc:
                log.error("Live polling error: %s", exc, exc_info=True)

            time.sleep(interval)

    except KeyboardInterrupt:
        log.info("Live mode stopped by user")
        print("\n[LIVE] Stopped.")


def _log_live_signal(
    fused: FusedSignal, bar: MarketData, logger: logging.Logger
) -> None:
    """Format and log a live signal."""
    signal_str = (
        f"[LIVE] {fused.symbol} | {bar.timestamp:%Y-%m-%d %H:%M} | "
        f"close={bar.close:.2f} | "
        f"SIGNAL={fused.signal_type.value.upper()} | "
        f"strength={fused.strength:.3f} | "
        f"buy={fused.metadata.get('buy_score', 0):.3f} | "
        f"sell={fused.metadata.get('sell_score', 0):.3f} | "
        f"conflict={fused.metadata.get('is_conflict', False)}"
    )
    logger.info(signal_str)
    print(signal_str)


# ---------------------------------------------------------------------------
# Main pipeline runner
# ---------------------------------------------------------------------------


def run_pipeline(
    config: dict[str, Any],
    symbol: str,
    mode: str,
    logger: logging.Logger,
) -> dict[str, Any] | None:
    """Execute the full pipeline in the specified mode.

    Args:
        config: Full nested config dict.
        symbol: Ticker symbol.
        mode: "backtest" or "live".
        logger: Application logger.

    Returns:
        Backtest results dict if mode is "backtest", else None.
    """
    # 1. Init registry and register indicators
    registry = IndicatorRegistry.instance()
    indicator_specs = register_indicators(config, registry, logger)

    # 2. Build fusion config
    fusion_cfg = config.get("pipeline", {}).get("fusion", {})

    # 3. Init pipeline
    pipeline = SignalPipeline(
        indicators=indicator_specs,
        registry=registry,
        fusion_cfg=fusion_cfg,
        logger=logger,
    )

    logger.info(
        "Pipeline initialized with %d indicator(s): %s",
        len(pipeline.indicators),
        ", ".join(n for n, _, _ in pipeline.indicators),
    )

    # 4. Run in requested mode
    if mode == "backtest":
        bt_cfg = config.get("backtest", {})
        cache_dir = Path(config.get("data", {}).get("cache_dir", "./cache"))

        data = fetch_market_data(
            symbol=symbol,
            start=bt_cfg.get("start", "2020-01-01"),
            end=bt_cfg.get("end", "2023-12-31"),
            source=config.get("data", {}).get("source", "akshare"),
            cache_dir=cache_dir,
            logger=logger,
        )

        if not data:
            logger.error("No market data fetched — cannot backtest")
            return None

        engine = BacktestEngine(
            pipeline=pipeline,
            start_cash=bt_cfg.get("cash", 1_000_000),
            commission=bt_cfg.get("commission", 0.001),
            logger=logger,
        )

        results = engine.run(data)
        return results

    elif mode == "live":
        live_cfg = config.get("live", {})
        if not live_cfg.get("enabled", False):
            logger.warning("Live mode is disabled in config — set live.enabled=true")
            print(
                "[WARN] Live mode is disabled in config. Set `live.enabled: true` to enable."
            )
            return None

        run_live(
            pipeline=pipeline,
            symbol=symbol,
            interval=live_cfg.get("interval", 60),
            logger=logger,
        )
        return None

    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'backtest' or 'live'.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="signal-pipeline",
        description="Multi-Indicator Signal Pipeline — Backtest & Live Trading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
        "  python main.py --mode backtest --symbol sh600000\n"
        "  python main.py --mode live --symbol sh600000 --config config.yaml\n"
        "  python main.py --mode backtest --symbol sz000001 --config config.yaml --verbose\n",
    )

    parser.add_argument(
        "--mode",
        choices=["backtest", "live"],
        default="backtest",
        help="Execution mode: backtest (default) or live",
    )
    parser.add_argument(
        "--symbol",
        default="sh600000",
        help="Ticker symbol (e.g. sh600000, sz000001)",
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to YAML config file (default: config.yaml next to main.py)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug-level console logging",
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="Directory for log files (default: ./logs)",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    print(_BANNER)

    args = parse_args(argv)

    # Setup logging
    logger = setup_logging(
        log_dir=Path(args.log_dir) if args.log_dir else None,
        verbose=args.verbose,
    )

    logger.info("Starting signal_pipeline — mode=%s, symbol=%s", args.mode, args.symbol)
    logger.info("Config file: %s", args.config)

    try:
        # Load config
        config = load_full_config(args.config)
        logger.info("Config loaded successfully")

        # Run pipeline
        results = run_pipeline(
            config=config,
            symbol=args.symbol,
            mode=args.mode,
            logger=logger,
        )

        if results is not None:
            logger.info("Pipeline completed successfully")
            return 0

        if args.mode == "live":
            return 0  # run_live blocks until interrupted

        return 1

    except FileNotFoundError as exc:
        logger.error("File error: %s", exc)
        return 1
    except ImportError as exc:
        logger.error("Missing dependency: %s", exc)
        return 1
    except RuntimeError as exc:
        logger.error("Runtime error: %s", exc)
        return 1
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as exc:
        logger.error("Unexpected error: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
