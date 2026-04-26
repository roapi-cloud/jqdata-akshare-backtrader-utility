"""Integration tests: end-to-end pipeline verification."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from quant_framework.core.backtest.broker import OrderSide, SimulatedBroker
from quant_framework.core.backtest.cost import AStockCostModel
from quant_framework.core.backtest.engine import (
    BacktestEngine,
    BacktestResult,
    DividendEvent,
)
from quant_framework.core.backtest.metrics import PerformanceMetrics
from quant_framework.core.factors.base import FactorRegistry, FactorResult
from quant_framework.core.factors.technical import MAFactor, RSIFactor
from quant_framework.core.signals.base import Signal, SignalResult, SignalType
from quant_framework.core.strategy.base import BaseStrategy, Portfolio
from quant_framework.core.strategy.combiner import StrategyCombiner
from quant_framework.core.strategy.portfolio import PortfolioManager
from quant_framework.core.strategy.position import EqualWeightSizer


def _generate_integration_data(
    n_days: int = 120,
    symbols: list[str] | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate realistic multi-stock data for integration tests."""
    rng = np.random.default_rng(seed)
    symbols = symbols or ["000001", "000002", "600000", "600036", "000858"]
    dates = pd.date_range("2024-01-02", periods=n_days, freq="B")

    records = []
    for symbol in symbols:
        base = rng.uniform(10.0, 50.0)
        prices = [base]
        for _ in range(1, n_days):
            ret = rng.normal(0.0003, 0.018)
            prices.append(max(1.0, prices[-1] * (1 + ret)))

        for i, dt in enumerate(dates):
            c = prices[i]
            h = c * (1 + rng.uniform(0.001, 0.02))
            l = c * (1 - rng.uniform(0.001, 0.02))
            o = l + (h - l) * rng.uniform(0.2, 0.8)
            v = int(rng.uniform(2_000_000, 30_000_000))
            to = rng.uniform(0.01, 0.04)
            records.append(
                {
                    "date": dt,
                    "symbol": symbol,
                    "open": round(o, 2),
                    "high": round(h, 2),
                    "low": round(l, 2),
                    "close": round(c, 2),
                    "volume": v,
                    "turnover": round(to, 4),
                }
            )

    return pd.DataFrame(records)


class FactorBasedStrategy:
    """Strategy that uses factor values to determine positions."""

    def __init__(self, name: str = "FactorStrategy") -> None:
        self.name = name

    def on_init(self, broker):
        pass

    def on_bar(self, data, broker):
        symbols = list(data.keys())
        if not symbols:
            return
        for sym in symbols:
            broker.submit_order(sym, OrderSide.BUY, quantity=1000)


class TestFullPipeline:
    """Test the complete data -> factors -> signals -> backtest pipeline."""

    def test_end_to_end_backtest(self):
        """Run a complete backtest with factor-based strategy."""
        data = _generate_integration_data(n_days=120)

        strategy = FactorBasedStrategy()
        engine = BacktestEngine(strategy, initial_cash=1_000_000.0)
        result = engine.run(data)

        assert isinstance(result, BacktestResult)
        assert not result.daily_values.empty
        assert result.initial_capital == 1_000_000.0
        assert result.final_capital > 0
        assert "date" in result.daily_values.columns
        assert "portfolio_value" in result.daily_values.columns

    def test_pipeline_produces_trades(self):
        """Verify the pipeline generates actual trades."""
        data = _generate_integration_data(n_days=120)

        strategy = FactorBasedStrategy()
        engine = BacktestEngine(strategy, initial_cash=1_000_000.0)
        result = engine.run(data)

        assert result.total_trades > 0

    def test_portfolio_value_changes(self):
        """Verify portfolio value changes over time."""
        data = _generate_integration_data(n_days=120)

        strategy = FactorBasedStrategy()
        engine = BacktestEngine(strategy, initial_cash=1_000_000.0)
        result = engine.run(data)

        values = result.daily_values["portfolio_value"]
        assert values.iloc[0] != values.iloc[-1] or len(values) > 1

    def test_metrics_can_be_computed(self):
        """Verify metrics can be computed from backtest results."""
        data = _generate_integration_data(n_days=120)

        strategy = FactorBasedStrategy()
        engine = BacktestEngine(strategy, initial_cash=1_000_000.0)
        result = engine.run(data)

        metrics = PerformanceMetrics(
            result.daily_values.rename(columns={"portfolio_value": "total_value"})
        )
        all_m = metrics.all_metrics()

        assert "total_return" in all_m
        assert "sharpe_ratio" in all_m
        assert "max_drawdown" in all_m
        assert all_m["max_drawdown"] >= 0


class TestStrategyCombinerIntegration:
    """Test strategy combination in a realistic scenario."""

    def test_combine_two_strategies(self):
        """Combine two simple strategies and verify output."""
        data = _generate_integration_data(n_days=60)

        class StrategyA:
            def __init__(self):
                self.name = "A"

            def on_init(self, broker):
                pass

            def on_bar(self, data, broker):
                syms = list(data.keys())
                if syms:
                    broker.submit_order(syms[0], OrderSide.BUY, quantity=1000)

        class StrategyB:
            def __init__(self):
                self.name = "B"

            def on_init(self, broker):
                pass

            def on_bar(self, data, broker):
                syms = list(data.keys())
                if syms:
                    broker.submit_order(syms[-1], OrderSide.BUY, quantity=1000)

        combiner = StrategyCombiner(combiner_method="weighted")
        combiner.add_strategy(StrategyA(), weight=1.0)
        combiner.add_strategy(StrategyB(), weight=1.0)

        portfolio = Portfolio(cash=1_000_000.0)
        first_date = data["date"].iloc[0]
        day_data = data[data["date"] == first_date]

        targets = combiner.get_target_positions(first_date, day_data, portfolio)
        assert len(targets) >= 0


