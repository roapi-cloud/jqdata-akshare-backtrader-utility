# MAC动量因子 (Moving Average Cross Momentum)

## 概述

MAC动量因子通过比较短期均线与长期均线的相对位置，衡量股票的中期动量强度。相比简单的N日收益率动量，MAC动量对噪声更不敏感，在A股小市值策略中表现优异。

来源：聚宽策略 `74 【动量应用V1】12年120倍，根据研报思路调整.txt`，`22 截止到21年12月依然有效的小市值适配因子.txt`

## 核心逻辑

```
MAC20 = 当前收盘价 / 过去20日均价 - 1  （短期动量）
MAC120 = 当前收盘价 / 过去120日均价 - 1 （中期动量）

综合评分 = 4 × normalize(MAC120) + 1 × normalize(MAC20)
（MAC120权重更高，中期趋势更重要）
```

与传统动量的区别：
- 传统动量：`return = (P_now - P_n_days_ago) / P_n_days_ago`
- MAC动量：`MAC = P_now / MA(n) - 1`，用均价替代单点价格，更稳定

## 效果验证

| 策略 | 年化收益 | 最大回撤 | 说明 |
|------|---------|---------|------|
| 小市值+MAC动量 | 120倍/12年 | 30-35% | 聚宽回测 |
| 纯小市值 | 50-80% | 35-40% | 对比基准 |
| MAC动量改善 | +20-30% | 回撤略降 | 加入MAC后 |

## 适用时机

- 小市值/微盘股策略的选股排序因子
- 趋势行情中效果最好（2019-2021年）
- 震荡市中效果一般
- 与基本面因子（EPS、成长率）结合使用

## 代码样例

