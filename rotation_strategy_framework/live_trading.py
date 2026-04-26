# -*- coding: utf-8 -*-
"""
实盘适配器: 抽象交易接口、模拟盘与实盘无缝切换、订单管理、仓位管理、滑点与手续费模拟、异常处理

核心类:
- Order: 订单 (symbol, side, quantity, price, order_type, status, filled_qty, avg_price)
- Position: 持仓 (symbol, quantity, avg_cost, current_price, pnl, pnl_pct)
- BrokerInterface: 券商接口抽象基类 (place_order, cancel_order, get_positions, get_balance)
- SimulatedBroker: 模拟券商 (基于历史数据回测)
- LiveBroker: 实盘券商 (预留接口，支持扩展)
- OrderManager: 订单管理器 (订单生命周期、状态跟踪、重试机制)
- PositionManager: 仓位管理器 (实时同步、盈亏计算)

订单状态机:
PENDING -> SUBMITTED -> PARTIAL_FILLED -> FILLED
                    -> CANCELLED
                    -> REJECTED

实盘接口预留:
- 支持聚宽 (JoinQuant)
- 支持掘金 (PQuant)
- 支持自定义接口 (实现 BrokerInterface)
"""

import logging
import datetime
import time
import uuid
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Tuple, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from copy import deepcopy

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 订单状态枚举
# ---------------------------------------------------------------------------
class OrderStatus(Enum):
    """订单状态"""

    PENDING = "pending"  # 待提交
    SUBMITTED = "submitted"  # 已提交
    PARTIAL_FILLED = "partial_filled"  # 部分成交
    FILLED = "filled"  # 全部成交
    CANCELLED = "cancelled"  # 已撤销
    REJECTED = "rejected"  # 已拒绝


class OrderSide(Enum):
    """买卖方向"""

    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """订单类型"""

    MARKET = "market"  # 市价单
    LIMIT = "limit"  # 限价单


class BrokerType(Enum):
    """券商类型"""

    SIMULATED = "simulated"  # 模拟盘
    LIVE = "live"  # 实盘
    JOINQUANT = "joinquant"  # 聚宽
    PQUANT = "pquant"  # 掘金


