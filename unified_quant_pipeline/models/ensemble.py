"""集成模型 - 多模型集成"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any
from .base import ModelCatalog, BasePredictModel

logger = logging.getLogger(__name__)


@ModelCatalog.register("stacking")
class StackingEnsemble(BasePredictModel):
    """Stacking集成 - 多模型堆叠"""

    name = "stacking"

    def __init__(
        self, base_models: List[Dict[str, Any]], meta_model: Dict[str, Any] = None
    ):
        """
        Args:
            base_models: 基础模型配置列表
                [{'name': 'random_forest', 'params': {...}}, ...]
            meta_model: 元模型配置（默认用逻辑回归）
        """
        self.base_models_config = base_models
        self.meta_model_config = meta_model or {"name": "logistic_regression"}
        self.base_models: List[BasePredictModel] = []
        self.meta_model = None

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        from sklearn.linear_model import LogisticRegression

        self.base_models = []
        for config in self.base_models_config:
            model_cls = ModelCatalog.get(config["name"])
            model = model_cls(**config.get("params", {}))
            model.train(X, y)
            self.base_models.append(model)

        meta_features = self._generate_meta_features(X)

        self.meta_model = LogisticRegression(max_iter=1000)
        self.meta_model.fit(meta_features, y)

        logger.info(
            f"Stacking ensemble trained with {len(self.base_models)} base models"
        )

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        meta_features = self._generate_meta_features(X)
        return self.meta_model.predict_proba(meta_features)[:, 1]

    def _generate_meta_features(self, X: pd.DataFrame) -> np.ndarray:
        """生成元特征（基础模型的预测）"""
        features = []
        for model in self.base_models:
            preds = model.predict(X)
            features.append(preds)
        return np.column_stack(features)


@ModelCatalog.register("logistic_regression")
class LogisticRegressionModel(BasePredictModel):
    """逻辑回归模型（可用作元模型）"""

    name = "logistic_regression"

    def __init__(self, max_iter: int = 1000, **kwargs):
        from sklearn.linear_model import LogisticRegression

        self.max_iter = max_iter
        self._model = LogisticRegression(max_iter=max_iter)

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        self._model.fit(X, y)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self._model.predict_proba(X)[:, 1]
