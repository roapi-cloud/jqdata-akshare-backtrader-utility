from __future__ import annotations

from pathlib import Path

import pandas as pd

from strategy_kits.universe.trade_calendar import (
    find_date_column,
    get_all_trade_days,
    get_next_trade_date,
    get_previous_trade_date,
    get_rebalance_dates,
    get_trade_days,
    is_trade_date,
    init_trade_cal_from_csv,
    is_trade_cal_initialized,
    set_trade_cal_source,
    shift_trade_day,
)
from strategy_kits.universe.trade_calendar import trade_calendar as tc_mod


def test_trade_calendar_basic_and_shift():
    days = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
    )
    set_trade_cal_source(days)
    assert is_trade_cal_initialized() is True

    out = get_trade_days(start="2024-01-02", end="2024-01-05")
    assert len(out) == 4
    assert str(shift_trade_day("2024-01-05", 1).date()) == "2024-01-08"


def test_trade_calendar_business_day_fallback():
    tc_mod._TRADE_CAL_CACHE = None
    out = get_all_trade_days(
        allow_business_day_fallback=True,
        fallback_start="2024-01-01",
        fallback_end="2024-01-10",
    )
    assert len(out) >= 7
    assert out[0] == pd.Timestamp("2024-01-01")


def test_init_trade_calendar_from_csv(tmp_path: Path):
    file = tmp_path / "trade_days.csv"
    pd.DataFrame({"date": ["2024-02-01", "2024-02-02", "2024-02-05"]}).to_csv(file, index=False)
    out = init_trade_cal_from_csv(str(file))
    assert list(out) == [
        pd.Timestamp("2024-02-01"),
        pd.Timestamp("2024-02-02"),
        pd.Timestamp("2024-02-05"),
    ]


def test_rebalance_month_anchor_clamps_to_month_end():
    set_trade_cal_source(pd.bdate_range("2024-01-01", "2024-03-31"))
    dates = get_rebalance_dates(
        start="2024-01-01",
        end="2024-03-31",
        freq="1M",
        anchor=31,
    )
    # Feb should align to 2024-02-29 (trade day)
    assert pd.Timestamp("2024-02-29") in dates


def test_trade_calendar_count_only_and_trade_date_aliases():
    set_trade_cal_source(pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-05"]))

    out = get_trade_days(count=2)
    assert list(out) == [pd.Timestamp("2024-01-03"), pd.Timestamp("2024-01-05")]
    assert is_trade_date("2024-01-03") is True
    assert is_trade_date("2024-01-04") is False
    assert get_previous_trade_date("2024-01-05") == pd.Timestamp("2024-01-03")
    assert get_next_trade_date("2024-01-03") == pd.Timestamp("2024-01-05")


def test_find_date_column_supports_market_and_financial_variants():
    market_df = pd.DataFrame({"trade_date": ["2024-01-01"]})
    financial_df = pd.DataFrame({"报告日期": ["2024-03-31"]})

    assert find_date_column(market_df, category="market") == "trade_date"
    assert find_date_column(financial_df, category="financial") == "报告日期"
