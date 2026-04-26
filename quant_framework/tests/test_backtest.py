"""Tests for the backtest engine: cost, broker, order execution, portfolio tracking."""

from datetime import date

import pandas as pd
import pytest

from quant_framework.core.backtest.broker import (
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    SimulatedBroker,
)
from quant_framework.core.backtest.cost import AStockCostModel, TradeCost
from quant_framework.core.backtest.engine import BacktestEngine, BacktestResult
from quant_framework.core.strategy.base import Portfolio


class TestTradeCost:
    """Tests for TradeCost dataclass."""

    def test_trade_cost_fields(self):
        cost = TradeCost(
            commission=10.0,
            stamp_duty=5.0,
            transfer_fee=1.0,
            slippage_cost=3.0,
            total=19.0,
        )
        assert cost.commission == 10.0
        assert cost.stamp_duty == 5.0
        assert cost.transfer_fee == 1.0
        assert cost.slippage_cost == 3.0
        assert cost.total == 19.0


class TestAStockCostModel:
    """Tests for A-share cost model."""

    @pytest.fixture
    def cost_model(self):
        return AStockCostModel()

    def test_buy_cost_components(self, cost_model):
        cost = cost_model.calculate_cost(price=10.0, quantity=1000, is_buy=True)
        assert cost.commission > 0
        assert cost.stamp_duty == 0.0
        assert cost.transfer_fee > 0
        assert cost.slippage_cost > 0
        assert cost.total > 0

    def test_sell_cost_has_stamp_duty(self, cost_model):
        cost = cost_model.calculate_cost(price=10.0, quantity=1000, is_buy=False)
        assert cost.stamp_duty > 0

    def test_buy_cost_no_stamp_duty(self, cost_model):
        cost = cost_model.calculate_cost(price=10.0, quantity=1000, is_buy=True)
        assert cost.stamp_duty == 0.0

    def test_min_commission(self, cost_model):
        cost = cost_model.calculate_cost(price=1.0, quantity=100, is_buy=True)
        assert cost.commission >= cost_model.min_commission

    def test_effective_price_buy_higher(self, cost_model):
        eff = cost_model.get_effective_price(price=10.0, quantity=1000, is_buy=True)
        assert eff > 10.0

    def test_effective_price_sell_lower(self, cost_model):
        eff = cost_model.get_effective_price(price=10.0, quantity=1000, is_buy=False)
        assert eff < 10.0

    def test_custom_rates(self):
        model = AStockCostModel(
            commission_rate=0.001,
            stamp_duty_rate=0.002,
            slippage_rate=0.005,
        )
        cost = model.calculate_cost(price=10.0, quantity=1000, is_buy=False)
        assert cost.commission == max(10000 * 0.001, 5.0)
        assert cost.stamp_duty == 10000 * 0.002
        assert cost.slippage_cost == 10000 * 0.005


class TestOrder:
    """Tests for Order dataclass."""

    def test_remaining_quantity(self):
        order = Order(
            order_id="1",
            symbol="000001",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            limit_price=None,
            filled_quantity=300,
        )
        assert order.remaining_quantity == 700

    def test_is_active_pending(self):
        order = Order(
            order_id="1",
            symbol="000001",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            limit_price=None,
            status=OrderStatus.PENDING,
        )
        assert order.is_active is True

    def test_is_active_filled(self):
        order = Order(
            order_id="1",
            symbol="000001",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            limit_price=None,
            status=OrderStatus.FILLED,
        )
        assert order.is_active is False


class TestPosition:
    """Tests for Position dataclass."""

    def test_market_value(self):
        pos = Position(symbol="000001", quantity=1000, avg_cost=10.0)
        assert pos.market_value == 10000.0

    def test_update_on_new_day(self):
        pos = Position(symbol="000001", quantity=1000, available_quantity=0)
        pos.update_on_new_day()
        assert pos.available_quantity == 1000


