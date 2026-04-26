"""模型训练管理器。

提供 ModelTrainer 类，封装模型训练、交叉验证网格搜索、
预测、评估、特征重要性分析和模型持久化等完整工作流。
"""

from typing import Dict, Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

from ml_quant_framework.core.config import ModelConfig
from ml_quant_framework.models.sklearn_models import SklearnModelWrapper


class ModelTrainer:
    """模型训练管理器。

    基于 ModelConfig 从注册中心获取模型，支持普通训练和时间序列交叉验证
    网格搜索训练，提供预测、评估、特征重要性及模型存取接口。

    Attributes:
        config: 模型配置对象。
        model: 训练后的模型包装器实例。
        model_name: 模型名称。
        feature_names: 训练时使用的特征名称列表。
    """

    def __init__(self, config: ModelConfig):
        """初始化训练管理器。

        Args:
            config: 模型配置，包含模型名称和超参数。
        """
        self.config = config
        self.model: Optional[SklearnModelWrapper] = None
        self.model_name = config.name
        self.feature_names: Optional[list] = None

    def _get_model(self) -> SklearnModelWrapper:
        """从注册中心获取模型实例。

        Returns:
            模型包装器实例。
        """
        from ml_quant_framework.core.registry import MODEL_REGISTRY

        model_factory = MODEL_REGISTRY.get(self.model_name)
        params = self.config.params or {}
        return model_factory(**params)

    def train(self, X: pd.DataFrame, y: pd.Series) -> "ModelTrainer":
        """训练模型。

        Args:
            X: 训练特征数据框。
            y: 训练标签序列。

        Returns:
            当前训练器实例。
        """
        self.feature_names = list(X.columns)
        self.model = self._get_model()
        self.model.train(X, y)
        return self

    def train_with_cv(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        param_grid: Optional[Dict] = None,
        cv: int = 5,
    ) -> "ModelTrainer":
        """带时间序列交叉验证的网格搜索训练。

        Args:
            X: 训练特征数据框。
            y: 训练标签序列。
            param_grid: 参数搜索网格，为 None 时使用默认网格。
            cv: 交叉验证折数。

        Returns:
            当前训练器实例。
        """
        self.feature_names = list(X.columns)
        base_model = self._get_model()

        if param_grid is None:
            param_grid = self._get_default_param_grid()

        tscv = TimeSeriesSplit(n_splits=cv)

        grid_search = GridSearchCV(
            base_model.model,
            param_grid,
            cv=tscv,
            scoring="roc_auc",
            n_jobs=-1,
            verbose=0,
        )
        grid_search.fit(X, y)

        self.model = SklearnModelWrapper(grid_search.best_estimator_, self.model_name)
        print(f"Best params: {grid_search.best_params_}")
        print(f"Best CV score: {grid_search.best_score_:.4f}")
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """预测。

        Args:
            X: 预测特征数据框。

        Returns:
            预测值数组。

        Raises:
            ValueError: 模型未训练时抛出。
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        return self.model.predict(X)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """评估模型性能。

        Args:
            X: 测试特征数据框。
            y: 测试标签序列。

        Returns:
            评估指标字典。

        Raises:
            ValueError: 模型未训练时抛出。
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        return self.model.evaluate(X, y)

    def feature_importance(self) -> pd.Series:
        """获取特征重要性。

        Returns:
            特征重要性 Series。

        Raises:
            ValueError: 模型未训练时抛出。
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        return self.model.feature_importance(self.feature_names)

    def save(self, path: str) -> None:
        """保存模型到磁盘。

        Args:
            path: 保存路径。

        Raises:
            ValueError: 模型未训练时抛出。
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        self.model.save(path)

    def load(self, path: str) -> "ModelTrainer":
        """从磁盘加载模型。

        Args:
            path: 模型文件路径。

        Returns:
            当前训练器实例。
        """
        self.model = self._get_model()
        self.model.load(path)
        return self

    def _get_default_param_grid(self) -> Dict:
        """获取默认参数搜索网格。

        Returns:
            参数网格字典，键为参数名，值为候选值列表。
        """
        grids: Dict[str, Dict] = {
            "xgboost": {
                "max_depth": [3, 5, 7],
                "learning_rate": [0.01, 0.05, 0.1],
                "n_estimators": [50, 100, 200],
            },
            "random_forest": {
                "n_estimators": [50, 100, 200],
                "max_depth": [3, 5, 7, None],
                "min_samples_split": [2, 5, 10],
            },
            "lightgbm": {
                "n_estimators": [50, 100, 200],
                "max_depth": [3, 5, 7],
                "learning_rate": [0.01, 0.05, 0.1],
                "num_leaves": [15, 31, 63],
            },
            "logistic": {
                "C": [0.01, 0.1, 1, 10, 100],
                "penalty": ["l1", "l2"],
            },
        }
        return grids.get(self.model_name, {})
