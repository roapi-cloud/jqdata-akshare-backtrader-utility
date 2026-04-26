# F-Score / FF-Score 基本面选股机制

## 概述

F-Score是Piotroski（2000）提出的9因子财务健康评分体系，通过盈利能力、杠杆/流动性、运营效率三个维度对公司财务质量打分。在A股实测年化收益80%+，是基本面选股的经典机制。

来源：聚宽策略 `29 F_Score 选股，年化80%+.txt`，`78 ffscore选股加rsrs择时.txt`

## 9个因子详解

### 盈利能力（3项）
| 因子 | 计算 | 含义 |
|------|------|------|
| ROA | 扣非利润TTM / 总资产均值 > 0 | 资产盈利为正 |
| OCFOA | 经营现金流TTM / 总资产均值 > 0 | 现金流为正 |
| ROA_CHG | 当期ROA - 上期ROA > 0 | 盈利能力改善 |

### 杠杆/流动性（3项）
| 因子 | 计算 | 含义 |
|------|------|------|
| OCFOA_ROA | 经营现金流/总资产 - ROA > 0 | 现金流质量高于账面利润 |
| LTDR_CHG | 长期负债率变化 ≤ 0 | 杠杆未增加 |
| CR_CHG | 流动比率变化 > 0 | 短期偿债能力改善 |

### 运营效率（3项）
| 因子 | 计算 | 含义 |
|------|------|------|
| SPO | 近一年无增发 | 未稀释股东权益 |
| GPM_CHG | 毛利率变化 > 0 | 盈利质量改善 |
| TAT_CHG | 资产周转率变化 > 0 | 运营效率提升 |

## 评分规则

- 每项满足得1分，不满足得0分
- 总分0-9分
- **F-Score ≥ 8**：高质量公司，买入信号
- **F-Score ≤ 2**：低质量公司，卖出/回避信号

## 效果验证

| 策略 | 年化收益 | 最大回撤 | 说明 |
|------|---------|---------|------|
| F-Score≥8 全市场 | 80%+ | 25-30% | 聚宽回测 |
| FFScore+RSRS择时 | 40-50% | 20-25% | 加入择时后更稳 |
| F-Score沪深300 | 30-40% | 15-20% | 大盘股更稳健 |

## 适用时机

- 月度/季度调仓的中长线策略
- 与RSRS择时结合，在趋势向上时持有高F-Score股票
- 不适合短线（财务数据更新慢，季度级别）
- 适合资金量较大（>50万）的投资者

## 代码样例

