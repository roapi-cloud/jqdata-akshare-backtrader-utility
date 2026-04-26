import pandas as pd
import numpy as np
import pytest

from strategy_kits.signals.indicator_factory import SignalRegistry
from strategy_kits.signals.indicator_factory.flow.overnight_ratio import OvernightRatioSignal

def test_overnight_ratio_signal():
    dates = pd.date_range("2023-01-01", periods=30)
    
    # 模拟数据
    # A股：隔夜收益一直是正的，日内也是正的，隔夜比例较高
    # B股：隔夜收益为0，日内随便波动，隔夜比例等于0
    
    c_A = np.zeros(30)
    o_A = np.zeros(30)
    c_B = np.zeros(30)
    o_B = np.zeros(30)
    
    close_prev_A = 100
    close_prev_B = 100
    
    for i in range(30):
        # A: overnight +1%, intraday +0.5%
        o_A[i] = close_prev_A * 1.01
        c_A[i] = o_A[i] * 1.005
        close_prev_A = c_A[i]
        
        # B: overnight 0%, intraday -1% or +1%
        o_B[i] = close_prev_B
        c_B[i] = o_B[i] * 0.99
        close_prev_B = c_B[i]
        
    price_df = pd.DataFrame({
        "A": c_A,
        "B": c_B,
    }, index=dates)
    
    open_df = pd.DataFrame({
        "A": o_A,
        "B": o_B,
    }, index=dates)

    signal = SignalRegistry.create("overnight_ratio", {"window": 10})
    
    # kwargs.get 实际上是在方法签名里的 **kwargs 取得
    # 实际上由于 BaseSignal 的 _compute_impl 接收 **kwargs，我们在 config.compute时得传对。
    # 修改：直接传 open_df=open_df 进去
    result = signal.compute(price_df=price_df, open_df=open_df)

    assert "signal_df" in result
    sig_df = result["signal_df"]
    
    assert sig_df.shape == price_df.shape
    
    # 前 5 天由于 min_periods=5（window=10），会有 NaN，第5天才有值
    assert np.isnan(sig_df.iloc[0, 0])
    
    # 验证后半段的值
    # A 的 overnight=0.01, intraday=0.005
    # overnight_abs = 0.01, total_abs = 0.015, ratio = 0.666...
    # overnight > 0 = 1.0
    # 所以 A 最终的 factor 值应接近 0.666
    assert abs(sig_df.iloc[-1, 0] - (0.01 / 0.015)) < 1e-4
    
    # B 的 overnight=0.0
    # ratio=0, direction=0
    # 所以 B 应该等于0
    assert abs(sig_df.iloc[-1, 1]) < 1e-4

def test_overnight_ratio_missing_open():
    dates = pd.date_range("2023-01-01", periods=10)
    price_df = pd.DataFrame({"A": np.ones(10)}, index=dates)
    
    signal = SignalRegistry.create("overnight_ratio", {"window": 10})
    with pytest.raises(ValueError, match="open_df is required"):
        signal.compute(price_df=price_df)
