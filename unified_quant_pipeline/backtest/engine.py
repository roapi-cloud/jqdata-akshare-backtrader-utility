"""回测引擎 - 基于持仓权重的简化回测"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from .metrics import calculate_all_metrics, calculate_turnover

logger = logging.getLogger(__name__)


class SimpleBacktestEngine:
    """简化回测引擎

    基于每日持仓权重和价格数据计算净值曲线。
    不需要逐笔交易模拟，适合策略快速验证。
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000,
        commission: float = 0.0003,
        slippage: float = 0.002,
    ):
        """初始化回测引擎

        Args:
            initial_capital: 初始资金
            commission: 佣金费率
            slippage: 滑点费率
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

    def run(
        self,
        weights_history: List[Dict[str, float]],
        price_data: pd.DataFrame,
        benchmark_data: Optional[pd.DataFrame] = None,
    ) -> Dict:
        """运行回测

        Args:
            weights_history: 每日权重列表 [{code: weight}, ...]
            price_data: 价格数据 DataFrame，index=date, columns=code
            benchmark_data: 基准价格数据

        Returns:
            Dict: 回测结果
        """
        nav = [self.initial_capital]
        daily_returns = []
        turnovers = []

        prev_weights = {}

        for i, weights in enumerate(weights_history):
            if i == 0:
                daily_returns.append(0)
                prev_weights = weights
                continue

            portfolio_return = self._calculate_portfolio_return(
                prev_weights, weights, price_data.iloc[i], price_data.iloc[i - 1]
            )
            daily_returns.append(portfolio_return)

            turnover = calculate_turnover(prev_weights, weights)
            turnovers.append(turnover)

            prev_weights = weights

        nav = self.initial_capital * np.cumprod(1 + np.array(daily_returns))
        dates = price_data.index[: len(nav)]
        nav_series = pd.Series(nav, index=dates, name="strategy")

        benchmark_nav = None
        if benchmark_data is not None:
            benchmark_nav = benchmark_data.iloc[: len(nav)].mean(axis=1)
            benchmark_nav = (
                benchmark_data.iloc[0, 0] * benchmark_nav / benchmark_data.iloc[0, 0]
            )

        metrics = calculate_all_metrics(nav_series, benchmark_nav)
        metrics["total_turnover"] = sum(turnovers)
        metrics["avg_turnover"] = np.mean(turnovers) if turnovers else 0

        return {
            "nav": nav_series,
            "benchmark_nav": benchmark_nav,
            "metrics": metrics,
            "daily_returns": pd.Series(daily_returns, index=dates),
            "turnovers": turnovers,
        }

    def _calculate_portfolio_return(
        self,
        prev_weights: Dict,
        curr_weights: Dict,
        curr_prices: pd.Series,
        prev_prices: pd.Series,
    ) -> float:
        """计算组合日收益

        Args:
            prev_weights: 昨日持仓权重
            curr_weights: 今日持仓权重
            curr_prices: 今日价格
            prev_prices: 昨日价格

        Returns:
            float: 组合日收益率
        """
        all_codes = set(prev_weights.keys())

        total_return = 0
        for code in all_codes:
            weight = prev_weights.get(code, 0)
            if weight > 0 and code in curr_prices.index and code in prev_prices.index:
                price_curr = curr_prices[code]
                price_prev = prev_prices[code]
                if price_prev > 0:
                    stock_return = price_curr / price_prev - 1
                    cost = self.commission + self.slippage
                    total_return += weight * stock_return - weight * cost

        return total_return
