"""
Tests for Market Diagnostic System - jq_workbench

Tests core functionality:
- Data models
- Cache with TTL
- Feature calculations
"""

import sys
import time
import unittest
from dataclasses import asdict

# Add parent directory to path for imports
sys.path.insert(0, '/Users/yuping/Downloads/git/jqdata_akshare_backtrader_utility/jq_workbench')

from diag_platform.market_diagnostic.data.models import (
    IndexDailyData,
    MarketBreadthData,
    SectorDailyData,
    CapitalFlowData,
)
from diag_platform.market_diagnostic.data.cache import DiagnosticDataCache
from diag_platform.market_diagnostic.features.trend import TrendFeatures, compute_trend_features, _ema, _sma, _compute_macd
from diag_platform.market_diagnostic.features.breadth import BreadthFeatures, compute_breadth_features
from diag_platform.market_diagnostic.features.sentiment import SentimentFeatures, compute_sentiment_features
from diag_platform.market_diagnostic.features.style import StyleFeatures, compute_style_features
from diag_platform.market_diagnostic.features.sector import (
    SectorFeatureResult,
    compute_sector_features,
    compute_all_sector_features,
    _compute_z_score,
)


class TestDataModels(unittest.TestCase):
    """Test data models."""

    def test_index_daily_data(self):
        """Test IndexDailyData creation and serialization."""
        data = IndexDailyData(
            code="sh000001",
            name="上证指数",
            date="2024-01-15",
            close=3150.5,
            open=3140.0,
            high=3160.0,
            low=3130.0,
            prev_close=3145.0,
            volume=3000000000,
            amount=350000000000,
            change_pct=0.17,
            close_series=[3100 + i for i in range(60)],
            volume_series=[3000000000 + i * 1000000 for i in range(60)],
        )

        self.assertEqual(data.code, "sh000001")
        self.assertEqual(data.close, 3150.5)
        self.assertEqual(len(data.close_series), 60)

        # Test serialization
        d = data.to_dict()
        self.assertEqual(d["code"], "sh000001")
        self.assertEqual(d["close"], 3150.5)

    def test_market_breadth_data(self):
        """Test MarketBreadthData creation."""
        data = MarketBreadthData(
            date="2024-01-15",
            up_count=2500,
            down_count=2000,
            flat_count=500,
            limit_up_count=50,
            limit_down_count=20,
            explode_count=5,
            seal_rate=0.91,
            continuous_limit_up=10,
            above_ma20_ratio=0.55,
            above_ma60_ratio=0.40,
            new_high_count=100,
            new_low_count=50,
            total_amount=8000.0,
            amount_ma5=7500.0,
            amount_ma20=7000.0,
        )

        self.assertEqual(data.up_count, 2500)
        self.assertAlmostEqual(data.seal_rate, 0.91)

    def test_sector_daily_data(self):
        """Test SectorDailyData creation."""
        data = SectorDailyData(
            date="2024-01-15",
            industry_code="BK0447",
            industry_name="电子",
            ret_1d=1.5,
            ret_5d=3.2,
            ret_20d=-2.1,
            excess_ret_1d=0.8,
            breadth_20=0.60,
            new_high_ratio=0.10,
            amount=500.0,
            amount_share=0.0625,
            amount_share_delta=0.005,
            limit_up_count=5,
            turnover=2.5,
        )

        self.assertEqual(data.industry_name, "电子")
        self.assertAlmostEqual(data.ret_1d, 1.5)


class TestCache(unittest.TestCase):
    """Test cache functionality with TTL."""

    def test_cache_set_get(self):
        """Test basic cache set and get."""
        cache = DiagnosticDataCache(ttl=1200)

        cache.set("test_key", "2024-01-15", {"data": "value"})
        result = cache.get("test_key", "2024-01-15")

        self.assertIsNotNone(result)
        self.assertEqual(result["data"], "value")

    def test_cache_expiry(self):
        """Test cache expiration after TTL."""
        cache = DiagnosticDataCache(ttl=1)  # 1 second TTL

        cache.set("test_key", "2024-01-15", {"data": "value"})

        # Should be available immediately
        result = cache.get("test_key", "2024-01-15")
        self.assertIsNotNone(result)

        # Wait for expiration
        time.sleep(2)

        result = cache.get("test_key", "2024-01-15")
        self.assertIsNone(result)

    def test_cache_clear(self):
        """Test cache clear."""
        cache = DiagnosticDataCache()

        cache.set("key1", "2024-01-15", "value1")
        cache.set("key2", "2024-01-15", "value2")

        self.assertEqual(cache.clear_all(), 2)
        self.assertIsNone(cache.get("key1", "2024-01-15"))

    def test_cache_stats(self):
        """Test cache statistics."""
        cache = DiagnosticDataCache()

        cache.set("key1", "2024-01-15", "value1")
        cache.set("key2", "2024-01-15", "value2")

        stats = cache.get_stats()
        self.assertEqual(stats["total_entries"], 2)
        self.assertEqual(stats["active_entries"], 2)


