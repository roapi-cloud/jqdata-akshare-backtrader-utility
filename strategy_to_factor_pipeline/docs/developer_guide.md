# 开发者指南

## 目录

- [系统架构概览](#系统架构概览)
- [如何扩展系统](#如何扩展系统)
- [如何添加新的因子类型](#如何添加新的因子类型)
- [如何优化性能](#如何优化性能)
- [如何添加新的数据源](#如何添加新的数据源)
- [如何编写测试](#如何编写测试)

---

## 系统架构概览

### 核心模块关系

```
┌─────────────────────────────────────────────────────────────┐
│                    PipelineOrchestrator                      │
│  (流水线编排器 - 协调所有步骤)                                │
├─────────┬───────────┬──────────────┬────────────┬───────────┤
│  Step 0 │  Step 1   │   Step 2     │   Step 3   │  Step 4   │
│ 扫描    │ 解析      │ 信号生成     │ 因子存储   │ 映射生成  │
│ Scanner │ Parser    │ (可扩展)     │ Database   │ Generator │
└─────────┴───────────┴──────────────┴────────────┴───────────┘
                              │
                    ┌─────────┴─────────┐
                    │   CodeGenerator    │
                    │  (代码生成器)       │
                    └───────────────────┘
```

### 数据流

```
策略文件 (.txt/.py)
    │
    ▼
StrategyScanner → 策略清单 JSON
    │
    ▼
StrategyParser → 解析结果 JSON
    │
    ▼
Signal Generator → 因子信号 DataFrame
    │
    ▼
FactorDatabase → Parquet 文件 + SQLite 元数据
    │
    ▼
MappingGenerator → 映射表 CSV/Excel
```

---

## 如何扩展系统

### 添加新的流水线步骤

1. 在 `pipeline_orchestrator.py` 中的 `PIPELINE_STEPS` 列表添加新步骤名称：

```python
PIPELINE_STEPS = [
    "scan_strategies",
    "parse_strategies",
    "generate_signals",
    "store_factors",
    "generate_mapping",
    "validate_results",  # 新增步骤
]
```

2. 实现对应的 `_step_` 方法：

```python
def _step_validate_results(self) -> Dict[str, Any]:
    """验证流水线产出结果。"""
    factors_dir = Path(self.config.output_dir) / "factors"
    factor_files = list(factors_dir.glob("*.parquet"))

    valid_count = 0
    invalid_files = []

    for f in factor_files:
        try:
            df = pd.read_parquet(f)
            if "date" in df.columns and "signal" in df.columns:
                valid_count += 1
            else:
                invalid_files.append(str(f))
        except Exception:
            invalid_files.append(str(f))

    return {
        "successes": list(range(valid_count)),
        "failures": invalid_files,
        "results": {"valid": valid_count, "invalid": len(invalid_files)},
        "total": len(factor_files),
        "success_count": valid_count,
        "failure_count": len(invalid_files),
    }
```

### 添加新的策略解析规则

在 `strategy_parser.py` 中添加新的正则模式：

```python
class StrategyParser:
    # 添加新的模式
    NEW_PATTERN = [
        re.compile(r"your_regex_pattern"),
    ]

    def _extract_new_feature(self, content: str) -> List[Dict]:
        """提取新功能"""
        results = []
        for match in self.NEW_PATTERN.finditer(content):
            results.append({
                "type": "new_feature",
                "value": match.group(1),
                "line_number": content[:match.start()].count("\n") + 1,
            })
        return results
```

### 自定义策略扫描器

继承 `StrategyScanner` 并覆盖方法：

```python
from core.strategy_scanner import StrategyScanner

class CustomScanner(StrategyScanner):
    def __init__(self, strategy_dir, cache_dir, custom_patterns=None):
        super().__init__(strategy_dir, cache_dir)
        self.custom_patterns = custom_patterns or []

    def _detect_strategy_type(self, content: str) -> str:
        # 调用父类方法
        base_type = super()._detect_strategy_type(content)

        # 添加自定义检测逻辑
        for pattern, strategy_type in self.custom_patterns:
            if pattern.search(content):
                return strategy_type

        return base_type
```

---

## 如何添加新的因子类型

### 方法一：在模板中添加因子计算逻辑

修改 `templates/strategy_template.py` 中的 `FactorEngine` 类：

```python
class FactorEngine:
    def _calculate_signals(self, stocks, price_data, fundamental_data):
        # ... 现有代码 ...

        for stock in stocks:
            df = price_data[stock].copy()

            # 添加新的因子计算
            df["new_factor"] = self._calc_new_factor(df)

            # ... 现有代码 ...

    def _calc_new_factor(self, df: pd.DataFrame) -> pd.Series:
        """计算新因子"""
        # 示例：计算价格变化率因子
        return df["close"].pct_change(5) / df["close"].pct_change(20)
```

### 方法二：扩展 DataLoader

在 `DataLoader` 类中添加新的数据获取方法：

```python
class DataLoader:
    def get_new_data_source(self, symbols, **kwargs):
        """获取新的数据源"""
        if self.source == "jqdata":
            # 聚宽数据获取逻辑
            pass
        elif self.source == "akshare":
            # AkShare 数据获取逻辑
            pass
```

### 方法三：在因子数据库中添加因子类型标记

```python
from core.factor_database import FactorDatabase

db = FactorDatabase("./metadata.db", "./data")

# 保存因子时指定类型
db.save_factor_signals(
    factor_name="custom_factor",
    signals_df=signals_df,
    metadata={
        "factor_type": "custom",  # 自定义因子类型
        "strategy_source": "my_strategy",
        "params": {"param1": 10, "param2": 20},
        "description": "自定义因子描述",
    },
)
```

### 因子类型分类建议

| 类型 | 说明 | 示例 |
|------|------|------|
| `technical` | 技术指标因子 | MA, MACD, RSI, BOLL |
| `fundamental` | 基本面因子 | PE, PB, ROE, 营收增长 |
| `momentum` | 动量因子 | 5日动量, 20日动量 |
| `volatility` | 波动率因子 | 20日波动率, ATR |
| `volume` | 成交量因子 | OBV, 量比 |
| `sentiment` | 情绪因子 | 换手率, 资金流向 |
| `custom` | 自定义因子 | 策略特有因子 |

---

## 如何优化性能

### 1. 并行处理优化

```python
# CPU 密集型任务使用进程池
config = PipelineOrchestratorConfig(
    max_workers=8,
    executor_type="process",  # 适合 CPU 密集型
)

# I/O 密集型任务使用线程池
config = PipelineOrchestratorConfig(
    max_workers=16,
    executor_type="thread",  # 适合 I/O 密集型
)
```

### 2. 缓存优化

策略扫描器内置 MD5 缓存机制：

```python
scanner = StrategyScanner("./strategies", "./cache")

# 首次扫描会计算文件哈希并缓存
strategies = scanner.scan_all_strategies()

# 后续扫描只处理修改过的文件
strategies = scanner.scan_all_strategies()  # 速度更快
```

### 3. Parquet 压缩优化

因子数据库使用 Snappy 压缩，可以自定义压缩算法：

```python
import pyarrow.parquet as pq

# 使用 ZSTD 压缩（更高压缩率）
pq.write_table(table, factor_file, compression="zstd")

# 使用 GZIP 压缩
pq.write_table(table, factor_file, compression="gzip")
```

### 4. 数据库查询优化

```python
# 使用日期范围过滤减少数据加载量
df = db.load_factor_signals(
    "momentum_20",
    date_range=("2023-01-01", "2023-06-30"),  # 只加载需要的日期
)

# 使用股票列表过滤
df = db.load_factor_signals(
    "momentum_20",
    stock_list=["000001.XSHE", "000002.XSHE"],  # 只加载需要的股票
)
```

### 5. 分块处理大数据

```python
def process_large_dataset(stocks, chunk_size=100):
    """分块处理大量股票"""
    for i in range(0, len(stocks), chunk_size):
        chunk = stocks[i:i + chunk_size]
        # 处理当前块
        process_chunk(chunk)
```

### 6. 内存优化

```python
# 使用合适的数据类型减少内存占用
df = df.astype({
    "stock_code": "category",
    "signal": "float32",
})

# 及时释放不需要的变量
del large_variable
import gc
gc.collect()
```

### 7. 超时控制

```python
config = PipelineOrchestratorConfig(
    step_timeout=3600,  # 单步骤超时 1 小时
)
```

---

## 如何添加新的数据源

### 1. 在 DataLoader 中添加新数据源

```python
class DataLoader:
    def __init__(self, source: str = "jqdata", cache_dir: str = ".data_cache"):
        self.source = source
        # ...

        if source == "jqdata":
            self._init_jqdata()
        elif source == "akshare":
            self._init_akshare()
        elif source == "tushare":
            self._init_tushare()  # 新增
        else:
            raise ValueError(f"不支持的数据源: {source}")

    def _init_tushare(self):
        """初始化 Tushare"""
        import tushare as ts
        token = os.environ.get("TUSHARE_TOKEN", "")
        ts.set_token(token)
        self._pro = ts.pro_api()
```

### 2. 实现数据获取方法

```python
class DataLoader:
    def get_price(self, symbols, start_date, end_date, frequency="daily", fields=None):
        # ... 现有代码 ...

        elif self.source == "tushare":
            for sym in symbols:
                clean_code = sym.split(".")[0]
                df = self._pro.daily(
                    ts_code=clean_code,
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                )
                # 转换为统一格式
                # ...
```

---

## 如何编写测试

### 测试目录结构

```
tests/
├── test_strategy_scanner.py
├── test_strategy_parser.py
├── test_pipeline_orchestrator.py
├── test_mapping_generator.py
├── test_factor_database.py
└── test_code_generator.py
```

### 测试示例

```python
import unittest
import tempfile
import os
from core.strategy_parser import StrategyParser

class TestStrategyParser(unittest.TestCase):
    def setUp(self):
        self.parser = StrategyParser(output_dir=tempfile.mkdtemp())

    def test_parse_jq_strategy(self):
        """测试聚宽策略解析"""
        test_content = """
def initialize(context):
    g.stock_num = 10
    set_benchmark('000300.XSHG')

def handle_data(context, data):
    q = query(valuation.code).filter(
        valuation.pe_ratio < 30
    ).limit(g.stock_num)
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            f.flush()
            result = self.parser.parse_jq_strategy(f.name)

        self.assertEqual(result["strategy_type"], "joinquant")
        self.assertEqual(result["portfolio_size"], 10)
        os.unlink(f.name)

    def test_extract_rebalance_frequency(self):
        """测试调仓周期提取"""
        content = "run_daily(my_trade, time='09:30')"
        freq = self.parser.extract_rebalance_frequency(content)
        self.assertIn("daily", freq)

if __name__ == "__main__":
    unittest.main()
```

### 运行测试

```bash
python -m pytest tests/ -v
```

---

## 代码规范

### 命名约定

- 类名：`PascalCase`（如 `StrategyParser`）
- 函数/方法：`snake_case`（如 `parse_jq_strategy`）
- 常量：`UPPER_SNAKE_CASE`（如 `PIPELINE_STEPS`）
- 私有方法：前缀 `_`（如 `_extract_meta`）

### 文档字符串

所有公共方法都应包含文档字符串：

```python
def method_name(self, param1: str, param2: int) -> Dict:
    """方法简要描述。

    Args:
        param1: 参数1说明
        param2: 参数2说明

    Returns:
        返回值说明

    Raises:
        ValueError: 异常说明
    """
```

### 类型注解

所有方法签名都应包含类型注解：

```python
def parse_jq_strategy(self, file_path: str) -> Dict:
    ...
```
