"""Missing value imputation for factor preprocessing."""
from __future__ import annotations
from typing import List, Optional, Literal
import pandas as pd
import numpy as np


FillMethod = Literal["mean", "median", "zero"]


def fill_missing_by_group(
    df: pd.DataFrame,
    factor_cols: List[str],
    group_col: Optional[str] = None,
    method: FillMethod = "median"
) -> pd.DataFrame:
    """按组填充缺失值

    当 group_col 为 None 时，对整个截面进行填充。
    当 group_col 指定时，按组分别计算统计量并填充，避免跨组污染。

    Args:
        df: 输入数据框，需包含 factor_cols 和 group_col
        factor_cols: 需要填充的因子列名列表
        group_col: 分组列名（如 'industry'），None 表示整体填充
        method: 填充方法 ("mean", "median", "zero")

    Returns:
        填充后的数据框（副本）

    Example:
        >>> df = fill_missing_by_group(
        ...     raw_df,
        ...     factor_cols=["roe", "pe", "pb"],
        ...     group_col="industry",
        ...     method="median"
        ... )
    """
    result = df.copy()

    # 只处理实际存在的列
    valid_cols = [c for c in factor_cols if c in result.columns]
    if not valid_cols:
        return result

    if group_col is not None and group_col in result.columns:
        # 按组填充
        for col in valid_cols:
            if method == "zero":
                # 简单填充0
                result[col] = result.groupby(group_col)[col].transform(
                    lambda x: x.fillna(0)
                )
            elif method == "mean":
                result[col] = result.groupby(group_col)[col].transform(
                    lambda x: x.fillna(x.mean())
                )
            elif method == "median":
                result[col] = result.groupby(group_col)[col].transform(
                    lambda x: x.fillna(x.median())
                )
    else:
        # 整体填充
        for col in valid_cols:
            if method == "zero":
                result[col] = result[col].fillna(0)
            elif method == "mean":
                result[col] = result[col].fillna(result[col].mean())
            elif method == "median":
                result[col] = result[col].fillna(result[col].median())

    return result


def fill_missing_by_date(
    df: pd.DataFrame,
    factor_cols: List[str],
    date_col: str = "date",
    method: FillMethod = "median"
) -> pd.DataFrame:
    """按日期截面填充缺失值

    适用于 MultiIndex 或含日期列的数据框，在每个截面（日期）内
    分别计算统计量并填充。

    Args:
        df: 输入数据框
        factor_cols: 需要填充的因子列名列表
        date_col: 日期列名，默认 "date"
        method: 填充方法

    Returns:
        填充后的数据框（副本）
    """
    result = df.copy()
    valid_cols = [c for c in factor_cols if c in result.columns]

    if date_col not in result.columns:
        # 没有日期列，退化为整体填充
        return fill_missing_by_group(result, valid_cols, None, method)

    for col in valid_cols:
        if method == "zero":
            result[col] = result.groupby(date_col)[col].transform(
                lambda x: x.fillna(0)
            )
        elif method == "mean":
            result[col] = result.groupby(date_col)[col].transform(
                lambda x: x.fillna(x.mean())
            )
        elif method == "median":
            result[col] = result.groupby(date_col)[col].transform(
                lambda x: x.fillna(x.median())
            )

    return result
