"""
终极轮动策略框架 (Ultimate Rotation Strategy Framework)

整合聚宽社区50+策略精华，提供统一、可扩展、可实盘的交易框架。

模块:
- data_layer: 数据加载与缓存
- factor_engine: 因子计算引擎
- strategy_registry: 策略注册中心
- backtest_engine: 回测引擎
- strategy_evaluator: 策略评估器
- portfolio_optimizer: 组合优化器
- risk_manager: 风控系统
- live_trading: 实盘交易适配器
- monitor: 监控与日志
- pipeline: 主流水线

使用:
    from rotation_strategy_framework import Pipeline, PipelineConfig
    config = PipelineConfig.from_yaml("config.yaml")
    pipeline = Pipeline(config)
    pipeline.run_research()
"""

from .data_layer import DataConfig, DataCache, DataLoader, DataValidator
from .factor_engine import (
    FactorEngine,
    MomentumFactors,
    AllocationFactors,
    TimingFactors,
    RiskFactors,
)
from .strategy_registry import (
    StrategyRegistry,
    StrategyConfig,
    StrategyMetadata,
    ParamSpace,
)
from .backtest_engine import BacktestConfig, BacktestResult, BacktestEngine
from .strategy_evaluator import StrategyEvaluator, StrategyScorer, StrategyRanker
from .portfolio_optimizer import PortfolioOptimizer, PortfolioManager
from .risk_manager import (
    RiskController,
    RiskMonitor,
    CircuitBreaker,
    RiskLimits,
    RiskMetrics,
)
from .live_trading import TradingEngine, SimulatedBroker, OrderManager
from .monitor import MonitorSystem, Logger, AlertManager
from .pipeline import Pipeline, PipelineConfig, AutoStrategySelector

__version__ = "1.0.0"
__all__ = [
    "Pipeline",
    "PipelineConfig",
    "AutoStrategySelector",
    "DataConfig",
    "DataCache",
    "DataLoader",
    "DataValidator",
    "FactorEngine",
    "MomentumFactors",
    "AllocationFactors",
    "TimingFactors",
    "RiskFactors",
    "StrategyRegistry",
    "StrategyConfig",
    "StrategyMetadata",
    "ParamSpace",
    "BacktestConfig",
    "BacktestResult",
    "BacktestEngine",
    "StrategyEvaluator",
    "StrategyScorer",
    "StrategyRanker",
    "PortfolioOptimizer",
    "PortfolioManager",
    "RiskController",
    "RiskMonitor",
    "CircuitBreaker",
    "RiskLimits",
    "RiskMetrics",
    "TradingEngine",
    "SimulatedBroker",
    "OrderManager",
    "MonitorSystem",
    "Logger",
    "AlertManager",
]
