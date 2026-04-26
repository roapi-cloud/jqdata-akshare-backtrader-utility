# RSRS择时机制 (Resistance Support Relative Strength)

## 概述

RSRS是利用最高价/最低价的线性回归斜率判断市场阻力支撑强度的技术指标，是策略库中使用最广泛的择时指标。

## 机制说明

1. **计算N日最高价与最低价的线性回归斜率**
2. **斜率越大，说明支撑越强，市场偏多**
3. **对斜率序列计算标准分(zscore)**
4. **结合拟合度R²进行右偏修正**

## 效果验证

| 策略 | 年化收益 | 最大回撤 | 改善 |
|------|---------|---------|------|
| ETF动量轮动RSRS择时 | 80-150% | 10-15% | 显著 |
| PEG+成长+小市值+RSRS | 50%+ | 可控 | 有效 |
| RSRS择时改进系列 | 40-100% | 15-20% | 稳定 |

## 代码样例

```python
# rsrs_impl.py
import numpy as np
import pandas as pd
from scipy.stats import linregress

class RSRSIndicator:
    """RSRS择时指标"""
    
    def __init__(self, N=18, M=600):
        self.N = N  # 计算斜率的窗口
        self.M = M  # 计算标准分的序列长度
        self.slope_series = []
    
    def calculate_beta_r2(self, prices):
        """计算斜率和拟合度"""
        high = prices['high'].values
        low = prices['low'].values
        
        if len(high) < self.N:
            return None, None
        
        # 取最近N天数据
        high = high[-self.N:]
        low = low[-self.N:]
        
        # 线性回归: high = alpha + beta * low
        slope, intercept, r_value, p_value, std_err = linregress(low, high)
        
        return slope, r_value ** 2
    
    def calculate_rsrs(self, context, security='000300.XSHG'):
        """计算RSRS指标"""
        # 获取数据
        prices = get_price(security, 
                          end_date=context.previous_date, 
                          fields=['high', 'low'], 
                          count=self.N, 
                          panel=False)
        
        # 计算当前斜率和R²
        beta, r2 = self.calculate_beta_r2(prices)
        
        if beta is None:
            return None
        
        # 更新斜率序列
        self.slope_series.append(beta)
        if len(self.slope_series) > self.M:
            self.slope_series.pop(0)
        
        # 计算标准分
        if len(self.slope_series) < 50:  # 需要足够数据
            return None
        
        mean = np.mean(self.slope_series)
        std = np.std(self.slope_series)
        zscore = (beta - mean) / std
        
        # 右偏修正: zscore * beta * r2
        rsrs_rightdev = zscore * beta * r2
        
        return rsrs_rightdev
    
    def get_signal(self, context, security='000300.XSHG', 
                   buy_threshold=0.7, sell_threshold=-0.7):
        """获取交易信号"""
        rsrs_value = self.calculate_rsrs(context, security)
        
        if rsrs_value is None:
            return 'HOLD'
        
        if rsrs_value > buy_threshold:
            return 'BUY'
        elif rsrs_value < sell_threshold:
            return 'SELL'
        return 'HOLD'


# 使用示例
def initialize(context):
    context.rsrs = RSRSIndicator(N=18, M=600)
    run_daily(handle_data, time='09:35')

def handle_data(context):
    signal = context.rsrs.get_signal(context, '000300.XSHG')
    
    if signal == 'SELL':
        # 清仓
        for stock in context.portfolio.positions:
            order_target_value(stock, 0)
    elif signal == 'BUY':
        # 买入ETF
        if '510310.XSHG' not in context.portfolio.positions:
            order_target_percent('510310.XSHG', 0.95)
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| N | 18 | 计算斜率的窗口天数 |
| M | 600 | 计算标准分的序列长度 |
| buy_threshold | 0.7 | 买入阈值 |
| sell_threshold | -0.7 | 卖出阈值 |

## 适用策略

- ✅ ETF动量轮动（几乎所有轮动策略）
- ✅ 小市值+择时
- ✅ 基本面+择时组合
- ⚠️ 短线策略（可能过于滞后）

## 优化方向

1. **成交量加权RSRS**：用成交量加权高低点
2. **右偏RSRS**：利用拟合度R²进行右偏修正
3. **钝化RSRS**：在极端值区域避免频繁信号
4. **多周期RSRS**：结合日线、周线信号

## 注意事项

1. 需要足够的历史数据初始化（M足够大）
2. 在震荡市中可能产生频繁开关信号
3. 建议结合MA等其他指标使用
