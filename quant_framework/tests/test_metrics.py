"""Tests for performance metrics."""

import numpy as np
import pandas as pd
import pytest

from quant_framework.core.backtest.metrics import PerformanceMetrics


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics class."""

    @pytest.fixture
    def metrics(self, sample_equity_curve):
        return PerformanceMetrics(sample_equity_curve)

    @pytest.fixture
    def rising_curve(self):
        dates = pd.date_range("2024-01-01", periods=50, freq="B")
        values = [1_000_000.0 * (1.001**i) for i in range(50)]
        return pd.DataFrame({"date": dates, "total_value": values})

    @pytest.fixture
    def falling_curve(self):
        dates = pd.date_range("2024-01-01", periods=50, freq="B")
        values = [1_000_000.0 * (0.999**i) for i in range(50)]
        return pd.DataFrame({"date": dates, "total_value": values})

    def test_total_return_rising(self, rising_curve):
        metrics = PerformanceMetrics(rising_curve)
        ret = metrics.total_return()
        assert ret > 0

    def test_total_return_falling(self, falling_curve):
        metrics = PerformanceMetrics(falling_curve)
        ret = metrics.total_return()
        assert ret < 0

    def test_total_return_known_value(self):
        dates = pd.date_range("2024-01-01", periods=2, freq="B")
        values = [1_000_000.0, 1_100_000.0]
        curve = pd.DataFrame({"date": dates, "total_value": values})
        metrics = PerformanceMetrics(curve)
        assert abs(metrics.total_return() - 0.10) < 1e-10

    def test_annualized_return_positive(self, rising_curve):
        metrics = PerformanceMetrics(rising_curve)
        ann = metrics.annualized_return()
        assert ann > 0

    def test_volatility_positive(self, sample_equity_curve):
        metrics = PerformanceMetrics(sample_equity_curve)
        vol = metrics.volatility()
        assert vol > 0

    def test_volatility_constant_curve(self):
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        values = [1_000_000.0] * 10
        curve = pd.DataFrame({"date": dates, "total_value": values})
        metrics = PerformanceMetrics(curve)
        assert metrics.volatility() == 0.0

    def test_sharpe_ratio(self, sample_equity_curve):
        metrics = PerformanceMetrics(sample_equity_curve, risk_free_rate=0.03)
        sharpe = metrics.sharpe_ratio()
        assert isinstance(sharpe, float)

    def test_sharpe_zero_volatility(self):
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        values = [1_000_000.0] * 10
        curve = pd.DataFrame({"date": dates, "total_value": values})
        metrics = PerformanceMetrics(curve)
        assert metrics.sharpe_ratio() == 0.0

    def test_max_drawdown_rising(self, rising_curve):
        metrics = PerformanceMetrics(rising_curve)
        mdd = metrics.max_drawdown()
        assert mdd >= 0

    def test_max_drawdown_known_value(self):
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        values = [100.0, 110.0, 90.0, 95.0, 105.0]
        curve = pd.DataFrame({"date": dates, "total_value": values})
        metrics = PerformanceMetrics(curve)
        mdd = metrics.max_drawdown()
        expected = (110.0 - 90.0) / 110.0
        assert abs(mdd - expected) < 1e-10

    def test_max_drawdown_no_drawdown(self, rising_curve):
        metrics = PerformanceMetrics(rising_curve)
        mdd = metrics.max_drawdown()
        assert mdd == 0.0

    def test_calmar_ratio(self, sample_equity_curve):
        metrics = PerformanceMetrics(sample_equity_curve)
        calmar = metrics.calmar_ratio()
        assert isinstance(calmar, float)

    def test_calmar_zero_drawdown(self, rising_curve):
        metrics = PerformanceMetrics(rising_curve)
        assert metrics.calmar_ratio() == 0.0

    def test_all_metrics_returns_dict(self, sample_equity_curve):
        metrics = PerformanceMetrics(sample_equity_curve)
        result = metrics.all_metrics()
        assert isinstance(result, dict)
        expected_keys = {
            "total_return",
            "annualized_return",
            "volatility",
            "sharpe_ratio",
            "max_drawdown",
            "calmar_ratio",
            "win_rate",
            "profit_factor",
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_daily_returns_length(self, sample_equity_curve):
        metrics = PerformanceMetrics(sample_equity_curve)
        assert len(metrics.daily_returns) == len(sample_equity_curve) - 1

    def test_single_data_point(self):
        dates = pd.date_range("2024-01-01", periods=1, freq="B")
        values = [1_000_000.0]
        curve = pd.DataFrame({"date": dates, "total_value": values})
        metrics = PerformanceMetrics(curve)
        assert metrics.total_return() == 0.0
        assert metrics.annualized_return() == 0.0
        assert metrics.volatility() == 0.0

    def test_win_rate_no_trades(self, sample_equity_curve):
        metrics = PerformanceMetrics(sample_equity_curve)
        assert metrics.win_rate() == 0.0

    def test_profit_factor_no_trades(self, sample_equity_curve):
        metrics = PerformanceMetrics(sample_equity_curve)
        assert metrics.profit_factor() == 0.0

    def test_risk_free_rate_affects_sharpe(self, sample_equity_curve):
        m1 = PerformanceMetrics(sample_equity_curve, risk_free_rate=0.0)
        m2 = PerformanceMetrics(sample_equity_curve, risk_free_rate=0.10)
        assert m1.sharpe_ratio() != m2.sharpe_ratio()

    def test_compare_with_known_values(self):
        dates = pd.date_range("2024-01-01", periods=252, freq="B")
        rng = np.random.default_rng(42)
        daily_ret = rng.normal(0.0004, 0.01, 251)
        values = [1_000_000.0]
        for r in daily_ret:
            values.append(values[-1] * (1 + r))
        curve = pd.DataFrame({"date": dates, "total_value": values})

        metrics = PerformanceMetrics(curve, risk_free_rate=0.03)

        total_ret = metrics.total_return()
        assert total_ret > -0.5
        assert total_ret < 2.0

        vol = metrics.volatility()
        assert vol > 0.05
        assert vol < 1.0

        mdd = metrics.max_drawdown()
        assert mdd >= 0
        assert mdd < 1.0
