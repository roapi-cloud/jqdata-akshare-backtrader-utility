"""模型管理模块。

提供 Sklearn、XGBoost、LightGBM 等模型的统一包装器，
以及模型训练管理器，支持交叉验证、特征重要性分析和模型持久化。
"""

from ml_quant_framework.models.sklearn_models import (
    SklearnModelWrapper,
    get_knn,
    get_logistic,
    get_decision_tree,
    get_naive_bayes,
    get_random_forest,
    get_adaboost,
    get_svm,
    get_gradient_boosting,
)
from ml_quant_framework.models.xgboost_model import get_xgboost
from ml_quant_framework.models.lightgbm_model import get_lightgbm
from ml_quant_framework.models.trainer import ModelTrainer

__all__ = [
    "SklearnModelWrapper",
    "get_knn",
    "get_logistic",
    "get_decision_tree",
    "get_naive_bayes",
    "get_random_forest",
    "get_adaboost",
    "get_svm",
    "get_gradient_boosting",
    "get_xgboost",
    "get_lightgbm",
    "ModelTrainer",
]
