from __future__ import annotations

from datetime import date, time

from strategy_kits.execution.backtrader_runtime.timer_rules import (
    MARKET_OPEN_TIME,
    check_bar_time_match,
    parse_time_rule,
    should_execute_timer,
)


def test_parse_time_rule_supports_offsets_and_absolute_times():
    assert parse_time_rule("14:50") == ("absolute", time(14, 50), None)
    assert parse_time_rule("open+5m") == ("open_offset", time(9, 35), 5)
    assert parse_time_rule("close-10m") == ("close_offset", time(14, 50), -10)


def test_daily_bar_matches_specific_time_rules_once_per_day():
    rule_type, target_time, _ = parse_time_rule("14:50")
    assert check_bar_time_match(None, rule_type, target_time, bar_resolution_minutes=390) is True

    should_run, reason = should_execute_timer(
        frequency="daily",
        current_date=date(2024, 1, 3),
        current_time=None,
        last_executed=None,
        time_rule="14:50",
        trading_days=[date(2024, 1, 2), date(2024, 1, 3)],
        bar_resolution_minutes=390,
    )
    assert should_run is True
    assert reason == "daily"


def test_weekly_and_monthly_timer_rules_respect_trading_calendar():
    trading_days = [
        date(2024, 1, 2),
        date(2024, 1, 3),
        date(2024, 1, 4),
        date(2024, 1, 5),
        date(2024, 1, 8),
        date(2024, 1, 9),
    ]

    weekly_run, _ = should_execute_timer(
        frequency="weekly",
        current_date=date(2024, 1, 8),
        current_time=MARKET_OPEN_TIME,
        last_executed=date(2024, 1, 2),
        time_rule="open",
        weekday=1,
        trading_days=trading_days,
    )
    monthly_run, _ = should_execute_timer(
        frequency="monthly",
        current_date=date(2024, 1, 2),
        current_time=MARKET_OPEN_TIME,
        last_executed=None,
        time_rule="open",
        day=1,
        trading_days=trading_days,
    )

    assert weekly_run is True
    assert monthly_run is True
