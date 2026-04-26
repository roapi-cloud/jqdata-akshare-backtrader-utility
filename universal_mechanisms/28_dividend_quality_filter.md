# 高股息质量过滤机制 (Dividend Quality Filter)

## 概述

通过近3年累计分红股息率筛选高质量分红股，结合PEG、PE、ROE等基本面指标过滤，构建"高股息+低估值+高成长"的价值投资股票池。

来源：聚宽策略 `04 高股息低市盈率高增长的价投策略.txt`，`35 菜场大妈股息率小市值策略.txt`，`04 红利搬砖，年化29%.txt`

## 核心逻辑

```
筛选流程：
1. 计算近3年累计分红/总市值 → 股息率排名前10%
2. PE在0-25之间（低估值）
3. PEG在0.08-1.9之间（合理成长）
4. ROE > 3%（盈利能力）
5. 营收增长率 > 5%（成长性）
6. 净利润增长率 > 11%（利润成长）
```

## 效果验证

| 策略 | 年化收益 | 最大回撤 | 说明 |
|------|---------|---------|------|
| 菜场大妈股息率小市值 | ~70% | 20-25% | 10年206倍 |
| 高股息低PE高增长 | 30-40% | 15-20% | 稳健型 |
| 红利搬砖 | 29% | 20% | 年度调仓 |

## 适用时机

- 熊市/震荡市中的防御性配置（高股息提供安全垫）
- 年报季后（4月）调仓，利用最新分红数据
- 与小市值因子结合，兼顾成长与分红
- 不适合牛市初期（成长股表现更好）

## 代码样例

