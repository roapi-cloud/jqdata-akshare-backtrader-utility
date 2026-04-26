# 拥挤度检测机制 (Crowding Detection)

## 概述

检测策略/行业的拥挤程度，避免在过度拥挤时开仓。微盘股策略必备风控机制。

## 机制说明

1. **离散度指标**：涨跌幅标准差（拥挤时个股涨跌趋同）
2. **集中度指标**：成交额前10%占比（拥挤时资金高度集中）
3. **综合判断**：低离散度+高集中度 = 拥挤

## 代码样例

```python
# crowding_detection.py
import numpy as np
import pandas as pd

class CrowdingDetector:
    """拥挤度检测器"""
    
    def __init__(self, index='000852.XSHG', 
                 dispersion_threshold=0.03, 
                 concentration_threshold=0.4):
        self.index = index
        self.dispersion_threshold = dispersion_threshold  # 离散度阈值
        self.concentration_threshold = concentration_threshold  # 集中度阈值
    
    def calculate_dispersion(self, context, stocks=None):
        """
        计算涨跌离散度
        离散度 = 涨跌幅标准差
        离散度低 = 市场拥挤（个股涨跌趋同）
        """
        if stocks is None:
            try:
                stocks = get_index_stocks(self.index)[:500]
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
                           count=5, 
                           panel=False)
        
        if prices is None or len(prices) == 0:
            return None
        
        price_df = prices.pivot(index='time', columns='code', values='close')
        
        # 涨跌幅
        pchg = price_df.pct_change().iloc[-1]
        
        # 离散度
        dispersion = pchg.std()
        mean_pchg = pchg.mean()
        
        return {
            'dispersion': dispersion,
            'mean_pchg': mean_pchg,
            'positive_ratio': (pchg > 0).mean()
        }
    
    def calculate_concentration(self, context, stocks=None):
        """
        计算成交集中度
        集中度 = 成交额前10% / 总成交额
        集中度高 = 市场拥挤
        """
        if stocks is None:
            try:
                stocks = get_index_stocks(self.index)[:500]
            except:
                stocks = get_all_securities('stock')[:500]
        
        current_data = get_current_data()
        stocks = [s for s in stocks if s in current_data 
                 and not current_data[s].is_st 
                 and not current_data[s].paused]
        
        # 获取成交额
        amounts = get_price(stocks, 
                           end_date=context.previous_date, 
                           fields='money', 
                           count=1, 
                           panel=False)
        
        if amounts is None or len(amounts) == 0:
            return None
        
        amount = amounts.iloc[-1]
        
        # 前10%集中度
        top10_sum = amount.nlargest(10).sum()
        total = amount.sum()
        concentration = top10_sum / total if total > 0 else 0
        
        return {
            'concentration': concentration,
            'top10_amount': top10_sum,
            'total_amount': total
        }
    
    def is_crowded(self, context):
        """判断市场是否拥挤"""
        dispersion_data = self.calculate_dispersion(context)
        concentration_data = self.calculate_concentration(context)
        
        if dispersion_data is None or concentration_data is None:
            return False
        
        # 条件：离散度低 + 集中度高
        crowded = (dispersion_data['dispersion'] < self.dispersion_threshold and 
                   concentration_data['concentration'] > self.concentration_threshold)
        
        return crowded
    
    def get_crowding_state(self, context):
        """获取拥挤状态"""
        dispersion_data = self.calculate_dispersion(context)
        concentration_data = self.calculate_concentration(context)
        
        if dispersion_data is None or concentration_data is None:
            return 'UNKNOWN'
        
        if self.is_crowded(context):
            return 'CROWDED'
        
        # 冷清状态
        if dispersion_data['dispersion'] > self.dispersion_threshold * 2:
            return 'COLD'
        
        return 'NORMAL'
    
    def get_position_multiplier(self, context):
        """获取仓位倍数"""
        state = self.get_crowding_state(context)
        
        if state == 'CROWDED':
            return 0.5  # 拥挤时减半仓
        elif state == 'COLD':
            return 1.2  # 冷清时可加仓
        return 1.0


# 使用示例
def initialize(context):
    context.crowding = CrowdingDetector(
        index='000852.XSHG',
        dispersion_threshold=0.03,
        concentration_threshold=0.4
    )

def handle_data(context):
    state = context.crowding.get_crowding_state(context)
    multiplier = context.crowding.get_position_multiplier(context)
    
    log.info(f"拥挤度状态: {state}, 仓位倍数: {multiplier}")
    
    if state == 'CROWDED':
        # 市场拥挤，清仓
        for stock in context.portfolio.positions:
            order_target_value(stock, 0)
        log.info("市场过度拥挤，空仓等待")
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| index | 000852.XSHG | 参考指数 |
| dispersion_threshold | 0.03 | 离散度阈值 |
| concentration_threshold | 0.4 | 集中度阈值（40%） |

## 适用策略

- ✅ 微盘股策略（小市值拥挤度极高）
- ✅ 趋势策略
- ✅ 动量策略
- ✅ 全市场选股策略

## 注意事项

1. 拥挤度指标是反向指标
2. 拥挤后往往还有惯性，信号可能过早
3. 建议结合其他指标综合判断
