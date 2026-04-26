# 任务 05：Walk-forward 与滚动 OOS 设计结果

**文档版本**: 1.0  
**日期**: 2026-04-03  
**任务编号**: 05

---

## 一、设计目标与核心原则

### 1.1 设什目标

把 `walkforward/` 设计成**真正可复用的滚动验证组件**，回答清楚：

1. 窗口怎么切（固定、expanding、rolling、最近窗口 OOS）
2. 什么时候算失效（OOS 坍塌判定标准）
3. 结果如何汇总进统一报告（`walkforward_results.csv` 与 `validation_manifest.yaml` 对接）

### 1.2 核心原则

- **拒绝单一 `split_date`**：任何策略都不允许只给出一个训练/测试切分点就结束验证。
- **时间序列尊重**：所有切分必须严格按时间顺序进行，禁止未来函数泄漏。
- **分型适配**：股票低频主仓与事件驱动的窗口设计不同，不能一刀切。
- **可消费性**：`walkforward_results.csv` 必须能被 `reporting/` 和 `admission/` 直接读取，无需二次解析。

---

## 二、四种窗口切分方案详解

### 2.1 固定样本内 / 样本外（Fixed IS/OOS）

**用途**：基线对照（V0-V3）的最低稳定性检查，必须与 walk-forward 并存，不能独立作为唯一验证。

**切分规则**：

```
IS  : [start_date,              split_date]
OOS : [split_date + 1day,       end_date  ]
```

**与 `dataset_config.py` 的区别**：
- 原代码用 `TRAIN_RATIO=0.6` 做单一比例切分，缺乏策略分型意识。
- 本设计要求 `split_date` 由**策略类型**和**数据长度**共同决定，且只在 Fixed IS/OOS 中使用。
- walk-forward 的结果才是主仓 A/B/D 档判断的核心依据。

**推荐 split_date 规则（仅用于 Fixed IS/OOS）**：

| 数据长度 | stock_main 推荐 split | event 推荐 split |
|---------|----------------------|-----------------|
| >= 8 年 | 按 70% IS / 30% OOS | 最近 24 个月或最近 8 个事件 |
| 4-8 年 | 按 75% IS / 25% OOS | 最近 12 个月或最近 4 个事件 |
| < 4 年 | 不强制 Fixed IS/OOS，以 expanding walk-forward 为主 | 最近 2 个事件 |

### 2.2 Expanding Walk-forward

**用途**：最大化利用历史数据训练，模拟"随时间积累经验"的过程，适合参数相对稳定、需要长周期拟合的策略（如股票低频主仓）。

**定义**：
- 初始窗口长度 `W0`
- 步长 `S`
- 每个窗口的 IS 从 `start_date` 开始，逐渐向后扩展
- OOS 紧跟在 IS 之后，长度固定为 `S`（或一个固定 OOS 长度 `L_oos`）

```
Window 1: IS=[start, W0],          OOS=[W0+1, W0+S]
Window 2: IS=[start, W0+S],        OOS=[W0+S+1, W0+2S]
Window 3: IS=[start, W0+2S],       OOS=[W0+2S+1, W0+3S]
...
```

### 2.3 Rolling Walk-forward

**用途**：只使用最近一段历史进行训练，模拟"策略有一定半衰期"的场景，适合对近期数据更敏感的策略（如微盘、动量类策略）。

**定义**：
- IS 长度固定为 `W_is`
- OOS 长度固定为 `S`（或 `L_oos`）
- 整个窗口向后滚动

```
Window 1: IS=[start, W_is],                   OOS=[W_is+1, W_is+S]
Window 2: IS=[start+S, W_is+S],               OOS=[W_is+S+1, W_is+2S]
Window 3: IS=[start+2S, W_is+2S],             OOS=[W_is+2S+1, W_is+3S]
...
```

### 2.4 最近窗口 OOS 监控（Rolling OOS Observation）

**用途**：策略入库后的持续观察，与一次性 walk-forward 验证分离，支撑 38 文档中 D 档（OOS 观察池）的判定和 A/B 档的后续降级预警。

**定义**：
- 以当前日期为锚点，向后滚动回顾最近的 1/3/6/12 个月（或自然季度）表现。
- 每个 OOS 窗口单独计算指标，与样本内最后一个完整窗口的指标对比。

