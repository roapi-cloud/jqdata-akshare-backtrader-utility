# 北向资金信号机制

## 概述

跟踪沪深股通北向资金流入/流出，利用布林带判断超买超卖。是判断外资情绪的重要指标。

## 机制说明

1. **获取北向资金净流入数据**（沪股通+深股通）
2. **计算布林带**（通常252日周期，1.5倍标准差）
3. **突破上轨=超买（卖出信号）**
4. **跌破下轨=超卖（买入信号）**

## 效果验证

| 策略 | 效果 | 备注 |
|------|------|------|
| 北向资金A股择时策略 | 5年16倍 | 经典策略 |
| 北向Boll带ETF组合宝 | 年化60%+ | 付费策略 |
| 北向RSRS与布林带择时 | 年化40%+ | 组合使用 |

## 代码样例

```python
# north_money.py
import pandas as pd
import numpy as np
from jqfactor import get_factor_values
from jqdatasdk import finance

class NorthMoneySignal:
    """北向资金信号"""
    
    def __init__(self, boll_window=252, boll_std=1.5):
        self.boll_window = boll_window
        self.boll_std = boll_std
        self.data = None
    
    def get_north_money(self, context, days=2):
        """获取北向资金净流入（近N日合计）"""
        yesterday = context.previous_date.strftime('%Y-%m-%d')
        
        try:
            # 沪股通
            n_sh = finance.run_query(
                query(finance.STK_ML_QUOTA)
                .filter(finance.STK_ML_QUOTA.day == yesterday)
                .filter(finance.STK_ML_QUOTA.type == '1')  # 沪股通
            )
            
            # 深股通
            n_sz = finance.run_query(
                query(finance.STK_ML_QUOTA)
                .filter(finance.STK_ML_QUOTA.day == yesterday)
                .filter(finance.STK_ML_QUOTA.type == '3')  # 深股通
            )
            
            # 计算净流入（买入 - 卖出）
            sh_buy = n_sh['buy'].sum() if len(n_sh) > 0 else 0
            sh_sell = n_sh['sell'].sum() if len(n_sh) > 0 else 0
            sz_buy = n_sz['buy'].sum() if len(n_sz) > 0 else 0
            sz_sell = n_sz['sell'].sum() if len(n_sz) > 0 else 0
            
            sh_net = sh_buy - sh_sell
            sz_net = sz_buy - sz_sell
            
            return sh_net + sz_net
            
        except Exception as e:
            log.error(f"获取北向资金失败: {e}")
            return 0
    
    def get_north_money_series(self, context, days=20):
        """获取近N日北向资金序列"""
        money_list = []
        current = context.previous_date
        
        for i in range(days):
            test_date = current - pd.Timedelta(days=i)
            test_date_str = test_date.strftime('%Y-%m-%d')
            
            try:
                n_sh = finance.run_query(
                    query(finance.STK_ML_QUOTA)
                    .filter(finance.STK_ML_QUOTA.day == test_date_str)
                    .filter(finance.STK_ML_QUOTA.type == '1')
                )
                n_sz = finance.run_query(
                    query(finance.STK_ML_QUOTA)
                    .filter(finance.STK_ML_QUOTA.day == test_date_str)
                    .filter(finance.STK_ML_QUOTA.type == '3')
                )
                
                if len(n_sh) > 0 or len(n_sz) > 0:
                    sh_net = n_sh['buy'].sum() - n_sh['sell'].sum() if len(n_sh) > 0 else 0
                    sz_net = n_sz['buy'].sum() - n_sz['sell'].sum() if len(n_sz) > 0 else 0
                    money_list.append({'date': test_date, 'money': sh_net + sz_net})
            except:
                pass
        
        self.data = pd.DataFrame(money_list)
        return self.data
    
    def calculate_boll_band(self):
        """计算布林带"""
        if self.data is None or len(self.data) < 10:
            return None, None, None
        
        mean = self.data['money'].mean()
        std = self.data['money'].std()
        
        upper = mean + self.boll_std * std
        lower = mean - self.boll_std * std
        
        return upper, mean, lower
    
    def get_signal(self, context):
        """获取交易信号"""
        # 获取最新北向资金
        money = self.get_north_money(context, days=2)
        
        # 获取历史数据计算布林带
        self.get_north_money_series(context, days=self.boll_window)
        upper, mean, lower = self.calculate_boll_band()
        
        if upper is None:
            return 'HOLD'
        
        if money > upper:
            return 'SELL'  # 超买
        elif money < lower:
            return 'BUY'   # 超卖
        return 'HOLD'


# 使用示例
def initialize(context):
    context.north_money = NorthMoneySignal(boll_window=252, boll_std=1.5)
    run_daily(handle_data, time='11:30')

def handle_data(context):
    signal = context.north_money.get_signal(context)
    
    if signal == 'SELL':
        # 清仓
        for stock in context.portfolio.positions:
            order_target_value(stock, 0)
    elif signal == 'BUY':
        # 买入创业板ETF
        if '159915.XSHE' not in context.portfolio.positions:
            order_target_percent('159915.XSHE', 0.95)
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| boll_window | 252 | 布林带计算窗口 |
| boll_std | 1.5 | 布林带标准差倍数 |
| upper_threshold | 10 | 超买绝对阈值（亿元） |
| lower_threshold | -10 | 超卖绝对阈值（亿元） |

## 适用策略

- ✅ ETF轮动择时
- ✅ 大盘择时辅助
- ✅ 外资偏好的蓝筹/消费
- ✅ 北向资金主题策略

## 注意事项

1. 北向资金数据从2014年11月才有
2. 需要在收盘后或次日获取数据
3. 建议结合RSRS等其他指标使用
