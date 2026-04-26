# 任务06：成本 / 容量 / 滑点压力测试模板

## 文档定位

为 `stress/` 目录提供实盘脆弱性验证模板，确保策略验证不停留在单一成本假设下的"漂亮结果"。这是 `36_data_benchmark_cost_spec.md` 的深度扩展，定义三类压力维度与定档规则。

---

## 一、压力维度定义

### 1.1 成本BPS压力（第一类压力）

**标准成本档位建议**：

| 档位 | 单边佣金 | 单边滑点 | 冲击成本 | 单边总成本 | 双边总成本 | 适用场景 |
|------|----------|----------|----------|-----------|-----------|----------|
| **5 bps** | 0.03% (3bps) | 0.02% (2bps) | 0 | 5 bps | 10 bps | ETF主仓/理想场景 |
| **10 bps** | 0.03% (3bps) | 0.07% (7bps) | 0 | 10 bps | 20 bps | 股票主仓标准 |
| **20 bps** | 0.03% (3bps) | 0.17% (17bps) | 0 | 20 bps | 40 bps | 股票主仓压力 |
| **30 bps** | 0.03% (3bps) | 0.27% (27bps) | 0 | 30 bps | 60 bps | 微盘/小票压力 |
| **50 bps** | 0.03% (3bps) | 0.47% (47bps) | 0 | 50 bps | 100 bps | 微盘极限测试 |

**成本构成公式**：
```python
total_cost_bps = commission_bps + slippage_bps + impact_bps + opportunity_cost_bps

# 其中：
# - commission_bps: 固定3bps（券商佣金）
# - slippage_bps: 根据策略类型设定（2/7/17/27/47 bps）
# - impact_bps: 根据成交量占比动态计算
# - opportunity_cost_bps: 停牌/涨跌停无法成交的隐性成本
```

**关键说明**：
- 表中单边总成本 = 佣金 + 滑点 + 冲击成本
- 双边总成本 = 2 × 单边总成本（买入+卖出）
- **必须至少测试5/10/20/30 bps四个档位**
- 微盘策略必须增加50 bps极限档位

### 1.2 滑点/成交价口径压力（第二类压力）

**成交价口径矩阵**：

| 口径类型 | 描述 | 滑点假设 | 适用场景 | 必测策略 |
|---------|------|---------|---------|---------|
| `next_open` | 下一交易日开盘价成交 | 固定或按波动率调整 | 日频策略默认 | 所有策略必测 |
| `vwap_like` | 成交量加权平均价成交 | 接近真实执行成本 | 大资金/高换手 | 主仓必测 |
| `close_like` | 当日收盘价成交 | 理想假设需加成本 | 快速调仓策略 | 事件策略建议测 |
| `twap_like` | 日内时间加权平均价 | 分批执行模拟 | 大额调仓 | 大资金建议测 |
| `limit_fill` | 限价单成交模拟 | 需定义挂单价位与成交率 | 精细化执行 | 高级功能 |

**成交价敏感性指标**：

```python
# 滑点脆弱性得分
slippage_vulnerability = (return_next_open - return_close_like) / abs(return_close_like)

# 口径差异衰减率
execution_decay_rate = (sharpe_next_open - sharpe_vwap_like) / sharpe_next_open

# 判断标准
if slippage_vulnerability > 0.3:
    mark_as("滑点敏感策略")
if execution_decay_rate > 0.2:
    mark_as("成交价口径脆弱")
```

**必须测试的口径组合**：
- **股票主仓**：`next_open` + `vwap_like`
- **微盘策略**：`next_open` + `close_like`（检验隔夜风险）
- **小票事件**：`next_open`（事件后首次开盘）
- **ETF主仓**：`close_like` + `vwap_like`

### 1.3 容量/成交率/Partial Fill压力（第三类压力）

**成交率测试档位**：

| 成交率 | 描述 | 测试方法 | 适用策略 |
|--------|------|---------|---------|
| **100%** | 理想成交 | 所有订单完全成交 | 基线场景 |
| **95%** | 轻度partial fill | 未成交5%延后或放弃 | ETF主仓压力 |
| **90%** | 标准压力 | 未成交10%延后或放弃 | 主仓压力场景 |
| **80%** | 中度压力 | 未成交20%延后或放弃 | 微盘压力场景 |
| **60%** | 重度压力 | 未成交40%延后或放弃 | 微盘极限场景 |
| **40%** | 流动性危机 | 仅成交40%，其余放弃 | 微盘崩溃测试 |

