# -*- coding: utf-8 -*-
"""
择时模型库使用示例

展示如何使用大盘择时、个股择时、信号融合和仓位管理。
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta


# =============================================================================
# 示例 1: 基础大盘择时 - RSRS 模型
# =============================================================================
def example_rsrs_market_timing():
    """RSRS 大盘择时示例"""
    from timing_model_library.market_timing import RSRSModel

    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=800, freq="B")
    close = 100 + np.cumsum(np.random.randn(800) * 0.5)
    high = close + np.abs(np.random.randn(800) * 0.3)
    low = close - np.abs(np.random.randn(800) * 0.3)
    volume = np.random.randint(1000000, 5000000, 800)

    data = pd.DataFrame(
        {"close": close, "high": high, "low": low, "volume": volume}, index=dates
    )

    model = RSRSModel(N=18, M=600, buy_threshold=0.7, sell_threshold=-0.7)
    signal = model.compute(data)

    print("=" * 60)
    print("示例 1: RSRS 大盘择时")
    print(f"  信号方向: {signal.direction.name}")
    print(f"  信号强度: {signal.strength:.3f}")
    print(f"  置信度: {signal.confidence:.3f}")
    print(f"  原始分数: {signal.raw_score:.3f}")
    print(f"  Z-Score: {signal.metadata['zscore']:.3f}")
    print(f"  R²: {signal.metadata['r2']:.3f}")
    print()


# =============================================================================
# 示例 2: 成交量加权 RSRS
# =============================================================================
def example_volume_weighted_rsrs():
    """成交量加权 RSRS 示例"""
    from timing_model_library.market_timing import VolumeWeightedRSRS

    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=800, freq="B")
    close = 100 + np.cumsum(np.random.randn(800) * 0.5)
    high = close + np.abs(np.random.randn(800) * 0.3)
    low = close - np.abs(np.random.randn(800) * 0.3)
    volume = np.random.randint(1000000, 5000000, 800)

    data = pd.DataFrame(
        {"close": close, "high": high, "low": low, "volume": volume}, index=dates
    )

    for variant in ["right", "right_dull", "unbiased", "unbiased_dull"]:
        model = VolumeWeightedRSRS(N=18, M=200, variant=variant)
        signal = model.compute(data)
        print(
            f"  Vol-RSRS-{variant}: {signal.direction.name} (strength={signal.strength:.3f})"
        )
    print()


# =============================================================================
# 示例 3: 波动率+换手率牛熊指标
# =============================================================================
def example_vol_turnover_bull_bear():
    """波动率+换手率牛熊指标示例"""
    from timing_model_library.market_timing import VolatilityTurnoverBullBear

    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=800, freq="B")
    close = 100 + np.cumsum(np.random.randn(800) * 0.5)
    volume = np.random.randint(1000000, 5000000, 800)

    data = pd.DataFrame({"close": close, "volume": volume}, index=dates)

    model = VolatilityTurnoverBullBear()
    signal = model.compute(data)

    print("=" * 60)
    print("示例 3: 波动率+换手率牛熊指标")
    print(f"  信号方向: {signal.direction.name}")
    print(f"  市场状态: {signal.metadata['regime']}")
    print(f"  波动率 Z-Score: {signal.metadata['vol_z']:.3f}")
    print(f"  换手率 Z-Score: {signal.metadata['turnover_z']:.3f}")
    print()


# =============================================================================
# 示例 4: FED 模型
# =============================================================================
def example_fed_model():
    """FED 模型示例"""
    from timing_model_library.market_timing import FEDModel

    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=300, freq="B")
    pe_ratio = np.random.uniform(10, 25, 300)
    bond_yield = np.random.uniform(0.02, 0.04, 300)

    data = pd.DataFrame({"pe_ratio": pe_ratio, "bond_yield": bond_yield}, index=dates)

    model = FEDModel()
    signal = model.compute(data)

    print("=" * 60)
    print("示例 4: FED 模型")
    print(f"  信号方向: {signal.direction.name}")
    print(f"  格雷厄姆指数: {signal.metadata['graham_ratio']:.3f}")
    print(f"  盈利收益率: {signal.metadata['earnings_yield']:.3f}")
    print(f"  国债收益率: {signal.metadata['bond_yield']:.3f}")
    print(f"  市场状态: {signal.metadata['regime']}")
    print()


# =============================================================================
# 示例 5: 多模型信号融合
# =============================================================================
def example_signal_ensemble():
    """多模型信号融合示例"""
    from timing_model_library.market_timing import (
        RSRSModel,
        VolatilityTurnoverBullBear,
        CVIXModel,
        BOLLTimingModel,
    )
    from timing_model_library.signal_fusion import SignalEnsemble, PositionManager

    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=800, freq="B")
    close = 100 + np.cumsum(np.random.randn(800) * 0.5)
    high = close + np.abs(np.random.randn(800) * 0.3)
    low = close - np.abs(np.random.randn(800) * 0.3)
    volume = np.random.randint(1000000, 5000000, 800)

    data = pd.DataFrame(
        {"close": close, "high": high, "low": low, "volume": volume}, index=dates
    )

    models = [
        RSRSModel(N=18, M=600),
        VolatilityTurnoverBullBear(),
        CVIXModel(),
        BOLLTimingModel(),
    ]

    signals = []
    for model in models:
        try:
            signal = model.compute(data)
            signals.append(signal)
            print(
                f"  {model.name}: {signal.direction.name} (strength={signal.strength:.3f})"
            )
        except Exception as e:
            print(f"  {model.name}: 计算失败 - {e}")

    ensemble = SignalEnsemble(
        name="Market-Timing-Ensemble",
        models=models,
        method="weighted",
        weights={
            "RSRS": 1.5,
            "Vol-Turnover-BullBear": 1.0,
            "C-VIX": 0.8,
            "BOLL-Timing": 0.7,
        },
    )

    result = ensemble.fuse(signals)

    print(f"\n  综合方向: {result.composite_direction.name}")
    print(f"  综合强度: {result.composite_strength:.3f}")
    print(f"  建议仓位: {result.composite_position:.0%}")

    pm = PositionManager(method="strength")
    position = pm.compute_position(result)
    print(f"  仓位管理输出: {position:.0%}")
    print()


# =============================================================================
# 示例 6: 个股择时
# =============================================================================
def example_stock_timing():
    """个股择时示例"""
    from timing_model_library.stock_timing import TechnicalTimingModel

    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=300, freq="B")
    close = 50 + np.cumsum(np.random.randn(300) * 0.3)
    high = close + np.abs(np.random.randn(300) * 0.2)
    low = close - np.abs(np.random.randn(300) * 0.2)
    volume = np.random.randint(100000, 500000, 300)

    data = pd.DataFrame(
        {"close": close, "high": high, "low": low, "volume": volume}, index=dates
    )

    model = TechnicalTimingModel(
        indicators=["rsi", "ma", "boll"],
        rsi_period=14,
        rsi_buy=40,
        rsi_sell=70,
        ma_fast=5,
        ma_slow=20,
    )
    signal = model.compute(data)

    print("=" * 60)
    print("示例 6: 个股技术指标择时")
    print(f"  信号方向: {signal.direction.name}")
    print(f"  信号强度: {signal.strength:.3f}")
    print(f"  子信号: {signal.metadata['sub_signals']}")
    print()


# =============================================================================
# 示例 7: 完整择时流程
# =============================================================================
def example_full_pipeline():
    """完整择时流程示例"""
    from timing_model_library.market_timing import (
        RSRSModel,
        VolatilityTurnoverBullBear,
        CVIXModel,
        FEDModel,
        NorthboundModel,
        MarketBreadthModel,
    )
    from timing_model_library.stock_timing import TechnicalTimingModel
    from timing_model_library.signal_fusion import SignalEnsemble, PositionManager

    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=800, freq="B")
    close = 100 + np.cumsum(np.random.randn(800) * 0.5)
    high = close + np.abs(np.random.randn(800) * 0.3)
    low = close - np.abs(np.random.randn(800) * 0.3)
    volume = np.random.randint(1000000, 5000000, 800)

    market_data = pd.DataFrame(
        {
            "close": close,
            "high": high,
            "low": low,
            "volume": volume,
            "north_net": np.random.randn(800) * 1e9,
            "up_count": np.random.randint(1000, 3000, 800),
            "down_count": np.random.randint(1000, 3000, 800),
        },
        index=dates,
    )

    fed_data = pd.DataFrame(
        {
            "pe_ratio": np.random.uniform(10, 25, 800),
            "bond_yield": np.random.uniform(0.02, 0.04, 800),
        },
        index=dates,
    )

    print("=" * 60)
    print("示例 7: 完整择时流程")
    print("-" * 60)

    market_models = [
        RSRSModel(N=18, M=600),
        VolatilityTurnoverBullBear(),
        CVIXModel(),
        BOLLTimingModel(),
        NorthboundModel(),
    ]

    signals = []
    for model in market_models:
        try:
            signal = model.compute(market_data)
            signals.append(signal)
        except:
            pass

    fed_model = FEDModel()
    try:
        fed_signal = fed_model.compute(fed_data)
        signals.append(fed_signal)
    except:
        pass

    ensemble = SignalEnsemble(
        name="Full-Market-Timing",
        models=market_models + [fed_model],
        method="hierarchical",
    )

    result = ensemble.fuse(signals)

    pm = PositionManager(method="volatility", volatility_target=0.15)
    market_vol = market_data["close"].pct_change().std() * np.sqrt(252)
    position = pm.compute_position(result, market_vol=market_vol)

    print(f"  参与模型数: {len(signals)}")
    print(f"  综合方向: {result.composite_direction.name}")
    print(f"  综合强度: {result.composite_strength:.3f}")
    print(f"  市场波动率: {market_vol:.1%}")
    print(f"  建议仓位: {position:.0%}")
    print()


# =============================================================================
# 运行所有示例
# =============================================================================
if __name__ == "__main__":
    from timing_model_library.market_timing import BOLLTimingModel

    example_rsrs_market_timing()
    example_volume_weighted_rsrs()
    example_vol_turnover_bull_bear()
    example_fed_model()
    example_signal_ensemble()
    example_stock_timing()
    example_full_pipeline()

    print("=" * 60)
    print("所有示例运行完成!")
