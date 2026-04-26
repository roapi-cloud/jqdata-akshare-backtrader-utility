# 任务 02 回执：Validation Profile 与策略分型映射

**任务状态**: 完成  
**日期**: 2026-04-03  
**主结果文档**: `../result_02_validation_profiles_and_strategy_mapping.md`

---

## 建议保留的 Profile 列表

| Profile ID | 策略类型 | 验证强度 | 建议保留 |
|-----------|---------|---------|---------|
| `main_stock_default` | stock_main | 严格 | ✅ 保留（核心） |
| `main_etf_default` | etf_main | 严格 | ✅ 保留（核心） |
| `microcap_strict` | microcap | 标准 | ✅ 保留（核心） |
| `microcap_lite` | microcap | 轻量 | ✅ 保留（快速验证用） |
| `event_lightweight` | event | 轻量 | ✅ 保留（核心） |
| `satellite_overlay` | satellite | 轻量 | ✅ 保留（核心） |
| `satellite_macro` | satellite | 标准 | ⚠️ 可选（如需要宏观信号细分） |

**总计**: 建议保留 6 个核心 profile（satellite_macro 可选）

---

## 每个 Profile 最关键的必跑项

| Profile | 最关键必跑项 | 理由 |
|---------|-------------|------|
| **main_stock_default** | V0-V3 全版 + Walk-forward + 容量测试 | 主仓必须验证装配增强效果和资金容量 |
| **main_etf_default** | V0-V3 全版 + Walk-forward + 风格归因 | 资产配置需跨周期验证风格暴露稳定性 |
| **microcap_strict** | V0,V1,V3 + 成本压力(10-100bps) + 拥挤度测试 | 微盘核心风险是成本和拥挤，V2 结构不适配可跳过 |
| **event_lightweight** | V0,V1 + 样本外(跨事件窗口) + 成本压力 | 事件策略离散，重点验证跨事件有效性和冲击成本 |
| **satellite_overlay** | V0,V1 + 样本外(3月+) | 卫星策略轻量验证，核心确认信号持续有效 |

---

## 哪类策略最容易误用主仓验证门槛

### 最高风险：microcap (微盘)

**误用场景**：
- 被要求按 stock_main 的 5bps 成本压力测试
- 被要求必须跑 V2 装配增强
- 容量预期按 5000万 设定

**后果**：
- 微盘实际滑点 20-50bps，5bps 门槛脱离实际
- 微盘策略结构差异大，强行走 V2 可能破坏原逻辑
- 微盘容量上限通常 300-500万，5000万预期导致实盘落差

**正确做法**：
- 使用 `microcap_strict` profile
- 成本压力测试范围 10-100bps
- 容量测试上限 500万

### 次高风险：event (事件驱动)

**误用场景**：
- 被要求跑 V2/V3 主仓装配
- 被要求做 walk-forward 滚动验证
- 被要求完整因子/风格归因

**后果**：
- 事件策略结构离散，不适合连续主仓底座
- 事件样本不连续，walk-forward 意义有限
- 事件收益来源是事件本身，非因子暴露

**正确做法**：
- 使用 `event_lightweight` profile
- 跳过 V2/V3，重点做 V0/V1
- 用事件窗口替代 walk-forward

---

## 是否可以直接据此写 `validation_profile.yaml`

### 结论：可以

主结果文档已提供完整的字段结构建议和完整 YAML 示例。

### 立即可执行的步骤：

1. **复制字段结构**（文档第3节）
2. **复制完整示例**（文档附录）
3. **根据实际策略调整以下参数**：
   - `cost_points_bps`: 根据实际交易频率和标的流动性
   - `capacity_levels`: 根据策略资金目标和标的容量
   - `oos_min_periods`: 根据策略周期（月频12月，季频4季）

### 需要注意的定制点：

| 字段 | 定制建议 |
|-----|---------|
| `cost_points_bps` | 参考历史成交数据，别用默认值硬套 |
| `capacity_levels` | 根据目标管理规模倒推 |
| `minimum_requirements` | 可根据策略类型差异化（如微盘 Sharpe 门槛可低于主仓） |

---

## 快速参考：一句话选 Profile

```
月频股票 + 稳健超额 -> main_stock_default
资产配置 + 宏观择时 -> main_etf_default  
小票暴露 + 流动性敏感 -> microcap_strict
事件触发 + 时间窗口 -> event_lightweight
战术配置 + 灵活进出 -> satellite_overlay
```

---

## 与任务 09 定档的边界

本文档解决的是：**选什么 profile → 跑什么验证**

任务 09 解决的是：**跑完验证 → 最终定档（主仓/过滤器/OOS/淘汰）**

本文档提供的 `minimum_requirements` 是 profile 级别的参考门槛，最终定档门槛由任务 09 统一制定。