**Partial Fill处理逻辑**：

```python
# 逻辑1：延后执行（适用于日内可多次执行策略）
def delay_execution(unfilled_weight, delay_days):
    if delay_days > 0:
        # 未成交部分下一交易日继续尝试
        target_weight_t+1 += unfilled_weight

# 逻辑2：放弃执行（适用于低频调仓策略）
def abandon_execution(unfilled_weight):
    # 未成交部分直接放弃，保留现金
    cash_weight += unfilled_weight

# 逻辑3：部分执行+平均成本（适用于多次成交）
def partial_execution_with_avg_cost(fill_rate):
    # 按成交量加权计算平均成交价
    avg_price = sum(price_i * volume_i) / total_volume
```

**容量上限测试**：

| 容量维度 | 测试档位 | 计算方式 |
|---------|----------|---------|
| **单票成交上限** | 当日成交额的 5% / 2% / 1% / 0.5% / 0.2% | 单票最大成交金额限制 |
| **组合调仓上限** | 5000万 / 2000万 / 1000万 / 500万 | 单日组合最大调仓金额 |
| **持仓集中度上限** | 单票最大权重 10% / 5% / 2% | 防止过度集中 |
| **流动性过滤** | 仅交易前20% / 10% / 5%流动性股票 | 流动性最低要求 |

**容量衰减曲线测试**：

```python
# 测试不同AUM下的策略表现
aum_levels = [0.5亿, 1亿, 2亿, 5亿, 10亿, 20亿, 50亿]

for aum in aum_levels:
    impact_cost = estimate_impact_cost(aum, turnover_rate)
    sharpe_at_aum = compute_sharpe_with_impact(impact_cost)
    
# 找到Sharpe衰减超过50%的AUM阈值
capacity_limit = find_decay_threshold(sharpe_curve, threshold=0.5)
```

---

## 二、不同策略类型的最低要求

### 2.1 股票低频主仓（大盘股为主）

**必须完成**：

| 压力维度 | 必须档位 | 说明 |
|---------|---------|------|
| 成本BPS | 5 / 10 / 20 / 30 bps | 四档必跑 |
| 成交价口径 | `next_open` + `vwap_like` | 两种口径必比 |
| 成交率 | 100% / 90% / 80% | 三档必跑 |
| 资金规模 | 1亿 / 5亿 / 10亿 / 50亿 | 至少四个规模档位 |

**建议增加**：
- 市场状态分解（牛市/震荡/下跌下成本敏感性）
- 换手率敏感性测试（降低换手是否能改善成本后表现）

**通过标准**：
- 30 bps成本下Sharpe > 1.0
- 30 bps成本下年化收益 > 0%
- 80%成交率下收益衰减 < 30%
- 容量上限 > 10亿

### 2.2 微盘/小市值策略（最严格）

**必须完成**（完整压力矩阵）：

| 压力维度 | 必须档位 | 说明 |
|---------|---------|------|
| 成本BPS | 20 / 30 / 50 bps | 三档必跑，增加50bps极限档 |
| 成交价口径 | `next_open` + `close_like` + `vwap_like` | 三种口径全跑 |
| 成交率 | 100% / 90% / 80% / 60% / 40% | 五档全跑（最严格） |
| Partial Fill延迟 | 0天 / 1天 / 2天 / 3天 | 四档全跑 |
| 单票容量上限 | 当日成交额 2% / 1% / 0.5% / 0.2% | 四档全跑 |
| 组合调仓上限 | 5000万 / 2000万 / 500万 | 三档全跑 |
| 资金规模 | 0.5亿 / 1亿 / 2亿 / 5亿 / 10亿 | 五档全跑，绘制容量衰减曲线 |

**必须报告**：
- 容量衰减曲线（AUM vs Sharpe）
- 成交率敏感性分析（fill_rate vs return）
- 流动性危机模拟（假设某日完全无法成交）
- Partial Fill两种处理逻辑对比（延后 vs 放弃）

