from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml


@dataclass
class DataConfig:
    """数据源配置。

    Attributes:
        source: 数据源类型，支持 jqdata 和 akshare。
        index: 基准指数代码，用于筛选股票池。
        start_date: 数据起始日期。
        end_date: 数据结束日期。
        frequency: 数据频率，如 daily, weekly, monthly。
        list_days: 上市天数过滤阈值。
    """

    source: str = "jqdata"
    index: str = "399905.XSHE"
    start_date: str = "2015-01-01"
    end_date: str = "2023-12-31"
    frequency: str = "monthly"
    list_days: int = 90


@dataclass
class PreprocessConfig:
    """预处理配置。

    Attributes:
        winsorize_method: 去极值方法，支持 mad, std, percentile。
        winsorize_scale: 去极值缩放倍数。
        fill_method: 缺失值填充方法，支持 industry_mean, median, zero。
        neutralize_by: 中性化维度列表，如 industry, market_cap。
        standardize: 是否进行标准化。
    """

    winsorize_method: str = "mad"
    winsorize_scale: float = 5.0
    fill_method: str = "industry_mean"
    neutralize_by: List[str] = field(default_factory=lambda: ["industry", "market_cap"])
    standardize: bool = True


@dataclass
class LabelConfig:
    """标签构建配置。

    Attributes:
        method: 标签构建方法，支持 top_bottom, regression, ranking。
        top_pct: 头部样本比例。
        bottom_pct: 尾部样本比例。
        holding_period: 持有期（交易日）。
    """

    method: str = "top_bottom"
    top_pct: float = 0.3
    bottom_pct: float = 0.3
    holding_period: int = 20


@dataclass
class ModelConfig:
    """模型配置。

    Attributes:
        name: 模型名称。
        params: 模型超参数字典。
        train_window: 训练窗口大小（月）。
        retrain_frequency: 重新训练频率，支持 daily, weekly, monthly。
    """

    name: str = "xgboost"
    params: Dict[str, Any] = field(default_factory=dict)
    train_window: int = 60
    retrain_frequency: str = "monthly"


@dataclass
class PortfolioConfig:
    """组合构建配置。

    Attributes:
        n_stocks: 组合中股票数量。
        weighting: 权重分配方法，支持 equal, probability, risk_parity。
        max_turnover: 最大换手率限制。
    """

    n_stocks: int = 5
    weighting: str = "equal"
    max_turnover: float = 1.0


@dataclass
class BacktestConfig:
    """回测配置。

    Attributes:
        initial_capital: 初始资金。
        commission: 佣金费率。
        slippage: 滑点比率。
        stamp_tax: 印花税率。
        benchmark: 基准指数代码。
    """

    initial_capital: float = 1_000_000
    commission: float = 0.0003
    slippage: float = 0.001
    stamp_tax: float = 0.001
    benchmark: str = "399905.XSHE"


@dataclass
class PipelineConfig:
    """流水线总配置。

    聚合所有子配置，支持从 YAML 文件加载和保存。

    Attributes:
        data: 数据源配置。
        preprocess: 预处理配置。
        label: 标签构建配置。
        model: 模型配置。
        portfolio: 组合构建配置。
        backtest: 回测配置。
        factors: 因子名称列表。
    """

    data: DataConfig = field(default_factory=DataConfig)
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)
    label: LabelConfig = field(default_factory=LabelConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    factors: List[str] = field(default_factory=lambda: ["EP", "BP", "ROE"])

    @classmethod
    def from_yaml(cls, path: str) -> "PipelineConfig":
        """从 YAML 文件加载配置。

        Args:
            path: YAML 文件路径。

        Returns:
            PipelineConfig 实例。
        """
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        def build_nested(dataclass_type, raw):
            nested_fields = {
                f.name: f.type
                for f in dataclass_type.__dataclass_fields__.values()
                if hasattr(f.type, "__dataclass_fields__")
            }
            kwargs = {}
            for k, v in raw.items():
                if k in nested_fields and isinstance(v, dict):
                    kwargs[k] = build_nested(nested_fields[k], v)
                else:
                    kwargs[k] = v
            return dataclass_type(**kwargs)

        return build_nested(cls, data)

    def to_yaml(self, path: str) -> None:
        """保存配置到 YAML 文件。

        Args:
            path: YAML 文件保存路径。
        """

        def dataclass_to_dict(obj):
            if hasattr(obj, "__dataclass_fields__"):
                return {k: dataclass_to_dict(v) for k, v in asdict(obj).items()}
            return obj

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                dataclass_to_dict(self), f, default_flow_style=False, allow_unicode=True
            )
