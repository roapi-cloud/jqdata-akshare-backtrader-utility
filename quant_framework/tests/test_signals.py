"""Tests for the signal layer."""

from datetime import date

import pandas as pd
import pytest

from quant_framework.core.signals.base import Signal, SignalResult, SignalType


class ConcreteSignal(Signal):
    """Concrete signal implementation for testing."""

    @property
    def name(self) -> str:
        return "TestSignal"

    def generate(
        self,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        params: dict | None = None,
    ) -> SignalResult:
        defaults = {"buy_threshold": 0.6, "sell_threshold": 0.4}
        p = self._merge_params(defaults, params)

        if "momentum" in factor_values:
            vals = factor_values["momentum"]
            if isinstance(vals, pd.Series):
                latest = vals.dropna().iloc[-1] if not vals.dropna().empty else 0.5
            else:
                latest = 0.5

            if latest >= p["buy_threshold"]:
                return SignalResult(
                    date=pd.Timestamp("2024-01-15"),
                    signal_type=SignalType.BUY,
                    strength=self._normalize_strength(latest),
                    stocks=["000001"],
                    metadata={"momentum": latest},
                )
            elif latest <= p["sell_threshold"]:
                return SignalResult(
                    date=pd.Timestamp("2024-01-15"),
                    signal_type=SignalType.SELL,
                    strength=self._normalize_strength(latest, 0.0, 0.4),
                    stocks=["000001"],
                    metadata={"momentum": latest},
                )

        return SignalResult(
            date=pd.Timestamp("2024-01-15"),
            signal_type=SignalType.HOLD,
            strength=0.0,
        )


class TestSignalType:
    """Tests for SignalType enum."""

    def test_enum_values(self):
        assert SignalType.BUY.value == "buy"
        assert SignalType.SELL.value == "sell"
        assert SignalType.HOLD.value == "hold"
        assert SignalType.REDUCE.value == "reduce"
        assert SignalType.INCREASE.value == "increase"


class TestSignalResult:
    """Tests for SignalResult dataclass."""

    def test_is_actionable_buy(self):
        sr = SignalResult(
            date=pd.Timestamp("2024-01-15"),
            signal_type=SignalType.BUY,
            strength=0.8,
            stocks=["000001"],
        )
        assert sr.is_actionable() is True

    def test_is_actionable_sell(self):
        sr = SignalResult(
            date=pd.Timestamp("2024-01-15"),
            signal_type=SignalType.SELL,
            strength=0.6,
            stocks=["000001"],
        )
        assert sr.is_actionable() is True

    def test_is_actionable_hold(self):
        sr = SignalResult(
            date=pd.Timestamp("2024-01-15"),
            signal_type=SignalType.HOLD,
            strength=0.0,
        )
        assert sr.is_actionable() is False

    def test_is_actionable_zero_strength(self):
        sr = SignalResult(
            date=pd.Timestamp("2024-01-15"),
            signal_type=SignalType.BUY,
            strength=0.0,
        )
        assert sr.is_actionable() is False

    def test_stock_count_with_stocks(self):
        sr = SignalResult(
            date=pd.Timestamp("2024-01-15"),
            signal_type=SignalType.BUY,
            strength=0.8,
            stocks=["000001", "000002", "600000"],
        )
        assert sr.stock_count() == 3

    def test_stock_count_without_stocks(self):
        sr = SignalResult(
            date=pd.Timestamp("2024-01-15"),
            signal_type=SignalType.HOLD,
            strength=0.0,
        )
        assert sr.stock_count() == 0


class TestSignalBase:
    """Tests for Signal base class utilities."""

    def test_merge_params_no_override(self):
        signal = ConcreteSignal()
        defaults = {"a": 1, "b": 2}
        merged = signal._merge_params(defaults, None)
        assert merged == {"a": 1, "b": 2}

    def test_merge_params_with_override(self):
        signal = ConcreteSignal()
        defaults = {"a": 1, "b": 2}
        merged = signal._merge_params(defaults, {"b": 99})
        assert merged == {"a": 1, "b": 99}

    def test_normalize_strength(self):
        signal = ConcreteSignal()
        assert signal._normalize_strength(0.5, 0.0, 1.0) == 0.5
        assert signal._normalize_strength(1.5, 0.0, 1.0) == 1.0
        assert signal._normalize_strength(-0.5, 0.0, 1.0) == 0.0

    def test_normalize_strength_equal_bounds(self):
        signal = ConcreteSignal()
        assert signal._normalize_strength(0.5, 1.0, 1.0) == 0.5

    def test_repr(self):
        signal = ConcreteSignal()
        assert "TestSignal" in repr(signal)


class TestConcreteSignal:
    """Tests for a concrete signal implementation."""

    def test_buy_signal_when_momentum_high(self):
        signal = ConcreteSignal()
        factors = {"momentum": pd.Series([0.3, 0.5, 0.7, 0.8])}
        result = signal.generate(factors)
        assert result.signal_type == SignalType.BUY
        assert result.strength > 0.0
        assert "000001" in result.stocks

    def test_sell_signal_when_momentum_low(self):
        signal = ConcreteSignal()
        factors = {"momentum": pd.Series([0.5, 0.3, 0.2, 0.1])}
        result = signal.generate(factors)
        assert result.signal_type == SignalType.SELL

    def test_hold_signal_when_momentum_middle(self):
        signal = ConcreteSignal()
        factors = {"momentum": pd.Series([0.5, 0.5, 0.5, 0.5])}
        result = signal.generate(factors)
        assert result.signal_type == SignalType.HOLD
        assert result.strength == 0.0

    def test_custom_thresholds(self):
        signal = ConcreteSignal()
        factors = {"momentum": pd.Series([0.3, 0.4, 0.5])}
        result = signal.generate(factors, params={"buy_threshold": 0.45})
        assert result.signal_type == SignalType.BUY

    def test_empty_factor_values(self):
        signal = ConcreteSignal()
        factors = {"momentum": pd.Series([], dtype=float)}
        result = signal.generate(factors)
        assert result.signal_type == SignalType.HOLD

    def test_missing_factor_key(self):
        signal = ConcreteSignal()
        factors = {"other": pd.Series([1.0, 2.0])}
        result = signal.generate(factors)
        assert result.signal_type == SignalType.HOLD
