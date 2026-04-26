# -*- coding: utf-8 -*-
"""
策略注册中心: 统一策略元数据管理、预设策略配置、参数搜索空间、兼容性检查、版本管理

核心类:
- StrategyMetadata: 策略元数据 (name, category, risk_level, min_capital, expected_annual_return, max_drawdown_tolerance)
- StrategyConfig: 策略配置 (scoring_mode, allocation_mode, timing_method, params, etf_pool, rebalance_period)
- ParamSpace: 参数搜索空间 (param_name, type, range/default)
- StrategyRegistry: 注册中心 (register, get, list, search, validate)

预设策略 (14+ 种，来自聚宽50+策略精华):
1. etf_momentum_rsrs - 动量+RSRS (经典)
2. etf_core_asset - 核心资产 (对数回归)
3. etf_bias_momentum - 乖离率动量
4. etf_kalman - 卡尔曼滤波
5. multi_factor_epo - 多因子+EPO
6. sector_heat - 板块热度
7. min_correlation - 最小相关性
8. epo_optimized - EPO优化
9. stock_bond_balance - 股债平衡
10. grid_trading - 网格交易
11. t0_momentum - T+0动量
12. chase_momentum - 追涨
13. ir_trend - IR趋势度
14. north_money_timing - 北向择时
"""

import os
import json
import logging
import datetime
from typing import Optional, Dict, List, Tuple, Any, Union, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from copy import deepcopy

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
REGISTRY_VERSION = "v1.0.0"


# ---------------------------------------------------------------------------
# 策略分类枚举
# ---------------------------------------------------------------------------
class StrategyCategory(Enum):
    """策略分类"""

    ETF_ROTATION = "etf_rotation"  # ETF轮动
    SECTOR_ROTATION = "sector_rotation"  # 行业轮动
    HYBRID = "hybrid"  # 混合
    T0_TRADING = "t0_trading"  # T+0
    CHASE_MOMENTUM = "chase_momentum"  # 追涨


class RiskLevel(Enum):
    """风险等级"""

    LOW = "low"  # 低风险
    MEDIUM = "medium"  # 中风险
    MEDIUM_HIGH = "medium_high"  # 中高风险
    HIGH = "high"  # 高风险


class ScoringMode(Enum):
    """评分模式"""

    MOMENTUM = "momentum"
    REGRESSION = "regression"
    LOG_REGRESSION = "log_regression"
    BIAS = "bias"
    KALMAN = "kalman"
    MULTI_FACTOR = "multi_factor"
    RSRS = "rsrs"
    SECTOR_HEAT = "sector_heat"
    CORRELATION = "correlation"
    EPO = "epo"
    IR_TREND = "ir_trend"
    NORTH_FLOW = "north_flow"


class AllocationMode(Enum):
    """配置模式"""

    TOP_N = "top_n"
    EPO = "epo"
    MIN_CORR = "min_corr"
    STOCK_BOND = "stock_bond"
    GRID = "grid"
    EQUAL_WEIGHT = "equal_weight"
    RISK_PARITY = "risk_parity"
    MOMENTUM_WEIGHT = "momentum_weight"


class TimingMethod(Enum):
    """择时方法"""

    NONE = "none"
    RSRS = "rsrs"
    MA_CROSS = "ma_cross"
    NORTH_BOLL = "north_boll"
    VOLUME_EMOTION = "volume_emotion"
    PRICE_FILTER = "price_filter"
    DRAWDOWN_TIER = "drawdown_tier"
    KALMAN_TREND = "kalman_trend"
    BIAS_REVERSION = "bias_reversion"


# ---------------------------------------------------------------------------
# ParamSpace: 参数搜索空间
# ---------------------------------------------------------------------------
@dataclass
class ParamSpace:
    """
    参数搜索空间定义

    用于自动优化 (网格搜索、贝叶斯优化等)

    Attributes:
        param_name: 参数名称
        param_type: 参数类型 (int, float, str, bool, list)
        low: 下界 (数值类型)
        high: 上界 (数值类型)
        step: 步长 (数值类型)
        choices: 离散候选值 (用于枚举类型)
        default: 默认值
        log_scale: 是否对数尺度 (仅数值类型)
        description: 参数说明
    """

    param_name: str
    param_type: str = "float"
    low: Optional[float] = None
    high: Optional[float] = None
    step: Optional[float] = None
    choices: Optional[List[Any]] = None
    default: Optional[Any] = None
    log_scale: bool = False
    description: str = ""

    def __post_init__(self):
        """初始化后处理: 类型校验"""
        if self.param_type not in (
            "int",
            "float",
            "str",
            "bool",
            "list",
            "categorical",
        ):
            raise ValueError(f"不支持的参数类型: {self.param_type}")

        if self.param_type in ("int", "float") and self.choices is None:
            if self.low is None or self.high is None:
                raise ValueError(
                    f"参数 {self.param_name}: 数值类型必须指定 low 和 high"
                )
            if self.low > self.high:
                raise ValueError(
                    f"参数 {self.param_name}: low ({self.low}) 不能大于 high ({self.high})"
                )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ParamSpace":
        """从字典创建"""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def sample(self, rng: Optional[np.random.RandomState] = None) -> Any:
        """
        从搜索空间中随机采样

        Args:
            rng: 随机数生成器

        Returns:
            采样值
        """
        import random

        if rng is None:
            rng = np.random.RandomState()

        if self.choices is not None:
            return random.choice(self.choices)

        if self.param_type == "bool":
            return bool(rng.randint(0, 2))

        if self.param_type in ("int", "float"):
            if self.log_scale:
                log_low = np.log(self.low)
                log_high = np.log(self.high)
                val = np.exp(rng.uniform(log_low, log_high))
            else:
                val = rng.uniform(self.low, self.high)

            if self.param_type == "int":
                val = int(round(val))
                if self.step is not None:
                    val = int(round(val / self.step) * self.step)
                return max(int(self.low), min(int(self.high), val))

            if self.step is not None:
                val = round(val / self.step) * self.step
            return round(val, 6)

        if self.param_type == "str":
            return str(self.default) if self.default is not None else ""

        return self.default

    def grid_values(self) -> List[Any]:
        """
        生成网格搜索值列表

        Returns:
            所有候选值列表
        """
        if self.choices is not None:
            return list(self.choices)

        if self.param_type == "bool":
            return [False, True]

        if self.param_type in ("int", "float"):
            if self.step is not None and self.step > 0:
                values = []
                current = self.low
                while current <= self.high + 1e-9:
                    values.append(
                        round(current, 6)
                        if self.param_type == "float"
                        else int(current)
                    )
                    current += self.step
                return values
            else:
                # 默认生成 10 个等分点
                if self.param_type == "int":
                    return [int(x) for x in np.linspace(self.low, self.high, 10)]
                else:
                    return [round(x, 4) for x in np.linspace(self.low, self.high, 10)]

        return [self.default] if self.default is not None else []

    def __repr__(self) -> str:
        if self.choices:
            return f"ParamSpace({self.param_name}, choices={self.choices}, default={self.default})"
        if self.param_type in ("int", "float"):
            return f"ParamSpace({self.param_name}, {self.param_type}, [{self.low}, {self.high}], step={self.step})"
        return f"ParamSpace({self.param_name}, default={self.default})"


