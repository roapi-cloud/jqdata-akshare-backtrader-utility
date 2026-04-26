"""大盘择时模型 - 集成timing_model_library中的模型"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class TimingSignal:
    """择时信号"""

    def __init__(
        self, name: str, direction: float, strength: float, confidence: float = 1.0
    ):
        """初始化择时信号

        Args:
            name: 信号名称
            direction: 方向 (-1: 卖出, 0: 持有, 1: 买入)
            strength: 信号强度 [-1, 1]
            confidence: 置信度 [0, 1]
        """
        self.name = name
        self.direction = direction
        self.strength = strength
        self.confidence = confidence


class BaseTimingModel(ABC):
    """择时模型基类"""

    name: str = "base"

    @abstractmethod
    def compute(self, data: pd.DataFrame) -> TimingSignal:
        """计算择时信号

        Args:
            data: 包含OHLCV等数据的DataFrame

        Returns:
            TimingSignal: 择时信号
        """
        pass


class TimingCatalog:
    """择时模型目录"""

    _models: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str):
        """注册择时模型装饰器

        Args:
            name: 模型名称

        Returns:
            装饰器函数
        """

        def decorator(model_cls):
            cls._models[name] = model_cls
            model_cls.name = name
            return model_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> type:
        """获取注册的择时模型类

        Args:
            name: 模型名称

        Returns:
            择时模型类

        Raises:
            KeyError: 模型未注册时抛出
        """
        if name not in cls._models:
            raise KeyError(
                f"Timing model '{name}' not found. Available: {list(cls._models.keys())}"
            )
        return cls._models[name]

    @classmethod
    def list(cls) -> list:
        """列出所有已注册的择时模型

        Returns:
            模型名称列表
        """
        return list(cls._models.keys())


# ============ 内置择时模型 ============


@TimingCatalog.register("ma_cross")
class MACrossTiming(BaseTimingModel):
    """均线交叉择时"""

    name = "ma_cross"

    def __init__(self, fast: int = 5, slow: int = 20):
        """初始化均线交叉择时模型

        Args:
            fast: 快速均线周期
            slow: 慢速均线周期
        """
        self.fast = fast
        self.slow = slow

    def compute(self, data: pd.DataFrame) -> TimingSignal:
        """计算均线交叉择时信号

        Args:
            data: 包含close列的DataFrame

        Returns:
            TimingSignal: 择时信号
        """
        close = data["close"]
        ma_fast = close.rolling(self.fast).mean()
        ma_slow = close.rolling(self.slow).mean()

        diff = (ma_fast.iloc[-1] - ma_slow.iloc[-1]) / ma_slow.iloc[-1]

        if diff > 0.01:
            direction, strength = 1, min(diff * 10, 1.0)
        elif diff < -0.01:
            direction, strength = -1, max(diff * 10, -1.0)
        else:
            direction, strength = 0, 0

        return TimingSignal(self.name, direction, strength)


@TimingCatalog.register("rsrs")
class RSRSTiming(BaseTimingModel):
    """RSRS择时"""

    name = "rsrs"

    def __init__(self, window: int = 18, threshold: float = 0.8):
        """初始化RSRS择时模型

        Args:
            window: 回归窗口大小
            threshold: 信号触发阈值
        """
        self.window = window
        self.threshold = threshold

    def compute(self, data: pd.DataFrame) -> TimingSignal:
        """计算RSRS择时信号

        Args:
            data: 包含high和low列的DataFrame

        Returns:
            TimingSignal: 择时信号
        """
        high = data["high"].values
        low = data["low"].values

        if len(high) < self.window:
            return TimingSignal(self.name, 0, 0)

        slopes = []
        r2s = []
        for i in range(self.window, len(high)):
            low_w = low[i - self.window : i]
            high_w = high[i - self.window : i]
            if np.std(low_w) > 0:
                slope, _ = np.polyfit(low_w, high_w, 1)
                r2 = np.corrcoef(low_w, high_w)[0, 1] ** 2
                slopes.append(slope)
                r2s.append(r2)

        if not slopes:
            return TimingSignal(self.name, 0, 0)

        slope_mean = np.mean(slopes)
        slope_std = np.std(slopes)
        latest_z = (slopes[-1] - slope_mean) / (slope_std + 1e-8) * r2s[-1]

        if latest_z > self.threshold:
            direction, strength = 1, min(latest_z, 1.0)
        elif latest_z < -self.threshold:
            direction, strength = -1, max(latest_z, -1.0)
        else:
            direction, strength = 0, latest_z

        return TimingSignal(self.name, direction, strength)


@TimingCatalog.register("volatility")
class VolatilityTiming(BaseTimingModel):
    """波动率择时（高波动降仓）"""

    name = "volatility"

    def __init__(self, window: int = 20, threshold: float = 0.03):
        """初始化波动率择时模型

        Args:
            window: 波动率计算窗口
            threshold: 波动率阈值
        """
        self.window = window
        self.threshold = threshold

    def compute(self, data: pd.DataFrame) -> TimingSignal:
        """计算波动率择时信号

        Args:
            data: 包含close列的DataFrame

        Returns:
            TimingSignal: 择时信号
        """
        returns = data["close"].pct_change()
        vol = returns.rolling(self.window).std().iloc[-1]

        if vol < self.threshold * 0.5:
            direction, strength = 1, 1.0
        elif vol > self.threshold * 2:
            direction, strength = -1, -1.0
        else:
            direction, strength = 0, 0

        return TimingSignal(self.name, direction, strength)


@TimingCatalog.register("momentum")
class MomentumTiming(BaseTimingModel):
    """动量择时"""

    name = "momentum"

    def __init__(self, period: int = 20, threshold: float = 0.05):
        """初始化动量择时模型

        Args:
            period: 动量计算周期
            threshold: 信号触发阈值
        """
        self.period = period
        self.threshold = threshold

    def compute(self, data: pd.DataFrame) -> TimingSignal:
        """计算动量择时信号

        Args:
            data: 包含close列的DataFrame

        Returns:
            TimingSignal: 择时信号
        """
        ret = data["close"].pct_change(self.period).iloc[-1]

        if ret > self.threshold:
            direction, strength = 1, min(ret * 5, 1.0)
        elif ret < -self.threshold:
            direction, strength = -1, max(ret * 5, -1.0)
        else:
            direction, strength = 0, ret * 5

        return TimingSignal(self.name, direction, strength)
