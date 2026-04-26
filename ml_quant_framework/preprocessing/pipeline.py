from typing import Optional

import pandas as pd

from ml_quant_framework.core.config import PreprocessConfig


class PreprocessingPipeline:
    """预处理流水线编排器。

    按照量化因子预处理标准流程依次执行：
    去极值 → 缺失值填充 → 中性化 → 标准化。

    通过PreprocessConfig配置各步骤的方法与参数，
    自动构建并执行预处理步骤链。

    Attributes:
        config: 预处理配置对象。
        steps: 预处理步骤列表，每项为(步骤名, 处理器实例)元组。
    """

    def __init__(self, config: Optional[PreprocessConfig] = None) -> None:
        self.config = config or PreprocessConfig()
        self._build_steps()

    def _build_steps(self) -> None:
        """根据配置构建预处理步骤链。"""
        from .imputation import IndustryMeanImputation, MedianImputation
        from .neutralize import (
            IndustryMarketCapNeutralization,
            IndustryNeutralization,
            MarketCapNeutralization,
        )
        from .standardize import ZScoreStandardize
        from .winsorize import MADWinsorize, PercentileWinsorize, SigmaWinsorize

        self.steps = []

        if self.config.winsorize_method == "mad":
            self.steps.append(("winsorize", MADWinsorize(self.config.winsorize_scale)))
        elif self.config.winsorize_method == "3sigma":
            self.steps.append(
                ("winsorize", SigmaWinsorize(self.config.winsorize_scale))
            )
        elif self.config.winsorize_method == "percentile":
            self.steps.append(("winsorize", PercentileWinsorize()))

        if self.config.fill_method == "industry_mean":
            self.steps.append(("imputation", IndustryMeanImputation()))
        elif self.config.fill_method == "median":
            self.steps.append(("imputation", MedianImputation()))

        if (
            "industry" in self.config.neutralize_by
            and "market_cap" in self.config.neutralize_by
        ):
            self.steps.append(("neutralize", IndustryMarketCapNeutralization()))
        elif "industry" in self.config.neutralize_by:
            self.steps.append(("neutralize", IndustryNeutralization()))
        elif "market_cap" in self.config.neutralize_by:
            self.steps.append(("neutralize", MarketCapNeutralization()))

        if self.config.standardize:
            self.steps.append(("standardize", ZScoreStandardize()))

    def transform(
        self,
        df: pd.DataFrame,
        industries: Optional[pd.Series] = None,
        market_cap: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        """执行完整预处理流程。

        按顺序执行去极值、缺失值填充、中性化和标准化步骤。

        Args:
            df: 输入因子数据框，行为样本，列为因子。
            industries: 行业分类序列，用于行业均值填充和行业中性化。
            market_cap: 市值序列，用于市值中性化。

        Returns:
            预处理后的数据框。
        """
        result = df.copy()
        for name, step in self.steps:
            if name == "imputation":
                result = step.transform(result, industries=industries)
            elif name == "neutralize":
                result = step.transform(
                    result, industries=industries, market_cap=market_cap
                )
            else:
                result = step.transform(result)
        return result

    def fit_transform(
        self,
        df: pd.DataFrame,
        industries: Optional[pd.Series] = None,
        market_cap: Optional[pd.Series] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """拟合并执行预处理流程。

        对于当前无状态预处理器，等同于transform。

        Args:
            df: 输入因子数据框。
            industries: 行业分类序列。
            market_cap: 市值序列。
            **kwargs: 其他参数。

        Returns:
            预处理后的数据框。
        """
        return self.transform(df, industries=industries, market_cap=market_cap)