```
锚点: T (当前日期)
OOS-1M : [T-1M, T]
OOS-3M : [T-3M, T]
OOS-6M : [T-6M, T]
OOS-12M: [T-12M, T]
```

**注意**：最近窗口 OOS 不再重新训练，只使用已锁定的最终模型/参数在最新数据上跑回测。

---

## 三、参数建议

### 3.1 最小窗口长度

| 策略类型 | 最小 IS 长度 (expanding) | 最小 IS 长度 (rolling) | 说明 |
|---------|-------------------------|----------------------|------|
| `stock_main` | 36 个月 | 36 个月 | 覆盖完整牛熊周期至少一轮 |
| `etf_main` | 24 个月 | 24 个月 | 跨资产策略数据密度较高 |
| `microcap` | 18 个月 | 12 个月 | 微盘风格切换快，rolling IS 可适当缩短 |
| `event` | 12 个月 或 6 个事件 | 6 个月 或 3 个事件 | 事件样本离散，按事件计数 |
| `satellite` | 12 个月 | 6 个月 | 战术性策略，近期数据权重更高 |

### 3.2 步长建议

| 策略类型 | 推荐步长 | 替代步长 | 说明 |
|---------|---------|---------|------|
| `stock_main` | 3 个月（季度） | 1 个月 | 与主仓常见调仓频率对齐 |
| `etf_main` | 3 个月 | 6 个月 | 资产配置策略换仓较慢 |
| `microcap` | 1 个月 | 2 周 | 微盘换手快，短步长更能捕捉衰退 |
| `event` | 1 个完整事件周期 | 2 个事件周期 | 按事件窗口滚动，不按自然月 |
| `satellite` | 1 个月 | 2 周 | 快速验证战术信号是否仍然有效 |

### 3.3 最少窗口数建议

| 验证类型 | 最少窗口数 | 理想窗口数 | 不达到的 fallback |
|---------|-----------|-----------|------------------|
| Expanding walk-forward | 4 | >= 8 | 改为更短步长或只做 Fixed IS/OOS |
| Rolling walk-forward | 6 | >= 12 | 缩短 rolling IS 长度或改用 expanding |
| 最近 OOS 监控 | 1 | 4 (1M/3M/6M/12M) | 数据不足时只报告可用窗口 |

---

## 四、不同策略类型的窗口设计差异

### 4.1 主仓策略（`stock_main` / `etf_main`）

**特点**：
- 数据连续，时间序列完整
- 需要长周期验证参数稳定性
- 对过拟合极为敏感

**推荐设计**：
- **Primary**: Expanding walk-forward，36 个月起 IS，3 个月步长
- **Secondary**: Rolling walk-forward（与 expanding 并行或二选一），36 个月 rolling IS
- **OOS**: 最近 12 个月 OOS 监控为必跑项

### 4.2 事件策略（`event`）

**特点**：
- 样本离散，不连续，有些月份可能无信号
- 窗口设计应以**事件数**而非自然日为主
- 单次事件持仓周期短（1-10 天）

**推荐设计**：
- ** expanding 不适用直接时间 expanding**，改用"事件批次 expanding"：
  - 按事件批次排序（如财报季、宏观公告批次）
  - IS 累积事件数逐渐增加（如 6 -> 12 -> 18 -> ... 个事件）
  - OOS 为下一批事件（如 2-4 个事件）
- **Rolling 事件窗口**：固定最近 N 个事件作为训练集，预测下 M 个事件
- **OOS**: 最近 3 个完整事件窗口 + 最近 12 个月自然时间 OOS（双轨制）

### 4.3 微盘策略（`microcap`）

**特点**：
- 风格切换快，2017、2021 年后有效性显著变化
- 近期数据往往比远期数据更有代表性

**推荐设计**：
- **Primary**: Rolling walk-forward，18-24 个月 rolling IS，1-3 个月步长
- **Secondary**: Expanding walk-forward 作为对比
- **OOS**: 最近 6 个月 OOS 监控（比主仓更短，因为微盘半衰期短）

### 4.4 卫星策略（`satellite`）

**特点**：
- 择时信号强，参数不是核心，信号有效性是核心
- 可能空仓期较长

