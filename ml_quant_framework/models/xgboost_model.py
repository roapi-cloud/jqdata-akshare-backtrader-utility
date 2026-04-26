"""XGBoost 模型注册。

提供 XGBoost 分类器的工厂函数，自动注册到 MODEL_REGISTRY。
"""

from typing import Any

from ml_quant_framework.core.registry import MODEL_REGISTRY
from ml_quant_framework.models.sklearn_models import SklearnModelWrapper


@MODEL_REGISTRY.register("xgboost")
def get_xgboost(
    max_depth: int = 5,
    learning_rate: float = 0.05,
    n_estimators: int = 100,
    min_child_weight: int = 1,
    subsample: float = 0.8,
    colsample_bytree: float = 0.8,
    **kwargs: Any,
) -> SklearnModelWrapper:
    """创建 XGBoost 分类器。

    Args:
        max_depth: 树的最大深度。
        learning_rate: 学习率（步长收缩）。
        n_estimators: 提升轮数。
        min_child_weight: 子节点最小样本权重和。
        subsample: 样本采样比例。
        colsample_bytree: 特征采样比例。
        **kwargs: 其他传递给 XGBClassifier 的参数。

    Returns:
        XGBoost 模型包装器。
    """
    from xgboost import XGBClassifier

    model = XGBClassifier(
        max_depth=max_depth,
        learning_rate=learning_rate,
        n_estimators=n_estimators,
        min_child_weight=min_child_weight,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        use_label_encoder=False,
        eval_metric="logloss",
        **kwargs,
    )
    return SklearnModelWrapper(model, "xgboost")
