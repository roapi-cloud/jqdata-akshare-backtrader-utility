# A 股股票池过滤器

新策略可直接复用的股票池过滤组件，无需从 notebook 复制粘贴过滤代码。

## 快速开始

```python
from strategy_kits.universe.stock_pool_filters import apply_filters, DEFAULT_FILTER_CONFIG
from datetime import date

# 基础股票池（如全市场、指数成分股等）
base_universe = get_all_securities('stock', date).index.tolist()

# 应用过滤器
result = apply_filters(
    base_universe=base_universe,
    date=date(2024, 1, 1),
    filter_config=DEFAULT_FILTER_CONFIG,
    positions=list(context.portfolio.positions.keys())  # 当前持仓
)

# 获取过滤后的股票池
filtered_stocks = result.filtered_universe

# 查看过滤统计
print(result.filter_stats)  # {'st': 15, 'paused': 3, 'new_stock': 8}

# 查看移除原因
print(result.removed_reasons['st'])  # ['600001.XSHG', ...]
```

## 第一版支持的过滤器

| 过滤器 | 功能 | 默认启用 |
|-------|------|---------|
| `st` | 过滤ST、\*ST、退市股票 | ✅ |
| `paused` | 过滤停牌股票 | ✅ |
| `new_stock` | 过滤上市不足250天次新股 | ✅ |
| `limitup` | 过滤涨停不可买股票（保留持仓） | ✅ |
| `limitdown` | 过滤跌停不可买股票（保留持仓） | ❌ |
| `kcbj` | 过滤科创板/北交所 | ✅ |

## 配置说明

```python
DEFAULT_FILTER_CONFIG = {
    'st': {
        'enabled': True,
        'check_name': True,  # 检查名称包含ST/*/退
    },
    'paused': {
        'enabled': True,
        'paused_N': 1,       # 查询当天
        'threshold': None,   # 停牌天数阈值（可选）
    },
    'new_stock': {
        'enabled': True,
        'min_days': 250,     # 最小上市天数
    },
    'limitup': {
        'enabled': True,
        'keep_positions': True,  # 保留持仓
    },
    'limitdown': {
        'enabled': False,    # 默认不启用
        'keep_positions': True,
    },
    'kcbj': {
        'enabled': True,     # 过滤科创/北交所
    },
}
```

## 自定义配置

```python
# 仅启用基础过滤（ST、停牌、次新、科创北交所）
from strategy_kits.universe.stock_pool_filters import get_minimal_config

result = apply_filters(
    base_universe=base_universe,
    date=date,
    filter_config=get_minimal_config()
)

# 自定义参数
custom_config = {
    'st': {'enabled': True},
    'new_stock': {'enabled': True, 'min_days': 500},  # 上市500天以上
    'limitup': {'enabled': True},
    'limitdown': {'enabled': False},
    'kcbj': {'enabled': False},  # 允许科创/北交所
}

result = apply_filters(base_universe, date, custom_config)
```

## 边界说明

### 涨停/跌停过滤

- **涨停**：当日已涨停股票无法买入，但已持仓股票保留观察后续走势
- **跌停**：当日已跌停股票买入可能困难，卖出确定无法成交，建议策略层在卖出逻辑中额外判断

### 职责边界

- **过滤器职责**：移除明确不可交易/不合规的股票
- **策略层职责**：在过滤后股票池上进行选股、打分、排序、数量控制

**不应在过滤器中实现的内容**：
- 最终股票数量限制（如取前100只）
- 市值排序/因子排序
- 行业中性配置
- 具体因子筛选条件（如EPS>0）

## 数据依赖

过滤器依赖以下数据接口（需适配聚宽风格API或AkShare）：

| 过滤器 | 必需数据 |
|-------|---------|
| ST | `is_st`字段、股票名称 |
| 停牌 | `paused`字段 |
| 次新 | 上市日期 `start_date` |
| 涨停/跌停 | `high_limit`、`low_limit`、最新价 |
| 科创/北交所 | 股票代码（前缀规则） |

聚宽风格API适配：
- `get_extras('is_st', stock_list, date)`
- `get_price(stock_list, fields='paused', date)`
- `get_security_info(stock).start_date`
- `get_current_data()[stock].high_limit/low_limit`

AkShare适配：
- ST数据：`ak.stock_zh_a_st_em()`
- 停牌数据：`ak.stock_zh_a_stop_em()`
- 上市日期：`ak.stock_info_a_code_name()`

## 扩展计划（第二版）

- 行业过滤：`filter_industry`
- 低流动性过滤：`filter_low_liquidity`
- 自定义黑名单：`filter_blacklist`

## 完整示例

```python
from datetime import date
from strategy_kits.universe.stock_pool_filters import apply_filters, DEFAULT_FILTER_CONFIG

# 1. 获取基础股票池（示例：聚宽风格）
base_universe = get_all_securities('stock', date).index.tolist()

# 2. 应用过滤器
result = apply_filters(
    base_universe=base_universe,
    date=date(2024, 1, 1),
    filter_config=DEFAULT_FILTER_CONFIG,
    positions=list(context.portfolio.positions.keys())
)

# 3. 查看结果
print(f"基础股票池: {len(base_universe)} 只")
print(f"过滤后股票池: {len(result.filtered_universe)} 只")
print(f"移除统计: {result.filter_stats}")

# 4. 后续策略逻辑（在过滤后股票池上选股）
# 这里进行因子选股、打分、排序等操作
# ...

# 不再需要复制粘贴 ST/停牌/次新等过滤代码
```

## 参考来源

- 聚宽有价值策略558系列（所有策略的过滤函数实现）
- QuantsPlaybook/B-因子构建类/高频价量相关性/Hugos_tools/BuildStockPool.py（工程化版本）

## 验收标准

- ✅ 新策略可直接调用 `apply_filters`，无需复制粘贴过滤代码
- ✅ 过滤器参数可配置，不硬编码
- ✅ 输入输出接口统一，便于扩展新过滤器
- ✅ 过滤统计和移除原因清晰，便于调试和日志
- ✅ 职责边界明确：过滤器只做合规/可交易性判断