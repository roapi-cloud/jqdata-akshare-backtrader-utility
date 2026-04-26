"""Registry for indicator (signal generator) classes.

Provides a thread-safe singleton registry with auto-discovery of all
:class:`BaseSignalGenerator` subclasses found under ``src/indicators/``.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import threading
from pathlib import Path
from typing import Dict, List, Type

from src.indicators.base import BaseSignalGenerator


class IndicatorRegistry:
    """Thread-safe singleton registry for signal generator classes.

    Usage::

        registry = IndicatorRegistry.instance()
        registry.register("my_rsi", MyRSI)
        indicator = registry.get("my_rsi", period=14)
    """

    _instance: IndicatorRegistry | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._registry: Dict[str, Type[BaseSignalGenerator]] = {}
        self._registry_lock: threading.RLock = threading.RLock()

    @classmethod
    def instance(cls) -> IndicatorRegistry:
        """Return the singleton instance (created on first call)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for testing)."""
        with cls._lock:
            cls._instance = None

    def register(self, name: str, generator_class: Type[BaseSignalGenerator]) -> None:
        """Register a signal generator class under a given name.

        Args:
            name: Unique identifier for the indicator.
            generator_class: A subclass of :class:`BaseSignalGenerator`.

        Raises:
            TypeError: If ``generator_class`` does not inherit from
                :class:`BaseSignalGenerator`.
        """
        if not issubclass(generator_class, BaseSignalGenerator):
            raise TypeError(
                f"{generator_class.__name__} must inherit from BaseSignalGenerator"
            )
        with self._registry_lock:
            self._registry[name] = generator_class

    def get(self, name: str, **params) -> BaseSignalGenerator:
        """Instantiate a registered indicator with the given parameters.

        Args:
            name: The registered name of the indicator.
            **params: Keyword arguments forwarded to the indicator's ``__init__``.

        Returns:
            A new instance of the requested indicator.

        Raises:
            KeyError: If the name is not registered.
        """
        with self._registry_lock:
            if name not in self._registry:
                raise KeyError(
                    f"Indicator '{name}' is not registered. "
                    f"Available: {list(self._registry.keys())}"
                )
            cls = self._registry[name]
        return cls(**params)

    def list_all(self) -> List[str]:
        """Return a sorted list of all registered indicator names."""
        with self._registry_lock:
            return sorted(self._registry.keys())

    def auto_discover(self, package_path: str | None = None) -> int:
        """Scan ``src/indicators/`` for subclasses of :class:`BaseSignalGenerator`.

        Walks the package directory, imports each module, and registers every
        concrete (non-abstract) subclass it finds.

        Args:
            package_path: Optional override for the package to scan.
                Defaults to ``src.indicators``.

        Returns:
            Number of indicator classes registered.
        """
        if package_path is None:
            package_path = "src.indicators"

        package = importlib.import_module(package_path)
        count = 0

        for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
            full_name = f"{package_path}.{module_name}"
            try:
                module = importlib.import_module(full_name)
            except ImportError:
                continue

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BaseSignalGenerator)
                    and obj is not BaseSignalGenerator
                    and not inspect.isabstract(obj)
                ):
                    indicator_name = getattr(obj, "name", obj.__name__)
                    self.register(indicator_name, obj)
                    count += 1

        return count


# Module-level convenience function
_auto_discovered = False


def auto_discover_indicators(registry: IndicatorRegistry | None = None) -> int:
    """Convenience wrapper to auto-discover indicators on the global registry.

    Safe to call multiple times; discovery runs only once per process.

    Args:
        registry: Registry to use. Defaults to ``IndicatorRegistry.instance()``.

    Returns:
        Number of newly registered indicators.
    """
    global _auto_discovered
    if _auto_discovered:
        return 0

    if registry is None:
        registry = IndicatorRegistry.instance()

    count = registry.auto_discover()
    _auto_discovered = True
    return count
