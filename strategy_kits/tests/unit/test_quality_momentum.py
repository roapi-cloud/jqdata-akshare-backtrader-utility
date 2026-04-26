import pandas as pd
import numpy as np
import pytest

from strategy_kits.signals.indicator_factory import SignalRegistry
from strategy_kits.signals.indicator_factory.trend.quality_momentum import calculate_quality_momentum

def test_calculate_quality_momentum():
    close = np.linspace(100, 150, 61)  # 61天数据，稳定上涨
    # 总体收益应为 150/100 - 1 = 0.5
    # 每天的收益率是常数/逐渐变小的常数，波动率接近0
    
    val = calculate_quality_momentum(close, window=60, penalty_factor=3000.0)
    assert not np.isnan(val)
    
    # 总体收益 0.5，减去一个比较小的惩罚，应该是个正数
    assert val > 0

    # 测试数据不足
    assert np.isnan(calculate_quality_momentum(close[:50], window=60))

def test_quality_momentum_signal():
    dates = pd.date_range("2023-01-01", periods=100)
    df = pd.DataFrame({
        "000001.XSHE": np.linspace(10, 20, 100),
        "000002.XSHE": np.linspace(20, 10, 100),
    }, index=dates)

    # 从注册中心创建信号
    signal = SignalRegistry.create("quality_momentum", {"window": 60, "penalty_factor": 3000.0})
    result = signal.compute(price_df=df)
    
    assert "signal_df" in result
    sig_df = result["signal_df"]
    
    assert sig_df.shape == df.shape
    
    # 前60天应该是 NaN
    assert np.isnan(sig_df.iloc[0, 0])
    assert np.isnan(sig_df.iloc[59, 0])
    
    # 第61天（idx 60）开始有数据
    assert not np.isnan(sig_df.iloc[60, 0])
    assert not np.isnan(sig_df.iloc[60, 1])
    
    # 000001.XSHE 是一直上涨，收益率为正，波动率极低，由于平滑上涨，总收益大于风险调整项，应该是正的
    assert sig_df.iloc[-1, 0] > 0
