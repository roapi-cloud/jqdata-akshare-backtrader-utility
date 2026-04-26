"""Pytest fixtures for the quant framework tests."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from quant_framework.core.backtest.broker import SimulatedBroker
from quant_framework.core.backtest.cost import AStockCostModel
from quant_framework.core.strategy.base import BaseStrategy, Portfolio
from quant_framework.core.strategy.portfolio import PortfolioManager
from quant_framework.core.data.base import DataSource


def _generate_ohlcv_data(
    start_date: date,
    end_date: date,
    symbols: list[str] | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate realistic OHLCV data for testing.

    Args:
        start_date: Start date.
        end_date: End date.
        symbols: List of stock codes.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with MultiIndex (date, code) and OHLCV columns.
    """
    rng = np.random.default_rng(seed)
    symbols = symbols or ["000001", "000002", "600000"]

    # Generate trading days (skip weekends)
    all_dates = pd.date_range(start=start_date, end=end_date, freq="B")

    records = []
    for symbol in symbols:
        base_price = rng.uniform(10.0, 50.0)
        prices = [base_price]
        for _ in range(1, len(all_dates)):
            ret = rng.normal(0.0005, 0.02)
            prices.append(prices[-1] * (1 + ret))

        for i, dt in enumerate(all_dates):
            close = prices[i]
            daily_range = close * rng.uniform(0.005, 0.03)
            high = close + daily_range * rng.uniform(0.3, 0.7)
            low = close - daily_range * rng.uniform(0.3, 0.7)
            open_price = low + (high - low) * rng.uniform(0.2, 0.8)
            volume = int(rng.uniform(1_000_000, 50_000_000))
            amount = volume * close * rng.uniform(0.8, 1.2)
            turnover = rng.uniform(0.01, 0.05)

            records.append(
                {
                    "date": dt,
                    "code": symbol,
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": volume,
                    "amount": round(amount, 2),
                    "turnover": round(turnover, 4),
                }
            )

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index(["date", "code"]).sort_index()
    return df


@pytest.fixture
def sample_ohlcv_data() -> pd.DataFrame:
    """Sample OHLCV data with 3 stocks over ~60 trading days."""
    start = date(2024, 1, 1)
    end = date(2024, 3, 31)
    return _generate_ohlcv_data(start, end, symbols=["000001", "000002", "600000"])


@pytest.fixture
def sample_ohlcv_single_stock() -> pd.DataFrame:
    """Sample OHLCV data for a single stock."""
    start = date(2024, 1, 1)
    end = date(2024, 6, 30)
    return _generate_ohlcv_data(start, end, symbols=["000001"])


@pytest.fixture
def sample_ohlcv_long() -> pd.DataFrame:
    """Longer sample OHLCV data (~1 year) for more robust tests."""
    start = date(2023, 1, 1)
    end = date(2023, 12, 31)
    return _generate_ohlcv_data(
        start, end, symbols=["000001", "000002", "600000", "600036", "000858"]
    )


@pytest.fixture
def sample_portfolio() -> Portfolio:
    """Sample portfolio with initial cash."""
    return Portfolio(cash=1_000_000.0)


@pytest.fixture
def sample_portfolio_manager() -> PortfolioManager:
    """Sample PortfolioManager with default settings."""
    return PortfolioManager(initial_cash=1_000_000.0)


@pytest.fixture
def sample_broker() -> SimulatedBroker:
    """Sample simulated broker with A-share cost model."""
    cost_model = AStockCostModel()
    return SimulatedBroker(initial_cash=1_000_000.0, cost_model=cost_model)


@pytest.fixture
def sample_cost_model() -> AStockCostModel:
    """Sample A-share cost model."""
    return AStockCostModel()


class MockDataSource(DataSource):
    """Mock data source that returns generated data without network calls."""

    def __init__(self, data: pd.DataFrame | None = None) -> None:
        self._data = data
        self._call_log: list[tuple] = []

    def get_index_prices(
        self, index_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        self._call_log.append(("get_index_prices", index_code, start_date, end_date))
        if self._data is not None:
            return self._data[self._data["code"] == index_code].copy()
        return pd.DataFrame()

    def get_stock_prices(
        self, stock_codes: list[str], start_date: str, end_date: str
    ) -> pd.DataFrame:
        self._call_log.append(("get_stock_prices", stock_codes, start_date, end_date))
        if self._data is not None:
            mask = self._data.reset_index()["code"].isin(stock_codes)
            return self._data.reset_index()[mask].copy()
        return pd.DataFrame()

    def get_index_stocks(self, index_code: str, date: str) -> list[str]:
        self._call_log.append(("get_index_stocks", index_code, date))
        return ["000001", "000002", "600000"]

    def get_all_stocks(self, date: str) -> list[str]:
        self._call_log.append(("get_all_stocks", date))
        return ["000001", "000002", "600000", "600036", "000858"]

    def get_trade_days(self, start_date: str, end_date: str) -> list[date]:
        self._call_log.append(("get_trade_days", start_date, end_date))
        days = pd.date_range(start=start_date, end=end_date, freq="B")
        return [d.date() for d in days]

    def get_valuation(self, stock_codes: list[str], date: str) -> pd.DataFrame:
        self._call_log.append(("get_valuation", stock_codes, date))
        records = []
        for code in stock_codes:
            records.append(
                {
                    "code": code,
                    "pe_ratio": 15.0,
                    "pb_ratio": 1.5,
                    "market_cap": 1e10,
                    "circ_market_cap": 5e9,
                }
            )
        return pd.DataFrame(records)

    def get_industry_stocks(self, industry_code: str, date: str) -> list[str]:
        self._call_log.append(("get_industry_stocks", industry_code, date))
        return ["000001", "000002"]


@pytest.fixture
def mock_data_source(sample_ohlcv_data: pd.DataFrame) -> MockDataSource:
    """Mock data source with sample OHLCV data."""
    return MockDataSource(data=sample_ohlcv_data)


class SimpleTestStrategy(BaseStrategy):
    """Simple strategy for testing: equal weight on all stocks."""

    def __init__(self, name: str = "SimpleTest") -> None:
        super().__init__(name=name)
        self._n_stocks = 3

    def get_target_positions(
        self,
        trade_date: date,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> dict[str, float]:
        codes = (
            data.index.get_level_values(1).unique().tolist()
            if hasattr(data.index, "nlevels")
            else data.get("code", []).tolist()
        )
        if not codes:
            return {}
        weight = 1.0 / len(codes)
        return {code: weight for code in codes}


@pytest.fixture
def simple_strategy() -> SimpleTestStrategy:
    """Simple equal-weight strategy for testing."""
    return SimpleTestStrategy()


@pytest.fixture
def sample_equity_curve() -> pd.DataFrame:
    """Sample equity curve for metrics testing."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    values = [1_000_000.0]
    for _ in range(99):
        ret = rng.normal(0.0005, 0.015)
        values.append(values[-1] * (1 + ret))
    return pd.DataFrame({"date": dates, "total_value": values})
