import pandas as pd
from typing import List, Dict, Optional


class Rebalancer:
    """调仓管理器

    管理组合调仓逻辑，包括换手率计算、交易成本评估和调仓执行。
    """

    def __init__(self, max_turnover: float = 1.0, transaction_cost: float = 0.003):
        """初始化调仓管理器

        Args:
            max_turnover: 最大换手率限制
            transaction_cost: 单笔交易成本费率
        """
        self.max_turnover = max_turnover
        self.transaction_cost = transaction_cost
        self.current_portfolio: Dict[str, float] = {}

    def calculate_turnover(
        self, old_weights: Dict[str, float], new_weights: Dict[str, float]
    ) -> float:
        """计算换手率

        Args:
            old_weights: 当前组合权重
            new_weights: 目标组合权重

        Returns:
            换手率 (0-1)
        """
        all_stocks = set(old_weights.keys()) | set(new_weights.keys())
        turnover = 0.0
        for stock in all_stocks:
            old_w = old_weights.get(stock, 0.0)
            new_w = new_weights.get(stock, 0.0)
            turnover += abs(new_w - old_w)
        return turnover / 2

    def calculate_cost(self, turnover: float, capital: float = 1.0) -> float:
        """计算交易成本

        Args:
            turnover: 换手率
            capital: 资金规模

        Returns:
            交易成本
        """
        return turnover * self.transaction_cost * capital

    def should_rebalance(
        self, old_weights: Dict[str, float], new_weights: Dict[str, float]
    ) -> bool:
        """判断是否需要调仓

        Args:
            old_weights: 当前组合权重
            new_weights: 目标组合权重

        Returns:
            是否需要调仓
        """
        if not old_weights:
            return True

        turnover = self.calculate_turnover(old_weights, new_weights)
        cost = self.calculate_cost(turnover)

        if turnover > self.max_turnover:
            return False
        if cost > 0.01:
            return False

        return True

    def rebalance(self, new_weights: Dict[str, float]) -> Dict[str, dict]:
        """执行调仓

        Args:
            new_weights: 目标组合权重

        Returns:
            trades: {"buy": {stock: weight}, "sell": [stock], "hold": {stock: weight}}
        """
        old_weights = self.current_portfolio
        trades: Dict[str, object] = {"buy": {}, "sell": [], "hold": {}}

        all_stocks = set(old_weights.keys()) | set(new_weights.keys())

        for stock in all_stocks:
            old_w = old_weights.get(stock, 0.0)
            new_w = new_weights.get(stock, 0.0)

            if new_w > 0 and old_w == 0:
                trades["buy"][stock] = new_w
            elif new_w == 0 and old_w > 0:
                trades["sell"].append(stock)
            elif abs(new_w - old_w) > 1e-6:
                if new_w > old_w:
                    trades["buy"][stock] = new_w - old_w
                else:
                    trades["sell"].append(stock)
                trades["hold"][stock] = new_w
            else:
                trades["hold"][stock] = new_w

        self.current_portfolio = new_weights
        return trades

    def get_portfolio_summary(self) -> dict:
        """获取当前组合摘要

        Returns:
            组合摘要字典
        """
        if not self.current_portfolio:
            return {"n_stocks": 0, "weights": {}}
        return {
            "n_stocks": len(self.current_portfolio),
            "weights": self.current_portfolio,
            "total_weight": sum(self.current_portfolio.values()),
        }
