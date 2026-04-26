"""因子注册辅助工具模块。

提供因子实例获取、批量计算和列表查询等便捷函数。
"""

from typing import List
import numpy as np
import pandas as pd
from datetime import date


def get_factor(name: str, **kwargs):
    """从注册中心获取因子实例。

    Args:
        name: 因子注册名称。
        **kwargs: 因子初始化参数。

    Returns:
        因子实例。

    Raises:
        KeyError: 如果因子未注册。
    """
    from ml_quant_framework.core.registry import FACTOR_REGISTRY

    factor_class = FACTOR_REGISTRY.get(name)
    return factor_class(**kwargs)


def compute_factors(
    factor_names: List[str],
    stocks: List[str],
    date: date,
    data_manager,
) -> pd.DataFrame:
    """批量计算多个因子。

    Args:
        factor_names: 因子名称列表。
        stocks: 股票代码列表。
        date: 计算日期。
        data_manager: 数据管理器实例。

    Returns:
        因子值DataFrame，index=stocks, columns=factor_names。
    """
    df = pd.DataFrame(index=stocks)
    for name in factor_names:
        try:
            factor = get_factor(name)
            df[name] = factor.compute(stocks, date, data_manager)
        except Exception as e:
            print(f"Warning: Failed to compute factor {name}: {e}")
            df[name] = np.nan
    return df


def list_available_factors() -> List[str]:
    """列出所有可用因子。

    Returns:
        已注册因子名称列表。
    """
    from ml_quant_framework.core.registry import FACTOR_REGISTRY

    return FACTOR_REGISTRY.list()
