"""LightGBM 模型注册。

提供 LightGBM 分类器的工厂函数，自动注册到 MODEL_REGISTRY。
"""

from typing import Any

from ml_quant_framework.core.registry import MODEL_REGISTRY
from ml_quant_framework.models.sklearn_models import SklearnModelWrapper


@MODEL_REGISTRY.register("lightgbm")
def get_lightgbm(
    n_estimators: int = 100,
    max_depth: int = 5,
    learning_rate: float = 0.05,
    num_leaves: int = 31,
    min_child_samples: int = 20,
    subsample: float = 0.8,
    colsample_bytree: float = 0.8,
    **kwargs: Any,
) -> SklearnModelWrapper:
    """创建 LightGBM 分类器。

    Args:
        n_estimators: 提升轮数。
        max_depth: 树的最大深度。
        learning_rate: 学习率。
        num_leaves: 叶子节点数。
        min_child_samples: 子节点最小样本数。
        subsample: 样本采样比例。
        colsample_bytree: 特征采样比例。
        **kwargs: 其他传递给 LGBMClassifier 的参数。

    Returns:
        LightGBM 模型包装器。
    """
    import lightgbm as lgb

    model = lgb.LGBMClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        num_leaves=num_leaves,
        min_child_samples=min_child_samples,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        **kwargs,
    )
    return SklearnModelWrapper(model, "lightgbm")
