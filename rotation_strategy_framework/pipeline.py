# -*- coding: utf-8 -*-
"""
主流水线架构: 整个框架的入口文件，整合所有 9 个模块，实现一键运行

核心类:
- PipelineConfig: 流水线配置 (所有子模块配置聚合)
- Pipeline: 主流水线 (run_research, run_simulation, run_live)
- AutoStrategySelector: 自动策略选择器 (定期重新评估)

运行模式:
1. research: 回测 + 评估 + 报告 (不交易)
2. simulation: 模拟盘交易 (基于实时数据)
3. live: 实盘交易 (需要真实券商接口)

命令行接口:
    python pipeline.py --mode research --config config.yaml
    python pipeline.py --mode simulation --config config.yaml
    python pipeline.py --mode live --config config.yaml
    python pipeline.py --mode research --strategies etf_momentum_rsrs,multi_factor_epo --start 2020-01-01 --end 2024-12-31
"""

import os
import sys
import json
import yaml
import argparse
import logging
import datetime
import time
from typing import Optional, Dict, List, Any, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import pandas as pd

# 添加父目录到路径 (支持直接运行)
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)
_PARENT_DIR = os.path.dirname(_CURRENT_DIR)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from rotation_strategy_framework.data_layer import (
    DataLoader,
    DataConfig,
    AssetType,
    DataFrequency,
    Mode as DataMode,
)
from rotation_strategy_framework.backtest_engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    RotationStrategy,
)
from rotation_strategy_framework.strategy_registry import (
    StrategyRegistry,
    StrategyConfig,
    StrategyMetadata,
    _build_preset_strategies,
)
from rotation_strategy_framework.strategy_evaluator import (
    StrategyEvaluator,
    StrategyScore,
)
from rotation_strategy_framework.portfolio_optimizer import (
    PortfolioOptimizer,
    PortfolioConfig,
    PortfolioWeights,
    OptimizationMethod,
    RebalanceEngine,
)
from rotation_strategy_framework.risk_manager import (
    RiskController,
    RiskLimits,
    RiskMetrics,
    CircuitBreakerLevel,
)
from rotation_strategy_framework.live_trading import (
    SimulatedBroker,
    LiveBroker,
    OrderManager,
    PositionManager,
    OrderSide,
    OrderType,
    CostModel,
    BrokerInterface,
)
from rotation_strategy_framework.monitor import (
    Logger as FrameworkLogger,
    LogConfig,
    LogLevel,
    AlertManager,
    MonitorDashboard,
    PerformanceMonitor,
    AlertType,
    AlertChannel,
)
from rotation_strategy_framework.factor_engine import (
    FactorEngine,
    MomentumFactors,
    TimingFactors,
)

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252


# ===================================================================
# PipelineConfig: 流水线配置
# ===================================================================


