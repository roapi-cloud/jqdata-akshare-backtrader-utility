# 一致性风控机制 (Consistency Control)

## 概述

基于市场一致性程度（上涨家数落在某个区间的比例）进行风控，极端一致时预警。是微盘股策略的核心风控机制。

## 机制说明

1. **计算市场一致性**：涨跌幅落在某个区间（如-2%~2%）的股票占比
2. **一致性过高**：市场过度一致，可能反转
3. **一致性过低**：市场过度分散，可能见底
4. **结合BOLL带判断极端值**

## 效果验证

| 策略 | 效果 | 说明 |
|------|------|------|
| 一致性用在微盘控制回撤 | 回撤改善明显 | 2023年后特别有效 |
| 微盘股扩散指数双均线择时 | 年化100%+ | 扩散指数择时 |

## 代码样例

```python
# consistency_control.py
import numpy as np
import pandas as pd
import talib

class ConsistencyChecker:
    """一致性风控检查器"""
    
    def __init__(self, index='000852.XSHG', window=20, 
                 upper_threshold=0.86, lower_threshold=0.80):
        self.index = index  # 中证1000或中证2000
        self.window = window  # 计算窗口
        self.upper_threshold = upper_threshold  # 过度一致上限
        self.lower_threshold = lower_threshold  # 过度分散下限
    
    def calculate_consistency(self, context):
        """
        计算市场一致性
        一致性 = 涨跌幅落在 [-2%, 2%] 区间的股票占比
        """
        # 获取成分股
        try:
            stocks = get_index_stocks(self.index)[:500]  # 取前500只
        except:
            stocks = get_all_securities('stock')[:500]
        
        # 过滤ST和停牌
        current_data = get_current_data()
        stocks = [s for s in stocks if s in current_data 
                  and not current_data[s].is_st 
                  and not current_data[s].paused]
        
        # 获取近期价格
        prices = get_price(stocks, 
                           end_date=context.previous_date, 
                           fields='close', 
                           count=self.window + 1, 
                           panel=False)
        
        if prices is None or len(prices) == 0:
            return None
        
        # 转为DataFrame
        price_df = prices.pivot(index='time', columns='code', values='close')
        
        # 计算涨跌幅
        pchg = (price_df.iloc[-1] - price_df.iloc[-2]) / price_df.iloc[-2]
        
        # 一致性：涨跌幅在 [-2%, 2%] 的占比
        consistency = ((pchg >= -0.02) & (pchg <= 0.02)).mean()
        
        # 广度：上涨家数占比
        breadth = (pchg > 0).mean()
        
        return {
            'consistency': consistency,
            'breadth': breadth,
            'pchg_mean': pchg.mean(),
            'pchg_std': pchg.std()
        }
    
    def calculate_consistency_boll(self, context, boll_period=120):
        """
        计算一致性的BOLL带
        用于判断当前一致性是否极端
        """
        # 获取近期一致性历史
        consistency_history = []
        current = context.previous_date
        
        for i in range(boll_period + 10):
            test_date = current - pd.Timedelta(days=i)
            
            try:
                stocks = get_index_stocks(self.index)[:500]
                current_data = get_current_data()
                stocks = [s for s in stocks if s in current_data 
                         and not current_data[s].is_st 
                         and not current_data[s].paused]
                
                prices = get_price(stocks, 
                                 end_date=test_date, 
                                 fields='close', 
                                 count=5, 
                                 panel=False)
                
                if prices is not None and len(prices) > 1:
                    price_df = prices.pivot(index='time', columns='code', values='close')
                    if len(price_df) >= 2:
                        pchg = (price_df.iloc[-1] - price_df.iloc[-2]) / price_df.iloc[-2]
                        c = ((pchg >= -0.02) & (pchg <= 0.02)).mean()
                        consistency_history.append({'date': test_date, 'consistency': c})
            except:
                pass
        
        if len(consistency_history) < 20:
            return None, None, None
        
        history_df = pd.DataFrame(consistency_history).sort_values('date')
        history_df = history_df.drop_duplicates('date').tail(boll_period)
        
        # 计算BOLL
        consistency = history_df['consistency'].values
        middle = np.mean(consistency)
        std = np.std(consistency)
        upper = middle + 2 * std
        lower = middle - 2 * std
        
        return upper, middle, lower
    
    def check(self, context):
        """
        检查一致性状态
        返回: 'OVER_CONSISTENT', 'UNDER_CONSISTENT', 'NORMAL'
        """
        current = self.calculate_consistency(context)
        
        if current is None:
            return 'NORMAL'
        
        # 获取BOLL带
        upper, middle, lower = self.calculate_consistency_boll(context)
        
        if upper is None:
            # 没有足够历史数据，使用固定阈值
            if current['consistency'] > self.upper_threshold:
                return 'OVER_CONSISTENT'
            elif current['consistency'] < self.lower_threshold:
                return 'UNDER_CONSISTENT'
            return 'NORMAL'
        
        current_c = current['consistency']
        
        if current_c > upper:
            return 'OVER_CONSISTENT'
        elif current_c < lower:
            return 'UNDER_CONSISTENT'
        return 'NORMAL'
    
    def get_position_multiplier(self, context):
        """获取仓位倍数"""
        state = self.check(context)
        
        if state == 'OVER_CONSISTENT':
            return 0.5  # 减半仓
        elif state == 'UNDER_CONSISTENT':
            return 1.2  # 可加仓
        return 1.0


# 使用示例
def initialize(context):
    context.consistency = ConsistencyChecker(
        index='000852.XSHG',
        window=20,
        upper_threshold=0.86,
        lower_threshold=0.80
    )

def handle_data(context):
    # 获取仓位倍数
    multiplier = context.consistency.get_position_multiplier(context)
    
    state = context.consistency.check(context)
    log.info(f"一致性状态: {state}, 仓位倍数: {multiplier}")
    
    if state == 'OVER_CONSISTENT':
        # 市场过度一致，减仓
        for stock in context.portfolio.positions:
            pos = context.portfolio.positions[stock]
            order_target_value(stock, pos.value * 0.5)
        log.info("市场过度一致，降低仓位")
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| index | 000852.XSHG | 参考指数（中证1000/中证2000） |
| window | 20 | 计算窗口 |
| upper_threshold | 0.86 | 过度一致上限 |
| lower_threshold | 0.80 | 过度分散下限 |
| boll_period | 120 | BOLL带计算周期 |

## 适用策略

- ✅ 微盘股策略（核心风控）
- ✅ 小市值策略
- ✅ 反弹策略
- ✅ 全市场选股策略

## 注意事项

1. 一致性指标在极端市场更有效
2. 阈值需要根据历史数据优化
3. 可结合市场广度一起使用