**通过标准**：
- 30 bps成本下Sharpe > 0.8
- 30 bps成本下年化收益 > 5%
- 60%成交率下收益衰减 < 40%
- Partial Fill延迟3天收益下降 < 30%
- 容量上限 > 2亿

### 2.3 小票事件策略

**必须完成**：

| 压力维度 | 必须档位 | 说明 |
|---------|---------|------|
| 成本BPS | 20 / 30 / 50 bps | 三档必跑 |
| 成交价口径 | `next_open`（事件后首次开盘） | 必测 |
| 成交率 | 100% / 90% / 75% | 三档必跑 |
| 事件集中度 | 单事件占比 <5% / 5-10% / >10% | 三档必跑 |
| 事件窗口执行 | T+0可执行 vs T+1执行 | 对比测试 |

**建议增加**：
- 事件拥挤度测试（多策略同时触发）
- limit_fill模拟（挂单价差±1%/±2%）
- 事件后流动性分层（大盘事件 vs 小盘事件）

**通过标准**：
- 30 bps成本下Sharpe > 1.0
- 75%成交率下收益衰减 < 40%
- 事件集中度>10%时收益衰减 < 20%
- 容量上限 > 5亿

### 2.4 ETF/多资产主仓

**必须完成**：

| 压力维度 | 必须档位 | 说明 |
|---------|---------|------|
| 成本BPS | 5 / 10 / 20 bps | 三档必跑 |
| 成交价口径 | `close_like` + `vwap_like` | 两种口径必比 |
| 成交率 | 100% / 95% / 90% | 三档必跑 |
| 资金规模 | 10亿 / 50亿 / 100亿 / 200亿 | 至少四个规模档位 |

**建议增加**：
- 大额申购赎回冲击成本
- ETF折溢价影响
- 跨资产流动性差异

**通过标准**：
- 20 bps成本下Sharpe > 1.2
- 90%成交率下收益衰减 < 15%
- 容量上限 > 50亿

---

## 三、默认压力矩阵

### 3.1 股票主仓完整压力矩阵

```csv
场景编号,成本BPS,成交价口径,成交率,资金规模(亿),必须跑
baseline_0,0,next_open,100,1,Yes
standard_10,10,next_open,100,1,Yes
pressure_20,20,next_open,100,1,Yes
extreme_30,30,next_open,100,1,Yes
vwap_10,10,vwap_like,100,1,Yes
vwap_20,20,vwap_like,100,1,Yes
fill90_10,10,next_open,90,1,Yes
fill80_10,10,next_open,80,1,Yes
aum_5,10,next_open,100,5,Recommended
aum_10,10,next_open,100,10,Yes
aum_50,10,next_open,100,50,Recommended
```

### 3.2 微盘策略完整压力矩阵（最严格）

```csv
场景编号,成本BPS,成交价口径,成交率,Partial Fill延迟(天),单票容量上限,资金规模(亿),必须跑
baseline_0,0,next_open,100,0,无限制,0.5,Yes
standard_20,20,next_open,100,0,无限制,0.5,Yes
pressure_30,30,next_open,100,0,无限制,0.5,Yes
extreme_50,50,next_open,100,0,无限制,0.5,Yes
close_20,20,close_like,100,0,无限制,0.5,Yes
vwap_20,20,vwap_like,100,0,无限制,0.5,Yes
fill90_20,20,next_open,90,0,无限制,0.5,Yes
fill80_20,20,next_open,80,0,无限制,0.5,Yes
fill60_20,20,next_open,60,0,无限制,0.5,Yes
fill40_20,20,next_open,40,0,无限制,0.5,Yes
delay1_20,20,next_open,100,1,无限制,0.5,Yes
delay2_20,20,next_open,100,2,无限制,0.5,Yes
delay3_20,20,next_open,100,3,无限制,0.5,Yes
cap_2pct,20,next_open,100,0,2%,0.5,Yes
cap_1pct,20,next_open,100,0,1%,0.5,Yes
cap_0.5pct,20,next_open,100,0,0.5%,0.5,Yes
cap_0.2pct,20,next_open,100,0,0.2%,0.5,Yes
aum_1,20,next_open,100,0,无限制,1,Yes
aum_2,20,next_open,100,0,无限制,2,Yes
aum_5,20,next_open,100,0,无限制,5,Yes
aum_10,20,next_open,100,0,无限制,10,Yes
```

