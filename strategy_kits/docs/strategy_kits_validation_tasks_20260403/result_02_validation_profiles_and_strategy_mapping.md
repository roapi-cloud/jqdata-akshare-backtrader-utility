# Validation Profile 与策略分型映射设计

**文档版本**: 1.0  
**日期**: 2026-04-03  
**任务编号**: 02

---

## 1. 策略分型定义

| 策略类型 | 代码 | 核心特征 | 持仓周期 | 典型场景 |
|---------|------|---------|---------|---------|
| **股票低频主仓** | `stock_main` | 月/周频调仓，持仓分散，追求稳健超额 | 15-60天 | 核心持仓，占仓位50%+ |
| **ETF/多资产主仓** | `etf_main` | 跨资产轮动，宏观择时，风险预算 | 30-90天 | 资产配置核心 |
| **微盘/小市值** | `microcap` | 小票暴露，流动性敏感，拥挤度风险 | 5-20天 | 风格增强，仓位受限 |
| **事件驱动** | `event` | 特定事件触发，持仓集中，时间敏感 | 1-10天 | 卫星机会，阶段性参与 |
| **卫星/机会仓** | `satellite` | 战术性配置，灵活进出，非持续持有 | 不定 | 辅助增强，严格止损 |

**分型边界说明**：
- 持仓周期 < 3天的策略不适用本验证框架（归为日内/高频）
- 纯宏观/战略信号不作为独立策略类型，归为 `satellite`
- 多因子组合若月频调仓，可归为 `stock_main` 而非 `microcap`

---

## 2. Validation Profile 设计原则

### 2.1 核心原则

1. **分型定制**：不同策略类型承担不同的验证负担
2. **层级递进**：从 V0 到 V3 逐级强化，允许部分类型跳过中间层
3. **成本敏感**：微盘/事件类必须做成本压力测试，ETF/股票主仓可适度放宽
4. **容量区分**：主仓必须做容量测试，卫星/事件可跳过

### 2.2 验证强度分级

| 强度 | 说明 | 适用类型 |
|-----|------|---------|
| **严格 (Strict)** | V0-V3 全跑 + walk-forward + 容量测试 | stock_main, etf_main |
| **标准 (Standard)** | V0, V1, V3 必跑 + OOS + 成本压力 | microcap |
| **轻量 (Lightweight)** | V0, V1 必跑 + OOS + 关键成本点 | event, satellite |

---

## 3. validation_profile.yaml 字段结构建议

```yaml
validation_profile:
  # 基础标识
  profile_id: string          # profile 唯一标识
  profile_name: string        # 可读名称
  strategy_type: enum         # stock_main / etf_main / microcap / event / satellite
  
  # V版本要求
  v_matrix:
    v0_baseline: bool         # 原策略基线 (所有类型必true)
    v1_unified_spec: bool     # 统一口径 (所有类型必true)
    v2_assembly_enhanced: bool # 装配增强 (stock_main/etf_main必true, 其他可选)
    v3_full_base: bool        # 完整底座 (stock_main/etf_main/microcap必true)
  
  # 稳定性验证
  stability:
    walk_forward: enum        # required / recommended / optional / skip
    oos_required: bool        # 是否必须OOS
    oos_min_periods: int      # OOS最少周期数 (月)
    rolling_window: enum      # required / recommended / optional / skip
  
  # 成本与容量
  cost_capacity:
    cost_stress_test: enum    # required / recommended / optional / skip
    cost_points_bps: []int    # 压力测试点位 [5, 10, 20, 30]
    capacity_test: enum       # required / recommended / optional / skip
    capacity_levels: []int    # 容量测试层级 (万) [100, 500, 1000]
  
  # 归因要求
  attribution:
    factor_attribution: enum  # required / recommended / optional / skip
    style_attribution: enum   # required / recommended / optional / skip
    sector_attribution: enum  # required / recommended / optional / skip
   特异收益分析: enum         # required / recommended / optional / skip
  
  # 特殊验证
  special:
    liquidity_test: enum      # required / recommended / optional / skip
    crowding_test: enum       # microcap/event建议required
    regime_decomposition: enum # required / recommended / optional / skip
  
  # 通过标准覆盖
  admission_override:
    min_calmar: float         # 覆盖默认Calmar门槛
    max_drawdown_limit: float # 覆盖默认回撤限制
    min_sharpe: float         # 覆盖默认Sharpe门槛
  
  # 跳过规则
  skip_rules:
    - condition: string       # 跳过某验证的条件描述
      applies_to: []string    # 适用的验证项
  
  # 备注
  notes: string
```

