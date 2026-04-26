"""组合管理 - 持仓跟踪、收益计算和再平衡"""

import logging
import pandas as pd
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Portfolio:
    """组合管理器 - 跟踪持仓、计算收益、生成调仓指令"""

    def __init__(self, initial_capital: float = 1_000_000):
        """初始化组合管理器

        Args:
            initial_capital: 初始资金
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, float] = {}
        self.target_weights: Dict[str, float] = {}
        self.trade_history: List[Dict] = []

    @property
    def holding_codes(self) -> List[str]:
        """当前持仓代码列表"""
        return list(self.positions.keys())

    def get_weights(self, prices: Dict[str, float]) -> Dict[str, float]:
        """根据当前价格计算持仓权重

        Args:
            prices: 当前价格 {code: price}

        Returns:
            Dict[str, float]: {code: weight}
        """
        total_value = self.get_total_value(prices)
        if total_value == 0:
            return {}

        weights = {}
        for code, shares in self.positions.items():
            price = prices.get(code, 0)
            weights[code] = (shares * price) / total_value

        return weights

    def get_total_value(self, prices: Dict[str, float]) -> float:
        """计算组合总价值

        Args:
            prices: 当前价格 {code: price}

        Returns:
            float: 组合总价值
        """
        position_value = sum(
            shares * prices.get(code, 0) for code, shares in self.positions.items()
        )
        return position_value + self.cash

    def rebalance(
        self, target_weights: Dict[str, float], prices: Dict[str, float]
    ) -> List[Dict]:
        """再平衡到目标权重

        Args:
            target_weights: 目标权重 {code: weight}
            prices: 当前价格 {code: price}

        Returns:
            List[Dict]: 交易指令列表
        """
        trades = []
        total_value = self.get_total_value(prices)

        target_shares = {}
        for code, weight in target_weights.items():
            price = prices.get(code, 0)
            if price > 0:
                target_shares[code] = int(total_value * weight / price / 100) * 100

        all_codes = set(list(self.positions.keys()) + list(target_shares.keys()))

        for code in all_codes:
            current = self.positions.get(code, 0)
            target = target_shares.get(code, 0)
            diff = target - current

            if diff != 0:
                price = prices.get(code, 0)
                trades.append(
                    {
                        "code": code,
                        "action": "buy" if diff > 0 else "sell",
                        "shares": abs(diff),
                        "price": price,
                        "value": abs(diff) * price,
                    }
                )

        return trades

    def execute_trades(
        self, trades: List[Dict], prices: Dict[str, float], commission: float = 0.0003
    ) -> None:
        """执行交易

        Args:
            trades: 交易指令列表
            prices: 成交价格 {code: price}
            commission: 手续费率
        """
        for trade in trades:
            code = trade["code"]
            shares = trade["shares"]
            price = prices.get(code, trade.get("price", 0))
            value = shares * price
            cost = value * commission

            if trade["action"] == "buy":
                if self.cash >= value + cost:
                    self.positions[code] = self.positions.get(code, 0) + shares
                    self.cash -= value + cost
                else:
                    affordable_shares = (
                        int((self.cash / (price * (1 + commission))) / 100) * 100
                    )
                    if affordable_shares > 0:
                        self.positions[code] = (
                            self.positions.get(code, 0) + affordable_shares
                        )
                        self.cash -= affordable_shares * price * (1 + commission)
            else:
                sell_shares = min(shares, self.positions.get(code, 0))
                self.positions[code] = self.positions.get(code, 0) - sell_shares
                self.cash += sell_shares * price * (1 - commission)

                if self.positions[code] == 0:
                    del self.positions[code]

            self.trade_history.append(
                {
                    **trade,
                    "executed_shares": sell_shares
                    if trade["action"] == "sell"
                    else trade["shares"],
                    "cost": cost,
                }
            )

    def snapshot(self, prices: Dict[str, float], date: str) -> Dict:
        """获取组合快照

        Args:
            prices: 当前价格 {code: price}
            date: 日期

        Returns:
            Dict: 组合快照信息
        """
        return {
            "date": date,
            "cash": self.cash,
            "positions": dict(self.positions),
            "total_value": self.get_total_value(prices),
            "n_holdings": len(self.positions),
        }
