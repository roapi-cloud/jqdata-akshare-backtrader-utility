"""
聚宽风格兼容层 (JQ Compatibility Layer)
=======================================

提供聚宽（JoinQuant）风格的 API 兼容，让原本为聚宽编写的策略
可以几乎无缝地迁移到本地 Backtrader 环境。

核心兼容特性：
- context 对象（current_dt, portfolio, g）
- run_daily 定时任务
- order_value / order_target / order_target_value 下单 API
- 全局变量 g 对象
"""

import backtrader as bt
from types import SimpleNamespace
from typing import Dict, List, Callable, Optional, Any, Union
import pandas as pd
import math

from ..data_gateways.symbol import to_ak, to_jq, to_qlib, to_ts
from .timer_manager import TimerManager


def _symbol_aliases(code: Any) -> set[str]:
    """Generate comparable aliases for robust symbol matching."""
    if code is None:
        return set()

    raw = str(code).strip()
    if not raw:
        return set()

    aliases = {raw, raw.lower(), raw.upper()}

    dot_base = raw.split(".", 1)[0]
    if dot_base.isdigit():
        aliases.add(dot_base.zfill(6))
        aliases.add(dot_base[-6:])

    try:
        jq = to_jq(raw)
        aliases.update({jq, jq.lower(), jq.upper()})

        bare = jq.split(".", 1)[0]
        aliases.add(bare)
        aliases.add(bare.zfill(6))

        ak = to_ak(raw)
        ts = to_ts(raw)
        qlib = to_qlib(raw)
        aliases.update({ak, ak.lower(), ak.upper(), ts, ts.lower(), ts.upper(), qlib, qlib.lower(), qlib.upper()})
    except Exception:
        # Keep raw aliases only when symbol normalization fails.
        pass

    return {x for x in aliases if x}


class PortfolioCompat:
    """
    兼容聚宽 context.portfolio 风格

    提供与聚宽 portfolio 一致的属性访问：
    - positions: 持仓字典
    - cash: 可用现金
    - available_cash: 可用现金（同 cash）
    - total_value: 总资产
    - positions_value: 持仓市值
    """

    def __init__(self, strategy: bt.Strategy):
        self._strategy = strategy

    @property
    def positions(self) -> Dict[str, bt.Position]:
        """返回持仓字典: {code -> Position对象}"""
        pos = {}
        for data in self._strategy.datas:
            position = self._strategy.getposition(data)
            if position.size != 0:
                pos[data._name] = position
        return pos

    @property
    def cash(self) -> float:
        """可用现金"""
        return self._strategy.broker.getcash()

    @property
    def available_cash(self) -> float:
        """可用现金（与 cash 相同）"""
        return self.cash

    @property
    def total_value(self) -> float:
        """总资产"""
        return self._strategy.broker.getvalue()

    @property
    def positions_value(self) -> float:
        """持仓市值"""
        return sum(p.size * p.price for p in self.positions.values())

    def __repr__(self):
        return (f"PortfolioCompat(cash={self.cash:.2f}, "
                f"total_value={self.total_value:.2f}, "
                f"positions={len(self.positions)})")