# ---------------------------------------------------------------------------
# Order: 订单
# ---------------------------------------------------------------------------
@dataclass
class Order:
    """
    订单对象

    Attributes:
        order_id: 订单唯一标识
        symbol: 标的代码
        side: 买卖方向
        quantity: 委托数量
        price: 委托价格 (市价单可为 None)
        order_type: 订单类型 (市价/限价)
        status: 订单状态
        filled_qty: 已成交数量
        avg_price: 成交均价
        commission: 手续费
        slippage_cost: 滑点成本
        created_at: 创建时间
        updated_at: 更新时间
        filled_at: 成交时间
        message: 附加消息 (如拒绝原因)
        broker_order_id: 券商返回的订单ID
        retry_count: 重试次数
    """

    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    price: Optional[float] = None
    order_type: OrderType = OrderType.LIMIT
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    avg_price: float = 0.0
    commission: float = 0.0
    slippage_cost: float = 0.0
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    filled_at: Optional[datetime.datetime] = None
    message: str = ""
    broker_order_id: str = ""
    retry_count: int = 0

    def __post_init__(self):
        if not self.order_id:
            self.order_id = self._generate_id()
        if self.created_at is None:
            self.created_at = datetime.datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at

    @staticmethod
    def _generate_id() -> str:
        return f"ORD-{uuid.uuid4().hex[:12].upper()}"

    @property
    def remaining_qty(self) -> float:
        """未成交数量"""
        return self.quantity - self.filled_qty

    @property
    def fill_ratio(self) -> float:
        """成交比例"""
        if self.quantity <= 0:
            return 0.0
        return self.filled_qty / self.quantity

    @property
    def is_active(self) -> bool:
        """订单是否处于活跃状态"""
        return self.status in (
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIAL_FILLED,
        )

    @property
    def is_terminal(self) -> bool:
        """订单是否处于终态"""
        return self.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        )

    @property
    def notional_value(self) -> float:
        """名义价值"""
        ref_price = self.avg_price if self.avg_price > 0 else (self.price or 0)
        return self.filled_qty * ref_price

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["side"] = self.side.value
        d["order_type"] = self.order_type.value
        d["status"] = self.status.value
        if self.created_at:
            d["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            d["updated_at"] = self.updated_at.isoformat()
        if self.filled_at:
            d["filled_at"] = self.filled_at.isoformat()
        return d

    def __repr__(self) -> str:
        return (
            f"Order(id={self.order_id}, symbol={self.symbol}, "
            f"side={self.side.value}, qty={self.quantity}, "
            f"status={self.status.value}, filled={self.filled_qty}/{self.quantity})"
        )


# ---------------------------------------------------------------------------
# Position: 持仓
# ---------------------------------------------------------------------------
@dataclass
class Position:
    """
    持仓对象

    Attributes:
        symbol: 标的代码
        quantity: 持仓数量 (正=多头, 负=空头)
        avg_cost: 平均成本价
        current_price: 当前价格
        pnl: 浮动盈亏
        pnl_pct: 浮动盈亏比例
        market_value: 市值
        cost_basis: 持仓成本
        created_at: 首次建仓时间
        updated_at: 更新时间
    """

    symbol: str = ""
    quantity: float = 0.0
    avg_cost: float = 0.0
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    market_value: float = 0.0
    cost_basis: float = 0.0
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    def __post_init__(self):
        self._recalculate()
        if self.created_at is None:
            self.created_at = datetime.datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at

    def _recalculate(self):
        """重新计算盈亏"""
        self.cost_basis = abs(self.quantity) * self.avg_cost
        self.market_value = abs(self.quantity) * self.current_price
        if self.quantity > 0:
            self.pnl = (self.current_price - self.avg_cost) * self.quantity
        elif self.quantity < 0:
            self.pnl = (self.avg_cost - self.current_price) * abs(self.quantity)
        else:
            self.pnl = 0.0
        if self.avg_cost > 0:
            self.pnl_pct = self.pnl / self.cost_basis
        else:
            self.pnl_pct = 0.0

    def update_price(self, price: float) -> None:
        """更新当前价格并重新计算盈亏"""
        self.current_price = price
        self.updated_at = datetime.datetime.now()
        self._recalculate()

    def update_from_fill(
        self, fill_qty: float, fill_price: float, side: OrderSide
    ) -> None:
        """根据成交更新持仓"""
        if side == OrderSide.BUY:
            total_cost = self.avg_cost * self.quantity + fill_price * fill_qty
            self.quantity += fill_qty
            if self.quantity > 0:
                self.avg_cost = total_cost / self.quantity
        elif side == OrderSide.SELL:
            self.quantity -= fill_qty
            if self.quantity <= 0:
                self.avg_cost = 0.0

        self.updated_at = datetime.datetime.now()
        self._recalculate()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.created_at:
            d["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            d["updated_at"] = self.updated_at.isoformat()
        return d

    def __repr__(self) -> str:
        return (
            f"Position(symbol={self.symbol}, qty={self.quantity}, "
            f"avg_cost={self.avg_cost:.4f}, current={self.current_price:.4f}, "
            f"pnl={self.pnl:.2f}, pnl_pct={self.pnl_pct:.2%})"
        )


# ---------------------------------------------------------------------------
# BrokerInterface: 券商接口抽象基类
# ---------------------------------------------------------------------------
class BrokerInterface(ABC):
    """
    券商接口抽象基类

    所有券商适配器必须实现此接口。
    支持模拟盘、实盘、聚宽、掘金等多种后端。
    """

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        **kwargs: Any,
    ) -> Order:
        """
        下单

        Args:
            symbol: 标的代码
            side: 买卖方向
            quantity: 数量
            price: 委托价格 (市价单可为 None)
            order_type: 订单类型
            **kwargs: 额外参数 (由各券商实现定义)

        Returns:
            Order 对象
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        撤单

        Args:
            order_id: 订单ID

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        查询订单

        Args:
            order_id: 订单ID

        Returns:
            Order 对象或 None
        """
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        获取当前持仓

        Returns:
            持仓列表
        """
        pass

    @abstractmethod
    def get_balance(self) -> Tuple[float, float, float]:
        """
        获取账户余额

        Returns:
            (cash, frozen, total) 可用资金、冻结资金、总资产
        """
        pass

    @abstractmethod
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        获取标的当前价格

        Args:
            symbol: 标的代码

        Returns:
            当前价格或 None
        """
        pass

    @abstractmethod
    def sync_positions(self) -> List[Position]:
        """
        同步实际持仓

        Returns:
            同步后的持仓列表
        """
        pass

    @abstractmethod
    def handle_order_update(self, order_update: Dict[str, Any]) -> Optional[Order]:
        """
        处理成交回报

        Args:
            order_update: 回报数据

        Returns:
            更新后的 Order 或 None
        """
        pass

    @property
    @abstractmethod
    def broker_type(self) -> BrokerType:
        """券商类型"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """建立连接"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接"""
        pass


# ---------------------------------------------------------------------------
# 滑点与手续费模型
# ---------------------------------------------------------------------------
@dataclass
class CostModel:
    """
    交易成本模型

    Attributes:
        commission_rate: 佣金比例 (如 0.0003 表示万分之三)
        min_commission: 最低佣金 (元)
        stamp_tax: 印花税比例 (卖出时收取，如 0.001)
        transfer_fee: 过户费比例
        slippage_rate: 滑点比例
        slippage_fixed: 固定滑点 (元)
        use_percentage_slippage: 使用比例滑点 (否则使用固定滑点)
    """

    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_tax: float = 0.001
    transfer_fee: float = 0.00002
    slippage_rate: float = 0.0
    slippage_fixed: float = 0.0
    use_percentage_slippage: bool = True

    def calc_commission(self, notional: float, side: OrderSide) -> float:
        """计算手续费"""
        comm = notional * self.commission_rate
        comm = max(comm, self.min_commission)
        if side == OrderSide.SELL:
            comm += notional * self.stamp_tax
        comm += notional * self.transfer_fee
        return round(comm, 2)

    def calc_slippage(self, price: float, side: OrderSide) -> float:
        """计算滑点后的执行价格"""
        if self.use_percentage_slippage:
            slip = price * self.slippage_rate
        else:
            slip = self.slippage_fixed

        if side == OrderSide.BUY:
            return price + slip
        else:
            return price - slip

    def calc_total_cost(
        self, price: float, quantity: float, side: OrderSide
    ) -> Tuple[float, float, float]:
        """
        计算总成本

        Returns:
            (exec_price, commission, slippage_cost)
        """
        exec_price = self.calc_slippage(price, side)
        notional = exec_price * quantity
        commission = self.calc_commission(notional, side)
        slippage_cost = abs(exec_price - price) * quantity
        return exec_price, commission, slippage_cost


# ---------------------------------------------------------------------------
# SimulatedBroker: 模拟券商
# ---------------------------------------------------------------------------
class SimulatedBroker(BrokerInterface):
    """
    模拟券商

    基于历史数据或实时价格模拟交易执行。
    支持滑点与手续费模拟，用于回测和模拟盘。

    Attributes:
        initial_cash: 初始资金
        cash: 当前可用资金
        frozen: 冻结资金
        positions: 持仓字典 {symbol: Position}
        orders: 订单字典 {order_id: Order}
        cost_model: 成本模型
        price_data: 价格数据 {symbol: pd.Series/DataFrame}
        current_bar_time: 当前bar时间
        fill_probability: 成交概率 (模拟部分成交)
    """

    def __init__(
        self,
        initial_cash: float = 1_000_000.0,
        cost_model: Optional[CostModel] = None,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
        fill_probability: float = 1.0,
    ):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.frozen = 0.0
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.cost_model = cost_model or CostModel()
        self.price_data = price_data or {}
        self.current_bar_time: Optional[datetime.datetime] = None
        self.fill_probability = fill_probability
        self._connected = False
        self._order_callbacks: List[Callable[[Order], None]] = []
        self._lock = threading.Lock()

    @property
    def broker_type(self) -> BrokerType:
        return BrokerType.SIMULATED

    def connect(self) -> bool:
        self._connected = True
        logger.info("SimulatedBroker: 连接成功")
        return True

    def disconnect(self) -> None:
        self._connected = False
        logger.info("SimulatedBroker: 已断开")

    def is_connected(self) -> bool:
        return self._connected

    def set_price_data(self, symbol: str, data: pd.DataFrame) -> None:
        """设置标的价格数据 (用于回测)"""
        self.price_data[symbol] = data

    def set_current_time(self, dt: datetime.datetime) -> None:
        """设置当前模拟时间"""
        self.current_bar_time = dt

    def _get_price(self, symbol: str) -> Optional[float]:
        """获取标的当前价格"""
        if symbol in self.price_data:
            df = self.price_data[symbol]
            if isinstance(df, pd.DataFrame) and len(df) > 0:
                if self.current_bar_time is not None:
                    try:
                        row = df.loc[self.current_bar_time]
                        if isinstance(row, pd.DataFrame):
                            return float(row["close"].iloc[-1])
                        return float(row["close"])
                    except (KeyError, IndexError):
                        pass
                last_row = df.iloc[-1]
                return float(last_row["close"])
        return None

    def get_current_price(self, symbol: str) -> Optional[float]:
        return self._get_price(symbol)

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        **kwargs: Any,
    ) -> Order:
        with self._lock:
            current_price = self._get_price(symbol)
            if current_price is None:
                order = Order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    order_type=order_type,
                    status=OrderStatus.REJECTED,
                    message=f"无法获取 {symbol} 的价格数据",
                )
                self.orders[order.order_id] = order
                return order

            exec_price = price if price is not None else current_price

            if order_type == OrderType.MARKET:
                exec_price = current_price

            if side == OrderSide.BUY:
                max_affordable = self.cash / exec_price
                if quantity > max_affordable:
                    order = Order(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=price,
                        order_type=order_type,
                        status=OrderStatus.REJECTED,
                        message=f"资金不足: 需要 {quantity * exec_price:.2f}, 可用 {self.cash:.2f}",
                    )
                    self.orders[order.order_id] = order
                    return order
            elif side == OrderSide.SELL:
                pos = self.positions.get(symbol)
                if pos is None or pos.quantity < quantity:
                    available = pos.quantity if pos else 0.0
                    order = Order(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=price,
                        order_type=order_type,
                        status=OrderStatus.REJECTED,
                        message=f"持仓不足: 需要 {quantity}, 可用 {available}",
                    )
                    self.orders[order.order_id] = order
                    return order

            cost_price, commission, slippage_cost = self.cost_model.calc_total_cost(
                exec_price, quantity, side
            )

            order = Order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
                status=OrderStatus.SUBMITTED,
                commission=commission,
                slippage_cost=slippage_cost,
            )

            if side == OrderSide.BUY:
                self.frozen += cost_price * quantity + commission

            self.orders[order.order_id] = order
            logger.info(
                f"SimulatedBroker: 下单 {order.order_id} | "
                f"{symbol} {side.value} {quantity} @ {exec_price:.4f}"
            )

            self._simulate_fill(order, cost_price, commission)

            for cb in self._order_callbacks:
                try:
                    cb(order)
                except Exception:
                    pass

            return order

    def _simulate_fill(
        self, order: Order, exec_price: float, commission: float
    ) -> None:
        """模拟成交"""
        if np.random.random() > self.fill_probability:
            return

        fill_qty = order.quantity
        if self.fill_probability < 1.0:
            fill_qty = order.quantity * np.random.uniform(0.5, 1.0)
            fill_qty = round(fill_qty, 2)

        order.filled_qty = fill_qty
        order.avg_price = exec_price
        order.commission = commission
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.datetime.now()
        order.updated_at = order.filled_at

        self._apply_fill(order)

    def _apply_fill(self, order: Order) -> None:
        """应用成交到账户"""
        if order.side == OrderSide.BUY:
            cost = order.avg_price * order.filled_qty + order.commission
            self.cash -= cost
            self.frozen -= order.avg_price * order.filled_qty + order.commission

            pos = self.positions.get(order.symbol)
            if pos is None:
                pos = Position(
                    symbol=order.symbol,
                    quantity=order.filled_qty,
                    avg_cost=order.avg_price,
                    current_price=order.avg_price,
                )
                self.positions[order.symbol] = pos
            else:
                pos.update_from_fill(order.filled_qty, order.avg_price, order.side)
        elif order.side == OrderSide.SELL:
            proceeds = order.avg_price * order.filled_qty - order.commission
            self.cash += proceeds
            self.frozen -= order.avg_price * order.filled_qty + order.commission

            pos = self.positions.get(order.symbol)
            if pos:
                pos.update_from_fill(order.filled_qty, order.avg_price, order.side)
                if pos.quantity <= 0:
                    del self.positions[order.symbol]

        self.frozen = max(0.0, self.frozen)

    def cancel_order(self, order_id: str) -> bool:
        with self._lock:
            order = self.orders.get(order_id)
            if order is None:
                return False

            if not order.is_active:
                return False

            if order.side == OrderSide.BUY and order.frozen > 0:
                unfilled = order.remaining_qty
                refund = unfilled * (order.price or 0)
                self.frozen -= refund
                self.frozen = max(0.0, self.frozen)

            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.datetime.now()

            logger.info(f"SimulatedBroker: 撤单 {order_id}")
            return True

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.orders.get(order_id)

    def get_positions(self) -> List[Position]:
        return list(self.positions.values())

    def get_balance(self) -> Tuple[float, float, float]:
        total = self.cash + self.frozen
        for pos in self.positions.values():
            total += pos.market_value
        return self.cash, self.frozen, total

    def sync_positions(self) -> List[Position]:
        for symbol, pos in self.positions.items():
            price = self._get_price(symbol)
            if price is not None:
                pos.update_price(price)
        return list(self.positions.values())

    def handle_order_update(self, order_update: Dict[str, Any]) -> Optional[Order]:
        order_id = order_update.get("order_id")
        if order_id not in self.orders:
            return None

        order = self.orders[order_id]
        status_str = order_update.get("status", "")

        status_map = {
            "submitted": OrderStatus.SUBMITTED,
            "partial_filled": OrderStatus.PARTIAL_FILLED,
            "filled": OrderStatus.FILLED,
            "cancelled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
        }

        new_status = status_map.get(status_str)
        if new_status:
            order.status = new_status

        filled_qty = order_update.get("filled_qty")
        if filled_qty is not None:
            order.filled_qty = filled_qty

        avg_price = order_update.get("avg_price")
        if avg_price is not None:
            order.avg_price = avg_price

        order.updated_at = datetime.datetime.now()

        if order.status == OrderStatus.FILLED:
            order.filled_at = order.updated_at
            self._apply_fill(order)

        return order

    def on_order_update(self, callback: Callable[[Order], None]) -> None:
        """注册订单更新回调"""
        self._order_callbacks.append(callback)

    def reset(self) -> None:
        """重置模拟账户"""
        self.cash = self.initial_cash
        self.frozen = 0.0
        self.positions.clear()
        self.orders.clear()
        logger.info("SimulatedBroker: 已重置")