**推荐设计**：
- 以 Rolling walk-forward 为主，IS 长度 12 个月，步长 1 个月
- OOS 以最近 3 个月和 6 个月为主

---

## 五、Expanding 与 Rolling 何时各自适用

### 5.1 Expanding 适用场景

1. **历史样本稀缺**：总数据长度 < 6 年，rolling 会导致窗口过少。
2. **参数/模型需要长周期学习**：如机器学习多因子模型、复杂非线性模型。
3. **相信策略逻辑长期稳定**：如价值投资、长期趋势跟踪。
4. **需要最大数据效率**：早期窗口训练数据尽可能多，减少方差。

### 5.2 Rolling 适用场景

1. **市场环境结构性变化大**：如微盘 2021 前后的风格切换，rolling 能更快抛弃旧环境。
2. **策略半衰期短**：动量、事件、卫星类策略。
3. **参数相对简单，短数据即可估计**：如均线参数、简单排序规则。
4. **需要检测"遗忘速度"**：如果 rolling 显著优于 expanding，说明老数据在拖累模型。

### 5.3 组合使用建议

**主仓候选（A 档）必须满足**：
- expanding walk-forward 表现稳定 **且**
- rolling walk-forward 不出现显著坍塌

如果 expanding 很好但 rolling 很差，说明策略过度依赖遥远历史中的旧环境，应降级为 D 档（OOS 观察池）或 C 档（战略辅助）。

---

## 六、最近 1/3/6/12 个月 OOS 接入方案

### 6.1 设计定位

最近窗口 OOS 是**两层体系**：

1. **验证层**：策略入库前，用历史数据模拟"如果我们在最近 1/3/6/12 个月前锁定参数，表现如何"。
2. **监控层**：策略入库后，定期（建议每月/每季度）更新一次最近 OOS 表现，触发预警。

### 6.2 接入方式

在 `walkforward/` 目录中，与一次性 walk-forward 分离，单独输出 `rolling_oos_snapshot.csv`：

```
rolling_oos_snapshot.csv
```

**计算方式**：
- 使用最终锁定的策略参数（V3 版或最终入选版本）
- 不再重新拟合/训练
- 直接滚动回测最近 N 个月
- 每个 N 单独一行

### 6.3 与 38 文档的对应

38 文档要求 OOS 观察重点跟踪：最近 1/3/6/12 个月表现、费后收益、回撤变化、胜率/换手变化、与基线策略相对表现。

本设计将其映射为以下必须字段：

- `oos_1m_return`
- `oos_3m_return`
- `oos_6m_return`
- `oos_12m_return`
- `oos_1m_max_drawdown`
- `oos_3m_max_drawdown`
- `oos_vs_baseline_excess` （最近 12 个月相对 V3 基线的超额）

---

## 七、walkforward_results.csv 字段设计

### 7.1 核心字段（必选）

| 字段名 | 类型 | 说明 |
|-------|------|------|
| `window_id` | string | 示例: `stock_main_jq_001_window_01_expanding` |
| `strategy_id` | string | 策略唯一标识 |
| `version_id` | string | 版本标识，如 `v3` |
| `window_type` | enum | `expanding` / `rolling` / `fixed` / `oos_snapshot` |
| `window_index` | int | 窗口序号，从 1 开始 |
| `is_start_date` | date | 样本内起始日 |
| `is_end_date` | date | 样本内结束日 |
| `oos_start_date` | date | 样本外起始日 |
| `oos_end_date` | date | 样本外结束日 |
| `is_trading_days` | int | 样本内交易日数 |
| `oos_trading_days` | int | 样本外交易日数 |
| `is_annual_return` | float | 样本内年化收益 |
| `oos_annual_return` | float | 样本外年化收益 |
| `is_max_drawdown` | float | 样本内最大回撤 |
| `oos_max_drawdown` | float | 样本外最大回撤 |
| `is_sharpe` | float | 样本内 Sharpe |
| `oos_sharpe` | float | 样本外 Sharpe |
| `is_calmar` | float | 样本内 Calmar |
| `oos_calmar` | float | 样本外 Calmar |
| `is_win_rate` | float | 样本内胜率 |
| `oos_win_rate` | float | 样本外胜率 |
| `is_turnover` | float | 样本内年化换手率 |
| `oos_turnover` | float | 样本外年化换手率 |
| `cost_tier` | string | 成本档位，如 `standard` |
| `after_cost_alpha` | float | 费后 Alpha（OOS） |
| `oos_collapse_flag` | bool | 本窗口是否触发 OOS 坍塌 |
| `collapse_reason` | string | 坍塌原因代码，如 `SHARPE_DROP_MAXDD_SPIKE` |
| `generated_at` | datetime | 结果生成时间 |

