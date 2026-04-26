import numpy as np
import pandas as pd

from ml_quant_framework.core.registry import PREPROCESSOR_REGISTRY


@PREPROCESSOR_REGISTRY.register("mad")
class MADWinsorize:
    """中位数去极值法 (Median Absolute Deviation)。

    基于中位数和绝对中位差(MAD)对异常值进行缩尾处理，
    对极端值具有鲁棒性。

    Attributes:
        scale: MAD的缩放倍数，默认5.0。
    """

    def __init__(self, scale: float = 5.0) -> None:
        self.scale = scale

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """对DataFrame每列进行MAD去极值。

        Args:
            df: 输入因子数据框，行为样本，列为因子。

        Returns:
            去极值后的数据框。
        """
        median = df.median()
        mad = (df - median).abs().median()
        upper = median + self.scale * mad
        lower = median - self.scale * mad
        return df.clip(lower, upper, axis=1)


@PREPROCESSOR_REGISTRY.register("3sigma")
class SigmaWinsorize:
    """3σ去极值法。

    基于均值和标准差对异常值进行缩尾处理，
    适用于近似正态分布的数据。

    Attributes:
        scale: 标准差的缩放倍数，默认3.0。
    """

    def __init__(self, scale: float = 3.0) -> None:
        self.scale = scale

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """对DataFrame每列进行3σ去极值。

        Args:
            df: 输入因子数据框，行为样本，列为因子。

        Returns:
            去极值后的数据框。
        """
        mean = df.mean()
        std = df.std()
        upper = mean + self.scale * std
        lower = mean - self.scale * std
        return df.clip(lower, upper, axis=1)


@PREPROCESSOR_REGISTRY.register("percentile")
class PercentileWinsorize:
    """百分位去极值法。

    基于指定百分位数对异常值进行缩尾处理，
    不依赖分布假设。

    Attributes:
        lower_pct: 下界百分位，默认0.01。
        upper_pct: 上界百分位，默认0.99。
    """

    def __init__(self, lower_pct: float = 0.01, upper_pct: float = 0.99) -> None:
        self.lower_pct = lower_pct
        self.upper_pct = upper_pct

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """对DataFrame每列进行百分位去极值。

        Args:
            df: 输入因子数据框，行为样本，列为因子。

        Returns:
            去极值后的数据框。
        """
        lower = df.quantile(self.lower_pct)
        upper = df.quantile(self.upper_pct)
        return df.clip(lower, upper, axis=1)