```python
# fscore_selection.py
import pandas as pd
import numpy as np
from jqdata import *

class FScoreSelector:
    """F-Score基本面选股器"""
    
    def __init__(self, min_score=8, stock_pool='000300.XSHG'):
        self.min_score = min_score
        self.stock_pool = stock_pool
    
    def calculate_fscore(self, context, stock_list=None):
        """
        计算F-Score
        需要5个连续季度的财务数据
        """
        if stock_list is None:
            stock_list = get_index_stocks(self.stock_pool)
        
        date = context.previous_date
        
        # 获取5期季度财务数据
        h = get_history_fundamentals(
            stock_list,
            [
                indicator.adjusted_profit,       # 扣非利润
                balance.total_current_assets,    # 流动资产
                balance.total_assets,            # 总资产
                balance.total_current_liability, # 流动负债
                balance.total_non_current_liability,  # 长期负债
                cash_flow.net_operate_cash_flow, # 经营现金流
                income.operating_revenue,        # 营业收入
                income.operating_cost,           # 营业成本
            ],
            watch_date=date,
            count=5
        ).dropna()
        
        if len(h) == 0:
            return pd.DataFrame()
        
        # TTM计算辅助函数
        def ttm_sum(x): return x.iloc[1:].sum()
        def ttm_avg(x): return x.iloc[1:].mean()
        def pre_ttm_sum(x): return x.iloc[:-1].sum()
        def pre_ttm_avg(x): return x.iloc[:-1].mean()
        def val_1(x): return x.iloc[-1]
        def val_2(x): return x.iloc[-2] if len(x) > 1 else np.nan
        
        # 计算各指标
        profit_ttm = h.groupby('code')['adjusted_profit'].apply(ttm_sum)
        profit_pre = h.groupby('code')['adjusted_profit'].apply(pre_ttm_sum)
        assets_avg = h.groupby('code')['total_assets'].apply(ttm_avg)
        assets_pre = h.groupby('code')['total_assets'].apply(pre_ttm_avg)
        ocf_ttm = h.groupby('code')['net_operate_cash_flow'].apply(ttm_sum)
        ltdr = h.groupby('code')['total_non_current_liability'].apply(val_1) / \
               h.groupby('code')['total_assets'].apply(val_1)
        ltdr_pre = h.groupby('code')['total_non_current_liability'].apply(val_2) / \
                   h.groupby('code')['total_assets'].apply(val_2)
        cr = h.groupby('code')['total_current_assets'].apply(val_1) / \
             h.groupby('code')['total_current_liability'].apply(val_1)
        cr_pre = h.groupby('code')['total_current_assets'].apply(val_2) / \
                 h.groupby('code')['total_current_liability'].apply(val_2)
        rev_ttm = h.groupby('code')['operating_revenue'].apply(ttm_sum)
        rev_pre = h.groupby('code')['operating_revenue'].apply(pre_ttm_sum)
        cost_ttm = h.groupby('code')['operating_cost'].apply(ttm_sum)
        cost_pre = h.groupby('code')['operating_cost'].apply(pre_ttm_sum)
        
        # 计算因子
        roa = profit_ttm / assets_avg
        roa_pre = profit_pre / assets_pre
        ocfoa = ocf_ttm / assets_avg
        tat = rev_ttm / assets_avg
        tat_pre = rev_pre / assets_pre
        
        # 近一年增发检测
        one_year_ago = date - pd.Timedelta(days=365)
        spo_list = set(finance.run_query(
            query(finance.STK_CAPITAL_CHANGE.code)
            .filter(
                finance.STK_CAPITAL_CHANGE.code.in_(stock_list),
                finance.STK_CAPITAL_CHANGE.pub_date.between(one_year_ago, date),
                finance.STK_CAPITAL_CHANGE.change_reason_id == 306004  # 增发
            )
        )['code'].tolist())
        
        # 打分
        df = pd.DataFrame(index=stock_list)
        df['roa'] = (roa > 0).astype(int)
        df['ocfoa'] = (ocfoa > 0).astype(int)
        df['roa_chg'] = (roa - roa_pre > 0).astype(int)
        df['ocfoa_roa'] = (ocfoa - roa > 0).astype(int)
        df['ltdr_chg'] = (ltdr - ltdr_pre <= 0).astype(int)
        df['cr_chg'] = (cr - cr_pre > 0).astype(int)
        df['spo'] = (~df.index.isin(spo_list)).astype(int)
        df['gpm_chg'] = (cost_pre/rev_pre - cost_ttm/rev_ttm > 0).astype(int)
        df['tat_chg'] = (tat - tat_pre > 0).astype(int)
        
        df = df.dropna()
        df['fscore'] = df.sum(axis=1)
        
        return df
    
    def get_high_score_stocks(self, context, stock_list=None):
        """获取高F-Score股票"""
        df = self.calculate_fscore(context, stock_list)
        if len(df) == 0:
            return []
        
        high_score = df[df['fscore'] >= self.min_score]
        return list(high_score.index)
    
    def get_stock_list_with_timing(self, context, rsrs_signal='BUY'):
        """结合RSRS择时的选股"""
        if rsrs_signal == 'SELL':
            return []  # 择时信号为卖出时，不选股
        
        return self.get_high_score_stocks(context)


# 使用示例
def initialize(context):
    context.fscore = FScoreSelector(min_score=8, stock_pool='000300.XSHG')
    context.rsrs = RSRSIndicator(N=18, M=600)
    run_monthly(monthly_trade, 1, '09:30')

def monthly_trade(context):
    # RSRS择时
    rsrs_signal = context.rsrs.get_signal(context)
    
    if rsrs_signal == 'SELL':
        # 清仓
        for stock in context.portfolio.positions:
            order_target_value(stock, 0)
        return
    
    # F-Score选股
    stocks = context.fscore.get_high_score_stocks(context)
    stocks = stocks[:10]  # 取前10只
    
    # 调仓
    for stock in context.portfolio.positions:
        if stock not in stocks:
            order_target_value(stock, 0)
    
    if stocks:
        value = context.portfolio.total_value / len(stocks)
        for stock in stocks:
            order_target_value(stock, value)
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|-------|------|
| min_score | 8 | 最低F-Score阈值（8-9分为高质量） |
| stock_pool | 000300.XSHG | 选股范围（沪深300或全市场） |
| count | 5 | 历史季度数（至少5期） |

## 与其他机制组合

```
F-Score选股 + RSRS择时（推荐组合）：
- RSRS > 0.7：持有高F-Score股票
- RSRS < -0.7：清仓等待
- 月度调仓，持仓5-10只
```

## 2026-04-03 补充：A股应优先关注 FFScore 本土化版本

来自 `QuantsPlaybook/A-量化基本面/华泰FFScore` 的补充结论是：原始 `Piotroski F-Score` 在 A 股未必显著跑赢低 `PB` 基准，更值得重视的是中国化 `Five_FScore` 路线。

### 中国版 FFScore

`Five_FScore = ROE + ΔROE + ΔCATURN + ΔTURN + ΔLEVER`

含义：
- 用 `ROE` 代替部分 `ROA` 视角，更贴近 A 股报表习惯
- 强调资本周转、资产周转与杠杆改善
- 更适合与 `PB`、红利、质量过滤组合

### 使用建议

- 海外/经典框架复现：保留 `F-Score`
- A股中低频主仓：优先测试 `FFScore + PB + 状态路由`
- 指数增强：把 `FFScore/质量分数` 作为目标权重生成层，而不是只做二元筛股

## 与指数增强底座的结合方式

`F-Score / FFScore` 更适合作为指数增强底座的 `alpha` 选股层：

1. 基础股票池：`04_base_filters`
2. 因子评分：`F-Score / FFScore / 高股息质量`
3. 状态过滤：`03_state_router` / `08_rsrs_timing`
4. 权重生成：目标权重表、`25_epo_portfolio`
5. 月度执行：`31_index_enhancement_base`

这比“单独拿 F-Score 全仓硬做”更接近低频高确定性的主仓架构。

## 适用策略

- ✅ 中长线基本面选股（月度调仓）
- ✅ 沪深300/中证500指数增强
- ✅ 与RSRS择时结合（FFScore+RSRS）
- ✅ 低频主仓的 alpha 选股层
- ⚠️ 不适合小市值策略（财务数据质量差）
- ⚠️ 不适合高频交易

## 待调研方向

1. **RFScore变体**：将F-Score中的ROA替换为ROE，并加入PB因子
2. **动态权重**：不同市场环境下各因子权重不同
3. **行业中性化**：在行业内部排名，避免行业偏差
4. **结合成长因子**：F-Score + 营收增长率，筛选"质量+成长"双优股票
