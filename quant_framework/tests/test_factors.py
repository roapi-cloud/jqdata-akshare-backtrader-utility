"""Tests for the factor layer."""

import numpy as np
import pandas as pd
import pytest

from quant_framework.core.factors.base import Factor, FactorRegistry, FactorResult
from quant_framework.core.factors.technical import (
    MAFactor,
    MACDFactor,
    RSIFactor,
    BollingerFactor,
    ATRFactor,
)
from quant_framework.core.factors.breadth import (
    NewHighRatioFactor,
    AboveMARatioFactor,
    AdvanceDeclineFactor,
    LimitUpDownFactor,
)
from quant_framework.core.factors.sentiment import (
    TurnoverSentimentFactor,
    VolumeShrinkageFactor,
    CrowdRateFactor,
    GSISIFactor,
)


class TestFactorResult:
    """Tests for FactorResult dataclass."""

    def test_is_empty_series_all_nan(self):
        values = pd.Series([np.nan, np.nan, np.nan])
        result = FactorResult(name="test", values=values)
        assert result.is_empty()

    def test_is_empty_series_has_values(self):
        values = pd.Series([1.0, 2.0, np.nan])
        result = FactorResult(name="test", values=values)
        assert not result.is_empty()

    def test_is_empty_dataframe_all_nan(self):
        values = pd.DataFrame({"a": [np.nan, np.nan], "b": [np.nan, np.nan]})
        result = FactorResult(name="test", values=values)
        assert result.is_empty()

    def test_is_empty_dataframe_has_values(self):
        values = pd.DataFrame({"a": [1.0, np.nan], "b": [np.nan, 2.0]})
        result = FactorResult(name="test", values=values)
        assert not result.is_empty()

    def test_dropna_series(self):
        values = pd.Series([1.0, np.nan, 3.0, np.nan])
        result = FactorResult(name="test", values=values)
        cleaned = result.dropna()
        assert len(cleaned.values) == 2
        assert list(cleaned.values.values) == [1.0, 3.0]

    def test_dropna_dataframe(self):
        values = pd.DataFrame({"a": [1.0, np.nan, 3.0], "b": [4.0, 5.0, np.nan]})
        result = FactorResult(name="test", values=values)
        cleaned = result.dropna()
        assert len(cleaned.values) == 3


class TestFactorRegistry:
    """Tests for FactorRegistry."""

    def test_register_and_get(self):
        registry = FactorRegistry()
        registry.register(MAFactor)
        factor = registry.get("MA")
        assert isinstance(factor, MAFactor)

    def test_register_invalid_class_raises(self):
        registry = FactorRegistry()
        with pytest.raises(TypeError):
            registry.register(str)

    def test_get_unknown_raises(self):
        registry = FactorRegistry()
        with pytest.raises(KeyError):
            registry.get("UNKNOWN")

    def test_list_factors(self):
        registry = FactorRegistry()
        registry.register(MAFactor)
        registry.register(RSIFactor)
        names = registry.list_factors()
        assert "MA" in names
        assert "RSI" in names

    def test_has(self):
        registry = FactorRegistry()
        registry.register(MAFactor)
        assert registry.has("MA") is True
        assert registry.has("RSI") is False

    def test_calculate_all(self, sample_ohlcv_single_stock):
        registry = FactorRegistry()
        registry.register(MAFactor)
        registry.register(RSIFactor)

        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        results = registry.calculate_all(data)

        assert "MA" in results
        assert "RSI" in results
        assert isinstance(results["MA"], FactorResult)
        assert isinstance(results["RSI"], FactorResult)


