from __future__ import annotations

import pandas as pd

from strategy_kits.execution.data_gateways import jq_gateway as jq_mod
from strategy_kits.execution.data_gateways.jq_gateway import JQDataGateway


def test_get_bars_passes_full_ak_code_to_native_fetch(monkeypatch):
    gateway = JQDataGateway()
    seen: dict[str, str] = {}

    def _fake_fetch(ak_code: str, frequency: str, adjust: str) -> pd.DataFrame:
        seen["ak_code"] = ak_code
        return pd.DataFrame(
            {
                "datetime": pd.to_datetime(["2024-01-02", "2024-01-03"]),
                "open": [1.0, 1.1],
                "high": [1.2, 1.3],
                "low": [0.9, 1.0],
                "close": [1.1, 1.2],
                "volume": [100, 120],
            }
        )

    monkeypatch.setattr(jq_mod, "ak", object())
    monkeypatch.setattr(gateway, "_fetch_price_native", _fake_fetch)

    out = gateway.get_bars("000001.XSHE", count=1, unit="1d")

    assert seen["ak_code"] == "sz000001"
    assert len(out) == 1
