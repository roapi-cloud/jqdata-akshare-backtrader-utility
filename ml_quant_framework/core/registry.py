from typing import Any, Dict, List, Optional


class Registry:
    """组件注册中心。

    提供装饰器注册机制，用于管理和查询各类组件（因子、模型、预处理器等）。
    支持按名称注册和检索，实现组件的解耦和动态加载。
    """

    def __init__(self, name: str):
        self.name = name
        self._registry: Dict[str, Any] = {}

    def register(self, name: Optional[str] = None):
        """注册装饰器。

        Args:
            name: 注册名称，默认为类名。

        Returns:
            装饰器函数。
        """

        def decorator(cls):
            registry_name = name or cls.__name__
            if registry_name in self._registry:
                raise ValueError(
                    f"Component '{registry_name}' is already registered in '{self.name}' registry."
                )
            self._registry[registry_name] = cls
            return cls

        return decorator

    def get(self, name: str) -> Any:
        """获取已注册的组件类。

        Args:
            name: 组件注册名称。

        Returns:
            组件类。

        Raises:
            KeyError: 如果组件未注册。
        """
        if name not in self._registry:
            raise KeyError(
                f"Component '{name}' not found in '{self.name}' registry. Available: {self.list()}"
            )
        return self._registry[name]

    def list(self) -> List[str]:
        """列出所有已注册的组件名称。

        Returns:
            组件名称列表。
        """
        return list(self._registry.keys())

    def has(self, name: str) -> bool:
        """检查组件是否已注册。

        Args:
            name: 组件注册名称。

        Returns:
            是否已注册。
        """
        return name in self._registry

    def unregister(self, name: str) -> None:
        """注销已注册的组件。

        Args:
            name: 组件注册名称。

        Raises:
            KeyError: 如果组件未注册。
        """
        if name not in self._registry:
            raise KeyError(f"Component '{name}' not found in '{self.name}' registry.")
        del self._registry[name]

    def __contains__(self, name: str) -> bool:
        return name in self._registry

    def __len__(self) -> int:
        return len(self._registry)

    def __repr__(self) -> str:
        return f"Registry(name='{self.name}', components={self.list()})"


FACTOR_REGISTRY = Registry("factor")
MODEL_REGISTRY = Registry("model")
PREPROCESSOR_REGISTRY = Registry("preprocessor")
LABEL_REGISTRY = Registry("label")
STRATEGY_REGISTRY = Registry("strategy")
