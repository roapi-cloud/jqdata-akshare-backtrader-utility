# 量化交易框架 - 快速开始指南

## 项目概述

这是一个**通用的A股量化交易框架**，支持从数据获取、因子计算、信号生成、策略组合到回测分析的完整流水线。所有模块可独立使用，也可组合运行。

## 项目结构

```
quant_framework/
├── config/                    # 配置管理
│   ├── settings.py           # 全局配置类
│   └── strategies.yaml       # 策略配置文件
├── core/                      # 核心模块
│   ├── data/                 # 数据层 (AkShare数据源)
│   ├── factors/              # 因子层 (技术/宽度/情绪因子)
│   ├── signals/              # 信号层 (择时/选股信号)
│   ├── strategy/             # 策略层 (组合/仓位管理)
│   └── backtest/             # 回测层 (引擎/券商/成本)
├── analysis/                  # 绩效分析
│   ├── metrics.py            # 绩效指标计算
│   ├── report.py             # 报告生成
│   └── visualizer.py         # 可视化图表
├── examples/                  # 示例策略
│   ├── breadth_timing_strategy.py
│   ├── multi_factor_strategy.py
│   ├── rsrs_timing_strategy.py
│   ├── sentiment_contrarian.py
│   └── combined_strategy.py
├── utils/                     # 工具函数
│   ├── logger.py             # 日志系统
│   └── helpers.py            # 辅助函数
├── tests/                     # 单元测试 (151 tests passed)
├── main.py                    # CLI入口
├── pipeline.py               # 主流水线
└── run_backtest.py           # 快速运行脚本
```

## 快速开始

### 1. 安装依赖

```bash
pip install pandas numpy akshare pyyaml matplotlib seaborn scipy pytest
```

### 2. 运行测试验证环境

```bash
python -m pytest quant_framework/tests/ -v
```

预期输出：`151 passed, 1 skipped`

### 3. 方式一：使用CLI运行回测

```bash
# 使用配置文件运行
python -m quant_framework.main --config quant_framework/config/strategies.yaml --mode backtest

# 指定日期范围
python -m quant_framework.main --config quant_framework/config/strategies.yaml --mode backtest --start 2020-01-01 --end 2023-12-31

# 详细分析模式
python -m quant_framework.main --config quant_framework/config/strategies.yaml --mode analyze
```

### 4. 方式二：使用Python代码运行

```python
from quant_framework.pipeline import QuantPipeline
from quant_framework.core.data import AkShareSource
from quant_framework.examples.breadth_timing_strategy import BreadthTimingStrategy
from quant_framework.config.settings import Settings

# 1. 初始化配置
config = Settings(
    initial_capital=1_000_000,
    commission_rate=0.0003,
    slippage=0.002
)

# 2. 初始化数据源
data_source = AkShareSource()

# 3. 初始化策略
strategy = BreadthTimingStrategy(
    symbol="510300",  # 沪深300ETF
    ma_window=20,
    volume_shrink_threshold=0.15
)

# 4. 创建并运行流水线
pipeline = QuantPipeline(data_source, strategy, config)
result = pipeline.run("2020-01-01", "2023-12-31")

# 5. 分析结果
metrics = pipeline.analyze(result)
print(metrics.summary())

# 6. 生成报告
pipeline.report(result, output_dir="output/")
```

### 5. 方式三：快速运行脚本

```bash
# 运行内置的动量策略
python quant_framework/run_backtest.py --start 2020-01-01 --end 2023-12-31 --top-n 10
```

## 核心模块使用指南

### 数据层

```python
from quant_framework.core.data import AkShareSource

source = AkShareSource()

# 获取指数价格
df = source.get_index_prices("000300", "2023-01-01", "2023-12-31")

# 获取股票价格
df = source.get_stock_prices(["600519", "000858"], "2023-01-01", "2023-12-31")

# 获取指数成分股
stocks = source.get_index_stocks("000300", "2023-06-01")

# 获取交易日历
days = source.get_trade_days("2023-01-01", "2023-12-31")
```

### 因子层

```python
from quant_framework.core.factors import FactorRegistry, MAFactor, RSIFactor

# 注册因子
registry = FactorRegistry()
registry.register(MAFactor())
registry.register(RSIFactor())

# 计算因子
results = registry.calculate_all(price_data, windows=[5, 10, 20])

# 查看结果
for name, result in results.items():
    print(f"{name}: {result.values.tail()}")
```

### 信号层

```python
from quant_framework.core.signals import MATimingSignal, FactorRankSignal

# 择时信号
timing = MATimingSignal(fast_window=5, slow_window=20)
signal = timing.generate(ma_data)

# 选股信号
selector = FactorRankSignal(top_n=10, factor_weights={"momentum": 0.5, "value": 0.5})
signal = selector.generate(factor_data)
```

