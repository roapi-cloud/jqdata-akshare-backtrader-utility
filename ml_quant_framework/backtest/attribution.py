"""分层回测与归因模块。

按预测分数分组检验单调性，验证模型区分能力。
"""

import pandas as pd
import numpy as np
from typing import Dict, List


class StratifiedBacktester:
    """分层回测器。

    按预测分数分组检验单调性，好的模型应该呈现
    Group1 > Group2 > ... > GroupN 的收益递减规律。
    """

    @staticmethod
    def group_returns(
        df: pd.DataFrame,
        score_col: str = "predict",
        return_col: str = "return",
        n_groups: int = 5,
    ) -> pd.DataFrame:
        """分层计算每组收益。

        Args:
            df: 包含预测分数和实际收益的 DataFrame。
            score_col: 预测分数列名。
            return_col: 实际收益列名。
            n_groups: 分组数。

        Returns:
            每组收益的统计 DataFrame。
        """
        df = df.copy()
        df["group"] = pd.qcut(df[score_col], n_groups, labels=False, duplicates="drop")

        group_stats = df.groupby("group").agg(
            {return_col: ["mean", "std", "count"], score_col: ["mean", "min", "max"]}
        )
        group_stats.columns = [
            "mean_return",
            "std_return",
            "n_stocks",
            "mean_score",
            "min_score",
            "max_score",
        ]
        return group_stats

    @staticmethod
    def group_cumulative_returns(
        group_returns: pd.DataFrame, periods_per_year: int = 12
    ) -> pd.Series:
        """计算每组累计收益。

        Args:
            group_returns: 分层收益统计 DataFrame。
            periods_per_year: 每年期数。

        Returns:
            每组累计收益序列。
        """
        cum_returns = (1 + group_returns["mean_return"]).cumprod()
        return cum_returns

    @staticmethod
    def monotonicity_test(group_returns: pd.DataFrame) -> Dict:
        """单调性检验。

        检验好的模型是否满足 Group1 > Group2 > ... > GroupN。

        Args:
            group_returns: 分层收益统计 DataFrame。

        Returns:
            包含单调性检验结果的字典。
        """
        returns = group_returns["mean_return"].values
        is_monotonic = all(
            returns[i] >= returns[i + 1] for i in range(len(returns) - 1)
        )

        # 计算多空收益 (Top组 - Bottom组)
        long_short_return = returns[0] - returns[-1]

        return {
            "is_monotonic": is_monotonic,
            "long_short_return": long_short_return,
            "top_group_return": returns[0],
            "bottom_group_return": returns[-1],
        }

    @staticmethod
    def run_full_stratified(
        df: pd.DataFrame,
        n_groups: int = 5,
        score_col: str = "predict",
        return_col: str = "return",
    ) -> Dict:
        """执行完整分层回测。

        Args:
            df: 包含预测分数和实际收益的 DataFrame。
            n_groups: 分组数。
            score_col: 预测分数列名。
            return_col: 实际收益列名。

        Returns:
            包含分组统计和单调性检验结果的字典。
        """
        group_stats = StratifiedBacktester.group_returns(
            df, score_col, return_col, n_groups
        )
        mono_result = StratifiedBacktester.monotonicity_test(group_stats)

        return {
            "group_stats": group_stats,
            "monotonicity": mono_result,
        }
