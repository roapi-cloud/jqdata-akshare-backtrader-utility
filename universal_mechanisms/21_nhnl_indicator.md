# NH-NL净新高占比 (行业指数顶底)

## 概述

NH-NL指标用于判断行业指数顶底，是行业轮动的重要参考。

## 机制说明

1. **计算行业指数中创52周新高与新低之差占比**
2. **正值代表市场强势，负值代表市场弱势**

## 阈值划分

| NH-NL值 | 状态 | 信号 |
|---------|------|------|
| **≥30%** | 贪婪 | 顶部预警,做空信号 |
| **20-30%** | 乐观 | 关注顶部 |
| **-20-20%** | 正常 | 维持 |
| **-30-(-20%)** | 悲观 | 关注底部 |
| **≤-30%** | 恐惧 | 底部信号,做多信号 |

## 代码样例

```python
# nhnl_indicator.py
import numpy as np
import pandas as pd

class NHNLIndicator:
    """NH-NL净新高占比指标"""
    
    def __init__(self):
        pass
    
    def get_52week_high_low(self, stocks, end_date, lookback=252):
        """获取52周新高新低股数"""
        high_count = 0
        low_count = 0
        
        for stock in stocks:
            try:
                prices = get_price(stock, 
                                 end_date=end_date, 
                                 fields='close', 
                                 count=lookback, 
                                 panel=False)
                
                if prices is None or len(prices) < 252:
                    continue
                
                current = prices['close'].iloc[-1]
                high_52w = prices['close'].max()
                low_52w = prices['close'].min()
                
                if current >= high_52w * 0.98:  # 接近新高
                    high_count += 1
                if current <= low_52w * 1.02:  # 接近新低
                    low_count += 1
                    
            except:
                continue
        
        return high_count, low_count
    
    def calculate_nhnl_pct(self, stocks, end_date):
        """计算NH-NL占比"""
        high_count, low_count = self.get_52week_high_low(stocks, end_date)
        total = len(stocks)
        
        if total == 0:
            return 0
        
        nhnl_pct = (high_count - low_count) / total * 100
        return nhnl_pct
    
    def get_signal(self, nhnl_pct):
        """获取信号"""
        if nhnl_pct >= 30:
            return 'TOP_SIGNAL', '贪婪,顶部预警'
        elif nhnl_pct >= 20:
            return 'OPTIMISTIC', '乐观,关注顶部'
        elif nhnl_pct >= -20:
            return 'NORMAL', '正常'
        elif nhnl_pct >= -30:
            return 'PESSIMISTIC', '悲观,关注底部'
        else:
            return 'BOTTOM_SIGNAL', '恐惧,底部信号'


# 使用示例
def initialize(context):
    context.nhnl = NHNLIndicator()

def get_monthly_signal(context):
    # 获取全市场股票
    stocks = get_all_securities('stock').index.tolist()
    
    # 计算NH-NL
    nhnl_pct = context.nhnl.calculate_nhnl_pct(stocks, context.previous_date)
    signal, desc = context.nhnl.get_signal(nhnl_pct)
    
    log.info(f"NH-NL: {nhnl_pct:.1f}%, 信号: {desc}")
    
    return signal, nhnl_pct
```

## 适用策略

- ✅ 行业轮动辅助判断
- ✅ 指数增强
- ✅ 顶部/底部识别
