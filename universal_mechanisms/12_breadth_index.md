# 扩散指数/市场广度 (Breadth Index)

## 概述

计算站上均线的股票比例，判断市场广度。是RSRS择时的重要补充。

## 机制说明

1. **计算成分股中站上MA的股票数量**
2. **广度 = 站上MA数量 / 总数量**
3. **广度动量 = 广度变化率**
4. **结合广度绝对值和动量判断市场状态**

## 代码样例

```python
# breadth_index.py
import numpy as np
import pandas as pd

class BreadthIndicator:
    """市场广度指标"""
    
    def __init__(self, index='000300.XSHG', ma_period=20):
        self.index = index
        self.ma_period = ma_period
    
    def calculate_breadth(self, context, stocks=None):
        """
        计算市场广度
        广度 = 站上MA20的股票占比
        """
        if stocks is None:
            try:
                stocks = get_index_stocks(self.index)[:300]
            except:
                stocks = get_all_securities('stock')[:500]
        
        # 过滤
        current_data = get_current_data()
        stocks = [s for s in stocks if s in current_data 
                  and not current_data[s].is_st 
                  and not current_data[s].paused]
        
        # 获取价格
        prices = get_price(stocks, 
                          end_date=context.previous_date, 
                          fields='close', 
                          count=self.ma_period + 1, 
                          panel=False)
        
        if prices is None or len(prices) == 0:
            return None
        
        price_df = prices.pivot(index='time', columns='code', values='close')
        
        # 计算MA
        ma = price_df.iloc[-self.ma_period:].mean()
        current_price = price_df.iloc[-1]
        
        # 站上MA的占比
        above_ma = (current_price > ma).mean()
        
        # 广度动量（广度变化）
        prev_price = price_df.iloc[-2]
        prev_ma = price_df.iloc[-self.ma_period-1:-1].mean()
        prev_above_ma = (prev_price > prev_ma).mean()
        
        breadth_momentum = above_ma - prev_above_ma
        
        return {
            'breadth': above_ma,
            'breadth_momentum': breadth_momentum,
            'above_count': (current_price > ma).sum(),
            'total_count': len(stocks)
        }
    
    def get_market_state(self, context):
        """判断市场状态"""
        data = self.calculate_breadth(context)
        
        if data is None:
            return 'UNKNOWN', 0
        
        breadth = data['breadth']
        momentum = data['breadth_momentum']
        
        # 状态判断
        if breadth < 0.15:
            return '极弱停手', 0
        elif breadth < 0.25:
            return '底部防守', 0.3
        elif breadth < 0.35:
            return '震荡平衡', 0.5
        elif momentum > 0.05:  # 广度正在扩张
            return '趋势正常', 0.8
        else:
            return '趋势正常', 0.7
    
    def get_position_ratio(self, context):
        """获取仓位比例"""
        state, ratio = self.get_market_state(context)
        return ratio


# 使用示例
def initialize(context):
    context.breadth = BreadthIndicator(index='000300.XSHG', ma_period=20)

def handle_data(context):
    state, ratio = context.breadth.get_market_state(context)
    log.info(f"市场广度状态: {state}, 建议仓位: {ratio}")
    
    # 根据仓位比例调整持仓
    target_value = context.portfolio.total_value * ratio
    
    for stock in context.portfolio.positions:
        pos = context.portfolio.positions[stock]
        if pos.value > target_value:
            order_target_value(stock, target_value * 0.5)
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| index | 000300.XSHG | 参考指数 |
| ma_period | 20 | 均线周期 |

## 适用策略

- ✅ 状态路由增强
- ✅ 择时辅助
- ✅ 行业轮动
