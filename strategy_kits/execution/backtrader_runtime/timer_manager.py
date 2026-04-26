"""Timer manager adapted from jk2bt for JoinQuant-style scheduling."""
from __future__ import annotations

from datetime import time
from typing import Any, Callable, Optional

from .timer_rules import TradingDayCalendar, should_execute_timer


class TimerManager:
    """Manage run_daily/run_weekly/run_monthly callbacks for a strategy."""

    def __init__(self, strategy: Any, trading_days: Optional[list] = None):
        self._strategy = strategy
        self._timers: list[dict[str, Any]] = []
        self._trading_days = trading_days
        self._calendar = TradingDayCalendar(trading_days)
        self._bar_resolution_minutes = 390

    def set_trading_days(self, trading_days: Optional[list]) -> None:
        self._trading_days = trading_days
        self._calendar.set_trading_days(trading_days)

    def set_bar_resolution(self, minutes: int) -> None:
        self._bar_resolution_minutes = max(1, int(minutes))

    def infer_bar_resolution(self) -> None:
        datas = getattr(self._strategy, "datas", None)
        if not datas:
            return
        try:
            if len(datas[0]) >= 2:
                dt0 = datas[0].datetime.datetime(0)
                dt1 = datas[0].datetime.datetime(-1)
                delta = int((dt0 - dt1).total_seconds() / 60)
                if delta >= 24 * 60:
                    self._bar_resolution_minutes = 390
                elif delta > 0:
                    self._bar_resolution_minutes = max(1, delta)
        except Exception:
            return

    def register(
        self,
        func: Callable,
        frequency: str,
        time_rule: Optional[str] = None,
        day: Optional[int] = None,
        weekday: Optional[int] = None,
    ) -> None:
        self._timers.append(
            {
                "func": func,
                "frequency": frequency,
                "time_rule": time_rule,
                "day": day,
                "weekday": weekday,
                "last_executed": None,
            }
        )

    def check_and_execute(self) -> None:
        current_date, current_time = self._current_bar_clock()
        self.infer_bar_resolution()

        for timer in self._timers:
            should_run, _ = should_execute_timer(
                frequency=timer["frequency"],
                current_date=current_date,
                current_time=current_time,
                last_executed=timer["last_executed"],
                time_rule=timer["time_rule"],
                day=timer["day"],
                weekday=timer["weekday"],
                trading_days=self._trading_days,
                bar_resolution_minutes=self._bar_resolution_minutes,
            )
            if not should_run:
                continue
            timer["func"](self._strategy.context)
            timer["last_executed"] = current_date

    def _current_bar_clock(self) -> tuple[Any, Optional[time]]:
        dt_value = self._strategy.datas[0].datetime.datetime(0)
        current_date = dt_value.date()
        current_time = dt_value.time()
        if current_time == time(0, 0):
            current_time = None
        return current_date, current_time
