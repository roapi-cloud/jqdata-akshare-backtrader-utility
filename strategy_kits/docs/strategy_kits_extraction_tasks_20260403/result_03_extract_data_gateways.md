# 任务 03：数据网关适配层抽取结果

> 目标：让新策略可以先写策略逻辑，再决定数据源；数据口径切换不影响上层策略写法。

---

## 1. 数据网关最小能力表

| 能力层级 | 接口 | 说明 | 优先级 |
|---|---|---|---|
| **行情数据** | `get_price` | 单/多标的 OHLCV，支持日线/分钟线、前/后复权 | P0 |
| **基础信息** | `get_all_securities` | 返回全市场标的列表（code / name / jq_code / 类型） | P0 |
| **基础信息** | `get_security_info` | 单只标的基础信息 | P1 |
| **财务/因子** | `get_fundamentals` | 资产负债表/利润表/现金流量表单期查询 | P0 |
| **财务/因子** | `get_history_fundamentals` | 多标的多期财报批量查询，支持字段前缀分流 | P0 |
| **指数成分** | `get_index_members` | 返回指数成分股列表（如沪深300、中证500） | P0 |
| **交易日历** | `get_trade_days` | 返回交易日序列 | P0 |
| **交易约束** | `get_extras` | ST、停牌等状态（最小支持 `is_st`、`is_paused`） | P0 |
| **K线 Bars** | `get_bars` | 按 count 拉取历史 K 线（日线/分钟） | P1 |
| **龙虎榜** | `get_billboard_list` | 每日龙虎榜数据 | P2 |

**不该抽的内容（明确排除）**：
- 策略专属字段拼接逻辑（如自定义 alpha 合成）
- 专题研究 feature engineering（如网络因子、隔夜收益率拆分）
- 回测框架级别的 `PortfolioCompat`、`JQ2BTBaseStrategy` 等执行层适配

---

## 2. 三端接口映射表（JQ / TuShare / Qlib）

统一对外接口签名采用 **聚宽（JQ）风格**，内部由各自适配器映射到原生 SDK。

### 2.1 行情数据

| 统一接口 | JQ 侧实现 | TuShare 侧实现 | Qlib 侧实现 |
|---|---|---|---|
| `get_price(symbols, start_date, end_date, frequency='daily', fields=None, adjust='qfq')` | `ak.stock_zh_a_hist` / `ak.stock_zh_a_minute`（`backtrader_base_strategy.py:726`） | `ts.pro_bar` 或 `ts.pro.daily` / `ts.pro.minutely` | `D.features(instruments, ['$open','$high','$low','$close','$volume'], start_time, end_time)` → pivot 为单标 df 或 dict |
| `get_bars(security, count, unit='1d', fields=None, end_dt=None)` | `ak.stock_zh_a_hist` / `ak.stock_zh_a_minute` 取 tail(count)（`backtrader_base_strategy.py:960`） | `ts.pro_bar` 按 count 限制 | `D.features` 后按 end_dt 截断取 tail(count) |

### 2.2 基础信息

| 统一接口 | JQ 侧实现 | TuShare 侧实现 | Qlib 侧实现 |
|---|---|---|---|
| `get_all_securities(types=['stock'], date=None)` | `ak.stock_info_a_code_name`（`backtrader_base_strategy.py:818`） | `ts.pro.stock_basic` | `D.list_instruments(D.instruments(market='csi300'), ...)` 等；Qlib 无“全部 A 股”元数据表，需传入预定义市场名 `csi300` / `csi500` / `ashares` |
| `get_security_info(code)` | `ak.stock_info_a_code_name` 按 code 过滤（`backtrader_base_strategy.py:843`） | `ts.pro.stock_basic(ts_code=...)` | 无直接对应；可返回空或从 `D.instruments` 反查 |

### 2.3 财务/因子

| 统一接口 | JQ 侧实现 | TuShare 侧实现 | Qlib 侧实现 |
|---|---|---|---|
| `get_fundamentals(query_obj, date=None, statDate=None)` | `ak.stock_financial_report_sina` / `ak.stock_financial_benefit_ths`（`backtrader_base_strategy.py:792`） | `ts.pro.balancesheet` / `ts.pro.income` / `ts.pro.cashflow` | **不支持**。Qlib 以预计算特征为主。适配层可抛 `NotImplementedError` 或映射到 `D.features` 中已有的财务表达式（如存在） |
| `get_history_fundamentals(security, fields, stat_date, count, ...)` | 自动按 `cash_flow.` / `income.` / `balance.` 前缀分流，合并为 MultiIndex DataFrame（`backtrader_base_strategy.py:291`） | 同样按表前缀分流到对应 `pro` 表，再 merge | **不支持**。同上 |

### 2.4 指数成分

