import pandas as pd

from ml_quant_framework.core.registry import PREPROCESSOR_REGISTRY


@PREPROCESSOR_REGISTRY.register("industry_mean")
class IndustryMeanImputation:
    """行业均值填充缺失值。

    按行业分组计算因子均值进行填充，
    保留行业特征信息。

    Attributes:
        industry_field: 行业字段名称，默认"industry"。
    """

    def __init__(self, industry_field: str = "industry") -> None:
        self.industry_field = industry_field

    def transform(
        self, df: pd.DataFrame, industries: pd.Series = None, **kwargs
    ) -> pd.DataFrame:
        """使用行业均值填充缺失值。

        Args:
            df: 输入因子数据框，行为样本，列为因子。
            industries: 行业分类序列，索引与df对齐。

        Returns:
            填充后的数据框。
        """
        if industries is None or self.industry_field not in df.columns:
            return df.fillna(df.mean())

        result = df.copy()
        for col in df.columns:
            if col == self.industry_field:
                continue
            group_mean = df.groupby(industries)[col].transform("mean")
            result[col] = df[col].fillna(group_mean)

        return result.fillna(result.mean())


@PREPROCESSOR_REGISTRY.register("median")
class MedianImputation:
    """中位数填充缺失值。

    使用每列的中位数填充该列的缺失值，
    对异常值具有鲁棒性。
    """

    def transform(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """使用中位数填充缺失值。

        Args:
            df: 输入因子数据框，行为样本，列为因子。

        Returns:
            填充后的数据框。
        """
        return df.fillna(df.median())


@PREPROCESSOR_REGISTRY.register("zero")
class ZeroImputation:
    """零值填充缺失值。

    将所有缺失值替换为0，
    适用于某些特定因子场景。
    """

    def transform(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """使用0填充缺失值。

        Args:
            df: 输入因子数据框，行为样本，列为因子。

        Returns:
            填充后的数据框。
        """
        return df.fillna(0)


@PREPROCESSOR_REGISTRY.register("forward_fill")
class ForwardFillImputation:
    """前向填充缺失值。

    使用时序上前一个有效值填充缺失值，
    适用于时间序列因子数据。
    """

    def transform(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """使用前向填充方法填充缺失值。

        Args:
            df: 输入因子数据框，行为样本，列为因子。

        Returns:
            填充后的数据框。
        """
        return df.fillna(method="ffill")