---

## 4. 各策略类型 Validation Profile 详细设计

### 4.1 stock_main (股票低频主仓)

**定位**：核心持仓策略，验证最严格

```yaml
profile_id: "main_stock_default"
strategy_type: "stock_main"
v_matrix:
  v0_baseline: true
  v1_unified_spec: true
  v2_assembly_enhanced: true
  v3_full_base: true
stability:
  walk_forward: "required"
  oos_required: true
  oos_min_periods: 12
  rolling_window: "required"
cost_capacity:
  cost_stress_test: "required"
  cost_points_bps: [5, 10, 20, 30, 50]
  capacity_test: "required"
  capacity_levels: [500, 1000, 2000, 5000]
attribution:
  factor_attribution: "required"
  style_attribution: "required"
  sector_attribution: "required"
  特异收益分析: "required"
special:
  liquidity_test: "recommended"
  crowding_test: "recommended"
  regime_decomposition: "required"
```

**必跑实验矩阵**：

| 实验 | 优先级 | 说明 |
|-----|-------|------|
| V0 原策略 | P0 | 基线 |
| V1 统一口径 | P0 | 数据/基准/成本统一 |
| V2 装配增强 | P0 | 接入路由+确认层 |
| V3 完整底座 | P0 | 统一执行底座 |
| Walk-forward | P0 | 滚动验证参数稳定性 |
| 成本压力(5-50bps) | P0 | 滑点敏感性 |
| 容量测试 | P0 | 500万-5000万 |
| 样本外12月+ | P0 | 持续跟踪 |
| 归因分解 | P0 | 市值/行业/风格/特异 |

**可跳过项**：
- 流动性测试（若持仓大于100只且单票权重<2%可标记为optional）
- 拥挤度测试（非小票暴露策略可降级为optional）

---

### 4.2 etf_main (ETF/多资产主仓)

**定位**：资产配置核心，换手相对较低

```yaml
profile_id: "main_etf_default"
strategy_type: "etf_main"
v_matrix:
  v0_baseline: true
  v1_unified_spec: true
  v2_assembly_enhanced: true
  v3_full_base: true
stability:
  walk_forward: "required"
  oos_required: true
  oos_min_periods: 6
  rolling_window: "recommended"
cost_capacity:
  cost_stress_test: "recommended"
  cost_points_bps: [5, 10, 20]
  capacity_test: "required"
  capacity_levels: [1000, 5000, 10000]
attribution:
  factor_attribution: "optional"
  style_attribution: "required"
  sector_attribution: "optional"
  特异收益分析: "required"
special:
  liquidity_test: "optional"
  crowding_test: "optional"
  regime_decomposition: "required"
```

**必跑实验矩阵**：

| 实验 | 优先级 | 说明 |
|-----|-------|------|
| V0-V3 全版 | P0 | 同 stock_main |
| Walk-forward | P0 | 资产配置策略需跨周期验证 |
| 容量测试 | P0 | ETF容量门槛更高(1000万起) |
| 样本外6月+ | P0 | 可接受较短OOS |
| 风格归因 | P0 | 资产风格暴露分析 |
| 市场状态分解 | P0 | 牛熊/震荡环境表现 |

**与 stock_main 差异**：
- 成本压力可降级为 recommended（ETF滑点通常更小）
- 因子归因可跳过（ETF通常不基于传统因子）
- 拥挤度测试可跳过（ETF流动性通常更好）

---

### 4.3 microcap (微盘/小市值)

**定位**：风格增强，流动性与拥挤度是关键风险

```yaml
profile_id: "microcap_strict"
strategy_type: "microcap"
v_matrix:
  v0_baseline: true
  v1_unified_spec: true
  v2_assembly_enhanced: false  # 微盘策略结构差异大，可跳过
  v3_full_base: true
stability:
  walk_forward: "recommended"   # 可降级，但强烈建议
  oos_required: true
  oos_min_periods: 6
  rolling_window: "required"
cost_capacity:
  cost_stress_test: "required"  # 微盘对成本极度敏感
  cost_points_bps: [10, 20, 30, 50, 100]  # 更宽的压力范围
  capacity_test: "required"
  capacity_levels: [100, 300, 500]  # 容量上限更低
attribution:
  factor_attribution: "required"
  style_attribution: "required"
  sector_attribution: "required"
  特异收益分析: "required"
special:
  liquidity_test: "required"    # 微盘必须测流动性
  crowding_test: "required"     # 拥挤度是微盘核心风险
  regime_decomposition: "recommended"
```

