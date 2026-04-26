# 任务 07：市场状态与情绪开关抽取结果

> 目标：让新策略先过一个可配置的总闸门（regime gate），再执行 alpha 逻辑。

---

## 1. 建议保留的状态指标（第一版）

从 `market_sentiment_indicators.py` 与 QuantsPlaybook 择时类模块中，抽取出的**策略总闸门**层指标应当满足：
- 计算口径稳定、可跨策略复用；
- 输出可直接映射到仓位动作（允许 / 降仓 / 观望 / 预警）；
- 不绑定某一策略的专属话术或固定阈值。

### 1.1 核心必选（P0）

| 指标名称 | 功能说明 | 来源文件 | 输出用途 |
|---------|---------|---------|---------|
| `market_breadth` | 市场宽度：全市场 BIAS>0 占比或行业扩散指数 | `market_sentiment_indicators.py:44-102` | 判断市场多头/空头扩散程度 |
| `crowding_rate` | 拥挤率：成交额前 5% 个股的资金集中度 | `market_sentiment_indicators.py:126-159` | 识别资金极端集中或分散 |
| `new_high_ratio` | 创新高个股比例（N 日新高占比） | `market_sentiment_indicators.py:452-497` | 判断市场强度与动量延续性 |
| `volatility_regime` | 波动率状态（C-VIX / ATR / 时变夏普简化版） | `C-VIX/scr/calc_func.py`; 聚宽558/27 | 识别高波动风险期 |
| `momentum_trend` | 趋势状态（ICU 均线 / 双均线 / RSRS） | `ICU均线/src/icu_ma.py`; 聚宽558/02,37 | 牛熊划分与趋势确认 |

### 1.2 扩展备选（P1）

| 指标名称 | 功能说明 | 来源文件 | 输出用途 |
|---------|---------|---------|---------|
| `bottom_features` | 底部特征组合（破净/低价/成交萎缩/破发率） | `market_sentiment_indicators.py:161-330` | 极端悲观时的左侧信号 |
| `gsisi` | 国信投资者情绪指数（GSISI） | `market_sentiment_indicators.py:344-402` | 行业 Beta 情绪极值 |
| `fed_graham` | FED 模型 + 格雷厄姆指数 | `market_sentiment_indicators.py:404-450` | 大周期估值锚定 |
| `volume_momentum` | 另类价量共振指标 | `成交量的奥秘/scr/create_signal.py:43-71` | 量价背离/共振确认 |

**明确不抽取到 regime_filters 层的内容**：
- 策略专属的择时阈值最终答案（如某策略固定 `score_threshold=0.7`）；
- 策略专属的状态解释话术（如“底部区域”“顶部区域”等带有策略持仓偏好的语义）；
- 需要期权完整链数据才能计算的 C-VIX 精确值（保留简化接口，实际实现可降级为历史波动率近似）。

---

## 2. 状态输出格式

### 2.1 统一接口 Contract

```python
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional
from enum import Enum


class RegimeState(Enum):
    ALLOWED = "allowed"      # 允许正常执行 alpha
    REDUCE = "reduce"        # 建议降仓（如半仓、0.3 倍仓）
    HOLD = "hold"            # 建议观望/空仓
    WARNING = "warning"      # 风险预警（不降仓也应收紧止损）


@dataclass
class SubSignal:
    """单个原始子信号"""
    name: str
    value: float
    direction: Literal["bullish", "bearish", "neutral", "extreme"]
    weight: float = 1.0      # 在合成 gate 时的权重（配置可调）
    meta: Dict = field(default_factory=dict)


@dataclass
class RiskFlag:
    """风险标志位"""
    name: str
    triggered: bool
    severity: Literal["low", "medium", "high"]
    suggestion: str = ""     # 人类可读建议，不绑定具体仓位数字


@dataclass
class RegimeFilterOutput:
    """总闸门输出"""
    date: str
    regime_state: RegimeState      # 合成状态
    sub_signals: List[SubSignal]   # 所有子信号原始值
    risk_flags: List[RiskFlag]     # 触发的风险标志
    raw_scores: Dict[str, float]   # 各维度原始分数，供策略层自定义
    config_snapshot: Dict          # 本次计算使用的配置快照
```

### 2.2 状态合成规则（可配置，不硬编码）

```python
DEFAULT_COMPOSITE_RULES = {
    # 任一 HIGH 风险标志直接触发 WARNING
    "any_high_risk_flag": {"action": RegimeState.WARNING},
    
    # 多个 MEDIUM 风险标志触发 REDUCE
    "medium_risk_count_threshold": 2,
    
    # 基于 sub_signals 的投票机制（示例）
    "vote_weights": {
        "market_breadth": 1.0,
        "crowding_rate": 0.8,
        "new_high_ratio": 0.8,
        "volatility_regime": 1.2,
        "momentum_trend": 1.0,
    },
    "vote_thresholds": {
        "reduce": -0.3,   # 加权得分低于此值 -> REDUCE
        "hold": -0.6,     # 加权得分低于此值 -> HOLD
    }
}
```

