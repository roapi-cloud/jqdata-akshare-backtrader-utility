"""
Backtrader 运行底座
==================

让一个新策略只要给出信号/目标权重，就能尽快跑起来，
而不必重新搭 Cerebro、佣金、datafeed、订单记录、context 兼容层。

快速开始
--------
```python
from strategy_kits.execution.backtrader_runtime import run_backtest, BacktraderConfig
from strategy_kits.execution.backtrader_runtime.compat import JQ2BTBaseStrategy

class MyStrategy(JQ2BTBaseStrategy):
    def initialize(self, context):
        context.run_daily(self.trade, time='14:50')

    def trade(self, context):
        # 你的交易逻辑
        context.order_target_value('000001.XSHE', 100000)

config = BacktraderConfig(
    start_date='2020-01-01',
    end_date='2023-12-31',
    symbols=['000001.XSHE', '600519.XSHG'],
    initial_cash=1_000_000
)

result = run_backtest(config, MyStrategy)
```

架构层次
--------
- config     : 配置对象（回测参数、佣金、滑点等）
- runtime    : 运行时（Cerebro组装、数据加载、执行）
- compat     : 兼容层（聚宽风格API、下单封装、context）
- datafeed   : 数据源适配（AkShare等）
- analyzers  : 分析器（交易记录、绩效统计）
"""

from .config import BacktraderConfig, CommissionConfig, SlippageConfig
from .runtime import run_backtest, load_datafeeds, build_broker, build_analyzers
from .analyzers import TradeRecordAnalyzer, PerformanceAnalyzer
from .timer_manager import TimerManager
from .timer_rules import TradingDayCalendar, parse_time_rule, should_execute_timer

__version__ = "0.1.0"
__all__ = [
    # 配置
    "BacktraderConfig",
    "CommissionConfig",
    "SlippageConfig",
    # 运行时
    "run_backtest",
    "load_datafeeds",
    "build_broker",
    "build_analyzers",
    # 分析器
    "TradeRecordAnalyzer",
    "PerformanceAnalyzer",
    # 定时器
    "TimerManager",
    "TradingDayCalendar",
    "parse_time_rule",
    "should_execute_timer",
]
