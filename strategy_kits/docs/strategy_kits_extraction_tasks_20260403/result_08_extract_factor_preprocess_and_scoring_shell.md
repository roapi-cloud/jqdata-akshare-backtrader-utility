# 任务 08：因子预处理与打分壳抽取结果

## 1. 目标归宿

所有骨架文件最终写入：`/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/signals/factor_preprocess/`

## 2. 第一版保留的预处理步骤

基于聚宽侧 (`backtest_framework.py:FactorProcessor`) 和 ML Pipeline 侧 (`ml/preprocessing.py:FeaturePreprocessor`) 的实现，第一版保留以下核心步骤：

| 步骤 | 函数名 | 来源 | 说明 |
|------|--------|------|------|
| 缺失值填充 | `fill_missing_by_group` | JoinQuant + ML | 支持按组（行业/板块）填充，避免跨组污染 |
| 去极值 | `winsorize_features` | JoinQuant | 支持 MAD 和 分位数 两种方法 |
| 标准化 | `standardize_features` | JoinQuant + ML | Z-score 标准化，支持按组中性化 |
| 打分合成 | `build_score_frame` | QuantsPlaybook | 多因子打分，支持多种加权方式 |

### 预处理流程图

```
原始因子表 (raw_df)
    │
    ▼
┌─────────────────┐
│ fill_missing    │ ◄── 按行业/板块分组填充
│ _by_group       │     (mean/median/zero)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ winsorize       │ ◄── 去极值
│ _features       │     (MAD / quantile clip)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ standardize     │ ◄── Z-score 标准化
│ _features       │     (可选: 行业中性化)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ build_score     │ ◄── 多因子打分合成
│ _frame          │     (equal/ic/icir/pca)
└─────────────────┘
    │
    ▼
score_df (含 score 列)
```

## 3. 打分壳最小接口

### 3.1 核心函数签名

```python
# ============ 预处理函数 ============

def fill_missing_by_group(
    df: pd.DataFrame,
    factor_cols: List[str],
    group_col: Optional[str] = None,
    method: Literal["mean", "median", "zero"] = "median"
) -> pd.DataFrame:
    """
    按组填充缺失值

    Args:
        df: 输入数据框，需包含 factor_cols 和 group_col
        factor_cols: 需要填充的因子列名列表
        group_col: 分组列名（如 'industry'），None 表示整体填充
        method: 填充方法

    Returns:
        填充后的数据框
    """


def winsorize_features(
    df: pd.DataFrame,
    factor_cols: List[str],
    method: Literal["mad", "quantile"] = "mad",
    n_mad: float = 3.0,
    quantile_limits: Tuple[float, float] = (0.01, 0.99)
) -> pd.DataFrame:
    """
    去极值处理

    Args:
        df: 输入数据框
        factor_cols: 需要去极值的因子列名列表
        method: "mad" 使用 MAD 方法，"quantile" 使用分位数裁剪
        n_mad: MAD 方法的倍数（默认 3）
        quantile_limits: 分位数方法的上下限

    Returns:
        去极值后的数据框
    """


def standardize_features(
    df: pd.DataFrame,
    factor_cols: List[str],
    group_col: Optional[str] = None,
    method: Literal["zscore", "rank"] = "zscore"
) -> pd.DataFrame:
    """
    标准化处理

    Args:
        df: 输入数据框
        factor_cols: 需要标准化的因子列名列表
        group_col: 分组列名，None 表示整体标准化
        method: "zscore" 使用 Z-score，"rank" 使用排名标准化

    Returns:
        标准化后的数据框
    """


# ============ 打分函数 ============

def build_score_frame(
    df: pd.DataFrame,
    factor_cols: List[str],
    method: Literal["equal", "ic", "icir", "pca"] = "equal",
    weights: Optional[Dict[str, float]] = None,
    direction: Union[Literal["ascending", "descending"], Dict[str, str]] = "ascending",
    ic_window: int = 5,
    ret_col: Optional[str] = None,
) -> pd.DataFrame:
    """
    多因子打分合成

    Args:
        df: 输入数据框，MultiIndex [date, code] 或普通 DataFrame
        factor_cols: 参与打分的因子列名列表
        method: 打分方法 (equal=等权, ic=IC加权, icir=ICIR加权, pca=PCA)
        weights: 自定义权重字典，method="custom" 时使用
        direction: 因子方向，"ascending" 表示因子值越大分数越高
                  或传入字典为每个因子单独指定方向
        ic_window: IC/IR 计算窗口（仅对 ic/icir 方法有效）
        ret_col: 收益率列名（用于 IC/IR 计算，仅对 ic/icir 方法有效）

    Returns:
        含 'score' 列的数据框
    """
```

