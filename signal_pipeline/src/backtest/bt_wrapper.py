"""Backtrader integration layer for the signal pipeline.

Provides:
- ``PipelineStrategy``: A ``bt.Strategy`` that runs the signal pipeline on
  each bar and executes trades based on fused signals.
- ``BacktestEngine``: A convenience wrapper around ``bt.Cerebro`` that
  handles data loading, strategy injection, and result collection.

Real-time / paper-trading hooks are marked with ``# LIVE-HOOK`` comments.
"""

from __future__ import annotations

import csv
import logging
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import backtrader as bt

from src.core.models import FusedSignal, MarketData, SignalType
from src.core.config import PipelineConfig
from src.fusion.engine import FusionConfig, SignalFusionEngine
from src.indicators.registry import IndicatorRegistry, auto_discover_indicators

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

A_SHARE_LOT = 100  # A-share minimum trading unit


def _calc_kelly_position(
    capital: float,
    risk_per_trade: float,
    confidence: float,
    stop_loss_distance: float,
    lot_size: int = A_SHARE_LOT,
) -> int:
    """Kelly-based position sizing rounded to lot size.

    Formula::

        size = capital * risk_per_trade * confidence / stop_loss_distance

    Args:
        capital: Available cash or portfolio value.
        risk_per_trade: Fraction of capital to risk on a single trade (e.g. 0.02).
        confidence: Signal confidence in [0, 1].
        stop_loss_distance: Absolute price distance to stop-loss level.
        lot_size: Rounding unit (100 for A-shares).

    Returns:
        Number of shares rounded down to the nearest ``lot_size``.
        Returns 0 if ``stop_loss_distance`` is zero or negative.
    """
    if stop_loss_distance <= 0:
        return 0
    raw = capital * risk_per_trade * confidence / stop_loss_distance
    return int(math.floor(raw / lot_size)) * lot_size


# ---------------------------------------------------------------------------
# PipelineStrategy
# ---------------------------------------------------------------------------


