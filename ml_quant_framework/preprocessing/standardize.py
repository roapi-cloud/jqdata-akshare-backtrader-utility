import pandas as pd

from ml_quant_framework.core.registry import PREPROCESSOR_REGISTRY


@PREPROCESSOR_REGISTRY.register("zscore")
class ZScoreStandardize:
    """Z-Score标准化。

    将因子值转换为均值为0、标准差为1的标准正态分布，
    是最常用的标准化方法。
    """

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行Z-Score标准化。

        Args:
            df: 输入因子数据框，行为样本，列为因子。

        Returns:
            标准化后的数据框。
        """
        mean = df.mean()
        std = df.std()
        std = std.replace(0, 1)
        return (df - mean) / std


@PREPROCESSOR_REGISTRY.register("minmax")
class MinMaxStandardize:
    """Min-Max标准化。

    将因子值线性缩放到[0, 1]区间，
    保留原始分布的相对关系。
    """

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行Min-Max标准化。

        Args:
            df: 输入因子数据框，行为样本，列为因子。

        Returns:
            标准化后的数据框，值域为[0, 1]。
        """
        min_val = df.min()
        max_val = df.max()
        range_val = max_val - min_val
        range_val = range_val.replace(0, 1)
        return (df - min_val) / range_val


@PREPROCESSOR_REGISTRY.register("rank")
class RankStandardize:
    """排名标准化。

    将因子值转换为百分位排名，
    消除极端值影响，得到均匀分布。
    """

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行排名标准化。

        Args:
            df: 输入因子数据框，行为样本，列为因子。

        Returns:
            标准化后的数据框，值为百分位排名(0, 1)。
        """
        return df.rank(pct=True)
