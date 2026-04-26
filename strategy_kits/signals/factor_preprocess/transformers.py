"""Outlier handling and standardization for factor preprocessing."""
from __future__ import annotations
from typing import List, Optional, Literal, Tuple
import pandas as pd
import numpy as np


WinsorizeMethod = Literal["mad", "quantile", "std"]
StandardizeMethod = Literal["zscore", "rank", "minmax"]


def winsorize_features(
    df: pd.DataFrame,
    factor_cols: List[str],
    method: WinsorizeMethod = "mad",
    n_mad: float = 3.0,
    quantile_limits: Tuple[float, float] = (0.01, 0.99),
    n_std: float = 3.0,
) -> pd.DataFrame:
    """去极值处理

    支持三种去极值方法:
    - mad: 使用 MAD (Median Absolute Deviation) 方法，稳健去极值
    - quantile: 使用分位数裁剪，简单直接
    - std: 使用标准差倍数裁剪

    Args:
        df: 输入数据框
        factor_cols: 需要去极值的因子列名列表
        method: 去极值方法 ("mad", "quantile", "std")
        n_mad: MAD 方法的倍数（默认 3）
        quantile_limits: 分位数方法的上下限，默认 (0.01, 0.99)
        n_std: 标准差方法的倍数（默认 3）

    Returns:
        去极值后的数据框（副本）

    Example:
        >>> df = winsorize_features(
        ...     raw_df,
        ...     factor_cols=["roe", "pe", "pb"],
        ...     method="mad",
        ...     n_mad=3.0
        ... )
    """
    result = df.copy()
    valid_cols = [c for c in factor_cols if c in result.columns]

    for col in valid_cols:
        series = result[col]

        if method == "mad":
            # MAD 方法: median ± n * 1.4826 * MAD
            median = series.median()
            mad = ((series - median).abs()).median()
            lower = median - n_mad * 1.4826 * mad
            upper = median + n_mad * 1.4826 * mad

        elif method == "quantile":
            # 分位数裁剪
            lower = series.quantile(quantile_limits[0])
            upper = series.quantile(quantile_limits[1])

        elif method == "std":
            # 标准差方法
            mean = series.mean()
            std = series.std()
            lower = mean - n_std * std
            upper = mean + n_std * std

        else:
            raise ValueError(f"Unknown method: {method}")

        result[col] = series.clip(lower=lower, upper=upper)

    return result


def standardize_features(
    df: pd.DataFrame,
    factor_cols: List[str],
    group_col: Optional[str] = None,
    method: StandardizeMethod = "zscore",
) -> pd.DataFrame:
    """标准化处理

    支持三种标准化方法:
    - zscore: Z-score 标准化 (x - mean) / std
    - rank: 排名标准化 (转换为 0-1 分位数)
    - minmax: Min-Max 标准化 (x - min) / (max - min)

    支持分组标准化（如行业中性化），在组内分别计算统计量。

    Args:
        df: 输入数据框
        factor_cols: 需要标准化的因子列名列表
        group_col: 分组列名（如 'industry'），None 表示整体标准化
        method: 标准化方法 ("zscore", "rank", "minmax")

    Returns:
        标准化后的数据框（副本）

    Example:
        >>> # 整体 Z-score 标准化
        >>> df = standardize_features(df, ["roe", "pe"], method="zscore")
        >>> # 行业中性化（组内 Z-score）
        >>> df = standardize_features(
        ...     df, ["roe", "pe"],
        ...     group_col="industry",
        ...     method="zscore"
        ... )
    """
    result = df.copy()
    valid_cols = [c for c in factor_cols if c in result.columns]

    if group_col is not None and group_col in result.columns:
        # 分组标准化
        for col in valid_cols:
            if method == "zscore":
                result[col] = result.groupby(group_col)[col].transform(
                    lambda x: (x - x.mean()) / (x.std() if x.std() > 1e-12 else 1)
                )
            elif method == "rank":
                # 排名标准化到 [0, 1]
                result[col] = result.groupby(group_col)[col].transform(
                    lambda x: x.rank(pct=True) if len(x) > 1 else x
                )
            elif method == "minmax":
                result[col] = result.groupby(group_col)[col].transform(
                    lambda x: (x - x.min()) / (x.max() - x.min())
                    if x.max() != x.min() else 0
                )
    else:
        # 整体标准化
        for col in valid_cols:
            if method == "zscore":
                mean = result[col].mean()
                std = result[col].std()
                result[col] = (result[col] - mean) / (std if std > 1e-12 else 1)
            elif method == "rank":
                result[col] = result[col].rank(pct=True)
            elif method == "minmax":
                min_val = result[col].min()
                max_val = result[col].max()
                if max_val != min_val:
                    result[col] = (result[col] - min_val) / (max_val - min_val)
                else:
                    result[col] = 0

    return result


def neutralize_features(
    df: pd.DataFrame,
    factor_cols: List[str],
    neutralize_cols: List[str],
) -> pd.DataFrame:
    """中性化处理（回归残差法）

    将因子对中性化变量（如行业、市值）做回归，取残差作为中性化后的因子值。

    Args:
        df: 输入数据框
        factor_cols: 需要中性化的因子列名列表
        neutralize_cols: 中性化变量列名列表（如 ["market_cap", "industry"])

    Returns:
        中性化后的数据框（副本）
    """
    result = df.copy()
    valid_factor_cols = [c for c in factor_cols if c in result.columns]
    valid_neutral_cols = [c for c in neutralize_cols if c in result.columns]

    if not valid_neutral_cols:
        return result

    # 构建中性化矩阵 X
    X_cols = []
    for col in valid_neutral_cols:
        if result[col].dtype == "object" or result[col].dtype.name == "category":
            # 类别变量进行 one-hot 编码
            dummies = pd.get_dummies(result[col], prefix=col, drop_first=True)
            X_cols.extend(dummies.columns.tolist())
            result = pd.concat([result, dummies], axis=1)
        else:
            X_cols.append(col)

    if not X_cols:
        return result

    X = result[X_cols].fillna(0).values

    # 对每个因子进行回归取残差
    for col in valid_factor_cols:
        y = result[col].fillna(0).values
        # 添加常数项
        X_with_const = np.column_stack([np.ones(len(X)), X])
        # 最小二乘求解
        try:
            beta = np.linalg.lstsq(X_with_const, y, rcond=None)[0]
            residual = y - X_with_const @ beta
            result[col] = residual
        except np.linalg.LinAlgError:
            # 回归失败，保持原值
            pass

    return result
