import pandas as pd
from typing import Dict, Optional

from ml_quant_framework.core.config import PortfolioConfig
from .selector import StockSelector
from .weighting import WeightAllocator
from .rebalancer import Rebalancer


class PortfolioBuilder:
    """组合构建器 - 统一选股、权重分配、调仓

    作为门面类，整合选股器、权重分配器和调仓管理器，
    提供一键式组合构建功能。
    """

    def __init__(self, config: Optional[PortfolioConfig] = None):
        """初始化组合构建器

        Args:
            config: 组合配置，默认使用 PortfolioConfig 默认值
        """
        self.config = config or PortfolioConfig()
        self.selector = StockSelector()
        self.allocator = WeightAllocator()
        self.rebalancer = Rebalancer(
            max_turnover=self.config.max_turnover,
            transaction_cost=0.003,
        )

    def build(
        self,
        scores: pd.Series,
        volatilities: Optional[pd.Series] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> Dict[str, float]:
        """构建投资组合

        Args:
            scores: 预测得分 Series, index=stocks
            volatilities: 波动率 Series (风险平价时使用)
            cov_matrix: 协方差矩阵 DataFrame (最大分散化时使用)

        Returns:
            weights: {stock: weight}
        """
        if self.config.n_stocks > 0:
            selected = self.selector.top_n(scores, self.config.n_stocks)
        else:
            selected = list(scores.index)

        selected_scores = scores[selected]

        weighting_method = self.config.weighting
        if weighting_method == "equal":
            weights = self.allocator.equal_weight(selected)
        elif weighting_method == "probability":
            weights = self.allocator.score_weighted(selected, selected_scores)
        elif weighting_method == "rank":
            weights = self.allocator.rank_weighted(selected, selected_scores)
        elif weighting_method == "risk_parity" and volatilities is not None:
            weights = self.allocator.risk_parity(selected, volatilities)
        elif weighting_method == "vol_adjusted" and volatilities is not None:
            weights = self.allocator.volatility_adjusted(
                selected, selected_scores, volatilities
            )
        else:
            weights = self.allocator.equal_weight(selected)

        return weights

    def rebalance(self, new_weights: Dict[str, float]) -> Dict[str, dict]:
        """执行调仓

        Args:
            new_weights: 目标组合权重

        Returns:
            trades: {"buy": {stock: weight}, "sell": [stock], "hold": {stock: weight}}
        """
        return self.rebalancer.rebalance(new_weights)