---

## 3. 状态路由与阈值配置位设计

### 3.1 配置结构

```python
DEFAULT_REGIME_CONFIG = {
    # 1. 子信号开关与参数
    "signals": {
        "market_breadth": {
            "enabled": True,
            "index_code": "000902.XSHG",  # 中证全指
            "window": 20,
            "threshold_low": 30.0,        # <30 视为极度悲观
            "threshold_high": 70.0,       # >70 视为极度乐观
        },
        "crowding_rate": {
            "enabled": True,
            "top_pct": 0.05,
            "threshold_low": 40.0,        # <40 资金分散
            "threshold_high": 60.0,       # >60 资金拥挤
        },
        "new_high_ratio": {
            "enabled": True,
            "window": 252,
            "check_days": 15,
            "gap": 60,
            "threshold_low": 1.0,         # <1% 弱势
            "threshold_high": 5.0,        # >5% 强势
        },
        "volatility_regime": {
            "enabled": True,
            "method": "atr_approx",       # 简化实现：atr / hist_vol
            "short_window": 20,
            "long_window": 60,
            "threshold_high": 1.5,        # 短周期波动率/长周期 > 1.5
        },
        "momentum_trend": {
            "enabled": True,
            "method": "icu_ma",           # 可选：icu_ma / dual_ema / rsrs
            "fast_window": 6,
            "slow_window": 28,
            "benchmark": "000300.XSHG",
        },
    },
    
    # 2. 风险标志规则
    "risk_flags": {
        "extreme_breadth_low": {
            "enabled": True,
            "condition": "market_breadth < 20",
            "severity": "high",
            "suggestion": "市场宽度极低，建议观望",
        },
        "extreme_crowding_high": {
            "enabled": True,
            "condition": "crowding_rate > 65",
            "severity": "medium",
            "suggestion": "资金高度拥挤，建议降仓",
        },
        "volatility_spike": {
            "enabled": True,
            "condition": "volatility_regime > threshold_high",
            "severity": "high",
            "suggestion": "波动率急剧放大，建议观望或收紧止损",
        },
        "momentum_bearish": {
            "enabled": True,
            "condition": "momentum_trend == 0",
            "severity": "medium",
            "suggestion": "趋势转空，建议降仓",
        },
    },
    
    # 3. 合成规则
    "composite": {
        "any_high_risk_to_warning": True,
        "medium_risk_count_to_reduce": 2,
        "vote_weights": {
            "market_breadth": 1.0,
            "crowding_rate": 0.8,
            "new_high_ratio": 0.8,
            "volatility_regime": 1.2,
            "momentum_trend": 1.0,
        },
        "thresholds": {
            "allowed": 0.2,
            "reduce": -0.3,
            "hold": -0.6,
        }
    }
}
```

### 3.2 状态路由逻辑

```python
def route_regime(sub_signals: List[SubSignal],
                 risk_flags: List[RiskFlag],
                 rules: dict) -> RegimeState:
    # 1. 风险标志直接路由
    high_flags = [f for f in risk_flags if f.triggered and f.severity == "high"]
    if rules.get("any_high_risk_to_warning", True) and high_flags:
        return RegimeState.WARNING

    medium_flags = [f for f in risk_flags if f.triggered and f.severity == "medium"]
    threshold = rules.get("medium_risk_count_to_reduce", 2)
    if len(medium_flags) >= threshold:
        return RegimeState.REDUCE

    # 2. 子信号投票路由
    weights = rules["vote_weights"]
    total_weight = sum(weights.values())
    score = 0.0
    for sig in sub_signals:
        if sig.name in weights:
            # 将 direction 映射到 [-1, 1]
            dir_map = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0, "extreme": -1.0}
            score += dir_map.get(sig.direction, 0.0) * weights[sig.name]
    score = score / total_weight if total_weight > 0 else 0.0

    th = rules["thresholds"]
    if score <= th.get("hold", -0.6):
        return RegimeState.HOLD
    elif score <= th.get("reduce", -0.3):
        return RegimeState.REDUCE
    elif score >= th.get("allowed", 0.2):
        return RegimeState.ALLOWED
    else:
        return RegimeState.WARNING
```

---

## 4. 推荐目标文件拆分

目标根目录：`strategy_kits/signals/regime_filters/`

