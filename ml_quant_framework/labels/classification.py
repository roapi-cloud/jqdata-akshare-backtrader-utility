import numpy as np
import pandas as pd

from ml_quant_framework.core.registry import LABEL_REGISTRY


@LABEL_REGISTRY.register("top_bottom")
class TopBottomLabelBuilder:
    """Top/Bottom分类标签 - 最常用。

    前top_pct标记为1(赢家), 后bottom_pct标记为0(输家), 中间剔除。
    """

    def __init__(self, top_pct: float = 0.3, bottom_pct: float = 0.3):
        self.top_pct = top_pct
        self.bottom_pct = bottom_pct

    def build(self, returns: pd.Series) -> pd.Series:
        """构建分类标签。

        Args:
            returns: 股票收益率 Series, index=stocks。

        Returns:
            labels: 标签 Series, index=stocks, values={0, 1}。
        """
        returns = returns.sort_values(ascending=False)
        n = len(returns)
        n_top = int(n * self.top_pct)
        n_bottom = int(n * self.bottom_pct)

        labels = pd.Series(np.nan, index=returns.index, name="label")
        labels.iloc[:n_top] = 1
        labels.iloc[-n_bottom:] = 0
        return labels.dropna()


@LABEL_REGISTRY.register("triple")
class TripleLabelBuilder:
    """三分类标签: Top=1, Mid=0, Bottom=-1。"""

    def __init__(self, top_pct: float = 0.3, bottom_pct: float = 0.3):
        self.top_pct = top_pct
        self.bottom_pct = bottom_pct

    def build(self, returns: pd.Series) -> pd.Series:
        """构建三分类标签。

        Args:
            returns: 股票收益率 Series, index=stocks。

        Returns:
            labels: 标签 Series, index=stocks, values={-1, 0, 1}。
        """
        returns = returns.sort_values(ascending=False)
        n = len(returns)
        n_top = int(n * self.top_pct)
        n_bottom = int(n * self.bottom_pct)

        labels = pd.Series(0, index=returns.index, name="label")
        labels.iloc[:n_top] = 1
        labels.iloc[-n_bottom:] = -1
        return labels


@LABEL_REGISTRY.register("binary_threshold")
class BinaryThresholdLabelBuilder:
    """阈值二分类: 收益率>阈值为1, 否则为0。"""

    def __init__(self, threshold: float = 0.0):
        self.threshold = threshold

    def build(self, returns: pd.Series) -> pd.Series:
        """构建阈值二分类标签。

        Args:
            returns: 股票收益率 Series, index=stocks。

        Returns:
            labels: 标签 Series, index=stocks, values={0, 1}。
        """
        return (returns > self.threshold).astype(int)