class TestTrendFeatures(unittest.TestCase):
    """Test trend feature calculations."""

    def test_ema(self):
        """Test EMA calculation."""
        data = [10.0, 11.0, 12.0, 13.0, 14.0]
        result = _ema(data, 3)
        self.assertAlmostEqual(result[-1], 13.5, places=1)

    def test_sma(self):
        """Test SMA calculation."""
        data = [10.0, 11.0, 12.0, 13.0, 14.0]
        result = _sma(data, 5)
        self.assertEqual(result, 12.0)

        result_short = _sma(data, 10)  # Not enough data
        self.assertTrue(result_short != result)

    def test_macd(self):
        """Test MACD calculation."""
        # Create 60 days of data with an uptrend
        data = [100 + i * 0.5 for i in range(60)]
        dif, dea, bar, signal = _compute_macd(data)

        self.assertIsInstance(dif, float)
        self.assertIsInstance(dea, float)
        self.assertIsInstance(bar, float)
        self.assertIn(signal, ["金叉", "死叉", "中性"])

    def test_compute_trend_features(self):
        """Test full trend feature computation."""
        index_data = IndexDailyData(
            code="sh000001",
            name="上证指数",
            date="2024-01-15",
            close=3150.0,
            open=3140.0,
            high=3160.0,
            low=3130.0,
            prev_close=3145.0,
            volume=3000000000,
            amount=350000000000,
            change_pct=0.17,
            close_series=[3100 + i * 0.5 for i in range(60)],
        )

        features = compute_trend_features(index_data)

        self.assertEqual(features.code, "sh000001")
        self.assertIsInstance(features.ma5, float)
        self.assertIsInstance(features.ma20, float)
        self.assertIn(features.ma_alignment, ["多头排列", "空头排列", "缠绕"])
        self.assertIn(features.macd_signal, ["金叉", "死叉", "中性"])


class TestBreadthFeatures(unittest.TestCase):
    """Test breadth feature calculations."""

    def test_compute_breadth_features(self):
        """Test breadth feature computation."""
        data = MarketBreadthData(
            date="2024-01-15",
            up_count=2500,
            down_count=2000,
            flat_count=500,
            limit_up_count=50,
            limit_down_count=20,
            explode_count=5,
            seal_rate=0.91,
            continuous_limit_up=10,
            above_ma20_ratio=0.55,
            above_ma60_ratio=0.40,
            new_high_count=100,
            new_low_count=50,
            total_amount=8000.0,
            amount_ma5=7500.0,
            amount_ma20=7000.0,
        )

        features = compute_breadth_features(data)

        self.assertIsInstance(features.up_down_ratio, float)
        self.assertIsInstance(features.limit_up_rate, float)
        self.assertAlmostEqual(features.seal_rate, 0.91)
        self.assertGreaterEqual(features.breadth_score, 0)
        self.assertLessEqual(features.breadth_score, 100)


class TestSentimentFeatures(unittest.TestCase):
    """Test sentiment feature calculations."""

    def test_compute_sentiment_features(self):
        """Test sentiment feature computation."""
        data = MarketBreadthData(
            date="2024-01-15",
            up_count=2500,
            down_count=2000,
            flat_count=500,
            limit_up_count=50,
            limit_down_count=20,
            explode_count=5,
            seal_rate=0.91,
            continuous_limit_up=10,
            above_ma20_ratio=0.55,
            above_ma60_ratio=0.40,
            new_high_count=100,
            new_low_count=50,
            total_amount=8000.0,
            amount_ma5=7500.0,
            amount_ma20=7000.0,
        )

        features = compute_sentiment_features(data)

        self.assertIsInstance(features.limit_up_down_ratio, float)
        self.assertEqual(features.continuous_limit_up, 10)
        self.assertGreaterEqual(features.sentiment_score, 0)
        self.assertLessEqual(features.sentiment_score, 100)


