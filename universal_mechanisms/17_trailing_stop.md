# 移动止盈止损机制 (Trailing Stop Loss/Profit)

## 概述

根据持仓期间的最高价/最低价，动态调整止盈止损线。是所有持仓策略必备的风控机制。

## 机制说明

1. **跟踪持仓最高价/最低价**
2. **从高点回撤超过阈值时触发止损**
3. **移动止盈**：从高点回落一定比例止盈
4. **时间止损**：持有超过N天强制卖出

## 代码样例

```python
# trailing_stop.py
import numpy as np

class TrailingStopManager:
    """移动止盈止损管理器"""
    
    def __init__(self, stop_loss=-0.05, take_profit=0.10, 
                 trailing_stop=0.08, max_hold_days=5):
        """
        参数:
        stop_loss: 止损比例（如-0.05表示亏损5%止损）
        take_profit: 固定止盈比例
        trailing_stop: 移动止盈（从高点回落比例）
        max_hold_days: 最大持仓天数
        """
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trailing_stop = trailing_stop
        self.max_hold_days = max_hold_days
        
        # 持仓记录
        self.high_prices = {}  # stock -> highest price since entry
        self.entry_prices = {}  # stock -> entry price
        self.entry_dates = {}  # stock -> entry date
    
    def record_position(self, stock, price, date):
        """记录持仓信息"""
        self.high_prices[stock] = price
        self.entry_prices[stock] = price
        self.entry_dates[stock] = date
    
    def update_high_price(self, stock, current_price):
        """更新持仓期间最高价"""
        if stock not in self.high_prices:
            self.high_prices[stock] = current_price
        else:
            if current_price > self.high_prices[stock]:
                self.high_prices[stock] = current_price
    
    def check_stop_loss(self, stock, current_price):
        """检查止损"""
        if stock not in self.entry_prices:
            return False
        
        entry_price = self.entry_prices[stock]
        pnl_ratio = (current_price - entry_price) / entry_price
        
        if pnl_ratio <= self.stop_loss:
            return True
        return False
    
    def check_trailing_stop(self, stock, current_price):
        """检查移动止盈"""
        if stock not in self.high_prices:
            return False
        
        high_price = self.high_prices[stock]
        drawdown = (current_price - high_price) / high_price
        
        if drawdown <= -self.trailing_stop:
            return True
        return False
    
    def check_take_profit(self, stock, current_price):
        """检查固定止盈"""
        if stock not in self.entry_prices:
            return False
        
        entry_price = self.entry_prices[stock]
        pnl_ratio = (current_price - entry_price) / entry_price
        
        if pnl_ratio >= self.take_profit:
            return True
        return False
    
    def check_time_stop(self, stock, current_date):
        """检查时间止损"""
        if stock not in self.entry_dates:
            return False
        
        entry_date = self.entry_dates[stock]
        hold_days = (current_date - entry_date).days
        
        if hold_days >= self.max_hold_days:
            return True
        return False
    
    def should_close(self, stock, current_price, current_date):
        """判断是否应该平仓"""
        reasons = []
        
        if self.check_stop_loss(stock, current_price):
            reasons.append('STOP_LOSS')
        
        if self.check_trailing_stop(stock, current_price):
            reasons.append('TRAILING_STOP')
        
        if self.check_take_profit(stock, current_price):
            reasons.append('TAKE_PROFIT')
        
        if self.check_time_stop(stock, current_date):
            reasons.append('TIME_STOP')
        
        return len(reasons) > 0, reasons
    
    def remove_position(self, stock):
        """移除持仓记录"""
        self.high_prices.pop(stock, None)
        self.entry_prices.pop(stock, None)
        self.entry_dates.pop(stock, None)


# 简化版：基于持仓收益率的移动止盈止损
class SimpleStopManager:
    """简化版止盈止损"""
    
    def __init__(self, stop_loss=-0.05, take_profit=0.10, trailing_stop=0.08):
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trailing_stop = trailing_stop
    
    def should_close(self, position, current_price):
        """
        判断是否平仓
        position: context.portfolio.positions[stock]
        """
        avg_cost = position.avg_cost
        pnl_ratio = (current_price - avg_cost) / avg_cost
        
        # 止损
        if pnl_ratio <= self.stop_loss:
            return True, 'STOP_LOSS'
        
        # 止盈
        if pnl_ratio >= self.take_profit:
            return True, 'TAKE_PROFIT'
        
        # 移动止盈（从最高点回落）
        if hasattr(position, 'high_since_entry'):
            if current_price < position.high_since_entry * (1 - self.trailing_stop):
                return True, 'TRAILING_STOP'
        
        return False, None


# 使用示例
def initialize(context):
    context.trailing_stop = TrailingStopManager(
        stop_loss=-0.05,
        take_profit=0.10,
        trailing_stop=0.08,
        max_hold_days=5
    )

def handle_data(context):
    for stock in context.portfolio.positions:
        pos = context.portfolio.positions[stock]
        current_price = pos.price
        
        # 更新最高价
        context.trailing_stop.update_high_price(stock, current_price)
        
        # 检查是否应该平仓
        should_close, reasons = context.trailing_stop.should_close(
            stock, current_price, context.current_dt
        )
        
        if should_close:
            order_target_value(stock, 0)
            context.trailing_stop.remove_position(stock)
            log.info(f"{stock} 触发 {'/'.join(reasons)} 平仓")


def after_trading_end(context):
    # 清理无效持仓记录
    held_stocks = set(context.portfolio.positions.keys())
    all_stocks = set(context.trailing_stop.entry_prices.keys())
    
    for stock in all_stocks - held_stocks:
        context.trailing_stop.remove_position(stock)
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| stop_loss | -0.05 | 止损比例（-5%） |
| take_profit | 0.10 | 固定止盈（+10%） |
| trailing_stop | 0.08 | 移动止盈（从高点回落8%） |
| max_hold_days | 5 | 最大持仓天数 |

## 适用策略

- ✅ 所有持仓策略
- ✅ 短线策略（更重要）
- ✅ 趋势跟踪
- ✅ 事件驱动策略

## 注意事项

1. 止损比例需要根据策略特性调整
2. 移动止盈可以捕捉更多趋势利润
3. 时间止损可以避免久持不动
