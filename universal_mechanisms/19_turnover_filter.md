# 换手率/波动率因子过滤 (Turnover Volatility Filter)

## 概述

使用换手率相对波动率因子过滤过度投机的股票，选择相对稳定的标的。

## 机制说明

1. **获取换手率和波动率数据**
2. **计算换手率/波动率比率**
3. **比率越小越稳定，保留比率小的前N%**
4. **过滤掉过度投机的股票**

## 效果验证

| 策略 | 效果 | 说明 |
|------|------|------|
| 换手率相对波动率因子选股500指数增强 | 12年15倍 | 经典策略 |

## 代码样例

```python
# turnover_filter.py
import numpy as np
import pandas as pd
import talib

class TurnoverVolatilityFilter:
    """换手率相对波动率过滤器"""
    
    def __init__(self, turnover_period=20, vol_period=20, keep_ratio=0.8):
        """
        参数:
        turnover_period: 换手率计算周期
        vol_period: 波动率计算周期
        keep_ratio: 保留比例（如0.8保留前80%）
        """
        self.turnover_period = turnover_period
        self.vol_period = vol_period
        self.keep_ratio = keep_ratio
    
    def calculate_turnover(self, stock, end_date):
        """计算换手率"""
        df = get_price(stock, 
                      end_date=end_date, 
                      fields=['volume', 'close'], 
                      count=self.turnover_period, 
                      panel=False)
        
        if df is None or len(df) < self.turnover_period:
            return None
        
        # 每日换手率 = 成交量 / 流通股本
        # 这里简化处理，用成交量变化率
        volume = df['volume'].values
        close = df['close'].values
        
        # 换手率（简化版）
        turnover = volume / (close * 1e8)  # 假设市值单位
        
        return np.mean(turnover[-self.turnover_period:])
    
    def calculate_volatility(self, stock, end_date):
        """计算波动率"""
        df = get_price(stock, 
                      end_date=end_date, 
                      fields='close', 
                      count=self.vol_period + 1, 
                      panel=False)
        
        if df is None or len(df) < self.vol_period + 1:
            return None
        
        close = df['close'].values
        returns = np.diff(close) / close[:-1]
        
        return np.std(returns[-self.vol_period:]) * np.sqrt(252)  # 年化波动率
    
    def calculate_turnover_volatility_ratio(self, stock, end_date):
        """计算换手率/波动率"""
        turnover = self.calculate_turnover(stock, end_date)
        volatility = self.calculate_volatility(stock, end_date)
        
        if turnover is None or volatility is None or volatility == 0:
            return None
        
        return turnover / volatility
    
    def filter_stocks(self, context, stocks, target_num=None):
        """过滤股票"""
        ratios = {}
        
        for stock in stocks:
            ratio = self.calculate_turnover_volatility_ratio(stock, context.previous_date)
            if ratio is not None:
                ratios[stock] = ratio
        
        if len(ratios) == 0:
            return stocks
        
        # 按比率排序（越小越稳定）
        sorted_stocks = sorted(ratios.items(), key=lambda x: x[1])
        
        # 保留前keep_ratio
        if target_num is None:
            target_num = int(len(sorted_stocks) * self.keep_ratio)
        
        filtered = [s[0] for s in sorted_stocks[:target_num]]
        
        return filtered


# 使用聚宽因子
class JQFactorFilter:
    """使用聚宽因子的过滤器"""
    
    def __init__(self, keep_ratio=0.8):
        self.keep_ratio = keep_ratio
    
    def filter_by_turnover_volatility(self, context, stocks):
        """使用聚宽换手率相对波动率因子"""
        try:
            # 获取因子值
            df = get_factor_values(stocks, 
                                  factors=['turnover_volatility'],
                                  end_date=context.previous_date,
                                  count=1)
            
            if df is None:
                return stocks
            
            # 获取最新一行
            factor = df.iloc[-1].dropna()
            
            # 排序（越小越好）
            sorted_factor = factor.sort_values(ascending=True)
            
            # 保留前keep_ratio
            target_num = int(len(sorted_factor) * self.keep_ratio)
            
            return sorted_factor.head(target_num).index.tolist()
            
        except Exception as e:
            log.error(f"获取因子失败: {e}")
            return stocks
    
    def filter_by_volume_stability(self, context, stocks, period=20):
        """成交量稳定性过滤"""
        stable_stocks = []
        
        for stock in stocks:
            try:
                df = get_price(stock, 
                              end_date=context.previous_date, 
                              fields='volume', 
                              count=period, 
                              panel=False)
                
                if df is None or len(df) < period:
                    continue
                
                volume = df['volume'].values
                cv = np.std(volume) / np.mean(volume)  # 变异系数
                
                if cv < 0.5:  # 变异系数小于0.5表示稳定
                    stable_stocks.append(stock)
                    
            except:
                continue
        
        return stable_stocks


# 使用示例
def initialize(context):
    context.tv_filter = TurnoverVolatilityFilter(keep_ratio=0.8)
    context.jq_filter = JQFactorFilter(keep_ratio=0.8)

def select_stocks(context):
    # 获取候选股票
    all_stocks = get_all_securities('stock').index.tolist()
    all_stocks = [s for s in all_stocks if s[:2] not in ['68', '4', '8']]
    
    # 基础过滤
    current_data = get_current_data()
    stocks = [s for s in all_stocks if s in current_data 
              and not current_data[s].is_st 
              and not current_data[s].paused]
    
    # 换手率波动率过滤
    stocks = context.tv_filter.filter_stocks(context, stocks)
    
    # 或使用聚宽因子
    # stocks = context.jq_filter.filter_by_turnover_volatility(context, stocks)
    
    log.info(f"换手率波动率过滤后剩余: {len(stocks)} 只")
    
    return stocks
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| turnover_period | 20 | 换手率计算周期 |
| vol_period | 20 | 波动率计算周期 |
| keep_ratio | 0.8 | 保留比例（80%） |

## 适用策略

- ✅ 基本面选股
- ✅ 指数增强
- ✅ 小市值选股

## 注意事项

1. 因子数据获取可能失败，需要容错
2. 阈值需要根据股票池特性调整
3. 可结合其他因子一起使用