# ---------------------------------------------------------------------------
# StrategyMetadata: 策略元数据
# ---------------------------------------------------------------------------
@dataclass
class StrategyMetadata:
    """
    策略元数据

    Attributes:
        name: 策略唯一标识名称
        display_name: 策略显示名称
        category: 策略分类
        risk_level: 风险等级
        min_capital: 最低资金要求 (元)
        expected_annual_return: 预期年化收益率 (小数，如 0.15 表示 15%)
        max_drawdown_tolerance: 最大回撤容忍度 (小数，如 0.20 表示 20%)
        description: 策略描述
        version: 策略版本 (语义化版本: major.minor.patch)
        author: 策略作者
        create_date: 创建日期
        update_date: 更新日期
        tags: 策略标签
        required_factors: 所需因子列表
        compatible_categories: 可组合的其他策略分类
    """

    name: str
    display_name: str = ""
    category: StrategyCategory = StrategyCategory.ETF_ROTATION
    risk_level: RiskLevel = RiskLevel.MEDIUM
    min_capital: float = 100000.0
    expected_annual_return: float = 0.10
    max_drawdown_tolerance: float = 0.20
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    create_date: str = ""
    update_date: str = ""
    tags: List[str] = field(default_factory=list)
    required_factors: List[str] = field(default_factory=list)
    compatible_categories: List[str] = field(default_factory=list)

    def __post_init__(self):
        """初始化后处理"""
        if not self.display_name:
            self.display_name = self.name
        if not self.create_date:
            self.create_date = datetime.date.today().isoformat()
        if not self.update_date:
            self.update_date = self.create_date

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        d = asdict(self)
        d["category"] = self.category.value
        d["risk_level"] = self.risk_level.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyMetadata":
        """从字典创建"""
        d = d.copy()
        if "category" in d and isinstance(d["category"], str):
            d["category"] = StrategyCategory(d["category"])
        if "risk_level" in d and isinstance(d["risk_level"], str):
            d["risk_level"] = RiskLevel(d["risk_level"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def bump_version(self, part: str = "patch") -> str:
        """
        递增版本号

        Args:
            part: 递增部分 (major, minor, patch)

        Returns:
            新版本号
        """
        parts = self.version.split(".")
        if len(parts) != 3:
            parts = ["1", "0", "0"]

        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        if part == "major":
            major += 1
            minor = 0
            patch = 0
        elif part == "minor":
            minor += 1
            patch = 0
        else:
            patch += 1

        self.version = f"{major}.{minor}.{patch}"
        self.update_date = datetime.date.today().isoformat()
        return self.version

    def __repr__(self) -> str:
        return (
            f"StrategyMetadata(name='{self.name}', category={self.category.value}, "
            f"risk={self.risk_level.value}, return={self.expected_annual_return:.1%})"
        )


# ---------------------------------------------------------------------------
# StrategyConfig: 策略配置
# ---------------------------------------------------------------------------
@dataclass
class StrategyConfig:
    """
    策略配置

    Attributes:
        metadata: 策略元数据
        scoring_mode: 评分模式
        allocation_mode: 配置模式
        timing_method: 择时方法
        params: 策略参数字典
        etf_pool: ETF 池 (标的代码列表)
        rebalance_period: 调仓周期 (交易日)
        param_spaces: 参数搜索空间定义
        risk_params: 风控参数
        benchmark: 基准指数
        max_positions: 最大持仓数
        min_position_weight: 最小仓位权重
        cash_reserve: 现金保留比例
    """

    metadata: StrategyMetadata
    scoring_mode: ScoringMode = ScoringMode.MOMENTUM
    allocation_mode: AllocationMode = AllocationMode.TOP_N
    timing_method: TimingMethod = TimingMethod.NONE
    params: Dict[str, Any] = field(default_factory=dict)
    etf_pool: List[str] = field(default_factory=list)
    rebalance_period: int = 5
    param_spaces: Dict[str, ParamSpace] = field(default_factory=dict)
    risk_params: Dict[str, Any] = field(default_factory=dict)
    benchmark: str = "000300"
    max_positions: int = 5
    min_position_weight: float = 0.05
    cash_reserve: float = 0.0
    max_single_weight: float = 0.30

    def __post_init__(self):
        """初始化后处理: 确保 risk_params 有默认值"""
        defaults = {
            "max_drawdown_stop": 0.15,
            "single_stop_loss": 0.08,
            "volatility_threshold": 0.03,
            "momentum_change_threshold": 0.05,
        }
        for k, v in defaults.items():
            self.risk_params.setdefault(k, v)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典 (可序列化)"""
        d = {
            "metadata": self.metadata.to_dict(),
            "scoring_mode": self.scoring_mode.value,
            "allocation_mode": self.allocation_mode.value,
            "timing_method": self.timing_method.value,
            "params": self.params,
            "etf_pool": self.etf_pool,
            "rebalance_period": self.rebalance_period,
            "param_spaces": {k: v.to_dict() for k, v in self.param_spaces.items()},
            "risk_params": self.risk_params,
            "benchmark": self.benchmark,
            "max_positions": self.max_positions,
            "min_position_weight": self.min_position_weight,
            "cash_reserve": self.cash_reserve,
            "max_single_weight": self.max_single_weight,
        }
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyConfig":
        """从字典创建"""
        d = d.copy()
        d["metadata"] = StrategyMetadata.from_dict(d.get("metadata", {}))
        if "scoring_mode" in d and isinstance(d["scoring_mode"], str):
            d["scoring_mode"] = ScoringMode(d["scoring_mode"])
        if "allocation_mode" in d and isinstance(d["allocation_mode"], str):
            d["allocation_mode"] = AllocationMode(d["allocation_mode"])
        if "timing_method" in d and isinstance(d["timing_method"], str):
            d["timing_method"] = TimingMethod(d["timing_method"])
        if "param_spaces" in d:
            d["param_spaces"] = {
                k: ParamSpace.from_dict(v) for k, v in d["param_spaces"].items()
            }
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_json(self, indent: int = 2) -> str:
        """导出为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "StrategyConfig":
        """从 JSON 字符串导入"""
        return cls.from_dict(json.loads(json_str))

    def save(self, path: str) -> None:
        """保存到文件"""
        os.makedirs(
            os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path: str) -> "StrategyConfig":
        """从文件加载"""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())

    def get_param_value(self, key: str, default: Any = None) -> Any:
        """获取参数值"""
        return self.params.get(key, default)

    def set_param(self, key: str, value: Any) -> None:
        """设置参数值"""
        self.params[key] = value

    def clone(self, name_suffix: str = "_clone") -> "StrategyConfig":
        """
        克隆策略配置

        Args:
            name_suffix: 名称后缀

        Returns:
            克隆的配置
        """
        new_config = deepcopy(self)
        new_config.metadata.name = f"{self.metadata.name}{name_suffix}"
        new_config.metadata.display_name = f"{self.metadata.display_name}{name_suffix}"
        new_config.metadata.bump_version("patch")
        return new_config

    def __repr__(self) -> str:
        return (
            f"StrategyConfig(name='{self.metadata.name}', "
            f"scoring={self.scoring_mode.value}, alloc={self.allocation_mode.value}, "
            f"timing={self.timing_method.value})"
        )


# ===================================================================
# 预设策略定义
# ===================================================================

# 常用 ETF 池
ETF_POOL_BROAD = [
    "510300",  # 沪深300ETF
    "510500",  # 中证500ETF
    "159919",  # 创业板ETF
    "510050",  # 上证50ETF
    "512100",  # 中证1000ETF
    "518880",  # 黄金ETF
    "513100",  # 纳指ETF
    "513500",  # 标普500ETF
    "513030",  # 德国30ETF
    "159915",  # 创业板50ETF
    "512480",  # 半导体ETF
    "512660",  # 军工ETF
    "512800",  # 银行ETF
    "515050",  # 5GETF
    "512690",  # 酒ETF
]

ETF_POOL_CORE = [
    "510300",  # 沪深300ETF
    "510500",  # 中证500ETF
    "159919",  # 创业板ETF
    "510050",  # 上证50ETF
    "512100",  # 中证1000ETF
    "518880",  # 黄金ETF
]

ETF_POOL_GLOBAL = [
    "510300",  # 沪深300ETF
    "510500",  # 中证500ETF
    "159919",  # 创业板ETF
    "513100",  # 纳指ETF
    "513500",  # 标普500ETF
    "513030",  # 德国30ETF
    "518880",  # 黄金ETF
]

ETF_POOL_SECTOR = [
    "512480",  # 半导体ETF
    "512660",  # 军工ETF
    "512800",  # 银行ETF
    "515050",  # 5GETF
    "512690",  # 酒ETF
    "512010",  # 医药ETF
    "512880",  # 证券ETF
    "512980",  # 传媒ETF
    "512200",  # 房地产ETF
    "512400",  # 有色金属ETF
]

ETF_POOL_T0 = [
    "510300",  # 沪深300ETF (支持T+0的跨境/商品ETF)
    "513100",  # 纳指ETF
    "513500",  # 标普500ETF
    "513030",  # 德国30ETF
    "518880",  # 黄金ETF
    "513660",  # 恒生ETF
]

STOCK_BOND_POOL = [
    "510300",  # 沪深300ETF (股)
    "511010",  # 国债ETF (债)
    "518880",  # 黄金ETF (商品)
]


def _build_preset_strategies() -> Dict[str, StrategyConfig]:
    """构建所有预设策略配置"""

    presets = {}

    # ===================================================================
    # 1. etf_momentum_rsrs - 动量+RSRS (经典)
    # ===================================================================
    presets["etf_momentum_rsrs"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="etf_momentum_rsrs",
            display_name="ETF动量+RSRS择时",
            category=StrategyCategory.ETF_ROTATION,
            risk_level=RiskLevel.MEDIUM,
            min_capital=100000,
            expected_annual_return=0.18,
            max_drawdown_tolerance=0.15,
            description="经典动量轮动 + RSRS择时过滤。多周期动量评分选出强势ETF，RSRS指标判断市场趋势，避免在下跌趋势中持有仓位。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["动量", "RSRS", "ETF轮动", "经典"],
            required_factors=["momentum", "rsrs"],
            compatible_categories=["etf_rotation", "hybrid"],
        ),
        scoring_mode=ScoringMode.MOMENTUM,
        allocation_mode=AllocationMode.TOP_N,
        timing_method=TimingMethod.RSRS,
        params={
            "momentum_periods": [5, 10, 20, 60],
            "momentum_weights": [0.1, 0.2, 0.3, 0.4],
            "rsrs_N": 18,
            "rsrs_M": 600,
            "rsrs_buy_threshold": 0.7,
            "rsrs_sell_threshold": -0.7,
            "top_n": 3,
        },
        etf_pool=ETF_POOL_BROAD,
        rebalance_period=5,
        param_spaces={
            "momentum_periods": ParamSpace(
                param_name="momentum_periods",
                param_type="list",
                choices=[[5, 10, 20], [5, 10, 20, 60], [10, 20, 60], [5, 20, 60, 120]],
                default=[5, 10, 20, 60],
                description="动量计算周期列表",
            ),
            "rsrs_N": ParamSpace(
                param_name="rsrs_N",
                param_type="int",
                low=10,
                high=30,
                step=2,
                default=18,
                description="RSRS回归窗口",
            ),
            "rsrs_M": ParamSpace(
                param_name="rsrs_M",
                param_type="int",
                low=300,
                high=800,
                step=50,
                default=600,
                description="RSRS Z-Score参考窗口",
            ),
            "top_n": ParamSpace(
                param_name="top_n",
                param_type="int",
                low=1,
                high=5,
                step=1,
                default=3,
                description="持仓ETF数量",
            ),
        },
        max_positions=3,
    )

    # ===================================================================
    # 2. etf_core_asset - 核心资产 (对数回归)
    # ===================================================================
    presets["etf_core_asset"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="etf_core_asset",
            display_name="核心资产对数回归",
            category=StrategyCategory.ETF_ROTATION,
            risk_level=RiskLevel.MEDIUM,
            min_capital=100000,
            expected_annual_return=0.15,
            max_drawdown_tolerance=0.18,
            description="基于对数价格回归斜率的核心资产选择。对数变换使收益率线性化，回归斜率反映趋势强度。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["对数回归", "核心资产", "趋势"],
            required_factors=["log_regression"],
            compatible_categories=["etf_rotation"],
        ),
        scoring_mode=ScoringMode.LOG_REGRESSION,
        allocation_mode=AllocationMode.MOMENTUM_WEIGHT,
        timing_method=TimingMethod.MA_CROSS,
        params={
            "regression_window": 20,
            "ma_fast": 5,
            "ma_slow": 20,
            "top_n": 4,
            "annualize": True,
        },
        etf_pool=ETF_POOL_CORE,
        rebalance_period=5,
        param_spaces={
            "regression_window": ParamSpace(
                param_name="regression_window",
                param_type="int",
                low=10,
                high=60,
                step=5,
                default=20,
                description="回归窗口",
            ),
            "ma_fast": ParamSpace(
                param_name="ma_fast",
                param_type="int",
                low=3,
                high=10,
                step=1,
                default=5,
                description="均线快线周期",
            ),
            "ma_slow": ParamSpace(
                param_name="ma_slow",
                param_type="int",
                low=10,
                high=60,
                step=5,
                default=20,
                description="均线慢线周期",
            ),
        },
        max_positions=4,
    )

    # ===================================================================
    # 3. etf_bias_momentum - 乖离率动量
    # ===================================================================
    presets["etf_bias_momentum"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="etf_bias_momentum",
            display_name="乖离率动量轮动",
            category=StrategyCategory.ETF_ROTATION,
            risk_level=RiskLevel.MEDIUM_HIGH,
            min_capital=100000,
            expected_annual_return=0.20,
            max_drawdown_tolerance=0.20,
            description="基于价格偏离均线程度的动量策略。乖离率反映超买超卖状态，结合动量趋势选择标的。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["乖离率", "均线", "动量"],
            required_factors=["bias", "momentum"],
            compatible_categories=["etf_rotation", "chase_momentum"],
        ),
        scoring_mode=ScoringMode.BIAS,
        allocation_mode=AllocationMode.TOP_N,
        timing_method=TimingMethod.BIAS_REVERSION,
        params={
            "ma_periods": [5, 10, 20],
            "bias_weight": 0.6,
            "momentum_weight": 0.4,
            "momentum_period": 20,
            "top_n": 3,
            "bias_reversion_threshold": 0.05,
        },
        etf_pool=ETF_POOL_BROAD,
        rebalance_period=3,
        param_spaces={
            "ma_periods": ParamSpace(
                param_name="ma_periods",
                param_type="list",
                choices=[[5, 10], [5, 10, 20], [10, 20, 60], [5, 20]],
                default=[5, 10, 20],
                description="均线周期列表",
            ),
            "bias_weight": ParamSpace(
                param_name="bias_weight",
                param_type="float",
                low=0.3,
                high=0.8,
                step=0.1,
                default=0.6,
                description="乖离率权重",
            ),
            "top_n": ParamSpace(
                param_name="top_n",
                param_type="int",
                low=1,
                high=5,
                step=1,
                default=3,
                description="持仓数量",
            ),
        },
        max_positions=3,
    )

    # ===================================================================
    # 4. etf_kalman - 卡尔曼滤波
    # ===================================================================
    presets["etf_kalman"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="etf_kalman",
            display_name="卡尔曼滤波趋势跟踪",
            category=StrategyCategory.ETF_ROTATION,
            risk_level=RiskLevel.MEDIUM,
            min_capital=100000,
            expected_annual_return=0.16,
            max_drawdown_tolerance=0.15,
            description="使用卡尔曼滤波估计资产趋势状态。卡尔曼滤波能自适应市场波动，平滑噪声并捕捉真实趋势。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["卡尔曼滤波", "状态估计", "趋势跟踪"],
            required_factors=["kalman"],
            compatible_categories=["etf_rotation"],
        ),
        scoring_mode=ScoringMode.KALMAN,
        allocation_mode=AllocationMode.MOMENTUM_WEIGHT,
        timing_method=TimingMethod.KALMAN_TREND,
        params={
            "kalman_R": 1e-2,
            "kalman_Q": [[1e-6, 0], [0, 1e-6]],
            "kalman_P_init": [[1e4, 0], [0, 1e4]],
            "top_n": 3,
            "min_trend_strength": 0.001,
        },
        etf_pool=ETF_POOL_CORE,
        rebalance_period=5,
        param_spaces={
            "kalman_R": ParamSpace(
                param_name="kalman_R",
                param_type="float",
                low=1e-4,
                high=1e-1,
                default=1e-2,
                log_scale=True,
                description="观测噪声方差",
            ),
            "kalman_Q_scale": ParamSpace(
                param_name="kalman_Q_scale",
                param_type="float",
                low=1e-8,
                high=1e-4,
                default=1e-6,
                log_scale=True,
                description="过程噪声协方差缩放",
            ),
            "top_n": ParamSpace(
                param_name="top_n",
                param_type="int",
                low=1,
                high=5,
                step=1,
                default=3,
                description="持仓数量",
            ),
        },
        max_positions=3,
    )

    # ===================================================================
    # 5. multi_factor_epo - 多因子+EPO
    # ===================================================================
    presets["multi_factor_epo"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="multi_factor_epo",
            display_name="多因子EPO优化",
            category=StrategyCategory.ETF_ROTATION,
            risk_level=RiskLevel.MEDIUM,
            min_capital=200000,
            expected_annual_return=0.20,
            max_drawdown_tolerance=0.15,
            description="多因子评分 + EPO (等权重动量组合) 优化。综合动量、波动率、相关性等多因子，使用EPO方法优化权重分配。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["多因子", "EPO", "组合优化", "协方差"],
            required_factors=["momentum", "volatility", "correlation"],
            compatible_categories=["etf_rotation", "hybrid"],
        ),
        scoring_mode=ScoringMode.MULTI_FACTOR,
        allocation_mode=AllocationMode.EPO,
        timing_method=TimingMethod.RSRS,
        params={
            "momentum_periods": [20, 60],
            "momentum_weight": 0.4,
            "volatility_weight": 0.3,
            "correlation_weight": 0.3,
            "risk_aversion": 1.0,
            "cov_window": 60,
            "rsrs_N": 18,
            "rsrs_M": 600,
        },
        etf_pool=ETF_POOL_BROAD,
        rebalance_period=5,
        param_spaces={
            "risk_aversion": ParamSpace(
                param_name="risk_aversion",
                param_type="float",
                low=0.5,
                high=5.0,
                step=0.5,
                default=1.0,
                description="风险厌恶系数",
            ),
            "cov_window": ParamSpace(
                param_name="cov_window",
                param_type="int",
                low=30,
                high=120,
                step=10,
                default=60,
                description="协方差估计窗口",
            ),
            "momentum_weight": ParamSpace(
                param_name="momentum_weight",
                param_type="float",
                low=0.2,
                high=0.6,
                step=0.1,
                default=0.4,
                description="动量因子权重",
            ),
        },
        max_positions=5,
    )

    # ===================================================================
    # 6. sector_heat - 板块热度
    # ===================================================================
    presets["sector_heat"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="sector_heat",
            display_name="板块热度轮动",
            category=StrategyCategory.SECTOR_ROTATION,
            risk_level=RiskLevel.MEDIUM_HIGH,
            min_capital=150000,
            expected_annual_return=0.22,
            max_drawdown_tolerance=0.22,
            description="基于行业板块热度的轮动策略。综合板块动量、资金流入、相对强度等指标，捕捉板块轮动机会。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["板块轮动", "行业", "热度", "资金流"],
            required_factors=["momentum", "volume_emotion"],
            compatible_categories=["sector_rotation", "chase_momentum"],
        ),
        scoring_mode=ScoringMode.SECTOR_HEAT,
        allocation_mode=AllocationMode.TOP_N,
        timing_method=TimingMethod.VOLUME_EMOTION,
        params={
            "momentum_period": 20,
            "volume_ratio_window": 20,
            "heat_decay": 0.9,
            "top_n": 3,
            "min_heat_score": 0.3,
        },
        etf_pool=ETF_POOL_SECTOR,
        rebalance_period=5,
        param_spaces={
            "momentum_period": ParamSpace(
                param_name="momentum_period",
                param_type="int",
                low=10,
                high=60,
                step=5,
                default=20,
                description="动量周期",
            ),
            "top_n": ParamSpace(
                param_name="top_n",
                param_type="int",
                low=1,
                high=5,
                step=1,
                default=3,
                description="持仓板块数",
            ),
            "min_heat_score": ParamSpace(
                param_name="min_heat_score",
                param_type="float",
                low=0.1,
                high=0.5,
                step=0.05,
                default=0.3,
                description="最低热度阈值",
            ),
        },
        max_positions=3,
    )

    # ===================================================================
    # 7. min_correlation - 最小相关性
    # ===================================================================
    presets["min_correlation"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="min_correlation",
            display_name="最小相关性组合",
            category=StrategyCategory.ETF_ROTATION,
            risk_level=RiskLevel.LOW,
            min_capital=200000,
            expected_annual_return=0.12,
            max_drawdown_tolerance=0.12,
            description="选择与其他资产相关性最低的ETF构建组合。低相关性组合能有效分散风险，降低整体波动。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["低相关性", "分散风险", "组合优化"],
            required_factors=["correlation"],
            compatible_categories=["etf_rotation", "hybrid"],
        ),
        scoring_mode=ScoringMode.CORRELATION,
        allocation_mode=AllocationMode.MIN_CORR,
        timing_method=TimingMethod.NONE,
        params={
            "corr_window": 60,
            "n_select": 4,
            "min_corr_threshold": 0.5,
        },
        etf_pool=ETF_POOL_GLOBAL,
        rebalance_period=10,
        param_spaces={
            "corr_window": ParamSpace(
                param_name="corr_window",
                param_type="int",
                low=30,
                high=120,
                step=10,
                default=60,
                description="相关性计算窗口",
            ),
            "n_select": ParamSpace(
                param_name="n_select",
                param_type="int",
                low=2,
                high=6,
                step=1,
                default=4,
                description="选择资产数量",
            ),
        },
        max_positions=4,
    )

    # ===================================================================
    # 8. epo_optimized - EPO优化
    # ===================================================================
    presets["epo_optimized"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="epo_optimized",
            display_name="EPO优化组合",
            category=StrategyCategory.ETF_ROTATION,
            risk_level=RiskLevel.MEDIUM,
            min_capital=200000,
            expected_annual_return=0.18,
            max_drawdown_tolerance=0.15,
            description="改进的EPO (等权重动量组合) 策略。使用动量得分替代传统均值，结合协方差矩阵优化权重分配。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["EPO", "组合优化", "动量得分", "协方差"],
            required_factors=["momentum", "covariance"],
            compatible_categories=["etf_rotation"],
        ),
        scoring_mode=ScoringMode.EPO,
        allocation_mode=AllocationMode.EPO,
        timing_method=TimingMethod.DRAWDOWN_TIER,
        params={
            "momentum_periods": [20, 60],
            "risk_aversion": 2.0,
            "cov_window": 60,
            "min_weight": 0.05,
            "max_weight": 0.40,
            "drawdown_windows": [20, 60, 250],
        },
        etf_pool=ETF_POOL_BROAD,
        rebalance_period=5,
        param_spaces={
            "risk_aversion": ParamSpace(
                param_name="risk_aversion",
                param_type="float",
                low=0.5,
                high=5.0,
                step=0.5,
                default=2.0,
                description="风险厌恶系数",
            ),
            "cov_window": ParamSpace(
                param_name="cov_window",
                param_type="int",
                low=30,
                high=120,
                step=10,
                default=60,
                description="协方差窗口",
            ),
            "max_weight": ParamSpace(
                param_name="max_weight",
                param_type="float",
                low=0.2,
                high=0.5,
                step=0.05,
                default=0.40,
                description="单资产最大权重",
            ),
        },
        max_positions=5,
        max_single_weight=0.40,
    )

    # ===================================================================
    # 9. stock_bond_balance - 股债平衡
    # ===================================================================
    presets["stock_bond_balance"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="stock_bond_balance",
            display_name="股债平衡配置",
            category=StrategyCategory.HYBRID,
            risk_level=RiskLevel.LOW,
            min_capital=100000,
            expected_annual_return=0.10,
            max_drawdown_tolerance=0.10,
            description="基于动量和波动率的股债动态平衡策略。根据股票和债券的相对吸引力自动调整配置比例。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["股债平衡", "资产配置", "风险平价", "稳健"],
            required_factors=["momentum", "volatility"],
            compatible_categories=["hybrid"],
        ),
        scoring_mode=ScoringMode.MULTI_FACTOR,
        allocation_mode=AllocationMode.STOCK_BOND,
        timing_method=TimingMethod.PRICE_FILTER,
        params={
            "momentum_period": 20,
            "vol_window": 60,
            "risk_budget": 0.5,
            "rebalance_threshold": 0.05,
            "price_filter_lookback": 250,
        },
        etf_pool=STOCK_BOND_POOL,
        rebalance_period=20,
        param_spaces={
            "risk_budget": ParamSpace(
                param_name="risk_budget",
                param_type="float",
                low=0.3,
                high=0.7,
                step=0.05,
                default=0.5,
                description="股票风险预算",
            ),
            "momentum_period": ParamSpace(
                param_name="momentum_period",
                param_type="int",
                low=10,
                high=60,
                step=5,
                default=20,
                description="动量周期",
            ),
            "vol_window": ParamSpace(
                param_name="vol_window",
                param_type="int",
                low=30,
                high=120,
                step=10,
                default=60,
                description="波动率窗口",
            ),
        },
        max_positions=3,
    )

    # ===================================================================
    # 10. grid_trading - 网格交易
    # ===================================================================
    presets["grid_trading"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="grid_trading",
            display_name="网格交易策略",
            category=StrategyCategory.HYBRID,
            risk_level=RiskLevel.MEDIUM,
            min_capital=200000,
            expected_annual_return=0.15,
            max_drawdown_tolerance=0.15,
            description="基于动量分档的网格交易策略。将资产按动量分档，不同档位配置不同权重，高动量高权重。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["网格", "分档", "动量加权"],
            required_factors=["momentum"],
            compatible_categories=["hybrid", "etf_rotation"],
        ),
        scoring_mode=ScoringMode.MOMENTUM,
        allocation_mode=AllocationMode.GRID,
        timing_method=TimingMethod.NONE,
        params={
            "grid_levels": 5,
            "rebalance_period": 20,
            "momentum_window": 20,
            "momentum_periods": [20],
        },
        etf_pool=ETF_POOL_BROAD,
        rebalance_period=20,
        param_spaces={
            "grid_levels": ParamSpace(
                param_name="grid_levels",
                param_type="int",
                low=3,
                high=10,
                step=1,
                default=5,
                description="网格档位数",
            ),
            "rebalance_period": ParamSpace(
                param_name="rebalance_period",
                param_type="int",
                low=5,
                high=40,
                step=5,
                default=20,
                description="调仓周期",
            ),
            "momentum_window": ParamSpace(
                param_name="momentum_window",
                param_type="int",
                low=10,
                high=60,
                step=5,
                default=20,
                description="动量窗口",
            ),
        },
        max_positions=10,
    )

    # ===================================================================
    # 11. t0_momentum - T+0动量
    # ===================================================================
    presets["t0_momentum"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="t0_momentum",
            display_name="T+0动量交易",
            category=StrategyCategory.T0_TRADING,
            risk_level=RiskLevel.HIGH,
            min_capital=300000,
            expected_annual_return=0.25,
            max_drawdown_tolerance=0.25,
            description="针对支持T+0交易的ETF (跨境/商品) 的动量策略。利用日内波动进行高频轮动，捕捉短期动量机会。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["T+0", "高频", "跨境ETF", "商品ETF"],
            required_factors=["momentum", "intraday"],
            compatible_categories=["t0_trading"],
        ),
        scoring_mode=ScoringMode.MOMENTUM,
        allocation_mode=AllocationMode.TOP_N,
        timing_method=TimingMethod.VOLUME_EMOTION,
        params={
            "momentum_periods": [1, 3, 5, 10],
            "momentum_weights": [0.4, 0.3, 0.2, 0.1],
            "top_n": 2,
            "intraday_threshold": 0.02,
            "volume_spike_threshold": 3.0,
        },
        etf_pool=ETF_POOL_T0,
        rebalance_period=1,
        param_spaces={
            "momentum_periods": ParamSpace(
                param_name="momentum_periods",
                param_type="list",
                choices=[[1, 3, 5], [1, 3, 5, 10], [3, 5, 10], [1, 5, 10]],
                default=[1, 3, 5, 10],
                description="短期动量周期",
            ),
            "top_n": ParamSpace(
                param_name="top_n",
                param_type="int",
                low=1,
                high=3,
                step=1,
                default=2,
                description="持仓数量",
            ),
            "intraday_threshold": ParamSpace(
                param_name="intraday_threshold",
                param_type="float",
                low=0.01,
                high=0.05,
                step=0.005,
                default=0.02,
                description="日内波幅阈值",
            ),
        },
        max_positions=2,
    )

    # ===================================================================
    # 12. chase_momentum - 追涨
    # ===================================================================
    presets["chase_momentum"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="chase_momentum",
            display_name="追涨动量策略",
            category=StrategyCategory.CHASE_MOMENTUM,
            risk_level=RiskLevel.HIGH,
            min_capital=100000,
            expected_annual_return=0.25,
            max_drawdown_tolerance=0.30,
            description="强势追涨策略。选择近期涨幅最大、动量最强的标的，配合严格止损控制风险。适合风险偏好高的投资者。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["追涨", "强势", "高收益", "高风险"],
            required_factors=["momentum", "stop_loss"],
            compatible_categories=["chase_momentum"],
        ),
        scoring_mode=ScoringMode.MOMENTUM,
        allocation_mode=AllocationMode.TOP_N,
        timing_method=TimingMethod.DRAWDOWN_TIER,
        params={
            "momentum_periods": [3, 5, 10],
            "momentum_weights": [0.5, 0.3, 0.2],
            "top_n": 2,
            "stop_loss_pct": 0.05,
            "trailing_stop_pct": 0.03,
            "min_momentum_score": 0.02,
        },
        etf_pool=ETF_POOL_SECTOR,
        rebalance_period=3,
        param_spaces={
            "momentum_periods": ParamSpace(
                param_name="momentum_periods",
                param_type="list",
                choices=[[3, 5], [3, 5, 10], [5, 10], [1, 3, 5]],
                default=[3, 5, 10],
                description="短期动量周期",
            ),
            "stop_loss_pct": ParamSpace(
                param_name="stop_loss_pct",
                param_type="float",
                low=0.03,
                high=0.10,
                step=0.01,
                default=0.05,
                description="止损比例",
            ),
            "top_n": ParamSpace(
                param_name="top_n",
                param_type="int",
                low=1,
                high=3,
                step=1,
                default=2,
                description="持仓数量",
            ),
        },
        max_positions=2,
        risk_params={
            "max_drawdown_stop": 0.10,
            "single_stop_loss": 0.05,
            "volatility_threshold": 0.04,
            "momentum_change_threshold": 0.03,
        },
    )

    # ===================================================================
    # 13. ir_trend - IR趋势度
    # ===================================================================
    presets["ir_trend"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="ir_trend",
            display_name="IR趋势度策略",
            category=StrategyCategory.ETF_ROTATION,
            risk_level=RiskLevel.MEDIUM,
            min_capital=100000,
            expected_annual_return=0.16,
            max_drawdown_tolerance=0.15,
            description="基于信息比率 (IR) 的趋势度策略。IR = 超额收益 / 跟踪误差，衡量风险调整后的趋势强度。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["信息比率", "风险调整", "趋势度"],
            required_factors=["momentum", "volatility"],
            compatible_categories=["etf_rotation"],
        ),
        scoring_mode=ScoringMode.IR_TREND,
        allocation_mode=AllocationMode.RISK_PARITY,
        timing_method=TimingMethod.MA_CROSS,
        params={
            "return_window": 20,
            "benchmark": "000300",
            "ir_annualize": True,
            "top_n": 3,
            "min_ir": 0.5,
            "ma_fast": 5,
            "ma_slow": 20,
        },
        etf_pool=ETF_POOL_BROAD,
        rebalance_period=5,
        param_spaces={
            "return_window": ParamSpace(
                param_name="return_window",
                param_type="int",
                low=10,
                high=60,
                step=5,
                default=20,
                description="收益计算窗口",
            ),
            "min_ir": ParamSpace(
                param_name="min_ir",
                param_type="float",
                low=0.0,
                high=2.0,
                step=0.1,
                default=0.5,
                description="最低IR阈值",
            ),
            "top_n": ParamSpace(
                param_name="top_n",
                param_type="int",
                low=1,
                high=5,
                step=1,
                default=3,
                description="持仓数量",
            ),
        },
        max_positions=3,
    )

    # ===================================================================
    # 14. north_money_timing - 北向择时
    # ===================================================================
    presets["north_money_timing"] = StrategyConfig(
        metadata=StrategyMetadata(
            name="north_money_timing",
            display_name="北向资金择时",
            category=StrategyCategory.HYBRID,
            risk_level=RiskLevel.MEDIUM,
            min_capital=100000,
            expected_annual_return=0.15,
            max_drawdown_tolerance=0.15,
            description="基于北向资金流向的择时策略。北向资金被视为聪明钱，其净流入/流出是重要的市场信号。结合动量轮动使用。",
            version="1.0.0",
            author="聚宽策略精华",
            tags=["北向资金", "择时", "资金流", "聪明钱"],
            required_factors=["north_flow", "momentum"],
            compatible_categories=["hybrid", "etf_rotation"],
        ),
        scoring_mode=ScoringMode.NORTH_FLOW,
        allocation_mode=AllocationMode.TOP_N,
        timing_method=TimingMethod.NORTH_BOLL,
        params={
            "north_window": 90,
            "north_stdev_n": 2.0,
            "north_flow_ma": 5,
            "momentum_periods": [10, 20, 60],
            "momentum_weights": [0.2, 0.3, 0.5],
            "top_n": 3,
            "north_signal_weight": 0.3,
            "momentum_signal_weight": 0.7,
        },
        etf_pool=ETF_POOL_CORE,
        rebalance_period=5,
        param_spaces={
            "north_window": ParamSpace(
                param_name="north_window",
                param_type="int",
                low=30,
                high=180,
                step=10,
                default=90,
                description="北向资金布林带窗口",
            ),
            "north_stdev_n": ParamSpace(
                param_name="north_stdev_n",
                param_type="float",
                low=1.0,
                high=3.0,
                step=0.25,
                default=2.0,
                description="标准差倍数",
            ),
            "north_signal_weight": ParamSpace(
                param_name="north_signal_weight",
                param_type="float",
                low=0.1,
                high=0.5,
                step=0.05,
                default=0.3,
                description="北向信号权重",
            ),
            "top_n": ParamSpace(
                param_name="top_n",
                param_type="int",
                low=1,
                high=5,
                step=1,
                default=3,
                description="持仓数量",
            ),
        },
        max_positions=3,
    )

    return presets