### 7.2 扩展字段（强烈建议）

| 字段名 | 类型 | 说明 |
|-------|------|------|
| `is_volatility` | float | 样本内年化波动率 |
| `oos_volatility` | float | 样本外年化波动率 |
| `is_sortino` | float | 样本内 Sortino |
| `oos_sortino` | float | 样本外 Sortino |
| `regime_tag` | string | OOS 期间主导市场状态（牛市/震荡/熊市） |
| `avg_holding_period` | float | OOS 平均持有期 |
| `param_snapshot` | json | 本窗口使用的关键参数快照（防止参数漂移） |

### 7.3 walkforward_summary.csv（每个策略一行，用于 admission/快速消费）

为了统一报告消费方便，除 per-window 的 `walkforward_results.csv` 外，再输出一个 summary 文件：

| 字段名 | 说明 |
|-------|------|
| `strategy_id` | 策略 ID |
| `version_id` | 版本 ID |
| `n_windows_expanding` | expanding 窗口数 |
| `n_windows_rolling` | rolling 窗口数 |
| `mean_oos_annual_return` | 所有 OOS 窗口平均年化收益 |
| `mean_oos_sharpe` | 所有 OOS 窗口平均 Sharpe |
| `mean_oos_max_drawdown` | 所有 OOS 窗口平均 MaxDD |
| `worst_oos_sharpe` | 最差 OOS Sharpe |
| `worst_oos_max_drawdown` | 最差 OOS MaxDD |
| `collapse_window_ratio` | 触发坍塌的窗口占比 |
| `last_12m_oos_return` | 最近 12 个月 OOS 收益 |
| `last_12m_oos_maxdd` | 最近 12 个月 OOS 回撤 |
| `oos_vs_is_sharpe_ratio` | 平均 OOS Sharpe / 平均 IS Sharpe |
| `walkforward_grade` | `strong` / `moderate` / `weak` / `collapsed` |

---

## 八、validation_manifest.yaml 中与窗口相关的配置建议

```yaml
validation_manifest:
  manifest_id: "manifest_stock_main_jq_001_20260403"
  strategy_id: "stock_main_jq_001"
  version_id: "v3"
  
  walkforward:
    enabled: true
    # 本次验证实际使用的窗口方案
    primary_scheme: "expanding"   # expanding | rolling | mixed
    schemes_executed:
      - expanding
      - rolling
    
    # 窗口参数（记录实际使用的参数，便于复现）
    window_params:
      expanding:
        min_is_length_months: 36
        step_months: 3
        min_windows: 4
        actual_windows: 8
      rolling:
        is_length_months: 36
        step_months: 3
        min_windows: 6
        actual_windows: 12
      fixed:
        split_date: "2023-06-30"
        is_ratio: 0.70
    
    # 最近 OOS 监控配置
    recent_oos:
      enabled: true
      observation_points: [1, 3, 6, 12]   # 单位：月
      last_update_date: "2026-04-03"
      snapshot_path: "walkforward/rolling_oos_snapshot.csv"
    
    # 输出文件路径索引
    output_files:
      walkforward_results: "walkforward/walkforward_results.csv"
      walkforward_summary: "walkforward/walkforward_summary.csv"
      window_definitions: "walkforward/walkforward_window_definitions.yaml"
    
    # 与 admission 的对接结论
    admission_input:
      collapse_window_ratio: 0.125   # 12.5% 窗口坍塌
      oos_vs_is_sharpe_ratio: 0.72
      last_12m_oos_return: 0.06
      walkforward_grade: "moderate"
```

### 8.1 配置说明

- `primary_scheme`：在做 A/B/D 档判断时，以哪个方案为主。
- `schemes_executed`：记录本次实际跑了哪些方案，便于审计。
- `window_params`：精确记录每个方案的参数，保证可复现。
- `admission_input`：预计算好 admission 需要的关键统计量，避免 admission 模块重复解析 CSV。

