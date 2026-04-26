"""
统一交易日历接口

参考来源：
- 聚宽：get_trade_days(start, end, count=None)
- QuantsPlaybook：get_all_trade_days() / get_trade_days() / Tdaysoffset()
- 米筐：get_trading_dates(start_date, end_date)

设计原则：
1. 统一多平台交易日历差异
2. 返回 pd.DatetimeIndex 保证一致性
3. 缓存全量日历数据避免重复IO
"""

from typing import Union, Optional
import datetime as dt
import pandas as pd

from ...core import ErrorCode, StrategyKitsError, get_logger, log_kv

# 全局日历缓存（后续接入DB/文件时替换为对应来源）
_TRADE_CAL_CACHE: Optional[pd.DatetimeIndex] = None
_logger = get_logger("trade_calendar.core")
_DATE_COLUMN_CANDIDATES = {
    "market": ["date", "trade_date", "trading_date", "日期", "时间"],
    "financial": [
        "report_date",
        "date",
        "STATEMENT_DATE",
        "报告期",
        "报告日期",
        "报告日",
        "报表日期",
    ],
}


def _normalize_trade_days(trade_days: Union[list, pd.DatetimeIndex]) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(trade_days))
    if idx.empty:
        raise StrategyKitsError(
            ErrorCode.CALENDAR_NOT_INITIALIZED,
            "trade_days is empty",
        )
    return pd.DatetimeIndex(sorted(set(idx)))


def find_date_column(df: pd.DataFrame, category: str = "market") -> Optional[str]:
    """Find a likely date column using market/financial naming conventions."""
    candidates = _DATE_COLUMN_CANDIDATES.get(category, _DATE_COLUMN_CANDIDATES["market"])
    for col in candidates:
        if col in df.columns:
            return col
    return None


def set_trade_cal_source(trade_days: Union[list, pd.DatetimeIndex]):
    """设置交易日历数据源。允许从外部（DB/文件/平台API）注入。"""
    global _TRADE_CAL_CACHE
    _TRADE_CAL_CACHE = _normalize_trade_days(trade_days)
    log_kv(
        _logger,
        20,  # logging.INFO
        "trade_calendar_set_source",
        total_days=len(_TRADE_CAL_CACHE),
        first_day=str(_TRADE_CAL_CACHE[0].date()),
        last_day=str(_TRADE_CAL_CACHE[-1].date()),
    )


def is_trade_cal_initialized() -> bool:
    return _TRADE_CAL_CACHE is not None and len(_TRADE_CAL_CACHE) > 0


def init_trade_cal_from_gateway(
    gateway,
    start_date: str = "2010-01-01",
    end_date: Optional[str] = None,
) -> pd.DatetimeIndex:
    """Initialize calendar from a data gateway implementing `get_trade_days`."""
    if end_date is None:
        end_date = pd.Timestamp.today().strftime("%Y-%m-%d")
    trade_days = gateway.get_trade_days(start_date=start_date, end_date=end_date)
    set_trade_cal_source(trade_days)
    return get_all_trade_days()


def init_trade_cal_from_csv(path: str, date_col: str = "date") -> pd.DatetimeIndex:
    """Initialize calendar from local CSV file."""
    df = pd.read_csv(path)
    if date_col not in df.columns:
        raise StrategyKitsError(
            ErrorCode.CONTRACT_MISSING_COLUMN,
            f"CSV calendar missing date column '{date_col}'",
            details={"columns": list(df.columns), "path": path},
        )
    set_trade_cal_source(df[date_col].tolist())
    return get_all_trade_days()


def get_all_trade_days(
    force_refresh: bool = False,
    allow_business_day_fallback: bool = False,
    fallback_start: str = "2010-01-01",
    fallback_end: Optional[str] = None,
) -> pd.DatetimeIndex:
    """获取全部交易日历。"""
    global _TRADE_CAL_CACHE
    if _TRADE_CAL_CACHE is None or force_refresh:
        if allow_business_day_fallback:
            if fallback_end is None:
                fallback_end = pd.Timestamp.today().strftime("%Y-%m-%d")
            fallback_days = pd.bdate_range(fallback_start, fallback_end)
            set_trade_cal_source(fallback_days)
            log_kv(
                _logger,
                30,  # logging.WARNING
                "trade_calendar_business_day_fallback",
                fallback_start=fallback_start,
                fallback_end=fallback_end,
            )
        else:
            raise StrategyKitsError(
                ErrorCode.CALENDAR_NOT_INITIALIZED,
                "交易日历未初始化。请先调用 set_trade_cal_source()/init_trade_cal_from_gateway()/init_trade_cal_from_csv()。",
            )
    return _TRADE_CAL_CACHE


