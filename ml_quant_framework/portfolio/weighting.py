import pandas as pd
import numpy as np
from typing import List, Dict


class WeightAllocator:
    """权重分配器

    提供多种权重分配方法，包括等权、得分加权、排名加权、风险平价等。
    """

    @staticmethod
    def equal_weight(stocks: List[str]) -> Dict[str, float]:
        """等权分配

        Args:
            stocks: 股票代码列表

        Returns:
            权重字典 {stock: weight}
        """
        n = len(stocks)
        if n == 0:
            return {}
        return {s: 1.0 / n for s in stocks}

    @staticmethod
    def score_weighted(stocks: List[str], scores: pd.Series) -> Dict[str, float]:
        """按得分比例分配权重

        Args:
            stocks: 股票代码列表
            scores: 预测得分 Series

        Returns:
            权重字典 {stock: weight}
        """
        stock_scores = scores[stocks]
        total = stock_scores.sum()
        if total == 0:
            return {s: 1.0 / len(stocks) for s in stocks}
        return {s: score / total for s, score in stock_scores.items()}

    @staticmethod
    def rank_weighted(stocks: List[str], scores: pd.Series) -> Dict[str, float]:
        """按排名比例分配权重 (排名越高权重越大)

        Args:
            stocks: 股票代码列表
            scores: 预测得分 Series

        Returns:
            权重字典 {stock: weight}
        """
        stock_scores = scores[stocks]
        ranks = stock_scores.rank(ascending=False)
        n = len(stocks)
        weights = (n + 1 - ranks) / (n * (n + 1) / 2)
        return weights.to_dict()

    @staticmethod
    def risk_parity(stocks: List[str], volatilities: pd.Series) -> Dict[str, float]:
        """风险平价分配 (波动率倒数加权)

        Args:
            stocks: 股票代码列表
            volatilities: 波动率 Series

        Returns:
            权重字典 {stock: weight}
        """
        stock_vols = volatilities[stocks]
        inv_vol = 1.0 / stock_vols.replace(0, np.inf)
        inv_vol = inv_vol.replace(np.inf, 0)
        total = inv_vol.sum()
        if total == 0:
            return {s: 1.0 / len(stocks) for s in stocks}
        return {s: w / total for s, w in inv_vol.items()}

    @staticmethod
    def volatility_adjusted(
        stocks: List[str],
        scores: pd.Series,
        volatilities: pd.Series,
        lambda_vol: float = 1.0,
    ) -> Dict[str, float]:
        """波动率调整得分加权

        Args:
            stocks: 股票代码列表
            scores: 预测得分 Series
            volatilities: 波动率 Series
            lambda_vol: 波动率调整系数

        Returns:
            权重字典 {stock: weight}
        """
        stock_scores = scores[stocks]
        stock_vols = volatilities[stocks].replace(0, 1)
        adj_scores = stock_scores / (stock_vols**lambda_vol)
        adj_scores = adj_scores.clip(lower=0)
        total = adj_scores.sum()
        if total == 0:
            return {s: 1.0 / len(stocks) for s in stocks}
        return {s: w / total for s, w in adj_scores.items()}

    @staticmethod
    def max_diversification(
        stocks: List[str], cov_matrix: pd.DataFrame
    ) -> Dict[str, float]:
        """最大分散化权重 (简化版)

        Args:
            stocks: 股票代码列表
            cov_matrix: 协方差矩阵 DataFrame

        Returns:
            权重字典 {stock: weight}
        """
        stock_cov = cov_matrix.loc[stocks, stocks]
        try:
            volatilities = np.sqrt(np.diag(stock_cov))
            inv_vol = 1.0 / volatilities
            weights = inv_vol / inv_vol.sum()
            return dict(zip(stocks, weights))
        except Exception:
            return {s: 1.0 / len(stocks) for s in stocks}
