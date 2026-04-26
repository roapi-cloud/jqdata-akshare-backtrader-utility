import pandas as pd
import numpy as np
from typing import List, Optional


class StockSelector:
    """选股器

    提供多种选股方法，包括Top-N、百分比、阈值和分位数过滤。
    """

    @staticmethod
    def top_n(scores: pd.Series, n: int = 5) -> List[str]:
        """选择得分最高的N只股票

        Args:
            scores: 预测得分 Series, index=stocks
            n: 选股数量

        Returns:
            股票代码列表
        """
        return scores.nlargest(n).index.tolist()

    @staticmethod
    def top_pct(scores: pd.Series, pct: float = 0.1) -> List[str]:
        """选择得分前pct%的股票

        Args:
            scores: 预测得分 Series, index=stocks
            pct: 选股比例 (0-1)

        Returns:
            股票代码列表
        """
        n = max(1, int(len(scores) * pct))
        return scores.nlargest(n).index.tolist()

    @staticmethod
    def threshold(scores: pd.Series, threshold: float = 0.6) -> List[str]:
        """选择得分超过阈值的股票

        Args:
            scores: 预测得分 Series, index=stocks
            threshold: 最低得分阈值

        Returns:
            股票代码列表
        """
        return scores[scores >= threshold].index.tolist()

    @staticmethod
    def quantile_filter(scores: pd.Series, quantile: float = 0.8) -> List[str]:
        """选择得分超过指定分位数的股票

        Args:
            scores: 预测得分 Series, index=stocks
            quantile: 分位数阈值 (0-1)

        Returns:
            股票代码列表
        """
        cutoff = scores.quantile(quantile)
        return scores[scores >= cutoff].index.tolist()

    @staticmethod
    def filter_by_conditions(
        scores: pd.Series,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        exclude: Optional[List[str]] = None,
    ) -> List[str]:
        """多条件过滤

        Args:
            scores: 预测得分 Series, index=stocks
            min_score: 最低得分
            max_score: 最高得分
            exclude: 需要排除的股票代码列表

        Returns:
            股票代码列表
        """
        result = scores.copy()
        if min_score is not None:
            result = result[result >= min_score]
        if max_score is not None:
            result = result[result <= max_score]
        if exclude:
            result = result.drop(exclude, errors="ignore")
        return result.index.tolist()