---

## 九、默认窗口模板

### 9.1 模板 A：主仓策略（`stock_main` / `etf_main`）

```yaml
# walkforward/window_templates/main_warehouse_default.yaml
walkforward_window_template:
  template_id: "main_warehouse_default"
  applicable_types: ["stock_main", "etf_main"]
  
  fixed_is_oos:
    enabled: true
    is_ratio: 0.70
    fallback: "当总数据 < 4 年时，关闭 fixed，只用 expanding"
  
  expanding:
    enabled: true
    min_is_length: { months: 36, trading_days_min: 500 }
    step: { months: 3, trading_days_min: 50 }
    min_windows: 4
    oos_length: "same_as_step"   # OOS 长度 = 步长
  
  rolling:
    enabled: true
    is_length: { months: 36, trading_days_min: 500 }
    step: { months: 3, trading_days_min: 50 }
    min_windows: 6
    oos_length: "same_as_step"
  
  recent_oos:
    enabled: true
    points: [1, 3, 6, 12]
    evaluation_mode: "frozen_params"  # 不重新训练
```

### 9.2 模板 B：事件策略（`event`）

```yaml
# walkforward/window_templates/event_driven_default.yaml
walkforward_window_template:
  template_id: "event_driven_default"
  applicable_types: ["event"]
  
  fixed_is_oos:
    enabled: true
    # 事件策略按事件数切分，而非时间比例
    split_rule: "最近 8 个事件作为 OOS，其余为 IS"
    fallback: "当总事件数 < 10 时，改用 expanding_by_event"
  
  expanding_by_event:
    enabled: true
    min_is_events: 6
    step_events: 2
    min_windows: 3
    oos_events: 2
  
  rolling_by_event:
    enabled: true
    is_events: 10
    step_events: 2
    min_windows: 3
    oos_events: 2
  
  recent_oos:
    enabled: true
    # 双轨制：自然时间 + 事件窗口
    time_points: [3, 6, 12]   # 月
    event_points: [2, 4]      # 最近 2 个 / 4 个事件
    evaluation_mode: "frozen_params"
```

### 9.3 模板 C：微盘策略（`microcap`）

```yaml
# walkforward/window_templates/microcap_default.yaml
walkforward_window_template:
  template_id: "microcap_default"
  applicable_types: ["microcap"]
  
  expanding:
    enabled: true
    min_is_length: { months: 24, trading_days_min: 350 }
    step: { months: 1, trading_days_min: 15 }
    min_windows: 6
  
  rolling:
    enabled: true
    is_length: { months: 18, trading_days_min: 260 }
    step: { months: 1, trading_days_min: 15 }
    min_windows: 8
  
  recent_oos:
    enabled: true
    points: [1, 3, 6]   # 微盘半衰期短，12 个月可选
```

---

## 十、OOS 预警规则与降级规则

### 10.1 OOS 坍塌判定标准（定量）

一个 OOS 窗口出现以下任一条件，即判定为**单窗口坍塌**：

| 条件代码 | 判定规则 | 阈值 |
|---------|---------|------|
| `SHARPE_DROP` | `oos_sharpe < is_sharpe * 0.5` | 50% |
| `MAXDD_SPIKE` | `oos_max_drawdown > is_max_drawdown * 1.5` 且绝对值 > 0.15 | 150%，且绝对回撤 > 15% |
| `RETURN_COLLAPSE` | `oos_annual_return < is_annual_return * 0.3` 且 `oos_annual_return < 0` | 30%，且为负 |
| `CALMAR_COLLAPSE` | `oos_calmar < is_calmar * 0.4` | 40% |
| `WIN_RATE_COLLAPSE` | `oos_win_rate < is_win_rate * 0.5` 且 `oos_win_rate < 0.40` | 50%，且 < 40% |

**全策略坍塌判定**（综合多个窗口）：

