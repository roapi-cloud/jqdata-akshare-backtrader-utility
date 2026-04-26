"""JQ / AkShare 风格数据网关适配器。"""

import hashlib
import os
import re
import warnings
from typing import List, Optional, Union

import pandas as pd

from .base import BaseDataGateway
from .cache import FileCache
from .retry import retry_on_failure
from .symbol import canonicalize, to_ak, to_jq
from ...universe.trade_calendar import find_date_column

# AkShare 为可选依赖；实际运行时才 import
try:
    import akshare as ak
except Exception:  # pragma: no cover
    ak = None


class JQDataGateway(BaseDataGateway):
    """基于 AkShare 的聚宽风格适配器。"""

    def __init__(
        self,
        cache_dir: str = ".gateway_cache_jq",
        ttl_seconds: int = 86400,
        retry: int = 3,
        retry_sleep: float = 1.0,
    ):
        self.cache = FileCache(cache_dir, ttl_seconds)
        self.retry = retry
        self.retry_sleep = retry_sleep

    def _cache_key(self, method: str, **kwargs) -> str:
        payload = f"{method}:{sorted(kwargs.items())}"
        return hashlib.md5(payload.encode()).hexdigest()

    def _maybe_cached(self, method: str, force_update: bool, fetch_fn, **kwargs):
        key = self._cache_key(method, **kwargs)
        if not force_update:
            val = self.cache.get(key)
            if val is not None:
                return val
        val = fetch_fn()
        self.cache.set(key, val)
        return val

    # --------------------- 行情 ---------------------
    @retry_on_failure(max_retry=3, sleep=1.0)
    def get_price(
        self,
        symbols: Union[str, List[str]],
        start_date: str,
        end_date: str,
        frequency: str = "daily",
        fields: Optional[List[str]] = None,
        adjust: str = "qfq",
        count: Optional[int] = None,
        force_update: bool = False,
    ) -> Union[pd.DataFrame, dict[str, pd.DataFrame]]:
        if ak is None:
            raise ImportError("akshare is required for JQDataGateway")
        if isinstance(symbols, str):
            symbols = [symbols]
        symbols = [canonicalize(s) for s in symbols]
        result: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            ak_code = to_ak(symbol)
            df = self._maybe_cached(
                "get_price",
                force_update,
                lambda: self._fetch_price_native(ak_code, frequency, adjust),
                symbol=symbol,
                frequency=frequency,
                adjust=adjust,
            )
            if start_date and end_date:
                df = df[
                    (df["datetime"] >= pd.to_datetime(start_date))
                    & (df["datetime"] <= pd.to_datetime(end_date))
                ]
            if fields:
                keep = ["datetime"] + [f for f in fields if f in df.columns]
                df = df[keep]
            result[symbol] = df.reset_index(drop=True)
        return result if len(result) > 1 else result[symbols[0]]

    def _fetch_price_native(self, ak_code: str, frequency: str, adjust: str) -> pd.DataFrame:
        num_code = ak_code[2:]
        if frequency in ("1d", "daily"):
            df = ak.stock_zh_a_hist(symbol=num_code, period="daily", adjust=adjust)
        elif frequency in ("1m", "5m", "15m", "30m", "60m", "minute"):
            period_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60"}
            period = period_map.get(frequency, "1")
            df = ak.stock_zh_a_minute(symbol=ak_code, period=period)
        else:
            raise ValueError(f"Unsupported frequency: {frequency}")
        if df is None or df.empty:
            return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
        if "日期" in df.columns:
            df["datetime"] = pd.to_datetime(df["日期"])
        elif "时间" in df.columns:
            df["datetime"] = pd.to_datetime(df["时间"])
        col_map = {"开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume", "成交额": "money"}
        for k, v in col_map.items():
            if k in df.columns:
                df[v] = df[k]
        keep = ["datetime"] + [v for v in col_map.values() if v in df.columns]
        return df[keep].copy()

    @retry_on_failure(max_retry=3, sleep=1.0)
    def get_bars(
        self,
        security: str,
        count: int,
        unit: str = "1d",
        fields: Optional[List[str]] = None,
        end_dt: Optional[str] = None,
    ) -> pd.DataFrame:
        if ak is None:
            raise ImportError("akshare is required for JQDataGateway")
        ak_code = to_ak(canonicalize(security))
        df = self._fetch_price_native(ak_code, unit, adjust="qfq")
        if end_dt:
            df = df[df["datetime"] <= pd.to_datetime(end_dt)]
        df = df.tail(count)
        if fields:
            keep = ["datetime"] + [f for f in fields if f in df.columns]
            df = df[keep]
        return df.reset_index(drop=True)

    # --------------------- 基础信息 ---------------------
    @retry_on_failure(max_retry=3, sleep=1.0)
    def get_all_securities(
        self, types: Optional[List[str]] = None, date: Optional[str] = None, force_update: bool = False
    ) -> pd.DataFrame:
        if ak is None:
            raise ImportError("akshare is required for JQDataGateway")
        df = self._maybe_cached(
            "get_all_securities", force_update, lambda: ak.stock_info_a_code_name()
        )
        df["code"] = df["code"].astype(str).str.zfill(6)
        df["jq_code"] = df["code"].apply(
            lambda x: f"{x}.XSHG" if x.startswith("6") else f"{x}.XSHE"
        )
        return df.copy()

    @retry_on_failure(max_retry=3, sleep=1.0)
    def get_security_info(self, code: str) -> Optional[dict]:
        if ak is None:
            raise ImportError("akshare is required for JQDataGateway")
        jq_code = canonicalize(code)
        num = jq_code.split(".")[0]
        df = ak.stock_info_a_code_name()
        row = df[df["code"] == num]
        if row.empty:
            return None
        return row.iloc[0].to_dict()

    # --------------------- 财务 ---------------------
    @retry_on_failure(max_retry=3, sleep=1.0)
    def get_fundamentals(
        self,
        query_obj: dict,
        date: Optional[str] = None,
        stat_date: Optional[str] = None,
        force_update: bool = False,
    ) -> pd.DataFrame:
        if ak is None:
            raise ImportError("akshare is required for JQDataGateway")
        if not isinstance(query_obj, dict):
            raise NotImplementedError("仅支持 dict 类型 query_obj")
        table = query_obj.get("table")
        symbol = query_obj.get("symbol")
        ak_code = to_ak(canonicalize(symbol))
        if table == "balance":
            return self._fetch_balance(ak_code, stat_date, force_update)
        elif table == "income":
            return self._fetch_income(ak_code, force_update)
        elif table == "cash_flow":
            return self._fetch_cashflow(ak_code, stat_date, force_update)
        else:
            raise NotImplementedError(f"暂不支持的 table: {table}")

    def _fetch_balance(self, ak_code: str, stat_date, force_update):
        key = self._cache_key("balance", symbol=ak_code, stat_date=stat_date)
        if not force_update:
            val = self.cache.get(key)
            if val is not None:
                df = val
            else:
                df = ak.stock_financial_report_sina(stock=ak_code, symbol="资产负债表")
                self.cache.set(key, df)
        else:
            df = ak.stock_financial_report_sina(stock=ak_code, symbol="资产负债表")
            self.cache.set(key, df)
        if stat_date:
            df = self._filter_stat_date(df, stat_date)
        return df.reset_index(drop=True)

    def _fetch_income(self, ak_code: str, force_update):
        key = self._cache_key("income", symbol=ak_code)
        if not force_update:
            val = self.cache.get(key)
            if val is not None:
                df = val
            else:
                num = ak_code[2:]
                df = ak.stock_financial_benefit_ths(symbol=num, indicator="按报告期")
                self.cache.set(key, df)
        else:
            num = ak_code[2:]
            df = ak.stock_financial_benefit_ths(symbol=num, indicator="按报告期")
            self.cache.set(key, df)
        return df.reset_index(drop=True)

    def _fetch_cashflow(self, ak_code: str, stat_date, force_update):
        key = self._cache_key("cashflow", symbol=ak_code, stat_date=stat_date)
        if not force_update:
            val = self.cache.get(key)
            if val is not None:
                df = val
            else:
                df = ak.stock_financial_report_sina(stock=ak_code, symbol="现金流量表")
                self.cache.set(key, df)
        else:
            df = ak.stock_financial_report_sina(stock=ak_code, symbol="现金流量表")
            self.cache.set(key, df)
        if stat_date:
            df = self._filter_stat_date(df, stat_date)
        return df.reset_index(drop=True)

    @staticmethod
    def _filter_stat_date(df: pd.DataFrame, stat_date: str) -> pd.DataFrame:
        date_fields = ["报告日", "报告日期", "报表日期", "STATEMENT_DATE", "date"]
        date_col = next((f for f in date_fields if f in df.columns), None)
        if date_col is None:
            raise ValueError("找不到报告日期字段")
        return df[df[date_col] == stat_date]

    @retry_on_failure(max_retry=3, sleep=1.0)
    def get_history_fundamentals(
        self,
        security: Union[str, List[str]],
        fields: List[str],
        watch_date: Optional[str] = None,
        stat_date: Optional[str] = None,
        count: int = 1,
        interval: str = "1q",
        force_update: bool = False,
    ) -> pd.DataFrame:
        if isinstance(security, str):
            security = [security]
        cash_fields, income_fields, balance_fields = [], [], []
        for f in fields:
            if f.startswith("cash_flow."):
                cash_fields.append(f.split(".", 1)[1])
            elif f.startswith("income."):
                income_fields.append(f.split(".", 1)[1])
            elif f.startswith("balance."):
                balance_fields.append(f.split(".", 1)[1])
            else:
                warnings.warn(f"字段 {f} 未指定表前缀，已跳过。")
        dfs = []
        for code in security:
            ak_code = to_ak(canonicalize(code))
            out = pd.DataFrame()
            if cash_fields:
                df = self._fetch_cashflow(ak_code, stat_date, force_update)
                df = self._head_or_from_stat_date(df, stat_date, count)
                out["code"] = code
                out["statDate"] = df[self._find_date_col(df)]
                for f in cash_fields:
                    out[f"cash_flow.{f}"] = df.get(f, None)
            if income_fields:
                df = self._fetch_income(ak_code, force_update)
                df = self._head_or_from_stat_date(df, stat_date, count)
                if out.empty:
                    out["code"] = code
                    out["statDate"] = df[self._find_date_col(df)]
                for f in income_fields:
                    out[f"income.{f}"] = df.get(f, None)
            if balance_fields:
                df = self._fetch_balance(ak_code, stat_date, force_update)
                df = self._head_or_from_stat_date(df, stat_date, count)
                if out.empty:
                    out["code"] = code
                    out["statDate"] = df[self._find_date_col(df)]
                for f in balance_fields:
                    out[f"balance.{f}"] = df.get(f, None)
            dfs.append(out)
        result = pd.concat(dfs, ignore_index=True)
        if not result.empty:
            result.set_index(["code", "statDate"], inplace=True)
        return result

    def _head_or_from_stat_date(self, df: pd.DataFrame, stat_date, count: int) -> pd.DataFrame:
        date_col = self._find_date_col(df)
        if stat_date:
            idx = df[df[date_col] == stat_date].index
            if not idx.empty:
                start_idx = idx[0]
                return df.iloc[start_idx : start_idx + count]
        return df.head(count)

    @staticmethod
    def _find_date_col(df: pd.DataFrame) -> str:
        return find_date_column(df, category="financial") or df.columns[0]

    # --------------------- 指数成分 ---------------------
    @retry_on_failure(max_retry=3, sleep=1.0)
    def get_index_members(self, index_code: str, date: Optional[str] = None) -> List[str]:
        if ak is None:
            raise ImportError("akshare is required for JQDataGateway")
        df = ak.index_stock_cons(symbol=index_code)
        code_col = next((c for c in ["代码", "code", "证券代码", "品种代码"] if c in df.columns), df.columns[0])
        codes = df[code_col].astype(str).str.replace(".SH", "", regex=False).str.replace(".SZ", "", regex=False).str.zfill(6).tolist()
        return [to_jq(c) for c in codes]

    # --------------------- 交易日历 ---------------------
    @retry_on_failure(max_retry=3, sleep=1.0)
    def get_trade_days(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[pd.Timestamp]:
        if ak is None:
            raise ImportError("akshare is required for JQDataGateway")
        df = ak.tool_trade_date_hist_sina()
        days = pd.to_datetime(df["trade_date"]).tolist()
        if start_date:
            days = [d for d in days if d >= pd.to_datetime(start_date)]
        if end_date:
            days = [d for d in days if d <= pd.to_datetime(end_date)]
        return days

    # --------------------- Extras ---------------------
    @retry_on_failure(max_retry=3, sleep=1.0)
    def get_extras(
        self,
        field: str,
        securities: Union[str, List[str]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        if ak is None:
            raise ImportError("akshare is required for JQDataGateway")
        if isinstance(securities, str):
            securities = [securities]
        nums = [canonicalize(s).split(".")[0] for s in securities]
        if field == "is_st":
            df = ak.stock_zh_a_st_em()
            return df[df["代码"].isin(nums)].copy()
        elif field == "is_paused":
            df = ak.stock_zh_a_stop_em()
            return df[df["代码"].isin(nums)].copy()
        else:
            raise NotImplementedError(f"暂不支持的 extras 字段: {field}")