### 3.3 小票事件策略压力矩阵

```csv
场景编号,成本BPS,成交价口径,成交率,事件集中度,必须跑
baseline_0,0,next_open,100,分散,Yes
standard_20,20,next_open,100,分散,Yes
pressure_30,30,next_open,100,分散,Yes
extreme_50,50,next_open,100,分散,Yes
fill90_20,20,next_open,90,分散,Yes
fill75_20,20,next_open,75,分散,Yes
concentration_low,20,next_open,100,<5%,Yes
concentration_medium,20,next_open,100,5-10%,Yes
concentration_high,20,next_open,100,>10%,Yes
t0_vs_t1,20,next_open,100,T+0,Recommended
t1_execution,20,next_open,100,T+1,Yes
```

### 3.4 ETF主仓压力矩阵

```csv
场景编号,成本BPS,成交价口径,成交率,资金规模(亿),必须跑
baseline_0,0,close_like,100,10,Yes
ideal_5,5,close_like,100,10,Yes
standard_10,10,close_like,100,10,Yes
pressure_20,20,close_like,100,10,Yes
vwap_10,10,vwap_like,100,10,Yes
vwap_20,20,vwap_like,100,10,Yes
fill95_10,10,close_like,95,10,Yes
fill90_10,10,close_like,90,10,Yes
aum_50,10,close_like,100,50,Yes
aum_100,10,close_like,100,100,Recommended
aum_200,10,close_like,100,200,Yes
```

---

## 四、stress_results.csv字段设计

### 4.1 完整字段列表

```csv
# === 基础标识字段 ===
strategy_id,strategy_name,strategy_type,test_date,stress_scenario_id,

# === 压力参数字段 ===
cost_bps_single,cost_bps_bilateral,commission_bps,slippage_bps,impact_bps,opportunity_cost_bps,
execution_price_type,fill_rate_pct,partial_fill_delay_days,
single_stock_capacity_pct,portfolio_capacity_cny_m,liquidity_filter_pct,
aum_cny_bn,event_concentration_pct,

# === 基线表现字段（费前） ===
baseline_annual_return,baseline_sharpe,baseline_calmar,baseline_max_dd,
baseline_turnover,baseline_win_rate,baseline_avg_holding_days,baseline_trade_count,

# === 压力场景表现字段（费后） ===
annual_return_gross,annual_return_net,sharpe_gross,sharpe_net,
calmar_gross,calmar_net,max_dd_gross,max_dd_net,
win_rate_gross,win_rate_net,avg_holding_days_gross,avg_holding_days_net,trade_count,

# === 成本敏感度指标 ===
cost_drag_bps,cost_decay_return_pct,cost_decay_sharpe_pct,
slippage_vulnerability,execution_decay_rate,fill_sensitivity,

# === 容量与成交率指标 ===
actual_fill_rate_pct,capacity_utilization_pct,daily_turnover_avg,
avg_trade_size_cny,impact_cost_actual_bps,

# === 样本切分字段 ===
sample_in_start,sample_in_end,sample_oos_start,sample_oos_end,
is_sample_in,is_sample_oos,

# === 分档结论字段 ===
stress_grade,pass_flag,recommended_action,notes
```

### 4.2 关键字段计算方式

| 字段 | 计算公式 | 说明 |
|------|---------|------|
| `cost_bps_bilateral` | `2 * cost_bps_single` | 双边总成本 |
| `cost_drag_bps` | `turnover * cost_bps_bilateral` | 成本拖累 |
| `cost_decay_return_pct` | `(baseline_return - net_return) / baseline_return * 100` | 收益衰减率 |
| `cost_decay_sharpe_pct` | `(baseline_sharpe - net_sharpe) / baseline_sharpe * 100` | Sharpe衰减率 |
| `slippage_vulnerability` | `(ret_next_open - ret_close_like) / abs(ret_close_like)` | 滑点脆弱性 |
| `execution_decay_rate` | `(sharpe_next_open - sharpe_vwap_like) / sharpe_next_open` | 口径差异衰减 |
| `fill_sensitivity` | `(sharpe_fill_rate_X - sharpe_fill_100) / (100 - X)` | 成交率敏感性 |
| `capacity_utilization_pct` | `actual_aum / capacity_limit * 100` | 容量利用率 |

