# 波动率仓位调整机制 (ATR-based Position Sizing)

## 概述

根据市场波动率（ATR）动态调整仓位，波动率高时轻仓，低时重仓。是桥水全天候等知名策略的核心机制。

## 机制说明

1. **计算ATR（Average True Range）**：反映市场波动程度
2. **计算ATR与价格的比率**：标准化波动率
3. **设定波动率高/低阈值**
4. **根据波动率状态调整仓位**

## 效果验证

| 策略 | 效果 | 说明 |
|------|------|------|
| 中证500指增+CTA | 波动率小1.2倍仓位，波动率大0.5倍 | CTA策略核心 |
| 桥水全天候 | ATR仓位管理 | 年化10-15%，回撤3-5% |
| 趋势永存 | ATR计算期望仓位 | 16年跑赢大盘 |

## 代码样例

```python
# volatility_position.py
import numpy as np
import talib

class VolatilityPositionManager:
    """波动率仓位管理器"""
    
    def __init__(self, atr_period=20, base_position=0.7):
        self.atr_period = atr_period
        self.base_position = base_position  # 基础仓位
        self.low_vol_threshold = 0.02  # 低波动阈值(ATR/价格)
        self.high_vol_threshold = 0.05  # 高波动阈值
        
    def calculate_atr(self, security, end_date, period=20):
        """计算ATR"""
        df = get_price(security, 
                       end_date=end_date, 
                       fields=['high', 'low', 'close'], 
                       count=period+1, 
                       panel=False)
        
        if df is None or len(df) < period + 1:
            return None
        
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        # 计算True Range
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        tr[0] = high[0] - low[0]  # 第一个值处理
        
        # ATR
        atr = np.mean(tr[-period:])
        
        return atr
    
    def calculate_atr_ratio(self, security, end_date):
        """计算ATR与价格的比率"""
        atr = self.calculate_atr(security, end_date, self.atr_period)
        if atr is None:
            return None
        
        current_price = get_price(security, end_date=end_date, 
                                  fields='close', count=1)['close'].iloc[-1]
        
        return atr / current_price
    
    def get_volatility_state(self, security, end_date):
        """获取波动率状态"""
        atr_ratio = self.calculate_atr_ratio(security, end_date)
        
        if atr_ratio is None:
            return 'UNKNOWN', 1.0
        
        if atr_ratio < self.low_vol_threshold:
            return 'LOW', 1.2   # 低波动，可以加仓
        elif atr_ratio > self.high_vol_threshold:
            return 'HIGH', 0.5  # 高波动，必须减仓
        else:
            return 'NORMAL', 1.0
    
    def get_position(self, security, end_date):
        """获取目标仓位"""
        state, multiplier = self.get_volatility_state(security, end_date)
        return self.base_position * multiplier


# 动态ATR止损止盈
class ATRStopLoss:
    """基于ATR的动态止损止盈"""
    
    def __init__(self, atr_period=20, stop_loss_atr=2, take_profit_atr=3):
        self.atr_period = atr_period
        self.stop_loss_atr = stop_loss_atr
        self.take_profit_atr = take_profit_atr
    
    def calculate_stop_prices(self, entry_price, atr, direction='long'):
        """计算止损止盈价格"""
        if direction == 'long':
            stop_loss = entry_price - self.stop_loss_atr * atr
            take_profit = entry_price + self.take_profit_atr * atr
        else:
            stop_loss = entry_price + self.stop_loss_atr * atr
            take_profit = entry_price - self.take_profit_atr * atr
        
        return stop_loss, take_profit
    
    def check_stop(self, current_price, entry_price, atr, direction='long'):
        """检查是否触发止损止盈"""
        stop_loss, take_profit = self.calculate_stop_prices(entry_price, atr, direction)
        
        if direction == 'long':
            if current_price <= stop_loss:
                return 'STOP_LOSS'
            if current_price >= take_profit:
                return 'TAKE_PROFIT'
        else:
            if current_price >= stop_loss:
                return 'STOP_LOSS'
            if current_price <= take_profit:
                return 'TAKE_PROFIT'
        
        return 'HOLD'


# 使用示例
def initialize(context):
    context.vol_mgr = VolatilityPositionManager(atr_period=20, base_position=0.7)
    context.atr_stop = ATRStopLoss(atr_period=20, stop_loss_atr=2, take_profit_atr=3)

def handle_data(context):
    # 获取基于波动率的仓位
    position = context.vol_mgr.get_position('000300.XSHG', context.previous_date)
    
    # 调整持仓
    current_value = context.portfolio.total_value
    target_value = current_value * position
    
    for stock in context.portfolio.positions:
        pos = context.portfolio.positions[stock]
        if pos.value > target_value:
            order_target_value(stock, target_value * 0.5)
    
    # 检查止损止盈
    for stock in context.portfolio.positions:
        pos = context.portfolio.positions[stock]
        
        atr = context.vol_mgr.calculate_atr(stock, context.previous_date)
        if atr is None:
            continue
        
        action = context.atr_stop.check_stop(
            pos.price, pos.avg_cost, atr, direction='long'
        )
        
        if action in ['STOP_LOSS', 'TAKE_PROFIT']:
            order_target_value(stock, 0)
            log.info(f"{stock} 触发 {action}")
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| atr_period | 20 | ATR计算周期 |
| base_position | 0.7 | 基础仓位 |
| low_vol_threshold | 0.02 | 低波动阈值(ATR/价格) |
| high_vol_threshold | 0.05 | 高波动阈值 |
| stop_loss_atr | 2 | 止损ATR倍数 |
| take_profit_atr | 3 | 止盈ATR倍数 |

## 适用策略

- ✅ 所有策略的仓位调整
- ✅ CTA策略
- ✅ 全天候组合
- ✅ 趋势跟踪策略

## 注意事项

1. ATR指标对参数不敏感，周期设置灵活
2. 波动率阈值需要根据品种特性调整
3. 可结合市场广度等其他指标综合判断
