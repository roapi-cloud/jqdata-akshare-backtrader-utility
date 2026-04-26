# 详细使用指南

## 目录

- [如何运行流水线](#如何运行流水线)
- [如何查看生成的因子](#如何查看生成的因子)
- [如何自定义配置](#如何自定义配置)
- [如何添加新策略](#如何添加新策略)

---

## 如何运行流水线

### 完整流水线运行

流水线包含 5 个步骤，按顺序执行：

```
scan_strategies → parse_strategies → generate_signals → store_factors → generate_mapping
```

```python
from core.pipeline_orchestrator import PipelineOrchestrator, PipelineOrchestratorConfig

# 1. 创建配置
config = PipelineOrchestratorConfig(
    strategy_dir="./strategies",
    output_dir="./output",
    max_workers=4,
    executor_type="process",  # CPU 密集型用 process，I/O 密集型用 thread
)

# 2. 创建流水线实例
pipeline = PipelineOrchestrator(config)

# 3. 运行完整流水线
result = pipeline.run_full_pipeline()

# 4. 查看结果
print(f"处理策略数: {result['summary']['total_strategies_processed']}")
print(f"失败策略数: {result['summary']['total_strategies_failed']}")
print(f"总耗时: {result['summary']['total_duration_sec']}s")
```

### 单步骤运行

每个步骤可以独立运行：

```python
# 仅扫描策略
scan_result = pipeline.run_step("scan_strategies")
print(f"发现 {scan_result['total']} 个策略文件")

# 仅解析策略
parse_result = pipeline.run_step("parse_strategies")

# 仅生成信号
signal_result = pipeline.run_step("generate_signals")

# 仅存储因子
store_result = pipeline.run_step("store_factors")

# 仅生成映射
mapping_result = pipeline.run_step("generate_mapping")
```

### 从指定步骤开始

```python
# 从第 2 步（generate_signals）开始运行
result = pipeline.run_full_pipeline(start_from=2)
```

### 断点续传

流水线会在每个步骤完成后自动保存检查点：

```python
# 从最新检查点恢复
pipeline = PipelineOrchestrator(config)
result = pipeline.resume_from_checkpoint()

# 从指定检查点恢复
result = pipeline.resume_from_checkpoint(
    "./checkpoints/checkpoint_20240101_120000.json"
)
```

### 查看流水线状态

```python
status = pipeline.get_pipeline_status()

for step_name, step_info in status["steps"].items():
    print(f"{step_name}: {step_info['status']}")
    print(f"  完成: {step_info['items_completed']}/{step_info['items_total']}")
    print(f"  失败: {step_info['items_failed']}")
    if step_info['duration']:
        print(f"  耗时: {step_info['duration']:.1f}s")
```

---

## 如何查看生成的因子

### 因子数据库查询

```python
from core.factor_database import FactorDatabase

db = FactorDatabase(
    db_path="./output/factors/metadata.db",
    data_dir="./output/factors/data",
)
```

#### 列出所有因子

```python
factors = db.list_all_factors()
for f in factors:
    print(f"因子: {f['factor_name']}")
    print(f"  类型: {f['factor_type']}")
    print(f"  来源策略: {f['strategy_source']}")
    print(f"  数据量: {f['row_count']} 条")
    print(f"  日期范围: {f['date_range_start']} ~ {f['date_range_end']}")
```

#### 获取因子元数据

```python
metadata = db.get_factor_metadata("momentum_20")
print(metadata)
```

#### 加载因子信号数据

```python
# 加载全部数据
df = db.load_factor_signals("momentum_20")

# 按日期范围加载
df = db.load_factor_signals(
    "momentum_20",
    date_range=("2023-01-01", "2023-12-31"),
)

# 按股票列表加载
df = db.load_factor_signals(
    "momentum_20",
    stock_list=["000001.XSHE", "000002.XSHE"],
)
```

#### 横截面查询（某日所有股票）

```python
# 获取 2023-06-01 所有股票的因子信号
cross_section = db.get_signals_cross_section("2023-06-01")
# 返回 DataFrame，index=stock_code, columns=factor_names
```

#### 时序查询（某股票在所有日期）

```python
# 获取平安银行在所有日期的因子信号
time_series = db.get_signals_time_series(
    "000001.XSHE",
    date_range=("2023-01-01", "2023-12-31"),
)
# 返回 DataFrame，index=date, columns=factor_names
```

#### 因子组合

```python
# 等权组合
combined = db.get_factor_combination(
    factor_names=["momentum_20", "volatility_20", "rsi_14"],
)

# 自定义权重
combined = db.get_factor_combination(
    factor_names=["momentum_20", "volatility_20"],
    weights={"momentum_20": 0.7, "volatility_20": 0.3},
)
```

#### 因子相关性

```python
corr_matrix = db.get_factor_correlation()
print(corr_matrix)
```

#### 因子统计

```python
stats = db.get_factor_stats("momentum_20")
print(f"均值: {stats['signal_mean']}")
print(f"标准差: {stats['signal_std']}")
print(f"股票数: {stats['unique_stocks']}")
print(f"交易日数: {stats['unique_dates']}")
```

### 查看映射表

```python
import pandas as pd

# 加载 CSV 映射表
mapping_df = pd.read_csv("./output/mapping_table.csv")
print(mapping_df.head())

# 加载 Excel 映射表（含多个 sheet）
xls = pd.ExcelFile("./output/strategy_factor_mapping.xlsx")
print(xls.sheet_names)  # ['策略因子映射', '因子分类', '追溯关系', '汇总']

mapping = pd.read_excel(xls, sheet_name="策略因子映射")
categories = pd.read_excel(xls, sheet_name="因子分类")
traceability = pd.read_excel(xls, sheet_name="追溯关系")
summary = pd.read_excel(xls, sheet_name="汇总")
```

### 查看策略解析结果

```python
import json

with open("./output/parsed/strategy.json", "r", encoding="utf-8") as f:
    result = json.load(f)

# 查看提取的因子
print(result["factors_and_indicators"])

# 查看选股规则
print(result["stock_selection_rules"])

# 查看调仓周期
print(result["rebalance_frequency"])

# 查看持仓数量
print(result["portfolio_size"])
```

---

## 如何自定义配置

### 流水线配置

```python
from core.pipeline_orchestrator import PipelineOrchestratorConfig

config = PipelineOrchestratorConfig(
    strategy_dir="/path/to/strategies",   # 策略目录
    output_dir="/path/to/output",         # 输出目录
    checkpoint_dir="/path/to/checkpoints", # 检查点目录
    max_workers=8,                        # 并行数
    executor_type="thread",               # process 或 thread
    retry_count=3,                        # 重试次数
    step_timeout=3600,                    # 单步骤超时（秒）
)
```

### 策略扫描器配置

```python
from core.strategy_scanner import StrategyScanner

scanner = StrategyScanner(
    strategy_dir="./strategies",
    cache_dir="./cache",  # 缓存目录，用于加速重复扫描
)
```

### 策略解析器配置

```python
from core.strategy_parser import StrategyParser

parser = StrategyParser(
    output_dir="./output/parsed",  # 解析结果输出目录
)
```

### 映射表生成器配置

```python
from core.mapping_generator import MappingGenerator

generator = MappingGenerator(
    output_dir="./output/mappings",  # 映射表输出目录
)
```

### 因子数据库配置

```python
from core.factor_database import FactorDatabase

db = FactorDatabase(
    db_path="./output/factors/metadata.db",  # SQLite 元数据路径
    data_dir="./output/factors/data",        # Parquet 数据目录
)
```

### 代码生成器配置

```python
from templates.code_generator import CodeGenerator

generator = CodeGenerator(
    template_dir="./templates",       # 模板目录
    output_dir="./output/generated",  # 生成代码输出目录
)
```

### 自定义模板

修改 `templates/strategy_template.py` 可以自定义生成的因子计算脚本：

- 修改 `DataLoader` 类以支持新的数据源
- 修改 `FactorEngine` 类以添加自定义因子计算逻辑
- 修改 `ResultSaver` 类以支持新的输出格式

---

## 如何添加新策略

### 1. 放置策略文件

将策略文件放入 `strategy_dir` 指定的目录：

```
strategies/
├── my_new_strategy.py      # Backtrader 策略
├── another_strategy.txt    # 聚宽策略
└── ...
```

### 2. 策略文件规范

#### 聚宽策略（.txt）

聚宽策略应包含标准的聚宽函数：

```python
def initialize(context):
    g.stock_num = 10
    set_benchmark('000300.XSHG')

def handle_data(context, data):
    # 选股逻辑
    q = query(valuation.code).filter(
        valuation.pe_ratio < 30,
        valuation.market_cap > 50
    ).order_by(
        valuation.market_cap.asc()
    ).limit(g.stock_num)

    # 调仓逻辑
    run_daily(my_trade, time='09:30')
```

#### Backtrader 策略（.py）

Backtrader 策略应继承 `bt.Strategy`：

```python
import backtrader as bt

class MyStrategy(bt.Strategy):
    params = (
        ("stock_num", 10),
        ("rebalance_period", 5),
    )

    def __init__(self):
        self.sma = bt.indicators.SMA(self.data.close, period=20)

    def next(self):
        # 选股和交易逻辑
        pass
```

### 3. 运行流水线

```python
from core.pipeline_orchestrator import PipelineOrchestrator, PipelineOrchestratorConfig

config = PipelineOrchestratorConfig(
    strategy_dir="./strategies",
    output_dir="./output",
)

pipeline = PipelineOrchestrator(config)
result = pipeline.run_full_pipeline()
```

### 4. 查看解析结果

```python
from core.strategy_parser import StrategyParser

parser = StrategyParser()

# 解析新策略
result = parser.parse_jq_strategy("./strategies/my_new_strategy.txt")

# 查看提取的信息
print(f"选股规则: {result['stock_selection_rules']}")
print(f"因子: {result['factors_and_indicators']}")
print(f"调仓周期: {result['rebalance_frequency']}")
print(f"持仓数量: {result['portfolio_size']}")
```

### 5. 生成因子计算代码

```python
from templates.code_generator import CodeGenerator

generator = CodeGenerator(
    template_dir="./templates",
    output_dir="./output/generated",
)

generator.generate_strategy_code(
    strategy_name="my_new_strategy",
    parsed_rules={
        "data_source": "jqdata",
        "universe": "000300.XSHG",
        "factors": ["pe_ratio", "market_cap"],
        "start_date": "2020-01-01",
        "end_date": "2024-12-31",
    },
)
```

### 6. 运行生成的因子计算脚本

```bash
python ./output/generated/my_new_strategy.py
```

或使用环境变量指定聚宽账号：

```bash
export JQDATA_USER=your_username
export JQDATA_PASSWORD=your_password
python ./output/generated/my_new_strategy.py
```
