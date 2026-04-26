# 仓位管理 (Position Management)

## 概述

提供等权分配和动态仓位管理两种模式。

## 等权分配

所有持仓股票获得相同权重。

## 动态仓位

基于市场状态动态调整持仓数量。

## 代码样例

```python
# position_management.py

def equal_weight_position(context, stocks):
    """等权分配仓位"""
    if len(stocks) == 0:
        return
    
    target_value = context.portfolio.total_value / len(stocks)
    for stock in stocks:
        order_target_value(stock, target_value)


def dynamic_position(context, base_hold_num=10):
    """动态调整持仓数量"""
    # 使用状态路由器
    from state_router import StateRouter
    
    router = StateRouter()
    position_ratio, state = router.route(context)
    
    hold_num = int(base_hold_num * position_ratio)
    return max(hold_num, 0)


def volatility_adjusted_position(context, stocks, base_position=0.7):
    """波动率调整仓位"""
    # 计算组合波动率
    total_vol = 0
    for stock in stocks:
        prices = get_price(stock, end_date=context.previous_date, 
                          fields='close', count=20, panel=False)
        if prices is not None and len(prices) > 1:
            returns = prices['close'].pct_change().dropna()
            total_vol += returns.std()
    
    # 平均波动率
    avg_vol = total_vol / len(stocks) if stocks else 0
    
    # 波动率高时降低仓位
    if avg_vol > 0.03:  # 日波动率3%
        return base_position * 0.5
    elif avg_vol > 0.02:
        return base_position * 0.75
    
    return base_position


# 使用示例
def initialize(context):
    context.base_hold_num = 10

def rebalance(context):
    # 选股
    stocks = select_stocks(context)
    
    # 获取目标持仓数量
    target_num = dynamic_position(context, context.base_hold_num)
    
    # 当前持仓
    current_hold = list(context.portfolio.positions.keys())
    
    # 差额
    to_buy = [s for s in stocks if s not in current_hold][:target_num]
    to_sell = [s for s in current_hold if s not in stocks]
    
    # 执行交易
    for stock in to_sell:
        order_target_value(stock, 0)
    
    if to_buy:
        equal_weight_position(context, to_buy)
```

## 适用策略

- ✅ 所有策略通用
