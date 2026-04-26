"""特征衍生模块 - 从原始因子生成新特征"""

import pandas as pd
import numpy as np
from typing import List, Optional, Tuple


class FeatureDerivator:
    """特征衍生器 - 从原始因子生成新特征

    Methods:
        add_lag_features: 添加滞后特征
        add_diff_features: 添加差分特征
        add_rolling_features: 添加滚动统计特征
        add_interaction_features: 添加交互特征
        add_ma_ratio_features: 添加均线比值特征
    """

    @staticmethod
    def add_lag_features(
        df: pd.DataFrame, columns: Optional[List[str]] = None, lags: List[int] = None
    ) -> pd.DataFrame:
        """添加滞后特征

        为指定列创建历史滞后值, 常用于时间序列特征工程。

        Args:
            df: 输入DataFrame, 需按时间排序
            columns: 需要添加滞后特征的列名列表, 为None时对全部列操作
            lags: 滞后期数列表, 默认为[1, 3, 5]

        Returns:
            添加了滞后特征的新DataFrame
        """
        if lags is None:
            lags = [1, 3, 5]

        result = df.copy()
        cols = columns if columns is not None else df.columns.tolist()
        for col in cols:
            for lag in lags:
                result[f"{col}_lag{lag}"] = df[col].shift(lag)
        return result

    @staticmethod
    def add_diff_features(
        df: pd.DataFrame, columns: Optional[List[str]] = None, periods: List[int] = None
    ) -> pd.DataFrame:
        """添加差分特征

        计算指定列的差分, 用于捕捉变化趋势和消除趋势性。

        Args:
            df: 输入DataFrame, 需按时间排序
            columns: 需要添加差分特征的列名列表, 为None时对全部列操作
            periods: 差分周期列表, 默认为[1]

        Returns:
            添加了差分特征的新DataFrame
        """
        if periods is None:
            periods = [1]

        result = df.copy()
        cols = columns if columns is not None else df.columns.tolist()
        for col in cols:
            for period in periods:
                result[f"{col}_diff{period}"] = df[col].diff(period)
        return result

    @staticmethod
    def add_rolling_features(
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
        windows: List[int] = None,
        stats: List[str] = None,
    ) -> pd.DataFrame:
        """添加滚动统计特征

        计算指定窗口内的滚动统计量, 如均值、标准差等。

        Args:
            df: 输入DataFrame, 需按时间排序
            columns: 需要添加滚动特征的列名列表, 为None时对全部列操作
            windows: 滚动窗口大小列表, 默认为[5, 10, 20]
            stats: 统计量类型列表, 支持mean/std/min/max, 默认为["mean", "std"]

        Returns:
            添加了滚动统计特征的新DataFrame
        """
        if windows is None:
            windows = [5, 10, 20]
        if stats is None:
            stats = ["mean", "std"]

        result = df.copy()
        cols = columns if columns is not None else df.columns.tolist()
        for col in cols:
            for window in windows:
                for stat in stats:
                    col_name = f"{col}_roll{window}_{stat}"
                    if stat == "mean":
                        result[col_name] = df[col].rolling(window).mean()
                    elif stat == "std":
                        result[col_name] = df[col].rolling(window).std()
                    elif stat == "min":
                        result[col_name] = df[col].rolling(window).min()
                    elif stat == "max":
                        result[col_name] = df[col].rolling(window).max()
        return result

    @staticmethod
    def add_interaction_features(
        df: pd.DataFrame, pairs: Optional[List[Tuple[str, str]]] = None
    ) -> pd.DataFrame:
        """添加交互特征

        通过特征相乘创建交互项, 捕捉特征间的协同效应。

        Args:
            df: 输入DataFrame
            pairs: 特征对列表, 默认为[("ROE", "BP"), ("Revenue_Growth", "EP")]

        Returns:
            添加了交互特征的新DataFrame
        """
        result = df.copy()
        if pairs is None:
            pairs = [
                ("ROE", "BP"),
                ("Revenue_Growth", "EP"),
            ]
        for col1, col2 in pairs:
            if col1 in df.columns and col2 in df.columns:
                result[f"{col1}_x_{col2}"] = df[col1] * df[col2]
        return result

    @staticmethod
    def add_ma_ratio_features(
        df: pd.DataFrame,
        price_col: str = "close",
        short_windows: List[int] = None,
        long_windows: List[int] = None,
    ) -> pd.DataFrame:
        """添加均线比值特征

        计算短期均线与长期均线的比值, 用于捕捉趋势信号。

        Args:
            df: 输入DataFrame, 需按时间排序
            price_col: 价格列名, 默认为"close"
            short_windows: 短期均线窗口列表, 默认为[5, 10]
            long_windows: 长期均线窗口列表, 默认为[20, 60]

        Returns:
            添加了均线比值特征的新DataFrame
        """
        if short_windows is None:
            short_windows = [5, 10]
        if long_windows is None:
            long_windows = [20, 60]

        result = df.copy()
        for sw in short_windows:
            for lw in long_windows:
                if lw > sw:
                    ma_short = df[price_col].rolling(sw).mean()
                    ma_long = df[price_col].rolling(lw).mean()
                    result[f"MA{sw}_{lw}_ratio"] = ma_short / ma_long
        return result