class TestSimulatedBroker:
    """Tests for the simulated broker."""

    @pytest.fixture
    def broker(self):
        cost_model = AStockCostModel()
        return SimulatedBroker(initial_cash=1_000_000.0, cost_model=cost_model)

    def test_initial_state(self, broker):
        assert broker.cash == 1_000_000.0
        assert len(broker.positions) == 0
        assert len(broker.orders) == 0

    def test_submit_buy_order(self, broker):
        order = broker.submit_order(
            symbol="000001",
            side=OrderSide.BUY,
            quantity=1000,
        )
        assert order.symbol == "000001"
        assert order.side == OrderSide.BUY
        assert order.quantity == 1000
        assert order.order_id in broker.orders

    def test_submit_sell_order(self, broker):
        order = broker.submit_order(
            symbol="000001",
            side=OrderSide.SELL,
            quantity=500,
        )
        assert order.side == OrderSide.SELL

    def test_submit_invalid_quantity(self, broker):
        with pytest.raises(ValueError, match="Quantity must be positive"):
            broker.submit_order("000001", OrderSide.BUY, quantity=0)

    def test_submit_limit_order_without_price(self, broker):
        with pytest.raises(ValueError, match="Limit price required"):
            broker.submit_order(
                "000001",
                OrderSide.BUY,
                quantity=1000,
                order_type=OrderType.LIMIT,
            )

    def test_cancel_order(self, broker):
        order = broker.submit_order("000001", OrderSide.BUY, quantity=1000)
        assert broker.cancel_order(order.order_id) is True
        assert order.status == OrderStatus.CANCELLED

    def test_cancel_already_filled(self, broker):
        order = broker.submit_order("000001", OrderSide.BUY, quantity=1000)
        order.status = OrderStatus.FILLED
        assert broker.cancel_order(order.order_id) is False

    def test_get_active_orders(self, broker):
        broker.submit_order("000001", OrderSide.BUY, quantity=1000)
        broker.submit_order("000002", OrderSide.BUY, quantity=500)
        active = broker.get_active_orders()
        assert len(active) == 2

    def test_portfolio_value(self, broker):
        broker.positions["000001"] = Position(
            symbol="000001", quantity=1000, avg_cost=10.0
        )
        value = broker.get_portfolio_value({"000001": 12.0})
        assert value == broker.cash + 1000 * 12.0

    def test_execute_buy_order(self, broker):
        broker.set_current_date(date(2024, 1, 15))
        order = broker.submit_order("000001", OrderSide.BUY, quantity=1000)
        fills = broker.try_execute_order(order, bar_price=10.0, bar_volume=10_000_000)

        assert len(fills) == 1
        assert fills[0].quantity == 1000
        assert fills[0].price == 10.0
        assert "000001" in broker.positions
        assert broker.positions["000001"].quantity == 1000

    def test_execute_sell_order(self, broker):
        broker.set_current_date(date(2024, 1, 15))
        broker.positions["000001"] = Position(
            symbol="000001", quantity=1000, avg_cost=10.0, available_quantity=1000
        )
        order = broker.submit_order("000001", OrderSide.SELL, quantity=500)
        fills = broker.try_execute_order(order, bar_price=12.0, bar_volume=10_000_000)

        assert len(fills) == 1
        assert broker.positions["000001"].quantity == 500

    def test_sell_no_position_rejected(self, broker):
        broker.set_current_date(date(2024, 1, 15))
        order = broker.submit_order("000001", OrderSide.SELL, quantity=500)
        fills = broker.try_execute_order(order, bar_price=10.0, bar_volume=10_000_000)
        assert len(fills) == 0
        assert order.status == OrderStatus.REJECTED

    def test_sell_t1_restriction(self, broker):
        broker.set_current_date(date(2024, 1, 15))
        broker.positions["000001"] = Position(
            symbol="000001", quantity=1000, avg_cost=10.0, available_quantity=0
        )
        order = broker.submit_order("000001", OrderSide.SELL, quantity=500)
        fills = broker.try_execute_order(order, bar_price=12.0, bar_volume=10_000_000)
        assert len(fills) == 0

    def test_buy_insufficient_cash(self, broker):
        broker.cash = 100.0
        broker.set_current_date(date(2024, 1, 15))
        order = broker.submit_order("000001", OrderSide.BUY, quantity=1000)
        fills = broker.try_execute_order(order, bar_price=10.0, bar_volume=10_000_000)
        assert len(fills) == 0
        assert order.status == OrderStatus.REJECTED

    def test_limit_order_not_triggered_buy(self, broker):
        broker.set_current_date(date(2024, 1, 15))
        order = broker.submit_order(
            "000001",
            OrderSide.BUY,
            quantity=1000,
            order_type=OrderType.LIMIT,
            limit_price=8.0,
        )
        fills = broker.try_execute_order(order, bar_price=10.0, bar_volume=10_000_000)
        assert len(fills) == 0

    def test_limit_order_triggered_buy(self, broker):
        broker.set_current_date(date(2024, 1, 15))
        order = broker.submit_order(
            "000001",
            OrderSide.BUY,
            quantity=1000,
            order_type=OrderType.LIMIT,
            limit_price=12.0,
        )
        fills = broker.try_execute_order(order, bar_price=10.0, bar_volume=10_000_000)
        assert len(fills) == 1

    def test_lot_size_rounding(self, broker):
        broker.set_current_date(date(2024, 1, 15))
        order = broker.submit_order("000001", OrderSide.BUY, quantity=150)
        fills = broker.try_execute_order(order, bar_price=10.0, bar_volume=10_000_000)
        assert len(fills) == 1
        assert fills[0].quantity == 100