---

## 五、失败阈值建议

### 5.1 成本压力失败阈值

| 策略类型 | 成本档位 | 收益衰减阈值 | Sharpe衰减阈值 | 失败判定 |
|---------|----------|-------------|---------------|---------|
| 股票主仓 | 20 bps | >30% | >25% | 进入OOS（一级坍塌） |
| 股票主仓 | 30 bps | >50% | >40% | 降档（二级坍塌） |
| 微盘策略 | 30 bps | >40% | >30% | 进入OOS（一级坍塌） |
| 微盘策略 | 50 bps | >60% | >50% | 降档或淘汰（二级坍塌） |
| 小票事件 | 30 bps | >40% | >35% | 进入OOS（一级坍塌） |
| 小票事件 | 50 bps | >60% | >50% | 降档或淘汰（二级坍塌） |
| ETF主仓 | 10 bps | >20% | >15% | 进入OOS（一级坍塌） |
| ETF主仓 | 20 bps | >35% | >25% | 降档（二级坍塌） |

### 5.2 成交率压力失败阈值

| 成交率档位 | 收益衰减阈值 | 失败判定 |
|-----------|-------------|---------|
| 90% | >25% | 进入OOS（一级坍塌） |
| 80% | >40% | 降档（二级坍塌） |
| 60% | 收益为负 | 淘汰（三级坍塌） |
| 40% | 收益为负 | 淘汰（三级坍塌） |

### 5.3 容量压力失败阈值

| 策略类型 | 容量上限 | 当前AUM警告阈值 | 失败判定 |
|---------|---------|----------------|---------|
| 股票主仓 | <10亿 | >8亿（利用率>80%） | 降档 |
| 微盘策略 | <2亿 | >1.5亿（利用率>75%） | 降档 |
| 小票事件 | <5亿 | >4亿（利用率>80%） | 降档 |
| ETF主仓 | <50亿 | >40亿（利用率>80%） | 降档 |

### 5.4 成交价口径失败阈值

| 口径差异 | 收益差异阈值 | Sharpe差异阈值 | 失败判定 |
|---------|-------------|---------------|---------|
| next_open vs vwap_like | >20% | >15% | 进入OOS（一级坍塌） |
| next_open vs close_like | >30% | >20% | 进入OOS（一级坍塌） |
| 任意口径vs理想假设 | >50% | >40% | 降档或淘汰（二级坍塌） |

### 5.5 Partial Fill延迟失败阈值

| 延迟天数 | 收益下降阈值 | 失败判定 |
|---------|-------------|---------|
| 1天 | >20% | 进入OOS（一级坍塌） |
| 2天 | >30% | 降档（二级坍塌） |
| 3天 | >40% | 淘汰（三级坍塌） |

---

## 六、压力结论分档模板

### 6.1 五档分级标准

**A档：坚韧（Robust）**
- 30 bps成本下Sharpe > 1.0，Calmar > 1.5
- 80%成交率下收益衰减 < 30%
- 口径差异衰减 < 20%
- 容量上限 > 10亿（主仓）或 > 2亿（微盘）
- 样本内外成本敏感性一致
- **去向**：主仓候选

**B档：可用（Moderate）**
- 20 bps成本下Sharpe > 1.0
- 30 bps成本下年化收益 > 0%
- 90%成交率下收益衰减 < 30%
- 口径差异衰减 < 30%
- 容量上限 > 5亿（主仓）或 > 1亿（微盘）
- **去向**：过滤器候选或限制容量使用

**C档：脆弱（Fragile）**
- 10 bps成本下Sharpe > 0.5
- 20 bps成本下收益衰减 > 50%
- 80%成交率下收益衰减 > 40%
- 口径差异衰减 > 30%
- 容量上限 < 5亿（主仓）
- **去向**：战略辅助模块，限制使用场景

**D档：观察（Watch）**
- 5 bps成本下有效但高成本失效
- 成本盈亏平衡点 < 20 bps
- 样本外成本敏感性 > 样本内1.5倍
- **去向**：OOS观察池，持续监控

