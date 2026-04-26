# 统一择时模型库 (Unified Timing Model Library)

> 聚合所有大盘择时与个股择时模型，提供统一的信号接口与仓位管理。

---

## 一、架构总览

```
timing_model_library/
├── base.py                      # 抽象基类 (BaseTimingModel, TimingSignal, TimingResult)
├── market_timing/               # 大盘择时 (12 个模型)
│   ├── rsrs.py                  # RSRS 家族 (3 个模型)
│   ├── volatility_turnover.py   # 波动率+换手率牛熊指标
│   ├── vix.py                   # C-VIX 恐慌指数
│   ├── fed_model.py             # FED 模型 + 格雷厄姆指数
│   ├── congestion.py            # 拥挤率指标
│   ├── market_breadth.py        # 市场宽度 + 扩散指标 (2 个模型)
│   ├── sentiment.py             # 投资者情绪指数
│   ├── bottom_features.py       # 市场底部特征
│   ├── northbound.py            # 北向资金择时
│   ├── macd_timing.py           # MACD 择时 (3 种变体)
│   ├── boll_timing.py           # 布林带择时
│   └── top_bottom.py            # 顶底判断 (MACD背离+EMA通道)
├── stock_timing/                # 个股择时 (4 个模型)
│   ├── technical_timing.py      # 技术指标择时 (RSI/MA/BOLL/MACD)
│   ├── factor_timing.py         # 因子择时
│   ├── ml_timing.py             # 机器学习择时 (SVR/随机森林/逻辑回归)
│   └── diffusion_timing.py      # 扩散指数择时
├── signal_fusion/               # 信号融合
│   ├── ensemble.py              # 多信号融合 (4 种方法)
│   └── position_manager.py      # 仓位管理 (5 种方法)
├── data/                        # 数据层
│   └── akshare_fetcher.py       # AKShare 数据获取 + 缓存
└── utils/                       # 工具函数
    ├── indicators.py            # 通用技术指标计算
    └── signal_processor.py      # 信号处理 (平滑/过滤/共振)
```

---

## 二、大盘择时模型 (12 类)

### 2.1 RSRS 家族

| 模型 | 核心公式 | 适用场景 |
|------|---------|---------|
| `RSRSModel` | `zscore(slope) × R²` | 基础大盘择时 |
| `VolumeWeightedRSRS` | 成交量加权 OLS + 4 种变体 | 提高信号质量 |
| `AdvancedRSRS` | RSRS + 斜率趋势 + WR 过滤 + 动量 | 综合择时 |

**参数:**
- `N`: 回归窗口 (默认 18)
- `M`: Z-Score 参考天数 (默认 600)
- `buy_threshold`: 买入阈值 (默认 0.7)
- `sell_threshold`: 卖出阈值 (默认 -0.7)

### 2.2 波动率 + 换手率 牛熊指标

| 模型 | 核心逻辑 |
|------|---------|
| `VolatilityTurnoverBullBear` | 波动率 Z-Score + 换手率 Z-Score → 牛熊分类 |

**市场状态分类:**
- 波动率高 + 换手率高 → 熊市-过热 → 卖出
- 波动率低 + 换手率低 → 牛市初期-冰点 → 买入
- 波动率低 + 换手率高 → 牛市中期-温和 → 买入
- 波动率高 + 换手率低 → 震荡-恐慌 → 持有

### 2.3 C-VIX 恐慌指数

| 模型 | 核心逻辑 |
|------|---------|
| `CVIXModel` | 已实现波动率 Z-Score → 恐慌/贪婪判断 |

**逆向逻辑:**
- VIX 极高 (Z > 1.5) → 极度恐慌 → 逆向买入
- VIX 极低 (Z < -1.0) → 极度贪婪 → 卖出

### 2.4 FED 模型 + 格雷厄姆指数

