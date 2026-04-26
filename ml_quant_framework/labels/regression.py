import numpy as np
import pandas as pd

from ml_quant_framework.core.registry import LABEL_REGISTRY


@LABEL_REGISTRY.register("raw_return")
class RawReturnLabelBuilder:
    """原始收益率标签。"""

    def build(self, returns: pd.Series) -> pd.Series:
        """构建原始收益率标签。

        Args:
            returns: 股票收益率 Series, index=stocks。

        Returns:
            labels: 原始收益率 Series, index=stocks。
        """
        return returns.copy()


@LABEL_REGISTRY.register("log_return")
class LogReturnLabelBuilder:
    """对数收益率标签。"""

    def build(self, returns: pd.Series) -> pd.Series:
        """构建对数收益率标签。

        Args:
            returns: 股票收益率 Series, index=stocks。

        Returns:
            labels: 对数收益率 Series, index=stocks。
        """
        return np.log(1 + returns)


@LABEL_REGISTRY.register("rank_return")
class RankReturnLabelBuilder:
    """排名收益率标签。"""

    def build(self, returns: pd.Series) -> pd.Series:
        """构建排名收益率标签（百分比排名）。

        Args:
            returns: 股票收益率 Series, index=stocks。

        Returns:
            labels: 百分比排名 Series, index=stocks, values=[0, 1]。
        """
        return returns.rank(pct=True)


@LABEL_REGISTRY.register("winsorized_return")
class WinsorizedReturnLabelBuilder:
    """去极值后的收益率标签。"""

    def __init__(self, scale: float = 3.0):
        self.scale = scale

    def build(self, returns: pd.Series) -> pd.Series:
        """构建去极值后的收益率标签（MAD方法）。

        Args:
            returns: 股票收益率 Series, index=stocks。

        Returns:
            labels: 去极值后收益率 Series, index=stocks。
        """
        median = returns.median()
        mad = (returns - median).abs().median()
        upper = median + self.scale * mad
        lower = median - self.scale * mad
        return returns.clip(lower, upper)