**E档：淘汰（Rejected）**
- 任意成本下无正收益
- 成本盈亏平衡点 < 10 bps
- 即使5 bps成本下Sharpe < 0.5
- **去向**：淘汰或挂起

### 6.2 成本后坍塌判断

**三级坍塌定义**：

**一级坍塌（进入OOS）**：
- 满足以下任一条件：
  1. 收益衰减：20 bps成本下收益衰减 > 30%
  2. Sharpe衰减：20 bps成本下Sharpe衰减 > 25%
  3. 成交率敏感：90%成交率下收益衰减 > 25%
  4. 口径差异：next_open vs vwap_like收益差异 > 20%
  5. 样本外恶化：样本外成本敏感性 > 样本内1.5倍

**二级坍塌（降档处理）**：
- 满足以下任一条件：
  1. 收益坍塌：30 bps成本下收益衰减 > 50%
  2. Sharpe坍塌：30 bps成本下Sharpe衰减 > 40%
  3. 成交率崩溃：80%成交率下收益衰减 > 40%
  4. 容量不足：实际AUM > 容量上限80%
  5. Partial Fill延迟：延迟2天收益下降 > 30%
  6. 盈亏平衡过低：成本盈亏平衡点 < 15 bps

**三级坍塌（直接淘汰）**：
- 满足以下任一条件：
  1. 极端成本失效：50 bps成本下年化收益为负
  2. 成交率崩溃：60%成交率下收益为负
  3. 容量极小：容量上限 < 5亿（主仓）或 < 2亿（微盘）
  4. 盈亏平衡崩溃：成本盈亏平衡点 < 10 bps
  5. 样本外完全失效：样本外费后收益为负

### 6.3 自动降档规则

```python
def auto_downgrade(stress_results):
    baseline_sharpe = stress_results['baseline_sharpe']
    
    # 三级坍塌检测
    if (stress_results['annual_return_50bps'] < 0 or 
        stress_results['annual_return_fill60'] < 0 or
        stress_results['break_even_cost'] < 10):
        return 'E档', '淘汰', '成本后三级坍塌'
    
    # 二级坍塌检测
    if (stress_results['cost_decay_sharpe_30bps'] > 40 or
        stress_results['cost_decay_return_30bps'] > 50 or
        stress_results['fill_decay_80'] > 40 or
        stress_results['capacity_utilization'] > 80):
        return 'C档', '降档', '成本后二级坍塌'
    
    # 一级坍塌检测
    if (stress_results['cost_decay_sharpe_20bps'] > 25 or
        stress_results['cost_decay_return_20bps'] > 30 or
        stress_results['fill_decay_90'] > 25 or
        stress_results['execution_decay'] > 20):
        return 'D档', '进入OOS', '成本后一级坍塌'
    
    # 正常分档
    if stress_results['sharpe_30bps'] > 1.0 and stress_results['calmar_30bps'] > 1.5:
        return 'A档', '主仓候选', '成本坚韧'
    elif stress_results['sharpe_20bps'] > 1.0 and stress_results['annual_return_30bps'] > 0:
        return 'B档', '过滤器候选', '成本可用'
    else:
        return 'C档', '战略辅助', '成本脆弱'
```

---

## 七、压力测试结果进入统一报告

### 7.1 与33_master_validation_pipeline.md的衔接

在33的三层报告中，压力测试属于**第二层：增强版对照报告**的扩展版本：

```
V0 原策略（费前基准）
V1 原策略 + 数据/成本统一口径（10bps标准成本）
V2 原策略 + 主仓装配增强
V3 原策略 + 完整执行底座

+ V2-stress-5bps（低成本场景）
+ V2-stress-10bps（标准场景）
+ V2-stress-20bps（压力场景）
+ V2-stress-30bps（极端场景）
+ V2-stress-vwap（成交价口径测试）
+ V2-stress-fill80（成交率测试）
+ V2-stress-aum10（容量测试）
```

### 7.2 与38_strategy_admission_oos.md的定档衔接

压力测试结果直接影响38的五级定档：

