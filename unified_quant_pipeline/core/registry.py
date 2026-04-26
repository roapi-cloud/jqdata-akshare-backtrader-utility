"""
Component registry center for the unified quantitative pipeline.

This module provides a decorator-based registration system that allows
pipeline components to be registered by name and instantiated dynamically.
"""

from typing import Any, Dict, List, Optional, Type


class Registry:
    """Component registry center.

    Provides decorator-based registration and dynamic instantiation of
    pipeline components.

    Example:
        @FACTOR_REGISTRY.register('momentum')
        class MomentumFactor(BaseFactor):
            ...

        cls = FACTOR_REGISTRY.get('momentum')
        factor = cls()
    """

    def __init__(self, name: str = "registry") -> None:
        """Initialize the registry.

        Args:
            name: Registry name for error messages and identification.
        """
        self.name = name
        self._registry: Dict[str, Type] = {}

    def register(self, name: Optional[str] = None):
        """Decorator to register a component class.

        Args:
            name: Registration name. If None, uses the class name in lowercase.

        Returns:
            Decorator function.

        Raises:
            ValueError: If the name is already registered.
        """

        def decorator(cls: Type) -> Type:
            register_name = name or cls.__name__.lower()
            if register_name in self._registry:
                raise ValueError(
                    f"Component '{register_name}' is already registered in {self.name}"
                )
            self._registry[register_name] = cls
            return cls

        return decorator

    def get(self, name: str) -> Type:
        """Get a registered component class by name.

        Args:
            name: Registration name of the component.

        Returns:
            The component class.

        Raises:
            KeyError: If the name is not registered.
        """
        if name not in self._registry:
            available = list(self._registry.keys())
            raise KeyError(
                f"Component '{name}' is not registered in {self.name}. Available: {available}"
            )
        return self._registry[name]

    def list(self) -> List[str]:
        """List all registered component names.

        Returns:
            List of registered component names.
        """
        return list(self._registry.keys())

    def has(self, name: str) -> bool:
        """Check if a component is registered.

        Args:
            name: Registration name to check.

        Returns:
            True if the component is registered, False otherwise.
        """
        return name in self._registry

    def create(self, name: str, **kwargs: Any) -> Any:
        """Create an instance of a registered component.

        Args:
            name: Registration name of the component.
            **kwargs: Keyword arguments to pass to the component constructor.

        Returns:
            Instantiated component.
        """
        cls = self.get(name)
        return cls(**kwargs)


# Predefined registries for each component type
FACTOR_REGISTRY = Registry("factors")
MODEL_REGISTRY = Registry("models")
PREPROCESSOR_REGISTRY = Registry("preprocessors")
LABEL_REGISTRY = Registry("labels")
STRATEGY_REGISTRY = Registry("strategies")
TIMING_REGISTRY = Registry("timing_models")
DATA_SOURCE_REGISTRY = Registry("data_sources")