class TestStyleFeatures(unittest.TestCase):
    """Test style feature calculations."""

    def test_compute_style_features(self):
        """Test style feature computation."""
        index_data = {
            "sh000016": IndexDailyData(
                code="sh000016", name="上证50", date="2024-01-15",
                close=2500.0, open=2490.0, high=2510.0, low=2480.0,
                prev_close=2480.0, volume=1000000000, amount=200000000000,
                change_pct=0.4,
                close_series=[2450 + i * 2 for i in range(30)],
            ),
            "sz399006": IndexDailyData(
                code="sz399006", name="创业板指", date="2024-01-15",
                close=1800.0, open=1780.0, high=1810.0, low=1770.0,
                prev_close=1770.0, volume=800000000, amount=150000000000,
                change_pct=1.0,
                close_series=[1700 + i * 3 for i in range(30)],
            ),
            "sh000300": IndexDailyData(
                code="sh000300", name="沪深300", date="2024-01-15",
                close=3800.0, open=3780.0, high=3810.0, low=3770.0,
                prev_close=3770.0, volume=1200000000, amount=250000000000,
                change_pct=0.5,
                close_series=[3700 + i * 3 for i in range(30)],
            ),
            "sh000852": IndexDailyData(
                code="sh000852", name="中证1000", date="2024-01-15",
                close=5500.0, open=5450.0, high=5520.0, low=5430.0,
                prev_close=5430.0, volume=900000000, amount=180000000000,
                change_pct=0.8,
                close_series=[5300 + i * 6 for i in range(30)],
            ),
            "sh000905": IndexDailyData(
                code="sh000905", name="中证500", date="2024-01-15",
                close=4800.0, open=4770.0, high=4820.0, low=4760.0,
                prev_close=4760.0, volume=700000000, amount=140000000000,
                change_pct=0.6,
                close_series=[4650 + i * 5 for i in range(30)],
            ),
        }

        features = compute_style_features(index_data)

        self.assertIsInstance(features.rs_large_vs_small, float)
        self.assertIsInstance(features.rs_300_vs_1000, float)
        self.assertIn(features.dominant_style, ["大盘防守", "小盘进攻", "成长主导", "红利防守", "风格冲突"])


class TestSectorFeatures(unittest.TestCase):
    """Test sector feature calculations."""

    def test_z_score(self):
        """Test Z-score calculation."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        z = _compute_z_score(3.0, values)
        self.assertAlmostEqual(z, 0.0, places=5)

        z_high = _compute_z_score(5.0, values)
        self.assertGreater(z_high, 0)

    def test_compute_sector_features(self):
        """Test sector feature computation."""
        sectors = [
            SectorDailyData(
                date="2024-01-15",
                industry_code="BK0447",
                industry_name="电子",
                ret_1d=1.5,
                ret_5d=3.2,
                ret_20d=-2.1,
                excess_ret_1d=0.8,
                breadth_20=0.60,
                new_high_ratio=0.10,
                amount=500.0,
                amount_share=0.0625,
                amount_share_delta=0.005,
                limit_up_count=5,
                turnover=2.5,
            ),
            SectorDailyData(
                date="2024-01-15",
                industry_code="BK0448",
                industry_name="计算机",
                ret_1d=2.0,
                ret_5d=5.0,
                ret_20d=3.0,
                excess_ret_1d=1.3,
                breadth_20=0.70,
                new_high_ratio=0.15,
                amount=600.0,
                amount_share=0.075,
                amount_share_delta=0.010,
                limit_up_count=8,
                turnover=3.0,
            ),
        ]

        result = compute_sector_features(sectors[0], sectors)

        self.assertEqual(result.industry_code, "BK0447")
        self.assertIsInstance(result.strength_score, float)
        self.assertIsInstance(result.persistence_score, float)
        self.assertIn(result.state, ["主升趋势", "趋势强化", "震荡整理", "超跌反弹", "弱势退潮"])

    def test_compute_all_sector_features(self):
        """Test parallel sector feature computation."""
        sectors = [
            SectorDailyData(
                date="2024-01-15",
                industry_code=f"BK044{i}",
                industry_name=f"行业{i}",
                ret_1d=1.0 + i * 0.1,
                ret_5d=2.0 + i * 0.2,
                ret_20d=-1.0 + i * 0.3,
                excess_ret_1d=0.5,
                breadth_20=0.5,
                new_high_ratio=0.1,
                amount=100.0 + i * 10,
                amount_share=0.05 + i * 0.01,
                amount_share_delta=0.005,
                limit_up_count=i,
                turnover=2.0,
            )
            for i in range(10)
        ]

        results = compute_all_sector_features(sectors)

        self.assertEqual(len(results), 10)
        for r in results:
            self.assertIsInstance(r.strength_score, float)


if __name__ == "__main__":
    print("Running Market Diagnostic System Tests...")
    print("=" * 60)

    # Run tests
    unittest.main(verbosity=2)