| 等级 | 判定规则 | 处理方式 |
|-----|---------|---------|
| **Collapsed（已坍塌）** | `collapse_window_ratio >= 0.30` 或 `worst_oos_sharpe < 0` 且 `last_12m_oos_return < 0` | 直接 E 档（淘汰）或 D 档降级观察 |
| **Warning（预警）** | `collapse_window_ratio >= 0.15` 或 `oos_vs_is_sharpe_ratio < 0.60` | D 档（OOS 观察池），需 3 个月内复检 |
| **Moderate（中等）** | `collapse_window_ratio < 0.15` 且 `oos_vs_is_sharpe_ratio >= 0.60` | B 档或 D 档视其他指标而定 |
| **Strong（稳健）** | `collapse_window_ratio == 0` 且 `oos_vs_is_sharpe_ratio >= 0.80` | A 档主仓候选的有力支撑 |

### 10.2 最近 OOS 监控的预警规则

针对 `rolling_oos_snapshot.csv` 中的最近 1/3/6/12 个月数据：

| 预警级别 | 触发条件 | 建议动作 |
|---------|---------|---------|
| **红色（Red）** | 最近 3 个月和 6 个月收益同时为负，且 MaxDD > 15% | 立即暂停该策略主仓仓位，进入 D 档紧急观察 |
| **橙色（Orange）** | 最近 3 个月收益为负 且 最近 12 个月收益低于基准 | 降低权重至辅助/过滤器级别，1 个月内复检 |
| **黄色（Yellow）** | 最近 1 个月收益为负 但 3/6 个月仍为正 | 仅增加关注度，不改变档位 |
| **绿色（Green）** | 所有最近窗口收益为正，OOS Sharpe >= 0.5 | 维持当前档位 |

### 10.3 降级规则（与 38 文档对接）

- **A -> D**：全策略坍塌判定为 Warning 或 Red 预警。
- **A -> B**：OOS 不坍塌，但单独跑不强，叠加后有所改善。
- **B -> D**：recent OOS 出现 Orange 或 Red 预警。
- **D -> E**：连续两次复检（如 3 个月和 6 个月）均显示衰退加剧，无恢复迹象。

---

## 十一、结果汇总与可视化建议

### 11.1 汇总表格（用于统一报告）

**表 1：Walk-forward 总览表**

| 指标 | IS 平均 | OOS 平均 | OOS 最差 | OOS/IS 比值 | 结论 |
|------|--------|---------|---------|------------|------|
| 年化收益 | ... | ... | ... | ... | ... |
| Sharpe | ... | ... | ... | ... | ... |
| MaxDD | ... | ... | ... | ... | ... |
| Calmar | ... | ... | ... | ... | ... |

**表 2：逐窗口明细表（节选）**

| Window | IS 区间 | OOS 区间 | OOS 年化 | OOS Sharpe | OOS MaxDD | 坍塌标记 |
|--------|--------|---------|---------|-----------|----------|---------|
| 01 | 2015-2018 | 2018Q1 | 12% | 0.9 | 8% | No |
| 02 | 2015-2018Q1 | 2018Q2 | -3% | -0.2 | 15% | Yes (SHARPE_DROP) |

**表 3：最近 OOS 监控表**

| 观察窗口 | 区间 | 年化收益 | MaxDD | Sharpe | 相对基准 | 预警级别 |
|---------|------|---------|------|--------|---------|---------|
| 最近 1M | 2026-03 ~ 2026-04 | ... | ... | ... | ... | ... |
| 最近 3M | 2026-01 ~ 2026-04 | ... | ... | ... | ... | ... |

### 11.2 可视化建议

1. **IS vs OOS Sharpe 散点图**：每个窗口一个点，x 轴 IS Sharpe，y 轴 OOS Sharpe，45 度线以下表示 OOS 衰减。
2. **OOS 收益时间序列柱状图**：按窗口顺序展示每个 OOS 期的年化收益，红色标出坍塌窗口。
3. **Expanding vs Rolling 对比折线图**：同一策略两种 walk-forward 方案的 OOS 累积收益曲线对比。
4. **最近 OOS 热力图**：横轴为时间，纵轴为 1M/3M/6M/12M，颜色表示收益或预警级别。

---

## 十二、推荐第一版实现路径

### Phase 1：最小可运行版本（P0）

1. **实现窗口生成器** `walkforward/window_generator.py`
   - 输入：策略类型、数据起止日期、模板参数
   - 输出：窗口列表（IS 起止、OOS 起止、window_id）
   - 支持 expanding / rolling / fixed 三种模式
   - 支持事件策略的"按事件数切分"扩展接口（可先抛出 NotImplemented，但接口预留）

