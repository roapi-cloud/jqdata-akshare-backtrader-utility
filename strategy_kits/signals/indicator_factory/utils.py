"""
Indicator Factory - Utility Functions

通用工具函数，如滑动窗口、排列检测等。
"""

from typing import Generator, Tuple

import numpy as np
import pandas as pd


class SlidingWindowError(Exception):
    """滑动窗口异常基类"""
    pass


class InputTooShortError(SlidingWindowError):
    """输入数据长度不足异常"""

    def __init__(self, n_samples: int, window: int):
        super().__init__(f"输入数据长度{n_samples}小于窗口长度{window}")
        self.n_samples = n_samples
        self.window = window


class InvalidWindowError(SlidingWindowError):
    """无效窗口参数异常"""
    pass


def sliding_window(
    arr: np.ndarray, window: int, step: int = 1
) -> Generator[np.ndarray, None, None]:
    """生成高效内存视图的滑动窗口

    参数:
        arr: 输入数组，形状为(N, ...)
        window: 窗口长度（时间步数）
        step: 窗口滑动步长

    生成:
        形状为(window, ...)的窗口视图

    异常:
        InputTooShortError: 当输入数据长度小于窗口长度时
        InvalidWindowError: 当窗口参数无效时

    示例:
        >>> data = np.arange(5)
        >>> list(sliding_window(data, 3))
        [array([0,1,2]), array([1,2,3]), array([2,3,4])]
    """
    # 参数验证
    if arr.ndim == 0:
        raise ValueError("输入数组维度必须≥1")
    if window < 1:
        raise InvalidWindowError(f"无效窗口长度: {window} (必须≥1)")
    if step < 1:
        raise InvalidWindowError(f"无效步长: {step} (必须≥1)")

    n_samples = arr.shape[0]
    if n_samples < window:
        raise InputTooShortError(n_samples, window)

    # 计算窗口数量
    num_windows = (n_samples - window) // step + 1

    # 构造内存视图
    new_shape = (num_windows, window) + arr.shape[1:]
    new_strides = (arr.strides[0] * step, arr.strides[0]) + arr.strides[1:]

    try:
        sliding_view = np.lib.stride_tricks.as_strided(
            arr, shape=new_shape, strides=new_strides, writeable=False
        )
    except ValueError as e:
        raise SlidingWindowError("滑动窗口构造失败") from e

    yield from sliding_view


def alignment_signal(arr: np.ndarray, alignment_type: str = "bullish") -> np.ndarray:
    """检测数组的排列信号

    参数:
        arr: 输入数组，形状为(n, m)，每行是一组值（如 [ma5, ma10, ma20, ma30]）
        alignment_type: 排列类型，'bullish' 或 'bearish'

    返回:
        布尔数组，True 表示该位置形成指定排列

    Raises:
        ValueError: alignment_type 无效

    示例:
        >>> arr = np.array([[1, 2, 3], [3, 2, 1], [2, 3, 1]])
        >>> alignment_signal(arr, "bullish")
        array([ True, False, False])
    """
    if alignment_type == "bullish":
        # 多头排列：从左到右递减（短周期 > 长周期）
        is_aligned: np.ndarray = np.all(np.diff(arr, axis=1) < 0, axis=1)
    elif alignment_type == "bearish":
        # 空头排列：从左到右递增（短周期 < 长周期）
        is_aligned: np.ndarray = np.all(np.diff(arr, axis=1) > 0, axis=1)
    else:
        raise ValueError("alignment_type must be 'bullish' or 'bearish'")

    return is_aligned


def trigger_signal(arr: np.ndarray) -> np.ndarray:
    """将连续信号转换为触发信号

    今天形成信号且昨天不是

    参数:
        arr: 布尔数组或 0/1 数组

    返回:
        触发信号数组
    """
    signal: np.ndarray = np.zeros(len(arr), dtype=bool)
    signal[1:] = arr[1:] & ~arr[:-1]
    return signal


def calc_zscore(data: np.ndarray, axis: int = 0) -> np.ndarray:
    """计算数据的z分数

    参数:
        data: 输入数据
        axis: 计算轴

    返回:
        z分数数组
    """
    return (data - np.nanmean(data, axis=axis, keepdims=True)) / np.nanstd(
        data, axis=axis, keepdims=True
    )


def calc_beta(low: np.ndarray, high: np.ndarray) -> np.ndarray:
    """计算 beta 值

    beta = std(high) / std(low) * corr(low, high)

    参数:
        low: 低值数组
        high: 高值数组

    返回:
        beta 值
    """
    if low.shape != high.shape:
        raise ValueError("low and high must have the same shape")

    if low.ndim == 2:
        corr_matrix: np.ndarray = np.corrcoef(high, low, rowvar=False)
        corr = np.diagonal(corr_matrix, offset=low.shape[1])
    elif low.ndim == 1:
        corr = np.corrcoef(high, low)[0, 1]
    else:
        raise ValueError("Input must be 1D or 2D array")

    return np.std(high, axis=0) / np.std(low, axis=0) * corr


def calc_corrcoef(low: np.ndarray, high: np.ndarray) -> np.ndarray:
    """计算相关系数

    参数:
        low: 低值数组
        high: 高值数组

    返回:
        相关系数
    """
    if low.shape != high.shape:
        raise ValueError("low and high must have the same shape")

    if low.ndim == 2:
        corr_matrix: np.ndarray = np.corrcoef(high, low, rowvar=False)
        return np.diagonal(corr_matrix, offset=low.shape[1])
    elif low.ndim == 1:
        return np.corrcoef(high, low)[0, 1]
    else:
        raise ValueError("Input must be 1D or 2D array")


def ffill_fillna(
    df: pd.DataFrame, fill_value: float = 0.0
) -> pd.DataFrame:
    """前向填充后填充缺失值

    参数:
        df: 输入DataFrame
        fill_value: 填充值

    返回:
        处理后的DataFrame
    """
    return df.ffill().fillna(fill_value)