| 压力表现 | 建议档位 | 说明 |
|----------|----------|------|
| A档（坚韧） | 主仓候选（38-A档） | 30bps下仍满足主仓标准 |
| B档（可用） | 过滤器候选（38-B档） | 20bps下满足，可限制容量 |
| C档（脆弱） | 战略辅助（38-C档） | 仅低成本下有效，限制场景 |
| D档（观察） | OOS观察池（38-D档） | 成本敏感需持续观察 |
| E档（淘汰） | 淘汰/挂起（38-E档） | 成本后无优势 |

### 7.3 统一报告中的压力测试表格

在主报告的`B. 稳定性分解`部分新增：

```markdown
### B. 压力成本对照表

| 版本 | 年化收益 | Sharpe | Calmar | 成本BPS | 成交率 | 资金规模 | 收益衰减 | Sharpe衰减 | 结论 |
|------|---------|--------|--------|---------|--------|---------|---------|-----------|------|
| V2-标准 | 15% | 1.2 | 2.0 | 10 | 100% | 1亿 | - | - | 基线 |
| V2-低压 | 18% | 1.4 | 2.3 | 5 | 100% | 1亿 | +20% | +17% | 成本敏感 |
| V2-中压 | 10% | 0.9 | 1.3 | 20 | 100% | 1亿 | -33% | -25% | 可用 |
| V2-高压 | 5% | 0.5 | 0.7 | 30 | 100% | 1亿 | -67% | -58% | 脆弱 |
| V2-vwap | 8% | 0.7 | 1.0 | 10 | 100% | 1亿 | -47% | -42% | 口径敏感 |
| V2-fill80 | 8% | 0.8 | 1.1 | 10 | 80% | 1亿 | -47% | -33% | 容量限制 |
| V2-aum50 | 3% | 0.3 | 0.4 | 10 | 100% | 50亿 | -80% | -75% | 容量不足 |
```

---

## 八、第一版最小实现建议

### 8.1 Phase 1：核心成本压力（2周）

**优先级：最高**

**实现内容**：
1. 支持5/10/20/30/50 bps五档成本切换
2. 计算并输出：
   - `cost_decay_return_pct`
   - `cost_decay_sharpe_pct`
   - `break_even_cost_bps`
3. 实现自动分档逻辑
4. 输出stress_results.csv

**代码实现示例**：

```python
class CostStressTester:
    def __init__(self, strategy_returns, turnover_series):
        self.returns = strategy_returns
        self.turnover = turnover_series
    
    def apply_cost(self, cost_bps_single):
        """应用交易成本"""
        cost_bps_bilateral = 2 * cost_bps_single
        daily_cost = self.turnover * (cost_bps_bilateral / 10000.0)
        net_returns = self.returns - daily_cost
        return net_returns
    
    def run_cost_stress(self, cost_levels=[5,10,20,30,50]):
        """运行成本压力测试"""
        baseline_sharpe = compute_sharpe(self.returns)
        results = []
        
        for cost in cost_levels:
            net_returns = self.apply_cost(cost)
            sharpe_net = compute_sharpe(net_returns)
            return_net = compute_annual_return(net_returns)
            
            decay_return = (baseline_return - return_net) / baseline_return * 100
            decay_sharpe = (baseline_sharpe - sharpe_net) / baseline_sharpe * 100
            
            results.append({
                'cost_bps_single': cost,
                'cost_bps_bilateral': 2 * cost,
                'annual_return_net': return_net,
                'sharpe_net': sharpe_net,
                'cost_decay_return_pct': decay_return,
                'cost_decay_sharpe_pct': decay_sharpe
            })
        
        return pd.DataFrame(results)
```

### 8.2 Phase 2：成交价口径（1周）

**优先级：高**

**实现内容**：
1. 实现next_open/vwap_like/close_like三种执行模型
2. 计算slippage_vulnerability和execution_decay_rate
3. 对比不同口径下的策略表现

**实现要点**：
- 扩展`execution_engine.py`的`_calculate_slippage_limit`函数
- 支持动态滑点函数（基于波动率、流动性）

### 8.3 Phase 3：容量与成交率（2周）

**优先级：中**

**实现内容**：
1. 实现成交率模拟（100%/90%/80%/60%/40%）
2. 实现Partial Fill延迟模拟（延后/放弃两种逻辑）
3. 实现容量上限测试（单票容量、组合容量）
4. 绘制容量衰减曲线

