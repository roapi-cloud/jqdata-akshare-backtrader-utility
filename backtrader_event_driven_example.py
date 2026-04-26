"""
事件驱动调仓示例策略

核心思路：
- 保留定时调仓（每20个交易日），作为兜底
- 增加事件触发：财报发布、技术信号、自定义条件
- 任意事件触发都会立即调仓，不等定时周期

事件类型：
1. FinancialReportTrigger  - 持仓股发财报时触发
2. TechnicalSignalTrigger  - 技术信号触发（均线交叉、放量等）
3. CustomTrigger           - 自定义条件触发（暴跌、涨幅过大等）
"""

import backtrader as bt
import pandas as pd
from backtrader_base_strategy import (
    JQ2BTBaseStrategy,
    FinancialReportTrigger,
    TechnicalSignalTrigger,
    CustomTrigger,
    format_stock_symbol_for_akshare,
    get_akshare_stock_data,
)


class EventDrivenStrategy(JQ2BTBaseStrategy):
    params = (
        ("stocknum", 4),
        ("rebalance_days", 20),  # 定时调仓周期
        ("printlog", True),
    )

    def __init__(self):
        super().__init__()
        self.last_rebalance = None
        self.selected_stocks = []
        self.rebalance_count = 0
        self.event_rebalance_count = 0

        # ========== 注册事件触发器 ==========

        # 1. 财报发布事件：监控持仓股的财报
        self.add_trigger(
            FinancialReportTrigger(
                stock_codes=None,  # None = 自动监控所有持仓股
                report_types=["q1", "q2", "q3", "annual"],
                check_interval=5,  # 每5个交易日检查一次财报
                name="持仓股财报发布",
            ).set_cooldown(3)
        )  # 触发后3天内不再触发

        # 2. 技术信号：沪深300指数5日均线上穿20日均线（看多信号）
        self.add_trigger(
            TechnicalSignalTrigger(
                signal_type="ma_cross",
                stock_code="sh000300",  # 用沪深300判断大势
                fast_period=5,
                slow_period=20,
                direction="up",
                name="沪深300金叉",
            ).set_cooldown(5)
        )

        # 3. 技术信号：大盘放量（成交量是20日均量的2倍）
        self.add_trigger(
            TechnicalSignalTrigger(
                signal_type="volume_spike",
                stock_code="sh000300",
                volume_ratio=2.0,
                name="大盘放量",
            ).set_cooldown(5)
        )

        # 4. 自定义事件：大盘单日跌幅超3%（暴跌信号）
        self.add_trigger(
            CustomTrigger(
                condition=lambda s, dt: (
                    len(s.datas[0]) >= 2
                    and s.datas[0].close[0] < s.datas[0].close[-1] * 0.97
                ),
                name="大盘暴跌3%",
            ).set_cooldown(5)
        )

        # 5. 自定义事件：大盘RSI超买
        self.add_trigger(
            TechnicalSignalTrigger(
                signal_type="rsi_overbought", stock_code="sh000300", name="大盘RSI超买"
            ).set_cooldown(10)
        )

        # ========== 注册事件处理函数 ==========
        # 所有事件触发时都调用 rebalance
        self.on_event(self._on_any_event)

    def _on_any_event(self, context, dt, trigger_name):
        """事件触发时的调仓逻辑"""
        context.log(f"[事件调仓] 触发原因: {trigger_name}")
        context.event_rebalance_count += 1
        context.rebalance_portfolio(dt, reason=f"事件:{trigger_name}")

    def next(self):
        # 定时调仓逻辑（保留原有的机械调仓作为兜底）
        dt = self.datas[0].datetime.date(0)
        if (
            self.last_rebalance is None
            or (dt - self.last_rebalance).days >= self.p.rebalance_days
        ):
            self.last_rebalance = dt
            self.rebalance_count += 1
            self.rebalance_portfolio(dt, reason="定时")

        # 调用父类（会自动检查事件触发器）
        super().next()

    def rebalance_portfolio(self, dt, reason="定时"):
        """调仓逻辑"""
        self.log(
            f"[{dt}] 调仓(第{self.rebalance_count}次定时+第{self.event_rebalance_count}次事件)，原因: {reason}"
        )

        # 选股逻辑（这里简化演示，实际应该用多因子打分）
        stock_pool = [
            "sh600519",
            "sh600036",
            "sz000333",
            "sz000651",
            "sh601318",
            "sh600276",
            "sh600104",
            "sz000858",
        ]
        selected = stock_pool[: self.p.stocknum]
        self.selected_stocks = selected
        self.log(f"选股结果: {selected}")

        # 调仓：卖出不在列表中的，买入/调整到目标权重
        for data in self.datas:
            if data._name not in selected:
                self.order_target_percent(data, 0)
        for data in self.datas:
            if data._name in selected:
                self.order_target_percent(data, 1.0 / self.p.stocknum)

    def stop(self):
        self.log(f"定时调仓次数: {self.rebalance_count}")
        self.log(f"事件调仓次数: {self.event_rebalance_count}")
        self.log(f"事件日志: {self.get_event_log()}")
        super().stop()


if __name__ == "__main__":
    STOCK_POOL = {
        "sh600519": "贵州茅台",
        "sh600036": "招商银行",
        "sz000333": "美的集团",
        "sz000651": "格力电器",
        "sh601318": "中国平安",
        "sh600276": "恒瑞医药",
        "sh600104": "上汽集团",
        "sz000858": "五粮液",
        "sh000300": "沪深300",  # 加入指数用于技术信号判断
    }
    start_date = "2020-01-01"
    end_date = "2022-12-31"

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(1000000)
    cerebro.broker.setcommission(commission=0.0002)
    cerebro.broker.set_slippage_perc(perc=0.000)

    for symbol in STOCK_POOL.keys():
        data = get_akshare_stock_data(symbol, start_date, end_date)
        cerebro.adddata(data, name=symbol)

    cerebro.addstrategy(EventDrivenStrategy)
    print("Starting Portfolio Value: %.2f" % cerebro.broker.getvalue())
    results = cerebro.run()
    print("Final Portfolio Value: %.2f" % cerebro.broker.getvalue())