```
strategy_kits/signals/regime_filters/
├── __init__.py
├── contract.py              # 数据类：RegimeState / SubSignal / RiskFlag / RegimeFilterOutput
├── config.py                # DEFAULT_REGIME_CONFIG 与配置校验
├── composite_gate.py        # 总闸门：输入子信号 -> 输出 regime_state + risk_flags
│                            #   职责：状态路由、规则解析、权重投票
├── breadth_filter.py        # 市场宽度（market_breadth）计算
├── crowding_filter.py       # 拥挤率（crowding_rate）计算
├── newhigh_filter.py        # 创新高比例（new_high_ratio）计算
├── volatility_filter.py     # 波动率状态（volatility_regime）计算
├── momentum_filter.py       # 趋势状态（momentum_trend）计算
├── bottom_filter.py         # 底部特征包（bottom_features）计算（P1）
├── sentiment_filter.py      # GSISI / FED-Graham（P1）
├── engine.py                # 统一调度引擎：按 config 调度各 filter -> composite_gate
└── README.md
```

### 4.1 文件职责边界

| 文件 | 职责 | 是否第一版实现 |
|-----|------|--------------|
| `contract.py` | 统一数据结构定义 | ✅ |
| `config.py` | 默认配置、配置校验与合并 | ✅ |
| `composite_gate.py` | 状态合成与路由（与数据计算解耦） | ✅ |
| `breadth_filter.py` | 市场宽度/扩散指数计算 | ✅ |
| `crowding_filter.py` | 拥挤率计算 | ✅ |
| `newhigh_filter.py` | 创新高比例计算 | ✅ |
| `volatility_filter.py` | 波动率状态（简化 ATR/hist_vol 近似） | ✅ |
| `momentum_filter.py` | 趋势判断（ICU MA / EMA / RSRS 接口） | ✅ |
| `engine.py` | 统一调度：读取 market_data + breadth_data + config，输出 RegimeFilterOutput | ✅ |
| `bottom_filter.py` | 底部特征组合（P1 扩展） | ❌ |
| `sentiment_filter.py` | GSISI / FED-Graham（P1 扩展） | ❌ |
| `README.md` | 使用说明与接入示例 | ✅ |

---

## 5. 最小骨架文件（已补）

骨架文件已落地到 `strategy_kits/signals/regime_filters/`。

### 5.1 最小使用示例

```python
from strategy_kits.signals.regime_filters import run_regime_gate, DEFAULT_REGIME_CONFIG

output = run_regime_gate(
    market_data=market_df,       # 指数行情 DataFrame (index-date, cols-open/high/low/close/volume)
    breadth_data=breadth_df,     # 可选：全市场个股行情/状态数据
    config=DEFAULT_REGIME_CONFIG,
    date="2024-01-15"
)

print(output.regime_state)      # RegimeState.ALLOWED / REDUCE / HOLD / WARNING
print([f.name for f in output.risk_flags if f.triggered])
print({s.name: s.value for s in output.sub_signals})
```

### 5.2 策略层接入模式

```python
def before_trading_start(context):
    gate = run_regime_gate(
        market_data=context.market_data,
        breadth_data=context.breadth_data,
        config=context.regime_config,
        date=str(context.previous_date)
    )
    context.regime_state = gate.regime_state

def handle_data(context, data):
    # 总闸门优先级高于 alpha
    if context.regime_state == RegimeState.HOLD:
        clear_position(context)
        return
    
    if context.regime_state == RegimeState.REDUCE:
        target_positions = build_alpha_signals(context)
        scale_positions(context, target_positions, scale=0.5)
        return
    
    # ALLOWED 或 WARNING 时正常执行 alpha（WARNING 可在止损层额外收紧）
    target_positions = build_alpha_signals(context)
    rebalance(context, target_positions)
```

---

## 6. 不该抽取的内容（明确边界）

| 内容 | 原因 |
|-----|------|
| 策略结论中的固定阈值“最终答案” | 阈值应配置化，不同策略可不同 |
| 策略专属的状态解释话术 | 如“顶部区域”“抄底神器”等带有持仓偏好的语义 |
| 具体选股/因子逻辑 | 属于 alpha 层，不属于 regime gate |
| 完整期权链 C-VIX 计算 | 数据依赖重，第一版用历史波动率近似接口替代 |
| 策略专属的仓位比例数字 | 如 `bearpercent=0.3` 应由策略层消费 `REDUCE` 状态后自行决定 |

---

## 7. 验收标准

- ✅ 新策略可以直接调用 `run_regime_gate` 获取总闸门状态，无需复制粘贴择时代码。
- ✅ 状态计算（`breadth_filter.py` 等）与状态使用（`composite_gate.py`）分层清楚。
- ✅ 输入为 `market_data` + `breadth_data` + `config`，输出包含 `regime_state` + `sub_signals` + `risk_flags`。
- ✅ 所有子信号计算器可独立调用（方便策略只订阅某几个信号）。
- ✅ 配置中的阈值、权重、开关均可热替换，不硬编码在计算逻辑中。
