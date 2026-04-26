"""
Indicator Factory - Signal Factory

信号工厂，支持批量信号计算和组合。
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from .base import BaseSignal
from .registry import SignalRegistry


class SignalFactory:
    """信号工厂

    用于批量管理多个信号的计算和组合。

    Example:
        factory = SignalFactory()
        factory.add_signal("macd", {"fastperiod": 12})
        factory.add_signal("alligator", {"periods": (13, 8, 5)})

        results = factory.compute_all(price_df=close_df)
    """

    def __init__(self):
        self._signals: Dict[str, BaseSignal] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}

    def add_signal(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> "SignalFactory":
        """添加信号到工厂

        Args:
            name: 信号名称
            config: 信号配置

        Returns:
            self，支持链式调用
        """
        signal = SignalRegistry.create(name, config)
        self._signals[name] = signal
        self._configs[name] = config or {}
        return self

    def remove_signal(self, name: str) -> "SignalFactory":
        """从工厂移除信号"""
        self._signals.pop(name, None)
        self._configs.pop(name, None)
        return self

    def list_signals(self) -> List[str]:
        """列出已添加的信号"""
        return list(self._signals.keys())

    def compute_all(
        self,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> Dict[str, Dict[str, Any]]:
        """计算所有信号

        Args:
            price_df: 价格数据
            feature_df: 特征数据
            **kwargs: 额外参数

        Returns:
            {信号名: 计算结果}
        """
        results = {}
        for name, signal in self._signals.items():
            results[name] = signal.compute(
                price_df=price_df, feature_df=feature_df, **kwargs
            )
        return results

    def compute_single(
        self,
        name: str,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """计算单个信号

        Args:
            name: 信号名称
            price_df: 价格数据
            feature_df: 特征数据
            **kwargs: 额外参数

        Returns:
            计算结果
        """
        if name not in self._signals:
            raise ValueError(f"Signal not found in factory: {name}")
        return self._signals[name].compute(
            price_df=price_df, feature_df=feature_df, **kwargs
        )

    def to_dataframe(
        self, results: Dict[str, Dict[str, Any]]
    ) -> pd.DataFrame:
        """将多信号结果转换为 DataFrame

        Args:
            results: compute_all 的返回结果

        Returns:
            DataFrame，每列是一个信号
        """
        combined = {}
        for name, result in results.items():
            sig = result.get("signal_series") or result.get("signal_df")
            if sig is not None:
                combined[name] = sig

        if not combined:
            return pd.DataFrame()

        return pd.concat(
            [
                s.rename(name) if isinstance(s, pd.Series) else s
                for name, s in combined.items()
            ],
            axis=1,
        )


class SignalComposer:
    """信号组合器

    将多个信号组合成一个综合信号。
    注意：这是工具类，策略层的投票规则应在 strategy_templates 中实现。
    """

    @staticmethod
    def equal_weight(signals_df: pd.DataFrame) -> pd.Series:
        """等权组合"""
        return signals_df.mean(axis=1)

    @staticmethod
    def weighted(signals_df: pd.DataFrame, weights: Dict[str, float]) -> pd.Series:
        """加权组合"""
        weight_series = pd.Series(weights)
        aligned = signals_df[list(weights.keys())]
        return aligned.mul(weight_series).sum(axis=1)

    @staticmethod
    def majority_vote(signals_df: pd.DataFrame) -> pd.Series:
        """多数投票 (-1/0/1 信号)"""
        return signals_df.sum(axis=1).apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))

    @staticmethod
    def unanimous(signals_df: pd.DataFrame) -> pd.Series:
        """一致同意 (所有信号同向才出信号)"""
        def _check_unanimous(row: pd.Series) -> int:
            unique = row.dropna().unique()
            if len(unique) == 1:
                return int(unique[0])
            return 0

        return signals_df.apply(_check_unanimous, axis=1)

    @staticmethod
    def threshold(signal: pd.Series, upper: float, lower: float) -> pd.Series:
        """阈值判断，将连续信号转为离散信号"""
        return signal.apply(
            lambda x: 1 if x > upper else (-1 if x < lower else 0)
        )