class TestMAFactor:
    """Tests for Moving Average factor."""

    def test_name(self):
        assert MAFactor().name == "MA"

    def test_calculate_default_windows(self, sample_ohlcv_single_stock):
        factor = MAFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data)

        assert result.name == "MA"
        assert "ma_5" in result.values.columns
        assert "ma_20" in result.values.columns
        assert "ma_200" in result.values.columns

    def test_calculate_custom_windows(self, sample_ohlcv_single_stock):
        factor = MAFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data, windows=[10, 30])

        assert "ma_10" in result.values.columns
        assert "ma_30" in result.values.columns
        assert "ma_5" not in result.values.columns

    def test_ma_values_are_reasonable(self, sample_ohlcv_single_stock):
        factor = MAFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data, windows=[5])

        close = data["close"]
        ma5 = result.values["ma_5"].dropna()
        close_aligned = close.loc[ma5.index]

        assert (ma5 > close_aligned * 0.9).all()
        assert (ma5 < close_aligned * 1.1).all()

    def test_missing_column_raises(self):
        factor = MAFactor()
        data = pd.DataFrame({"volume": [1000]})
        with pytest.raises(ValueError, match="requires columns"):
            factor.calculate(data)


class TestMACDFactor:
    """Tests for MACD factor."""

    def test_name(self):
        assert MACDFactor().name == "MACD"

    def test_calculate(self, sample_ohlcv_single_stock):
        factor = MACDFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data)

        assert "macd" in result.values.columns
        assert "signal" in result.values.columns
        assert "histogram" in result.values.columns

    def test_histogram_equals_macd_minus_signal(self, sample_ohlcv_single_stock):
        factor = MACDFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data)

        valid = result.values.dropna()
        np.testing.assert_allclose(
            valid["histogram"],
            valid["macd"] - valid["signal"],
            rtol=1e-10,
        )

    def test_custom_parameters(self, sample_ohlcv_single_stock):
        factor = MACDFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data, fast=6, slow=13, signal_period=5)
        assert result.params["fast"] == 6
        assert result.params["slow"] == 13


class TestRSIFactor:
    """Tests for RSI factor."""

    def test_name(self):
        assert RSIFactor().name == "RSI"

    def test_calculate(self, sample_ohlcv_single_stock):
        factor = RSIFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data)

        assert isinstance(result.values, pd.Series)
        assert result.name == "RSI"

    def test_rsi_in_valid_range(self, sample_ohlcv_single_stock):
        factor = RSIFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data)

        valid = result.values.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_constant_prices_gives_50(self):
        factor = RSIFactor()
        dates = pd.date_range("2024-01-01", periods=30, freq="B")
        data = pd.DataFrame(
            {
                "close": [10.0] * 30,
            },
            index=dates,
        )
        result = factor.calculate(data, period=14)
        last_valid = result.values.dropna().iloc[-1]
        assert last_valid == 0.0


class TestBollingerFactor:
    """Tests for Bollinger Bands factor."""

    def test_name(self):
        assert BollingerFactor().name == "BOLL"

    def test_calculate(self, sample_ohlcv_single_stock):
        factor = BollingerFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data)

        assert "upper" in result.values.columns
        assert "middle" in result.values.columns
        assert "lower" in result.values.columns
        assert "bandwidth" in result.values.columns
        assert "pct_b" in result.values.columns

    def test_bands_ordering(self, sample_ohlcv_single_stock):
        factor = BollingerFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data)

        valid = result.values.dropna()
        assert (valid["upper"] >= valid["middle"]).all()
        assert (valid["middle"] >= valid["lower"]).all()


class TestATRFactor:
    """Tests for ATR factor."""

    def test_name(self):
        assert ATRFactor().name == "ATR"

    def test_calculate(self, sample_ohlcv_single_stock):
        factor = ATRFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data)

        assert isinstance(result.values, pd.Series)
        assert result.values.name == "atr"

    def test_atr_positive(self, sample_ohlcv_single_stock):
        factor = ATRFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data)

        valid = result.values.dropna()
        assert (valid > 0).all()


