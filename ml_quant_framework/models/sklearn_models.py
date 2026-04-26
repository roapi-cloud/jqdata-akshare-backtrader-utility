"""Sklearn 模型包装器与注册。

封装 8 大 Sklearn 分类模型，提供统一的 train/predict/evaluate/save/load 接口，
并自动注册到 MODEL_REGISTRY 中。
"""

import pickle
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import (
    RandomForestClassifier,
    AdaBoostClassifier,
    GradientBoostingClassifier,
)
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, roc_auc_score

from ml_quant_framework.core.registry import MODEL_REGISTRY


class SklearnModelWrapper:
    """Sklearn 模型统一包装器。

    将 Sklearn 分类器封装为量化框架标准接口，支持概率输出、
    特征重要性提取和模型持久化。

    Attributes:
        model: 底层 Sklearn 分类器实例。
        name: 模型名称标识。
    """

    def __init__(self, model, name: str):
        """初始化包装器。

        Args:
            model: Sklearn 分类器实例。
            name: 模型名称。
        """
        self.model = model
        self.name = name

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> "SklearnModelWrapper":
        """训练模型。

        Args:
            X: 训练特征数据框。
            y: 训练标签序列。
            **kwargs: 传递给 fit 的额外参数。

        Returns:
            训练后的包装器实例。
        """
        self.model.fit(X, y, **kwargs)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """预测样本为正类的概率或决策函数值。

        Args:
            X: 预测特征数据框。

        Returns:
            预测值数组，形状为 (n_samples,)。
        """
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)[:, 1]
        elif hasattr(self.model, "decision_function"):
            return self.model.decision_function(X)
        return self.model.predict(X)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """评估模型性能。

        Args:
            X: 测试特征数据框。
            y: 测试标签序列。

        Returns:
            包含 accuracy 和 auc 的评估指标字典。
        """
        preds = self.predict(X)
        if hasattr(self.model, "predict_proba"):
            pred_classes = self.model.predict(X)
            acc = accuracy_score(y, pred_classes)
            try:
                auc = roc_auc_score(y, preds)
            except Exception:
                auc = 0.5
        else:
            pred_classes = preds
            acc = accuracy_score(y, pred_classes)
            auc = 0.5
        return {"accuracy": acc, "auc": auc}

    def feature_importance(self, feature_names: List[str]) -> pd.Series:
        """提取特征重要性。

        Args:
            feature_names: 特征名称列表。

        Returns:
            特征重要性 Series，索引为特征名称。
        """
        if hasattr(self.model, "feature_importances_"):
            return pd.Series(self.model.feature_importances_, index=feature_names)
        elif hasattr(self.model, "coef_"):
            coefs = self.model.coef_
            if coefs.ndim == 2:
                return pd.Series(np.abs(coefs[0]), index=feature_names)
            return pd.Series(np.abs(coefs), index=feature_names)
        return pd.Series(dtype=float)

    def save(self, path: str) -> None:
        """保存模型到磁盘。

        Args:
            path: 保存路径。
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.model, f)

    def load(self, path: str) -> "SklearnModelWrapper":
        """从磁盘加载模型。

        Args:
            path: 模型文件路径。

        Returns:
            加载后的包装器实例。
        """
        with open(path, "rb") as f:
            self.model = pickle.load(f)
        return self


@MODEL_REGISTRY.register("knn")
def get_knn(n_neighbors: int = 10) -> SklearnModelWrapper:
    """创建 KNN 分类器。

    Args:
        n_neighbors: 邻居数量。

    Returns:
        KNN 模型包装器。
    """
    return SklearnModelWrapper(KNeighborsClassifier(n_neighbors=n_neighbors), "knn")


@MODEL_REGISTRY.register("logistic")
def get_logistic(
    C: float = 1.0, penalty: str = "l2", max_iter: int = 300
) -> SklearnModelWrapper:
    """创建逻辑回归分类器。

    Args:
        C: 正则化强度的倒数。
        penalty: 正则化类型。
        max_iter: 最大迭代次数。

    Returns:
        逻辑回归模型包装器。
    """
    return SklearnModelWrapper(
        LogisticRegression(C=C, penalty=penalty, max_iter=max_iter), "logistic"
    )


@MODEL_REGISTRY.register("decision_tree")
def get_decision_tree(max_depth: Optional[int] = 3) -> SklearnModelWrapper:
    """创建决策树分类器。

    Args:
        max_depth: 树的最大深度。

    Returns:
        决策树模型包装器。
    """
    return SklearnModelWrapper(
        DecisionTreeClassifier(max_depth=max_depth), "decision_tree"
    )


@MODEL_REGISTRY.register("naive_bayes")
def get_naive_bayes() -> SklearnModelWrapper:
    """创建高斯朴素贝叶斯分类器。

    Returns:
        朴素贝叶斯模型包装器。
    """
    return SklearnModelWrapper(GaussianNB(), "naive_bayes")


@MODEL_REGISTRY.register("random_forest")
def get_random_forest(
    n_estimators: int = 100, max_depth: Optional[int] = 5
) -> SklearnModelWrapper:
    """创建随机森林分类器。

    Args:
        n_estimators: 树的数量。
        max_depth: 树的最大深度。

    Returns:
        随机森林模型包装器。
    """
    return SklearnModelWrapper(
        RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth),
        "random_forest",
    )


@MODEL_REGISTRY.register("adaboost")
def get_adaboost(
    n_estimators: int = 50, learning_rate: float = 1.0
) -> SklearnModelWrapper:
    """创建 AdaBoost 分类器。

    Args:
        n_estimators: 弱学习器数量。
        learning_rate: 学习率。

    Returns:
        AdaBoost 模型包装器。
    """
    return SklearnModelWrapper(
        AdaBoostClassifier(n_estimators=n_estimators, learning_rate=learning_rate),
        "adaboost",
    )


@MODEL_REGISTRY.register("svm")
def get_svm(
    C: float = 1.0, kernel: str = "rbf", gamma: str = "scale"
) -> SklearnModelWrapper:
    """创建 SVM 分类器。

    Args:
        C: 正则化参数。
        kernel: 核函数类型。
        gamma: 核系数。

    Returns:
        SVM 模型包装器。
    """
    return SklearnModelWrapper(
        SVC(C=C, kernel=kernel, gamma=gamma, probability=True), "svm"
    )


@MODEL_REGISTRY.register("gradient_boosting")
def get_gradient_boosting(
    n_estimators: int = 100,
    max_depth: int = 3,
    learning_rate: float = 0.1,
) -> SklearnModelWrapper:
    """创建梯度提升分类器。

    Args:
        n_estimators: 提升阶段数。
        max_depth: 树的最大深度。
        learning_rate: 学习率。

    Returns:
        梯度提升模型包装器。
    """
    return SklearnModelWrapper(
        GradientBoostingClassifier(
            n_estimators=n_estimators, max_depth=max_depth, learning_rate=learning_rate
        ),
        "gradient_boosting",
    )
