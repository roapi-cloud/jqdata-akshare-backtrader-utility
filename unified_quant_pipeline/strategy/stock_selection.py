"""选股策略 - 基于分数/因子选股"""

import logging
import pandas as pd
from typing import List, Dict
from .base import StrategyCatalog, BaseSelectionStrategy

logger = logging.getLogger(__name__)


@StrategyCatalog.register("top_n")
class TopNSelection(BaseSelectionStrategy):
    """Top N选股 - 选择分数最高的N只股票"""

    name = "top_n"

    def select_stocks(
        self,
        data: pd.DataFrame,
        date: str,
        n_stocks: int = 10,
        min_stocks: int = 5,
        score_col: str = "score",
        **kwargs,
    ) -> List[str]:
        """选择分数最高的N只股票

        Args:
            data: 截面数据
            date: 当前日期
            n_stocks: 目标选股数量
            min_stocks: 最少选股数量
            score_col: 分数字段名

        Returns:
            List[str]: 选中的股票代码列表
        """
        df = data.copy()

        if score_col not in df.columns:
            score_col = df.columns[-1]

        df = df.sort_values(score_col, ascending=False)

        n = min(n_stocks, len(df))
        n = max(n, min_stocks)

        selected = df.head(n)["code"].tolist()
        logger.info(f"[{date}] Selected {len(selected)} stocks (target: {n_stocks})")

        return selected


@StrategyCatalog.register("threshold")
class ThresholdSelection(BaseSelectionStrategy):
    """阈值选股 - 选择分数超过阈值的股票"""

    name = "threshold"

    def select_stocks(
        self,
        data: pd.DataFrame,
        date: str,
        n_stocks: int = 10,
        min_stocks: int = 5,
        score_col: str = "score",
        threshold: float = 0.5,
        **kwargs,
    ) -> List[str]:
        """选择分数超过阈值的股票

        Args:
            data: 截面数据
            date: 当前日期
            n_stocks: 目标选股数量
            min_stocks: 最少选股数量
            score_col: 分数字段名
            threshold: 分数阈值

        Returns:
            List[str]: 选中的股票代码列表
        """
        df = data.copy()

        if score_col not in df.columns:
            score_col = df.columns[-1]

        selected_df = df[df[score_col] >= threshold]
        selected_df = selected_df.sort_values(score_col, ascending=False)

        if len(selected_df) > n_stocks:
            selected_df = selected_df.head(n_stocks)

        if len(selected_df) < min_stocks:
            selected_df = df.sort_values(score_col, ascending=False).head(min_stocks)

        selected = selected_df["code"].tolist()
        logger.info(
            f"[{date}] Selected {len(selected)} stocks (threshold: {threshold})"
        )

        return selected


@StrategyCatalog.register("percentile")
class PercentileSelection(BaseSelectionStrategy):
    """分位数选股 - 选择前X%的股票"""

    name = "percentile"

    def select_stocks(
        self,
        data: pd.DataFrame,
        date: str,
        n_stocks: int = 10,
        min_stocks: int = 5,
        score_col: str = "score",
        top_pct: float = 0.1,
        **kwargs,
    ) -> List[str]:
        """选择前X%的股票

        Args:
            data: 截面数据
            date: 当前日期
            n_stocks: 目标选股数量
            min_stocks: 最少选股数量
            score_col: 分数字段名
            top_pct: 前百分之几

        Returns:
            List[str]: 选中的股票代码列表
        """
        df = data.copy()

        if score_col not in df.columns:
            score_col = df.columns[-1]

        df = df.sort_values(score_col, ascending=False)

        n = int(len(df) * top_pct)
        n = max(n, min_stocks)
        n = min(n, len(df))

        selected = df.head(n)["code"].tolist()
        logger.info(f"[{date}] Selected {len(selected)} stocks (top {top_pct * 100}%)")

        return selected
