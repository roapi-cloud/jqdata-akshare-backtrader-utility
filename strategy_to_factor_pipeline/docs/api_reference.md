# API 参考文档

## 目录

- [StrategyScanner](#strategyscanner)
- [StrategyParser](#strategyparser)
- [PipelineOrchestrator](#pipelineorchestrator)
- [PipelineOrchestratorConfig](#pipelineorchestratorconfig)
- [StepStatus](#stepstatus)
- [Checkpoint](#checkpoint)
- [ProgressTracker](#progresstracker)
- [MappingGenerator](#mappinggenerator)
- [FactorDatabase](#factordatabase)
- [CodeGenerator](#codegenerator)

---

## StrategyScanner

**模块**: `core.strategy_scanner`

策略文件扫描与分类模块。扫描指定目录下的所有策略文件，自动识别策略类型，提取策略元数据。

### 类定义

```python
class StrategyScanner(strategy_dir: str, cache_dir: str)
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `strategy_dir` | str | 策略文件目录路径 |
| `cache_dir` | str | 缓存目录路径 |

### 方法

#### `scan_all_strategies() -> List[Dict]`

扫描目录下所有策略文件并返回元数据列表。

**返回值**: 策略元数据列表，每个元素包含：
- `strategy_name`: 策略名称
- `file_path`: 文件路径
- `strategy_type`: 策略类型（joinquant/backtrader/other）
- `rebalance_cycle`: 调仓周期
- `stock_pool`: 股票池
- `author`: 作者
- `file_size_bytes`: 文件大小
- `line_count`: 代码行数

**示例**:

```python
scanner = StrategyScanner("./strategies", "./cache")
strategies = scanner.scan_all_strategies()
for s in strategies:
    print(f"{s['strategy_name']}: {s['strategy_type']}")
```

#### `get_strategy_metadata(file_path: str) -> Dict`

获取单个策略文件的元数据。

**参数**:
- `file_path`: 策略文件路径

**返回值**: 策略元数据字典

#### `save_strategy_list(output_path: str) -> Dict`

扫描并保存策略清单到 JSON 文件。

**参数**:
- `output_path`: 输出文件路径

**返回值**: 包含统计信息的字典

#### `load_cached_list() -> List[Dict]`

从缓存加载策略列表（如果文件未修改）。

**返回值**: 缓存的策略元数据列表

---

## StrategyParser

**模块**: `core.strategy_parser`

策略代码解析器。支持解析聚宽策略（.txt）和 Backtrader 策略（.py），提取策略逻辑并输出结构化结果。

### 类定义

```python
class StrategyParser(output_dir: str = "./output")
```

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_dir` | str | `./output` | 解析结果输出目录 |

### 方法

#### `parse_jq_strategy(file_path: str) -> Dict`

解析聚宽策略代码。

**参数**:
- `file_path`: 策略文件路径（.txt 或 .py）

**返回值**: 解析结果字典，包含：
- `strategy_type`: "joinquant"
- `stock_selection_rules`: 选股规则列表
- `rebalance_frequency`: 调仓周期
- `portfolio_size`: 持仓数量
- `weights_config`: 权重配置
- `factors_and_indicators`: 使用的因子和指标
- `global_variables`: 全局变量
- `trading_logic`: 交易逻辑
- `risk_control`: 风控逻辑

**示例**:

```python
parser = StrategyParser()
result = parser.parse_jq_strategy("./strategies/momentum.txt")
print(result["factors_and_indicators"]["technical_indicators"])
```

#### `parse_backtrader_strategy(file_path: str) -> Dict`

解析 Backtrader 策略代码。

**参数**:
- `file_path`: 策略文件路径（.py）

**返回值**: 解析结果字典，包含：
- `strategy_type`: "backtrader"
- `stock_selection_rules`: 选股规则
- `rebalance_frequency`: 调仓周期
- `portfolio_size`: 持仓数量
- `parameters`: 策略参数
- `factors_and_indicators`: 因子和指标
- `scoring_logic`: 评分逻辑
- `allocation_logic`: 仓位分配逻辑
- `timing_logic`: 择时逻辑
- `risk_control`: 风控逻辑

#### `extract_stock_selection_rules(content: str) -> List[Dict]`

从策略代码中提取选股规则。

**参数**:
- `content`: 策略代码内容字符串

**返回值**: 选股规则列表

#### `extract_rebalance_frequency(content: str) -> str`

提取调仓周期描述。

**返回值**: 调仓周期字符串，如 "daily", "weekly", "monthly"

#### `extract_portfolio_size(content: str) -> int`

提取持仓数量。

**返回值**: 持仓数量，未找到返回 0

#### `save_parsed_result(result: Dict, output_path: str) -> str`

保存解析结果到 JSON 文件。

**参数**:
- `result`: 解析结果字典
- `output_path`: 输出文件路径

**返回值**: 实际保存的文件路径

---

## PipelineOrchestrator

**模块**: `core.pipeline_orchestrator`

策略到因子生成流水线编排器。负责编排完整的策略扫描、解析、信号生成、因子存储和映射表生成流程。

### 类定义

```python
class PipelineOrchestrator(config: Optional[PipelineOrchestratorConfig] = None)
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | PipelineOrchestratorConfig | 流水线配置，可选 |

### 方法

#### `run_full_pipeline(start_from: int = 0) -> Dict[str, Any]`

运行完整流水线。

**参数**:
- `start_from`: 起始步骤索引（0-4）

**返回值**: 流水线运行结果字典，包含：
- `pipeline_id`: 流水线 ID
- `steps`: 各步骤状态
- `summary`: 汇总统计
- `failed_strategies`: 失败策略列表

**示例**:

```python
pipeline = PipelineOrchestrator(config)
result = pipeline.run_full_pipeline()
print(f"处理了 {result['summary']['total_strategies_processed']} 个策略")
```

#### `run_step(step_name: str) -> Dict[str, Any]`

运行单个步骤。

**参数**:
- `step_name`: 步骤名称，可选值：
  - `scan_strategies`
  - `parse_strategies`
  - `generate_signals`
  - `store_factors`
  - `generate_mapping`

**返回值**: 该步骤的运行结果

#### `get_pipeline_status() -> Dict[str, Any]`

获取流水线当前状态。

**返回值**: 状态字典，包含各步骤状态、进度和失败记录

#### `resume_from_checkpoint(checkpoint_path: Optional[str] = None) -> Dict[str, Any]`

从检查点恢复流水线。

**参数**:
- `checkpoint_path`: 检查点文件路径，未指定时使用最新检查点

**返回值**: 恢复后继续运行的结果

#### `run_parallel(items, worker_func, max_workers, step_name) -> Dict`

并行处理项目列表。

**参数**:
- `items`: 待处理项目列表
- `worker_func`: 工作函数
- `max_workers`: 最大并行数
- `step_name`: 步骤名称（用于日志）

**返回值**: 包含 successes, failures, results 的字典

#### `generate_summary_report() -> Dict[str, Any]`

生成汇总报告。

**返回值**: 汇总报告字典

---

## PipelineOrchestratorConfig

**模块**: `core.pipeline_orchestrator`

流水线编排器配置数据类。

### 属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `strategy_dir` | str | `./strategies` | 策略文件目录 |
| `output_dir` | str | `./output` | 输出目录 |
| `checkpoint_dir` | str | `./checkpoints` | 检查点目录 |
| `max_workers` | int | 4 | 最大并行工作数 |
| `executor_type` | str | `process` | 执行器类型（process/thread） |
| `retry_count` | int | 1 | 失败重试次数 |
| `step_timeout` | int | 0 | 单步骤超时秒数 |

---

## StepStatus

**模块**: `core.pipeline_orchestrator`

单个步骤的运行状态数据类。

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | str | 步骤名称 |
| `status` | str | 状态（pending/running/completed/failed/skipped） |
| `start_time` | float | 开始时间戳 |
| `end_time` | float | 结束时间戳 |
| `items_total` | int | 总项目数 |
| `items_completed` | int | 已完成项目数 |
| `items_failed` | int | 失败项目数 |
| `error` | str | 错误信息 |
| `details` | Dict | 附加详情 |

### 属性（只读）

- `duration`: 步骤耗时（秒）

### 方法

#### `to_dict() -> Dict[str, Any]`

转换为字典格式。

---

## Checkpoint

**模块**: `core.pipeline_orchestrator`

检查点数据类。

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `pipeline_id` | str | 流水线运行唯一标识 |
| `created_at` | str | 创建时间 |
| `updated_at` | str | 更新时间 |
| `current_step` | int | 当前步骤索引 |
| `step_statuses` | List[Dict] | 各步骤状态 |
| `results` | Dict | 已产出的结果 |
| `failed_strategies` | List[Dict] | 失败策略记录 |

### 方法

#### `to_dict() -> Dict[str, Any]`

转换为字典。

#### `from_dict(data: Dict) -> Checkpoint`

从字典创建 Checkpoint 实例（类方法）。

---

## ProgressTracker

**模块**: `core.pipeline_orchestrator`

进度追踪器，实时输出进度并估算剩余时间。

### 类定义

```python
class ProgressTracker(total_items: int, step_name: str = "")
```

### 方法

#### `update(completed: int = 0, failed: int = 0)`

更新进度。

#### `finish()`

标记进度完成。

---

## MappingGenerator

**模块**: `core.mapping_generator`

策略-因子映射表生成器。生成策略到因子的映射关系表、因子分类表和可追溯的对应关系。

### 类定义

```python
class MappingGenerator(output_dir: str = "./output")
```

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_dir` | str | `./output` | 输出目录 |

### 方法

#### `generate_strategy_factor_mapping(strategy_list, parsed_results) -> pd.DataFrame`

生成策略到因子的映射关系表。

**参数**:
- `strategy_list`: 策略列表
- `parsed_results`: 策略解析结果字典

**返回值**: 映射关系 DataFrame

#### `generate_factor_category_table(factor_metadata) -> pd.DataFrame`

生成因子分类表。

**参数**:
- `factor_metadata`: 因子元数据列表

**返回值**: 因子分类 DataFrame

#### `generate_traceability_map(strategy_name, parsed_result, factor_name) -> Dict`

生成可追溯的对应关系。

**参数**:
- `strategy_name`: 策略名称
- `parsed_result`: 策略解析结果
- `factor_name`: 因子名称

**返回值**: 追溯关系字典

#### `save_mapping_table(mapping_df, output_path) -> str`

保存映射表到 CSV。

**返回值**: 实际保存的文件路径

#### `save_traceability_report(output_path) -> str`

保存追溯报告到 JSON。

**返回值**: 实际保存的文件路径

#### `export_to_excel(output_path, mapping_df, category_df) -> str`

导出到 Excel，包含多个 sheet（策略因子映射、因子分类、追溯关系、汇总）。

**返回值**: 实际保存的文件路径

---

## FactorDatabase

**模块**: `core.factor_database`

因子数据库管理类。使用 Parquet 文件存储因子信号数据，SQLite 存储元数据。

### 类定义

```python
class FactorDatabase(db_path: str, data_dir: str)
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `db_path` | str | SQLite 元数据数据库路径 |
| `data_dir` | str | Parquet 数据存储目录 |

### 方法

#### `save_factor_signals(factor_name, signals_df, metadata) -> None`

保存因子信号数据。

**参数**:
- `factor_name`: 因子名称
- `signals_df`: 信号数据 DataFrame（需包含 date, stock_code, signal 列）
- `metadata`: 因子元数据字典（factor_type, strategy_source, params, description）

#### `load_factor_signals(factor_name, date_range, stock_list) -> pd.DataFrame`

加载因子信号数据。

**参数**:
- `factor_name`: 因子名称
- `date_range`: 日期范围 (start_date, end_date)
- `stock_list`: 股票代码列表

**返回值**: 因子信号 DataFrame

#### `get_factor_metadata(factor_name: str) -> Dict`

获取因子元数据。

**返回值**: 因子元数据字典

#### `list_all_factors() -> List[Dict]`

列出所有因子。

**返回值**: 因子元数据列表

#### `get_signals_cross_section(date, factor_names) -> pd.DataFrame`

获取某日期所有股票的横截面信号。

**参数**:
- `date`: 查询日期
- `factor_names`: 因子名称列表，None 表示所有因子

**返回值**: DataFrame，index=stock_code, columns=factor_names

#### `get_signals_time_series(stock_code, factor_names, date_range) -> pd.DataFrame`

获取某股票在所有策略中的时序信号。

**参数**:
- `stock_code`: 股票代码
- `factor_names`: 因子名称列表
- `date_range`: 日期范围

**返回值**: DataFrame，index=date, columns=factor_names

#### `update_factor(factor_name, new_signals_df) -> None`

增量更新因子数据。

#### `delete_factor(factor_name: str) -> None`

删除因子及其数据。

#### `get_factor_combination(factor_names, weights, date_range, stock_list) -> pd.DataFrame`

获取因子组合信号。

**参数**:
- `factor_names`: 因子名称列表
- `weights`: 因子权重字典，None 表示等权
- `date_range`: 日期范围
- `stock_list`: 股票代码列表

**返回值**: 包含各因子信号及组合信号的 DataFrame

#### `get_factor_correlation(factor_names, date_range) -> pd.DataFrame`

计算因子间相关性矩阵。

**返回值**: 相关性矩阵 DataFrame

#### `get_factor_stats(factor_name, date_range) -> Dict`

获取因子统计信息。

**返回值**: 统计信息字典（count, mean, std, min, max, median 等）

---

## CodeGenerator

**模块**: `templates.code_generator`

策略转因子代码生成器。根据解析后的策略规则，生成可独立运行的因子计算 Python 脚本。

### 类定义

```python
class CodeGenerator(template_dir: str, output_dir: str)
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `template_dir` | str | 模板文件目录路径 |
| `output_dir` | str | 生成代码的输出目录路径 |

### 方法

#### `load_template(template_name: str) -> str`

加载模板文件。

**参数**:
- `template_name`: 模板文件名

**返回值**: 模板内容字符串

#### `fill_template(template, strategy_info, rules) -> str`

填充模板占位符。

**参数**:
- `template`: 模板内容字符串
- `strategy_info`: 策略基本信息（name, desc, source_file）
- `rules`: 解析后的策略规则

**返回值**: 填充后的代码字符串

#### `generate_strategy_code(strategy_name, parsed_rules, output_path) -> str`

为单个策略生成因子计算代码。

**参数**:
- `strategy_name`: 策略名称
- `parsed_rules`: 解析后的策略规则字典
- `output_path`: 输出文件路径（可选）

**返回值**: 生成的代码文件路径

**示例**:

```python
generator = CodeGenerator("./templates", "./output/generated")
path = generator.generate_strategy_code(
    strategy_name="小市值策略",
    parsed_rules={
        "data_source": "jqdata",
        "universe": "399101.XSHE",
        "factors": ["circulating_market_cap"],
    },
)
```

#### `generate_all_strategy_codes(strategy_list, parsed_results, output_dir) -> List[str]`

批量生成所有策略的代码。

**参数**:
- `strategy_list`: 策略列表
- `parsed_results`: 解析结果字典
- `output_dir`: 输出目录

**返回值**: 生成的代码文件路径列表

#### `validate_generated_code(code: str) -> bool`

验证生成的代码是否合法。

**检查项**:
1. Python 语法是否正确
2. 是否还有未替换的占位符
3. 是否包含必要的类和函数

**返回值**: True 表示验证通过

#### `generate_batch_script(strategy_list, output_path) -> str`

生成批量运行脚本。

**返回值**: 批量运行脚本的文件路径

#### `get_generation_report() -> Dict`

获取代码生成报告。

**返回值**: 包含生成统计信息的字典

#### `save_generation_report(output_path) -> str`

保存代码生成报告。

**返回值**: 报告文件路径
