# Regime Pattern Library

Stores pattern definitions and historical examples for the 7 composite market regimes.

## Directory Structure

```
regime_patterns/
├── trend_risk_on_growth/
│   ├── pattern.yaml          # Pattern definition
│   ├── examples/              # Historical examples
│   │   ├── 2023-10-01.json
│   │   └── ...
│   └── description.md         # Pattern description
├── trend_risk_on_smallcap/
├── balanced_rotation/
├── defensive_dividend/
├── high_volatility_warning/
├── panic_bottoming/
└── broad_weakness_hold/
```

## Regime Definitions

### 1. trend_risk_on_growth (趋势进攻·成长主导)
**特征**: 强趋势上行 + 成长风格主导
**触发条件**:
- trend_state = 强趋势上行 (MA5>MA10>MA20>MA60, MACD金叉, RSRS>0.7)
- breadth_state = 偏强或过热 (>55%)
- sentiment_state = 活跃或狂热
- style_state = 成长主导 (成长股显著跑赢)

**典型市场环境**: 牛市中期，成长股领涨，趋势强劲

### 2. trend_risk_on_smallcap (趋势进攻·小盘主导)
**特征**: 强趋势上行 + 小盘风格主导
**触发条件**:
- trend_state = 强趋势上行
- breadth_state = 偏强 (>55%)
- style_state = 小盘进攻 (小盘股显著跑赢大盘)

**典型市场环境**: 牛市中期，小盘股弹性更大

### 3. balanced_rotation (均衡轮动)
**特征**: 震荡整理 + 行业轮动活跃
**触发条件**:
- trend_state = 震荡 (均线缠绕，MACD在零轴附近)
- breadth_state = 中性 (35-55%)
- sector_state = 高速轮动或双主线

**典型市场环境**: 震荡市，行业快速轮动

### 4. defensive_dividend (防守·红利)
**特征**: 趋势转弱 + 红利价值防御
**触发条件**:
- trend_state = 趋势转弱或破位下行
- style_state = 红利防守 (高股息股票显著跑赢)
- risk_state = 中性风险或高风险

**典型市场环境**: 熊市初期或市场调整，红利策略防御性强

### 5. high_volatility_warning (高波动预警)
**特征**: 波动率显著上升 + 风险预警
**触发条件**:
- risk_state = 高风险或极端风险
- 已实现波动率 > 2倍历史均值
- 存在3个以上风险标志

**典型市场环境**: 市场剧震，波动率飙升

### 6. panic_bottoming (恐慌探底)
**特征**: 广度极弱 + 情绪冰点
**触发条件**:
- breadth_state = 极弱 (<20%)
- sentiment_state = 冰点
- 连续恐慌性抛售

**典型市场环境**: 阶段性底部，情绪极度悲观

### 7. broad_weakness_hold (全面弱势·持币观望)
**特征**: 破位下行 + 广度偏弱
**触发条件**:
- trend_state = 破位下行 (跌破MA60, RSRS<0.3)
- breadth_state = 极弱或偏弱 (<35%)

**典型市场环境**: 熊市确立，系统性风险释放