# ===================================================================
# StrategyRegistry: 策略注册中心
# ===================================================================
class StrategyRegistry:
    """
    策略注册中心

    功能:
    - 注册自定义策略
    - 获取预设策略
    - 按分类/风险等级/标签搜索
    - 策略兼容性检查
    - 参数冲突检测
    - 策略版本管理
    - 导出/导入策略配置

    使用示例:
        registry = StrategyRegistry()
        config = registry.get("etf_momentum_rsrs")
        configs = registry.list_by_category(StrategyCategory.ETF_ROTATION)
        results = registry.search(risk_level=RiskLevel.LOW, min_return=0.10)
        registry.validate(config)
    """

    def __init__(self, auto_register_presets: bool = True):
        """
        初始化策略注册中心

        Args:
            auto_register_presets: 是否自动注册预设策略
        """
        self._strategies: Dict[str, StrategyConfig] = {}
        self._version_history: Dict[str, List[Dict[str, Any]]] = {}
        self._compatibility_rules: Dict[str, Set[str]] = {}
        self._param_conflict_rules: Dict[str, Set[str]] = {}

        if auto_register_presets:
            self._register_all_presets()

        self._setup_compatibility_rules()
        self._setup_param_conflict_rules()

    def _register_all_presets(self) -> None:
        """注册所有预设策略"""
        presets = _build_preset_strategies()
        for name, config in presets.items():
            self._strategies[name] = config
            self._record_version(name, config.metadata.version, "preset_registered")
        logger.info(f"已注册 {len(presets)} 个预设策略")

    def _setup_compatibility_rules(self) -> None:
        """设置策略兼容性规则"""
        self._compatibility_rules = {
            "etf_rotation": {"etf_rotation", "hybrid", "t0_trading"},
            "sector_rotation": {"sector_rotation", "chase_momentum", "hybrid"},
            "hybrid": {"etf_rotation", "sector_rotation", "hybrid", "t0_trading"},
            "t0_trading": {"t0_trading", "hybrid"},
            "chase_momentum": {"chase_momentum", "sector_rotation"},
        }

    def _setup_param_conflict_rules(self) -> None:
        """设置参数冲突规则"""
        # 同一策略中不能同时存在的参数组合
        self._param_conflict_rules = {
            "allocation_mode": {"top_n", "epo", "min_corr", "stock_bond", "grid"},
            "scoring_mode": {
                "momentum",
                "regression",
                "log_regression",
                "bias",
                "kalman",
                "multi_factor",
            },
        }

    # ===================================================================
    # 注册 & 获取
    # ===================================================================

    def register(self, config: StrategyConfig, overwrite: bool = False) -> bool:
        """
        注册策略配置

        Args:
            config: 策略配置
            overwrite: 是否覆盖已有策略

        Returns:
            是否注册成功
        """
        name = config.metadata.name

        if name in self._strategies and not overwrite:
            logger.warning(f"策略 '{name}' 已存在，使用 overwrite=True 覆盖")
            return False

        if name in self._strategies and overwrite:
            old_config = self._strategies[name]
            self._record_version(
                name,
                old_config.metadata.version,
                "overwritten",
                old_version=old_config.metadata.version,
                new_version=config.metadata.version,
            )

        self._strategies[name] = config
        self._record_version(name, config.metadata.version, "registered")
        logger.info(f"策略已注册: {name} (v{config.metadata.version})")
        return True

    def get(self, name: str) -> Optional[StrategyConfig]:
        """
        获取策略配置

        Args:
            name: 策略名称

        Returns:
            策略配置，不存在则返回 None
        """
        config = self._strategies.get(name)
        if config is not None:
            return deepcopy(config)
        logger.warning(f"策略 '{name}' 不存在")
        return None

    def remove(self, name: str) -> bool:
        """
        移除策略

        Args:
            name: 策略名称

        Returns:
            是否移除成功
        """
        if name in self._strategies:
            del self._strategies[name]
            self._record_version(name, "removed", "removed")
            logger.info(f"策略已移除: {name}")
            return True
        return False

    # ===================================================================
    # 列表 & 搜索
    # ===================================================================

    def list_all(self) -> List[str]:
        """
        列出所有策略名称

        Returns:
            策略名称列表
        """
        return sorted(self._strategies.keys())

    def list_configs(self) -> Dict[str, StrategyConfig]:
        """
        获取所有策略配置 (深拷贝)

        Returns:
            dict[name, StrategyConfig]
        """
        return {name: deepcopy(config) for name, config in self._strategies.items()}

    def list_by_category(self, category: StrategyCategory) -> List[str]:
        """
        按分类列出策略

        Args:
            category: 策略分类

        Returns:
            策略名称列表
        """
        return sorted(
            [
                name
                for name, cfg in self._strategies.items()
                if cfg.metadata.category == category
            ]
        )

    def list_by_risk_level(self, risk_level: RiskLevel) -> List[str]:
        """
        按风险等级列出策略

        Args:
            risk_level: 风险等级

        Returns:
            策略名称列表
        """
        return sorted(
            [
                name
                for name, cfg in self._strategies.items()
                if cfg.metadata.risk_level == risk_level
            ]
        )

    def search(
        self,
        category: Optional[StrategyCategory] = None,
        risk_level: Optional[RiskLevel] = None,
        min_return: Optional[float] = None,
        max_drawdown: Optional[float] = None,
        min_capital: Optional[float] = None,
        tags: Optional[List[str]] = None,
        scoring_mode: Optional[ScoringMode] = None,
        timing_method: Optional[TimingMethod] = None,
    ) -> List[str]:
        """
        多条件搜索策略

        Args:
            category: 策略分类
            risk_level: 风险等级
            min_return: 最低预期年化收益
            max_drawdown: 最大回撤容忍度上限
            min_capital: 最低资金要求上限
            tags: 标签列表 (任一匹配)
            scoring_mode: 评分模式
            timing_method: 择时方法

        Returns:
            匹配的策略名称列表
        """
        results = []

        for name, cfg in self._strategies.items():
            if category and cfg.metadata.category != category:
                continue
            if risk_level and cfg.metadata.risk_level != risk_level:
                continue
            if (
                min_return is not None
                and cfg.metadata.expected_annual_return < min_return
            ):
                continue
            if (
                max_drawdown is not None
                and cfg.metadata.max_drawdown_tolerance > max_drawdown
            ):
                continue
            if min_capital is not None and cfg.metadata.min_capital > min_capital:
                continue
            if tags and not any(t in cfg.metadata.tags for t in tags):
                continue
            if scoring_mode and cfg.scoring_mode != scoring_mode:
                continue
            if timing_method and cfg.timing_method != timing_method:
                continue
            results.append(name)

        return sorted(results)

    def search_by_tag(self, tag: str) -> List[str]:
        """
        按标签搜索

        Args:
            tag: 标签

        Returns:
            匹配的策略名称列表
        """
        return sorted(
            [name for name, cfg in self._strategies.items() if tag in cfg.metadata.tags]
        )

    # ===================================================================
    # 兼容性检查
    # ===================================================================

    def check_compatibility(self, strategy_a: str, strategy_b: str) -> Tuple[bool, str]:
        """
        检查两个策略是否兼容 (可组合)

        Args:
            strategy_a: 策略A名称
            strategy_b: 策略B名称

        Returns:
            (是否兼容, 原因说明)
        """
        cfg_a = self._strategies.get(strategy_a)
        cfg_b = self._strategies.get(strategy_b)

        if cfg_a is None:
            return False, f"策略 '{strategy_a}' 不存在"
        if cfg_b is None:
            return False, f"策略 '{strategy_b}' 不存在"

        cat_a = cfg_a.metadata.category.value
        cat_b = cfg_b.metadata.category.value

        compatible_cats = self._compatibility_rules.get(cat_a, set())
        if cat_b not in compatible_cats:
            return False, (f"分类不兼容: '{cat_a}' 与 '{cat_b}' 不能组合")

        # 检查参数冲突
        conflict = self._check_param_conflict(cfg_a, cfg_b)
        if conflict:
            return False, f"参数冲突: {conflict}"

        return True, "兼容"

    def check_portfolio_compatibility(
        self, strategies: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        检查多个策略的组合兼容性

        Args:
            strategies: 策略名称列表

        Returns:
            (是否全部兼容, 不兼容对列表)
        """
        incompatible_pairs = []

        for i in range(len(strategies)):
            for j in range(i + 1, len(strategies)):
                compatible, reason = self.check_compatibility(
                    strategies[i], strategies[j]
                )
                if not compatible:
                    incompatible_pairs.append(
                        f"{strategies[i]} <-> {strategies[j]}: {reason}"
                    )

        return len(incompatible_pairs) == 0, incompatible_pairs

    def _check_param_conflict(
        self, cfg_a: StrategyConfig, cfg_b: StrategyConfig
    ) -> Optional[str]:
        """检查两个策略之间的参数冲突"""
        # 检查 allocation_mode 冲突
        if (
            cfg_a.allocation_mode == cfg_b.allocation_mode
            and cfg_a.allocation_mode.value
            in self._param_conflict_rules.get("allocation_mode", set())
        ):
            # 相同配置模式不一定冲突，但需要检查具体参数
            pass

        # 检查 etf_pool 重叠度
        pool_a = set(cfg_a.etf_pool)
        pool_b = set(cfg_b.etf_pool)
        overlap = pool_a & pool_b
        if len(overlap) > 0 and len(overlap) == min(len(pool_a), len(pool_b)):
            # 完全重叠的ETF池可能导致过度集中
            if cfg_a.metadata.category == cfg_b.metadata.category:
                return f"ETF池完全重叠 ({len(overlap)} 个标的)"

        return None

    # ===================================================================
    # 参数验证
    # ===================================================================

    def validate(self, config: StrategyConfig) -> Tuple[bool, List[str]]:
        """
        验证策略配置

        检查项:
        - 必需参数是否存在
        - 参数值是否在合理范围
        - 参数之间是否冲突
        - ETF池是否有效
        - 风控参数是否合理

        Args:
            config: 策略配置

        Returns:
            (是否有效, 问题列表)
        """
        issues = []

        # 1. 元数据验证
        if not config.metadata.name:
            issues.append("策略名称不能为空")
        if config.metadata.min_capital <= 0:
            issues.append("最低资金必须大于 0")
        if not (0 < config.metadata.expected_annual_return <= 1):
            issues.append("预期年化收益应在 (0, 1] 范围内")
        if not (0 < config.metadata.max_drawdown_tolerance <= 1):
            issues.append("最大回撤容忍度应在 (0, 1] 范围内")

        # 2. ETF池验证
        if not config.etf_pool:
            issues.append("ETF池不能为空")
        elif len(config.etf_pool) < config.max_positions:
            issues.append(
                f"ETF池数量 ({len(config.etf_pool)}) 小于最大持仓数 ({config.max_positions})"
            )

        # 3. 参数范围验证
        if config.max_positions < 1:
            issues.append("最大持仓数必须 >= 1")
        if not (0 <= config.min_position_weight <= 1):
            issues.append("最小仓位权重应在 [0, 1] 范围内")
        if not (0 <= config.cash_reserve < 1):
            issues.append("现金保留比例应在 [0, 1) 范围内")
        if not (0 < config.max_single_weight <= 1):
            issues.append("单资产最大权重应在 (0, 1] 范围内")

        # 4. 权重一致性检查
        if config.min_position_weight > config.max_single_weight:
            issues.append("最小仓位权重不能大于单资产最大权重")

        # 5. 调仓周期验证
        if config.rebalance_period < 1:
            issues.append("调仓周期必须 >= 1")

        # 6. 风控参数验证
        rp = config.risk_params
        if rp.get("max_drawdown_stop", 0) <= 0:
            issues.append("最大回撤止损必须 > 0")
        if rp.get("single_stop_loss", 0) <= 0:
            issues.append("单个止损比例必须 > 0")

        # 7. 参数空间验证
        for pname, pspace in config.param_spaces.items():
            try:
                # 尝试采样验证
                pspace.sample()
            except Exception as e:
                issues.append(f"参数空间 '{pname}' 无效: {e}")

        return len(issues) == 0, issues

    def auto_fix(self, config: StrategyConfig) -> StrategyConfig:
        """
        自动修复常见配置问题

        Args:
            config: 策略配置

        Returns:
            修复后的配置
        """
        config = deepcopy(config)

        # 修复 ETF 池不足
        if config.etf_pool and len(config.etf_pool) < config.max_positions:
            config.max_positions = len(config.etf_pool)
            logger.warning(
                f"策略 '{config.metadata.name}': max_positions 已调整为 {config.max_positions}"
            )

        # 修复权重范围
        if config.min_position_weight > config.max_single_weight:
            config.min_position_weight = min(
                config.min_position_weight, config.max_single_weight
            )

        # 修复调仓周期
        if config.rebalance_period < 1:
            config.rebalance_period = 1

        # 修复风控参数
        if config.risk_params.get("max_drawdown_stop", 0) <= 0:
            config.risk_params["max_drawdown_stop"] = 0.15
        if config.risk_params.get("single_stop_loss", 0) <= 0:
            config.risk_params["single_stop_loss"] = 0.08

        return config

    # ===================================================================
    # 版本管理
    # ===================================================================

    def _record_version(
        self,
        name: str,
        version: str,
        action: str,
        old_version: Optional[str] = None,
        new_version: Optional[str] = None,
    ) -> None:
        """记录版本变更"""
        if name not in self._version_history:
            self._version_history[name] = []

        self._version_history[name].append(
            {
                "version": version,
                "action": action,
                "timestamp": datetime.datetime.now().isoformat(),
                "old_version": old_version,
                "new_version": new_version,
            }
        )

    def get_version_history(self, name: str) -> List[Dict[str, Any]]:
        """
        获取策略版本历史

        Args:
            name: 策略名称

        Returns:
            版本历史记录
        """
        return self._version_history.get(name, [])

    def bump_version(self, name: str, part: str = "patch") -> Optional[str]:
        """
        递增策略版本

        Args:
            name: 策略名称
            part: 递增部分 (major, minor, patch)

        Returns:
            新版本号，策略不存在则返回 None
        """
        config = self._strategies.get(name)
        if config is None:
            return None

        old_version = config.metadata.version
        new_version = config.metadata.bump_version(part)
        self._record_version(
            name,
            new_version,
            "version_bumped",
            old_version=old_version,
            new_version=new_version,
        )
        logger.info(f"策略 '{name}' 版本已更新: {old_version} -> {new_version}")
        return new_version

    def get_version(self, name: str) -> Optional[str]:
        """获取策略当前版本号"""
        config = self._strategies.get(name)
        return config.metadata.version if config else None

    # ===================================================================
    # 导出 & 导入
    # ===================================================================

    def export_strategy(self, name: str, path: Optional[str] = None) -> Optional[str]:
        """
        导出策略配置为 JSON

        Args:
            name: 策略名称
            path: 保存路径，None 则返回 JSON 字符串

        Returns:
            JSON 字符串或 None
        """
        config = self._strategies.get(name)
        if config is None:
            logger.warning(f"策略 '{name}' 不存在")
            return None

        json_str = config.to_json()

        if path:
            os.makedirs(
                os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True
            )
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_str)
            logger.info(f"策略 '{name}' 已导出到: {path}")
        else:
            return json_str

        return json_str

    def import_strategy(self, path: str, overwrite: bool = False) -> bool:
        """
        从 JSON 文件导入策略

        Args:
            path: JSON 文件路径
            overwrite: 是否覆盖已有策略

        Returns:
            是否导入成功
        """
        with open(path, "r", encoding="utf-8") as f:
            config = StrategyConfig.from_json(f.read())

        return self.register(config, overwrite=overwrite)

    def export_all(self, path: str) -> None:
        """
        导出所有策略到单个 JSON 文件

        Args:
            path: 保存路径
        """
        all_configs = {
            name: config.to_dict() for name, config in self._strategies.items()
        }
        os.makedirs(
            os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(all_configs, f, ensure_ascii=False, indent=2)
        logger.info(f"所有策略已导出到: {path}")

    # ===================================================================
    # 统计 & 信息
    # ===================================================================

    def get_stats(self) -> Dict[str, Any]:
        """
        获取注册中心统计信息

        Returns:
            统计字典
        """
        stats = {
            "total_strategies": len(self._strategies),
            "by_category": {},
            "by_risk_level": {},
            "avg_expected_return": 0.0,
            "avg_max_drawdown": 0.0,
            "avg_min_capital": 0.0,
        }

        if not self._strategies:
            return stats

        returns = []
        drawdowns = []
        capitals = []

        for cfg in self._strategies.values():
            cat = cfg.metadata.category.value
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

            rl = cfg.metadata.risk_level.value
            stats["by_risk_level"][rl] = stats["by_risk_level"].get(rl, 0) + 1

            returns.append(cfg.metadata.expected_annual_return)
            drawdowns.append(cfg.metadata.max_drawdown_tolerance)
            capitals.append(cfg.metadata.min_capital)

        stats["avg_expected_return"] = round(np.mean(returns), 4)
        stats["avg_max_drawdown"] = round(np.mean(drawdowns), 4)
        stats["avg_min_capital"] = round(np.mean(capitals), 2)

        return stats

    def get_strategy_summary(self):
        """
        获取策略汇总表

        Returns:
            DataFrame 包含所有策略的关键信息
        """
        import pandas as pd

        rows = []
        for name, cfg in self._strategies.items():
            rows.append(
                {
                    "name": name,
                    "display_name": cfg.metadata.display_name,
                    "category": cfg.metadata.category.value,
                    "risk_level": cfg.metadata.risk_level.value,
                    "min_capital": cfg.metadata.min_capital,
                    "expected_return": cfg.metadata.expected_annual_return,
                    "max_drawdown": cfg.metadata.max_drawdown_tolerance,
                    "scoring": cfg.scoring_mode.value,
                    "allocation": cfg.allocation_mode.value,
                    "timing": cfg.timing_method.value,
                    "rebalance_period": cfg.rebalance_period,
                    "max_positions": cfg.max_positions,
                    "etf_pool_size": len(cfg.etf_pool),
                    "version": cfg.metadata.version,
                    "tags": ", ".join(cfg.metadata.tags),
                }
            )

        return pd.DataFrame(rows)

    def __repr__(self) -> str:
        return f"StrategyRegistry(strategies={len(self._strategies)})"

    def __contains__(self, name: str) -> bool:
        return name in self._strategies

    def __len__(self) -> int:
        return len(self._strategies)

    def __getitem__(self, name: str) -> StrategyConfig:
        config = self._strategies.get(name)
        if config is None:
            raise KeyError(f"策略 '{name}' 不存在")
        return deepcopy(config)


# ---------------------------------------------------------------------------
# 便捷函数 (模块级 API)
# ---------------------------------------------------------------------------


def create_registry(auto_register: bool = True) -> StrategyRegistry:
    """
    创建策略注册中心

    Args:
        auto_register: 是否自动注册预设策略

    Returns:
        StrategyRegistry 实例
    """
    return StrategyRegistry(auto_register_presets=auto_register)


def get_strategy(name: str) -> Optional[StrategyConfig]:
    """便捷函数: 获取策略配置"""
    registry = StrategyRegistry()
    return registry.get(name)


def list_strategies(category: Optional[StrategyCategory] = None) -> List[str]:
    """便捷函数: 列出策略"""
    registry = StrategyRegistry()
    if category:
        return registry.list_by_category(category)
    return registry.list_all()


def search_strategies(**kwargs) -> List[str]:
    """便捷函数: 搜索策略"""
    registry = StrategyRegistry()
    return registry.search(**kwargs)


# ---------------------------------------------------------------------------
# 使用示例
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 70)
    print("策略注册中心 - 使用示例")
    print("=" * 70)

    # 示例 1: 创建注册中心并查看统计
    print("\n--- 示例 1: 注册中心统计 ---")
    registry = StrategyRegistry()
    stats = registry.get_stats()
    print(f"总策略数: {stats['total_strategies']}")
    print(f"按分类: {stats['by_category']}")
    print(f"按风险等级: {stats['by_risk_level']}")
    print(f"平均预期收益: {stats['avg_expected_return']:.1%}")
    print(f"平均最大回撤: {stats['avg_max_drawdown']:.1%}")

    # 示例 2: 获取特定策略
    print("\n--- 示例 2: 获取策略配置 ---")
    config = registry.get("etf_momentum_rsrs")
    if config:
        print(f"策略: {config.metadata.display_name}")
        print(f"分类: {config.metadata.category.value}")
        print(f"风险: {config.metadata.risk_level.value}")
        print(f"预期收益: {config.metadata.expected_annual_return:.1%}")
        print(f"最大回撤: {config.metadata.max_drawdown_tolerance:.1%}")
        print(f"评分模式: {config.scoring_mode.value}")
        print(f"配置模式: {config.allocation_mode.value}")
        print(f"择时方法: {config.timing_method.value}")
        print(f"参数: {config.params}")

    # 示例 3: 按分类列出策略
    print("\n--- 示例 3: 按分类列出 ---")
    for cat in StrategyCategory:
        names = registry.list_by_category(cat)
        print(f"  {cat.value}: {names}")

    # 示例 4: 搜索策略
    print("\n--- 示例 4: 搜索策略 ---")
    low_risk = registry.list_by_risk_level(RiskLevel.LOW)
    print(f"低风险策略: {low_risk}")

    high_return = registry.search(min_return=0.18)
    print(f"高收益策略 (>=18%): {high_return}")

    rsrs_timing = registry.search(timing_method=TimingMethod.RSRS)
    print(f"RSRS择时策略: {rsrs_timing}")

    # 示例 5: 兼容性检查
    print("\n--- 示例 5: 兼容性检查 ---")
    compatible, reason = registry.check_compatibility(
        "etf_momentum_rsrs", "min_correlation"
    )
    print(f"etf_momentum_rsrs + min_correlation: {compatible} ({reason})")

    compatible, reason = registry.check_compatibility(
        "chase_momentum", "stock_bond_balance"
    )
    print(f"chase_momentum + stock_bond_balance: {compatible} ({reason})")

    # 示例 6: 参数搜索空间
    print("\n--- 示例 6: 参数搜索空间 ---")
    config = registry.get("etf_momentum_rsrs")
    if config:
        for name, pspace in config.param_spaces.items():
            print(f"  {name}: {pspace}")
            print(f"    网格值: {pspace.grid_values()[:5]}...")
            print(f"    随机采样: {pspace.sample()}")

    # 示例 7: 策略验证
    print("\n--- 示例 7: 策略验证 ---")
    config = registry.get("etf_momentum_rsrs")
    valid, issues = registry.validate(config)
    print(f"验证结果: {'通过' if valid else '失败'}")
    if issues:
        for issue in issues:
            print(f"  - {issue}")

    # 示例 8: 版本管理
    print("\n--- 示例 8: 版本管理 ---")
    old_ver = registry.get_version("etf_momentum_rsrs")
    print(f"当前版本: {old_ver}")
    new_ver = registry.bump_version("etf_momentum_rsrs", "minor")
    print(f"升级后版本: {new_ver}")
    history = registry.get_version_history("etf_momentum_rsrs")
    print(f"版本历史: {len(history)} 条记录")

    # 示例 9: 策略汇总
    print("\n--- 示例 9: 策略汇总表 ---")
    summary = registry.get_strategy_summary()
    print(summary.to_string(index=False))

    # 示例 10: 克隆策略
    print("\n--- 示例 10: 克隆策略 ---")
    original = registry.get("etf_momentum_rsrs")
    cloned = original.clone("_v2")
    print(f"原始: {original.metadata.name} v{original.metadata.version}")
    print(f"克隆: {cloned.metadata.name} v{cloned.metadata.version}")
