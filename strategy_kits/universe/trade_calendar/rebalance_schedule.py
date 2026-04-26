"""
统一调仓日计算接口

参考来源：
- 聚宽策略中大量使用 run_monthly(rebalance, 1, time='9:35') / run_weekly(rebalance, 1)
- QuantsPlaybook 中回测框架的调仓日逻辑

设计原则：
1. 将平台自带调度器（run_monthly/run_weekly）中的“日期决定权”抽出来
2. 支持 freq/anchor 组合，适配不同策略的回测与实盘需求
3. 输出纯日期序列，供策略或运行底座消费
"""

from typing import Union, Optional, List
import datetime as dt
import pandas as pd

from .trade_calendar import get_trade_days, shift_trade_day


def get_rebalance_dates(
    start: Union[str, dt.date, dt.datetime, pd.Timestamp],
    end: Union[str, dt.date, dt.datetime, pd.Timestamp],
    freq: str = "1M",
    anchor: Union[str, int] = "last",
    market: str = "SSE",
) -> pd.DatetimeIndex:
    """
    获取调仓日序列。

    Args:
        start: 起始日期
        end: 结束日期
        freq: 调仓频率。支持 "1W"/"2W"（周）,"1M"/"3M"（月）,"1Q"（季）,"1Y"（年）。
        anchor: 锚点。
            - 周频：支持 "MON"/"TUE"/.../"FRI" 或 0-4（周一到周五）
            - 月/季/年频：支持 "first"/"last" 或正整数（如 1 表示每月1日，若非交易日顺延）
        market: 市场代码

    Returns:
        pd.DatetimeIndex: 调仓交易日序列（已对齐到实际交易日）

    Example:
        >>> get_rebalance_dates("2024-01-01", "2024-12-31", freq="1M", anchor="last")
        # 每月最后一个交易日
        >>> get_rebalance_dates("2024-01-01", "2024-12-31", freq="1W", anchor="FRI")
        # 每周五（或周五前最后一个交易日）
    """
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    all_days = get_trade_days(start_dt, end_dt, market=market)

    if len(all_days) == 0:
        return all_days

    freq_lower = freq.lower()

    # 周频
    if freq_lower.endswith("w"):
        weeks = int(freq_lower.replace("w", "").strip() or "1")
        anchor_day = _resolve_week_anchor(anchor)
        # 先生成每周目标候选日，再对齐交易日
        candidates = []
        current = start_dt
        while current <= end_dt:
            # 找到本周目标星期几的日期
            days_to_anchor = (anchor_day - current.weekday()) % 7
            candidate = current + pd.Timedelta(days=days_to_anchor)
            if start_dt <= candidate <= end_dt:
                candidates.append(candidate)
            current += pd.Timedelta(weeks=weeks)
        return _align_to_trade_days(candidates, all_days)

    # 月/季/年频
    if freq_lower.endswith("m"):
        months = int(freq_lower.replace("m", "").strip() or "1")
        date_range = pd.date_range(start_dt, end_dt, freq=f"{months}MS")
        candidates = [_resolve_month_anchor(d, anchor) for d in date_range]
        return _align_to_trade_days(candidates, all_days)

    if freq_lower.endswith("q"):
        quarters = int(freq_lower.replace("q", "").strip() or "1")
        date_range = pd.date_range(start_dt, end_dt, freq=f"{quarters}QS")
        candidates = [_resolve_month_anchor(d, anchor) for d in date_range]
        return _align_to_trade_days(candidates, all_days)

    if freq_lower.endswith("y"):
        years = int(freq_lower.replace("y", "").strip() or "1")
        date_range = pd.date_range(start_dt, end_dt, freq=f"{years}YS")
        candidates = [_resolve_month_anchor(d, anchor) for d in date_range]
        return _align_to_trade_days(candidates, all_days)

    raise ValueError(f"不支持的调仓频率: {freq}")


def get_rolling_window_bounds(
    anchor_date: Union[str, dt.date, dt.datetime, pd.Timestamp],
    lookback: int,
    lookahead: int = 0,
    market: str = "SSE",
) -> tuple:
    """
    获取滚动窗口起止点（均为交易日）。

    Args:
        anchor_date: 锚定交易日
        lookback: 向前滚动交易日数（包含 anchor_date）
        lookahead: 向后滚动交易日数（不包含 anchor_date）
        market: 市场代码

    Returns:
        (window_start, window_end) 均为 pd.Timestamp
    """
    anchor = pd.to_datetime(anchor_date)
    window_start = shift_trade_day(anchor, -(lookback - 1), market=market)
    window_end = shift_trade_day(anchor, lookahead, market=market)
    return window_start, window_end


def _resolve_week_anchor(anchor: Union[str, int]) -> int:
    mapping = {
        "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4,
        "1": 0, "2": 1, "3": 2, "4": 3, "5": 4,
        0: 0, 1: 1, 2: 2, 3: 3, 4: 4,
    }
    key = str(anchor).lower() if isinstance(anchor, str) else anchor
    if key not in mapping:
        raise ValueError(f"周频 anchor 不支持: {anchor}")
    return mapping[key]


def _resolve_month_anchor(d: pd.Timestamp, anchor: Union[str, int]) -> pd.Timestamp:
    if str(anchor).lower() == "last":
        # 下个月第一天减一天
        next_month = d + pd.offsets.MonthBegin(1)
        return next_month - pd.Timedelta(days=1)
    if str(anchor).lower() == "first":
        return d
    try:
        day = int(anchor)
    except ValueError:
        raise ValueError(f"月频 anchor 不支持: {anchor}")
    month_end = (d + pd.offsets.MonthEnd(0)).day
    clamped_day = max(1, min(day, month_end))
    return d.replace(day=clamped_day)


def _align_to_trade_days(
    candidates: List[pd.Timestamp], trade_days: pd.DatetimeIndex
) -> pd.DatetimeIndex:
    """将候选日期对齐到最近的前一个交易日（若本身是交易日则不变）。"""
    aligned = []
    for c in candidates:
        idx = trade_days.get_indexer([c], method="ffill")[0]
        if idx >= 0:
            aligned.append(trade_days[idx])
    return pd.DatetimeIndex(sorted(set(aligned)))