# ---------------------------------------------------------------------------
# LiveBroker: 实盘券商 (预留接口)
# ---------------------------------------------------------------------------
class LiveBroker(BrokerInterface):
    """
    实盘券商基类

    预留接口，支持扩展具体券商实现。
    子类需实现所有抽象方法。

    支持的扩展:
    - JoinQuantBroker: 聚宽实盘
    - PQuantBroker: 掘金实盘
    - CustomBroker: 自定义券商
    """

    def __init__(
        self,
        cost_model: Optional[CostModel] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.cost_model = cost_model or CostModel()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._connected = False
        self._orders: Dict[str, Order] = {}
        self._order_callbacks: List[Callable[[Order], None]] = []
        self._lock = threading.Lock()

    @property
    def broker_type(self) -> BrokerType:
        return BrokerType.LIVE

    def connect(self) -> bool:
        self._connected = True
        logger.info("LiveBroker: 连接成功")
        return True

    def disconnect(self) -> None:
        self._connected = False
        logger.info("LiveBroker: 已断开")

    def is_connected(self) -> bool:
        return self._connected

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        **kwargs: Any,
    ) -> Order:
        return self._with_retry(
            self._place_order_impl, symbol, side, quantity, price, order_type, kwargs
        )

    def _place_order_impl(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: Optional[float],
        order_type: OrderType,
        kwargs: Dict[str, Any],
    ) -> Order:
        raise NotImplementedError("子类必须实现 _place_order_impl")

    def cancel_order(self, order_id: str) -> bool:
        return self._with_retry(self._cancel_order_impl, order_id)

    def _cancel_order_impl(self, order_id: str) -> bool:
        raise NotImplementedError("子类必须实现 _cancel_order_impl")

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_positions(self) -> List[Position]:
        return self._get_positions_impl()

    def _get_positions_impl(self) -> List[Position]:
        raise NotImplementedError("子类必须实现 _get_positions_impl")

    def get_balance(self) -> Tuple[float, float, float]:
        return self._get_balance_impl()

    def _get_balance_impl(self) -> Tuple[float, float, float]:
        raise NotImplementedError("子类必须实现 _get_balance_impl")

    def get_current_price(self, symbol: str) -> Optional[float]:
        return self._get_current_price_impl(symbol)

    def _get_current_price_impl(self, symbol: str) -> Optional[float]:
        raise NotImplementedError("子类必须实现 _get_current_price_impl")

    def sync_positions(self) -> List[Position]:
        return self._sync_positions_impl()

    def _sync_positions_impl(self) -> List[Position]:
        raise NotImplementedError("子类必须实现 _sync_positions_impl")

    def handle_order_update(self, order_update: Dict[str, Any]) -> Optional[Order]:
        order_id = order_update.get("order_id")
        if order_id not in self._orders:
            return None

        order = self._orders[order_id]
        status_str = order_update.get("status", "")

        status_map = {
            "submitted": OrderStatus.SUBMITTED,
            "partial_filled": OrderStatus.PARTIAL_FILLED,
            "filled": OrderStatus.FILLED,
            "cancelled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
        }

        new_status = status_map.get(status_str)
        if new_status:
            order.status = new_status

        filled_qty = order_update.get("filled_qty")
        if filled_qty is not None:
            order.filled_qty = filled_qty

        avg_price = order_update.get("avg_price")
        if avg_price is not None:
            order.avg_price = avg_price

        order.updated_at = datetime.datetime.now()

        if order.status == OrderStatus.FILLED:
            order.filled_at = order.updated_at

        for cb in self._order_callbacks:
            try:
                cb(order)
            except Exception:
                pass

        return order

    def on_order_update(self, callback: Callable[[Order], None]) -> None:
        self._order_callbacks.append(callback)

    def _with_retry(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """带重试的执行"""
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"LiveBroker: 第 {attempt} 次重试，等待 {delay:.1f}s"
                    )
                    time.sleep(delay)
                return func(*args, **kwargs)
            except ConnectionError as e:
                last_error = e
                logger.error(f"LiveBroker: 网络断开 - {e}")
                self._connected = False
            except Exception as e:
                last_error = e
                logger.error(f"LiveBroker: 执行失败 - {e}")

        raise RuntimeError(
            f"LiveBroker: 操作失败，已重试 {self.max_retries} 次: {last_error}"
        )


