"""Pure timer rules adapted from jk2bt for local Backtrader runtimes."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

try:
    import pandas as pd
except Exception:  # pragma: no cover
    class _PandasFallback:
        @staticmethod
        def to_datetime(value):
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value))

    pd = _PandasFallback()

MARKET_OPEN_TIME = time(9, 30)
MARKET_CLOSE_TIME = time(15, 0)


def _normalize_trading_days(trading_days: Optional[List[date]]) -> Optional[List[date]]:
    if trading_days is None:
        return None
    normalized = sorted({pd.to_datetime(d).date() for d in trading_days})
    return normalized


def _generate_approx_trading_days(year: int, month: int) -> List[date]:
    first_day = date(year, month, 1)
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    current = first_day
    out: List[date] = []
    while current < next_month:
        if current.weekday() < 5:
            out.append(current)
        current += timedelta(days=1)
    return out


def parse_time_rule(rule: Optional[str]) -> Tuple[str, Optional[time], Optional[int]]:
    """Parse JoinQuant-style time expressions."""
    if rule is None:
        return ("every_bar", None, None)

    normalized = str(rule).strip().lower()
    if normalized in {"every_bar", "each_bar"}:
        return ("every_bar", None, None)
    if normalized == "before_open":
        return ("before_open", None, None)
    if normalized in {"open", "market_open", "开盘"}:
        return ("open", MARKET_OPEN_TIME, None)
    if normalized in {"after_close", "market_close", "收盘", "尾盘"}:
        return ("after_close", MARKET_CLOSE_TIME, None)

    if ":" in normalized and "+" not in normalized and "-" not in normalized:
        hours, minutes = normalized.split(":", 1)
        return ("absolute", time(int(hours), int(minutes)), None)

    if normalized.startswith("open+"):
        offset = int(normalized.split("+", 1)[1].replace("m", "").replace("min", "").strip())
        target_dt = datetime.combine(date.today(), MARKET_OPEN_TIME) + timedelta(minutes=offset)
        return ("open_offset", target_dt.time(), offset)

    if normalized.startswith("open-"):
        offset = int(normalized.split("-", 1)[1].replace("m", "").replace("min", "").strip())
        target_dt = datetime.combine(date.today(), MARKET_OPEN_TIME) - timedelta(minutes=offset)
        return ("open_offset", target_dt.time(), -offset)

    if normalized.startswith("close+"):
        offset = int(normalized.split("+", 1)[1].replace("m", "").replace("min", "").strip())
        target_dt = datetime.combine(date.today(), MARKET_CLOSE_TIME) + timedelta(minutes=offset)
        return ("close_offset", target_dt.time(), offset)

    if normalized.startswith("close-"):
        offset = int(normalized.split("-", 1)[1].replace("m", "").replace("min", "").strip())
        target_dt = datetime.combine(date.today(), MARKET_CLOSE_TIME) - timedelta(minutes=offset)
        return ("close_offset", target_dt.time(), -offset)

    return ("open", MARKET_OPEN_TIME, None)


def _time_in_bar(bar_time: time, target_time: time, bar_resolution_minutes: int) -> bool:
    start_dt = datetime.combine(date.today(), bar_time)
    end_dt = start_dt + timedelta(minutes=max(1, bar_resolution_minutes))
    target_dt = datetime.combine(date.today(), target_time)
    return start_dt <= target_dt < end_dt


def check_bar_time_match(
    bar_time: Optional[time],
    rule_type: str,
    target_time: Optional[time],
    bar_resolution_minutes: int = 1,
) -> bool:
    """
    Match a time rule against the current bar.

    For daily bars, Backtrader usually exposes ``00:00``. In that case we treat
    any single-point time rule as matched once per trading day, so research
    strategies using ``14:50`` still execute under daily bars.
    """
    if rule_type == "every_bar":
        return True

    if bar_time is None:
        return True

    if rule_type == "before_open":
        return bar_time <= MARKET_OPEN_TIME
    if rule_type in {"open", "open_offset", "market_open"} and target_time is not None:
        return _time_in_bar(bar_time, target_time, bar_resolution_minutes)
    if rule_type in {"after_close", "close_offset", "market_close"} and target_time is not None:
        return _time_in_bar(bar_time, target_time, bar_resolution_minutes)
    if rule_type == "absolute" and target_time is not None:
        return _time_in_bar(bar_time, target_time, bar_resolution_minutes)

    return False


def is_trading_day(dt_value: date, trading_days: Optional[List[date]] = None) -> bool:
    normalized = _normalize_trading_days(trading_days)
    if normalized is not None:
        return dt_value in set(normalized)
    return dt_value.weekday() < 5


def get_nth_trading_day_of_month(
    year: int,
    month: int,
    n: int,
    trading_days: Optional[List[date]] = None,
) -> Optional[date]:
    normalized = _normalize_trading_days(trading_days)
    month_days = (
        [d for d in normalized if d.year == year and d.month == month]
        if normalized is not None
        else _generate_approx_trading_days(year, month)
    )
    if not month_days:
        return None
    if n > 0:
        idx = n - 1
        return month_days[idx] if idx < len(month_days) else month_days[-1]
    idx = n
    return month_days[idx] if abs(idx) <= len(month_days) else month_days[0]


def check_daily_trigger(
    current_date: date,
    last_executed: Optional[date] = None,
    trading_days: Optional[List[date]] = None,
) -> bool:
    return is_trading_day(current_date, trading_days) and last_executed != current_date


def check_weekly_trigger(
    current_date: date,
    last_executed: Optional[date],
    target_weekday: int,
    trading_days: Optional[List[date]] = None,
) -> bool:
    if not is_trading_day(current_date, trading_days):
        return False
    if current_date.isoweekday() != target_weekday:
        return False
    if last_executed is None:
        return True
    current_week = current_date.isocalendar()[:2]
    last_week = last_executed.isocalendar()[:2]
    return current_week != last_week


def check_monthly_trigger(
    current_date: date,
    last_executed: Optional[date],
    target_day: int,
    trading_days: Optional[List[date]] = None,
) -> bool:
    if not is_trading_day(current_date, trading_days):
        return False
    if last_executed is not None and last_executed.year == current_date.year and last_executed.month == current_date.month:
        return False
    target = get_nth_trading_day_of_month(
        current_date.year,
        current_date.month,
        target_day,
        trading_days=trading_days,
    )
    return target == current_date


def should_execute_timer(
    frequency: str,
    current_date: date,
    current_time: Optional[time] = None,
    last_executed: Optional[date] = None,
    time_rule: Optional[str] = None,
    day: Optional[int] = None,
    weekday: Optional[int] = None,
    trading_days: Optional[List[date]] = None,
    bar_resolution_minutes: int = 1,
) -> Tuple[bool, str]:
    rule_type, target_time, _ = parse_time_rule(time_rule)

    if not is_trading_day(current_date, trading_days):
        return (False, "not_trading_day")
    if not check_bar_time_match(current_time, rule_type, target_time, bar_resolution_minutes):
        return (False, "time_not_match")

    if frequency == "every_bar":
        return (True, "every_bar")
    if frequency == "daily":
        return (
            (True, "daily")
            if check_daily_trigger(current_date, last_executed, trading_days)
            else (False, "already_executed")
        )
    if frequency == "weekly":
        target_weekday = 1 if weekday is None else weekday
        return (
            (True, "weekly")
            if check_weekly_trigger(current_date, last_executed, target_weekday, trading_days)
            else (False, "not_target_weekday")
        )
    if frequency == "monthly":
        target_day = 1 if day is None else day
        return (
            (True, "monthly")
            if check_monthly_trigger(current_date, last_executed, target_day, trading_days)
            else (False, "not_target_day")
        )

    return (False, "unknown_frequency")


class TradingDayCalendar:
    """Small helper wrapper around injected trading days."""

    def __init__(self, trading_days: Optional[List[date]] = None):
        self.set_trading_days(trading_days)

    def set_trading_days(self, trading_days: Optional[List[date]]) -> None:
        self._trading_days = _normalize_trading_days(trading_days)

    def is_trading_day(self, dt_value: date) -> bool:
        return is_trading_day(dt_value, self._trading_days)

    def get_nth_trading_day_of_month(self, year: int, month: int, n: int) -> Optional[date]:
        return get_nth_trading_day_of_month(year, month, n, trading_days=self._trading_days)

    def get_all_trading_days(self) -> Optional[List[date]]:
        return self._trading_days
