import pandas as pd

from ml_quant_framework.core.registry import LABEL_REGISTRY


@LABEL_REGISTRY.register("quantile")
class QuantileLabelBuilder:
    """分位数标签: 按收益分N组, 标签1-N。"""

    def __init__(self, n_groups: int = 5):
        self.n_groups = n_groups

    def build(self, returns: pd.Series) -> pd.Series:
        """构建分位数标签。

        Args:
            returns: 股票收益率 Series, index=stocks。

        Returns:
            labels: 分位数标签 Series, index=stocks, values={1, 2, ..., N}。
        """
        return pd.qcut(returns, self.n_groups, labels=False, duplicates="drop") + 1


@LABEL_REGISTRY.register("percentile_rank")
class PercentileRankLabelBuilder:
    """百分位排名标签 [0, 1]。"""

    def build(self, returns: pd.Series) -> pd.Series:
        """构建百分位排名标签。

        Args:
            returns: 股票收益率 Series, index=stocks。

        Returns:
            labels: 百分位排名 Series, index=stocks, values=[0, 1]。
        """
        return returns.rank(pct=True)