**必跑实验矩阵**：

| 实验 | 优先级 | 说明 |
|-----|-------|------|
| V0, V1, V3 | P0 | V2可跳过（微盘结构特殊） |
| 成本压力(10-100bps) | P0 | 微盘滑点显著高于主仓 |
| 流动性测试 | P0 | 日均成交量/冲击成本 |
| 拥挤度测试 | P0 | 扩散指数/情绪指标 |
| 容量测试 | P0 | 100-500万即可能受限 |
| 滚动窗口 | P0 | 参数脆弱性检测 |

**不能直接复用的主仓门槛**：
- 成本压力测试：主仓用5-30bps，微盘需10-100bps
- 容量测试：主仓1000万起，微盘100万起
- 拥挤度测试：主仓optional，微盘required

---

### 4.4 event (事件驱动)

**定位**：战术性机会，信号离散，难以连续回测

```yaml
profile_id: "event_lightweight"
strategy_type: "event"
v_matrix:
  v0_baseline: true
  v1_unified_spec: true
  v2_assembly_enhanced: false
  v3_full_base: false         # 事件策略不接主仓底座
stability:
  walk_forward: "optional"    # 事件样本离散，walk-forward意义有限
  oos_required: true
  oos_min_periods: 3          # 最少3个独立事件窗口
  rolling_window: "optional"
cost_capacity:
  cost_stress_test: "required"
  cost_points_bps: [10, 20, 30]  # 事件冲击成本更高
  capacity_test: "recommended"
  capacity_levels: [100, 500]
attribution:
  factor_attribution: "optional"
  style_attribution: "optional"
  sector_attribution: "recommended"
  特异收益分析: "required"    # 事件策略的核心是事件本身
special:
  liquidity_test: "required"  # 事件期间流动性可能骤降
  crowding_test: "recommended"
  regime_decomposition: "optional"
```

**必跑实验矩阵**：

| 实验 | 优先级 | 说明 |
|-----|-------|------|
| V0, V1 | P0 | 只跑基线+统一口径 |
| 样本外(3个事件+) | P0 | 跨事件窗口验证 |
| 成本压力(10-30bps) | P0 | 事件冲击成本 |
| 流动性测试 | P0 | 事件期间流动性 |
| 特异收益分析 | P0 | 剔除风格后的纯事件收益 |

**跳过规则**：
- V2/V3：事件策略结构差异大，不接入主仓装配流程
- Walk-forward：事件样本不连续，用事件窗口替代
- 归因：因子/风格归因可跳过，重点看事件特异收益

---

### 4.5 satellite (卫星/机会仓)

**定位**：战术性配置，灵活性强，严格止损

```yaml
profile_id: "satellite_overlay"
strategy_type: "satellite"
v_matrix:
  v0_baseline: true
  v1_unified_spec: true
  v2_assembly_enhanced: false
  v3_full_base: false
stability:
  walk_forward: "optional"
  oos_required: true
  oos_min_periods: 3
  rolling_window: "optional"
cost_capacity:
  cost_stress_test: "recommended"
  cost_points_bps: [10, 20, 30]
  capacity_test: "optional"
  capacity_levels: [100, 500]
attribution:
  factor_attribution: "optional"
  style_attribution: "optional"
  sector_attribution: "optional"
  特异收益分析: "recommended"
special:
  liquidity_test: "recommended"
  crowding_test: "optional"
  regime_decomposition: "optional"
```

**必跑实验矩阵**：

| 实验 | 优先级 | 说明 |
|-----|-------|------|
| V0, V1 | P0 | 基线+统一口径 |
| 样本外(3月+) | P0 | 持续跟踪有效性 |
| 成本压力 | P1 | 建议10-30bps测试 |

**跳过规则**：
- V2/V3：卫星策略不接主仓底座
- 容量测试：卫星仓位轻，容量非关键
- 完整归因：卫星策略重时机选择，轻风格暴露

---

## 5. 策略类型 -> Validation Profile 对照表

