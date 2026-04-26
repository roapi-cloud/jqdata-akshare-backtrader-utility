import numpy as np
import pandas as pd
import statsmodels.api as sm

from ml_quant_framework.core.registry import PREPROCESSOR_REGISTRY


@PREPROCESSOR_REGISTRY.register("industry_market_cap")
class IndustryMarketCapNeutralization:
    """行业 + 市值中性化。

    通过横截面回归剔除因子中的行业效应和市值效应，
    使因子值不受行业和市值规模的影响。

    Attributes:
        min_samples: 回归所需的最小样本数，默认10。
    """

    def __init__(self, min_samples: int = 10) -> None:
        self.min_samples = min_samples

    def transform(
        self,
        df: pd.DataFrame,
        industries: pd.Series = None,
        market_cap: pd.Series = None,
        **kwargs,
    ) -> pd.DataFrame:
        """执行行业+市值中性化。

        Args:
            df: 输入因子数据框，行为样本，列为因子。
            industries: 行业分类序列。
            market_cap: 市值序列。

        Returns:
            中性化后的数据框，值为回归残差。
        """
        if industries is None and market_cap is None:
            return df

        X_parts = []
        if industries is not None:
            industry_dummies = pd.get_dummies(industries, prefix="ind")
            X_parts.append(industry_dummies)
        if market_cap is not None:
            X_parts.append(
                pd.DataFrame({"ln_mv": np.log(market_cap)}, index=market_cap.index)
            )

        X = pd.concat(X_parts, axis=1)
        X = sm.add_constant(X)

        result = df.copy()
        for col in df.columns:
            y = df[col]
            valid = y.notnull() & X.notnull().all(axis=1)
            if valid.sum() > self.min_samples:
                try:
                    res = sm.OLS(y[valid], X.loc[valid]).fit()
                    result[col] = res.resid
                except Exception:
                    pass

        return result


@PREPROCESSOR_REGISTRY.register("industry_only")
class IndustryNeutralization:
    """仅行业中性化。

    通过横截面回归剔除因子中的行业效应，
    保留其他特征信息。
    """

    def transform(
        self, df: pd.DataFrame, industries: pd.Series = None, **kwargs
    ) -> pd.DataFrame:
        """执行行业中性化。

        Args:
            df: 输入因子数据框，行为样本，列为因子。
            industries: 行业分类序列。

        Returns:
            中性化后的数据框，值为回归残差。
        """
        if industries is None:
            return df

        industry_dummies = pd.get_dummies(industries, prefix="ind")
        X = sm.add_constant(industry_dummies)

        result = df.copy()
        for col in df.columns:
            y = df[col]
            valid = y.notnull() & X.notnull().all(axis=1)
            if valid.sum() > 10:
                try:
                    res = sm.OLS(y[valid], X.loc[valid]).fit()
                    result[col] = res.resid
                except Exception:
                    pass

        return result


@PREPROCESSOR_REGISTRY.register("market_cap_only")
class MarketCapNeutralization:
    """仅市值中性化。

    通过横截面回归剔除因子中的市值效应，
    消除市值大小对因子的影响。
    """

    def transform(
        self, df: pd.DataFrame, market_cap: pd.Series = None, **kwargs
    ) -> pd.DataFrame:
        """执行市值中性化。

        Args:
            df: 输入因子数据框，行为样本，列为因子。
            market_cap: 市值序列。

        Returns:
            中性化后的数据框，值为回归残差。
        """
        if market_cap is None:
            return df

        X = sm.add_constant(
            pd.DataFrame({"ln_mv": np.log(market_cap)}, index=market_cap.index)
        )

        result = df.copy()
        for col in df.columns:
            y = df[col]
            valid = y.notnull() & X.notnull().all(axis=1)
            if valid.sum() > 10:
                try:
                    res = sm.OLS(y[valid], X.loc[valid]).fit()
                    result[col] = res.resid
                except Exception:
                    pass

        return result
