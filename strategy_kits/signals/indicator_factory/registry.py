"""
Indicator Factory - Signal Registry

信号注册中心，支持装饰器方式注册信号。
"""

from typing import Any, Dict, Optional, Type

from .base import BaseSignal


class SignalRegistry:
    """信号注册中心"""

    _signals: Dict[str, Type[BaseSignal]] = {}

    @classmethod
    def register(cls, name: str, signal_class: Type[BaseSignal]) -> Type[BaseSignal]:
        """注册信号计算器

        Args:
            name: 信号名称
            signal_class: 信号计算器类

        Returns:
            返回 signal_class 本身，支持装饰器用法
        """
        if not issubclass(signal_class, BaseSignal):
            raise TypeError(f"Signal class must inherit from BaseSignal: {signal_class}")
        cls._signals[name] = signal_class
        return signal_class

    @classmethod
    def get(cls, name: str) -> Type[BaseSignal]:
        """获取信号计算器类

        Args:
            name: 信号名称

        Returns:
            信号计算器类

        Raises:
            ValueError: 信号不存在
        """
        if name not in cls._signals:
            available = ", ".join(sorted(cls._signals.keys()))
            raise ValueError(f"Unknown signal: {name}. Available: {available}")
        return cls._signals[name]

    @classmethod
    def list_signals(cls, category: Optional[str] = None) -> Dict[str, Type[BaseSignal]]:
        """列出所有已注册信号

        Args:
            category: 按类别过滤，None 表示所有

        Returns:
            信号名称到类的映射
        """
        if category is None:
            return cls._signals.copy()
        return {
            name: sig
            for name, sig in cls._signals.items()
            if sig.category == category
        }

    @classmethod
    def create(cls, name: str, config: Optional[Dict[str, Any]] = None) -> BaseSignal:
        """创建信号计算器实例

        Args:
            name: 信号名称
            config: 配置参数

        Returns:
            信号计算器实例
        """
        signal_class = cls.get(name)
        return signal_class(config)

    @classmethod
    def unregister(cls, name: str) -> None:
        """注销信号（主要用于测试）"""
        cls._signals.pop(name, None)

    @classmethod
    def clear(cls) -> None:
        """清空所有注册（主要用于测试）"""
        cls._signals.clear()


def register_signal(name: str):
    """信号注册装饰器

    用法:
        @register_signal("macd")
        class MACDSignal(DiscreteSignal):
            ...
    """

    def decorator(cls: Type[BaseSignal]) -> Type[BaseSignal]:
        return SignalRegistry.register(name, cls)

    return decorator
