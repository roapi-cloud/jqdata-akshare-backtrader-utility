"""Multi-factor scoring and combination methods."""
from __future__ import annotations
from typing import List, Optional, Dict, Union, Literal, Callable
from functools import wraps
import pandas as pd
import numpy as np
from scipy import stats


# 注册表，用于扩展自定义打分方法
_SCORING_REGISTRY: Dict[str, Callable] = {}


def register_scoring_method(name: str):
    """注册自定义打分方法的装饰器

    Example:
        >>> @register_scoring_method("my_method")
        ... def my_score_method(df, factor_cols, **kwargs):
        ...     # 自定义打分逻辑
        ...     score = df[factor_cols].mean(axis=1)
        ...     return df.assign(score=score)
    """
    def decorator(func: Callable) -> Callable:
        _SCORING_REGISTRY[name] = func
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def _get_factor_direction(
    factor_col: str,
    direction: Union[str, Dict[str, str]]
) -> int:
    """获取因子方向 (1 表示正向，-1 表示反向)

    Args:
        factor_col: 因子列名
        direction: 方向配置，可以是 "ascending"/"descending"
                  或字典 {"factor1": "ascending", ...}
    """
    if isinstance(direction, dict):
        dir_str = direction.get(factor_col, "ascending")
    else:
        dir_str = direction

    return 1 if dir_str == "ascending" else -1


def _rank_factors(
    df: pd.DataFrame,
    factor_cols: List[str],
    direction: Union[str, Dict[str, str]] = "ascending"
) -> pd.DataFrame:
    """将因子值转换为排名（截面排名）

    Args:
        df: 输入数据框
        factor_cols: 因子列名列表
        direction: 因子方向配置

    Returns:
        含排名列的数据框
    """
    result = df.copy()

    for col in factor_cols:
        dir_mult = _get_factor_direction(col, direction)
        # 排名并归一化到 [0, 1]，然后调整方向
        rank_col = result[col].rank(pct=True)
        if dir_mult == -1:
            rank_col = 1 - rank_col
        result[col] = rank_col

    return result


def _calc_ic(
    df: pd.DataFrame,
    factor_cols: List[str],
    ret_col: str,
    date_col: Optional[str] = None
) -> pd.DataFrame:
    """计算因子 IC 值

    Args:
        df: 输入数据框
        factor_cols: 因子列名列表
        ret_col: 收益率列名
        date_col: 日期列名，None 表示单截面

    Returns:
        IC DataFrame (index=date, columns=factor)
    """
    if date_col is not None and date_col in df.columns:
        def calc_ic_group(group):
            return pd.Series({
                col: stats.spearmanr(group[col], group[ret_col])[0]
                if len(group) > 2 else 0
                for col in factor_cols
            })
        ic = df.groupby(date_col).apply(calc_ic_group)
    else:
        ic = pd.Series({
            col: stats.spearmanr(df[col], df[ret_col])[0]
            if len(df) > 2 else 0
            for col in factor_cols
        }).to_frame().T

    return ic


def _score_equal(df: pd.DataFrame, factor_cols: List[str], **kwargs) -> pd.DataFrame:
    """等权打分"""
    score = df[factor_cols].mean(axis=1)
    return df.assign(score=score)


def _score_custom(
    df: pd.DataFrame,
    factor_cols: List[str],
    weights: Dict[str, float],
    **kwargs
) -> pd.DataFrame:
    """自定义权重打分"""
    # 确保权重归一化
    valid_weights = {k: v for k, v in weights.items() if k in factor_cols}
    if not valid_weights:
        return _score_equal(df, factor_cols)

    total = sum(valid_weights.values())
    normalized_weights = {k: v / total for k, v in valid_weights.items()}

    # 加权求和
    score = sum(df[col] * w for col, w in normalized_weights.items())
    return df.assign(score=score)


def _score_ic_weighted(
    df: pd.DataFrame,
    factor_cols: List[str],
    ret_col: str,
    ic_window: int = 5,
    date_col: Optional[str] = None,
    use_ir: bool = False,
    **kwargs
) -> pd.DataFrame:
    """IC 或 ICIR 加权打分

    需要历史 IC 数据来计算权重，如果数据不足，回退到等权。
    """
    if date_col is None or date_col not in df.columns:
        # 单截面，回退到等权
        return _score_equal(df, factor_cols)

    # 计算历史 IC
    ic_df = _calc_ic(df, factor_cols, ret_col, date_col)

    if len(ic_df) < ic_window:
        # 历史数据不足，回退到等权
        return _score_equal(df, factor_cols)

    # 计算 IC 均值（半衰加权或简单平均）
    mean_ic = ic_df.rolling(ic_window).mean().iloc[-1]

    if use_ir:
        # ICIR 加权
        std_ic = ic_df.rolling(ic_window).std().iloc[-1]
        weights = mean_ic / (std_ic + 1e-12)
        # 负 IC 置 0
        weights = weights.clip(lower=0)
    else:
        # IC 加权，负 IC 置 0
        weights = mean_ic.clip(lower=0)

    # 归一化
    if weights.sum() > 0:
        weights = weights / weights.sum()
    else:
        weights = pd.Series(1 / len(factor_cols), index=factor_cols)

    # 获取当前日期的数据
    current_date = df[date_col].max()
    current_df = df[df[date_col] == current_date].copy()

    score = sum(current_df[col] * weights.get(col, 0) for col in factor_cols)
    current_df = current_df.assign(score=score)

    return current_df


