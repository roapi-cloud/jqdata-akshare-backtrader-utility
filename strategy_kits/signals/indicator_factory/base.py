"""
Indicator Factory - Base Signal Classes

统一信号接口定义，所有信号计算器必须继承自 BaseSignal。
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd


class BaseSignal(ABC):
    """信号计算器基类

    所有具体信号计算器必须继承此基类，实现 compute 方法。
    输入输出格式统一，便于策略层拼装。

    Attributes:
        name: 信号名称
        category: 信号类别 (trend, mean_reversion, volatility, pattern, volume, flow)
        output_type: 输出类型 (discrete, continuous, binary)
    """

    name: str = "base"
    category: str = "unknown"
    output_type: str = "discrete"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化信号计算器

        Args:
            config: 信号计算参数配置
        """
        self.config = config or {}
        self._validate_config()

    @abstractmethod
    def compute(
        self,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """计算信号

        Args:
            price_df: 价格数据，必须包含 OHLCV 列
            feature_df: 特征数据，用于非价格类信号
            **kwargs: 额外参数

        Returns:
            {
                "signal_series": pd.Series,  # 单资产信号 (可选)
                "signal_df": pd.DataFrame,   # 多资产信号 (可选)
                "meta": {
                    "name": str,
                    "category": str,
                    "output_type": str,
                    "params": Dict,
                    "timestamp": datetime,
                }
            }
        """
        pass

    def _validate_config(self) -> None:
        """验证配置参数，子类可重写"""
        pass

    def get_meta(self) -> Dict[str, Any]:
        """获取信号元信息"""
        return {
            "name": self.name,
            "category": self.category,
            "output_type": self.output_type,
            "params": self.config,
        }

    def _wrap_result(
        self,
        signal: Union[pd.Series, pd.DataFrame, None] = None,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """包装返回结果"""
        result: Dict[str, Any] = {"meta": self.get_meta()}
        result["meta"]["timestamp"] = datetime.now()

        if signal is not None:
            if isinstance(signal, pd.Series):
                result["signal_series"] = signal
            else:
                result["signal_df"] = signal

        if extra_meta:
            result["meta"].update(extra_meta)

        return result


class DiscreteSignal(BaseSignal):
    """离散信号基类 (-1/0/1)"""

    output_type = "discrete"

    def compute(
        self,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        result = self._compute_impl(price_df=price_df, feature_df=feature_df, **kwargs)

        # 标准化输出为 -1, 0, 1
        if "signal_df" in result:
            result["signal_df"] = result["signal_df"].clip(-1, 1).fillna(0)
        if "signal_series" in result:
            result["signal_series"] = result["signal_series"].clip(-1, 1).fillna(0)

        return result

    @abstractmethod
    def _compute_impl(
        self,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """子类实现具体的信号计算逻辑"""
        pass


class ContinuousSignal(BaseSignal):
    """连续信号基类"""

    output_type = "continuous"

    def compute(
        self,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._compute_impl(price_df=price_df, feature_df=feature_df, **kwargs)

    @abstractmethod
    def _compute_impl(
        self,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """子类实现具体的信号计算逻辑"""
        pass


class BinarySignal(BaseSignal):
    """二进制信号基类 (0/1)"""

    output_type = "binary"

    def compute(
        self,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        result = self._compute_impl(price_df=price_df, feature_df=feature_df, **kwargs)

        # 标准化输出为 0, 1
        if "signal_df" in result:
            result["signal_df"] = (result["signal_df"] > 0).astype(int)
        if "signal_series" in result:
            result["signal_series"] = (result["signal_series"] > 0).astype(int)

        return result

    @abstractmethod
    def _compute_impl(
        self,
        price_df: Optional[pd.DataFrame] = None,
        feature_df: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """子类实现具体的信号计算逻辑"""
        pass
