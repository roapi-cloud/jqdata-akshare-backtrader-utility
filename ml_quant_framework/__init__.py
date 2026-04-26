"""ML量化选股框架 - 通用机器学习量化流水线"""

__version__ = "1.0.0"
__author__ = "ML Quant Framework"

from ml_quant_framework.core.config import PipelineConfig
from ml_quant_framework.core.pipeline import MLPipeline

__all__ = ["PipelineConfig", "MLPipeline"]
