"""模型基类"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd
import numpy as np


class ModelCatalog:
    """模型目录"""

    _models: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(model_cls):
            cls._models[name] = model_cls
            model_cls.name = name
            return model_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> type:
        if name not in cls._models:
            raise KeyError(
                f"Model '{name}' not found. Available: {list(cls._models.keys())}"
            )
        return cls._models[name]

    @classmethod
    def list(cls) -> list:
        return list(cls._models.keys())


class BasePredictModel(ABC):
    """预测模型基类（用于选股预测）"""

    name: str = "base"

    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        """训练模型"""
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """预测"""
        pass

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """评估模型"""
        preds = self.predict(X)
        return self._calculate_metrics(y, preds)

    def _calculate_metrics(
        self, y_true: pd.Series, y_pred: np.ndarray
    ) -> Dict[str, float]:
        """计算评估指标"""
        from scipy import stats

        if len(y_true) != len(y_pred):
            return {}

        ic, _ = stats.spearmanr(y_true, y_pred)

        if len(np.unique(y_true)) == 2:
            accuracy = np.mean((y_pred > 0.5).astype(int) == y_true)
            return {"ic": ic, "accuracy": accuracy}

        return {"ic": ic}

    def save(self, path: str):
        """保存模型"""
        import joblib

        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str):
        """加载模型"""
        import joblib

        return joblib.load(path)
