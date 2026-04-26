"""特征变换模块 - Sklearn风格的特征变换流水线"""

import pandas as pd
from typing import List, Optional
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler, MinMaxScaler


class FeaturePipeline(BaseEstimator, TransformerMixin):
    """特征变换流水线 (Sklearn风格)

    将多个变换步骤串联执行, 支持fit/transform/fit_transform接口。

    Attributes:
        steps: 变换步骤列表, 每个元素为(name, transformer)元组

    Example:
        >>> pipeline = FeaturePipeline([
        ...     ("scaler", StandardScaler()),
        ...     ("selector", SelectKBest(f_classif, k=10)),
        ... ])
        >>> X_transformed = pipeline.fit_transform(X, y)
    """

    def __init__(self, steps: Optional[list] = None):
        """初始化特征变换流水线

        Args:
            steps: 变换步骤列表, 每个元素为(name, transformer)元组
        """
        self.steps = steps if steps is not None else []

    def fit(self, X, y=None):
        """拟合流水线中的所有变换器

        Args:
            X: 输入特征矩阵
            y: 目标变量 (可选)

        Returns:
            self
        """
        for name, transformer in self.steps:
            if hasattr(transformer, "fit"):
                X = transformer.fit_transform(X, y)
            else:
                X = transformer.transform(X)
        return self

    def transform(self, X):
        """应用流水线中的所有变换

        Args:
            X: 输入特征矩阵

        Returns:
            变换后的特征矩阵
        """
        for name, transformer in self.steps:
            if hasattr(transformer, "transform"):
                X = transformer.transform(X)
            else:
                X = transformer(X)
        return X

    def fit_transform(self, X, y=None):
        """拟合并变换

        Args:
            X: 输入特征矩阵
            y: 目标变量 (可选)

        Returns:
            变换后的特征矩阵
        """
        return self.fit(X, y).transform(X)


class FeatureUnion:
    """特征合并器

    提供静态方法用于DataFrame的列选择、删除和重命名操作。

    Methods:
        select_columns: 选择指定列
        drop_columns: 删除指定列
        rename_columns: 重命名列
    """

    @staticmethod
    def select_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """选择指定列

        Args:
            df: 输入DataFrame
            columns: 要选择的列名列表

        Returns:
            只包含指定列的DataFrame
        """
        return df[columns]

    @staticmethod
    def drop_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """删除指定列

        Args:
            df: 输入DataFrame
            columns: 要删除的列名列表

        Returns:
            删除指定列后的DataFrame
        """
        return df.drop(columns=[c for c in columns if c in df.columns])

    @staticmethod
    def rename_columns(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
        """重命名列

        Args:
            df: 输入DataFrame
            mapping: 列名映射字典 {old_name: new_name}

        Returns:
            重命名列后的DataFrame
        """
        return df.rename(columns=mapping)