# ---------------------------------------------------------------------------
# JoinQuantBroker: 聚宽实盘适配器 (示例实现)
# ---------------------------------------------------------------------------
class JoinQuantBroker(LiveBroker):
    """
    聚宽 (JoinQuant) 实盘适配器

    需要安装 jqdatasdk 并配置账号。
    此实现为示例框架，实际使用时需根据聚宽 API 完善。
    """

    def __init__(
        self,
        username: str = "",
        password: str = "",
        cost_model: Optional[CostModel] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        super().__init__(cost_model, max_retries, retry_delay)
        self.username = username
        self.password = password
        self._jq = None

    @property
    def broker_type(self) -> BrokerType:
        return BrokerType.JOINQUANT

    def connect(self) -> bool:
        try:
            try:
                import jqdatasdk as jq
            except ImportError:
                logger.error("JoinQuantBroker: 请安装 jqdatasdk")
                return False

            jq.auth(self.username, self.password)
            self._jq = jq
            self._connected = True
            logger.info("JoinQuantBroker: 聚宽连接成功")
            return True
        except Exception as e:
            logger.error(f"JoinQuantBroker: 连接失败 - {e}")
            return False

    def disconnect(self) -> None:
        if self._jq:
            try:
                self._jq.logout()
            except Exception:
                pass
        self._connected = False
        logger.info("JoinQuantBroker: 已断开")

    def _place_order_impl(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: Optional[float],
        order_type: OrderType,
        kwargs: Dict[str, Any],
    ) -> Order:
        if not self._connected or self._jq is None:
            raise ConnectionError("聚宽未连接")

        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            status=OrderStatus.SUBMITTED,
        )

        jq_side = "buy" if side == OrderSide.BUY else "sell"

        try:
            if order_type == OrderType.MARKET:
                jq_order_id = self._jq.order_market(symbol, jq_side, quantity)
            else:
                if price is None:
                    raise ValueError("限价单必须指定价格")
                jq_order_id = self._jq.order_limit(symbol, jq_side, quantity, price)

            order.broker_order_id = str(jq_order_id)
            self._orders[order.order_id] = order

            logger.info(f"JoinQuantBroker: 下单成功 {order.order_id} -> {jq_order_id}")
        except Exception as e:
            order.status = OrderStatus.REJECTED
            order.message = str(e)
            self._orders[order.order_id] = order
            logger.error(f"JoinQuantBroker: 下单失败 - {e}")

        return order

    def _cancel_order_impl(self, order_id: str) -> bool:
        if not self._connected or self._jq is None:
            raise ConnectionError("聚宽未连接")

        order = self._orders.get(order_id)
        if order and order.broker_order_id:
            try:
                self._jq.cancel_order(order.broker_order_id)
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.datetime.now()
                return True
            except Exception as e:
                logger.error(f"JoinQuantBroker: 撤单失败 - {e}")
                return False
        return False

    def _get_positions_impl(self) -> List[Position]:
        if not self._connected or self._jq is None:
            raise ConnectionError("聚宽未连接")

        positions = []
        try:
            jq_positions = self._jq.get_all_positions()
            for jp in jq_positions:
                pos = Position(
                    symbol=jp.get("code", ""),
                    quantity=jp.get("volume", 0),
                    avg_cost=jp.get("avg_cost", 0),
                    current_price=jp.get("price", 0),
                )
                positions.append(pos)
        except Exception as e:
            logger.error(f"JoinQuantBroker: 获取持仓失败 - {e}")

        return positions

    def _get_balance_impl(self) -> Tuple[float, float, float]:
        if not self._connected or self._jq is None:
            raise ConnectionError("聚宽未连接")

        try:
            account = self._jq.get_account()
            cash = account.get("available_cash", 0)
            frozen = account.get("frozen_cash", 0)
            total = account.get("total_value", 0)
            return cash, frozen, total
        except Exception as e:
            logger.error(f"JoinQuantBroker: 获取账户失败 - {e}")
            return 0.0, 0.0, 0.0

    def _get_current_price_impl(self, symbol: str) -> Optional[float]:
        if not self._connected or self._jq is None:
            raise ConnectionError("聚宽未连接")

        try:
            tick = self._jq.get_current_tick(symbol)
            return tick.get("last", None)
        except Exception:
            return None

    def _sync_positions_impl(self) -> List[Position]:
        return self._get_positions_impl()