class PipelineStrategy(bt.Strategy):
    """Backtrader strategy that delegates signal generation to the pipeline.

    Params
    ------
    pipeline_config : PipelineConfig
        Configuration for indicator selection and fusion.
    indicators : list[str]
        Legacy param — indicator names (merged into pipeline_config if given).
    weights : list[float]
        Legacy param — indicator weights (merged into pipeline_config if given).
    risk_per_trade : float
        Fraction of capital risked per trade (default 0.02).
    stop_loss_pct : float
        Stop-loss as a fraction of entry price (default 0.05 → 5%).
    log_dir : str | None
        Directory for signal CSV logs. ``None`` disables logging.
    """

    params = (
        ("pipeline_config", None),
        ("indicators", []),
        ("weights", []),
        ("risk_per_trade", 0.02),
        ("stop_loss_pct", 0.05),
        ("log_dir", None),
    )

    def __init__(self) -> None:
        # -- Resolve pipeline config ----------------------------------------
        cfg = self.p.pipeline_config
        if cfg is None:
            # Build from legacy params
            cfg = PipelineConfig(
                indicators=list(self.p.indicators),
                weights=list(self.p.weights) if self.p.weights else [],
            )
        self.pipeline_config: PipelineConfig = cfg

        # -- Build fusion engine --------------------------------------------
        self.fusion_engine = SignalFusionEngine(FusionConfig())

        # -- Instantiate indicators from registry ---------------------------
        self._indicators = []
        registry = IndicatorRegistry.instance()
        auto_discover_indicators(registry)  # safe no-op if already called
        for name in cfg.indicators:
            try:
                self._indicators.append(registry.get(name))
            except KeyError:
                logger.warning("Indicator '%s' not registered, skipping.", name)

        # -- Data buffers ---------------------------------------------------
        # Rolling buffer of MarketData bars kept for incremental indicators.
        self._data_buffer: list[MarketData] = []

        # -- Signal log -----------------------------------------------------
        self._log_path: str | None = None
        if self.p.log_dir:
            os.makedirs(self.p.log_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._log_path = os.path.join(self.p.log_dir, f"signals_{ts}.csv")
            self._init_log_csv()

        # -- Entry price tracking for stop-loss distance --------------------
        self._entry_price: float | None = None

        logger.info(
            "PipelineStrategy initialised with indicators: %s",
            cfg.indicators,
        )

    # -- Backtrader callbacks -----------------------------------------------

    def next(self) -> None:
        """Called on every new bar by Backtrader.

        Flow:
        1. Collect latest bar into ``MarketData``.
        2. Run pipeline → ``FusedSignal``.
        3. Execute trade logic.
        4. Log signal to CSV.
        """
        # 1. Collect latest bar ------------------------------------------------
        data = self.datas[0]  # primary data feed
        try:
            bar = MarketData(
                symbol=data._name or "UNKNOWN",
                timestamp=data.datetime.datetime(0),
                open=data.open[0],
                high=data.high[0],
                low=data.low[0],
                close=data.close[0],
                volume=data.volume[0],
            )
        except IndexError:
            # Data feed not yet ready (warm-up period)
            return

        self._data_buffer.append(bar)

        # Trim buffer to a reasonable size (keep 2× min_history)
        max_len = max(self.pipeline_config.min_history * 2, 500)
        if len(self._data_buffer) > max_len:
            self._data_buffer = self._data_buffer[-max_len:]

        # Need enough history before generating signals
        if len(self._data_buffer) < self.pipeline_config.min_history:
            return

        # 2. Run pipeline → FusedSignal ----------------------------------------
        fused = self._run_pipeline(bar)
        self._last_fused = fused  # store for calc_position

        # 3. Execute trade -----------------------------------------------------
        self._execute_trade(fused, bar)

        # 4. Log signal --------------------------------------------------------
        if self._log_path:
            self._log_signal_csv(fused, bar)

    # -- LIVE-HOOK: override ``next`` in a subclass or add a live-data
    # feed (e.g. via ``bt.DataFeed`` subclass that pulls from a WebSocket
    # or REST API). The rest of the pipeline logic remains unchanged.

    # -- Internal helpers -------------------------------------------------

    def _run_pipeline(self, latest_bar: MarketData) -> FusedSignal:
        """Run all indicators and fuse their signals.

        For a production system, replace this with the real
        ``SignalPipeline.run()`` once that orchestrator is implemented.
        """
        # Run each indicator on the buffered data
        raw_signals = []
        for indicator in self._indicators:
            try:
                sigs = indicator.generate(self._data_buffer)
                raw_signals.extend(sigs)
            except Exception:
                logger.exception(
                    "Indicator %s failed on bar %s",
                    indicator.name,
                    latest_bar.timestamp,
                )

        # Fuse signals
        if raw_signals:
            fused = self.fusion_engine.fuse(
                raw_signals,
                market_regime=self.pipeline_config.market_regime,
            )
        else:
            # No signals produced → neutral
            fused = FusedSignal(
                symbol=latest_bar.symbol,
                timestamp=latest_bar.timestamp,
                signal_type=SignalType.HOLD,
                strength=0.0,
                metadata={"reason": "no_indicator_signals"},
            )

        return fused

    def _execute_trade(self, fused: FusedSignal, bar: MarketData) -> None:
        """Execute orders based on the fused signal."""
        if fused.signal_type == SignalType.BUY and not self.position:
            size = self.calc_position(bar)
            if size > 0:
                self._entry_price = bar.close
                self.buy(size=size)
                logger.info(
                    "[BUY] %s size=%d price=%.2f confidence=%.3f",
                    bar.symbol,
                    size,
                    bar.close,
                    fused.strength,
                )

        elif fused.signal_type == SignalType.SELL and self.position:
            self.close()
            self._entry_price = None
            logger.info(
                "[SELL] %s price=%.2f",
                bar.symbol,
                bar.close,
            )

    def calc_position(self, bar: MarketData) -> int:
        """Calculate position size using Kelly-based formula.

        Uses the entry-price-based stop-loss distance. If no prior entry
        exists, uses a percentage of the current close as a proxy.
        """
        capital = self.broker.getvalue()
        risk = self.p.risk_per_trade
        confidence = (
            self._last_fused.strength
            if hasattr(self, "_last_fused") and self._last_fused
            else 0.5
        )

        # Estimate stop-loss distance
        if self._entry_price is not None:
            stop_distance = abs(bar.close - self._entry_price) or (
                bar.close * self.p.stop_loss_pct
            )
        else:
            stop_distance = bar.close * self.p.stop_loss_pct

        return _calc_kelly_position(capital, risk, confidence, stop_distance)

    # -- CSV logging ------------------------------------------------------

    def _init_log_csv(self) -> None:
        """Write header row to the signal log CSV."""
        if self._log_path is None:
            return
        with open(self._log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "symbol",
                    "signal_type",
                    "strength",
                    "buy_score",
                    "sell_score",
                    "net",
                    "is_conflict",
                    "position",
                    "cash",
                    "value",
                ]
            )

    def _log_signal_csv(self, fused: FusedSignal, bar: MarketData) -> None:
        """Append a row to the signal log CSV."""
        if self._log_path is None:
            return
        with open(self._log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    fused.timestamp.isoformat(),
                    fused.symbol,
                    fused.signal_type.value,
                    round(fused.strength, 4),
                    round(fused.metadata.get("buy_score", 0), 4),
                    round(fused.metadata.get("sell_score", 0), 4),
                    round(fused.metadata.get("net", 0), 4),
                    fused.metadata.get("is_conflict", False),
                    self.position.size if self.position else 0,
                    round(self.broker.getcash(), 2),
                    round(self.broker.getvalue(), 2),
                ]
            )


