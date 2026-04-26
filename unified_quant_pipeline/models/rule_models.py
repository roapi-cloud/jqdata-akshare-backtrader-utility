"""规则模型 - 基于规则的打分排序"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List
from .base import ModelCatalog, BasePredictModel

logger = logging.getLogger(__name__)


@ModelCatalog.register("weighted_score")
class WeightedScoreModel(BasePredictModel):
    """加权打分模型"""

    name = "weighted_score"

    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or {}
        self._fitted = False

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        if not self.weights:
            self.weights = {col: 1.0 / len(X.columns) for col in X.columns}
        self._fitted = True

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        scores = np.zeros(len(X))
        for col, w in self.weights.items():
            if col in X.columns:
                scores += X[col].values * w
        return scores

    def set_weights(self, weights: Dict[str, float]):
        """设置权重"""
        self.weights = weights


@ModelCatalog.register("rank_ensemble")
class RankEnsembleModel(BasePredictModel):
    """排名集成模型 - 多因子排名平均"""

    name = "rank_ensemble"

    def __init__(self):
        self._fitted = False

    def train(self, X: pd.DataFrame, y: pd.Series, **kwargs) -> None:
        self._fitted = True

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        ranks = []
        for col in X.columns:
            rank = X[col].rank(pct=True, ascending=True)
            ranks.append(rank)

        avg_rank = pd.concat(ranks, axis=1).mean(axis=1)
        return avg_rank.values