def _score_pca(
    df: pd.DataFrame,
    factor_cols: List[str],
    date_col: Optional[str] = None,
    window: int = 20,
    **kwargs
) -> pd.DataFrame:
    """PCA 打分（第一主成分）"""
    from sklearn.decomposition import PCA as SklearnPCA
    from sklearn.preprocessing import StandardScaler

    result = df.copy()

    if date_col is not None and date_col in df.columns:
        # 时间序列模式，使用滚动窗口
        dates = df[date_col].unique()
        if len(dates) < window:
            # 数据不足，回退到等权
            return _score_equal(df, factor_cols)

        scores = []
        for i in range(window - 1, len(dates)):
            window_dates = dates[i - window + 1:i + 1]
            window_df = df[df[date_col].isin(window_dates)].copy()

            # 取当前截面的数据
            current_df = df[df[date_col] == dates[i]].copy()

            # 标准化
            scaler = StandardScaler()
            factor_values = window_df[factor_cols].fillna(0).values
            scaled = scaler.fit_transform(factor_values)

            # PCA
            pca = SklearnPCA(n_components=1)
            pca.fit(scaled)

            # 应用到当前截面
            current_scaled = scaler.transform(current_df[factor_cols].fillna(0).values)
            score = pca.transform(current_scaled).flatten()

            scores.append(current_df.assign(score=score))

        return pd.concat(scores, ignore_index=True)

    else:
        # 单截面
        scaler = StandardScaler()
        factor_values = df[factor_cols].fillna(0).values
        scaled = scaler.fit_transform(factor_values)

        pca = SklearnPCA(n_components=1)
        score = pca.fit_transform(scaled).flatten()

        return result.assign(score=score)


def build_score_frame(
    df: pd.DataFrame,
    factor_cols: List[str],
    method: Literal["equal", "ic", "icir", "pca", "custom"] = "equal",
    weights: Optional[Dict[str, float]] = None,
    direction: Union[str, Dict[str, str]] = "ascending",
    ic_window: int = 5,
    ret_col: Optional[str] = None,
    date_col: Optional[str] = None,
    rank_first: bool = True,
) -> pd.DataFrame:
    """多因子打分合成

    Args:
        df: 输入数据框，含因子列
        factor_cols: 参与打分的因子列名列表
        method: 打分方法
            - "equal": 等权法
            - "ic": IC 加权法
            - "icir": ICIR 加权法
            - "pca": 主成分分析法（第一主成分）
            - "custom": 自定义权重
        weights: 自定义权重字典，method="custom" 时使用
        direction: 因子方向，"ascending" 表示因子值越大分数越高
                  或传入字典为每个因子单独指定方向
        ic_window: IC/IR 计算窗口
        ret_col: 收益率列名（IC/IR 方法需要）
        date_col: 日期列名（用于截面计算）
        rank_first: 打分前是否先转秩（截面排名）

    Returns:
        含 'score' 列的数据框

    Example:
        >>> score_df = build_score_frame(
        ...     df,
        ...     factor_cols=["roe", "pe", "pb"],
        ...     method="equal",
        ...     direction="ascending"
        ... )
        >>> score_df = build_score_frame(
        ...     df,
        ...     factor_cols=["roe", "pe"],
        ...     method="custom",
        ...     weights={"roe": 0.6, "pe": 0.4},
        ...     direction={"roe": "ascending", "pe": "descending"}
        ... )
    """
    # 过滤有效列
    valid_cols = [c for c in factor_cols if c in df.columns]
    if not valid_cols:
        raise ValueError(f"None of factor_cols {factor_cols} found in df")

    # 步骤1: 方向调整（如果需要排名）
    if rank_first:
        work_df = _rank_factors(df, valid_cols, direction)
    else:
        work_df = df.copy()
        # 方向调整（反向因子乘以 -1）
        for col in valid_cols:
            if _get_factor_direction(col, direction) == -1:
                work_df[col] = -work_df[col]

    # 步骤2: 根据方法计算分数
    if method in _SCORING_REGISTRY:
        # 使用注册的自定义方法
        return _SCORING_REGISTRY[method](
            work_df, valid_cols, weights=weights, **kwargs
        )

    scoring_funcs = {
        "equal": _score_equal,
        "ic": lambda df, cols, **kw: _score_ic_weighted(
            df, cols, ret_col=ret_col, ic_window=ic_window,
            date_col=date_col, use_ir=False, **kw
        ),
        "icir": lambda df, cols, **kw: _score_ic_weighted(
            df, cols, ret_col=ret_col, ic_window=ic_window,
            date_col=date_col, use_ir=True, **kw
        ),
        "pca": lambda df, cols, **kw: _score_pca(
            df, cols, date_col=date_col, window=ic_window, **kw
        ),
        "custom": lambda df, cols, **kw: _score_custom(
            df, cols, weights=weights or {}, **kw
        ),
    }

    if method not in scoring_funcs:
        raise ValueError(f"Unknown method: {method}. Available: {list(scoring_funcs.keys())}")

    return scoring_funcs[method](work_df, valid_cols)