### 回测引擎

```python
from quant_framework.core.backtest import BacktestEngine, SimulatedBroker, AStockCostModel

# 初始化
cost_model = AStockCostModel(commission=0.0003, slippage=0.002)
broker = SimulatedBroker(initial_capital=1_000_000, cost_model=cost_model)
engine = BacktestEngine(strategy, broker, data_source)

# 运行回测
result = engine.run("2020-01-01", "2023-12-31")

# 查看结果
print(f"总收益: {result.total_return:.2%}")
print(f"最大回撤: {result.max_drawdown:.2%}")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
```

### 绩效分析

```python
from quant_framework.analysis import PerformanceMetrics, ReportGenerator

# 计算指标
metrics = PerformanceMetrics(
    daily_values=result.daily_values,
    benchmark_values=benchmark_values,
    trades=result.trades
)

# 获取所有指标
summary = metrics.all_metrics()
print(summary)

# 生成报告
reporter = ReportGenerator()
reporter.generate_html_report(result, metrics, output_dir="output/")
```

## 内置策略说明

### 1. 市场宽度择时策略 (breadth_timing_strategy.py)
- **原理**: MA上方比例 + 成交额萎缩度
- **买入**: 宽度改善 + 地量见底
- **卖出**: 宽度恶化 + 放量见顶
- **适用**: 宽基指数ETF择时

### 2. 多因子选股策略 (multi_factor_strategy.py)
- **原理**: PE + PB + 动量 + 换手率综合打分
- **选股**: 排名前10的股票
- **调仓**: 月度调仓
- **适用**: 股票组合构建

### 3. RSRS择时策略 (rsrs_timing_strategy.py)
- **原理**: 高低点回归斜率标准化 × R²
- **买入**: RSRS > 0.7
- **卖出**: RSRS < -0.7
- **适用**: 指数ETF择时

### 4. 情绪反向策略 (sentiment_contrarian.py)
- **原理**: GSISI情绪指数 + 换手率情绪
- **买入**: 情绪极度悲观(Z < -1.5)
- **卖出**: 情绪极度乐观(Z > 1.5)
- **适用**: 逆向投资

### 5. 组合策略 (combined_strategy.py)
- **原理**: 择时控制仓位 + 因子选股
- **仓位**: 波动率目标管理
- **适用**: 完整投资组合

## 自定义策略

继承`BaseStrategy`类，实现`on_bar`方法：

```python
from quant_framework.core.strategy import BaseStrategy, Portfolio

class MyStrategy(BaseStrategy):
    def initialize(self, params):
        self.my_param = params.get("my_param", 10)
    
    def on_bar(self, date, data, portfolio):
        # 你的策略逻辑
        if self.should_buy(data):
            self.buy("600519", 1000)
        elif self.should_sell(data):
            self.sell("600519", 1000)
    
    def should_buy(self, data):
        # 买入条件
        return False
    
    def should_sell(self, data):
        # 卖出条件
        return False
```

## 配置文件示例

```yaml
# config/strategies.yaml
strategy:
  name: "breadth_timing"
  class: "BreadthTimingStrategy"
  params:
    symbol: "510300"
    ma_window: 20
    volume_shrink_threshold: 0.15

backtest:
  start_date: "2020-01-01"
  end_date: "2023-12-31"
  initial_capital: 1000000
  commission_rate: 0.0003
  slippage: 0.002

data:
  source: "akshare"
  cache_dir: "./data_cache"
  cache_ttl: 86400
```

## 常见问题

### Q: 数据获取失败怎么办？
A: AkShare是免费数据源，可能有频率限制。可以：
1. 启用数据缓存（默认开启）
2. 降低请求频率
3. 切换到Tushare或聚宽数据源

### Q: 如何添加新因子？
A: 继承`Factor`基类，实现`calculate`方法，然后注册到`FactorRegistry`。

### Q: 回测结果与预期不符？
A: 检查：
1. 数据是否正确复权
2. 交易成本设置是否合理
3. 是否有未来函数（使用未来数据）

### Q: 如何优化策略参数？
A: 使用`main.py`的optimize模式：
```bash
python -m quant_framework.main --config config/strategies.yaml --mode optimize
```

## 测试

```bash
# 运行所有测试
python -m pytest quant_framework/tests/ -v

# 运行特定模块测试
python -m pytest quant_framework/tests/test_factors.py -v

# 运行集成测试
python -m pytest quant_framework/tests/test_integration.py -v
```

## 贡献指南

1. 添加新因子：在`core/factors/`下新建文件
2. 添加新信号：在`core/signals/`下新建文件
3. 添加新策略：在`examples/`下新建文件
4. 所有代码需通过测试：`pytest quant_framework/tests/`

## 许可证

MIT License
