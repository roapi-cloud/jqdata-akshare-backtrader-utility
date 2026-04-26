# 任务 06 回执：SignalMaker 指标工厂抽取

## 完成状态
✅ 已完成

## 核心产出

### 1. 值得抽取的信号列表（第一版）

| 类别 | 信号 | 来源 |
|------|------|------|
| 趋势跟踪 | AlligatorSignal, AOMomentumSignal, MACDSignal, ICUMASignal | 鳄鱼线择时/ICU均线 |
| 分形形态 | FractalSignal, AlignmentSignal | 鳄鱼线择时 |
| 波动率 | NoiseAreaSignal, QRSSignal | ETF日内动量/QRS择时 |
| 成交量 | VMACDMTMSignal | 成交量择时 |
| 希尔伯特 | HTSignal, HHTSignal | HHT择时 |
| 资金流向 | NorthMoneySignal | 北向资金 |

### 2. 统一接口定义

```python
# 核心输入输出
compute(price_df, feature_df, **kwargs) -> {
    "signal_series": pd.Series,  # 单资产
    "signal_df": pd.DataFrame,   # 多资产
    "meta": {...}                # 元信息
}
```

### 3. 目录结构

```
indicator_factory/
├── base.py, registry.py, factory.py
├── trend/ (鳄鱼线, AO, MACD, ICU)
├── pattern/ (分型, 排列)
├── volatility/ (噪声区域, QRS)
├── volume/ (VMACD)
├── transform/ (HT, HHT)
└── flow/ (北向资金)
```

### 4. 关键边界

- ✅ 抽取：单指标计算器、原始信号值
- ❌ 不抽：策略投票规则、固定阈值、最终仓位

## 文件位置

- **详细文档**: `/docs/strategy_kits_extraction_tasks_20260403/result_06_extract_indicator_factory.md`
- **骨架代码**: `/strategy_kits/signals/indicator_factory/` (已补最小骨架)

## 下步建议

1. 按文档迁移具体信号实现
2. 补充单元测试
3. 验证与聚宽侧的兼容性