```python
# mac_momentum_factor.py
import numpy as np
import pandas as pd
from jqdata import *
from jqfactor import get_factor_values

class MACMomentumFactor:
    """MAC动量因子选股器"""
    
    def __init__(self, fast_period=20, slow_period=120,
                 fast_weight=1, slow_weight=4):
        """
        参数:
        fast_period: 短期均线周期（20日）
        slow_period: 长期均线周期（120日）
        fast_weight: 短期动量权重
        slow_weight: 长期动量权重（更重要）
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.fast_weight = fast_weight
        self.slow_weight = slow_weight
    
    def get_mac_scores(self, context, stock_list):
        """
        计算MAC动量综合评分
        
        返回: DataFrame，包含code和score列，按score降序排列
        """
        yesterday = context.previous_date
        
        # 方法1：使用jqfactor（推荐，更快）
        try:
            mac_fast = get_factor_values(
                stock_list, f'MAC{self.fast_period}',
                end_date=yesterday, count=1
            )[f'MAC{self.fast_period}'].iloc[0]
            
            mac_slow = get_factor_values(
                stock_list, f'MAC{self.slow_period}',
                end_date=yesterday, count=1
            )[f'MAC{self.slow_period}'].iloc[0]
            
            df = pd.DataFrame({
                'code': stock_list,
                'mac_fast': mac_fast.values,
                'mac_slow': mac_slow.values
            }).dropna()
            
        except Exception:
            # 方法2：手动计算
            df = self._calculate_mac_manually(stock_list, yesterday)
        
        if len(df) == 0:
            return pd.DataFrame(columns=['code', 'score'])
        
        # 标准化（z-score）
        def normalize(series):
            mean, std = series.mean(), series.std()
            if std == 0:
                return series * 0
            return (series - mean) / std
        
        df['mac_fast_norm'] = normalize(df['mac_fast'])
        df['mac_slow_norm'] = normalize(df['mac_slow'])
        
        # 综合评分
        df['score'] = (self.slow_weight * df['mac_slow_norm'] +
                       self.fast_weight * df['mac_fast_norm'])
        
        return df[['code', 'score']].sort_values('score', ascending=False)
    
    def _calculate_mac_manually(self, stock_list, date):
        """手动计算MAC因子"""
        prices = get_price(
            stock_list, end_date=date,
            fields='close', count=self.slow_period + 1,
            panel=False
        )
        price_df = prices.pivot(index='time', columns='code', values='close')
        
        current = price_df.iloc[-1]
        ma_fast = price_df.iloc[-self.fast_period:].mean()
        ma_slow = price_df.iloc[-self.slow_period:].mean()
        
        mac_fast = current / ma_fast - 1
        mac_slow = current / ma_slow - 1
        
        return pd.DataFrame({
            'code': price_df.columns,
            'mac_fast': mac_fast.values,
            'mac_slow': mac_slow.values
        }).dropna()
    
    def get_top_stocks(self, context, stock_list, top_n=10):
        """获取MAC动量最强的前N只股票"""
        scores = self.get_mac_scores(context, stock_list)
        if len(scores) == 0:
            return []
        return list(scores['code'].head(top_n))
    
    def filter_by_mac(self, context, stock_list, top_pct=0.3):
        """过滤保留MAC动量前N%的股票"""
        scores = self.get_mac_scores(context, stock_list)
        if len(scores) == 0:
            return stock_list
        n = max(1, int(len(scores) * top_pct))
        return list(scores['code'].head(n))


# 使用示例（结合小市值+成长因子）
def initialize(context):
    context.mac = MACMomentumFactor(
        fast_period=20,
        slow_period=120,
        fast_weight=1,
        slow_weight=4
    )
    
    g.stock_num = 10
    run_weekly(my_trade, weekday=1, time='9:30')

def my_trade(context):
    # 基础股票池
    initial_list = get_all_securities().index.tolist()
    initial_list = [s for s in initial_list
                   if s[:2] not in ['68'] and s[0] not in ['4', '8']
                   and not get_current_data()[s].is_st
                   and not get_current_data()[s].paused]
    
    # 成长因子筛选（营收增长率前10%）
    from jqfactor import get_factor_values
    yesterday = context.previous_date
    growth = get_factor_values(initial_list, 'sales_growth',
                               end_date=yesterday, count=1)['sales_growth'].iloc[0]
    growth_df = growth.dropna().sort_values(ascending=False)
    growth_list = list(growth_df.index[:int(len(growth_df) * 0.1)])
    
    # 小市值筛选
    q = query(valuation.code, valuation.circulating_market_cap,
              indicator.eps).filter(
        valuation.code.in_(growth_list)
    ).order_by(valuation.circulating_market_cap.asc()).limit(30)
    df = get_fundamentals(q)
    df = df[df['eps'] > 0]
    small_cap_list = list(df.code)
    
    # MAC动量排序（最终选股）
    final_list = context.mac.get_top_stocks(context, small_cap_list, top_n=g.stock_num)
    
    if not final_list:
        return
    
    # 调仓
    for s in list(context.portfolio.positions.keys()):
        if s not in final_list:
            order_target_value(s, 0)
    
    value = context.portfolio.total_value / len(final_list)
    for s in final_list:
        order_target_value(s, value)
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| fast_period | 20 | 短期均线（20日） |
| slow_period | 120 | 长期均线（120日） |
| fast_weight | 1 | 短期权重 |
| slow_weight | 4 | 长期权重（更重要） |

## 因子组合建议

```
小市值+成长+MAC动量（推荐组合）：
1. 成长因子（sales_growth）：筛选营收增长前10%
2. 小市值：在成长股中取最小市值前30只
3. MAC动量：按MAC综合评分排序，取前10只
4. EPS>0：过滤亏损股
```

## 适用策略

- ✅ 小市值/微盘股策略（核心排序因子）
- ✅ 成长股策略（趋势确认）
- ✅ 多因子模型（动量因子之一）
- ⚠️ 价值股策略（动量与价值有时冲突）
- ⚠️ 震荡市（动量因子失效）

## 待调研方向

1. **反转效应**：短期（5日）动量反转，中期（20-120日）动量延续
2. **行业中性MAC**：在行业内部计算MAC，避免行业偏差
3. **MAC+成交量**：结合成交量确认动量有效性
4. **MAC衰减**：动量因子的半衰期约9-10天，需要高频更新
