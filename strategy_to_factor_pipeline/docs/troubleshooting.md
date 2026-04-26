# 常见问题与故障排查

## 目录

- [常见问题解答](#常见问题解答)
- [错误排查指南](#错误排查指南)
- [性能优化建议](#性能优化建议)

---

## 常见问题解答

### Q1: 流水线运行失败怎么办？

**A**: 按以下步骤排查：

1. 查看流水线状态：
```python
status = pipeline.get_pipeline_status()
for step, info in status["steps"].items():
    if info["status"] == "failed":
        print(f"失败步骤: {step}")
        print(f"错误信息: {info['error']}")
```

2. 查看失败策略列表：
```python
for failure in status["failed_strategies"]:
    print(f"策略: {failure['item']}")
    print(f"错误: {failure['error']}")
```

3. 从检查点恢复：
```python
pipeline.resume_from_checkpoint()
```

### Q2: 策略扫描不到任何文件？

**A**: 检查以下几点：

1. 确认策略目录路径正确：
```python
import os
print(os.path.exists("./strategies"))  # 应为 True
```

2. 确认文件扩展名为 `.txt` 或 `.py`：
```python
from pathlib import Path
files = list(Path("./strategies").rglob("*.txt"))
files += list(Path("./strategies").rglob("*.py"))
print(f"找到 {len(files)} 个文件")
```

3. 确认文件名不以 `_` 开头（会被过滤）

### Q3: 解析结果为空或不完整？

**A**: 可能的原因：

1. 策略代码格式不符合预期模式
2. 策略使用了非标准的函数名或变量名
3. 策略代码有语法错误

**解决方法**：
```python
parser = StrategyParser()
result = parser.parse_jq_strategy("./strategy.txt")

# 查看原始代码片段
print(result.get("raw_code_snippets", {}))

# 查看提取的因子
print(result.get("factors_and_indicators", {}))
```

### Q4: 因子数据库查询报错 "因子不存在"？

**A**: 确认因子名称正确：

```python
# 列出所有因子
factors = db.list_all_factors()
print([f["factor_name"] for f in factors])

# 检查因子名称是否匹配
```

### Q5: 生成的因子计算脚本运行失败？

**A**: 检查以下几点：

1. 确认数据源配置正确：
```python
# 如果使用聚宽，需要设置环境变量
export JQDATA_USER=your_username
export JQDATA_PASSWORD=your_password
```

2. 确认依赖库已安装：
```bash
pip install jqdatasdk  # 聚宽
pip install akshare    # AkShare
pip install pandas numpy pyarrow
```

3. 查看生成的代码是否有语法错误：
```python
from templates.code_generator import CodeGenerator
generator = CodeGenerator("./templates", "./output")
with open("./output/strategy.py", "r") as f:
    code = f.read()
valid = generator.validate_generated_code(code)
print(f"代码验证: {'通过' if valid else '失败'}")
```

### Q6: 如何处理非标准策略格式？

**A**: 可以自定义解析规则：

```python
from core.strategy_parser import StrategyParser
import re

class CustomParser(StrategyParser):
    def __init__(self, output_dir="./output"):
        super().__init__(output_dir)
        # 添加自定义模式
        self.CUSTOM_PATTERNS = [
            re.compile(r"custom_pattern"),
        ]

    def parse_jq_strategy(self, file_path):
        result = super().parse_jq_strategy(file_path)
        # 添加自定义解析逻辑
        with open(file_path, "r") as f:
            content = f.read()
        result["custom_field"] = self._extract_custom_field(content)
        return result
```

### Q7: 并行处理时出现内存不足？

**A**: 减少并行工作数：

```python
config = PipelineOrchestratorConfig(
    max_workers=2,  # 减少并行数
    executor_type="thread",  # 线程池比进程池内存占用小
)
```

### Q8: 如何清理缓存和临时文件？

**A**:

```python
import shutil
from pathlib import Path

# 清理缓存
shutil.rmtree("./cache", ignore_errors=True)

# 清理检查点
shutil.rmtree("./checkpoints", ignore_errors=True)

# 清理临时数据
for f in Path("./output").rglob("*.tmp"):
    f.unlink()
```

---

## 错误排查指南

### 常见错误及解决方案

#### 错误 1: `FileNotFoundError: No checkpoint found to resume from`

**原因**: 没有可用的检查点文件

**解决**:
```python
# 从头开始运行
pipeline = PipelineOrchestrator(config)
result = pipeline.run_full_pipeline(start_from=0)
```

#### 错误 2: `ValueError: Unknown step: xxx`

**原因**: 步骤名称不正确

**解决**: 使用有效的步骤名称：
```python
valid_steps = ["scan_strategies", "parse_strategies", "generate_signals",
               "store_factors", "generate_mapping"]
```

#### 错误 3: `ModuleNotFoundError: No module named 'jqdatasdk'`

**原因**: 未安装聚宽 SDK

**解决**:
```bash
pip install jqdatasdk
```

#### 错误 4: `ValueError: DataFrame 必须包含列: {'date', 'stock_code', 'signal'}`

**原因**: 因子数据格式不正确

**解决**: 确保 DataFrame 包含必需的列：
```python
df = df.rename(columns={
    "datetime": "date",
    "code": "stock_code",
    "value": "signal",
})
```

#### 错误 5: `JSONDecodeError`

**原因**: JSON 文件格式错误或损坏

**解决**:
```python
import json

# 检查 JSON 文件
with open("./output/parsed/strategy.json", "r") as f:
    try:
        data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        # 可能需要重新生成该文件
```

#### 错误 6: `sqlite3.OperationalError`

**原因**: SQLite 数据库文件损坏或权限问题

**解决**:
```python
# 删除并重建数据库
import os
if os.path.exists("./output/factors/metadata.db"):
    os.remove("./output/factors/metadata.db")

db = FactorDatabase("./output/factors/metadata.db", "./output/factors/data")
```

#### 错误 7: 策略解析结果中 `factors_and_indicators` 为空

**原因**: 策略代码中使用的因子不在预定义的模式列表中

**解决**: 查看 `strategy_parser.py` 中的 `JQ_TECH_INDICATORS` 和 `JQ_FUNDAMENTAL_FIELDS` 列表，添加缺失的因子名称。

### 日志配置

启用详细日志以排查问题：

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,  # 最详细的日志级别
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# 或者只启用特定模块的调试日志
logging.getLogger("core.pipeline_orchestrator").setLevel(logging.DEBUG)
logging.getLogger("core.strategy_parser").setLevel(logging.DEBUG)
```

### 调试模式

```python
# 单步执行流水线
pipeline = PipelineOrchestrator(config)

# 逐步运行每个步骤
for step in ["scan_strategies", "parse_strategies", "generate_signals",
             "store_factors", "generate_mapping"]:
    print(f"运行步骤: {step}")
    try:
        result = pipeline.run_step(step)
        print(f"  成功: {result.get('success_count', 0)}")
    except Exception as e:
        print(f"  失败: {e}")
        break
```

---

## 性能优化建议

### 1. 选择合适的并行策略

| 场景 | executor_type | max_workers |
|------|---------------|-------------|
| CPU 密集型（解析、计算） | `process` | CPU 核心数 |
| I/O 密集型（文件读写、网络请求） | `thread` | CPU 核心数 × 2~4 |
| 混合负载 | `process` | CPU 核心数 / 2 |

```python
import multiprocessing

cpu_count = multiprocessing.cpu_count()

# CPU 密集型
config = PipelineOrchestratorConfig(
    max_workers=cpu_count,
    executor_type="process",
)

# I/O 密集型
config = PipelineOrchestratorConfig(
    max_workers=cpu_count * 2,
    executor_type="thread",
)
```

### 2. 使用缓存加速重复扫描

```python
scanner = StrategyScanner("./strategies", "./cache")

# 首次扫描
strategies = scanner.scan_all_strategies()

# 后续扫描（只处理修改过的文件）
strategies = scanner.scan_all_strategies()

# 或者直接从缓存加载
cached = scanner.load_cached_list()
```

### 3. 批量处理减少 I/O

```python
# 不推荐：逐个保存
for factor_name, df in factors.items():
    db.save_factor_signals(factor_name, df)

# 推荐：批量保存（如果支持）
batch_data = [(name, df) for name, df in factors.items()]
# 实现批量保存逻辑
```

### 4. 优化 Parquet 写入

```python
import pyarrow.parquet as pq
import pyarrow as pa

# 使用合适的压缩算法
# Snappy: 速度快，压缩率一般
# ZSTD: 速度中等，压缩率高
# GZIP: 速度慢，压缩率高

pq.write_table(table, file_path, compression="snappy")

# 对于大文件，使用分块写入
pq.write_to_dataset(table, root_path="./data/factor_name/")
```

### 5. 减少内存占用

```python
# 使用合适的数据类型
df = df.astype({
    "stock_code": "category",    # 字符串用 category
    "signal": "float32",         # 不需要 float64 精度
    "date": "datetime64[ns]",    # 确保日期类型正确
})

# 及时释放内存
del intermediate_result
import gc
gc.collect()
```

### 6. 设置合理的超时时间

```python
config = PipelineOrchestratorConfig(
    step_timeout=3600,  # 1 小时超时
)
```

### 7. 使用检查点避免重复计算

```python
# 每次运行后自动保存检查点
pipeline.run_full_pipeline()

# 中断后从检查点恢复，避免重复计算
pipeline.resume_from_checkpoint()
```

### 8. 数据库查询优化

```python
# 使用索引加速查询（SQLite）
import sqlite3

conn = sqlite3.connect("./metadata.db")
cursor = conn.cursor()

# 创建索引
cursor.execute("CREATE INDEX IF NOT EXISTS idx_factor_type ON factor_metadata(factor_type)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategy_source ON factor_metadata(strategy_source)")
conn.commit()
conn.close()
```

### 9. 监控流水线性能

```python
import time

start = time.time()
result = pipeline.run_full_pipeline()
elapsed = time.time() - start

print(f"总耗时: {elapsed:.1f}s")
print(f"处理策略数: {result['summary']['total_strategies_processed']}")
print(f"平均每个策略: {elapsed / max(result['summary']['total_strategies_processed'], 1):.2f}s")

# 查看各步骤耗时
for step_name, step_info in result["steps"].items():
    if step_info.get("duration"):
        print(f"  {step_name}: {step_info['duration']:.1f}s")
```

### 10. 硬件建议

| 策略数量 | 推荐配置 |
|----------|----------|
| < 100 | 4 核 CPU, 8GB 内存 |
| 100-500 | 8 核 CPU, 16GB 内存 |
| 500-1000 | 16 核 CPU, 32GB 内存 |
| > 1000 | 32 核 CPU, 64GB+ 内存, SSD 存储 |
