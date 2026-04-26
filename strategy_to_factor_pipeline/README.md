# 策略转因子流水线 (Strategy-to-Factor Pipeline)

将聚宽（JoinQuant）和 Backtrader 策略代码自动解析、提取因子信号，并生成标准化因子数据的完整流水线系统。

## 项目简介

本项目是一个量化策略因子提取流水线，能够：

- **自动扫描**指定目录下的策略文件（`.txt` / `.py`）
- **智能识别**策略类型（聚宽 / Backtrader）
- **深度解析**策略代码，提取选股条件、排序规则、调仓周期、持仓数量、因子/指标等
- **生成因子信号**并存储为 Parquet 格式
- **生成映射表**，建立策略与因子的可追溯对应关系
- **生成可运行代码**，将策略转换为独立的因子计算脚本

## 快速开始

### 环境要求

- Python 3.8+
- 依赖库：`pandas`, `pyarrow`, `openpyxl`

### 安装

```bash
pip install pandas pyarrow openpyxl
```

### 运行流水线

```python
from core.pipeline_orchestrator import PipelineOrchestrator, PipelineOrchestratorConfig

config = PipelineOrchestratorConfig(
    strategy_dir="./strategies",   # 策略文件目录
    output_dir="./output",         # 输出目录
    max_workers=4,                 # 并行工作数
)

pipeline = PipelineOrchestrator(config)
result = pipeline.run_full_pipeline()
```

### 单步骤运行

```python
# 仅扫描策略
pipeline.run_step("scan_strategies")

# 仅解析策略
pipeline.run_step("parse_strategies")
```

### 断点续传

```python
# 从最新检查点恢复
pipeline.resume_from_checkpoint()

# 从指定检查点恢复
pipeline.resume_from_checkpoint("./checkpoints/checkpoint_20240101_120000.json")
```

## 项目结构

```
strategy_to_factor_pipeline/
├── core/                          # 核心模块
│   ├── strategy_scanner.py        # 策略文件扫描与分类
│   ├── strategy_parser.py         # 策略代码解析器
│   ├── pipeline_orchestrator.py   # 流水线编排器
│   ├── mapping_generator.py       # 策略-因子映射表生成器
│   └── factor_database.py         # 因子数据存储（Parquet + SQLite）
├── templates/                     # 模板与代码生成
│   ├── strategy_template.py       # 因子计算脚本模板
│   └── code_generator.py          # 代码生成器
├── config/                        # 配置文件目录
├── output/                        # 输出目录
│   ├── factors/                   # 因子数据
│   └── mappings/                  # 映射表
├── scripts/                       # 运行脚本
├── tests/                         # 测试用例
└── utils/                         # 工具函数
```

## 使用方法

### 1. 扫描策略

```python
from core.strategy_scanner import StrategyScanner

scanner = StrategyScanner(
    strategy_dir="./strategies",
    cache_dir="./cache",
)

# 扫描所有策略
strategy_list = scanner.scan_all_strategies()

# 保存策略清单
scanner.save_strategy_list("./output/mappings/strategy_list.json")
```

### 2. 解析策略

```python
from core.strategy_parser import StrategyParser

parser = StrategyParser(output_dir="./output")

# 解析聚宽策略
jq_result = parser.parse_jq_strategy("./strategies/strategy.txt")

# 解析 Backtrader 策略
bt_result = parser.parse_backtrader_strategy("./strategies/strategy.py")

# 保存解析结果
parser.save_parsed_result(jq_result, "./output/parsed/strategy.json")
```

### 3. 生成映射表

```python
from core.mapping_generator import MappingGenerator

generator = MappingGenerator(output_dir="./output")

# 生成策略-因子映射
mapping_df = generator.generate_strategy_factor_mapping(strategy_list, parsed_results)

# 保存映射表
generator.save_mapping_table(mapping_df, "./output/mapping_table.csv")

# 导出 Excel（含多个 sheet）
generator.export_to_excel(
    output_path="./output/strategy_factor_mapping.xlsx",
    mapping_df=mapping_df,
    category_df=category_df,
)
```

### 4. 因子数据库操作

```python
from core.factor_database import FactorDatabase

db = FactorDatabase(
    db_path="./output/factors/metadata.db",
    data_dir="./output/factors/data",
)

# 保存因子信号
db.save_factor_signals("momentum_20", signals_df, metadata={...})

# 查询因子
df = db.load_factor_signals("momentum_20", date_range=("2023-01-01", "2023-12-31"))

# 横截面查询
cross_section = db.get_signals_cross_section("2023-06-01")

# 时序查询
time_series = db.get_signals_time_series("000001.XSHE")

# 因子组合
combined = db.get_factor_combination(["momentum_20", "volatility_20"])

# 因子相关性
corr = db.get_factor_correlation()

# 因子统计
stats = db.get_factor_stats("momentum_20")
```

### 5. 生成因子计算代码

```python
from templates.code_generator import CodeGenerator

generator = CodeGenerator(
    template_dir="./templates",
    output_dir="./output/strategies",
)

# 生成单个策略代码
generator.generate_strategy_code(
    strategy_name="小市值策略",
    parsed_rules={"universe": "399101.XSHE", "factors": ["circulating_market_cap"]},
    output_path="./output/strategies/small_cap.py",
)

# 批量生成
generator.generate_all_strategy_codes(strategy_list, parsed_results)
```

## 配置说明

### PipelineOrchestratorConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `strategy_dir` | str | `./strategies` | 策略文件目录 |
| `output_dir` | str | `./output` | 输出目录 |
| `checkpoint_dir` | str | `./checkpoints` | 检查点目录 |
| `max_workers` | int | 4 | 最大并行工作数 |
| `executor_type` | str | `process` | 执行器类型（process/thread） |
| `retry_count` | int | 1 | 失败重试次数 |
| `step_timeout` | int | 0 | 单步骤超时秒数（0=不限制） |

### 环境变量

| 变量 | 说明 |
|------|------|
| `JQDATA_USER` | 聚宽账号 |
| `JQDATA_PASSWORD` | 聚宽密码 |

## 流水线步骤

| 步骤 | 名称 | 说明 |
|------|------|------|
| 0 | `scan_strategies` | 扫描策略目录，收集所有策略文件 |
| 1 | `parse_strategies` | 解析策略文件，提取元信息 |
| 2 | `generate_signals` | 基于解析结果生成交易信号 |
| 3 | `store_factors` | 存储因子数据到 Parquet 文件 |
| 4 | `generate_mapping` | 生成策略到因子的映射表 |

## 常见问题

### Q: 支持哪些策略格式？

支持聚宽策略（`.txt`）和 Backtrader 策略（`.py`）。

### Q: 如何处理大量策略文件？

使用并行处理，配置 `max_workers` 和 `executor_type`。对于 I/O 密集型任务使用 `thread`，CPU 密集型使用 `process`。

### Q: 流水线中断后如何恢复？

系统自动保存检查点，使用 `resume_from_checkpoint()` 即可恢复。

### Q: 因子数据存储在什么格式？

因子信号数据使用 Parquet 格式（高效压缩），元数据使用 SQLite 存储。

### Q: 如何添加自定义因子类型？

参考 `docs/developer_guide.md` 中的扩展指南。
