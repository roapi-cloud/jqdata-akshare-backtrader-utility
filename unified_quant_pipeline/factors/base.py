"""因子计算基类"""

from abc import abstractmethod
from typing import Dict, Optional
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from core.base import BaseFactor


class FactorCatalog:
    """因子目录 - 注册所有可用因子"""

    _factors: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str):
        """注册因子

        Args:
            name: 因子名称

        Returns:
            装饰器函数
        """

        def decorator(factor_cls):
            cls._factors[name] = factor_cls
            factor_cls.name = name
            return factor_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> type:
        """获取因子类

        Args:
            name: 因子名称

        Returns:
            因子类

        Raises:
            KeyError: 因子不存在时抛出
        """
        if name not in cls._factors:
            raise KeyError(
                f"Factor '{name}' not found. Available: {list(cls._factors.keys())}"
            )
        return cls._factors[name]

    @classmethod
    def list(cls) -> list:
        """列出所有因子

        Returns:
            因子名称列表
        """
        return list(cls._factors.keys())