### 3.2 配置类

```python
@dataclass
class PreprocessConfig:
    """预处理配置"""
    fill_method: Literal["mean", "median", "zero"] = "median"
    fill_group_col: Optional[str] = "industry"  # None 表示不按组
    winsorize_method: Literal["mad", "quantile"] = "mad"
    winsorize_n: float = 3.0
    standardize_method: Literal["zscore", "rank"] = "zscore"
    standardize_group_col: Optional[str] = None


@dataclass
class ScoreConfig:
    """打分配置"""
    method: Literal["equal", "ic", "icir", "pca", "custom"] = "equal"
    weights: Optional[Dict[str, float]] = None
    direction: Union[str, Dict[str, str]] = "ascending"
    ic_window: int = 5
    rank_first: bool = True  # 打分前是否先转秩
```

## 4. 目标文件拆分建议

```
strategy_kits/signals/factor_preprocess/
├── __init__.py              # 导出核心接口
├── config.py                # 配置类 (PreprocessConfig, ScoreConfig)
├── cleaners.py              # 缺失值填充 (fill_missing_by_group)
├── transformers.py          # 去极值 + 标准化 (winsorize_features, standardize_features)
├── scoring.py               # 打分合成 (build_score_frame)
└── pipeline.py              # 流水线编排 (FactorPreprocessPipeline)
```

## 5. 已补骨架文件

以下文件已创建：

- `/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/signals/factor_preprocess/__init__.py`
- `/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/signals/factor_preprocess/config.py`
- `/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/signals/factor_preprocess/cleaners.py`
- `/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/signals/factor_preprocess/transformers.py`
- `/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/signals/factor_preprocess/scoring.py`
- `/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/signals/factor_preprocess/pipeline.py`

## 6. 不该抽的内容（边界清晰）

| 类型 | 不该抽的内容 | 归属 |
|------|-------------|------|
| 策略专属 | 具体因子列表 (如 ROE、PE、PB) | 各策略自行定义 |
| 策略专属 | 因子方向字典 | 各策略配置文件 |
| 模型专属 | 超参数 (如 n_mad=3 vs 3.5) | 策略或调参模块 |
| 模型专属 | 标签定义 (next_ret 计算方式) | 标签构建模块 |
| 数据专属 | 原始数据获取逻辑 | data_fetcher 模块 |

## 7. 通过门槛验证

### 7.1 快速使用示例

```python
from strategy_kits.signals.factor_preprocess import (
    FactorPreprocessPipeline,
    PreprocessConfig,
    ScoreConfig
)

# 假设已有原始因子表 raw_df (含 date, code, factor1, factor2, ...)

# 方式1: 使用 Pipeline 一步到位
config = PreprocessConfig(
    fill_method="median",
    winsorize_method="mad",
    standardize_method="zscore"
)
score_config = ScoreConfig(method="equal")

pipeline = FactorPreprocessPipeline(
    factor_cols=["factor1", "factor2", "factor3"],
    preprocess_config=config,
    score_config=score_config
)

score_df = pipeline.fit_transform(raw_df)
# score_df 含原始列 + 'score' 列

# 方式2: 分步调用
from strategy_kits.signals.factor_preprocess import (
    fill_missing_by_group,
    winsorize_features,
    standardize_features,
    build_score_frame
)

df = fill_missing_by_group(raw_df, ["f1", "f2"], group_col="industry")
df = winsorize_features(df, ["f1", "f2"])
df = standardize_features(df, ["f1", "f2"])
score_df = build_score_frame(df, ["f1", "f2"], method="equal")
```

### 7.2 扩展新打分方法

```python
# 在 scoring.py 中注册新方法
from .scoring import register_scoring_method

@register_scoring_method("my_method")
def my_custom_score(df, factor_cols, **kwargs):
    # 自定义打分逻辑
    return df.assign(score=...)
```

## 8. 参考来源汇总

| 文件路径 | 参考内容 |
|----------|----------|
| `stock-backtesting-system/research/ml/preprocessing.py` | FeaturePreprocessor 类设计 |
| `output/backtest_framework.py:FactorProcessor` | winsorize, standardize, fill_na 实现 |
| `QuantsPlaybook/B-因子构建类/企业生命周期/factor_tools/composition_factor.py` | 多因子打分方法 (equal/ic/icir/pca) |
| `QuantsPlaybook/B-因子构建类/筹码因子/scr/cyq.py` | winsorize 简化实现 |
| `QuantsPlaybook/SignalMaker/qrs.py` | zscore 计算 |

---
**抽取完成时间**: 2026-04-03
**抽取负责人**: Claude Code
