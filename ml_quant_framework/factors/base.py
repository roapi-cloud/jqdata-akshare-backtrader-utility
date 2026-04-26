from abc import abstractmethod
from typing import List, Optional
import pandas as pd
from datetime import date

from ml_quant_framework.core.base import BaseFactor


class Factor(BaseFactor):
    """因子基类 - 所有因子的基础。

    扩展 core.BaseFactor，提供简化的因子计算接口。
    子类需实现 compute 方法来计算特定因子值。
    """

    def __init__(self, name: str = None, params: dict = None):
        factor_name = name or self.__class__.__name__
        super().__init__(name=factor_name, config=params or {})
        self.params = params or {}

    @abstractmethod
    def compute(self, stocks: List[str], date: date, data_manager) -> pd.Series:
        """计算因子值。

        Args:
            stocks: 股票代码列表。
            date: 计算日期。
            data_manager: 数据管理器实例。

        Returns:
            pd.Series, index=stocks, values=factor_values.
        """
        pass

    def validate(self, stocks: List[str], date: date, data_manager) -> bool:
        """验证因子是否可计算。

        Args:
            stocks: 股票代码列表。
            date: 计算日期。
            data_manager: 数据管理器实例。

        Returns:
            是否可计算。
        """
        return True
