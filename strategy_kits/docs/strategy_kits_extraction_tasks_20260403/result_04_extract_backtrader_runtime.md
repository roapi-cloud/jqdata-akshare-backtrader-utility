# 任务 04：抽 Backtrader 运行底座

## 1. 职责切分：聚宽 compat 层 vs QuantsPlaybook runtime 层

### 1.1 原始代码分析

| 来源 | 核心职责 | 问题 |
|------|----------|------|
| `聚宽有价值策略558/backtrader_base_strategy.py` | JQ2BTBaseStrategy、PortfolioCompat、下单API、定时任务、AkShare数据加载 | 与具体策略耦合，难以复用 |
| `QuantsPlaybook/BackTestTemplate/backtest_engine.py` | get_backtesting()、TradeRecord、StockCommission | 单一函数入口，配置能力弱 |
| `QuantsPlaybook/BackTestTemplate/bt_strategy.py` | SignalStrategy 简单模板 | 过于简单，缺乏JQ兼容层 |

### 1.2 抽取后的三层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    策略层 (User Strategy)                      │
│  ┌─────────────────┐  ┌─────────────────┐                    │
│  │ JQ2BTBaseStrategy│  │ SignalStrategy  │                    │
│  │ (聚宽风格)       │  │ (信号驱动)      │                    │
│  └─────────────────┘  └─────────────────┘                    │
├─────────────────────────────────────────────────────────────┤
│                    兼容层 (compat.py)                         │
│  - PortfolioCompat (context.portfolio)                       │
│  - run_daily 定时任务调度                                    │
│  - order_value/target/target_value 下单API                    │
│  - g 全局变量对象                                            │
├─────────────────────────────────────────────────────────────┤
│                    运行时层 (runtime.py)                      │
│  - run_backtest() 主入口                                     │
│  - build_broker() 佣金/滑点配置                              │
│  - build_analyzers() 分析器挂载                              │
├─────────────────────────────────────────────────────────────┤
│                    数据层 (datafeed.py)                       │
│  - load_datafeeds() 批量加载                                 │
│  - AkshareDataFeed 适配器                                    │
│  - get_price() JQ风格兼容                                    │
├─────────────────────────────────────────────────────────────┤
│                    配置层 (config.py)                         │
│  - BacktraderConfig 主配置                                   │
│  - CommissionConfig / SlippageConfig                         │
│  - AnalyzerConfig 分析器开关                                 │
├─────────────────────────────────────────────────────────────┤
│                    分析层 (analyzers.py)                      │
│  - TradeRecordAnalyzer 交易记录                              │
│  - PerformanceAnalyzer 绩效指标                              │
│  - SQNAnalyzer 系统质量数                                    │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 职责边界明确

| 层级 | 负责 | 不负责 |
|------|------|--------|
| **compat** | 聚宽风格API、context对象、定时任务、下单封装 | 回测执行、数据加载 |
| **runtime** | Cerebro组装、Broker配置、分析器挂载、结果收集 | 策略逻辑、具体信号 |
| **datafeed** | 数据加载、缓存管理、格式转换 | 策略决策、回测执行 |
| **config** | 参数定义、类型检查、默认值 | 业务逻辑 |

---

## 2. 最小运行底座文件清单

目标目录：`/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/execution/backtrader_runtime/`

```
backtrader_runtime/
├── __init__.py          # 包入口，导出主要接口
├── config.py            # 配置对象定义
├── runtime.py           # 运行核心（run_backtest等）
├── compat.py            # 聚宽兼容层
├── datafeed.py          # 数据加载
└── analyzers.py         # 分析器集合
```

---

## 3. 最小配置对象定义

### 3.1 BacktraderConfig（主配置）

```python
@dataclass
class BacktraderConfig:
    # === 基础回测参数 ===
    start_date: Union[str, date]
    end_date: Union[str, date]
    symbols: List[str]
    initial_cash: float = 1_000_000.0

    # === 佣金与滑点 ===
    commission: CommissionConfig = field(default_factory=CommissionConfig)
    slippage: SlippageConfig = field(default_factory=SlippageConfig)

    # === 数据源 ===
    data_config: DataConfig = field(default_factory=DataConfig)

    # === 分析器 ===
    analyzer_config: AnalyzerConfig = field(default_factory=AnalyzerConfig)

    # === 基准 ===
    benchmark: Optional[str] = "000300"

    # === 日志与调试 ===
    log_dir: str = "./logs"
    printlog: bool = True
    tradehistory: bool = True

    # === 策略参数 ===
    strategy_params: Dict[str, Any] = field(default_factory=dict)
```