def get_trade_days(
    start: Optional[Union[str, dt.date, dt.datetime, pd.Timestamp]] = None,
    end: Optional[Union[str, dt.date, dt.datetime, pd.Timestamp]] = None,
    market: str = "SSE",
    count: Optional[int] = None,
) -> pd.DatetimeIndex:
    """
    获取区间交易日。

    Args:
        start: 起始日期（含）。若与 count 同时传，优先 count + end 模式。
        end: 结束日期（含）。
        market: 市场代码，默认 "SSE"（上交所）。保留参数用于后续扩展港股/美股。
        count: 交易日数量（>0 表示从 end 往前取 count 个，包含 end）。

    Returns:
        pd.DatetimeIndex: 交易日序列
    """
    if count is not None and start is not None:
        raise ValueError("不能同时指定 start 和 count")

    all_days = get_all_trade_days(allow_business_day_fallback=False)

    if count is not None:
        end_dt = pd.to_datetime(end) if end is not None else all_days[-1]
        end_idx = all_days.get_indexer([end_dt], method="ffill")[0]
        if end_idx < 0:
            raise StrategyKitsError(
                ErrorCode.CALENDAR_OUT_OF_RANGE,
                f"end={end_dt.date()} 不在日历范围内",
            )
        start_idx = max(0, end_idx - count + 1)
        return all_days[start_idx : end_idx + 1]

    start_dt = pd.to_datetime(start) if start is not None else all_days[0]
    end_dt = pd.to_datetime(end) if end is not None else all_days[-1]
    idx = all_days.slice_indexer(start_dt, end_dt)
    return all_days[idx]


def shift_trade_day(
    date: Union[str, dt.date, dt.datetime, pd.Timestamp],
    n: int,
    market: str = "SSE",
) -> pd.Timestamp:
    """
    按交易日偏移。

    Args:
        date: 观察日
        n: 偏移交易日数（正数向后，负数向前）
        market: 市场代码

    Returns:
        pd.Timestamp: 偏移后的交易日
    """
    all_days = get_all_trade_days()
    date_dt = pd.to_datetime(date)
    pos = all_days.get_indexer([date_dt], method="ffill")[0]
    if pos < 0:
        raise StrategyKitsError(
            ErrorCode.CALENDAR_OUT_OF_RANGE,
            f"date={date} 不在日历范围内",
        )
    target_pos = pos + n
    if target_pos < 0 or target_pos >= len(all_days):
        raise StrategyKitsError(
            ErrorCode.CALENDAR_OUT_OF_RANGE,
            f"偏移后超出日历范围: date={date}, n={n}",
        )
    return all_days[target_pos]


def previous_trade_day(
    date: Union[str, dt.date, dt.datetime, pd.Timestamp],
    market: str = "SSE",
) -> pd.Timestamp:
    """获取前一交易日。"""
    return shift_trade_day(date, -1, market=market)


def next_trade_day(
    date: Union[str, dt.date, dt.datetime, pd.Timestamp],
    market: str = "SSE",
) -> pd.Timestamp:
    """获取下一交易日。"""
    return shift_trade_day(date, 1, market=market)


def is_trade_date(
    date: Union[str, dt.date, dt.datetime, pd.Timestamp],
    market: str = "SSE",
) -> bool:
    """Return whether the supplied date is a trading day in the loaded calendar."""
    all_days = get_all_trade_days()
    dt_value = pd.to_datetime(date)
    return dt_value in all_days


def get_previous_trade_date(
    date: Union[str, dt.date, dt.datetime, pd.Timestamp],
    n: int = 1,
    market: str = "SSE",
) -> pd.Timestamp:
    """JoinQuant-style alias for shifting backward by trading days."""
    return shift_trade_day(date, -abs(n), market=market)


def get_next_trade_date(
    date: Union[str, dt.date, dt.datetime, pd.Timestamp],
    n: int = 1,
    market: str = "SSE",
) -> pd.Timestamp:
    """JoinQuant-style alias for shifting forward by trading days."""
    return shift_trade_day(date, abs(n), market=market)
