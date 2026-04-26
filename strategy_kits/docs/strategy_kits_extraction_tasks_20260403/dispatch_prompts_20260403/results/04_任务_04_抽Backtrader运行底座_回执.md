# 任务 04 回执：抽 Backtrader 运行底座

## 完成状态

- [x] 聚宽 compat 层与 QuantsPlaybook runtime 层职责切分
- [x] 最小运行底座文件清单
- [x] 最小配置对象定义
- [x] 最小策略接入接口
- [x] 骨架文件已创建

## 产出文件

### 1. 主结果文档
`/Users/fengzhi/Downloads/git/testlixingren/docs/strategy_kits_extraction_tasks_20260403/result_04_extract_backtrader_runtime.md`

### 2. 运行底座骨架（已创建）
```
/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/execution/backtrader_runtime/
├── __init__.py          # 包入口
├── config.py            # BacktraderConfig / CommissionConfig / SlippageConfig
├── runtime.py           # run_backtest() / load_datafeeds() / build_broker() / build_analyzers()
├── compat.py            # JQ2BTBaseStrategy / PortfolioCompat / SignalStrategy
├── datafeed.py          # AkshareDataFeed / load_datafeeds()
└── analyzers.py         # TradeRecordAnalyzer / PerformanceAnalyzer / SQNAnalyzer
```

## 核心接口定义

### 运行时接口
```python
run_backtest(config, strategy_cls, data_bundle=None) -> dict
load_datafeeds(symbols, start_date, end_date, data_config=None)
build_broker(cerebro, config)
build_analyzers(cerebro, analyzer_config)
```

### 策略基类
```python
JQ2BTBaseStrategy          # 聚宽风格：initialize() + run_daily() + context
SignalStrategy             # 信号驱动：只需实现 generate_signals()
```

### 配置对象
```python
BacktraderConfig(
    start_date, end_date, symbols, initial_cash,
    commission, slippage, data_config, analyzer_config,
    benchmark, strategy_params
)
```

## 职责切分

| 层级 | 负责 | 不负责 |
|------|------|--------|
| compat.py | JQ风格API、context、定时任务、下单封装 | 数据加载、回测执行 |
| runtime.py | Cerebro组装、Broker配置、分析器挂载 | 策略逻辑、信号计算 |
| datafeed.py | 数据加载、缓存、格式转换 | 策略决策 |
| analyzers.py | 交易记录、绩效计算 | 交易执行 |

## 新策略接入示例

```python
from strategy_kits.execution.backtrader_runtime import run_backtest, BacktraderConfig
from strategy_kits.execution.backtrader_runtime.compat import JQ2BTBaseStrategy

class MyStrategy(JQ2BTBaseStrategy):
    def initialize(self, context):
        context.run_daily(self.trade, time='14:50')
    
    def trade(self, context):
        context.order_target_value('000001.XSHE', 100000)

config = BacktraderConfig(
    start_date='2020-01-01',
    end_date='2023-12-31',
    symbols=['000001.XSHE', '600519.XSHG']
)

result = run_backtest(config, MyStrategy)
```

## 通过检查

- [x] 新策略接入路径短（3行配置 + 策略类定义）
- [x] JQ风格策略有清晰归宿（继承 JQ2BTBaseStrategy）
- [x] 原生BT策略有清晰归宿（直接传入 bt.Strategy 子类）
- [x] 最小接口已完整定义
- [x] 骨架文件可直接使用

## 边界声明

**已抽取**：
- 配置管理、数据加载、回测执行、分析器、聚宽兼容层

**未抽取（属于策略层）**：
- 具体择时信号
- 具体ETF轮动参数
- 具体仓位计算逻辑