| 策略类型 | 推荐 Profile | V0 | V1 | V2 | V3 | Walk-forward | OOS | 成本压力 | 容量测试 | 拥挤度 | 流动性 |
|---------|-------------|----|----|----|----|--------------|-----|---------|---------|--------|--------|
| stock_main | main_stock_default | 必跑 | 必跑 | 必跑 | 必跑 | 必跑 | 必跑(12月+) | 必跑(5-50bps) | 必跑 | 建议 | 建议 |
| etf_main | main_etf_default | 必跑 | 必跑 | 必跑 | 必跑 | 必跑 | 必跑(6月+) | 建议(5-20bps) | 必跑 | 可跳过 | 可跳过 |
| microcap | microcap_strict | 必跑 | 必跑 | 可跳过 | 必跑 | 建议 | 必跑(6月+) | 必跑(10-100bps) | 必跑 | 必跑 | 必跑 |
| event | event_lightweight | 必跑 | 必跑 | 可跳过 | 可跳过 | 可跳过 | 必跑(3事件+) | 必跑(10-30bps) | 建议 | 建议 | 必跑 |
| satellite | satellite_overlay | 必跑 | 必跑 | 可跳过 | 可跳过 | 可跳过 | 必跑(3月+) | 建议 | 可跳过 | 可跳过 | 建议 |

---

## 6. 典型误用场景

### 6.1 误用 1：用主仓门槛要求微盘

**场景**：微盘策略被要求按 stock_main 的 5bps 成本压力测试通过。

**问题**：微盘实际滑点远高于主仓，5bps 门槛脱离实际。

**正确做法**：
- 微盘应使用 microcap_strict profile
- 成本压力测试范围应为 10-100bps
- 容量预期应降至 100-500万

### 6.2 误用 2：事件策略强行走 V2/V3

**场景**：事件策略被要求接入主仓装配流程，跑 V2/V3。

**问题**：事件策略结构离散，不适合连续的主仓底座。

**正确做法**：
- 事件策略使用 event_lightweight profile
- 只跑 V0/V1 + 独立验证
- 重点验证跨事件窗口的有效性

### 6.3 误用 3：卫星策略要求完整归因

**场景**：卫星策略被要求输出完整的市值/行业/风格归因。

**问题**：卫星策略重择时轻暴露，完整归因意义不大。

**正确做法**：
- 卫星策略使用 satellite_overlay profile
- 重点验证时点选择有效性
- 归因可简化或跳过

### 6.4 误用 4：ETF 策略要求因子归因

**场景**：ETF 轮动策略被要求做传统股票因子归因。

**问题**：ETF 收益来源是资产类别/行业/地域，非传统因子。

**正确做法**：
- ETF 策略使用 main_etf_default profile
- 风格归因关注资产风格（价值/成长/防御/周期）
- 市场状态分解为必跑项

---

## 7. 推荐默认 Profile 集合

### 7.1 核心 Profile 列表

| Profile ID | 策略类型 | 验证强度 | 适用场景 |
|-----------|---------|---------|---------|
| `main_stock_default` | stock_main | 严格 | 核心股票策略 |
| `main_etf_default` | etf_main | 严格 | 资产配置策略 |
| `microcap_strict` | microcap | 标准 | 小市值增强 |
| `microcap_lite` | microcap | 轻量 | 快速验证微盘想法 |
| `event_lightweight` | event | 轻量 | 事件驱动策略 |
| `satellite_overlay` | satellite | 轻量 | 战术性机会仓 |
| `satellite_macro` | satellite | 标准 | 宏观战略信号 |

### 7.2 Profile 继承关系

```
base_profile (所有类型共用)
    ├── main_stock_default
    ├── main_etf_default
    ├── microcap_strict
    │       └── microcap_lite (继承后精简)
    ├── event_lightweight
    └── satellite_overlay
            └── satellite_macro (增加归因要求)
```

### 7.3 快速选择指南

```
策略月频调仓 + 持仓50+ + 追求稳健超额
    └── main_stock_default

策略跨资产 + 宏观择时 + 风险预算
    └── main_etf_default

策略小票暴露 + 流动性敏感 + 拥挤度风险
    └── microcap_strict (正式) / microcap_lite (快速验证)

策略事件触发 + 持仓集中 + 时间窗口
    └── event_lightweight

策略战术配置 + 灵活进出 + 非持续持有
    └── satellite_overlay (常规) / satellite_macro (宏观信号)
```

---

## 8. 与现有文档的衔接

