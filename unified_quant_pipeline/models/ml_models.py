"""ML模型 - 随机森林、XGBoost、LightGBM等"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from .base import ModelCatalog, BasePredictModel

logger = logging.getLogger(__name__)


@ModelCatalog.register("random_forest")
class RandomForestModel(BasePredictModel):
    """随机森林模型"""

    name = "random_forest"

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = 5,
        random_state: int = 42,
        **kwargs,
    ):
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.random_state = random_state
        self._model = None
        self._is_classifier = True

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

        if len(np.unique(y)) <= 10:
            self._model = RandomForestClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                random_state=self.random_state,
                n_jobs=-1,
            )
            self._is_classifier = True
        else:
            self._model = RandomForestRegressor(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                random_state=self.random_state,
                n_jobs=-1,
            )
            self._is_classifier = False

        self._model.fit(X, y)
        logger.info(f"RandomForest trained with {self.n_estimators} trees")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self._is_classifier:
            return self._model.predict_proba(X)[:, 1]
        return self._model.predict(X)

    def feature_importance(self) -> Dict[str, float]:
        if self._model is None:
            return {}
        return dict(
            zip(self._model.feature_names_in_, self._model.feature_importances_)
        )


@ModelCatalog.register("xgboost")
class XGBoostModel(BasePredictModel):
    """XGBoost模型"""

    name = "xgboost"

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        **kwargs,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self._model = None

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        try:
            import xgboost as xgb
        except ImportError:
            raise ImportError("Please install xgboost: pip install xgboost")

        self._model = xgb.XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            use_label_encoder=False,
            eval_metric="logloss",
            n_jobs=-1,
        )
        self._model.fit(X, y)
        logger.info(f"XGBoost trained with {self.n_estimators} rounds")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self._model.predict_proba(X)[:, 1]

    def feature_importance(self) -> Dict[str, float]:
        if self._model is None:
            return {}
        return dict(
            zip(self._model.feature_names_in_, self._model.feature_importances_)
        )


@ModelCatalog.register("lightgbm")
class LightGBMModel(BasePredictModel):
    """LightGBM模型"""

    name = "lightgbm"

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        **kwargs,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self._model = None

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        try:
            import lightgbm as lgb
        except ImportError:
            raise ImportError("Please install lightgbm: pip install lightgbm")

        self._model = lgb.LGBMClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            n_jobs=-1,
            verbose=-1,
        )
        self._model.fit(X, y)
        logger.info(f"LightGBM trained with {self.n_estimators} rounds")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self._model.predict_proba(X)[:, 1]

    def feature_importance(self) -> Dict[str, float]:
        if self._model is None:
            return {}
        return dict(zip(self._model.feature_name_, self._model.feature_importances_))