| 统一接口 | JQ 侧实现 | TuShare 侧实现 | Qlib 侧实现 |
|---|---|---|---|
| `get_index_members(index_code, date=None)` | `ak.index_stock_cons(symbol=index_code)` | `ts.pro.index_weight(index_code=...)` 或 `ts.pro.index_member` | `D.instruments(market='csi300')`（仅支持预定义市场别名映射） |

### 2.5 交易日历

| 统一接口 | JQ 侧实现 | TuShare 侧实现 | Qlib 侧实现 |
|---|---|---|---|
| `get_trade_days(start_date=None, end_date=None)` | `ak.tool_trade_date_hist_sina`（`backtrader_base_strategy.py:870`） | `ts.pro.trade_cal` | `D.calendar(start_time, end_time, freq='day')` |

### 2.6 交易约束 / Extras

| 统一接口 | JQ 侧实现 | TuShare 侧实现 | Qlib 侧实现 |
|---|---|---|---|
| `get_extras(field, securities, start_date=None, end_date=None)` | `ak.stock_zh_a_st_em`（`is_st`）/ `ak.stock_zh_a_stop_em`（`is_paused`）（`backtrader_base_strategy.py:878`） | `ts.pro.namechange`（ST） / `ts.pro.suspend_d`（停牌） | **不支持**。返回空 DataFrame |

---

## 3. 统一 Gateway Interface

采用 **抽象基类（ABC）+ 具体适配器** 模式。策略层只依赖 `BaseDataGateway`。

```python
from abc import ABC, abstractmethod
from typing import Union, List, Optional, Sequence
import pandas as pd

class BaseDataGateway(ABC):
    """数据网关统一接口。策略代码只应依赖此抽象类。"""

    @abstractmethod
    def get_price(
        self,
        symbols: Union[str, List[str]],
        start_date: str,
        end_date: str,
        frequency: str = "daily",
        fields: Optional[List[str]] = None,
        adjust: str = "qfq",
        count: Optional[int] = None,
    ) -> Union[pd.DataFrame, dict[str, pd.DataFrame]]:
        """获取行情数据。多标时返回 dict[symbol] -> DataFrame。"""
        ...

    @abstractmethod
    def get_fundamentals(
        self,
        query_obj: dict,
        date: Optional[str] = None,
        stat_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """单期财务数据查询。"""
        ...

    @abstractmethod
    def get_history_fundamentals(
        self,
        security: Union[str, List[str]],
        fields: List[str],
        watch_date: Optional[str] = None,
        stat_date: Optional[str] = None,
        count: int = 1,
        interval: str = "1q",
    ) -> pd.DataFrame:
        """多标的多期财报数据。fields 支持 'balance.xxx' / 'income.xxx' / 'cash_flow.xxx' 前缀。"""
        ...

    @abstractmethod
    def get_all_securities(
        self, types: Optional[List[str]] = None, date: Optional[str] = None
    ) -> pd.DataFrame:
        """全市场基础信息。"""
        ...

    @abstractmethod
    def get_security_info(self, code: str) -> Optional[dict]:
        """单只标的基础信息。"""
        ...

    @abstractmethod
    def get_index_members(
        self, index_code: str, date: Optional[str] = None
    ) -> List[str]:
        """指数成分股列表，返回统一 code 格式（如 JQ 风格 000001.XSHE）。"""
        ...

    @abstractmethod
    def get_trade_days(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[pd.Timestamp]:
        """交易日序列。"""
        ...

    @abstractmethod
    def get_extras(
        self,
        field: str,
        securities: Union[str, List[str]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """ST、停牌等附加信息。"""
        ...

    @abstractmethod
    def get_bars(
        self,
        security: str,
        count: int,
        unit: str = "1d",
        fields: Optional[List[str]] = None,
        end_dt: Optional[str] = None,
    ) -> pd.DataFrame:
        """按 count 获取历史 K 线。"""
        ...
```

### 3.1 符号标准化约定

网关内部统一使用 **聚宽风格** `000001.XSHE` / `600000.XSHG` 作为 canonical 格式。各适配器负责出入转换：

| 风格 | 示例 | 负责转换模块 |
|---|---|---|
| Canonical (JQ) | `000001.XSHE` | 内部标准 |
| AkShare | `sz000001` / `sh600000` | `JQDataGateway` |
| TuShare | `000001.SZ` / `600000.SH` | `TuShareDataGateway` |
| Qlib | `SZ000001` / `SH600000` | `QlibDataGateway` |

---

## 4. 缓存与容错的最小要求

### 4.1 缓存要求（最小可用）

1. **粒度**：按 `(接口名, 参数哈希)` 作为缓存 key，存储为本地 pickle 文件。
2. **TTL**：元数据类缓存（如 `get_all_securities`、`get_index_members`、`get_trade_days`）建议 **1 天**；行情/财报类缓存建议 **7 天** 或永久（历史数据不变）。
3. **刷新开关**：所有查询接口均暴露 `force_update: bool = False`，为 `True` 时跳过缓存直接拉取。
4. **目录隔离**：不同适配器使用不同的 `cache_dir`（如 `.gateway_cache_jq`、`.gateway_cache_ts`、`.gateway_cache_qlib`），避免 key 冲突。

