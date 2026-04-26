# 宏观事件过滤 (Macro Event Filter)

## 概述

在重要宏观数据（如CPI、PPI、GDP、非农）发布前后降低仓位，避免意外波动。

## 机制说明

1. **维护宏观事件日历**
2. **检测当前是否在事件窗口期**
3. **窗口期内降低风险敞口**
4. **事件后恢复正常仓位**

## 代码样例

```python
# macro_event_filter.py
import pandas as pd
from datetime import datetime

class MacroEventFilter:
    """宏观事件过滤器"""
    
    def __init__(self, pre_days=1, post_days=1, reduction_ratio=0.5):
        """
        参数:
        pre_days: 事件前影响天数
        post_days: 事件后影响天数
        reduction_ratio: 窗口期内仓位缩减比例
        """
        self.pre_days = pre_days
        self.post_days = post_days
        self.reduction_ratio = reduction_ratio
        
        # 2024年宏观事件日历（简化版）
        # 实际应使用API获取
        self.events = {
            # 非农就业（每月第一个周五）
            '2024-01-05': '非农就业',
            '2024-02-02': '非农就业',
            '2024-03-08': '非农就业',
            '2024-04-05': '非农就业',
            '2024-05-03': '非农就业',
            '2024-06-07': '非农就业',
            '2024-07-05': '非农就业',
            '2024-08-02': '非农就业',
            '2024-09-06': '非农就业',
            '2024-10-04': '非农就业',
            '2024-11-01': '非农就业',
            '2024-12-06': '非农就业',
            
            # CPI数据（每月10-15日）
            '2024-01-11': 'CPI数据',
            '2024-02-13': 'CPI数据',
            '2024-03-12': 'CPI数据',
            '2024-04-11': 'CPI数据',
            '2024-05-10': 'CPI数据',
            '2024-06-12': 'CPI数据',
            '2024-07-11': 'CPI数据',
            '2024-08-09': 'CPI数据',
            '2024-09-11': 'CPI数据',
            '2024-10-11': 'CPI数据',
            '2024-11-12': 'CPI数据',
            '2024-12-10': 'CPI数据',
            
            # PPI数据（每月10-15日）
            '2024-01-12': 'PPI数据',
            '2024-02-12': 'PPI数据',
            '2024-03-12': 'PPI数据',
            '2024-04-12': 'PPI数据',
            '2024-05-10': 'PPI数据',
            '2024-06-12': 'PPI数据',
            '2024-07-12': 'PPI数据',
            '2024-08-09': 'PPI数据',
            '2024-09-09': 'PPI数据',
            '2024-10-14': 'PPI数据',
            '2024-11-11': 'PPI数据',
            '2024-12-09': 'PPI数据',
            
            # 美联储利率决议（大约每6周一次）
            '2024-01-31': '美联储利率决议',
            '2024-03-20': '美联储利率决议',
            '2024-05-01': '美联储利率决议',
            '2024-06-12': '美联储利率决议',
            '2024-07-31': '美联储利率决议',
            '2024-09-18': '美联储利率决议',
            '2024-11-06': '美联储利率决议',
            '2024-12-18': '美联储利率决议',
        }
    
    def is_event_window(self, current_date):
        """检查是否在事件窗口期"""
        current_str = current_date.strftime('%Y-%m-%d')
        current_dt = pd.to_datetime(current_str)
        
        for event_date_str, event_name in self.events.items():
            event_dt = pd.to_datetime(event_date_str)
            
            days_diff = (current_dt - event_dt).days
            
            if -self.pre_days <= days_diff <= self.post_days:
                return True, event_name, days_diff
        
        return False, None, None
    
    def get_multiplier(self, context):
        """
        获取仓位倍数
        窗口期内返回缩减后的倍数
        """
        is_window, event_name, days_diff = self.is_event_window(context.current_dt)
        
        if is_window:
            log.info(f"宏观事件期间 [{event_name}], 降低风险敞口")
            return self.reduction_ratio
        
        return 1.0
    
    def add_event(self, date_str, event_name):
        """添加事件"""
        self.events[date_str] = event_name


# 使用示例
def initialize(context):
    context.macro_filter = MacroEventFilter(
        pre_days=1,
        post_days=1,
        reduction_ratio=0.5
    )

def handle_data(context):
    # 获取仓位倍数
    multiplier = context.macro_filter.get_multiplier(context)
    
    # 检查是否有事件
    is_window, event_name, days_diff = context.macro_filter.is_event_window(context.current_dt)
    
    if is_window:
        log.info(f"当前处于 [{event_name}] 窗口期, 仓位倍数: {multiplier}")
        
        # 降低仓位
        for stock in context.portfolio.positions:
            pos = context.portfolio.positions[stock]
            order_target_value(stock, pos.value * multiplier)
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| pre_days | 1 | 事件前影响天数 |
| post_days | 1 | 事件后影响天数 |
| reduction_ratio | 0.5 | 窗口期内仓位缩减比例 |

## 适用策略

- ✅ 长线价值策略
- ✅ 全球宏观策略
- ⚠️ 短线策略（影响较小）

## 注意事项

1. 宏观事件日历需要定期更新
2. 不同事件影响程度可能不同
3. 实际应使用宏观数据API获取准确日期
