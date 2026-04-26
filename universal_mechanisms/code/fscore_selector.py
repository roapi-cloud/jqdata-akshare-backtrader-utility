# F-Score / FF-Score 基本面选股器
# 来源：聚宽策略 29 F_Score 选股，年化80%+.txt
# 文档：docs/universal_mechanisms/24_fscore_selection.md

import pandas as pd
import numpy as np
from jqdata import *


class FScoreSelector:
    """
    F-Score基本面选股器
    9因子财务健康评分，≥8分为高质量公司
    """

    def __init__(self, min_score=8, stock_pool='000300.XSHG'):
        self.min_score = min_score
        self.stock_pool = stock_pool

    def calculate_fscore(self, context, stock_list=None):
        """计算F-Score，返回含fscore列的DataFrame"""
        if stock_list is None:
            stock_list = get_index_stocks(self.stock_pool)

        date = context.previous_date

        h = get_history_fundamentals(
            stock_list,
            [
                indicator.adjusted_profit,
                balance.total_current_assets,
                balance.total_assets,
                balance.total_current_liability,
                balance.total_non_current_liability,
                cash_flow.net_operate_cash_flow,
                income.operating_revenue,
                income.operating_cost,
            ],
            watch_date=date,
            count=5
        ).dropna()

        if len(h) == 0:
            return pd.DataFrame()

        def ttm_sum(x): return x.iloc[1:].sum()
        def ttm_avg(x): return x.iloc[1:].mean()
        def pre_ttm_sum(x): return x.iloc[:-1].sum()
        def pre_ttm_avg(x): return x.iloc[:-1].mean()
        def val_1(x): return x.iloc[-1]
        def val_2(x): return x.iloc[-2] if len(x) > 1 else np.nan

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

        roa = profit_ttm / assets_avg
        roa_pre = profit_pre / assets_pre
        ocfoa = ocf_ttm / assets_avg
        tat = rev_ttm / assets_avg
        tat_pre = rev_pre / assets_pre

        one_year_ago = date - pd.Timedelta(days=365)
        spo_list = set(finance.run_query(
            query(finance.STK_CAPITAL_CHANGE.code)
            .filter(
                finance.STK_CAPITAL_CHANGE.code.in_(stock_list),
                finance.STK_CAPITAL_CHANGE.pub_date.between(one_year_ago, date),
                finance.STK_CAPITAL_CHANGE.change_reason_id == 306004
            )
        )['code'].tolist())

        df = pd.DataFrame(index=stock_list)
        df['roa'] = (roa > 0).astype(int)
        df['ocfoa'] = (ocfoa > 0).astype(int)
        df['roa_chg'] = (roa - roa_pre > 0).astype(int)
        df['ocfoa_roa'] = (ocfoa - roa > 0).astype(int)
        df['ltdr_chg'] = (ltdr - ltdr_pre <= 0).astype(int)
        df['cr_chg'] = (cr - cr_pre > 0).astype(int)
        df['spo'] = (~df.index.isin(spo_list)).astype(int)
        df['gpm_chg'] = (cost_pre / rev_pre - cost_ttm / rev_ttm > 0).astype(int)
        df['tat_chg'] = (tat - tat_pre > 0).astype(int)

        df = df.dropna()
        df['fscore'] = df[['roa', 'ocfoa', 'roa_chg', 'ocfoa_roa',
                            'ltdr_chg', 'cr_chg', 'spo', 'gpm_chg', 'tat_chg']].sum(axis=1)
        return df

    def get_high_score_stocks(self, context, stock_list=None):
        """获取F-Score >= min_score的股票列表"""
        df = self.calculate_fscore(context, stock_list)
        if len(df) == 0:
            return []
        return list(df[df['fscore'] >= self.min_score].index)