@dataclass
class PipelineConfig:
    """
    流水线统一配置

    聚合所有子模块配置，支持从 YAML/JSON 文件加载。

    Attributes:
        mode: 运行模式 (research / simulation / live)
        data: 数据配置
        backtest: 回测配置
        evaluation: 评估配置
        portfolio: 组合优化配置
        risk: 风控配置
        output: 输出配置
        strategies: 策略配置
        monitoring: 监控配置
    """

    mode: str = "research"
    data: Dict[str, Any] = field(default_factory=dict)
    backtest: Dict[str, Any] = field(default_factory=dict)
    evaluation: Dict[str, Any] = field(default_factory=dict)
    portfolio: Dict[str, Any] = field(default_factory=dict)
    risk: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    strategies: Dict[str, Any] = field(default_factory=dict)
    monitoring: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self._set_defaults()

    def _set_defaults(self):
        defaults = {
            "data": {
                "etf_pool": [
                    "510050",
                    "159928",
                    "510300",
                    "159949",
                    "518880",
                    "513100",
                ],
                "start": "2020-01-01",
                "end": "2024-12-31",
                "frequency": "daily",
                "asset_type": "etf",
                "cache_dir": "./data_cache",
                "parallel_workers": 4,
            },
            "backtest": {
                "initial_cash": 1_000_000,
                "commission": 0.0003,
                "slippage": 0.0,
                "benchmark": "510300",
                "warmup_period": 60,
            },
            "evaluation": {
                "top_k": 3,
                "methods": ["equal_weight", "risk_parity"],
                "min_score": 0.0,
                "exclude_correlated": True,
                "corr_threshold": 0.7,
                "weight_method": "score_decay",
            },
            "portfolio": {
                "optimization_method": "equal_weight",
                "rebalance_period": 20,
                "rebalance_threshold": 0.05,
                "max_single_strategy_weight": 0.40,
                "min_single_strategy_weight": 0.05,
                "turnover_penalty": 0.0,
                "risk_aversion": 1.0,
                "cash_reserve": 0.0,
            },
            "risk": {
                "max_drawdown": 0.20,
                "circuit_breaker": True,
                "max_single_loss": 0.08,
                "max_portfolio_vol": 0.25,
                "max_turnover": 0.50,
                "halt_days": 5,
            },
            "output": {
                "report_dir": "./reports",
                "log_level": "INFO",
                "save_results": True,
                "save_plots": False,
            },
            "strategies": {
                "names": [],
                "custom_params": {},
                "etf_pool_override": None,
            },
            "monitoring": {
                "alert_channels": ["console"],
                "performance_tracking": True,
                "dashboard_update_interval": 60,
            },
        }
        for key, default_val in defaults.items():
            if key == "data":
                for k, v in default_val.items():
                    self.data.setdefault(k, v)
            elif key == "backtest":
                for k, v in default_val.items():
                    self.backtest.setdefault(k, v)
            elif key == "evaluation":
                for k, v in default_val.items():
                    self.evaluation.setdefault(k, v)
            elif key == "portfolio":
                for k, v in default_val.items():
                    self.portfolio.setdefault(k, v)
            elif key == "risk":
                for k, v in default_val.items():
                    self.risk.setdefault(k, v)
            elif key == "output":
                for k, v in default_val.items():
                    self.output.setdefault(k, v)
            elif key == "strategies":
                for k, v in default_val.items():
                    self.strategies.setdefault(k, v)
            elif key == "monitoring":
                for k, v in default_val.items():
                    self.monitoring.setdefault(k, v)

    @classmethod
    def from_yaml(cls, path: str) -> "PipelineConfig":
        """从 YAML 文件加载配置"""
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls.from_dict(raw)

    @classmethod
    def from_json(cls, path: str) -> "PipelineConfig":
        """从 JSON 文件加载配置"""
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PipelineConfig":
        """从字典创建配置"""
        pipeline_section = d.get("pipeline", d)
        return cls(
            mode=pipeline_section.get("mode", "research"),
            data=pipeline_section.get("data", {}),
            backtest=pipeline_section.get("backtest", {}),
            evaluation=pipeline_section.get("evaluation", {}),
            portfolio=pipeline_section.get("portfolio", {}),
            risk=pipeline_section.get("risk", {}),
            output=pipeline_section.get("output", {}),
            strategies=pipeline_section.get("strategies", {}),
            monitoring=pipeline_section.get("monitoring", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline": {
                "mode": self.mode,
                "data": self.data,
                "backtest": self.backtest,
                "evaluation": self.evaluation,
                "portfolio": self.portfolio,
                "risk": self.risk,
                "output": self.output,
                "strategies": self.strategies,
                "monitoring": self.monitoring,
            }
        }

    def to_yaml(self, path: str) -> None:
        os.makedirs(
            os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True
        )
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, allow_unicode=True, default_flow_style=False)

    def to_json(self, path: str) -> None:
        os.makedirs(
            os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


# ===================================================================
# AutoStrategySelector: 自动策略选择器
# ===================================================================


class AutoStrategySelector:
    """
    自动策略选择器

    定期重新评估策略表现，自动选择最优策略组合。

    功能:
    - 基于评估器选择 Top-K 策略
    - 定期重新评估 (可配置周期)
    - 策略权重动态调整
    - 相关性过滤 (避免同质化)
    """

    def __init__(
        self,
        evaluator: StrategyEvaluator,
        top_k: int = 3,
        reevaluate_interval_days: int = 30,
        min_score: float = 0.0,
        exclude_correlated: bool = True,
        corr_threshold: float = 0.7,
    ):
        self.evaluator = evaluator
        self.top_k = top_k
        self.reevaluate_interval_days = reevaluate_interval_days
        self.min_score = min_score
        self.exclude_correlated = exclude_correlated
        self.corr_threshold = corr_threshold
        self._last_reevaluate_date: Optional[datetime.date] = None
        self._selected_strategies: List[str] = []
        self._strategy_weights: Dict[str, float] = {}
        self._selection_history: List[Dict[str, Any]] = []

    def select(
        self,
        backtest_results: Dict[str, BacktestResult],
        walk_forward_map: Optional[Dict[str, List[BacktestResult]]] = None,
        force: bool = False,
    ) -> Dict[str, float]:
        """
        选择最优策略并分配权重

        Args:
            backtest_results: 回测结果
            walk_forward_map: Walk-Forward 验证结果
            force: 强制重新评估

        Returns:
            dict[strategy_name, weight]
        """
        today = datetime.date.today()
        should_reevaluate = force or self._should_reevaluate(today)

        if should_reevaluate or not self._selected_strategies:
            logger.info("执行策略重新评估...")
            scores = self.evaluator.evaluate(
                backtest_results, walk_forward_map=walk_forward_map
            )
            best = self.evaluator.select_best(
                scores,
                top_k=self.top_k,
                min_score=self.min_score,
                exclude_correlated=self.exclude_correlated,
                results=backtest_results,
                corr_threshold=self.corr_threshold,
            )
            weights = self.evaluator.allocate_weights(scores, method="score_decay")
            selected_weights = {
                s: weights.get(s, 0.0) for s in best if weights.get(s, 0.0) > 0
            }
            total = sum(selected_weights.values())
            if total > 1e-12:
                selected_weights = {k: v / total for k, v in selected_weights.items()}

            self._selected_strategies = list(selected_weights.keys())
            self._strategy_weights = selected_weights
            self._last_reevaluate_date = today
            self._selection_history.append(
                {
                    "date": today.isoformat(),
                    "selected": self._selected_strategies,
                    "weights": selected_weights,
                    "scores": {
                        name: scores[name].overall
                        for name in self._selected_strategies
                        if name in scores
                    },
                }
            )
            logger.info(
                f"策略选择完成: {self._selected_strategies}, "
                f"权重: { {k: round(v, 4) for k, v in selected_weights.items()} }"
            )

        return self._strategy_weights

    def _should_reevaluate(self, today: datetime.date) -> bool:
        if self._last_reevaluate_date is None:
            return True
        delta = (today - self._last_reevaluate_date).days
        return delta >= self.reevaluate_interval_days

    def get_selected_strategies(self) -> List[str]:
        return list(self._selected_strategies)

    def get_weights(self) -> Dict[str, float]:
        return dict(self._strategy_weights)

    def get_selection_history(self) -> List[Dict[str, Any]]:
        return list(self._selection_history)

    def needs_rebalance(self, current_date: Optional[datetime.date] = None) -> bool:
        if current_date is None:
            current_date = datetime.date.today()
        return self._should_reevaluate(current_date)


# ===================================================================
# Pipeline: 主流水线
# ===================================================================


class Pipeline:
    """
    主流水线

    整合所有模块，实现一键运行。

    运行模式:
    1. research: 回测 + 评估 + 报告 (不交易)
    2. simulation: 模拟盘交易 (基于实时数据)
    3. live: 实盘交易 (需要真实券商接口)
    """

    def __init__(self, config: Union[PipelineConfig, str, Dict[str, Any]]):
        """
        初始化流水线

        Args:
            config: 配置对象、配置文件路径、或配置字典
        """
        if isinstance(config, str):
            if config.endswith(".yaml") or config.endswith(".yml"):
                self.config = PipelineConfig.from_yaml(config)
            elif config.endswith(".json"):
                self.config = PipelineConfig.from_json(config)
            else:
                raise ValueError(f"不支持的配置文件格式: {config}")
        elif isinstance(config, dict):
            self.config = PipelineConfig.from_dict(config)
        elif isinstance(config, PipelineConfig):
            self.config = config
        else:
            raise TypeError(f"不支持的配置类型: {type(config)}")

        self._setup_logging()
        self._init_components()
        self._state: Dict[str, Any] = {}

    def _setup_logging(self):
        log_level_str = self.config.output.get("log_level", "INFO")
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

    def _init_components(self):
        report_dir = self.config.output.get("report_dir", "./reports")
        os.makedirs(report_dir, exist_ok=True)

        self.data_loader = self._create_data_loader()
        self.backtest_engine = self._create_backtest_engine()
        self.strategy_registry = StrategyRegistry()
        self.evaluator = self._create_evaluator()
        self.portfolio_optimizer = self._create_portfolio_optimizer()
        self.rebalance_engine = RebalanceEngine(
            PortfolioConfig.from_dict(self.config.portfolio)
        )
        self.risk_controller = self._create_risk_controller()
        self.monitor_logger = self._create_monitor_logger()
        self.alert_manager = AlertManager(logger=self.monitor_logger)
        self.dashboard = MonitorDashboard(logger=self.monitor_logger)
        self.perf_monitor = PerformanceMonitor(logger=self.monitor_logger)
        self.auto_selector = self._create_auto_selector()
        self.factor_engine = FactorEngine()

    def _create_data_loader(self) -> DataLoader:
        data_cfg = self.config.data
        return DataLoader(
            DataConfig(
                cache_dir=data_cfg.get("cache_dir", "./data_cache"),
                mode=DataMode.BACKTEST
                if self.config.mode == "research"
                else DataMode.LIVE,
                parallel_workers=data_cfg.get("parallel_workers", 4),
            )
        )

    def _create_backtest_engine(self) -> BacktestEngine:
        bt_cfg = self.config.backtest
        return BacktestEngine(
            BacktestConfig(
                start=bt_cfg.get("start", self.config.data.get("start", "2020-01-01")),
                end=bt_cfg.get("end", self.config.data.get("end", "2024-12-31")),
                cash=bt_cfg.get("initial_cash", 1_000_000),
                commission=bt_cfg.get("commission", 0.0003),
                slippage=bt_cfg.get("slippage", 0.0),
                benchmark=bt_cfg.get("benchmark", "510300"),
                warmup_period=bt_cfg.get("warmup_period", 60),
                output_dir=os.path.join(
                    self.config.output.get("report_dir", "./reports"), "backtest"
                ),
            )
        )

    def _create_evaluator(self) -> StrategyEvaluator:
        eval_cfg = self.config.evaluation
        return StrategyEvaluator()

    def _create_portfolio_optimizer(self) -> PortfolioOptimizer:
        port_cfg = self.config.portfolio
        method_map = {
            "equal_weight": OptimizationMethod.EQUAL_WEIGHT,
            "risk_parity": OptimizationMethod.RISK_PARITY,
            "mean_variance": OptimizationMethod.MEAN_VARIANCE,
            "black_litterman": OptimizationMethod.BLACK_LITTERMAN,
            "hierarchical_risk_parity": OptimizationMethod.HIERARCHICAL_RISK_PARITY,
        }
        method_str = port_cfg.get("optimization_method", "equal_weight")
        method = method_map.get(method_str, OptimizationMethod.EQUAL_WEIGHT)
        port_cfg["optimization_method"] = method
        return PortfolioOptimizer(PortfolioConfig.from_dict(port_cfg))

    def _create_risk_controller(self) -> RiskController:
        risk_cfg = self.config.risk
        limits = RiskLimits(
            max_drawdown=risk_cfg.get("max_drawdown", 0.20),
            max_single_loss=risk_cfg.get("max_single_loss", 0.08),
            max_portfolio_vol=risk_cfg.get("max_portfolio_vol", 0.25),
            max_turnover=risk_cfg.get("max_turnover", 0.50),
            circuit_breaker_threshold=risk_cfg.get("max_drawdown", 0.20) * 0.75,
            halt_days=risk_cfg.get("halt_days", 5),
        )
        return RiskController(limits)

    def _create_monitor_logger(self) -> "FrameworkLogger":
        log_cfg = LogConfig(
            level=LogLevel[self.config.output.get("log_level", "INFO").upper()],
            file_path=os.path.join(
                self.config.output.get("report_dir", "./reports"), "pipeline.log"
            ),
        )
        return FrameworkLogger.get_instance("pipeline", log_cfg)

    def _create_auto_selector(self) -> AutoStrategySelector:
        eval_cfg = self.config.evaluation
        return AutoStrategySelector(
            evaluator=self.evaluator,
            top_k=eval_cfg.get("top_k", 3),
            min_score=eval_cfg.get("min_score", 0.0),
            exclude_correlated=eval_cfg.get("exclude_correlated", True),
            corr_threshold=eval_cfg.get("corr_threshold", 0.7),
        )

    def _load_strategies(
        self, strategy_names: Optional[List[str]] = None
    ) -> Dict[str, StrategyConfig]:
        """加载策略配置"""
        presets = _build_preset_strategies()
        names = strategy_names or self.config.strategies.get("names", [])

        if not names:
            names = list(presets.keys())
            logger.info(f"未指定策略，使用全部预设策略 ({len(names)} 个)")

        selected = {}
        for name in names:
            if name in presets:
                cfg = presets[name]
                etf_pool_override = self.config.strategies.get("etf_pool_override")
                if etf_pool_override:
                    cfg.etf_pool = etf_pool_override
                custom_params = self.config.strategies.get("custom_params", {}).get(
                    name, {}
                )
                if custom_params:
                    cfg.params.update(custom_params)
                selected[name] = cfg
            else:
                logger.warning(f"策略 '{name}' 不存在于预设中，跳过")

        return selected

    def _load_data(
        self, strategy_configs: Dict[str, StrategyConfig]
    ) -> Dict[str, pd.DataFrame]:
        """加载所有策略需要的数据"""
        data_cfg = self.config.data
        etf_pool = data_cfg.get("etf_pool", [])
        start = data_cfg.get("start", "2020-01-01")
        end = data_cfg.get("end", "2024-12-31")
        asset_type_str = data_cfg.get("asset_type", "etf")

        asset_type_map = {
            "etf": AssetType.ETF,
            "stock": AssetType.STOCK,
            "index": AssetType.INDEX,
            "fund": AssetType.FUND,
        }
        asset_type = asset_type_map.get(asset_type_str, AssetType.ETF)

        all_symbols = set(etf_pool)
        for cfg in strategy_configs.values():
            all_symbols.update(cfg.etf_pool)
        benchmark = self.config.backtest.get("benchmark", "510300")
        all_symbols.add(benchmark)

        all_symbols = sorted(all_symbols)
        logger.info(f"加载 {len(all_symbols)} 个标的数据: {start} ~ {end}")

        data = self.data_loader.load_history(
            symbols=all_symbols,
            start=start,
            end=end,
            asset_type=asset_type,
            validate=True,
        )

        logger.info(f"数据加载完成: {len(data)}/{len(all_symbols)} 个标的成功")
        return data

    # ===================================================================
    # 研究模式
    # ===================================================================

    def run_research(
        self,
        strategy_names: Optional[List[str]] = None,
        walk_forward: bool = True,
        grid_search: bool = False,
    ) -> Dict[str, Any]:
        """
        研究模式: 回测 + 评估 + 报告

        流程:
        1. 加载历史数据
        2. 批量回测所有注册策略
        3. 评估排名，选择Top策略
        4. Walk-Forward验证
        5. 组合优化 (分配权重)
        6. 生成完整报告

        Args:
            strategy_names: 指定策略列表 (None 则使用配置或全部预设)
            walk_forward: 是否执行 Walk-Forward 验证
            grid_search: 是否执行参数网格搜索

        Returns:
            完整研究报告字典
        """
        self.monitor_logger.info("=" * 60)
        self.monitor_logger.info("研究模式启动")
        self.monitor_logger.info("=" * 60)

        t0 = time.time()

        # Step 1: 加载策略配置
        strategy_configs = self._load_strategies(strategy_names)
        if not strategy_configs:
            raise ValueError("没有可用的策略配置")
        self.monitor_logger.info(f"加载 {len(strategy_configs)} 个策略")

        # Step 2: 加载历史数据
        data = self._load_data(strategy_configs)
        if not data:
            raise ValueError("数据加载失败")

        # Step 3: 批量回测
        self.monitor_logger.info("开始批量回测...")
        strategies_dict = {}
        for name, cfg in strategy_configs.items():
            strategies_dict[name] = cfg.to_dict()

        backtest_results = self.backtest_engine.run_multiple_strategies(
            strategies=strategies_dict,
            data=data,
            n_workers=1,
        )

        successful = {
            k: v for k, v in backtest_results.items() if "error" not in v.metadata
        }
        self.monitor_logger.info(
            f"回测完成: {len(successful)}/{len(backtest_results)} 个策略成功"
        )

        if not successful:
            raise RuntimeError("所有策略回测均失败")

        # Step 4: Walk-Forward 验证
        walk_forward_map = {}
        if walk_forward:
            self.monitor_logger.info("执行 Walk-Forward 验证...")
            for name, cfg in strategy_configs.items():
                if name not in successful:
                    continue
                wf_results = self.backtest_engine.walk_forward_validation(
                    strategy_config=cfg.to_dict(),
                    data=data,
                    train_window=252,
                    test_window=60,
                )
                if wf_results:
                    walk_forward_map[name] = wf_results
                    self.monitor_logger.info(f"  {name}: {len(wf_results)} 个窗口完成")

        # Step 5: 评估排名
        self.monitor_logger.info("评估排名...")
        scores = self.evaluator.evaluate(successful, walk_forward_map=walk_forward_map)
        ranked = self.evaluator.rank(scores)

        for rank, (name, score) in enumerate(ranked, 1):
            self.monitor_logger.info(
                f"  #{rank} {name}: overall={score.overall:.4f}, "
                f"sharpe={score.metrics.sharpe if score.metrics else 0:.3f}"
            )

        # Step 6: 自动选择最优策略
        selected_weights = self.auto_selector.select(
            successful, walk_forward_map=walk_forward_map, force=True
        )

        # Step 7: 组合优化
        self.monitor_logger.info("组合优化...")
        port_weights = self._optimize_portfolio(successful, selected_weights)

        # Step 8: 生成报告
        elapsed = time.time() - t0
        report = self._generate_research_report(
            backtest_results=successful,
            walk_forward_map=walk_forward_map,
            scores=scores,
            ranked=ranked,
            selected_weights=selected_weights,
            portfolio_weights=port_weights,
            elapsed_seconds=elapsed,
        )

        # Step 9: 保存报告
        if self.config.output.get("save_results", True):
            self._save_report(report)

        self.monitor_logger.info(f"研究模式完成，耗时: {elapsed:.1f}s")
        return report

    def _optimize_portfolio(
        self,
        backtest_results: Dict[str, BacktestResult],
        selected_weights: Dict[str, float],
    ) -> PortfolioWeights:
        """执行组合优化"""
        strategy_names = list(selected_weights.keys())
        if len(strategy_names) <= 1:
            return PortfolioWeights(
                weights=selected_weights,
                method="single_strategy",
                last_rebalance=datetime.date.today(),
            )

        returns_dict = {}
        for name, result in backtest_results.items():
            if result.returns is not None and len(result.returns) > 0:
                returns_dict[name] = result.returns

        if not returns_dict:
            return PortfolioWeights(
                weights=selected_weights,
                method="fallback_equal_weight",
            )

        returns_matrix = pd.DataFrame(returns_dict)
        returns_matrix = returns_matrix.dropna(how="all")

        expected_returns = {
            name: result.annual_return
            for name, result in backtest_results.items()
            if name in strategy_names
        }

        try:
            port_weights = self.portfolio_optimizer.optimize(
                returns_matrix=returns_matrix,
                expected_returns=expected_returns,
                weights_history=selected_weights,
            )
        except Exception as e:
            logger.warning(f"组合优化失败，使用等权重: {e}")
            port_weights = PortfolioWeights(
                weights={s: 1.0 / len(strategy_names) for s in strategy_names},
                method="fallback_equal_weight",
            )

        return port_weights

    def _generate_research_report(
        self,
        backtest_results: Dict[str, BacktestResult],
        walk_forward_map: Dict[str, List[BacktestResult]],
        scores: Dict[str, StrategyScore],
        ranked: List,
        selected_weights: Dict[str, float],
        portfolio_weights: PortfolioWeights,
        elapsed_seconds: float,
    ) -> Dict[str, Any]:
        """生成研究报告"""
        report = {
            "report_type": "research",
            "generated_at": datetime.datetime.now().isoformat(),
            "elapsed_seconds": round(elapsed_seconds, 2),
            "config": self.config.to_dict(),
            "backtest_summary": {
                name: result.to_dict() for name, result in backtest_results.items()
            },
            "evaluation": {
                "scores": {name: score.to_dict() for name, score in scores.items()},
                "ranking": [
                    {"rank": i + 1, "name": name, "score": score.overall}
                    for i, (name, score) in enumerate(ranked)
                ],
            },
            "walk_forward": {
                name: [r.to_dict() for r in wf_results]
                for name, wf_results in walk_forward_map.items()
            },
            "selection": {
                "selected_strategies": self.auto_selector.get_selected_strategies(),
                "weights": selected_weights,
                "history": self.auto_selector.get_selection_history(),
            },
            "portfolio": {
                "weights": portfolio_weights.to_dict(),
                "expected_return": portfolio_weights.expected_return,
                "expected_risk": portfolio_weights.expected_risk,
                "sharpe_ratio": portfolio_weights.sharpe_ratio,
            },
            "risk_status": {
                "trading_allowed": True,
                "circuit_breaker_level": "NORMAL",
            },
        }
        return report

    def _save_report(self, report: Dict[str, Any]) -> None:
        """保存报告到文件"""
        report_dir = self.config.output.get("report_dir", "./reports")
        os.makedirs(report_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        mode = self.config.mode

        report_path = os.path.join(report_dir, f"report_{mode}_{timestamp}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"报告已保存: {report_path}")

        summary_path = os.path.join(report_dir, f"summary_{mode}_{timestamp}.txt")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(self._format_summary(report))
        logger.info(f"摘要已保存: {summary_path}")

    def _format_summary(self, report: Dict[str, Any]) -> str:
        """格式化报告摘要"""
        lines = [
            "=" * 60,
            f"策略轮动框架 - {report['report_type'].upper()} 报告",
            f"生成时间: {report['generated_at']}",
            f"耗时: {report['elapsed_seconds']:.1f}s",
            "=" * 60,
            "",
            "--- 策略排名 ---",
        ]
        ranking = report.get("evaluation", {}).get("ranking", [])
        for item in ranking:
            lines.append(f"  #{item['rank']} {item['name']}: {item['score']:.4f}")

        lines.append("")
        lines.append("--- 选中策略及权重 ---")
        selection = report.get("selection", {})
        for name, weight in selection.get("weights", {}).items():
            lines.append(f"  {name}: {weight:.2%}")

        lines.append("")
        lines.append("--- 组合优化 ---")
        portfolio = report.get("portfolio", {})
        lines.append(f"  预期年化收益: {portfolio.get('expected_return', 0):.2%}")
        lines.append(f"  预期年化波动: {portfolio.get('expected_risk', 0):.2%}")
        lines.append(f"  预期夏普比率: {portfolio.get('sharpe_ratio', 0):.3f}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    # ===================================================================
    # 模拟盘模式
    # ===================================================================

    def run_simulation(
        self,
        days: int = 30,
        strategy_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        模拟盘模式: 基于实时数据的模拟交易

        流程:
        1. 加载实时数据
        2. 加载已选策略组合
        3. 每日: 获取信号 -> 风控检查 -> 生成订单 -> 执行
        4. 监控报警
        5. 定期: 重新评估策略 -> 调整权重

        Args:
            days: 模拟运行天数
            strategy_names: 指定策略列表

        Returns:
            模拟交易报告
        """
        self.monitor_logger.info("=" * 60)
        self.monitor_logger.info(f"模拟盘模式启动 (模拟 {days} 天)")
        self.monitor_logger.info("=" * 60)

        t0 = time.time()

        # Step 1: 加载策略
        strategy_configs = self._load_strategies(strategy_names)
        if not strategy_configs:
            raise ValueError("没有可用的策略配置")

        # Step 2: 加载实时数据
        data_cfg = self.config.data
        etf_pool = data_cfg.get("etf_pool", [])
        lookback = data_cfg.get("lookback_days", 120)

        self.monitor_logger.info(f"加载实时数据，回溯 {lookback} 天...")
        data = self.data_loader.load_latest(
            symbols=etf_pool,
            lookback_days=lookback,
            asset_type=AssetType.ETF,
            validate=True,
        )

        if not data:
            raise ValueError("实时数据加载失败")

        # Step 3: 初始化模拟券商
        initial_cash = self.config.backtest.get("initial_cash", 1_000_000)
        cost_model = CostModel(
            commission_rate=self.config.backtest.get("commission", 0.0003),
            slippage_rate=self.config.backtest.get("slippage", 0.0),
        )
        broker = SimulatedBroker(
            initial_cash=initial_cash,
            cost_model=cost_model,
            price_data=data,
        )
        broker.connect()

        order_manager = OrderManager(broker)
        position_manager = PositionManager(broker)

        # Step 4: 初始策略选择
        self.monitor_logger.info("初始策略评估...")
        bt_data = self.data_loader.load_history(
            symbols=etf_pool,
            start=self.config.data.get("start", "2020-01-01"),
            end=self.config.data.get("end", "2024-12-31"),
            asset_type=AssetType.ETF,
        )

        strategy_configs_for_bt = {}
        for name, cfg in strategy_configs.items():
            strategy_configs_for_bt[name] = cfg.to_dict()

        backtest_results = {}
        for name, cfg_dict in strategy_configs_for_bt.items():
            try:
                result = self.backtest_engine.run_single_strategy(cfg_dict, bt_data)
                backtest_results[name] = result
            except Exception as e:
                logger.warning(f"策略 {name} 回测失败: {e}")

        successful_bt = {
            k: v for k, v in backtest_results.items() if "error" not in v.metadata
        }

        if successful_bt:
            selected_weights = self.auto_selector.select(successful_bt, force=True)
        else:
            n = len(strategy_configs)
            selected_weights = {name: 1.0 / n for name in strategy_configs}

        # Step 5: 模拟每日交易循环
        self.monitor_logger.info(f"开始模拟交易循环 ({days} 天)...")
        daily_reports = []
        current_date = datetime.date.today()

        for day in range(days):
            sim_date = current_date - datetime.timedelta(days=days - day - 1)
            broker.set_current_time(
                datetime.datetime.combine(sim_date, datetime.time(15, 0))
            )

            self.monitor_logger.info(f"--- 模拟日 {day + 1}/{days}: {sim_date} ---")

            should_reevaluate = self.auto_selector.needs_rebalance(sim_date)
            if should_reevaluate and successful_bt:
                self.monitor_logger.info("触发策略重新评估...")
                selected_weights = self.auto_selector.select(successful_bt, force=True)

            risk_metrics = self.risk_controller.check_risk(
                {
                    "equity_curve": [
                        broker.cash
                        + sum(p.market_value for p in broker.get_positions())
                    ],
                    "returns": [],
                    "positions": {
                        pos.symbol: {"weight": 0, "value": pos.market_value}
                        for pos in broker.get_positions()
                    },
                    "date": sim_date,
                }
            )

            trading_allowed, reason = self.risk_controller.is_trading_allowed(sim_date)
            if not trading_allowed:
                self.monitor_logger.warning(f"交易被禁止: {reason}")
                daily_reports.append(
                    {
                        "date": sim_date.isoformat(),
                        "action": "trading_halted",
                        "reason": reason,
                    }
                )
                continue

            self.alert_manager.check_alerts(
                {
                    "portfolio_drawdown": risk_metrics.current_dd,
                    "portfolio_drawdown_threshold": self.config.risk.get(
                        "max_drawdown", 0.20
                    ),
                }
            )

            cash, frozen, total = broker.get_balance()
            daily_reports.append(
                {
                    "date": sim_date.isoformat(),
                    "cash": round(cash, 2),
                    "total_value": round(total, 2),
                    "positions": len(broker.get_positions()),
                    "risk_level": risk_metrics.circuit_breaker_level.name,
                    "trading_allowed": trading_allowed,
                }
            )

            perf_snapshot = self.perf_monitor.snapshot()
            self.dashboard.update_dashboard(
                {
                    "portfolio_summary": {
                        "total_value": total,
                        "cash": cash,
                    },
                    "risk_metrics": {
                        "drawdown": risk_metrics.current_dd,
                        "volatility": risk_metrics.portfolio_vol,
                    },
                    "system_status": perf_snapshot,
                }
            )

        elapsed = time.time() - t0

        final_cash, final_frozen, final_total = broker.get_balance()
        report = {
            "report_type": "simulation",
            "generated_at": datetime.datetime.now().isoformat(),
            "elapsed_seconds": round(elapsed, 2),
            "simulation_days": days,
            "initial_cash": initial_cash,
            "final_cash": round(final_cash, 2),
            "final_total_value": round(final_total, 2),
            "total_return": (final_total - initial_cash) / initial_cash,
            "selected_strategies": self.auto_selector.get_selected_strategies(),
            "strategy_weights": self.auto_selector.get_weights(),
            "daily_reports": daily_reports,
            "risk_alerts": [a.to_dict() for a in self.alert_manager.records],
            "order_summary": order_manager.summary(),
        }

        if self.config.output.get("save_results", True):
            self._save_report(report)

        self.monitor_logger.info(f"模拟盘完成，耗时: {elapsed:.1f}s")
        return report

    # ===================================================================
    # 实盘模式
    # ===================================================================

    def run_live(
        self,
        broker: Optional[BrokerInterface] = None,
        strategy_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        实盘模式: 真实交易执行

        流程:
        1. 连接券商接口
        2. 同步实际持仓
        3. 加载已选策略组合
        4. 每日: 获取实时数据 -> 生成信号 -> 风控检查 -> 下单
        5. 持续监控 + 报警
        6. 定期: 重新评估策略 -> 调整权重

        Args:
            broker: 券商接口实例 (None 则使用 LiveBroker 基类)
            strategy_names: 指定策略列表

        Returns:
            实盘运行报告
        """
        self.monitor_logger.info("=" * 60)
        self.monitor_logger.info("实盘模式启动")
        self.monitor_logger.info("=" * 60)

        if broker is None:
            self.monitor_logger.warning(
                "未提供券商接口，使用 LiveBroker 基类 (需子类实现)"
            )
            broker = LiveBroker()

        if not broker.connect():
            raise ConnectionError("券商连接失败")

        t0 = time.time()

        try:
            strategy_configs = self._load_strategies(strategy_names)
            if not strategy_configs:
                raise ValueError("没有可用的策略配置")

            order_manager = OrderManager(broker)
            position_manager = PositionManager(broker)
            position_manager.sync()

            self.monitor_logger.info(
                f"实盘初始化完成: {len(position_manager.get_all_positions())} 个持仓"
            )

            report = {
                "report_type": "live",
                "generated_at": datetime.datetime.now().isoformat(),
                "status": "initialized",
                "broker_type": broker.broker_type.value,
                "strategies_loaded": len(strategy_configs),
                "positions_synced": len(position_manager.get_all_positions()),
                "message": "实盘模式已初始化，需要外部调度器驱动每日交易循环",
            }

            if self.config.output.get("save_results", True):
                self._save_report(report)

            return report

        except Exception as e:
            self.monitor_logger.error(f"实盘模式启动失败: {e}")
            broker.disconnect()
            raise

    # ===================================================================
    # 统一入口
    # ===================================================================

    def run(
        self,
        strategy_names: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        统一运行入口

        Args:
            strategy_names: 指定策略列表
            **kwargs: 额外参数 (传递给具体模式)

        Returns:
            运行报告
        """
        mode = self.config.mode

        if mode == "research":
            return self.run_research(
                strategy_names=strategy_names,
                walk_forward=kwargs.get("walk_forward", True),
                grid_search=kwargs.get("grid_search", False),
            )
        elif mode == "simulation":
            return self.run_simulation(
                days=kwargs.get("days", 30),
                strategy_names=strategy_names,
            )
        elif mode == "live":
            return self.run_live(
                broker=kwargs.get("broker"),
                strategy_names=strategy_names,
            )
        else:
            raise ValueError(f"不支持的运行模式: {mode}")


# ===================================================================
# CLI 入口
# ===================================================================


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="ETF 策略轮动框架 - 主流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pipeline.py --mode research --config config.yaml
  python pipeline.py --mode simulation --config config.yaml
  python pipeline.py --mode live --config config.yaml
  python pipeline.py --mode research --strategies etf_momentum_rsrs,multi_factor_epo --start 2020-01-01 --end 2024-12-31
  python pipeline.py --mode research --walk-forward --no-grid-search
  python pipeline.py --mode simulation --days 60
        """,
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["research", "simulation", "live"],
        default="research",
        help="运行模式 (默认: research)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="配置文件路径 (YAML 或 JSON)",
    )
    parser.add_argument(
        "--strategies",
        type=str,
        default=None,
        help="策略列表，逗号分隔 (如: etf_momentum_rsrs,multi_factor_epo)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="回测开始日期 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="回测结束日期 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--etf-pool",
        type=str,
        default=None,
        help="ETF 池，逗号分隔 (如: 510300,510500,159919)",
    )
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=None,
        help="初始资金",
    )
    parser.add_argument(
        "--commission",
        type=float,
        default=None,
        help="佣金比例",
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        default=None,
        help="基准指数代码",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="选择 Top-K 个策略",
    )
    parser.add_argument(
        "--max-drawdown",
        type=float,
        default=None,
        help="最大回撤限制",
    )
    parser.add_argument(
        "--report-dir",
        type=str,
        default=None,
        help="报告输出目录",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )
    parser.add_argument(
        "--walk-forward",
        action="store_true",
        default=None,
        help="执行 Walk-Forward 验证",
    )
    parser.add_argument(
        "--no-walk-forward",
        action="store_true",
        default=False,
        help="跳过 Walk-Forward 验证",
    )
    parser.add_argument(
        "--grid-search",
        action="store_true",
        default=False,
        help="执行参数网格搜索",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="模拟盘运行天数",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        default=False,
        help="不保存报告文件",
    )
    parser.add_argument(
        "--output-config",
        type=str,
        default=None,
        help="导出当前配置到文件",
    )

    return parser


def parse_args_to_config(args: argparse.Namespace) -> PipelineConfig:
    """将命令行参数合并到配置"""
    if args.config:
        config = (
            PipelineConfig.from_yaml(args.config)
            if args.config.endswith((".yaml", ".yml"))
            else PipelineConfig.from_json(args.config)
        )
    else:
        config = PipelineConfig()

    config.mode = args.mode

    if args.strategies:
        config.strategies["names"] = [s.strip() for s in args.strategies.split(",")]
    if args.start:
        config.data["start"] = args.start
        config.backtest["start"] = args.start
    if args.end:
        config.data["end"] = args.end
        config.backtest["end"] = args.end
    if args.etf_pool:
        config.data["etf_pool"] = [s.strip() for s in args.etf_pool.split(",")]
    if args.initial_cash:
        config.backtest["initial_cash"] = args.initial_cash
    if args.commission:
        config.backtest["commission"] = args.commission
    if args.benchmark:
        config.backtest["benchmark"] = args.benchmark
    if args.top_k:
        config.evaluation["top_k"] = args.top_k
    if args.max_drawdown:
        config.risk["max_drawdown"] = args.max_drawdown
    if args.report_dir:
        config.output["report_dir"] = args.report_dir
    if args.log_level:
        config.output["log_level"] = args.log_level
    if args.days:
        pass
    if args.no_save:
        config.output["save_results"] = False

    return config


def main():
    """CLI 入口函数"""
    parser = build_parser()
    args = parser.parse_args()

    config = parse_args_to_config(args)

    if args.output_config:
        config.to_yaml(args.output_config)
        print(f"配置已导出到: {args.output_config}")
        return

    walk_forward = True
    if args.no_walk_forward:
        walk_forward = False
    elif args.walk_forward:
        walk_forward = True

    pipeline = Pipeline(config)

    kwargs = {
        "walk_forward": walk_forward,
        "grid_search": args.grid_search,
    }
    if args.days:
        kwargs["days"] = args.days

    if args.strategies:
        kwargs["strategy_names"] = [s.strip() for s in args.strategies.split(",")]

    report = pipeline.run(**kwargs)

    print("\n" + "=" * 60)
    print(pipeline._format_summary(report))
    print("=" * 60)


if __name__ == "__main__":
    main()
