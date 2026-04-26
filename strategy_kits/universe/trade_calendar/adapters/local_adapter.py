"""Local gateway adapter for strategy_kits trade calendar and universe."""
from __future__ import annotations

from typing import List, Optional

from ..trade_calendar import init_trade_cal_from_gateway
from ..universe_selector import BaseUniverseAdapter, set_default_adapter


class LocalGatewayAdapter(BaseUniverseAdapter):
    """Wrap a BaseDataGateway-like object as a UniverseAdapter."""

    def __init__(self, gateway):
        self.gateway = gateway

    def get_all_securities(
        self, types: Optional[List[str]] = None, date: Optional[str] = None
    ) -> List[str]:
        df = self.gateway.get_all_securities(types=types, date=date)
        if hasattr(df, "index"):
            return list(df.index.astype(str))
        return []

    def get_index_stocks(self, index_code: str, date: Optional[str] = None) -> List[str]:
        return self.gateway.get_index_members(index_code=index_code, date=date)

    def get_industry_stocks(
        self, industry_code: str, level: str = "sw_l1", date: Optional[str] = None
    ) -> List[str]:
        if hasattr(self.gateway, "get_industry_stocks"):
            return self.gateway.get_industry_stocks(industry_code=industry_code, level=level, date=date)
        raise NotImplementedError("gateway does not implement get_industry_stocks")


def init_cal_from_local_gateway(
    gateway,
    start: str = "2010-01-01",
    end: Optional[str] = None,
    set_as_default_adapter: bool = True,
):
    """Initialize trade calendar and adapter from local gateway."""
    adapter = LocalGatewayAdapter(gateway)
    init_trade_cal_from_gateway(gateway=gateway, start_date=start, end_date=end)
    if set_as_default_adapter:
        set_default_adapter(adapter)
    return adapter

