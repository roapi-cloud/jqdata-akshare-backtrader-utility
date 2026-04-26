"""策略基类 - 提供策略注册、选股、权重计算和调仓功能"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import pandas as pd
import numpy as np


class StrategyCatalog:
    """策略目录 - 用于注册和获取策略类"""

    _strategies: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str):
        """注册策略装饰器

        Args:
            name: 策略名称

        Returns:
            callable: 装饰器函数
        """

        def decorator(strategy_cls):
            cls._strategies[name] = strategy_cls
            strategy_cls.name = name
            return strategy_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> type:
        """获取策略类

        Args:
            name: 策略名称

        Returns:
            type: 策略类

        Raises:
            KeyError: 策略不存在时抛出
        """
        if name not in cls._strategies:
            raise KeyError(
                f"Strategy '{name}' not found. Available: {list(cls._strategies.keys())}"
            )
        return cls._strategies[name]

    @classmethod
    def list(cls) -> list:
        """列出所有已注册策略

        Returns:
            list: 策略名称列表
        """
        return list(cls._strategies.keys())


class BaseSelectionStrategy(ABC):
    """选股策略基类 - 定义选股、权重计算和调仓接口"""

    name: str = "base"

    @abstractmethod
    def select_stocks(
        self,
        data: pd.DataFrame,
        date: str,
        n_stocks: int = 10,
        min_stocks: int = 5,
        **kwargs,
    ) -> List[str]:
        """选股

        Args:
            data: 截面数据，包含预测分数
            date: 当前日期
            n_stocks: 目标选股数量
            min_stocks: 最少选股数量

        Returns:
            List[str]: 选中的股票代码列表
        """
        pass

    def compute_weights(
        self, data: pd.DataFrame, selected: List[str], method: str = "equal", **kwargs
    ) -> Dict[str, float]:
        """计算权重

        Args:
            data: 截面数据
            selected: 选中的股票列表
            method: 权重计算方法 (equal/market_cap/score)

        Returns:
            Dict[str, float]: {stock_code: weight}
        """
        if method == "equal":
            return {s: 1.0 / len(selected) for s in selected}
        elif method == "score":
            scores = data[data["code"].isin(selected)].set_index("code")["score"]
            total = scores.sum()
            return {s: scores[s] / total for s in selected if s in scores.index}
        else:
            return {s: 1.0 / len(selected) for s in selected}

    def rebalance(
        self,
        current_holdings: Dict[str, float],
        target_weights: Dict[str, float],
        max_turnover: float = 0.5,
    ) -> List[Dict]:
        """生成调仓指令

        Args:
            current_holdings: 当前持仓 {code: weight}
            target_weights: 目标权重 {code: weight}
            max_turnover: 最大换手率

        Returns:
            List[Dict]: 调仓指令列表
        """
        trades = []
        all_stocks = set(list(current_holdings.keys()) + list(target_weights.keys()))

        for stock in all_stocks:
            current = current_holdings.get(stock, 0)
            target = target_weights.get(stock, 0)
            diff = target - current

            if abs(diff) > 0.001:
                trades.append(
                    {
                        "code": stock,
                        "action": "buy" if diff > 0 else "sell",
                        "weight_change": diff,
                        "current_weight": current,
                        "target_weight": target,
                    }
                )

        return trades