| 模型 | 核心逻辑 |
|------|---------|
| `FEDModel` | 1/PE vs 国债收益率 → 股债相对估值 |

**格雷厄姆指数 = (1/PE) / 国债收益率:**
- > 2.0 → 极度低估 → 强买
- 1.5 ~ 2.0 → 低估 → 买入
- 1.0 ~ 1.5 → 合理 → 持有
- < 1.0 → 高估 → 卖出

### 2.5 拥挤率指标

| 模型 | 核心逻辑 |
|------|---------|
| `CongestionModel` | 成交量/成交额增速 → 交易拥挤度 |

### 2.6 市场宽度 / 扩散指标

| 模型 | 核心逻辑 |
|------|---------|
| `MarketBreadthModel` | 涨跌家数比 + 双均线 |
| `DiffusionIndexModel` | ROC > 0 的股票占比 + 双均线 |

### 2.7 投资者情绪指数

| 模型 | 核心逻辑 |
|------|---------|
| `SentimentModel` | 涨停/跌停比 + 融资余额 + 换手率 + 封板率 → 综合情绪分数 |

### 2.8 市场底部特征

| 模型 | 核心逻辑 |
|------|---------|
| `BottomFeaturesModel` | 5 个底部信号: 地量/波动率回落/超跌/宽度回升/跌停减少 |

### 2.9 北向资金择时

| 模型 | 核心逻辑 |
|------|---------|
| `NorthboundModel` | 北向资金净流入布林带 → 资金流向极端值判断 |

### 2.10 MACD 择时

| 变体 | 核心逻辑 |
|------|---------|
| `monthly` | 月线 MACD → 大周期趋势 |
| `daily` | 日线 MACD → 标准趋势 |
| `fast` | EMA2-EMA4 → 超短期过滤 |

### 2.11 布林带择时

| 模型 | 核心逻辑 |
|------|---------|
| `BOLLTimingModel` | 价格在布林带中的位置 → 超买超卖 |

### 2.12 顶底判断

| 模型 | 核心逻辑 |
|------|---------|
| `TopBottomModel` | MACD 背离结构 + EMA 通道 → 顶底判断 + 仓位分级 |

---

## 三、个股择时模型 (4 类)

### 3.1 技术指标择时

| 模型 | 包含指标 |
|------|---------|
| `TechnicalTimingModel` | RSI / MA 金叉死叉 / BOLL 位置 / MACD |

### 3.2 因子择时

| 模型 | 核心逻辑 |
|------|---------|
| `FactorTimingModel` | 跟踪因子 IC/收益 → 因子有效性周期判断 |

### 3.3 机器学习择时

| 模型 | 支持算法 |
|------|---------|
| `MLTimingModel` | SVR / 随机森林 / 逻辑回归 |

### 3.4 扩散指数择时

| 模型 | 核心逻辑 |
|------|---------|
| `StockDiffusionTimingModel` | 股票池 ROC > 0 占比 + EMA 交叉 |

---

## 四、信号融合 (4 种方法)

| 方法 | 说明 |
|------|------|
| `weighted` | 各模型信号加权求和 |
| `vote` | 多数投票决定方向 |
| `resonance` | 只有多个模型一致时才产生强信号 |
| `hierarchical` | 先按类别 (大盘/个股) 融合，再综合 |

---

## 五、仓位管理 (5 种方法)

| 方法 | 公式 |
|------|------|
| `fixed` | BUY=100%, SELL=0%, HOLD=50% |
| `strength` | position = (strength + 1) / 2 |
| `kelly` | Kelly 公式 × 分数 Kelly |
| `volatility` | 根据市场波动率动态调整 |
| `hierarchical` | 大盘择时控制总仓位 × 60% + 个股择时 × 40% |

---

## 六、快速开始