class JQ2BTBaseStrategy(bt.Strategy):
    """
    聚宽风格策略基类

    提供聚宽风格的策略编写体验：
    1. context 对象兼容（current_dt, portfolio, g, run_daily）
    2. 定时任务注册（run_daily）
    3. 下单 API 兼容（order_value, order_target, order_target_value）
    4. 日志记录（自动按日期、类型分类）

    使用方法：
        ```python
        class MyStrategy(JQ2BTBaseStrategy):
            def initialize(self, context):
                # 初始化逻辑
                context.g.my_param = 0.5
                context.run_daily(self.trade, time='14:50')

            def trade(self, context):
                # 每日交易逻辑
                context.order_target_value('000001.XSHE', 100000)
        ```
    """

    params = (
        ("printlog", True),
        ("log_dir", "./logs"),
    )

    def __init__(self):
        super().__init__()
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.navs: List[float] = []

        # 创建日志目录
        import os
        os.makedirs(self.params.log_dir, exist_ok=True)

        # 日志文件
        self._trade_log = open(
            os.path.join(self.params.log_dir, "trade_log.txt"),
            "w", encoding="utf-8"
        )
        self._position_log = open(
            os.path.join(self.params.log_dir, "position_log.txt"),
            "w", encoding="utf-8"
        )

        # 聚宽风格全局变量 g
        self.g = SimpleNamespace()

        # 聚宽风格定时器
        self.timer_manager = TimerManager(self)

        # 状态跟踪
        self._bar_count = 0
        self._last_date = None

        # context 兼容层
        self.context = self
        self.current_dt: Optional[pd.Timestamp] = None
        self.previous_date: Optional[pd.Timestamp] = None
        self.portfolio = PortfolioCompat(self)

    def initialize(self, context):
        """
        策略初始化入口（子类重写）

        Args:
            context: 策略上下文对象（即 self）
        """
        pass

    def log(self, txt: str, dt=None, log_type: str = 'info'):
        """
        日志记录

        Args:
            txt: 日志内容
            dt: 日期，默认为当前 bar 日期
            log_type: 日志类型 ('info', 'trade', 'position')
        """
        if not self.params.printlog and log_type == 'info':
            return

        dt = dt or self.datas[0].datetime.date(0)
        line = f'{dt.isoformat()}, {txt}\n'

        if log_type == 'trade':
            self._trade_log.write(line)
        elif log_type == 'position':
            self._position_log.write(line)
        else:
            print(line, end='')

    def notify_order(self, order: bt.Order):
        """订单状态回调"""
        if order.status in [order.Completed]:
            self.log(
                f'ORDER EXECUTED, {order.data._name}, '
                f'{order.executed.price:.2f}, Size: {order.executed.size}',
                log_type='trade'
            )
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(
                f'ORDER FAILED, {order.data._name}, '
                f'Status: {order.Status[order.status]}',
                log_type='trade'
            )

    def notify_trade(self, trade: bt.Trade):
        """交易完成回调"""
        if not trade.isclosed:
            return
        self.log(
            f'TRADE PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}',
            log_type='trade'
        )

    # ====== 定时任务 API ======

    def run_daily(self, func: Callable, time: Optional[str] = None):
        """
        注册定时任务

        支持的时间格式：
        - '14:50'     : 具体时间（24小时制）
        - 'before_open': 开盘前（第一个 bar）
        - 'after_close': 收盘后（最后一个 bar）
        - 'every_bar'  : 每个 bar
        - None        : 每个 bar（默认）

        Args:
            func: 要执行的函数，接收 context 参数
            time: 执行时间标识
        """
        if time in (None, "every_bar"):
            self.timer_manager.register(func, frequency="every_bar", time_rule="every_bar")
        else:
            self.timer_manager.register(func, frequency="daily", time_rule=time)

    def run_weekly(self, func: Callable, weekday: int = 1, time: str = "open"):
        """Register a weekly callback using JoinQuant-style weekday semantics."""
        self.timer_manager.register(
            func,
            frequency="weekly",
            time_rule=time,
            weekday=weekday,
        )

    def run_monthly(self, func: Callable, day: int = 1, time: str = "before_open"):
        """Register a monthly callback using the Nth trading day of month."""
        self.timer_manager.register(
            func,
            frequency="monthly",
            time_rule=time,
            day=day,
        )

    def next(self):
        """主循环（每个 bar 调用）"""
        # 记录净值
        self.navs.append(self.broker.getvalue())
        self._bar_count += 1

        # 更新 context 时间
        dt = self.datas[0].datetime.date(0)
        dt_time = self.datas[0].datetime.datetime(0)
        self.previous_date = getattr(self, 'current_dt', None)
        self.current_dt = dt_time
        self.context = self

        # 统计今日 bar 数（支持分钟级数据）
        if not hasattr(self, '_bars_today') or self._last_date != dt:
            self._bars_today = []
            self._last_date = dt
        self._bars_today.append(self._bar_count)

        # 首次初始化
        if self._bar_count == 1:
            self.initialize(self.context)

        # 执行定时任务
        self.timer_manager.check_and_execute()

    def stop(self):
        """策略结束回调"""
        self._trade_log.close()
        self._position_log.close()

        # 保存净值序列
        import os
        pd.Series(self.navs).to_csv(
            os.path.join(self.params.log_dir, "strategy_nav.csv"),
            index=False
        )

    # ====== 下单 API（聚宽风格） ======

    def order_value(self, code: Union[str, bt.DataBase], value: float) -> Optional[bt.Order]:
        """
        按指定金额下单

        Args:
            code: 股票代码或 data 对象
            value: 金额（正数买入，负数卖出）

        Returns:
            Order 对象或 None
        """
        data = self._find_data(code)
        price = data.close[0]
        if price == 0 or math.isnan(price):
            return None

        size = int(abs(value) // price)
        if size == 0:
            return None

        if value > 0:
            return self.buy(data=data, size=size)
        else:
            return self.sell(data=data, size=size)

    def order_target(self, code: Union[str, bt.DataBase], amount: int) -> Optional[bt.Order]:
        """
        调仓到指定股数

        Args:
            code: 股票代码或 data 对象
            amount: 目标股数

        Returns:
            Order 对象或 None
        """
        data = self._find_data(code)
        pos = self.getposition(data).size
        diff = amount - pos

        if diff == 0:
            return None
        elif diff > 0:
            return self.buy(data=data, size=diff)
        else:
            return self.sell(data=data, size=abs(diff))

    def order_target_value(
        self,
        code: Optional[Union[str, bt.DataBase]] = None,
        target: Optional[float] = None,
        data: Optional[bt.DataBase] = None
    ) -> Optional[bt.Order]:
        """
        调仓到指定金额

        Args:
            code: 股票代码（如果未提供 data）
            target: 目标金额
            data: data 对象（可选，优先于 code）

        Returns:
            Order 对象或 None
        """
        if data is None and code is not None:
            data = self._find_data(code)
        elif data is None:
            raise ValueError("必须提供 data 或 code")

        price = data.close[0]
        if price == 0 or math.isnan(price):
            return None

        target_size = int(target // price)
        return self.order_target(code or data, target_size)

    def order_target_percent(
        self,
        code: Union[str, bt.DataBase],
        target: float
    ) -> Optional[bt.Order]:
        """
        调仓到指定仓位比例

        Args:
            code: 股票代码或 data 对象
            target: 目标仓位比例（0-1）

        Returns:
            Order 对象或 None
        """
        target_value = self.portfolio.total_value * target
        return self.order_target_value(code, target_value)

    def _find_data(self, code: Union[str, bt.DataBase]) -> bt.DataBase:
        """
        根据代码查找 data 对象

        Args:
            code: 股票代码或 data 对象

        Returns:
            Data 对象

        Raises:
            ValueError: 找不到对应数据源
        """
        if isinstance(code, bt.DataBase):
            return code

        target_aliases = _symbol_aliases(code)
        for data in self.datas:
            data_aliases = _symbol_aliases(getattr(data, "_name", None))
            data_aliases.update(_symbol_aliases(getattr(data, "code", None)))
            if target_aliases.intersection(data_aliases):
                return data

        raise ValueError(f"找不到数据源: {code}")


class SignalStrategy(JQ2BTBaseStrategy):
    """
    信号驱动策略基类

    适用于基于信号的策略（如 GSISI 信号），
    子类只需实现 `generate_signals` 方法返回目标仓位。

    Example:
        ```python
        class MySignalStrategy(SignalStrategy):
            def generate_signals(self, context):
                # 返回 {code: target_weight} 字典
                return {
                    '000001.XSHE': 0.5,
                    '600519.XSHG': 0.5
                }
        ```
    """

    params = (
        ("rebalance_time", "14:50"),  # 默认调仓时间
    )

    def initialize(self, context):
        """注册调仓任务"""
        context.run_daily(self._rebalance, time=self.params.rebalance_time)

    def _rebalance(self, context):
        """执行调仓"""
        target_weights = self.generate_signals(context)
        if target_weights is None:
            return

        # 清空不在目标中的持仓
        for code in context.portfolio.positions:
            if code not in target_weights or target_weights.get(code, 0) == 0:
                context.order_target_value(code, 0)

        # 调整目标持仓
        total_value = context.portfolio.total_value
        for code, weight in target_weights.items():
            if weight > 0:
                target_value = total_value * weight
                context.order_target_value(code, target_value)

    def generate_signals(self, context) -> Dict[str, float]:
        """
        生成目标权重信号

        Args:
            context: 策略上下文

        Returns:
            Dict[str, float]: {股票代码: 目标权重(0-1)}
        """
        raise NotImplementedError("子类必须实现 generate_signals 方法")
