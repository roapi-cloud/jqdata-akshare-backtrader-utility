from __future__ import annotations

import pytest

pytest.importorskip("backtrader")

from strategy_kits.execution.backtrader_runtime.compat import JQ2BTBaseStrategy, _symbol_aliases


class _DummyData:
    def __init__(self, name: str, code: str | None = None):
        self._name = name
        self.code = code


class _DummyStrategy:
    _find_data = JQ2BTBaseStrategy._find_data

    def __init__(self, datas):
        self.datas = datas


def test_symbol_aliases_cover_common_formats():
    aliases = _symbol_aliases("000001.XSHE")
    assert "000001.XSHE" in aliases
    assert "sz000001" in aliases
    assert "000001.SZ" in aliases
    assert "SZ000001" in aliases


def test_find_data_matches_cross_format_symbols():
    st = _DummyStrategy(
        datas=[
            _DummyData("sz000001"),
            _DummyData("sh600000", code="600000.SH"),
        ]
    )

    d1 = st._find_data("000001.XSHE")
    d2 = st._find_data("600000.XSHG")
    d3 = st._find_data("600000")

    assert d1._name == "sz000001"
    assert d2._name == "sh600000"
    assert d3._name == "sh600000"

    with pytest.raises(ValueError):
        st._find_data("300999.XSHE")