```python
from timing_model_library.market_timing import RSRSModel, BOLLTimingModel
from timing_model_library.signal_fusion import SignalEnsemble, PositionManager

# 1. 准备数据 (OHLCV)
import pandas as pd
import numpy as np

dates = pd.date_range("2020-01-01", periods=800, freq="B")
close = 100 + np.cumsum(np.random.randn(800) * 0.5)
high = close + np.abs(np.random.randn(800) * 0.3)
low = close - np.abs(np.random.randn(800) * 0.3)
volume = np.random.randint(1000000, 5000000, 800)

data = pd.DataFrame({
    "close": close, "high": high, "low": low, "volume": volume
}, index=dates)

# 2. 计算各模型信号
rsrs = RSRSModel(N=18, M=600)
boll = BOLLTimingModel()

signal_rsrs = rsrs.compute(data)
signal_boll = boll.compute(data)

# 3. 信号融合
ensemble = SignalEnsemble(
    models=[rsrs, boll],
    method="weighted",
    weights={"RSRS": 1.5, "BOLL-Timing": 0.7}
)
result = ensemble.fuse([signal_rsrs, signal_boll])

# 4. 仓位计算
pm = PositionManager(method="strength")
position = pm.compute_position(result)

print(f"建议仓位: {position:.0%}")
```

---

## 七、数据要求

### 大盘择时数据

| 模型 | 必需列 | 可选列 |
|------|--------|--------|
| RSRS | high, low | volume |
| Vol-Turnover | close, volume | - |
| C-VIX | close | - |
| FED | pe_ratio, bond_yield | - |
| Congestion | volume, amount, close | - |
| MarketBreadth | up_count, down_count | new_high, new_low |
| Sentiment | limit_up, limit_down (至少 2 个) | margin_balance, turnover_rate, sealed_rate |
| BottomFeatures | close, volume | limit_down, up_count, down_count |
| Northbound | north_net | close |
| MACD | close | - |
| BOLL | close | - |
| TopBottom | close, high, low | - |

### 个股择时数据

| 模型 | 必需列 |
|------|--------|
| Technical | close, high, low, volume |
| Factor | *_ic 或 *_ret 列 |
| ML | close, high, low, volume |
| Diffusion | 多股票收盘价 DataFrame |

---

## 八、统一接口

所有择时模型遵循统一接口:

```python
class BaseTimingModel:
    def compute(self, data: pd.DataFrame, **kwargs) -> TimingSignal:
        """计算择时信号"""

@dataclass
class TimingSignal:
    model_name: str           # 模型名称
    scope: TimingScope        # 适用范围 (MARKET/STOCK/ETF)
    direction: SignalDirection # 信号方向 (BUY/HOLD/SELL)
    strength: float           # 信号强度 [-1.0, 1.0]
    confidence: float         # 置信度 [0.0, 1.0]
    raw_score: float          # 原始分数
    timestamp: pd.Timestamp   # 时间戳
    metadata: Dict            # 模型特定元数据
```

---

## 九、方法论总结

### 择时信号三大来源

```
├── 价格/成交量类: RSRS、BOLL、均线、动量、波动率
├── 资金/情绪类: 换手率、北向资金、拥挤率、VIX、情绪指数
└── 基本面/宏观类: FED模型、格雷厄姆指数、风险溢价、股债平衡
```

### 大盘择时核心原则

1. **低频为主**: 信号周期通常为周/月级别
2. **多信号共振**: 单一指标胜率低，建议 2-3 个不同维度信号共振
3. **右侧确认**: 底部信号需要右侧确认
4. **与选股解耦**: 大盘择时控制仓位，选股策略控制标的

### 推荐组合

| 场景 | 推荐组合 |
|------|---------|
| 稳健型 | RSRS + FED + 波动率牛熊 |
| 积极型 | Advanced-RSRS + C-VIX + 拥挤率 |
| 全面型 | RSRS + 波动率牛熊 + C-VIX + FED + 北向 + 市场宽度 |
| 个股型 | 技术指标择时 + 因子择时 + 扩散指数 |
