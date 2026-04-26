# 多周期共振过滤 (Multi-Timeframe Confirmation)

## 概述

结合多个时间周期（如日线+周线）的信号，提高买入胜率。适用于中线趋势策略。

## 机制说明

1. **获取日线、周线数据**
2. **计算各周期指标（如MACD、RSI）**
3. **多周期方向一致时信号更强**
4. **共振分数决定仓位**

## 代码样例

```python
# multi_timeframe.py
import numpy as np
import pandas as pd
import talib

class MultiTimeframeIndicator:
    """多周期指标计算"""
    
    def __init__(self):
        pass
    
    def get_daily_data(self, stock, end_date, count):
        """获取日线数据"""
        df = get_price(stock, 
                      end_date=end_date, 
                      fields=['close', 'high', 'low'], 
                      count=count, 
                      panel=False)
        return df
    
    def get_weekly_data(self, stock, end_date, count):
        """获取周线数据"""
        df = get_price(stock, 
                      end_date=end_date, 
                      frequency='1w',
                      fields=['close', 'high', 'low'], 
                      count=count, 
                      panel=False)
        return df
    
    def calculate_rsi(self, close, period=14):
        """计算RSI"""
        return talib.RSI(close, timeperiod=period)
    
    def calculate_macd(self, close, fast=12, slow=26, signal=9):
        """计算MACD"""
        dif, dea, macd = talib.MACDEXT(close, 
                                        fastperiod=fast, 
                                        fastmatype=1,
                                        slowperiod=slow, 
                                        slowmatype=1,
                                        signalperiod=signal, 
                                        signalmatype=1)
        return dif, dea, macd
    
    def calculate_ma_direction(self, close, period=20):
        """计算均线方向"""
        ma = talib.MA(close, timeperiod=period)
        if len(ma) < 2:
            return 0
        return 1 if ma[-1] > ma[-2] else -1
    
    def get_daily_signal(self, stock, end_date):
        """获取日线信号"""
        df = self.get_daily_data(stock, end_date, 50)
        if df is None or len(df) < 30:
            return None
        
        close = df['close'].values
        
        # RSI
        rsi = self.calculate_rsi(close, 14)
        rsi_signal = 'BUY' if rsi[-1] > 50 else 'SELL'
        
        # MACD
        dif, dea, macd = self.calculate_macd(close)
        macd_signal = 'BUY' if dif[-1] > dea[-1] and macd[-1] > 0 else 'SELL'
        
        # MA方向
        ma_direction = self.calculate_ma_direction(close, 20)
        
        return {
            'rsi': rsi[-1],
            'rsi_signal': rsi_signal,
            'macd_signal': macd_signal,
            'macd_diff': dif[-1] - dea[-1],
            'ma_direction': ma_direction
        }
    
    def get_weekly_signal(self, stock, end_date):
        """获取周线信号"""
        df = self.get_weekly_data(stock, end_date, 30)
        if df is None or len(df) < 10:
            return None
        
        close = df['close'].values
        
        # RSI
        rsi = self.calculate_rsi(close, 14)
        rsi_signal = 'BUY' if rsi[-1] > 50 else 'SELL'
        
        # MACD
        dif, dea, macd = self.calculate_macd(close)
        macd_signal = 'BUY' if dif[-1] > dea[-1] and macd[-1] > 0 else 'SELL'
        
        # MA方向
        ma_direction = self.calculate_ma_direction(close, 20)
        
        return {
            'rsi': rsi[-1],
            'rsi_signal': rsi_signal,
            'macd_signal': macd_signal,
            'macd_diff': dif[-1] - dea[-1],
            'ma_direction': ma_direction
        }
    
    def get_combined_signal(self, stock, end_date, min_resonance=2):
        """
        获取综合信号
        min_resonance: 最少共振数
        """
        daily = self.get_daily_signal(stock, end_date)
        weekly = self.get_weekly_signal(stock, end_date)
        
        if daily is None or weekly is None:
            return None, 0
        
        # 共振计数
        resonance_score = 0
        
        # RSI共振
        if daily['rsi_signal'] == weekly['rsi_signal']:
            resonance_score += 1
        
        # MACD共振
        if daily['macd_signal'] == weekly['macd_signal']:
            resonance_score += 1
        
        # 均线共振
        if daily['ma_direction'] == weekly['ma_direction']:
            resonance_score += 1
        
        # 综合判断
        if resonance_score >= min_resonance:
            if daily['rsi_signal'] == 'BUY':
                return 'BUY', resonance_score
            else:
                return 'SELL', resonance_score
        
        return 'HOLD', resonance_score


# 使用示例
def initialize(context):
    context.mtf = MultiTimeframeIndicator()

def handle_data(context):
    # 候选股票
    stocks = context.portfolio.positions.keys()
    
    for stock in stocks:
        signal, score = context.mtf.get_combined_signal(
            stock, context.previous_date, min_resonance=2
        )
        
        log.info(f"{stock}: 信号={signal}, 共振分数={score}")
        
        if signal == 'SELL':
            order_target_value(stock, 0)
        elif signal == 'BUY' and score >= 2:
            # 共振强，可以加仓
            pos = context.portfolio.positions[stock]
            if pos.value < context.portfolio.total_value * 0.15:
                order_target_value(stock, pos.value * 1.5)
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| rsi_period | 14 | RSI周期 |
| macd_fast | 12 | MACD快线周期 |
| macd_slow | 26 | MACD慢线周期 |
| macd_signal | 9 | MACD信号线周期 |
| ma_period | 20 | 均线周期 |
| min_resonance | 2 | 最小共振数 |

## 适用策略

- ✅ 中线趋势策略
- ✅ 价值投资
- ⚠️ 短线策略（延迟较大）

## 注意事项

1. 周线数据需要更长的时间
2. 多周期共振会降低交易频率
3. 建议与其他指标结合使用
