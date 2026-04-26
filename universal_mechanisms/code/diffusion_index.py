# 扩散指数双均线择时
# 来源：聚宽策略 37 微盘股扩散指数双均线择时.txt
# 文档：docs/universal_mechanisms/26_diffusion_index_timing.md

import numpy as np
import talib
from jqdata import *


class DiffusionIndexTimer:
    """
    扩散指数双均线择时
    KS = 过去N天内收盘价高于开盘价的股票占比
    EMA6(KS) < EMA28(KS) → 空头，清仓
    """

    def __init__(self, index='000852.XSHG', watch_day=20,
                 fast_period=6, slow_period=28, history_days=40):
        self.index = index
        self.watch_day = watch_day
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.history_days = history_days

    def calculate_ks_series(self, context):
        """计算扩散指数历史序列"""
        yesterday = context.previous_date
        dates = get_trade_days(end_date=yesterday, count=self.history_days)

        ks_series = []
        for date in dates:
            try:
                stocks = get_index_stocks(self.index, date=date)
                df = get_price(
                    stocks, end_date=date,
                    fields=['close', 'open'],
                    count=self.watch_day,
                    fill_paused=False, skip_paused=False,
                    panel=False
                ).dropna()

                end_price = df.groupby('code')['close'].last()
                open_price = df.groupby('code')['open'].first()
                result = end_price - open_price
                ks = len(result[result > 0]) / max(len(result), 1)
                ks_series.append(ks)
            except Exception:
                ks_series.append(0.5)

        return np.array(ks_series)

    def get_timing_signal(self, context):
        """
        获取择时信号
        返回: (should_clear: bool, detail: dict)
        should_clear=True 表示应该清仓
        """
        ks_series = self.calculate_ks_series(context)

        if len(ks_series) < self.slow_period + 5:
            return False, {'error': '数据不足'}

        ema_fast = talib.EMA(ks_series, self.fast_period)
        ema_slow = talib.EMA(ks_series, self.slow_period)

        should_clear = bool(ema_fast[-1] < ema_slow[-1])

        detail = {
            'ks_latest': float(ks_series[-1]),
            'ema_fast': float(ema_fast[-1]),
            'ema_slow': float(ema_slow[-1]),
            'signal': '空头清仓' if should_clear else '多头持仓'
        }

        return should_clear, detail
