from datetime import date
from typing import Any, Dict, List

import pandas as pd

from ml_quant_framework.core.config import LabelConfig
from ml_quant_framework.data.base import DataSource


class LabelManager:
    """标签构建管理器。

    根据配置选择标签构建方法，管理从收益率计算到标签生成的完整流程。
    """

    def __init__(self, config: LabelConfig):
        self.config = config
        self.builder = self._get_builder()

    def _get_builder(self) -> Any:
        """根据配置获取对应的标签构建器实例。

        Returns:
            标签构建器实例。
        """
        from ml_quant_framework.labels.classification import (
            BinaryThresholdLabelBuilder,
            TopBottomLabelBuilder,
            TripleLabelBuilder,
        )
        from ml_quant_framework.labels.ranking import (
            PercentileRankLabelBuilder,
            QuantileLabelBuilder,
        )
        from ml_quant_framework.labels.regression import (
            LogReturnLabelBuilder,
            RawReturnLabelBuilder,
            RankReturnLabelBuilder,
            WinsorizedReturnLabelBuilder,
        )

        builders = {
            "top_bottom": lambda: TopBottomLabelBuilder(
                self.config.top_pct, self.config.bottom_pct
            ),
            "triple": lambda: TripleLabelBuilder(
                self.config.top_pct, self.config.bottom_pct
            ),
            "binary_threshold": lambda: BinaryThresholdLabelBuilder(),
            "raw_return": RawReturnLabelBuilder,
            "log_return": LogReturnLabelBuilder,
            "rank_return": RankReturnLabelBuilder,
            "winsorized_return": lambda: WinsorizedReturnLabelBuilder(),
            "quantile": lambda: QuantileLabelBuilder(),
            "percentile_rank": PercentileRankLabelBuilder,
        }
        return builders.get(self.config.method, builders["top_bottom"])()

    def compute_returns(
        self,
        stocks: List[str],
        date: date,
        next_date: date,
        data_manager: DataSource,
    ) -> pd.Series:
        """计算持有期收益率。

        Args:
            stocks: 股票代码列表。
            date: 起始日期。
            next_date: 结束日期。
            data_manager: 数据源管理器。

        Returns:
            收益率 Series, index=stocks。
        """
        prices = data_manager.get_price(
            stocks, start_date=date, end_date=next_date, fields=["close"]
        )

        if isinstance(prices, pd.DataFrame) and "code" in prices.columns:
            ret = prices.groupby("code")["close"].apply(
                lambda x: x.iloc[-1] / x.iloc[0] - 1
            )
        else:
            ret = prices["close"].iloc[-1] / prices["close"].iloc[0] - 1
        return ret

    def build(
        self,
        stocks: List[str],
        date: date,
        next_date: date,
        data_manager: DataSource,
    ) -> pd.Series:
        """完整标签构建流程。

        Args:
            stocks: 股票代码列表。
            date: 起始日期。
            next_date: 结束日期。
            data_manager: 数据源管理器。

        Returns:
            标签 Series, index=stocks。
        """
        returns = self.compute_returns(stocks, date, next_date, data_manager)
        return self.builder.build(returns)

    def build_labels_for_dates(
        self, dates: List[date], data_manager: DataSource
    ) -> Dict[date, pd.Series]:
        """为多个日期构建标签 (用于训练集)。

        Args:
            dates: 日期列表。
            data_manager: 数据源管理器。

        Returns:
            标签字典，key=日期, value=标签 Series。
        """
        labels_dict: Dict[date, pd.Series] = {}
        for i, current_date in enumerate(dates[:-1]):
            next_date = dates[i + 1]
            try:
                labels = self.build([], current_date, next_date, data_manager)
                labels_dict[current_date] = labels
            except Exception as e:
                print(f"Warning: Failed to build labels for {current_date}: {e}")
        return labels_dict
