"""特征选择模块 - 支持F检验/互信息/随机森林重要性/RFE/LightGBM/相关性过滤"""

import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif, RFE
from sklearn.feature_selection import SelectFromModel
from sklearn.ensemble import RandomForestClassifier
from typing import List, Optional


class FeatureSelector:
    """特征选择器 - 支持多种特征选择方法

    Methods:
        f_test: F检验特征选择
        mutual_information: 互信息特征选择
        rf_importance: 随机森林特征重要性选择
        rfe: 递归特征消除
        lgbm_importance: LightGBM特征重要性选择
        correlation_filter: 相关性过滤
    """

    @staticmethod
    def f_test(
        X: pd.DataFrame,
        y: pd.Series,
        k: Optional[int] = None,
        p_threshold: float = 0.01,
    ) -> List[str]:
        """F检验特征选择

        使用方差分析(ANOVA)的F统计量评估特征与目标变量的线性关系显著性。

        Args:
            X: 特征矩阵, shape (n_samples, n_features)
            y: 目标变量, shape (n_samples,)
            k: 选择的特征数量, 为None时根据p_threshold自动确定
            p_threshold: p值阈值, 用于自动确定k

        Returns:
            选中的特征名称列表
        """
        if k is None:
            F, p_values = f_classif(X, y)
            k = F.shape[0] - (p_values > p_threshold).sum()
            k = max(k, 1)

        selector = SelectKBest(f_classif, k=k)
        selector.fit(X, y)
        mask = selector.get_support()
        return list(X.columns[mask])

    @staticmethod
    def mutual_information(
        X: pd.DataFrame, y: pd.Series, k: Optional[int] = None
    ) -> List[str]:
        """互信息特征选择

        基于互信息评估特征与目标变量之间的非线性依赖关系。

        Args:
            X: 特征矩阵, shape (n_samples, n_features)
            y: 目标变量, shape (n_samples,)
            k: 选择的特征数量, 为None时选择MI>0的所有特征

        Returns:
            选中的特征名称列表
        """
        mi_scores = mutual_info_classif(X, y)
        if k is None:
            k = sum(mi_scores > 0)
            k = max(k, 1)

        selector = SelectKBest(mutual_info_classif, k=k)
        selector.fit(X, y)
        mask = selector.get_support()
        return list(X.columns[mask])

    @staticmethod
    def rf_importance(
        X: pd.DataFrame,
        y: pd.Series,
        threshold: float = 0.005,
        n_estimators: int = 100,
        max_depth: int = 3,
    ) -> List[str]:
        """随机森林特征重要性选择

        基于随机森林模型的特征重要性进行特征选择。

        Args:
            X: 特征矩阵, shape (n_samples, n_features)
            y: 目标变量, shape (n_samples,)
            threshold: 重要性阈值, 低于此值的特征将被移除
            n_estimators: 随机森林树的数量
            max_depth: 树的最大深度

        Returns:
            选中的特征名称列表
        """
        rf = RandomForestClassifier(
            n_estimators=n_estimators, max_depth=max_depth, random_state=42
        )
        selector = SelectFromModel(rf, threshold=threshold)
        selector.fit(X, y)
        mask = selector.get_support()
        return list(X.columns[mask])

    @staticmethod
    def rfe(
        X: pd.DataFrame, y: pd.Series, n_features: int = 20, estimator=None
    ) -> List[str]:
        """递归特征消除 (Recursive Feature Elimination)

        递归地移除最不重要的特征, 直到剩余指定数量的特征。

        Args:
            X: 特征矩阵, shape (n_samples, n_features)
            y: 目标变量, shape (n_samples,)
            n_features: 最终保留的特征数量
            estimator: 基础估计器, 默认为RandomForestClassifier

        Returns:
            选中的特征名称列表
        """
        if estimator is None:
            estimator = RandomForestClassifier(
                n_estimators=100, max_depth=3, random_state=42
            )

        selector = RFE(estimator, n_features_to_select=n_features, step=1)
        selector.fit(X, y)
        mask = selector.get_support()
        return list(X.columns[mask])

    @staticmethod
    def lgbm_importance(
        X: pd.DataFrame, y: pd.Series, p_importance: float = 0.9, n_iterations: int = 10
    ) -> List[str]:
        """LightGBM特征重要性选择

        基于LightGBM多次训练的平均特征重要性, 按累计重要性阈值选择特征。

        Args:
            X: 特征矩阵, shape (n_samples, n_features)
            y: 目标变量, shape (n_samples,)
            p_importance: 累计重要性阈值, 选择累计重要性达到此比例的特征
            n_iterations: 训练迭代次数, 用于平均化重要性

        Returns:
            选中的特征名称列表
        """
        import lightgbm as lgb

        feature_names = list(X.columns)
        importance_values = np.zeros(len(feature_names))

        for _ in range(n_iterations):
            model = lgb.LGBMClassifier(
                n_estimators=100, learning_rate=0.05, verbose=-1, random_state=42
            )
            model.fit(X, y)
            importance_values += model.feature_importances_ / n_iterations

        importance_df = pd.DataFrame(
            {"feature": feature_names, "importance": importance_values}
        )
        importance_df = importance_df.sort_values("importance", ascending=False)
        importance_df["cumulative_importance"] = (
            importance_df["importance"].cumsum() / importance_df["importance"].sum()
        )

        selected = importance_df[importance_df["cumulative_importance"] <= p_importance]
        return selected["feature"].tolist()

    @staticmethod
    def correlation_filter(X: pd.DataFrame, threshold: float = 0.9) -> List[str]:
        """相关性过滤 - 去除高度相关的特征

        计算特征间的相关系数矩阵, 移除与其他特征高度相关的冗余特征。

        Args:
            X: 特征矩阵, shape (n_samples, n_features)
            threshold: 相关系数阈值, 超过此值认为高度相关

        Returns:
            保留的特征名称列表 (去除了高度相关的特征)
        """
        corr_matrix = X.corr().abs()
        upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        to_drop = [col for col in upper.columns if any(upper[col] > threshold)]
        return [col for col in X.columns if col not in to_drop]