### 3.2 子配置对象

| 配置类 | 关键参数 | 说明 |
|--------|----------|------|
| `CommissionConfig` | commission, stamp_duty, stocklike | A股佣金+印花税模型 |
| `SlippageConfig` | slippage_type, value | 百分比/固定滑点 |
| `DataConfig` | source, frequency, adjust, cache_dir | 数据源配置 |
| `AnalyzerConfig` | returns, sharpe, drawdown, trade_record... | 分析器开关 |

### 3.3 配置使用示例

```python
from strategy_kits.execution.backtrader_runtime import BacktraderConfig, CommissionConfig

config = BacktraderConfig(
    start_date="2020-01-01",
    end_date="2023-12-31",
    symbols=["000001.XSHE", "600519.XSHG", "510300"],
    initial_cash=1_000_000,
    commission=CommissionConfig(commission=0.0002, stamp_duty=0.001),
    benchmark="000300"
)
```

---

## 4. 最小策略接入接口

### 4.1 核心运行时接口

```python
# runtime.py
def run_backtest(
    config: BacktraderConfig,
    strategy_cls: Type[bt.Strategy],
    data_bundle: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    运行回测主入口
    
    Returns:
        {
            'cerebro': Cerebro 实例,
            'strategy': 策略实例,
            'portfolio_value': 最终资产,
            'nav_series': 净值序列,
            'metrics': 绩效指标 DataFrame,
            'trades': 交易记录 DataFrame,
            'analyzers': 分析器结果
        }
    """

def load_datafeeds(
    symbols: List[str],
    start_date: Union[str, date],
    end_date: Union[str, date],
    data_config: Optional[Dict] = None
) -> List[bt.feeds.PandasData]:
    """批量加载数据源"""

def build_broker(cerebro: bt.Cerebro, config: BacktraderConfig) -> bt.Broker:
    """配置佣金、滑点"""

def build_analyzers(cerebro: bt.Cerebro, config: AnalyzerConfig):
    """挂载分析器"""
```

### 4.2 聚宽兼容层接口

```python
# compat.py
class JQ2BTBaseStrategy(bt.Strategy):
    """聚宽风格策略基类"""
    
    def initialize(self, context):
        """策略初始化，替代 __init__"""
        pass
    
    def run_daily(self, func, time):
        """注册定时任务"""
        # 支持 '14:50', 'before_open', 'after_close', 'every_bar'
    
    # 下单API
    def order_value(self, code, value) -> Order
    def order_target(self, code, amount) -> Order
    def order_target_value(self, code, target) -> Order
    def order_target_percent(self, code, target) -> Order

class PortfolioCompat:
    """context.portfolio 兼容对象"""
    positions      # 持仓字典
    cash           # 可用现金
    available_cash # 可用现金
    total_value    # 总资产
    positions_value # 持仓市值
```

### 4.3 信号驱动策略基类

```python
class SignalStrategy(JQ2BTBaseStrategy):
    """信号驱动策略 - 只需实现 generate_signals"""
    
    params = (("rebalance_time", "14:50"),)
    
    def generate_signals(self, context) -> Dict[str, float]:
        """
        返回目标权重字典
        {code: weight}，weight 为 0-1 之间的比例
        """
        raise NotImplementedError
```

---

## 5. 骨架文件内容

### 5.1 `__init__.py`

```python
from .config import BacktraderConfig, CommissionConfig, SlippageConfig
from .runtime import run_backtest, load_datafeeds, build_broker, build_analyzers
from .analyzers import TradeRecordAnalyzer, PerformanceAnalyzer

__version__ = "0.1.0"
__all__ = [
    "BacktraderConfig", "CommissionConfig", "SlippageConfig",
    "run_backtest", "load_datafeeds", "build_broker", "build_analyzers",
    "TradeRecordAnalyzer", "PerformanceAnalyzer",
]
```

### 5.2 `config.py`