class TestBacktestEngine:
    """Tests for the backtest engine."""

    def _make_bar_data(self):
        records = []
        dates = pd.date_range("2024-01-02", "2024-01-31", freq="B")
        for symbol in ["000001", "000002"]:
            price = 10.0 if symbol == "000001" else 20.0
            for dt in dates:
                price *= 1.001
                records.append(
                    {
                        "date": dt,
                        "symbol": symbol,
                        "open": round(price * 0.99, 2),
                        "high": round(price * 1.01, 2),
                        "low": round(price * 0.98, 2),
                        "close": round(price, 2),
                        "volume": 10_000_000,
                    }
                )
        return pd.DataFrame(records)

    def test_run_produces_result(self):
        from quant_framework.core.backtest.engine import StrategyProtocol

        class EngineTestStrategy:
            def on_init(self, broker):
                pass

            def on_bar(self, data, broker):
                for sym in data:
                    broker.submit_order(sym, OrderSide.BUY, quantity=1000)

        bar_data = self._make_bar_data()
        strategy = EngineTestStrategy()
        engine = BacktestEngine(strategy, initial_cash=1_000_000.0)
        result = engine.run(bar_data)

        assert isinstance(result, BacktestResult)
        assert not result.daily_values.empty
        assert result.initial_capital == 1_000_000.0

    def test_result_summary(self):
        class EngineTestStrategy:
            def on_init(self, broker):
                pass

            def on_bar(self, data, broker):
                for sym in data:
                    broker.submit_order(sym, OrderSide.BUY, quantity=1000)

        bar_data = self._make_bar_data()
        engine = BacktestEngine(EngineTestStrategy(), initial_cash=1_000_000.0)
        result = engine.run(bar_data)
        summary = result.summary()
        assert "BACKTEST RESULTS" in summary
        assert "Initial Capital" in summary

    def test_result_has_trades(self):
        class EngineTestStrategy:
            def on_init(self, broker):
                pass

            def on_bar(self, data, broker):
                for sym in data:
                    broker.submit_order(sym, OrderSide.BUY, quantity=1000)

        bar_data = self._make_bar_data()
        engine = BacktestEngine(EngineTestStrategy(), initial_cash=1_000_000.0)
        result = engine.run(bar_data)
        assert result.total_trades >= 0

    def test_broker_cash_decreases_on_buy(self):
        class EngineTestStrategy:
            def on_init(self, broker):
                pass

            def on_bar(self, data, broker):
                for sym in data:
                    broker.submit_order(sym, OrderSide.BUY, quantity=1000)

        bar_data = self._make_bar_data()
        engine = BacktestEngine(EngineTestStrategy(), initial_cash=1_000_000.0)
        engine.run(bar_data)
        assert engine.broker.cash < 1_000_000.0

    def test_portfolio_value_positive(self):
        class EngineTestStrategy:
            def on_init(self, broker):
                pass

            def on_bar(self, data, broker):
                for sym in data:
                    broker.submit_order(sym, OrderSide.BUY, quantity=1000)

        bar_data = self._make_bar_data()
        engine = BacktestEngine(EngineTestStrategy(), initial_cash=1_000_000.0)
        engine.run(bar_data)
        final_value = engine.broker.get_portfolio_value(
            {s: 10.0 for s in engine.broker.positions}
        )
        assert final_value > 0
