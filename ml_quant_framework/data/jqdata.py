from datetime import date
from typing import Dict, List, Optional

import pandas as pd

from ml_quant_framework.core.config import DataConfig

from .base import DataSource


class JQDataSource(DataSource):
    """JQData聚宽数据源适配器。

    适配聚宽JQData API，提供A股行情、基本面、因子、行业等数据的统一访问接口。
    适用于聚宽研究环境或已安装jqdata/jqfactor库的本地环境。
    """

    def __init__(self, config: Optional[DataConfig] = None):
        """初始化JQDataSource。

        Args:
            config: 数据配置对象，包含数据源类型、指数代码、日期范围等。
        """
        self.config = config or DataConfig()
        self._authenticated = False

    def _ensure_auth(self) -> None:
        """确保已认证。

        在聚宽研究环境中通常已自动认证，此处做幂等检查。
        """
        if not self._authenticated:
            try:
                from jqdata import auth

                if not auth.is_auth():
                    raise RuntimeError("JQData not authenticated. Please login first.")
            except ImportError:
                pass
            self._authenticated = True

    def get_stock_list(self, index: str, date: date) -> List[str]:
        """获取指数成分股列表。

        Args:
            index: 指数代码，如 "000300.XSHG"。
            date: 查询日期。

        Returns:
            成分股代码列表。
        """
        from jqdata import get_index_stocks

        self._ensure_auth()
        return get_index_stocks(index, date=date)

    def get_price(
        self,
        stocks: List[str],
        start_date: date,
        end_date: date,
        fields: Optional[List[str]] = None,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """获取行情数据。

        Args:
            stocks: 股票代码列表。
            start_date: 起始日期。
            end_date: 结束日期。
            fields: 需要获取的字段列表。
            frequency: 数据频率。

        Returns:
            行情数据 DataFrame，MultiIndex 为 (code, date)。
        """
        from jqdata import get_price

        self._ensure_auth()
        default_fields = ["close", "volume", "open", "high", "low", "money"]
        return get_price(
            stocks,
            start_date=start_date,
            end_date=end_date,
            fields=fields or default_fields,
            frequency=frequency,
        )

    def get_fundamentals(
        self,
        stocks: List[str],
        date: date,
        fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """获取财务基本面数据。

        自动根据字段名映射到对应的财务表 (valuation, balance, income,
        indicator, cash_flow)。

        Args:
            stocks: 股票代码列表。
            date: 查询日期。
            fields: 需要获取的字段列表。

        Returns:
            基本面数据 DataFrame，索引为股票代码。
        """
        from jqdata import (
            balance,
            cash_flow,
            get_fundamentals,
            income,
            indicator,
            query,
            valuation,
        )

        self._ensure_auth()

        table_map = {
            "valuation": valuation,
            "balance": balance,
            "income": income,
            "indicator": indicator,
            "cash_flow": cash_flow,
        }

        field_to_table = {}
        for table_name, table_obj in table_map.items():
            for col in table_obj.__dict__.get("_columns", {}):
                field_to_table[col] = table_obj

        if fields is None:
            fields = ["pe_ratio", "pb_ratio", "market_cap", "circulating_market_cap"]

        grouped_fields: Dict[object, List[str]] = {}
        for f in fields:
            tbl = field_to_table.get(f, valuation)
            if tbl not in grouped_fields:
                grouped_fields[tbl] = []
            grouped_fields[tbl].append(f)

        q = query(valuation.code)
        for tbl, cols in grouped_fields.items():
            for col in cols:
                q = q.add_column(getattr(tbl, col))

        q = q.filter(valuation.code.in_(stocks))
        df = get_fundamentals(q, date=date)

        if df is not None and not df.empty and "code" in df.columns:
            df = df.set_index("code")

        return df

    def get_factor_values(
        self,
        stocks: List[str],
        factors: List[str],
        date: date,
    ) -> pd.DataFrame:
        """获取因子值。

        Args:
            stocks: 股票代码列表。
            factors: 因子名称列表。
            date: 查询日期。

        Returns:
            因子值 DataFrame，索引为股票代码，列为因子名称。
        """
        from jqfactor import get_factor_values

        self._ensure_auth()
        result = get_factor_values(
            securities=stocks, factors=factors, count=1, end_date=date
        )

        df = pd.DataFrame(index=stocks)
        for f in factors:
            if f in result and result[f] is not None and not result[f].empty:
                df[f] = result[f].iloc[:, 0]
            else:
                df[f] = None
        return df

    def get_industry(
        self,
        stocks: List[str],
        date: date,
        classification: str = "sw_l1",
    ) -> Dict[str, str]:
        """获取行业分类。

        Args:
            stocks: 股票代码列表。
            date: 查询日期。
            classification: 行业分类标准。

        Returns:
            股票到行业代码的映射字典。
        """
        from jqdata import get_industry

        self._ensure_auth()
        raw = get_industry(securities=stocks, date=date)

        result = {}
        for stock, info in raw.items():
            if info and classification in info:
                result[stock] = info[classification].get("industry_code", "")
            else:
                result[stock] = ""
        return result

    def get_extras(
        self,
        field: str,
        stocks: List[str],
        date: date,
    ) -> Dict[str, bool]:
        """获取额外信息。

        Args:
            field: 字段名称，如 "is_st"。
            stocks: 股票代码列表。
            date: 查询日期。

        Returns:
            股票到额外信息的映射字典。
        """
        from jqdata import get_extras

        self._ensure_auth()
        raw = get_extras(field, stocks, count=1, end_date=date)

        result = {}
        for stock in stocks:
            if stock in raw and not raw[stock].empty:
                result[stock] = bool(raw[stock].iloc[-1])
            else:
                result[stock] = False
        return result

    def get_trade_days(
        self,
        start_date: date,
        end_date: date,
        frequency: str = "1d",
    ) -> List[date]:
        """获取交易日历。

        Args:
            start_date: 起始日期。
            end_date: 结束日期。
            frequency: 频率。

        Returns:
            交易日列表。
        """
        from jqdata import get_trade_days

        self._ensure_auth()
        days = get_trade_days(start_date=start_date, end_date=end_date)

        if frequency == "monthly":
            df = pd.DataFrame(days, index=days)
            df.index = pd.to_datetime(df.index)
            return list(df.resample("ME").last().dropna().index.date)
        elif frequency == "weekly":
            df = pd.DataFrame(days, index=days)
            df.index = pd.to_datetime(df.index)
            return list(df.resample("W-FRI").last().dropna().index.date)

        return list(days)

    def get_security_info(self, stock: str) -> dict:
        """获取证券信息。

        Args:
            stock: 股票代码。

        Returns:
            证券信息字典，包含 start_date, end_date, name, type 等。
        """
        from jqdata import get_security_info

        self._ensure_auth()
        info = get_security_info(stock)
        if info is not None:
            return {
                "start_date": info.start_date,
                "end_date": info.end_date,
                "name": info.display_name,
                "type": info.type,
            }
        return {}