# ---------------------------------------------------------------------------
# BacktestEngine
# ---------------------------------------------------------------------------


class BacktestEngine:
    """High-level wrapper around ``bt.Cerebro`` for running backtests.

    Usage::

        engine = BacktestEngine()
        results = engine.run(
            symbol="000001",
            start="2023-01-01",
            end="2023-12-31",
            config=PipelineConfig(indicators=["my_rsi"], weights=[1.0]),
        )
    """

    def __init__(
        self,
        cash: float = 1_000_000.0,
        commission: float = 0.001,
        slippage: float = 0.0,
        log_dir: str | None = None,
    ) -> None:
        """
        Args:
            cash: Initial cash.
            commission: Commission rate per trade (e.g. 0.001 = 0.1%).
            slippage: Fixed slippage in price units.
            log_dir: Directory for signal CSV logs.
        """
        self.cash = cash
        self.commission = commission
        self.slippage = slippage
        self.log_dir = log_dir

    def run(
        self,
        symbol: str,
        start: str,
        end: str,
        config: PipelineConfig | None = None,
        **strategy_kwargs: Any,
    ) -> dict[str, Any]:
        """Run a backtest and return analyzer results.

        Args:
            symbol: Ticker symbol (passed to DataLoader).
            start: Start date string (YYYY-MM-DD).
            end: End date string (YYYY-MM-DD).
            config: Pipeline configuration.
            **strategy_kwargs: Extra kwargs forwarded to ``PipelineStrategy``.

        Returns:
            Dict with keys: ``sharpe``, ``drawdown``, ``total_return``,
            ``trade_count``, ``final_value``, ``final_cash``.
        """
        cerebro = bt.Cerebro()

        # -- Load data ----------------------------------------------------------
        data_feed = self._load_data(symbol, start, end)
        cerebro.adddata(data_feed, name=symbol)

        # -- Broker settings ----------------------------------------------------
        cerebro.broker.setcash(self.cash)
        cerebro.broker.setcommission(commission=self.commission)

        # -- Add strategy -------------------------------------------------------
        strat_kwargs: dict[str, Any] = {
            "pipeline_config": config,
            "log_dir": self.log_dir,
        }
        strat_kwargs.update(strategy_kwargs)
        cerebro.addstrategy(PipelineStrategy, **strat_kwargs)

        # -- Analyzers ----------------------------------------------------------
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.03)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

        # -- LIVE-HOOK: for paper trading, replace ``cerebro.run()`` with a
        # live data feed and call ``cerebro.run()`` in a loop or use
        # ``cerebro.runstop()`` / ``cerebro.run()`` with live feeds.
        # Example:
        #     live_feed = MyLiveWebSocketDataFeed()
        #     cerebro.adddata(live_feed)
        #     cerebro.run()

        # -- Run ----------------------------------------------------------------
        logger.info("Starting backtest: %s from %s to %s", symbol, start, end)
        results = cerebro.run()
        strat_result = results[0]

        # -- Collect analyzer results -------------------------------------------
        return self._collect_results(strat_result, cerebro)

    def _load_data(self, symbol: str, start: str, end: str) -> bt.feeds.PandasData:
        """Load OHLCV data and return a Backtrader data feed.

        Tries to use the project's ``DataLoader`` if available; falls back
        to a generic CSV-based feed.

        # LIVE-HOOK: Replace this method with a live data feed class that
        # streams bars from a WebSocket / polling API. The returned object
        # must be a ``bt.DataFeed`` subclass.
        """
        import pandas as pd

        # Attempt to use the project's DataLoader
        try:
            from src.data.loader import DataLoader  # type: ignore

            loader = DataLoader()
            dfs = loader.load_history(
                symbols=symbol,
                start=start.replace("-", ""),
                end=end.replace("-", ""),
            )
            df = dfs.get(symbol) if isinstance(dfs, dict) else dfs
            if df is None:
                raise FileNotFoundError(f"No data returned for {symbol}")
        except ImportError:
            logger.warning(
                "DataLoader not available; falling back to CSV load. "
                "Expected CSV at: data/%s.csv",
                symbol,
            )
            csv_path = Path("data") / f"{symbol}.csv"
            df = pd.read_csv(csv_path, parse_dates=["date"], index_col="date")

        return self._df_to_bt_feed(df, symbol)

    @staticmethod
    def _df_to_bt_feed(df: pd.DataFrame, name: str) -> bt.feeds.PandasData:
        """Convert a DataFrame to a Backtrader PandasData feed.

        Expected columns (case-insensitive):
        ``open``, ``high``, ``low``, ``close``, ``volume``.
        The index must be a ``DatetimeIndex``.
        """
        import pandas as pd

        # Normalise column names to lowercase
        df = df.copy()
        df.columns = [c.lower().strip() for c in df.columns]

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if "date" in df.columns:
                df = df.set_index("date")
            elif "datetime" in df.columns:
                df = df.set_index("datetime")
            else:
                raise ValueError(
                    "DataFrame must have a DatetimeIndex or a 'date'/'datetime' column"
                )

        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        return bt.feeds.PandasData(
            dataname=df,
            name=name,
            datetime=None,  # use index
            open="open",
            high="high",
            low="low",
            close="close",
            volume="volume",
            openinterest=-1,
        )

    @staticmethod
    def _collect_results(strat: bt.Strategy, cerebro: bt.Cerebro) -> dict[str, Any]:
        """Extract analyzer results into a flat dict."""
        sharpe = strat.analyzers.sharpe.get_analysis()
        dd = strat.analyzers.drawdown.get_analysis()
        ret = strat.analyzers.returns.get_analysis()
        trades = strat.analyzers.trades.get_analysis()

        return {
            "sharpe": sharpe.get("sharperatio"),
            "drawdown_pct": round(dd.get("max", {}).get("drawdown", 0), 2),
            "drawdown_money": round(dd.get("max", {}).get("moneydown", 0), 2),
            "total_return_pct": round(ret.get("rtot", 0) * 100, 2),
            "trade_count": trades.get("total", {}).get("total", 0),
            "final_value": round(cerebro.broker.getvalue(), 2),
            "final_cash": round(cerebro.broker.getcash(), 2),
        }