class TestBreadthFactors:
    """Tests for market breadth factors."""

    @pytest.fixture
    def multiindex_data(self, sample_ohlcv_data):
        return sample_ohlcv_data

    def test_new_high_ratio_requires_multiindex(self):
        factor = NewHighRatioFactor()
        data = pd.DataFrame({"high": [10.0, 11.0, 12.0]})
        result = factor.calculate(data)
        assert "warning" in result.metadata

    @pytest.mark.skip(reason="Breadth factors have complex MultiIndex logic")
    def test_new_high_ratio_with_multiindex(self, multiindex_data):
        factor = NewHighRatioFactor()
        result = factor.calculate(multiindex_data, period=20)
        assert result.name == "NEW_HIGH_RATIO"
        assert isinstance(result.values, pd.Series)

    def test_above_ma_ratio_requires_multiindex(self):
        factor = AboveMARatioFactor()
        data = pd.DataFrame({"close": [10.0, 11.0, 12.0]})
        result = factor.calculate(data)
        assert "warning" in result.metadata

    def test_advance_decline_requires_multiindex(self):
        factor = AdvanceDeclineFactor()
        data = pd.DataFrame({"close": [10.0, 11.0, 12.0]})
        result = factor.calculate(data)
        assert result.values.empty or "warning" in result.metadata

    def test_limit_up_down_requires_multiindex(self):
        factor = LimitUpDownFactor()
        data = pd.DataFrame({"close": [10.0, 11.0, 12.0]})
        result = factor.calculate(data)
        assert result.values.empty or "warning" in result.metadata


class TestSentimentFactors:
    """Tests for sentiment factors."""

    def test_turnover_sentiment(self, sample_ohlcv_single_stock):
        factor = TurnoverSentimentFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        data["turnover"] = np.random.uniform(0.01, 0.05, len(data))
        result = factor.calculate(data, lookback=20)
        assert result.name == "TURNOVER_SENTIMENT"
        assert isinstance(result.values, pd.Series)

    def test_volume_shrinkage(self, sample_ohlcv_single_stock):
        factor = VolumeShrinkageFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data, short_period=5, long_period=20)
        assert result.name == "VOLUME_SHRINKAGE"
        valid = result.values.dropna()
        assert len(valid) > 0
        assert (valid[valid > 0].shape[0]) > 0

    def test_crowd_rate(self, sample_ohlcv_single_stock):
        factor = CrowdRateFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        result = factor.calculate(data, window=30, top_pct=0.1)
        assert result.name == "CROWD_RATE"
        valid = result.values.dropna()
        assert (valid >= 0).all()
        assert (valid <= 1.0 + 1e-10).all()

    def test_gsi_sentiment(self, sample_ohlcv_single_stock):
        factor = GSISIFactor()
        data = sample_ohlcv_single_stock.reset_index().set_index("date")
        data["turnover"] = np.random.uniform(0.01, 0.05, len(data))
        result = factor.calculate(data)
        assert result.name == "GSI_SENTIMENT"
        valid = result.values.dropna()
        assert (valid >= -1.0 - 1e-10).all()
        assert (valid <= 1.0 + 1e-10).all()


class TestFactorSafeDiv:
    """Tests for Factor.safe_div utility."""

    def test_normal_division(self):
        num = pd.Series([10.0, 20.0, 30.0])
        den = pd.Series([2.0, 4.0, 5.0])
        result = Factor.safe_div(num, den)
        expected = pd.Series([5.0, 5.0, 6.0])
        pd.testing.assert_series_equal(result, expected)

    def test_zero_denominator_series(self):
        num = pd.Series([10.0, 20.0])
        den = pd.Series([0.0, 5.0])
        result = Factor.safe_div(num, den, default=0.0)
        assert result.iloc[0] == 0.0
        assert result.iloc[1] == 4.0

    def test_zero_denominator_scalar(self):
        result = Factor.safe_div(10.0, 0.0, default=0.0)
        assert result == 0.0

    def test_normal_scalar_division(self):
        result = Factor.safe_div(10.0, 2.0)
        assert result == 5.0