已创建完整文件，关键设计：
- 使用 `@dataclass` 实现类型安全
- `__post_init__` 自动处理日期格式转换
- 支持策略参数透传

### 5.3 `compat.py`

已创建完整文件，关键设计：
- `PortfolioCompat` 代理 broker 持仓查询
- `JQ2BTBaseStrategy` 封装定时任务调度
- 下单API自动处理 data 查找

### 5.4 `datafeed.py`

已创建完整文件，关键设计：
- `AkshareDataFeed` 统一数据接口
- 自动识别股票/ETF代码特征
- 支持缓存机制

### 5.5 `analyzers.py`

已创建完整文件，包含：
- `TradeRecordAnalyzer`: 详细交易记录（含 MFE/MAE）
- `PerformanceAnalyzer`: 收益率、夏普、回撤等
- `SQNAnalyzer`: 系统质量数

### 5.6 `runtime.py`

已创建完整文件，关键设计：
- `run_backtest()`: 统一入口
- `quick_backtest()`: 简化快速接口
- `_collect_results()`: 自动收集所有分析器结果

---

## 6. 新策略接入路径

### 6.1 聚宽风格策略（推荐）

```python
from strategy_kits.execution.backtrader_runtime import run_backtest, BacktraderConfig
from strategy_kits.execution.backtrader_runtime.compat import JQ2BTBaseStrategy

class MyStrategy(JQ2BTBaseStrategy):
    def initialize(self, context):
        # 初始化：设置参数、注册定时任务
        context.g.risk_ratio = 0.5
        context.run_daily(self.trade, time='14:50')
    
    def trade(self, context):
        # 定时执行的交易逻辑
        if some_condition(context):
            context.order_target_value('000001.XSHE', 100000)
        
        # 访问组合信息
        print(f"总资产: {context.portfolio.total_value}")

# 运行
config = BacktraderConfig(
    start_date='2020-01-01',
    end_date='2023-12-31',
    symbols=['000001.XSHE', '600519.XSHG']
)
result = run_backtest(config, MyStrategy)
print(result['metrics'])
```

### 6.2 信号驱动策略

```python
from strategy_kits.execution.backtrader_runtime.compat import SignalStrategy

class FactorStrategy(SignalStrategy):
    def generate_signals(self, context):
        # 计算因子，返回目标权重
        scores = self.calculate_factor_scores()
        top_stocks = scores.nlargest(10).index.tolist()
        
        # 等权分配
        weights = {code: 0.1 for code in top_stocks}
        return weights

result = run_backtest(config, FactorStrategy)
```

### 6.3 原生 Backtrader 策略

```python
import backtrader as bt

class NativeStrategy(bt.Strategy):
    def next(self):
        # 原生 Backtrader 写法
        if self.dataclose[0] > self.sma[0]:
            self.buy()

# 同样支持
result = run_backtest(config, NativeStrategy)
```

---

## 7. 不该抽的内容（明确边界）

| 类型 | 示例 | 归属 |
|------|------|------|
| 具体择时信号 | RSI金叉、MACD背离 | 策略层 |
| 具体ETF轮动参数 | ETF_POOL字典、轮动周期 | 策略层 |
| 具体仓位答案 | 目标仓位比例计算 | 策略层 |
| 数据获取细节 | AkShare具体调用参数 | datafeed层已封装 |
| 图表展示 | matplotlib绘图 | 分析层可选功能 |

---

## 8. 通过门槛检查

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 新策略接入路径足够短 | ✅ | 3行代码完成配置+运行 |
| JQ风格策略有清晰归宿 | ✅ | 继承 JQ2BTBaseStrategy |
| 普通BT策略有清晰归宿 | ✅ | 直接传入 bt.Strategy 子类 |
| 最小接口完整定义 | ✅ | run_backtest, load_datafeeds, build_broker, build_analyzers |
| context/portfolio_compat | ✅ | PortfolioCompat + JQ2BTBaseStrategy |
| 骨架文件可直接使用 | ✅ | 6个文件已创建完整 |

---

## 9. 文件创建确认

```
/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/execution/backtrader_runtime/
├── __init__.py          ✅ 已创建
├── config.py            ✅ 已创建
├── runtime.py           ✅ 已创建
├── compat.py            ✅ 已创建
├── datafeed.py          ✅ 已创建
└── analyzers.py         ✅ 已创建
```