| 本文档 | 衔接文档 | 衔接点 |
|-------|---------|--------|
| Validation Profile 设计 | `32_master_portfolio_assembly.md` | Step 0 策略分型直接对应 profile 选择 |
| V0/V1/V2/V3 要求 | `33_master_validation_pipeline.md` | 强制对照矩阵的必跑版本 |
| Walk-forward/OOS | `35_enhancement_replay_checklist.md` | 增强回放的必跑实验 |
| 容量/成本测试 | `36_data_benchmark_cost_spec.md` | 统一成本口径与压力测试规范 |
| 最终定档 | `38_strategy_admission_oos.md` | Profile 输出进入定档流程 |
| 策略卡片 | `39_strategy_factory_execution_checklist.md` | `validation_profile` 字段映射 |

---

## 9. 实施建议

### 9.1 第一阶段：固化 Profile

1. 建立 `validation_profile.yaml` 模板文件
2. 实现 5 个核心 profile (main_stock_default, main_etf_default, microcap_strict, event_lightweight, satellite_overlay)
3. 在策略卡片模板中加入 `validation_profile` 必填字段

### 9.2 第二阶段：工具化

1. 开发 profile 选择向导（基于策略特征问答推荐 profile）
2. 开发验证任务自动生成器（根据 profile 生成实验列表）
3. 开发 profile 合规检查器（验证输出是否符合 profile 要求）

### 9.3 第三阶段：迭代优化

1. 根据实际策略验证结果调整各 profile 参数
2. 积累误用案例，完善跳过规则和前提条件
3. 按需新增细分 profile（如 `main_stock_defensive` 等）

---

## 10. 关键决策点

| 决策 | 建议 | 理由 |
|-----|------|------|
| microcap 是否必须 walk-forward? | recommended 而非 required | 微盘参数通常较稳定，但强烈建议做 |
| event 是否必须容量测试? | recommended 而非 required | 事件策略容量受限，但非所有事件策略都追求规模 |
| satellite 是否必须 OOS? | required | 即使轻量验证，样本外有效性也必须确认 |
| 成本压力测试点位如何定? | 按策略类型区分 | 主仓5-50bps，微盘10-100bps，事件10-30bps |
| 主仓/ETF 的 V2 是否可跳过? | 不可 | 主仓必须验证装配增强效果 |

---

## 附录：Profile YAML 完整示例

```yaml
# validation_profile.yaml 示例

profiles:
  - profile_id: "main_stock_default"
    profile_name: "股票低频主仓默认"
    strategy_type: "stock_main"
    description: "适用于月频/周频调仓的股票主仓策略"
    v_matrix:
      v0_baseline: true
      v1_unified_spec: true
      v2_assembly_enhanced: true
      v3_full_base: true
    stability:
      walk_forward: "required"
      oos_required: true
      oos_min_periods: 12
      rolling_window: "required"
    cost_capacity:
      cost_stress_test: "required"
      cost_points_bps: [5, 10, 20, 30, 50]
      capacity_test: "required"
      capacity_levels: [500, 1000, 2000, 5000]
    attribution:
      factor_attribution: "required"
      style_attribution: "required"
      sector_attribution: "required"
      specific_return: "required"
    special:
      liquidity_test: "recommended"
      crowding_test: "recommended"
      regime_decomposition: "required"
    skip_rules:
      - condition: "持仓数>100且单票权重<2%"
        applies_to: ["liquidity_test"]
        new_level: "optional"
    minimum_requirements:
      calmar: 0.8
      max_drawdown: 0.25
      sharpe: 0.8

  - profile_id: "microcap_strict"
    profile_name: "微盘严格验证"
    strategy_type: "microcap"
    description: "适用于小市值/微盘暴露策略"
    v_matrix:
      v0_baseline: true
      v1_unified_spec: true
      v2_assembly_enhanced: false
      v3_full_base: true
    stability:
      walk_forward: "recommended"
      oos_required: true
      oos_min_periods: 6
      rolling_window: "required"
    cost_capacity:
      cost_stress_test: "required"
      cost_points_bps: [10, 20, 30, 50, 100]
      capacity_test: "required"
      capacity_levels: [100, 300, 500]
    attribution:
      factor_attribution: "required"
      style_attribution: "required"
      sector_attribution: "required"
      specific_return: "required"
    special:
      liquidity_test: "required"
      crowding_test: "required"
      regime_decomposition: "recommended"
    skip_rules: []
    minimum_requirements:
      calmar: 0.6
      max_drawdown: 0.30
      sharpe: 0.6
      # 微盘门槛适当放宽，但成本压力必须过硬
```