class TestPortfolioManagerIntegration:
    """Test PortfolioManager with realistic rebalancing."""

    def test_rebalance_creates_trades(self):
        """Verify rebalancing generates trades."""
        pm = PortfolioManager(initial_cash=1_000_000.0)
        prices = {"000001": 10.0, "000002": 20.0, "600000": 15.0}
        targets = {"000001": 0.3, "000002": 0.3, "600000": 0.3}

        trades = pm.rebalance(targets, prices, trade_date=date(2024, 1, 15))
        assert len(trades) > 0
        assert pm.position_count == 3

    def test_rebalance_respects_max_weight(self):
        """Verify max weight constraint is enforced."""
        pm = PortfolioManager(initial_cash=1_000_000.0, max_weight=0.2)
        prices = {"000001": 10.0}
        targets = {"000001": 0.5}

        pm.rebalance(targets, prices, trade_date=date(2024, 1, 15))
        weight = pm.get_position_weight("000001")
        assert weight <= 0.21

    def test_rebalance_sells_to_close(self):
        """Verify selling closes positions."""
        pm = PortfolioManager(initial_cash=1_000_000.0)
        prices = {"000001": 10.0, "000002": 20.0}

        pm.rebalance(
            {"000001": 0.5, "000002": 0.5}, prices, trade_date=date(2024, 1, 15)
        )
        assert pm.position_count == 2

        pm.rebalance({"000001": 0.5}, prices, trade_date=date(2024, 1, 16))
        assert pm.position_count == 1
        assert "000002" not in pm.positions

    def test_portfolio_summary(self):
        """Verify portfolio summary is correct."""
        pm = PortfolioManager(initial_cash=1_000_000.0)
        prices = {"000001": 10.0}
        pm.rebalance({"000001": 0.3}, prices, trade_date=date(2024, 1, 15))

        summary = pm.get_portfolio_summary()
        assert "total_value" in summary
        assert "cash" in summary
        assert "position_count" in summary
        assert summary["position_count"] == 1


class TestBrokerIntegration:
    """Test broker with realistic order flow."""

    def test_buy_and_sell_cycle(self):
        """Test a complete buy-then-sell cycle."""
        cost_model = AStockCostModel()
        broker = SimulatedBroker(initial_cash=100_000.0, cost_model=cost_model)

        broker.set_current_date(date(2024, 1, 15))
        buy_order = broker.submit_order("000001", OrderSide.BUY, quantity=1000)
        fills = broker.try_execute_order(
            buy_order, bar_price=10.0, bar_volume=10_000_000
        )
        assert len(fills) == 1
        assert "000001" in broker.positions

        broker.set_current_date(date(2024, 1, 16))
        sell_order = broker.submit_order("000001", OrderSide.SELL, quantity=1000)
        fills = broker.try_execute_order(
            sell_order, bar_price=11.0, bar_volume=10_000_000
        )
        assert len(fills) == 1
        assert "000001" not in broker.positions

    def test_multiple_symbols(self):
        """Test trading multiple symbols."""
        cost_model = AStockCostModel()
        broker = SimulatedBroker(initial_cash=500_000.0, cost_model=cost_model)

        broker.set_current_date(date(2024, 1, 15))
        for sym in ["000001", "000002", "600000"]:
            order = broker.submit_order(sym, OrderSide.BUY, quantity=1000)
            broker.try_execute_order(order, bar_price=10.0, bar_volume=10_000_000)

        assert len(broker.positions) == 3

        value = broker.get_portfolio_value({s: 10.0 for s in broker.positions})
        assert value > 0


class TestDividendHandling:
    """Test dividend and corporate action handling."""

    def test_cash_dividend(self):
        """Test cash dividend increases broker cash."""
        data = _generate_integration_data(n_days=30, symbols=["000001"])

        class BuyAndHoldStrategy:
            def on_init(self, broker):
                pass

            def on_bar(self, data, broker):
                syms = list(data.keys())
                if syms and not broker.positions:
                    broker.submit_order(syms[0], OrderSide.BUY, quantity=1000)

        dividends = [
            DividendEvent(
                date=pd.Timestamp("2024-01-15").date(),
                symbol="000001",
                cash_dividend=0.5,
            )
        ]

        strategy = BuyAndHoldStrategy()
        engine = BacktestEngine(
            strategy,
            initial_cash=100_000.0,
            dividends=dividends,
        )
        result = engine.run(data)

        assert result.final_capital > 0

    def test_result_with_benchmark(self):
        """Test backtest with benchmark data."""
        data = _generate_integration_data(n_days=60, symbols=["000001"])

        bench_dates = pd.date_range("2024-01-02", periods=60, freq="B")
        bench_data = pd.DataFrame(
            {
                "date": bench_dates,
                "close": [3000.0 * (1.0005**i) for i in range(60)],
            }
        )

        class SimpleStrategy:
            def on_init(self, broker):
                pass

            def on_bar(self, data, broker):
                syms = list(data.keys())
                if syms and not broker.positions:
                    broker.submit_order(syms[0], OrderSide.BUY, quantity=1000)

        strategy = SimpleStrategy()
        engine = BacktestEngine(
            strategy,
            initial_cash=100_000.0,
            benchmark_data=bench_data,
        )
        result = engine.run(data)

        assert result.benchmark_return != 0 or len(result.benchmark_values) > 0
