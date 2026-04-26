# 任务 02 主结果：交易日历与基础池选择器抽取

## 一、参考源现状分析

### 1.1 聚宽侧实现（skills/joinquant_strategy/）

- **交易日历**：依赖平台内置 `get_trade_days(start, end, count=None)`，各策略直接使用，无统一封装。
- **基础池获取**：
  - `get_all_securities("stock", date)` → 全A股票池
  - `get_index_stocks("000300.XSHG", date=date)` → 指数成分股
  - 各策略重复写 `not s.startswith("688")`、IPO 天数过滤、ST 过滤等逻辑。
- **调仓日**：依赖 `run_monthly(rebalance, 1, time="9:35")` 或 `run_weekly(rebalance, 1)`，平台隐式决定调仓日，策略无法独立获取调仓日序列。

### 1.2 QuantsPlaybook 侧实现

- **交易日历**：已封装 `get_all_trade_days()` → `pd.DatetimeIndex`，`get_trade_days(start, end, count)` 获取区间交易日，`Tdaysoffset(watch_date, count, freq)` 做交易日偏移。
- **基础池**：各研报分别调用指数成分或全A数据，未出现统一入口。
- **调仓日**：回测脚本中多使用 `pd.date_range` 或 `get_trading_dates` 生成日期序列，再逐日遍历。

### 1.3 米筐 RiceQuant 侧实现

- **交易日历**：`get_trading_dates(start_date, end_date)` 返回交易日序列。
- **基础池**：`get_all_securities(["stock"])` 获取全市场证券，`index_components` 获取指数成分（API 名称因版本略有差异）。

---

## 二、问题归纳

| 问题 | 影响 |
|------|------|
| 各策略重复写 "去掉688/ST/IPO过滤" | 口径不一致，维护成本高 |
| 调仓日逻辑耦合在平台调度器内 | 无法提取日期序列做离线分析、滚动回测 |
| 聚宽/米筐/本地数据 API 差异大 | 策略迁移时需逐行改代码 |
| 没有统一的 "基础池类型" 抽象 | 策略初始化时无法声明 "我用沪深300成分股" |

---

## 三、统一接口设计

### 3.1 交易日历层（`trade_calendar.py`）

```python
from strategy_kits.universe.trade_calendar import (
    get_trade_days,
    shift_trade_day,
    previous_trade_day,
    next_trade_day,
)
```

| 函数 | 语义 | 对应原实现 |
|------|------|-----------|
| `get_trade_days(start, end, market="SSE", count=None)` | 获取区间交易日 | 聚宽 `get_trade_days` / QP `get_trade_days` |
| `shift_trade_day(date, n, market="SSE")` | 按交易日偏移 n 天 | QP `Tdaysoffset` |
| `previous_trade_day(date, market="SSE")` | 前一交易日 | — |
| `next_trade_day(date, market="SSE")` | 下一交易日 | — |

**设计要点**：
- 全局缓存 `_TRADE_CAL_CACHE` 持有完整交易日历，避免重复 IO。
- 首次使用需通过 `set_trade_cal_source()` 或平台适配器 `init_cal_from_*()` 注入。

### 3.2 调仓日计算层（`rebalance_schedule.py`）

```python
from strategy_kits.universe.trade_calendar import get_rebalance_dates, get_rolling_window_bounds
```

| 函数 | 语义 | 应用场景 |
|------|------|---------|
| `get_rebalance_dates(start, end, freq="1M", anchor="last", market="SSE")` | 生成调仓日序列 | 回测前生成调仓计划 |
| `get_rolling_window_bounds(anchor_date, lookback, lookahead=0, market="SSE")` | 获取滚动窗口起止交易日 | 因子计算窗口界定 |

**支持的 freq/anchor 组合**：
- 周频：`"1W"` / `"2W"`，锚点 `"MON"`~`"FRI"`
- 月频：`"1M"` / `"3M"`，锚点 `"first"` / `"last"` / 正整数（如 `1`）
- 季频：`"1Q"`，锚点同月频
- 年频：`"1Y"`，锚点同月频

### 3.3 基础池选择器（`universe_selector.py`）

```python
from strategy_kits.universe.trade_calendar import resolve_base_universe, UniverseType
```

| 抽象类型 | 配置示例 | 返回 |
|---------|---------|------|
| `UniverseType.ALL_A` | — | 全部A股代码列表 |
| `UniverseType.INDEX` | `{"index_code": "000300.XSHG"}` | 指数成分股 |
| `UniverseType.ETF` | `{"etf_types": ["etf", "lof"]}` 或 `{"custom_list": [...]}` | ETF/LOF 列表 |
| `UniverseType.INDUSTRY` | `{"industry_code": "801010", "level": "sw_l1"}` | 行业成分股 |
| `UniverseType.CUSTOM` | `{"codes": [...]}` | 自定义列表 |

**设计要点**：
- 策略层只与 `UniverseType` + `config` 字典交互，不直接调用平台 API。
- 平台差异下沉到 `BaseUniverseAdapter` 子类实现。

---

## 四、平台适配器设计

### 4.1 聚宽适配器（`adapters/joinquant_adapter.py`）

