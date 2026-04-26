from __future__ import annotations

from strategy_kits.execution.data_gateways.symbol import (
    canonicalize,
    format_stock_symbol,
    get_symbol_prefix,
    is_valid_stock_code,
    to_ak,
    to_jq,
    to_ts,
)


def test_symbol_utils_preserve_explicit_exchange_and_common_formats():
    assert to_jq("sh600000") == "600000.XSHG"
    assert to_jq("000001.SZ") == "000001.XSHE"
    assert to_jq("000300.XSHG") == "000300.XSHG"
    assert to_jq("399006.XSHE") == "399006.XSHE"
    assert to_ak("510300.XSHG") == "sh510300"
    assert to_ts("159915.XSHE") == "159915.SZ"
    assert canonicalize("SZ000001") == "000001.XSHE"


def test_symbol_utils_numeric_body_and_prefix_helpers():
    assert format_stock_symbol("sh600519") == "600519"
    assert format_stock_symbol("000001.XSHE") == "000001"
    assert get_symbol_prefix("510300.XSHG") == "sh"
    assert get_symbol_prefix("159915.XSHE") == "sz"
    assert is_valid_stock_code("600000.SH") is True
    assert is_valid_stock_code("bad_code") is False
