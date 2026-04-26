# 扩散指数双均线择时 (Diffusion Index Timing)

## 概述

扩散指数（KS指数）衡量一段时间内上涨股票的占比，通过双均线交叉判断市场趋势。专为微盘股/小市值策略设计，在2018-2024年回测中显著改善回撤。

来源：聚宽策略 `37 微盘股扩散指数双均线择时.txt`

## 核心逻辑

```
扩散指数 KS = 过去N天内收盘价高于开盘价的股票数 / 总股票数

双均线：
- EMA6(KS) > EMA28(KS)：多头，持仓
- EMA6(KS) < EMA28(KS)：空头，清仓
```

与市场宽度（站上MA20占比）的区别：
- 市场宽度：静态截面，看当前有多少股票在均线上方
- 扩散指数：动态时序，看过去N天内有多少股票在上涨

## 效果验证

| 策略 | 无择时 | 有扩散指数择时 | 改善 |
|------|--------|--------------|------|
| 微盘股策略 | 回撤45% | 回撤28% | 回撤-38% |
| 小市值策略 | 年化80% | 年化65% | 收益略降但更稳 |

## 适用时机

- 微盘股/小市值策略的主要择时工具
- 市场出现系统性下跌时（如2022年、2024年初）效果最明显
- 震荡市中可能产生频繁信号，需要结合其他指标
- 不适合ETF轮动（RSRS更适合）

## 代码样例

```python
# diffusion_index.py
import numpy as np
import pandas as pd
import talib
from jqdata import *

class DiffusionIndexTimer:
    """扩散指数双均线择时"""
    
    def __init__(self, index='000852.XSHG', watch_day=20,
                 fast_period=6, slow_period=28, history_days=30):
        """
        参数:
        index: 参考指数（中证1000）
        watch_day: 计算扩散指数的窗口（N天内上涨占比）
        fast_period: 快均线周期（EMA6）
        slow_period: 慢均线周期（EMA28）
        history_days: 计算均线需要的历史天数
        """
        self.index = index
        self.watch_day = watch_day
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.history_days = history_days
    
    def calculate_ks_index(self, context):
        """
        计算扩散指数序列
        KS = 过去watch_day天内，收盘价高于开盘价的股票占比
        """
        yesterday = context.previous_date
        dates = get_trade_days(end_date=yesterday, count=self.history_days)
        
        ks_series = []
        for date in dates:
            try:
                stocks = get_index_stocks(self.index, date=date)
                # 获取每只股票过去watch_day天的价格
                df = get_price(
                    stocks, end_date=date,
                    fields=['close', 'open'],
                    count=self.watch_day,
                    fill_paused=False, skip_paused=False,
                    panel=False
                ).dropna()
                
                # 计算每只股票的涨跌（收盘 vs 开盘）
                end_price = df.groupby('code')['close'].last()
                open_price = df.groupby('code')['open'].first()
                
                result = end_price - open_price
                ks = len(result[result > 0]) / max(len(result), 1)
                ks_series.append(ks)
            except Exception as e:
                ks_series.append(0.5)  # 异常时用中性值
        
        return np.array(ks_series)
    
    def get_timing_signal(self, context):
        """
        获取择时信号
        返回: True=空仓（清仓信号），False=持仓
        """
        ks_series = self.calculate_ks_index(context)
        
        if len(ks_series) < self.slow_period + 5:
            return False  # 数据不足，默认持仓
        
        # 计算双均线
        ema_fast = talib.EMA(ks_series, self.fast_period)
        ema_slow = talib.EMA(ks_series, self.slow_period)
        
        # 最新信号：快线在慢线下方 = 空头 = 清仓
        should_clear = ema_fast[-1] < ema_slow[-1]
        
        return should_clear
    
    def get_signal_with_detail(self, context):
        """获取信号及详情"""
        ks_series = self.calculate_ks_index(context)
        
        if len(ks_series) < self.slow_period + 5:
            return False, {'ks': 0.5, 'ema_fast': 0.5, 'ema_slow': 0.5}
        
        ema_fast = talib.EMA(ks_series, self.fast_period)
        ema_slow = talib.EMA(ks_series, self.slow_period)
        
        should_clear = ema_fast[-1] < ema_slow[-1]
        
        detail = {
            'ks_latest': ks_series[-1],
            'ema_fast': ema_fast[-1],
            'ema_slow': ema_slow[-1],
            'signal': '空头清仓' if should_clear else '多头持仓'
        }
        
        return should_clear, detail


# 使用示例
def initialize(context):
    context.diffusion = DiffusionIndexTimer(
        index='000852.XSHG',  # 中证1000
        watch_day=20,
        fast_period=6,
        slow_period=28,
        history_days=40
    )
    
    run_daily(prepare_stock_list, '9:05')
    run_daily(daily_adjustment, '9:30')

def daily_adjustment(context):
    # 获取扩散指数择时信号
    should_clear, detail = context.diffusion.get_signal_with_detail(context)
    
    log.info(f"扩散指数: KS={detail['ks_latest']:.3f}, "
             f"EMA6={detail['ema_fast']:.3f}, EMA28={detail['ema_slow']:.3f}, "
             f"信号={detail['signal']}")
    
    if should_clear:
        # 清仓
        for stock in list(context.portfolio.positions.keys()):
            order_target_value(stock, 0)
        log.info("扩散指数空头，清仓")
        return
    
    # 正常选股交易逻辑
    # ... 小市值选股 ...
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| index | 000852.XSHG | 参考指数（中证1000） |
| watch_day | 20 | 扩散指数计算窗口 |
| fast_period | 6 | 快均线（EMA6） |
| slow_period | 28 | 慢均线（EMA28） |
| history_days | 30-40 | 历史数据天数 |

## 与其他机制组合

```
微盘股策略推荐组合：
扩散指数择时（主要择时）
    + 一致性风控（极端情绪过滤）
    + 情绪开关（涨停家数）
    + 停手机制（连亏保护）
```

## 适用策略

- ✅ 微盘股策略（核心择时）
- ✅ 小市值策略（辅助择时）
- ✅ 中证1000/中证2000成分股策略
- ⚠️ ETF轮动（不适合，RSRS更好）
- ⚠️ 大盘蓝筹策略（不适合）

## 待调研方向

1. **行业扩散指数**：分行业计算扩散指数，用于行业轮动
2. **多周期扩散**：同时计算5日、20日、60日扩散指数
3. **扩散指数+RSRS**：双重择时，减少误判
4. **动态参数**：根据市场波动率动态调整均线周期
