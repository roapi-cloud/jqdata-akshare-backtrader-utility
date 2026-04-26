from __future__ import annotations

from datetime import date

from strategy_kits.universe.stock_pool_filters import (
    apply_filters,
    filter_limitdown,
    filter_limitup,
    filter_new_stock,
    filter_paused,
    filter_st,
)
from strategy_kits.universe.stock_pool_filters.contract import FilterInput


def test_filter_st_with_map_and_name():
    base = ["600001.XSHG", "000001.XSHE", "000002.XSHE"]
    output = filter_st(
        FilterInput(
            base_universe=base,
            date=date(2024, 1, 5),
            config={
                "is_st_map": {"600001.XSHG": True},
                "name_map": {"000001.XSHE": "平安银行", "000002.XSHE": "*ST万科"},
                "check_name": True,
            },
        )
    )
    assert output.filtered_universe == ["000001.XSHE"]
    assert output.filter_stats["st"] == 2


def test_filter_paused_with_threshold():
    base = ["600001.XSHG", "000001.XSHE", "000002.XSHE"]
    output = filter_paused(
        FilterInput(
            base_universe=base,
            date=date(2024, 1, 5),
            config={
                "paused_N": 3,
                "threshold": 2,
                "paused_history_map": {
                    "600001.XSHG": [1, 1, 0],
                    "000001.XSHE": [0, 0, 0],
                    "000002.XSHE": [1, 0, 0],
                },
            },
        )
    )
    assert output.filtered_universe == ["000001.XSHE", "000002.XSHE"]
    assert output.filter_stats["paused"] == 1


def test_filter_new_stock_min_days():
    base = ["600001.XSHG", "000001.XSHE"]
    output = filter_new_stock(
        FilterInput(
            base_universe=base,
            date=date(2024, 1, 5),
            config={
                "min_days": 250,
                "listing_date_map": {
                    "600001.XSHG": "2020-01-01",
                    "000001.XSHE": "2023-09-01",
                },
            },
        )
    )
    assert output.filtered_universe == ["600001.XSHG"]
    assert output.removed_reasons["new_stock"] == ["000001.XSHE"]


def test_filter_limitup_limitdown_keep_positions():
    base = ["600001.XSHG", "000001.XSHE", "000002.XSHE"]
    config = {
        "price_map": {"600001.XSHG": 10.0, "000001.XSHE": 11.0, "000002.XSHE": 9.0},
        "high_limit_map": {"600001.XSHG": 10.0, "000001.XSHE": 12.0, "000002.XSHE": 10.0},
        "low_limit_map": {"600001.XSHG": 9.0, "000001.XSHE": 10.0, "000002.XSHE": 9.0},
        "keep_positions": True,
    }

    limitup_out = filter_limitup(
        FilterInput(
            base_universe=base,
            date=date(2024, 1, 5),
            config=config,
            positions=["600001.XSHG"],
        )
    )
    assert "600001.XSHG" in limitup_out.filtered_universe
    assert "000002.XSHE" in limitup_out.filtered_universe

    limitdown_out = filter_limitdown(
        FilterInput(
            base_universe=base,
            date=date(2024, 1, 5),
            config=config,
            positions=["000002.XSHE"],
        )
    )
    assert "000002.XSHE" in limitdown_out.filtered_universe
    assert "600001.XSHG" in limitdown_out.filtered_universe


def test_apply_filters_pipeline_e2e():
    base = [
        "600001.XSHG",
        "000001.XSHE",
        "000002.XSHE",
        "688001.XSHG",
    ]
    cfg = {
        "st": {
            "enabled": True,
            "is_st_map": {"600001.XSHG": True},
            "check_name": False,
        },
        "paused": {
            "enabled": True,
            "paused_map": {"000002.XSHE": 1},
        },
        "new_stock": {
            "enabled": True,
            "min_days": 250,
            "listing_date_map": {
                "000001.XSHE": "2010-01-01",
                "688001.XSHG": "2018-06-01",
            },
        },
        "limitup": {"enabled": False},
        "limitdown": {"enabled": False},
        "kcbj": {"enabled": True},
    }
    result = apply_filters(
        base_universe=base,
        date=date(2024, 1, 5),
        filter_config=cfg,
        positions=None,
    )
    assert result.filtered_universe == ["000001.XSHE"]
    assert result.filter_stats["st"] == 1
    assert result.filter_stats["paused"] == 1
    assert result.filter_stats["kcbj"] == 1