### 4.2 容错要求（最小可用）

1. **重试机制**：网络层统一封装 `retry_on_failure(max_retry=3, sleep=1.0)`。
   - TuShare 已有自带无限重试封装（`QuantsPlaybook/*/tushare_api.py`），可复用其逻辑或再包一层。
   - AkShare/Qlib 网关显式加装饰器重试。
2. **失败降级**：
   - 单标拉取失败时，返回空 `DataFrame`（避免整批中断）。
   - 全市场元数据拉取失败时，抛出异常并提示检查网络（无法安全伪造）。
   - Qlib 侧不支持的能力（如原始财报、ST 状态）返回空结构或显式抛 `NotImplementedError`。
3. **日志**：所有异常要走统一 logger，记录 `symbol / method / exception`，方便策略排查。

---

## 5. 代码骨架

骨架文件已落地到 `/Users/fengzhi/Downloads/git/testlixingren/strategy_kits/execution/data_gateways/`。

### 目录结构

```
strategy_kits/execution/data_gateways/
├── __init__.py
├── base.py                 # BaseDataGateway 抽象类
├── symbol.py               # 股票代码标准化工具
├── cache.py                # 最小文件缓存 (pickle + TTL)
├── retry.py                # 通用重试装饰器
├── jq_gateway.py           # JQ / AkShare 适配器
├── tushare_gateway.py      # TuShare 适配器
├── qlib_gateway.py         # Qlib 适配器
└── factory.py              # create_gateway(kind) 工厂
```

### 5.1 各文件职责与关键实现要点

- **`base.py`**：定义 ABC，所有策略层类型提示应使用 `BaseDataGateway`。
- **`symbol.py`**：提供 `to_jq()`、`to_ak()`、`to_ts()`、`to_qlib()`，以及 `canonicalize()`。
- **`cache.py`**：`FileCache` 基于 `hashlib.md5(key).hexdigest()` 命名文件名，支持 `ttl_seconds`。
- **`retry.py`**：`retry_on_failure` 装饰器，对 AkShare/Qlib 原生调用做保护。
- **`jq_gateway.py`**：
  - 直接复用 `backtrader_base_strategy.py` 中的字段映射逻辑（`开盘->open` 等）。
  - `get_price` 返回单标 `DataFrame` 或多标 `dict`。
  - `get_history_fundamentals` 保留前缀分流逻辑（`balance.`/`income.`/`cash_flow.`）。
- **`tushare_gateway.py`**：
  - 引用 `QuantsPlaybook` 中的 `TuShare` 自动重试类作为底层 client。
  - `get_price` 中通过 `ts.pro_bar` 实现日线/分钟线获取，再统一字段名。
  - `get_fundamentals` 按 `table` 键分发到 `balancesheet` / `income` / `cashflow`。
- **`qlib_gateway.py`**：
  - 全局 `qlib.init_once()` 机制（参考 `QlibDataProvider`）。
  - `get_price` 调用 `D.features(...)` 获取长表数据，按 `instrument` 拆分或 pivot。
  - `get_index_members` 映射 `000300` -> `csi300`。
  - `get_fundamentals` 直接抛 `NotImplementedError`（Qlib 不提供原始三张表）。
- **`factory.py`**：提供 `create_gateway(kind: Literal["jq", "tushare", "qlib"], **kwargs)`。

### 5.2 使用示例

```python
from strategy_kits.execution.data_gateways import create_gateway

# 策略层只与 BaseDataGateway 打交道
gw = create_gateway("jq", cache_dir=".gateway_cache")

# 获取行情
prices = gw.get_price(
    ["000001.XSHE", "600000.XSHG"],
    start_date="2023-01-01",
    end_date="2023-01-31",
    fields=["open", "close", "volume"],
)

# 获取沪深300成分股
members = gw.get_index_members("000300")

# 切换数据源时，策略代码无需改动
gw = create_gateway("tushare", token="your_token")
members = gw.get_index_members("000300")
```

---

## 6. 边界与后续建议

1. **Qlib 财报缺口**：Qlib 以特征表达式为主，原始财报三张表不在其数据模型内。若策略强依赖原始财报，Qlib 网关只能抛异常；建议策略层做 `try/except` 或运行前检查网关能力。
2. **实时 vs 离线**：当前提取的是**离线/日终**数据网关。若后续需要实时 tick/逐笔，应再建一层 `RealtimeDataGateway`。
3. **指数成分权重**：当前 `get_index_members` 只返回 code 列表。若需要权重，可后续扩展 `get_index_weights`。
4. **分钟线对齐**：不同数据源对 minute 字段命名不同（如 `成交额` 可能缺失），适配层内部统一为 `open/high/low/close/volume/money`。
