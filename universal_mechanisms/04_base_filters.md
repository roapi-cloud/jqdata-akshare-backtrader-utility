# 基础股票池过滤 (Base Filters)

## 概述

所有策略通用的基础股票池过滤，排除科创板、北交所、ST、停牌、次新股等。

## 过滤条件

1. **排除科创板（68开头）**
2. **排除北交所（4、8开头）**
3. **排除ST股票**
4. **排除停牌**
5. **排除次新股（上市不足180天）**

## 代码样例

```python
from datetime import timedelta

def get_base_universe(date):
    """获取基础股票池（所有策略通用）"""
    stocks = get_all_securities("stock", date).index.tolist()
    
    # 1. 排除科创板/北交所
    stocks = [s for s in stocks if s[:2] != "68" and s[0] not in ["4", "8"]]
    
    # 2. 排除ST
    try:
        is_st = get_extras("is_st", stocks, end_date=date, count=1).iloc[-1]
        stocks = is_st[is_st == False].index.tolist()
    except:
        pass
    
    # 3. 排除停牌
    try:
        paused = get_price(stocks, end_date=date, fields="paused", count=1, panel=False)
        paused = paused.pivot(index="time", columns="code", values="paused").iloc[-1]
        stocks = paused[paused == 0].index.tolist()
    except:
        pass
    
    # 4. 排除次新股（180天）
    try:
        all_stocks = get_all_securities("stock", date)
        stocks = [s for s in stocks 
                  if date - all_stocks.loc[s, "start_date"] > timedelta(days=180)]
    except:
        pass
    
    return stocks


def filter_buyable(context, stocks):
    """过滤可买入股票"""
    current_data = get_current_data()
    buyable = []
    
    for stock in stocks:
        if stock not in current_data:
            continue
        
        cd = current_data[stock]
        if cd.paused or cd.is_st:
            continue
        
        # 排除名称含ST/*的
        if "ST" in (cd.name or "") or "*" in (cd.name or ""):
            continue
        
        # 不追涨停（开盘价接近涨停价）
        try:
            if cd.last_price >= cd.high_limit * 0.995:
                continue
        except:
            pass
        
        buyable.append(stock)
    
    return buyable


# 使用示例
def select_stocks(context):
    # 获取基础股票池
    stocks = get_base_universe(context.current_dt.date())
    
    # 过滤可买入
    stocks = filter_buyable(context, stocks)
    
    log.info(f"基础股票池过滤后剩余: {len(stocks)} 只")
    
    return stocks
```

## 适用策略

- ✅ 所有策略必须使用