# ---------------------------------------------------------------------------
# OrderManager: 订单管理器
# ---------------------------------------------------------------------------
class OrderManager:
    """
    订单管理器

    管理订单生命周期、状态跟踪、重试机制。

    Attributes:
        broker: 券商接口
        orders: 所有订单 {order_id: Order}
        active_orders: 活跃订单 {order_id: Order}
        completed_orders: 已完成订单列表
        max_retries: 最大重试次数
        retry_delay: 重试延迟 (秒)
        order_timeout: 订单超时时间 (秒)
    """

    def __init__(
        self,
        broker: BrokerInterface,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        order_timeout: float = 300.0,
    ):
        self.broker = broker
        self.orders: Dict[str, Order] = {}
        self.active_orders: Dict[str, Order] = {}
        self.completed_orders: List[Order] = []
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.order_timeout = order_timeout
        self._lock = threading.Lock()
        self._callbacks: Dict[str, List[Callable[[Order], None]]] = {}
        self._global_callbacks: List[Callable[[Order], None]] = []

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        **kwargs: Any,
    ) -> Order:
        """
        下单 (带重试)

        Args:
            symbol: 标的代码
            side: 买卖方向
            quantity: 数量
            price: 委托价格
            order_type: 订单类型
            **kwargs: 额外参数

        Returns:
            Order 对象
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"OrderManager: 第 {attempt} 次重试下单，等待 {delay:.1f}s"
                    )
                    time.sleep(delay)

                order = self.broker.place_order(
                    symbol, side, quantity, price, order_type, **kwargs
                )
                order.retry_count = attempt

                with self._lock:
                    self.orders[order.order_id] = order
                    if order.is_active:
                        self.active_orders[order.order_id] = order

                self._notify(order)
                logger.info(
                    f"OrderManager: 下单成功 {order.order_id} "
                    f"({symbol} {side.value} {quantity} @ {price})"
                )
                return order

            except Exception as e:
                last_error = e
                logger.error(f"OrderManager: 下单失败 (尝试 {attempt + 1}) - {e}")

        rejected = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            status=OrderStatus.REJECTED,
            message=f"下单失败，已重试 {self.max_retries} 次: {last_error}",
            retry_count=self.max_retries,
        )

        with self._lock:
            self.orders[rejected.order_id] = rejected

        self._notify(rejected)
        return rejected

    def cancel_order(self, order_id: str) -> bool:
        """
        撤单 (带重试)

        Args:
            order_id: 订单ID

        Returns:
            是否成功
        """
        order = self.orders.get(order_id)
        if order is None:
            logger.warning(f"OrderManager: 订单 {order_id} 不存在")
            return False

        if not order.is_active:
            logger.warning(
                f"OrderManager: 订单 {order_id} 已处于终态 ({order.status.value})"
            )
            return False

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"OrderManager: 第 {attempt} 次重试撤单，等待 {delay:.1f}s"
                    )
                    time.sleep(delay)

                success = self.broker.cancel_order(order_id)
                if success:
                    order.status = OrderStatus.CANCELLED
                    order.updated_at = datetime.datetime.now()
                    self._move_to_completed(order)
                    self._notify(order)
                    logger.info(f"OrderManager: 撤单成功 {order_id}")
                    return True

            except Exception as e:
                last_error = e
                logger.error(f"OrderManager: 撤单失败 (尝试 {attempt + 1}) - {e}")

        order.message = f"撤单失败，已重试 {self.max_retries} 次: {last_error}"
        order.updated_at = datetime.datetime.now()
        self._notify(order)
        return False

    def cancel_all_active(self) -> int:
        """撤销所有活跃订单"""
        count = 0
        order_ids = list(self.active_orders.keys())
        for oid in order_ids:
            if self.cancel_order(oid):
                count += 1
        return count

    def handle_order_update(self, order_update: Dict[str, Any]) -> Optional[Order]:
        """
        处理成交回报

        Args:
            order_update: 回报数据，需包含 order_id

        Returns:
            更新后的 Order 或 None
        """
        order_id = order_update.get("order_id")
        if order_id is None:
            return None

        order = self.broker.handle_order_update(order_update)
        if order is None:
            return None

        with self._lock:
            self.orders[order.order_id] = order

            if order.is_terminal:
                self._move_to_completed(order)

        self._notify(order)
        return order

    def check_timeouts(self) -> List[Order]:
        """
        检查超时订单并自动撤单

        Returns:
            超时订单列表
        """
        timed_out = []
        now = datetime.datetime.now()

        for order_id, order in list(self.active_orders.items()):
            if order.created_at is None:
                continue
            elapsed = (now - order.created_at).total_seconds()
            if elapsed > self.order_timeout:
                timed_out.append(order)
                logger.warning(
                    f"OrderManager: 订单 {order_id} 超时 ({elapsed:.0f}s > {self.order_timeout:.0f}s)"
                )
                self.cancel_order(order_id)

        return timed_out

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.orders.get(order_id)

    def get_active_orders(self) -> List[Order]:
        return list(self.active_orders.values())

    def get_completed_orders(self) -> List[Order]:
        return list(self.completed_orders)

    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        return [o for o in self.orders.values() if o.symbol == symbol]

    def get_orders_by_status(self, status: OrderStatus) -> List[Order]:
        return [o for o in self.orders.values() if o.status == status]

    def on_order_update(
        self, callback: Callable[[Order], None], order_id: Optional[str] = None
    ) -> None:
        """
        注册订单更新回调

        Args:
            callback: 回调函数
            order_id: 指定订单ID (None 表示全局回调)
        """
        if order_id:
            if order_id not in self._callbacks:
                self._callbacks[order_id] = []
            self._callbacks[order_id].append(callback)
        else:
            self._global_callbacks.append(callback)

    def _move_to_completed(self, order: Order) -> None:
        """将订单移至已完成列表"""
        self.active_orders.pop(order.order_id, None)
        if order not in self.completed_orders:
            self.completed_orders.append(order)

    def _notify(self, order: Order) -> None:
        """通知回调"""
        for cb in self._global_callbacks:
            try:
                cb(order)
            except Exception as e:
                logger.error(f"OrderManager: 回调执行失败 - {e}")

        for cb in self._callbacks.get(order.order_id, []):
            try:
                cb(order)
            except Exception as e:
                logger.error(f"OrderManager: 订单回调执行失败 - {e}")

    def summary(self) -> Dict[str, Any]:
        """订单管理摘要"""
        return {
            "total_orders": len(self.orders),
            "active_orders": len(self.active_orders),
            "completed_orders": len(self.completed_orders),
            "filled": len(self.get_orders_by_status(OrderStatus.FILLED)),
            "cancelled": len(self.get_orders_by_status(OrderStatus.CANCELLED)),
            "rejected": len(self.get_orders_by_status(OrderStatus.REJECTED)),
            "submitted": len(self.get_orders_by_status(OrderStatus.SUBMITTED)),
            "partial_filled": len(
                self.get_orders_by_status(OrderStatus.PARTIAL_FILLED)
            ),
        }


# ---------------------------------------------------------------------------
# PositionManager: 仓位管理器
# ---------------------------------------------------------------------------
class PositionManager:
    """
    仓位管理器

    实时同步持仓、盈亏计算、仓位控制。

    Attributes:
        broker: 券商接口
        positions: 持仓字典 {symbol: Position}
        sync_interval: 同步间隔 (秒)
        last_sync_time: 上次同步时间
        pnl_history: 盈亏历史
    """

    def __init__(
        self,
        broker: BrokerInterface,
        sync_interval: float = 5.0,
    ):
        self.broker = broker
        self.positions: Dict[str, Position] = {}
        self.sync_interval = sync_interval
        self.last_sync_time: Optional[datetime.datetime] = None
        self.pnl_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def sync(self) -> List[Position]:
        """
        同步实际持仓

        Returns:
            同步后的持仓列表
        """
        try:
            broker_positions = self.broker.sync_positions()

            with self._lock:
                broker_pos_map = {p.symbol: p for p in broker_positions}

                for symbol, pos in broker_pos_map.items():
                    self.positions[symbol] = pos

                symbols_to_remove = [
                    s for s in self.positions if s not in broker_pos_map
                ]
                for s in symbols_to_remove:
                    del self.positions[s]

            self.last_sync_time = datetime.datetime.now()
            logger.info(f"PositionManager: 同步完成，共 {len(self.positions)} 个持仓")
            return list(self.positions.values())

        except Exception as e:
            logger.error(f"PositionManager: 同步失败 - {e}")
            return list(self.positions.values())

    def update_prices(self, price_map: Dict[str, float]) -> None:
        """
        批量更新持仓价格

        Args:
            price_map: {symbol: price}
        """
        with self._lock:
            for symbol, price in price_map.items():
                if symbol in self.positions:
                    self.positions[symbol].update_price(price)

    def update_single_price(self, symbol: str, price: Optional[float] = None) -> None:
        """
        更新单个标的价格

        Args:
            symbol: 标的代码
            price: 价格 (None 时从券商获取)
        """
        if price is None:
            price = self.broker.get_current_price(symbol)
        if price is not None and symbol in self.positions:
            self.positions[symbol].update_price(price)

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)

    def get_all_positions(self) -> List[Position]:
        return list(self.positions.values())

    def get_total_pnl(self) -> float:
        """总浮动盈亏"""
        return sum(p.pnl for p in self.positions.values())

    def get_total_pnl_pct(self) -> float:
        """总浮动盈亏比例"""
        total_cost = sum(p.cost_basis for p in self.positions.values())
        if total_cost <= 0:
            return 0.0
        return self.get_total_pnl() / total_cost

    def get_total_market_value(self) -> float:
        """总市值"""
        return sum(p.market_value for p in self.positions.values())

    def get_total_cost_basis(self) -> float:
        """总持仓成本"""
        return sum(p.cost_basis for p in self.positions.values())

    def get_position_weights(self) -> Dict[str, float]:
        """各持仓权重"""
        total_mv = self.get_total_market_value()
        if total_mv <= 0:
            return {}
        return {
            symbol: pos.market_value / total_mv
            for symbol, pos in self.positions.items()
        }

    def get_account_summary(self) -> Dict[str, Any]:
        """账户摘要"""
        cash, frozen, total = self.broker.get_balance()
        return {
            "cash": cash,
            "frozen": frozen,
            "total_asset": total,
            "market_value": self.get_total_market_value(),
            "total_pnl": self.get_total_pnl(),
            "total_pnl_pct": self.get_total_pnl_pct(),
            "position_count": len(self.positions),
            "position_weights": self.get_position_weights(),
            "last_sync": self.last_sync_time.isoformat()
            if self.last_sync_time
            else None,
        }

    def record_pnl_snapshot(self) -> Dict[str, Any]:
        """记录盈亏快照"""
        snapshot = {
            "timestamp": datetime.datetime.now().isoformat(),
            "total_pnl": self.get_total_pnl(),
            "total_pnl_pct": self.get_total_pnl_pct(),
            "market_value": self.get_total_market_value(),
            "positions": {
                s: {"pnl": p.pnl, "pnl_pct": p.pnl_pct, "market_value": p.market_value}
                for s, p in self.positions.items()
            },
        }
        self.pnl_history.append(snapshot)
        return snapshot

    def get_pnl_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取盈亏历史"""
        return self.pnl_history[-limit:]

    def liquidate_all(self) -> List[Order]:
        """
        清仓所有持仓

        Returns:
            提交的订单列表
        """
        orders = []
        for symbol, pos in list(self.positions.items()):
            if pos.quantity > 0:
                order = self.broker.place_order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    quantity=pos.quantity,
                    order_type=OrderType.MARKET,
                )
                orders.append(order)
                logger.info(f"PositionManager: 清仓 {symbol} {pos.quantity} 股")
        return orders

    def auto_sync(self, stop_event: Optional[threading.Event] = None) -> None:
        """
        自动同步循环 (后台线程)

        Args:
            stop_event: 停止事件 (设置后退出循环)
        """
        while stop_event is None or not stop_event.is_set():
            try:
                self.sync()
                price_map = {}
                for symbol in self.positions:
                    price = self.broker.get_current_price(symbol)
                    if price is not None:
                        price_map[symbol] = price
                if price_map:
                    self.update_prices(price_map)
            except Exception as e:
                logger.error(f"PositionManager: 自动同步失败 - {e}")

            if stop_event:
                stop_event.wait(self.sync_interval)
            else:
                time.sleep(self.sync_interval)

    def summary(self) -> Dict[str, Any]:
        """仓位管理摘要"""
        return {
            "position_count": len(self.positions),
            "total_pnl": self.get_total_pnl(),
            "total_pnl_pct": self.get_total_pnl_pct(),
            "market_value": self.get_total_market_value(),
            "positions": {s: p.to_dict() for s, p in self.positions.items()},
        }


