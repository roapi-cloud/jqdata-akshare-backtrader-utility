"""
Backtrader 运行配置
==================

定义回测所需的全部配置参数，采用 dataclass 便于类型检查和序列化。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable, Union
from datetime import date
from enum import Enum


class CommissionType(Enum):
    """佣金类型"""
    PERC = "percentage"      # 百分比佣金
    FIXED = "fixed"          # 固定金额


class SlippageType(Enum):
    """滑点类型"""
    PERC = "percentage"      # 百分比滑点
    FIXED = "fixed"          # 固定金额滑点


@dataclass
class CommissionConfig:
    """
    佣金配置

    支持股票模式（买入佣金 + 卖出佣金 + 印花税）
    """
    commission: float = 0.0002           # 佣金率（默认万2）
    stamp_duty: float = 0.001            # 印花税率（默认千1，仅卖出）
    stocklike: bool = True               # 是否为股票模式
    commtype: CommissionType = CommissionType.PERC
    percabs: bool = True                 # commission 是否以 % 为单位
    min_commission: float = 5.0          # 最低佣金（部分券商）

    def to_backtrader_params(self) -> Dict[str, Any]:
        """转换为 backtrader 参数格式"""
        import backtrader as bt
        return {
            "commission": self.commission,
            "stocklike": self.stocklike,
            "commtype": bt.CommInfoBase.COMM_PERC if self.commission == CommissionType.PERC else bt.CommInfoBase.COMM_FIXED,
            "percabs": self.percabs,
        }


@dataclass
class SlippageConfig:
    """
    滑点配置
    """
    slippage_type: SlippageType = SlippageType.PERC
    value: float = 0.0001                  # 默认万1滑点

    def apply_to_broker(self, broker):
        """应用滑点配置到 broker"""
        import backtrader as bt
        if self.slippage_type == SlippageType.PERC:
            broker.set_slippage_perc(perc=self.value)
        else:
            broker.set_slippage_fixed(fixed=self.value)


@dataclass
class DataConfig:
    """
    数据源配置
    """
    source: str = "akshare"               # 数据源类型
    frequency: str = "daily"              # 频率: daily, minute
    adjust: str = "qfq"                   # 复权方式: qfq(前复权), hfq(后复权), none
    cache_dir: str = "./data_cache"       # 缓存目录
    force_update: bool = False            # 强制更新缓存
    fields: Optional[List[str]] = None    # 指定字段


@dataclass
class AnalyzerConfig:
    """
    分析器配置
    """
    returns: bool = True                  # 收益率分析
    sharpe: bool = True                   # 夏普比率
    drawdown: bool = True                 # 回撤分析
    trade_analyzer: bool = True           # 交易分析
    transactions: bool = True             # 交易成本
    sqn: bool = True                      # SQN 系统质量数
    trade_record: bool = True             # 详细交易记录
    period_stats: bool = True             # 周期统计
    time_return: bool = True              # 时间序列收益率

    # 自定义分析器
    custom_analyzers: List[Any] = field(default_factory=list)


@dataclass
class BacktraderConfig:
    """
    Backtrader 回测配置（主配置对象）

    这是运行回测所需的最小配置集合，策略接入时只需关注：
    - 时间范围（start_date, end_date）
    - 标的列表（symbols）
    - 初始资金（initial_cash）
    - 佣金滑点（commission, slippage）

    Example:
        ```python
        config = BacktraderConfig(
            start_date="2020-01-01",
            end_date="2023-12-31",
            symbols=["000001.XSHE", "600519.XSHG"],
            initial_cash=1_000_000,
            commission=CommissionConfig(commission=0.0002),
            slippage=SlippageConfig(value=0.0001),
        )
        ```
    """
    # === 基础回测参数 ===
    start_date: Union[str, date]
    end_date: Union[str, date]
    symbols: List[str] = field(default_factory=list)
    initial_cash: float = 1_000_000.0

    # === 佣金与滑点 ===
    commission: CommissionConfig = field(default_factory=CommissionConfig)
    slippage: SlippageConfig = field(default_factory=SlippageConfig)

    # === 数据源 ===
    data_config: DataConfig = field(default_factory=DataConfig)

    # === 分析器 ===
    analyzer_config: AnalyzerConfig = field(default_factory=AnalyzerConfig)

    # === 基准 ===
    benchmark: Optional[str] = "000300"   # 基准指数代码，None表示无基准

    # === 日志与调试 ===
    log_dir: str = "./logs"
    printlog: bool = True
    tradehistory: bool = True             # 开启详细交易历史

    # === 策略参数 ===
    strategy_params: Dict[str, Any] = field(default_factory=dict)

    # === 数据预加载（可选）===
    # 如果提供，将跳过数据加载直接使用
    preloaded_data: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """初始化后处理"""
        # 统一转换为 date 类型
        if isinstance(self.start_date, str):
            from datetime import datetime
            self.start_date = datetime.strptime(self.start_date, "%Y-%m-%d").date()
        if isinstance(self.end_date, str):
            from datetime import datetime
            self.end_date = datetime.strptime(self.end_date, "%Y-%m-%d").date()

        # 确保 symbols 是列表
        if isinstance(self.symbols, str):
            self.symbols = [self.symbols]

        # 创建日志目录
        import os
        os.makedirs(self.log_dir, exist_ok=True)
