# strategy_kits.signals.regime_filters

市场状态与情绪开关（Regime Filters）——策略总闸门。

## 设计目标

让新策略先过一个可配置的总闸门，拿到 `ALLOWED / REDUCE / HOLD / WARNING` 状态后，再决定是否执行 alpha 逻辑。

## 目录结构

```
strategy_kits/signals/regime_filters/
├── __init__.py
├── contract.py          # 统一数据类
├── config.py            # 默认配置与合并
├── composite_gate.py    # 状态合成与路由
├── engine.py            # 统一调度引擎
├── breadth_filter.py    # 市场宽度
├── crowding_filter.py   # 拥挤率
├── newhigh_filter.py    # 创新高比例
├── volatility_filter.py # 波动率状态（简化）
├── momentum_filter.py   # 趋势状态（ICU MA / EMA / RSRS）
└── README.md            # 本文件
```

## 快速开始

```python
from strategy_kits.signals.regime_filters import run_regime_gate, DEFAULT_REGIME_CONFIG

output = run_regime_gate(
    market_data=market_df,      # index-date, cols-open/high/low/close/volume
    breadth_data=None,           # 可选：全市场个股数据
    config=DEFAULT_REGIME_CONFIG,
    date="2024-01-15"
)

print(output.regime_state)      # RegimeState.ALLOWED / REDUCE / HOLD / WARNING
print([f.name for f in output.risk_flags if f.triggered])
print({s.name: s.value for s in output.sub_signals})
```

## 状态含义

| 状态 | 建议动作 |
|------|---------|
| `ALLOWED` | 允许正常执行 alpha |
| `REDUCE` | 建议降仓（如半仓、0.3 倍仓） |
| `HOLD` | 建议观望/空仓 |
| `WARNING` | 风险预警（可继续交易但收紧止损） |

## 策略层接入示例

```python
def before_trading_start(context):
    gate = run_regime_gate(
        market_data=context.market_data,
        config=context.regime_config,
        date=str(context.previous_date)
    )
    context.regime_state = gate.regime_state

def handle_data(context, data):
    if context.regime_state == RegimeState.HOLD:
        clear_position(context)
        return
    if context.regime_state == RegimeState.REDUCE:
        targets = build_alpha_signals(context)
        scale_positions(context, targets, scale=0.5)
        return
    # ALLOWED / WARNING 时正常执行
    targets = build_alpha_signals(context)
    rebalance(context, targets)
```

## 扩展说明

- `breadth_filter.py`、`crowding_filter.py` 在 `breadth_data` 缺失时会尝试从 `market_data` 中读取同名列作为降级。
- `volatility_filter.py` 在缺少期权数据时默认使用 ATR 近似，不强制依赖 C-VIX 完整计算。
- `momentum_filter.py` 支持 `dual_ema`、`icu_ma`、`simple_ma`、`rsrs` 四种方法，通过 `config.signals.momentum_trend.method` 切换。