```python
from strategy_kits.universe.trade_calendar.adapters import init_cal_from_jq
init_cal_from_jq(start="2010-01-01", end="2025-12-31")
```

功能：
1. 用 `jqdata.get_trade_days()` 拉取日历并注入。
2. 注册 `JoinQuantAdapter` 为默认适配器。
3. 封装 `get_all_securities` / `get_index_stocks` / `get_industry_stocks`。

### 4.2 米筐适配器（`adapters/ricequant_adapter.py`）

```python
from strategy_kits.universe.trade_calendar.adapters import init_cal_from_rq
init_cal_from_rq(start="2010-01-01", end="2025-12-31")
```

功能：
1. 用 `rqalpha.get_trading_dates()` 拉取日历并注入。
2. 注册 `RiceQuantAdapter` 为默认适配器。
3. 封装 `get_all_securities` / `get_index_stocks`。
4. **注意**：米筐 `get_industry_stocks` 因版本差异较大，标记为 `NotImplementedError`，需按实际环境补全。

### 4.3 新增本地数据适配器建议

若后续接入 Tushare / 自建数据库，只需：
1. 继承 `BaseUniverseAdapter`
2. 实现 3 个方法
3. 调用 `set_default_adapter()` 注册

无需改动 `trade_calendar.py` 或 `universe_selector.py`。

---

## 五、目录与文件拆分推荐

目标归宿：`strategy_kits/universe/trade_calendar/`

```
strategy_kits/universe/trade_calendar/
├── __init__.py                    # 对外统一入口，暴露核心函数
├── trade_calendar.py              # 交易日历：get_trade_days, shift_trade_day
├── rebalance_schedule.py          # 调仓日计算：get_rebalance_dates, get_rolling_window_bounds
├── universe_selector.py           # 基础池选择：resolve_base_universe, BaseUniverseAdapter
└── adapters/
    ├── __init__.py                # 导出 init_cal_from_jq / init_cal_from_rq
    ├── joinquant_adapter.py       # 聚宽适配器
    ├── ricequant_adapter.py       # 米筐适配器
    └── local_adapter.py (待建)   # Tushare/本地DB适配器
```

**拆分理由**：
- `trade_calendar.py` 与 `rebalance_schedule.py` 是正交职责：前者提供 "日历"，后者提供 "调度"。
- `universe_selector.py` 独立：基础池选择与交易日历无直接依赖，仅在策略层组合使用。
- `adapters/` 隔离平台差异：新增平台不波及核心逻辑。

---

## 六、已创建的最小骨架文件

已在 `strategy_kits/universe/trade_calendar/` 下直接生成全部骨架文件：

1. `__init__.py`
2. `trade_calendar.py`
3. `rebalance_schedule.py`
4. `universe_selector.py`
5. `adapters/__init__.py`
6. `adapters/joinquant_adapter.py`
7. `adapters/ricequant_adapter.py`

所有接口已定义完毕，可立即被策略调用。平台细节（如米筐 `get_industry_stocks`）标记为待补全。

---

## 七、使用示例

### 7.1 调仓日序列生成

```python
from strategy_kits.universe.trade_calendar import get_rebalance_dates, get_trade_days

rebalance_days = get_rebalance_dates("2024-01-01", "2024-12-31", freq="1M", anchor="last")
print(rebalance_days)  # 每月最后一个交易日
```

### 7.2 滚动窗口起止

```python
from strategy_kits.universe.trade_calendar import get_rolling_window_bounds

start, end = get_rolling_window_bounds("2024-03-15", lookback=20, lookahead=5)
# start = 20 个交易日前（含 03-15）
# end   = 5  个交易日后（不含 03-15）
```

### 7.3 策略初始化：选基础池

```python
from strategy_kits.universe.trade_calendar import resolve_base_universe, UniverseType
from strategy_kits.universe.trade_calendar.adapters import init_cal_from_jq

init_cal_from_jq("2010-01-01")

codes = resolve_base_universe(
    UniverseType.INDEX,
    date="2024-01-15",
    config={"index_code": "000300.XSHG"}
)
```

---

## 八、明确不抽的内容

以下内容由各策略自行维护，不纳入本层：

1. **策略专属 ETF 白名单**（如 "只选科技ETF"）→ 策略层过滤
2. **研报专属行业池**（如 "某研报自定义的10个行业"）→ 策略层通过 `UniverseType.CUSTOM` 传入
3. **具体调仓时间点**（如 "09:35 开盘买入"）→ 运行底座 / 执行层决策
4. **股票过滤器**（ST、IPO、涨停、流动性过滤）→ 由任务 01（股票池过滤器）负责

---

## 九、通过门槛检查

| 检查项 | 状态 |
|--------|------|
| 新策略一开始就能统一拿交易日和基础池 | 通过。一键 `init_cal_from_*` + `resolve_base_universe` |
| 不再在各策略里重复处理调仓日逻辑 | 通过。`get_rebalance_dates` 统一生成序列 |
| 兼容聚宽/米筐双平台 | 通过。适配器层隔离差异 |
| 最小接口（4个）已定义并实现骨架 | 通过。`get_trade_days` / `shift_trade_day` / `resolve_base_universe` / `get_rebalance_dates` |
