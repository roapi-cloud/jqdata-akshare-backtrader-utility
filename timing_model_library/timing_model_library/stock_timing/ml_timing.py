# -*- coding: utf-8 -*-
"""
机器学习择时模型

使用 SVR、随机森林等机器学习模型进行择时预测。

核心逻辑:
    - 特征: 技术指标 (RSI/MACD/BOLL/成交量等) + 宏观指标
    - 目标: 未来 N 日收益率方向 (分类) 或收益率 (回归)
    - 模型: SVR / 随机森林 / 逻辑回归
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from ..base import BaseTimingModel, TimingSignal, SignalDirection, TimingScope
from ..utils.indicators import rsi, sma, boll, macd, realized_volatility


class MLTimingModel(BaseTimingModel):
    """
    机器学习择时模型

    参数:
        model_type: 模型类型 (svr/random_forest/logistic)
        prediction_horizon: 预测天数 (默认 5)
        feature_window: 特征计算窗口 (默认 20)
    """

    def __init__(
        self,
        model_type: str = "svr",
        prediction_horizon: int = 5,
        feature_window: int = 20,
    ):
        super().__init__(name=f"ML-Timing-{model_type}", scope=TimingScope.STOCK)
        self.model_type = model_type
        self.prediction_horizon = prediction_horizon
        self.feature_window = feature_window
        self._model = None
        self._feature_names = []

    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        self._validate_data(data, ["close", "high", "low", "volume"])

        features = self._extract_features(data)
        latest_features = features.iloc[-1:].values

        if self._model is None:
            return TimingSignal(
                model_name=self.name,
                scope=self.scope,
                direction=SignalDirection.HOLD,
                strength=0.0,
                confidence=0.0,
                raw_score=0.0,
                timestamp=data.index[-1],
                metadata={"status": "model_not_trained"},
            )

        prediction = self._model.predict(latest_features)[0]

        if hasattr(self._model, "predict_proba"):
            proba = self._model.predict_proba(latest_features)[0]
            confidence = max(proba)
        else:
            confidence = 0.5

        if prediction > 0.5:
            direction = SignalDirection.BUY
        elif prediction < -0.5:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        strength = np.clip(prediction, -1.0, 1.0)

        return TimingSignal(
            model_name=self.name,
            scope=self.scope,
            direction=direction,
            strength=strength,
            confidence=confidence,
            raw_score=prediction,
            timestamp=data.index[-1],
            metadata={
                "model_type": self.model_type,
                "feature_count": len(self._feature_names),
            },
        )

    def _extract_features(self, data: pd.DataFrame) -> pd.DataFrame:
        features = pd.DataFrame(index=data.index)

        features["rsi_14"] = rsi(data["close"], 14)
        features["rsi_9"] = rsi(data["close"], 9)

        dif, dea, macd_hist = macd(data["close"])
        features["macd_dif"] = dif
        features["macd_dea"] = dea
        features["macd_hist"] = macd_hist

        upper, mid, lower = boll(data["close"], 20)
        features["boll_position"] = (data["close"] - lower) / (upper - lower).replace(
            0, np.nan
        )

        features["volatility"] = realized_volatility(data["close"], 20)
        features["volume_ma_ratio"] = data["volume"] / sma(data["volume"], 20)

        features["ma5_20_ratio"] = sma(data["close"], 5) / sma(data["close"], 20)
        features["ma10_60_ratio"] = sma(data["close"], 10) / sma(data["close"], 60)

        self._feature_names = list(features.columns)
        return features.dropna()

    def train(self, data: pd.DataFrame, labels: pd.Series) -> None:
        """
        训练模型

        Args:
            data: 训练数据 (OHLCV)
            labels: 标签 (未来收益率方向: 1=涨, -1=跌, 0=平)
        """
        features = self._extract_features(data)
        aligned = features.join(labels).dropna()
        X = aligned[features.columns].values
        y = aligned[labels.name].values

        if self.model_type == "svr":
            from sklearn.svm import SVR

            self._model = SVR(kernel="rbf", C=1.0, gamma="scale")
        elif self.model_type == "random_forest":
            from sklearn.ensemble import RandomForestClassifier

            self._model = RandomForestClassifier(
                n_estimators=100, max_depth=5, random_state=42
            )
        elif self.model_type == "logistic":
            from sklearn.linear_model import LogisticRegression

            self._model = LogisticRegression(max_iter=1000, random_state=42)
        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

        self._model.fit(X, y)

    def get_params(self) -> Dict[str, Any]:
        return {
            "model_type": self.model_type,
            "prediction_horizon": self.prediction_horizon,
            "feature_window": self.feature_window,
            "trained": self._model is not None,
        }
