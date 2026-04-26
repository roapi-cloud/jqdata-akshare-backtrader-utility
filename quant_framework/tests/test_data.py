"""Tests for the data layer: source, cache, and validator."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from quant_framework.core.data.cache import DataCache
from quant_framework.core.data.validator import DataValidator
from quant_framework.core.data.source import AkShareDataSource


class TestAkShareDataSource:
    """Tests for AkShareDataSource with mocked API calls."""

    def test_get_daily_bars_mocked(self):
        """Test fetching daily bars with mocked akshare."""
        mock_df = pd.DataFrame(
            {
                "日期": ["2024-01-02", "2024-01-03", "2024-01-04"],
                "开盘": [10.0, 10.2, 10.1],
                "最高": [10.5, 10.6, 10.4],
                "最低": [9.8, 10.0, 9.9],
                "收盘": [10.3, 10.1, 10.2],
                "成交量": [1_000_000, 1_200_000, 900_000],
                "成交额": [10_300_000, 12_120_000, 9_180_000],
            }
        )

        with patch("akshare.stock_zh_a_hist", return_value=mock_df) as mock_api:
            ds = AkShareDataSource()
            result = ds.get_daily_bars(
                symbol="000001",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
            )

            mock_api.assert_called_once()
            assert "open" in result.columns
            assert "close" in result.columns
            assert "volume" in result.columns
            assert result["code"].iloc[0] == "000001"
            assert len(result) == 3

    def test_get_daily_bars_caches_result(self):
        """Test that results are cached internally."""
        mock_df = pd.DataFrame(
            {
                "日期": ["2024-01-02"],
                "开盘": [10.0],
                "最高": [10.5],
                "最低": [9.8],
                "收盘": [10.3],
                "成交量": [1_000_000],
                "成交额": [10_300_000],
            }
        )

        with patch("akshare.stock_zh_a_hist", return_value=mock_df) as mock_api:
            ds = AkShareDataSource()
            ds.get_daily_bars("000001", date(2024, 1, 1), date(2024, 1, 31))
            ds.get_daily_bars("000001", date(2024, 1, 1), date(2024, 1, 31))

            assert mock_api.call_count == 1

    def test_get_daily_bars_column_renaming(self):
        """Test that Chinese column names are properly renamed."""
        mock_df = pd.DataFrame(
            {
                "日期": ["2024-01-02"],
                "开盘": [10.0],
                "最高": [10.5],
                "最低": [9.8],
                "收盘": [10.3],
                "成交量": [1_000_000],
                "成交额": [10_300_000],
            }
        )

        with patch("akshare.stock_zh_a_hist", return_value=mock_df):
            ds = AkShareDataSource()
            result = ds.get_daily_bars("000001", date(2024, 1, 1), date(2024, 1, 31))

            expected_cols = {"open", "high", "low", "close", "volume", "amount", "code"}
            assert expected_cols.issubset(set(result.columns))

    def test_get_symbol_list_mocked(self):
        """Test symbol list retrieval with mocked API."""
        mock_df = pd.DataFrame({"代码": ["000001", "000002", "600000"]})

        with patch("akshare.stock_zh_a_spot_em", return_value=mock_df):
            ds = AkShareDataSource()
            symbols = ds.get_symbol_list()
            assert "000001" in symbols
            assert len(symbols) == 3


class TestDataCache:
    """Tests for the data caching layer."""

    def test_put_and_get(self, tmp_path):
        """Test storing and retrieving cached data."""
        cache = DataCache(cache_dir=str(tmp_path), ttl_seconds=86400, format="pickle")
        df = pd.DataFrame({"close": [10.0, 11.0, 12.0]})
        key = cache._make_key("000001", date(2024, 1, 1), date(2024, 1, 31))

        cache.put(key, df)
        result = cache.get(key)

        assert result is not None
        pd.testing.assert_frame_equal(result, df)

    def test_cache_miss_returns_none(self, tmp_path):
        """Test that missing cache entries return None."""
        cache = DataCache(cache_dir=str(tmp_path))
        result = cache.get("nonexistent_key_12345")
        assert result is None

    def test_clear_removes_all(self, tmp_path):
        """Test that clear removes all cached data."""
        cache = DataCache(cache_dir=str(tmp_path), format="pickle")
        df = pd.DataFrame({"close": [10.0]})
        key = cache._make_key("000001")
        cache.put(key, df)
        cache.clear()

        assert cache.get(key) is None

    def test_memory_cache(self, tmp_path):
        """Test in-memory cache layer."""
        cache = DataCache(cache_dir=str(tmp_path), ttl_seconds=86400, format="pickle")
        df = pd.DataFrame({"close": [10.0]})
        key = cache._make_key("000001")
        cache.put(key, df)

        assert key in cache._memory_cache

    def test_get_or_compute(self, tmp_path):
        """Test get_or_compute convenience method."""
        cache = DataCache(cache_dir=str(tmp_path), format="pickle")

        def compute():
            return pd.DataFrame({"val": [1, 2, 3]})

        result = cache.get_or_compute(compute)
        assert result is not None
        assert len(result) == 3

    def test_cache_size(self, tmp_path):
        """Test cache size reporting."""
        cache = DataCache(cache_dir=str(tmp_path), format="pickle")
        assert cache.size() == 0
        key = cache._make_key("test")
        cache.put(key, pd.DataFrame({"a": [1]}))
        assert cache.size() == 1


class TestDataValidator:
    """Tests for data validation."""

    @pytest.fixture
    def valid_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "open": [10.0, 10.2, 10.1],
                "high": [10.5, 10.6, 10.4],
                "low": [9.8, 10.0, 9.9],
                "close": [10.3, 10.1, 10.2],
                "volume": [1_000_000, 1_200_000, 900_000],
            }
        )

    def test_has_required_columns_true(self, valid_df):
        assert DataValidator.has_required_columns(valid_df)

    def test_has_required_columns_false(self):
        df = pd.DataFrame({"open": [10.0], "close": [10.3]})
        assert not DataValidator.has_required_columns(df)

    def test_has_no_nulls_true(self, valid_df):
        assert DataValidator.has_no_nulls(valid_df)

    def test_has_no_nulls_false(self):
        df = pd.DataFrame(
            {
                "open": [10.0, None],
                "high": [10.5, 10.6],
                "low": [9.8, 10.0],
                "close": [10.3, 10.1],
                "volume": [1_000_000, 1_200_000],
            }
        )
        assert not DataValidator.has_no_nulls(df)

    def test_price_positive_true(self, valid_df):
        assert DataValidator.price_positive(valid_df)

    def test_price_positive_false(self):
        df = pd.DataFrame(
            {
                "open": [-1.0],
                "high": [10.5],
                "low": [9.8],
                "close": [10.3],
                "volume": [1_000_000],
            }
        )
        assert not DataValidator.price_positive(df)

    def test_volume_non_negative_true(self, valid_df):
        assert DataValidator.volume_non_negative(valid_df)

    def test_volume_non_negative_false(self):
        df = pd.DataFrame(
            {
                "open": [10.0],
                "high": [10.5],
                "low": [9.8],
                "close": [10.3],
                "volume": [-100],
            }
        )
        assert not DataValidator.volume_non_negative(df)

    def test_high_low_consistent_true(self, valid_df):
        assert DataValidator.high_low_consistent(valid_df)

    def test_high_low_consistent_false(self):
        df = pd.DataFrame(
            {
                "open": [10.0],
                "high": [9.0],
                "low": [10.0],
                "close": [10.3],
                "volume": [1_000_000],
            }
        )
        assert not DataValidator.high_low_consistent(df)

    def test_validate_returns_errors(self):
        df = pd.DataFrame(
            {
                "open": [10.0],
                "high": [10.5],
                "low": [9.8],
                "close": [10.3],
                "volume": [-100],
            }
        )
        errors = DataValidator.validate(df)
        assert len(errors) > 0

    def test_validate_returns_empty_for_valid(self, valid_df):
        errors = DataValidator.validate(valid_df)
        assert errors == []