**实现要点**：
- 扩展`execution_engine.py`的订单拆分逻辑
- 支持多种Partial Fill处理策略
- 计算impact_cost并纳入总成本

### 8.4 Phase 4：集成与报告（1周）

**优先级：高**

**实现内容**：
1. 集成到33_master_validation_pipeline.md
2. 集成到38_strategy_admission_oos.md
3. 自动化报告生成（Markdown/HTML）
4. 可视化关键指标（成本衰减曲线、容量曲线）

**集成点**：
- 在33的B部分增加压力测试表格
- 在38的分档逻辑中引用压力测试结论
- 生成独立的压力测试报告

### 8.5 最小可运行命令

```bash
# Phase 1：成本压力测试
python run_stress_test.py \
    --strategy_id my_strategy \
    --cost_levels "5,10,20,30,50" \
    --output stress_results.csv

# Phase 2：成交价口径测试
python run_stress_test.py \
    --strategy_id my_strategy \
    --execution_models "next_open,vwap_like,close_like" \
    --cost_levels "10,20"

# Phase 3：微盘完整压力测试
python run_stress_test.py \
    --strategy_id microcap_strategy \
    --strategy_type microcap \
    --cost_levels "20,30,50" \
    --execution_models "next_open,close_like,vwap_like" \
    --fill_rates "100,90,80,60,40" \
    --partial_fill_delays "0,1,2,3" \
    --capacity_limits "2pct,1pct,0.5pct,0.2pct" \
    --aum_levels "0.5,1,2,5,10"
```

---

## 九、关键指标参考阈值

### 9.1 成本后韧性指标

| 指标 | 优秀 | 及格 | 不及格 |
|------|------|------|--------|
| cost_decay_return_pct | < 30% | < 50% | >= 50% |
| cost_decay_sharpe_pct | < 25% | < 40% | >= 40% |
| slippage_vulnerability | < 0.3 | < 0.5 | >= 0.5 |
| execution_decay_rate | < 0.15 | < 0.25 | >= 0.25 |
| fill_sensitivity | < 0.2 | < 0.4 | >= 0.4 |
| break_even_cost_bps | > 30 | > 15 | < 15 |

### 9.2 微盘策略特殊阈值

| 指标 | 优秀 | 及格 | 不及格 |
|------|------|------|--------|
| 30bps下年化收益 | > 10% | > 5% | <= 5% |
| fill_60%下收益保持率 | > 70% | > 50% | <= 50% |
| partial fill延迟2天收益下降 | < 20% | < 30% | >= 30% |
| 容量上限 | > 5亿 | > 2亿 | < 2亿 |
| capacity_utilization_pct | < 50% | < 75% | > 75% |

---

## 十、总结

### 必须记住的三个原则

1. **没有压力测试的策略结果不能用于定档**
2. **微盘策略必须通过最严格的容量测试**（完整压力矩阵）
3. **成本后坍塌的策略必须进入OOS或淘汰**

### 核心贡献

1. **三类压力清晰定义**：成本BPS、滑点/成交价口径、容量/成交率/Partial Fill
2. **标准成本档位明确**：5/10/20/30 bps四个档位必须测试
3. **策略类型差异化**：股票主仓、微盘、小票事件、ETF主仓各有最低要求
4. **失败阈值量化**：三级坍塌判断标准明确
5. **结果纳入统一报告**：与33、38无缝衔接
6. **最小实现路径清晰**：分四阶段实施，优先核心功能

### 下一步行动

1. 立即启动Phase 1实现（成本压力测试）
2. 为微盘策略建立独立的高压力测试流程
3. 将压力测试结果自动映射到38的定档流程
4. 建立压力测试结果数据库（stress_results.csv）

---

## 关联文档

| 文档 | 作用 |
|------|------|
| `33_master_validation_pipeline.md` | 统一报告框架，压力测试纳入第二层 |
| `36_data_benchmark_cost_spec.md` | 成本口径基础，扩展压力场景 |
| `38_strategy_admission_oos.md` | 定档与OOS接续，引用压力测试结论 |
| `execution_engine.py` | 执行引擎参考，扩展滑点与成交率 |
| `run_event_backtest.py` | 回测成本计算基础 |