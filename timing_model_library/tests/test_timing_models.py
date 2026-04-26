# -*- coding: utf-8 -*-
"""
择时模型库测试
"""

import pytest
import numpy as np
import pandas as pd
from timing_model_library.base import (
    TimingSignal,
    TimingResult,
    SignalDirection,
    TimingScope,
)
from timing_model_library.market_timing import (
    RSRSModel,
    VolumeWeightedRSRS,
    AdvancedRSRS,
    VolatilityTurnoverBullBear,
    CVIXModel,
    FEDModel,
    CongestionModel,
    MarketBreadthModel,
    DiffusionIndexModel,
    SentimentModel,
    BottomFeaturesModel,
    NorthboundModel,
    MACDTimingModel,
    BOLLTimingModel,
    TopBottomModel,
)
from timing_model_library.stock_timing import (
    TechnicalTimingModel,
    FactorTimingModel,
    StockDiffusionTimingModel,
)
from timing_model_library.signal_fusion import SignalEnsemble, PositionManager


def make_market_data(n=800):
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    volume = np.random.randint(1000000, 5000000, n)
    return pd.DataFrame(
        {"close": close, "high": high, "low": low, "volume": volume}, index=dates
    )


class TestRSRS:
    def test_basic_rsrs(self):
        data = make_market_data()
        model = RSRSModel(N=18, M=600)
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)
        assert signal.direction in SignalDirection
        assert -1.0 <= signal.strength <= 1.0

    def test_volume_weighted_rsrs(self):
        data = make_market_data()
        for variant in ["right", "right_dull", "unbiased", "unbiased_dull"]:
            model = VolumeWeightedRSRS(variant=variant)
            signal = model.compute(data)
            assert isinstance(signal, TimingSignal)

    def test_advanced_rsrs(self):
        data = make_market_data()
        model = AdvancedRSRS()
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)
        assert "rsrs_slope" in signal.metadata


class TestVolatilityTurnover:
    def test_bull_bear(self):
        data = make_market_data()
        model = VolatilityTurnoverBullBear()
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)
        assert "regime" in signal.metadata


class TestCVIX:
    def test_cvix(self):
        data = make_market_data()
        model = CVIXModel()
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)
        assert "regime" in signal.metadata


class TestFED:
    def test_fed_model(self):
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=300, freq="B")
        data = pd.DataFrame(
            {
                "pe_ratio": np.random.uniform(10, 25, 300),
                "bond_yield": np.random.uniform(0.02, 0.04, 300),
            },
            index=dates,
        )
        model = FEDModel()
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)
        assert "graham_ratio" in signal.metadata


class TestCongestion:
    def test_congestion(self):
        data = make_market_data()
        data["amount"] = data["close"] * data["volume"]
        model = CongestionModel()
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)


class TestMarketBreadth:
    def test_breadth(self):
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=300, freq="B")
        data = pd.DataFrame(
            {
                "up_count": np.random.randint(1000, 3000, 300),
                "down_count": np.random.randint(1000, 3000, 300),
            },
            index=dates,
        )
        model = MarketBreadthModel()
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)

    def test_diffusion_index(self):
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=300, freq="B")
        data = pd.DataFrame(
            {
                "A": 100 + np.cumsum(np.random.randn(300) * 0.5),
                "B": 50 + np.cumsum(np.random.randn(300) * 0.3),
                "C": 200 + np.cumsum(np.random.randn(300) * 0.4),
            },
            index=dates,
        )
        model = DiffusionIndexModel(roc_period=20, ma_fast=10, ma_slow=5)
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)


class TestSentiment:
    def test_sentiment(self):
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=300, freq="B")
        data = pd.DataFrame(
            {
                "limit_up": np.random.randint(20, 100, 300),
                "limit_down": np.random.randint(0, 30, 300),
                "turnover_rate": np.random.uniform(0.01, 0.05, 300),
            },
            index=dates,
        )
        model = SentimentModel()
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)


class TestBottomFeatures:
    def test_bottom(self):
        data = make_market_data()
        model = BottomFeaturesModel()
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)
        assert "signal_count" in signal.metadata


class TestNorthbound:
    def test_northbound(self):
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=300, freq="B")
        data = pd.DataFrame(
            {
                "north_net": np.random.randn(300) * 1e9,
            },
            index=dates,
        )
        model = NorthboundModel()
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)


class TestMACD:
    def test_macd_daily(self):
        data = make_market_data()
        model = MACDTimingModel(variant="daily")
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)

    def test_macd_fast(self):
        data = make_market_data()
        model = MACDTimingModel(variant="fast")
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)


class TestBOLL:
    def test_boll(self):
        data = make_market_data()
        model = BOLLTimingModel()
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)
        assert "position_in_band" in signal.metadata


class TestTopBottom:
    def test_top_bottom(self):
        data = make_market_data()
        model = TopBottomModel()
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)
        assert "position_pct" in signal.metadata


class TestStockTiming:
    def test_technical(self):
        data = make_market_data(300)
        model = TechnicalTimingModel(indicators=["rsi", "ma", "boll"])
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)

    def test_stock_diffusion(self):
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=300, freq="B")
        data = pd.DataFrame(
            {
                "A": 100 + np.cumsum(np.random.randn(300) * 0.5),
                "B": 50 + np.cumsum(np.random.randn(300) * 0.3),
            },
            index=dates,
        )
        model = StockDiffusionTimingModel()
        signal = model.compute(data)
        assert isinstance(signal, TimingSignal)


class TestEnsemble:
    def test_weighted_fusion(self):
        data = make_market_data()
        models = [
            RSRSModel(N=18, M=600),
            BOLLTimingModel(),
        ]
        signals = [m.compute(data) for m in models]
        ensemble = SignalEnsemble(models=models, method="weighted")
        result = ensemble.fuse(signals)
        assert isinstance(result, TimingResult)
        assert 0.0 <= result.composite_position <= 1.0

    def test_vote_fusion(self):
        data = make_market_data()
        models = [
            RSRSModel(N=18, M=600),
            BOLLTimingModel(),
            CVIXModel(),
        ]
        signals = [m.compute(data) for m in models]
        ensemble = SignalEnsemble(models=models, method="vote")
        result = ensemble.fuse(signals)
        assert isinstance(result, TimingResult)


class TestPositionManager:
    def test_strength_position(self):
        pm = PositionManager(method="strength")
        result = TimingResult(
            signals=[],
            composite_direction=SignalDirection.BUY,
            composite_strength=0.5,
            composite_position=0.75,
            timestamp=pd.Timestamp.now(),
        )
        pos = pm.compute_position(result)
        assert 0.0 <= pos <= 1.0

    def test_fixed_position(self):
        pm = PositionManager(method="fixed")
        result = TimingResult(
            signals=[],
            composite_direction=SignalDirection.SELL,
            composite_strength=-0.5,
            composite_position=0.0,
            timestamp=pd.Timestamp.now(),
        )
        pos = pm.compute_position(result)
        assert pos == 0.0
