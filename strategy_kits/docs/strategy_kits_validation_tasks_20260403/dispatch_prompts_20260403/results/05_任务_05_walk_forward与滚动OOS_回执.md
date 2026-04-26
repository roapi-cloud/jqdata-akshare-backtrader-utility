# 任务 05 Walk-forward 与滚动 OOS 回执

**日期**: 2026-04-03  
**状态**: 设计完成，可直接进入实现

---

## 1. 推荐的默认窗口模板

### 股票低频主仓 / ETF 主仓

- **Fixed IS/OOS**: 数据 >= 4 年时启用，IS 占 70%（最少 36 个月）
- **Expanding Walk-forward**: IS 起点固定，最小 IS 36 个月，步长 3 个月，最少 4 个窗口
- **Rolling Walk-forward**: IS 长度固定 36 个月，步长 3 个月，最少 6 个窗口
- **Recent OOS**: 必跑 1M / 3M / 6M / 12M

### 事件驱动策略

- **Fixed IS/OOS**: 按事件数切分，最近 8 个事件为 OOS（总事件 < 10 时改用 expanding）
- **Expanding by Event**: 最小 IS 6 个事件，步长 2 个事件，OOS 2 个事件，最少 3 个窗口
- **Rolling by Event**: IS 固定 10 个事件，步长 2 个事件，OOS 2 个事件，最少 3 个窗口
- **Recent OOS**: 双轨制——自然时间 3M / 6M / 12M + 事件窗口 2 个 / 4 个事件

### 微盘策略

- **Expanding**: 最小 IS 24 个月，步长 1 个月，最少 6 个窗口
- **Rolling**: IS 固定 18 个月，步长 1 个月，最少 8 个窗口
- **Recent OOS**: 1M / 3M / 6M（12M 可选，因微盘半衰期短）

---

## 2. OOS 坍塌标准

### 单窗口坍塌（出现任一即触发）

| 条件 | 规则 |
|-----|------|
| **Sharpe 断崖** | `oos_sharpe < is_sharpe * 0.5` |
| **回撤飙升** | `oos_max_drawdown > is_max_drawdown * 1.5` 且绝对值 > 15% |
| **收益崩塌** | `oos_annual_return < is_annual_return * 0.3` 且为负 |
| **Calmar 腰斩** | `oos_calmar < is_calmar * 0.4` |
| **胜率暴跌** | `oos_win_rate < is_win_rate * 0.5` 且 < 40% |

### 全策略坍塌（用于定档）

- **Collapsed（已坍塌）**: 坍塌窗口占比 >= 30% 或最差 OOS Sharpe < 0 且最近 12 个月 OOS 收益 < 0 → **E 档淘汰 或 D 档降级观察**
- **Warning（预警）**: 坍塌占比 >= 15% 或 OOS/IS Sharpe 比值 < 0.6 → **D 档 OOS 观察池**
- **Strong（稳健）**: 坍塌占比为 0 且 OOS/IS Sharpe >= 0.8 → **A 档主仓候选有力支撑**

### 最近 OOS 监控预警

- **红色**: 最近 3M 和 6M 收益同时为负 且 MaxDD > 15% → 立即暂停主仓仓位
- **橙色**: 最近 3M 收益为负 且 最近 12M 跑输基准 → 降权为辅助/过滤器
- **黄色**: 仅最近 1M 为负，3M/6M 为正 → 关注但不改档
- **绿色**: 全部为正 且 OOS Sharpe >= 0.5 → 维持当前档位

---

## 3. walkforward_results.csv 最关键字段

以下 10 个字段是 admission 和统一报告消费的**绝对核心**，第一版必须完整输出：

| 字段 | 用途 |
|-----|------|
| `window_id` | 窗口唯一标识，审计与追踪 |
| `window_type` | expanding / rolling / fixed / oos_snapshot |
| `is_start_date` / `is_end_date` | 样本内区间 |
| `oos_start_date` / `oos_end_date` | 样本外区间 |
| `oos_sharpe` | OOS 风险调整收益 |
| `oos_max_drawdown` | OOS 最大回撤 |
| `oos_annual_return` | OOS 年化收益 |
| `oos_collapse_flag` | 本窗口是否触发坍塌 |
| `collapse_reason` | 坍塌根因代码（如 SHARPE_DROP） |
| `cost_tier` | 成本档位（standard/stress 等） |

此外，`walkforward_summary.csv` 为每个策略输出一行聚合结果，admission 优先消费该文件的 `collapse_window_ratio`、`oos_vs_is_sharpe_ratio`、`last_12m_oos_return`、`walkforward_grade` 四个字段。

---

## 4. 是否可直接进入实现

**是，建议立即进入 Phase 1 实现。**

需要优先完成的 5 个文件：

1. `walkforward/window_generator.py` — 生成 expanding / rolling / fixed 窗口列表
2. `walkforward/collapse_detector.py` — 单窗口坍塌判定
3. `walkforward/window_templates/main_warehouse_default.yaml`
4. `walkforward/window_templates/event_driven_default.yaml`
5. `walkforward/window_templates/microcap_default.yaml`

同时产出 3 个结果模板文件：
- `walkforward/walkforward_results.csv`（含核心字段的空模板）
- `walkforward/walkforward_summary.csv`
- `walkforward/oos_observation_protocol.yaml`

---

## 5. 与任务 09 的接口要点

- 任务 05 向任务 09 输出：`walkforward_results.csv` + `walkforward_summary.csv` + `rolling_oos_snapshot.csv`
- 任务 09 直接读取并渲染稳定性分解表、预警热力图
- 核心字段 28 列已锁定，扩展可增加但不可改必填字段命名/含义