# ---------------------------------------------------------------------------
# TradingEngine: 统一交易引擎 (模拟/实盘切换)
# ---------------------------------------------------------------------------
class TradingEngine:
    """
    统一交易引擎

    封装 BrokerInterface, OrderManager, PositionManager，
    提供模拟盘与实盘无缝切换能力。

    Attributes:
        broker: 券商接口
        order_manager: 订单管理器
        position_manager: 仓位管理器
        mode: 交易模式 (simulated/live)
    """

    def __init__(
        self,
        broker: BrokerInterface,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        order_timeout: float = 300.0,
        sync_interval: float = 5.0,
    ):
        self.broker = broker
        self.order_manager = OrderManager(
            broker, max_retries, retry_delay, order_timeout
        )
        self.position_manager = PositionManager(broker, sync_interval)
        self.mode = broker.broker_type.value

    @classmethod
    def create_simulated(
        cls,
        initial_cash: float = 1_000_000.0,
        cost_model: Optional[CostModel] = None,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
        **kwargs: Any,
    ) -> "TradingEngine":
        """创建模拟盘引擎"""
        broker = SimulatedBroker(initial_cash, cost_model, price_data)
        broker.connect()
        return cls(broker, **kwargs)

    @classmethod
    def create_live(
        cls,
        broker: LiveBroker,
        **kwargs: Any,
    ) -> "TradingEngine":
        """创建实盘引擎"""
        broker.connect()
        return cls(broker, **kwargs)

    @classmethod
    def create_joinquant(
        cls,
        username: str = "",
        password: str = "",
        cost_model: Optional[CostModel] = None,
        **kwargs: Any,
    ) -> "TradingEngine":
        """创建聚宽实盘引擎"""
        broker = JoinQuantBroker(username, password, cost_model)
        return cls.create_live(broker, **kwargs)

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        **kwargs: Any,
    ) -> Order:
        """下单"""
        return self.order_manager.place_order(
            symbol, side, quantity, price, order_type, **kwargs
        )

    def buy(
        self,
        symbol: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        **kwargs: Any,
    ) -> Order:
        """买入"""
        return self.place_order(
            symbol, OrderSide.BUY, quantity, price, order_type, **kwargs
        )

    def sell(
        self,
        symbol: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        **kwargs: Any,
    ) -> Order:
        """卖出"""
        return self.place_order(
            symbol, OrderSide.SELL, quantity, price, order_type, **kwargs
        )

    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        return self.order_manager.cancel_order(order_id)

    def cancel_all(self) -> int:
        """撤销所有活跃订单"""
        return self.order_manager.cancel_all_active()

    def get_positions(self) -> List[Position]:
        """获取持仓"""
        return self.position_manager.get_all_positions()

    def get_position(self, symbol: str) -> Optional[Position]:
        """获取单个持仓"""
        return self.position_manager.get_position(symbol)

    def get_balance(self) -> Tuple[float, float, float]:
        """获取账户余额"""
        return self.broker.get_balance()

    def sync(self) -> List[Position]:
        """同步持仓"""
        return self.position_manager.sync()

    def get_account_summary(self) -> Dict[str, Any]:
        """获取账户摘要"""
        summary = self.position_manager.get_account_summary()
        summary["mode"] = self.mode
        summary["order_summary"] = self.order_manager.summary()
        summary["connected"] = self.broker.is_connected()
        return summary

    def liquidate_all(self) -> List[Order]:
        """清仓"""
        return self.position_manager.liquidate_all()

    def shutdown(self) -> None:
        """关闭引擎"""
        self.cancel_all()
        self.broker.disconnect()
        logger.info(f"TradingEngine ({self.mode}): 已关闭")

    def __repr__(self) -> str:
        cash, frozen, total = self.broker.get_balance()
        return (
            f"TradingEngine(mode={self.mode}, "
            f"cash={cash:,.0f}, total={total:,.0f}, "
            f"positions={len(self.position_manager.positions)})"
        )
