"""
统一基础池选择器

参考来源：
- 聚宽：get_all_securities(types, date) / get_index_stocks(index_code, date)
- 米筐：get_all_securities(types) / history_bars + all_instruments
- QuantsPlaybook：各研报中的标的池获取逻辑

设计原则：
1. 策略只关心 "全A / 指数 / ETF池 / 行业池" 的抽象类型
2. 平台差异由 adapter 层处理
3. 返回统一的 list[str] 代码列表
"""

from enum import Enum
from typing import Union, Optional, List, Dict, Any
import datetime as dt
import pandas as pd


class UniverseType(str, Enum):
    ALL_A = "all_a"                # 全A股票池
    INDEX = "index"                # 指数成分股
    ETF = "etf"                    # ETF 池
    INDUSTRY = "industry"          # 行业池
    CUSTOM = "custom"              # 自定义池


def resolve_base_universe(
    universe_type: Union[str, UniverseType],
    date: Union[str, dt.date, dt.datetime, pd.Timestamp],
    config: Optional[Dict[str, Any]] = None,
    adapter=None,
) -> List[str]:
    """
    解析基础池。

    Args:
        universe_type: 池类型，支持 UniverseType 或字符串。
        date: 观察日期（用于获取指数成分、全A上市状态等快照）。
        config: 扩展配置，根据 universe_type 不同含义不同：
            - INDEX: {"index_code": "000300.XSHG"}
            - ETF:   {"etf_types": ["etf", "lof"]} 或 {"custom_list": [...]}
            - INDUSTRY: {"industry_code": "801010", "level": "sw_l1"}
            - CUSTOM: {"codes": [...]}
        adapter: 平台适配器。若未提供，默认尝试从全局注入的默认适配器获取。

    Returns:
        List[str]: 股票/基金代码列表（已去重）

    Example:
        >>> resolve_base_universe("index", "2024-01-15", {"index_code": "000300.XSHG"})
        ["000001.XSHE", ...]
        >>> resolve_base_universe("all_a", "2024-01-15")
        ["000001.XSHE", ...]
    """
    if adapter is None:
        adapter = _get_default_adapter()

    date_str = pd.to_datetime(date).strftime("%Y-%m-%d")
    config = config or {}
    universe_type = UniverseType(universe_type)

    if universe_type == UniverseType.ALL_A:
        codes = adapter.get_all_securities(types=["stock"], date=date_str)
    elif universe_type == UniverseType.INDEX:
        index_code = config.get("index_code")
        if not index_code:
            raise ValueError("index 类型必须提供 index_code")
        codes = adapter.get_index_stocks(index_code, date=date_str)
    elif universe_type == UniverseType.ETF:
        if "custom_list" in config:
            codes = config["custom_list"]
        else:
            etf_types = config.get("etf_types", ["etf"])
            codes = adapter.get_all_securities(types=etf_types, date=date_str)
    elif universe_type == UniverseType.INDUSTRY:
        industry_code = config.get("industry_code")
        level = config.get("level", "sw_l1")
        if not industry_code:
            raise ValueError("industry 类型必须提供 industry_code")
        codes = adapter.get_industry_stocks(industry_code, level=level, date=date_str)
    elif universe_type == UniverseType.CUSTOM:
        codes = config.get("codes", [])
    else:
        raise ValueError(f"不支持的 universe_type: {universe_type}")

    return sorted(set(str(c) for c in codes))


# 全局默认适配器占位（由 adapters 模块注册）
_DEFAULT_ADAPTER = None


def set_default_adapter(adapter):
    """注册全局默认适配器。"""
    global _DEFAULT_ADAPTER
    _DEFAULT_ADAPTER = adapter


def _get_default_adapter():
    if _DEFAULT_ADAPTER is None:
        raise RuntimeError(
            "未设置 adapter。请先调用 set_default_adapter(adapter)，"
            "或显式传入 adapter 参数。详见 adapters/joinquant_adapter.py 或 ricequant_adapter.py"
        )
    return _DEFAULT_ADAPTER


class BaseUniverseAdapter:
    """
    平台适配器抽象基类。
    各平台（聚宽/米筐/本地数据）实现此接口即可被 resolve_base_universe 消费。
    """

    def get_all_securities(
        self,
        types: Optional[List[str]] = None,
        date: Optional[str] = None,
    ) -> List[str]:
        raise NotImplementedError

    def get_index_stocks(self, index_code: str, date: Optional[str] = None) -> List[str]:
        raise NotImplementedError

    def get_industry_stocks(
        self, industry_code: str, level: str = "sw_l1", date: Optional[str] = None
    ) -> List[str]:
        raise NotImplementedError