```python
# dividend_quality_filter.py
import pandas as pd
import datetime
from jqdata import *

class DividendQualityFilter:
    """高股息质量过滤器"""
    
    def __init__(self, 
                 dividend_years=3,
                 dividend_top_pct=0.1,
                 pe_max=25,
                 peg_min=0.08,
                 peg_max=1.9,
                 roe_min=3,
                 revenue_growth_min=5,
                 profit_growth_min=11):
        self.dividend_years = dividend_years
        self.dividend_top_pct = dividend_top_pct
        self.pe_max = pe_max
        self.peg_min = peg_min
        self.peg_max = peg_max
        self.roe_min = roe_min
        self.revenue_growth_min = revenue_growth_min
        self.profit_growth_min = profit_growth_min
    
    def get_dividend_ratio(self, context, stock_list):
        """
        计算近N年累计分红股息率
        股息率 = 近N年累计分红金额 / 当前总市值
        """
        time1 = context.previous_date
        time0 = time1 - datetime.timedelta(days=365 * self.dividend_years)
        
        # 分批查询（避免超过4000行限制）
        interval = 1000
        list_len = len(stock_list)
        
        df = finance.run_query(
            query(finance.STK_XR_XD.code,
                  finance.STK_XR_XD.a_registration_date,
                  finance.STK_XR_XD.bonus_amount_rmb)
            .filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)])
            )
        )
        
        # 分批追加
        for i in range(list_len // interval):
            start = interval * (i + 1)
            end = min(list_len, interval * (i + 2))
            temp = finance.run_query(
                query(finance.STK_XR_XD.code,
                      finance.STK_XR_XD.a_registration_date,
                      finance.STK_XR_XD.bonus_amount_rmb)
                .filter(
                    finance.STK_XR_XD.a_registration_date >= time0,
                    finance.STK_XR_XD.a_registration_date <= time1,
                    finance.STK_XR_XD.code.in_(stock_list[start:end])
                )
            )
            df = pd.concat([df, temp])
        
        dividend = df.fillna(0).groupby('code').sum()
        
        # 获取总市值
        q = query(valuation.code, valuation.market_cap).filter(
            valuation.code.in_(list(dividend.index))
        )
        cap = get_fundamentals(q, date=time1).set_index('code')
        
        # 计算股息率
        cap['dividend_ratio'] = (dividend['bonus_amount_rmb'] / 10000) / cap['market_cap']
        cap = cap.sort_values('dividend_ratio', ascending=False)
        
        # 取前N%
        n = int(len(cap) * self.dividend_top_pct)
        return list(cap.index[:n])
    
    def apply_fundamental_filter(self, context, stock_list):
        """应用基本面过滤条件"""
        df = get_fundamentals(
            query(
                valuation.code,
                valuation.circulating_market_cap,
                valuation.pe_ratio,
            ).filter(
                valuation.code.in_(stock_list),
                valuation.pe_ratio.between(0, self.pe_max),
                indicator.inc_return > self.roe_min,
                indicator.inc_total_revenue_year_on_year > self.revenue_growth_min,
                indicator.inc_net_profit_year_on_year > self.profit_growth_min,
                # PEG = PE / 净利润增长率
                valuation.pe_ratio / indicator.inc_net_profit_year_on_year > self.peg_min,
                valuation.pe_ratio / indicator.inc_net_profit_year_on_year < self.peg_max,
            )
        )
        return list(df.code)
    
    def get_stock_list(self, context, universe=None):
        """
        获取高股息质量股票池
        
        参数:
        universe: 初始股票池（None则使用全市场）
        """
        if universe is None:
            universe = get_all_securities('stock', context.previous_date).index.tolist()
        
        # 基础过滤
        current_data = get_current_data()
        universe = [s for s in universe
                   if not current_data[s].is_st
                   and not current_data[s].paused
                   and s[:2] not in ['68']
                   and s[0] not in ['4', '8']
                   and (context.previous_date - get_security_info(s).start_date).days > 300]
        
        # 步骤1：股息率筛选
        dividend_stocks = self.get_dividend_ratio(context, universe)
        
        if not dividend_stocks:
            return []
        
        # 步骤2：基本面过滤
        quality_stocks = self.apply_fundamental_filter(context, dividend_stocks)
        
        return quality_stocks
    
    def get_sorted_by_market_cap(self, context, stock_list, ascending=True):
        """按市值排序"""
        if not stock_list:
            return []
        q = query(valuation.code, valuation.circulating_market_cap).filter(
            valuation.code.in_(stock_list)
        ).order_by(
            valuation.circulating_market_cap.asc() if ascending
            else valuation.circulating_market_cap.desc()
        )
        df = get_fundamentals(q)
        return list(df.code)


# 使用示例（月度调仓）
def initialize(context):
    context.div_filter = DividendQualityFilter(
        dividend_years=3,
        dividend_top_pct=0.1,   # 股息率前10%
        pe_max=25,
        peg_min=0.08,
        peg_max=1.9,
        roe_min=3,
        revenue_growth_min=5,
        profit_growth_min=11
    )
    
    g.stock_num = 10
    g.month = -1
    
    run_daily(handle_data, time='09:30')

def handle_data(context):
    # 月度调仓
    if context.current_dt.month == g.month:
        return
    g.month = context.current_dt.month
    
    # 获取股票池
    stocks = context.div_filter.get_stock_list(context)
    
    # 按市值排序（小市值优先）
    stocks = context.div_filter.get_sorted_by_market_cap(context, stocks, ascending=True)
    stocks = stocks[:g.stock_num]
    
    if not stocks:
        return
    
    # 调仓
    for s in list(context.portfolio.positions.keys()):
        if s not in stocks:
            order_target_value(s, 0)
    
    value = context.portfolio.total_value / len(stocks)
    for s in stocks:
        order_target_value(s, value)
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| dividend_years | 3 | 统计分红的年数 |
| dividend_top_pct | 0.1 | 股息率前N%（10%） |
| pe_max | 25 | 最大PE |
| peg_min/max | 0.08/1.9 | PEG范围 |
| roe_min | 3 | 最低ROE（%） |
| revenue_growth_min | 5 | 最低营收增长率（%） |
| profit_growth_min | 11 | 最低净利润增长率（%） |

## 策略变体

| 变体 | 调整 | 适用场景 |
|------|------|---------|
| 纯高股息 | 只用股息率筛选，去掉成长条件 | 熊市防御 |
| 高股息+小市值 | 加入市值排序，取最小市值 | 进攻型 |
| 高股息+大市值 | 取最大市值，去掉成长条件 | 稳健型 |
| 红利搬砖 | 只取股息率最高1只，年度调仓 | 极简版 |

## 适用策略

- ✅ 价值投资中长线策略（月度/季度调仓）
- ✅ 熊市/震荡市防御配置
- ✅ 与小市值因子结合（菜场大妈策略）
- ✅ 与RSRS择时结合（熊市空仓）
- ⚠️ 不适合牛市初期（成长股更强）
- ⚠️ 4月份需注意年报季风险

## 待调研方向

1. **股息率预测**：用历史分红趋势预测未来股息率
2. **股息稳定性**：筛选连续N年分红的股票
3. **股息增长率**：优先选择股息持续增长的公司
4. **行业中性化**：在行业内部排名，避免集中在银行/地产
