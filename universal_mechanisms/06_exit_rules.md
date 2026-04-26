# 卖出规则模板 (Exit Rules)

## 概述

提供时间退出、止盈止损退出等通用卖出规则模板。

## 时间退出

持有N天后卖出，适用于短线策略。

## 止盈止损退出

根据盈亏比例触发卖出。

## 代码样例

```python
# exit_rules.py

def time_based_exit(context, hold_period_days=1):
    """持有N天后卖出"""
    for stock in context.portfolio.positions:
        pos = context.portfolio.positions[stock]
        if (context.current_dt.date() - pos.transact_time.date()).days >= hold_period_days:
            order_target_value(stock, 0)


def stop_loss_take_profit(context, stop_loss=-0.05, take_profit=0.10):
    """止损止盈"""
    for stock in context.portfolio.positions:
        pos = context.portfolio.positions[stock]
        pnl = pos.price / pos.avg_cost - 1
        
        if pnl <= stop_loss or pnl >= take_profit:
            order_target_value(stock, 0)


def trailing_stop_loss(context, trailing_ratio=0.08):
    """移动止盈止损"""
    for stock in context.portfolio.positions:
        pos = context.portfolio.positions[stock]
        
        # 计算从最高点回撤
        if hasattr(pos, 'high_since_entry'):
            drawdown = (pos.price - pos.high_since_entry) / pos.high_since_entry
            if drawdown <= -trailing_ratio:
                order_target_value(stock, 0)


def combination_exit(context, hold_days=1, stop_loss=-0.05, take_profit=0.10):
    """组合退出条件"""
    for stock in context.portfolio.positions:
        pos = context.portfolio.positions[stock]
        
        # 时间退出
        hold_days_passed = (context.current_dt.date() - pos.transact_time.date()).days
        if hold_days_passed >= hold_days:
            order_target_value(stock, 0)
            continue
        
        # 止损止盈
        pnl = pos.price / pos.avg_cost - 1
        if pnl <= stop_loss or pnl >= take_profit:
            order_target_value(stock, 0)


# 使用示例
def initialize(context):
    # 设置止损止盈参数
    context.stop_loss = -0.05
    context.take_profit = 0.10
    context.hold_days = 1

def handle_data(context):
    # 时间退出
    time_based_exit(context, hold_period_days=context.hold_days)
    
    # 止损止盈
    stop_loss_take_profit(context, 
                          stop_loss=context.stop_loss, 
                          take_profit=context.take_profit)


# ATR止损止盈（更动态）
def atr_stop_loss(context, atr_multiplier=2):
    """基于ATR的动态止损"""
    from volatility_position import VolatilityPositionManager
    
    vol_mgr = VolatilityPositionManager(atr_period=20)
    
    for stock in context.portfolio.positions:
        pos = context.portfolio.positions[stock]
        
        atr = vol_mgr.calculate_atr(stock, context.previous_date)
        if atr is None:
            continue
        
        # ATR止损
        entry_price = pos.avg_cost
        stop_price = entry_price - atr_multiplier * atr
        
        if pos.price <= stop_price:
            order_target_value(stock, 0)
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| hold_days | 1 | 持有天数 |
| stop_loss | -0.05 | 止损比例（-5%） |
| take_profit | 0.10 | 止盈比例（+10%） |
| trailing_ratio | 0.08 | 移动止盈回撤比例 |
| atr_multiplier | 2 | ATR止损倍数 |

## 适用策略

- ✅ 所有策略可配置