2. **实现 OOS 坍塌判定器** `walkforward/collapse_detector.py`
   - 硬编码 10.1 节中的定量规则
   - 输入：单窗口 IS 指标、OOS 指标
   - 输出：`oos_collapse_flag` + `collapse_reason`

3. **产出默认模板文件**
   - `walkforward/window_templates/main_warehouse_default.yaml`
   - `walkforward/window_templates/microcap_default.yaml`
   - `walkforward/window_templates/event_driven_default.yaml`

4. **产出结果模板**
   - `walkforward/walkforward_results.csv`（含全部核心字段的空模板）
   - `walkforward/walkforward_summary.csv`（空模板）

5. **产出 OOS 观察协议**
   - `walkforward/oos_observation_protocol.yaml`（最近 OOS 监控配置与预警规则）

### Phase 2：与任务 09 对接（P0，见下节）

### Phase 3：可视化与报告集成（P1）

- 在 `reporting/` 中增加 walk-forward 章节渲染函数
- 读取 `walkforward_results.csv` 生成 11.1 节的汇总表格

### Phase 4：自动化监控（P1）

- 将 `rolling_oos_snapshot.csv` 的更新脚本化
- 与 `admission/` 的降级规则联动

---

## 十三、与任务 09 的接口关系

任务 09（假设为**统一报告生成与全链路验收**）是本设计的直接消费方。接口关系如下：

### 13.1 任务 05 -> 任务 09 的输出

| 文件路径 | 任务 09 如何使用 |
|---------|----------------|
| `walkforward/walkforward_results.csv` | 直接读取逐窗口指标，渲染稳定性分解表 |
| `walkforward/walkforward_summary.csv` | 快速提取 collapse_window_ratio、last_12m_oos_return 等关键统计量 |
| `walkforward/rolling_oos_snapshot.csv` | 渲染"最近 OOS 监控表"和预警热力图 |
| `walkforward/oos_observation_protocol.yaml` | 作为报告脚注/附录，说明 OOS 监控规则 |
| `walkforward/walkforward_window_definitions.yaml` | 在报告中展示"本次验证使用的窗口参数"，增强可复现性 |

### 13.2 任务 09 -> 任务 05 的输入

任务 09 不需要向任务 05 回传数据。但如果任务 09 发现报告渲染失败（如字段缺失），应反馈给任务 05 修正 `walkforward_results.csv` 字段设计。

### 13.3 数据流示意

```
数据集 + 策略卡片
      ↓
[walkforward/window_generator.py]  ← 模板配置
      ↓
窗口列表 (IS/OOS 起止)
      ↓
回测引擎 / 验证引擎（任务 09 或外部引擎执行）
      ↓
 walkforward_results.csv
      ↓
[collapse_detector.py] → walkforward_summary.csv + rolling_oos_snapshot.csv
      ↓
[admission/] 定档 (A/B/C/D/E)
      ↓
[reporting/] 任务 09 消费 → 统一验证报告
```

### 13.4 契约版本约定

- 任务 05 保证 `walkforward_results.csv` 的前 28 个核心字段（7.1 节）稳定不变。
- 扩展字段可增加，但不得修改必填核心字段的命名和含义。
- 若发生字段变更，需同步更新 `contracts/validation_manifest_contract.yaml`（任务 01 产出）。

---

## 十四、结论

1. **不再依赖一次性 split**：通过 expanding + rolling 双轨 walk-forward 覆盖所有策略类型；事件策略使用事件窗口替代时间窗口。
2. **支撑 A/B/D 档判断**：通过 `walkforward_summary.csv` 中的 `walkforward_grade`、`collapse_window_ratio`、`last_12m_oos_return` 为 admission 提供定量输入。
3. **可直接被统一报告消费**：`walkforward_results.csv` 字段结构完整对接 `reporting/` 和 `admission/` 的需求。
4. **默认模板已就位**：主仓、微盘、事件三类策略各有独立的 `walkforward_window_template`，避免一刀切。
5. **OOS 坍塌标准已量化**：从单窗口到全策略，从 walk-forward 到最近监控，形成完整的预警与降级链条。

**下一步动作**：进入 Phase 1 实现，优先完成 `window_generator.py`、`collapse_detector.py` 和三个默认模板文件。
