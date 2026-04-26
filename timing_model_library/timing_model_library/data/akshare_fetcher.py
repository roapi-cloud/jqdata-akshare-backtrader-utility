# -*- coding: utf-8 -*-
"""
数据获取层: AKShare 数据获取 + 本地缓存
"""

import os
import pickle
import datetime
from typing import Optional
import pandas as pd
import akshare as ak


class DataCache:
    """本地数据缓存"""

    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _cache_path(self, key: str) -> str:
        safe_key = key.replace("/", "_").replace(":", "_")
        return os.path.join(self.cache_dir, f"{safe_key}.pkl")

    def get(self, key: str) -> Optional[pd.DataFrame]:
        path = self._cache_path(key)
        if os.path.exists(path):
            with open(path, "rb") as f:
                data, cached_time = pickle.load(f)
                if cached_time.date() == datetime.date.today():
                    return data
        return None

    def put(self, key: str, data: pd.DataFrame) -> None:
        path = self._cache_path(key)
        with open(path, "wb") as f:
            pickle.dump((data, datetime.datetime.now()), f)


class AKShareFetcher:
    """AKShare 数据获取器"""

    def __init__(self, cache: bool = True, cache_dir: str = ".cache"):
        self.cache = DataCache(cache_dir) if cache else None

    def get_index_daily(
        self,
        symbol: str = "000300",
        start_date: str = "20100101",
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取指数日线数据

        Args:
            symbol: 指数代码 (000300=沪深300, 000001=上证指数, 000905=中证500)
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount
        """
        cache_key = f"index_daily_{symbol}_{start_date}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        if end_date is None:
            end_date = datetime.date.today().strftime("%Y%m%d")

        df = ak.index_zh_a_hist(
            symbol=symbol, period="daily", start_date=start_date, end_date=end_date
        )

        df = df.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
            }
        )
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        if self.cache:
            self.cache.put(cache_key, df)

        return df

    def get_northbound_flow(
        self, start_date: str = "20140101", end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取北向资金流向数据

        Returns:
            DataFrame with columns: date, north_buy, north_sell, north_net
        """
        cache_key = f"northbound_{start_date}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        if end_date is None:
            end_date = datetime.date.today().strftime("%Y%m%d")

        df = ak.stock_hsgt_hist_em(
            symbol="北上", start_date=start_date, end_date=end_date
        )

        df = df.rename(
            columns={
                "日期": "date",
                "当日资金流入": "north_net",
            }
        )
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        if self.cache:
            self.cache.put(cache_key, df)

        return df

    def get_market_breadth(
        self, start_date: str = "20180101", end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取市场宽度数据 (涨跌家数)

        Returns:
            DataFrame with columns: date, up_count, down_count, flat_count
        """
        cache_key = f"market_breadth_{start_date}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        if end_date is None:
            end_date = datetime.date.today().strftime("%Y%m%d")

        df = ak.stock_market_activity_legu()
        df = df.rename(
            columns={
                "日期": "date",
            }
        )
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        if self.cache:
            self.cache.put(cache_key, df)

        return df

    def get_bond_yield(
        self,
        bond_type: str = "国债",
        period: str = "10年",
        start_date: str = "20100101",
    ) -> pd.DataFrame:
        """
        获取债券收益率曲线

        Args:
            bond_type: 债券类型 (国债/企业债)
            period: 期限 (1年/3年/5年/10年)
        """
        cache_key = f"bond_yield_{bond_type}_{period}_{start_date}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        df = ak.bond_china_yield(start_date=start_date)

        if self.cache:
            self.cache.put(cache_key, df)

        return df

    def get_turnover_rate(
        self,
        symbol: str = "000001",
        start_date: str = "20100101",
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取市场换手率数据
        """
        cache_key = f"turnover_{symbol}_{start_date}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        if end_date is None:
            end_date = datetime.date.today().strftime("%Y%m%d")

        df = ak.index_zh_a_hist(
            symbol=symbol, period="daily", start_date=start_date, end_date=end_date
        )

        df = df.rename(
            columns={
                "日期": "date",
                "换手率": "turnover_rate",
            }
        )
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        if self.cache:
            self.cache.put(cache_key, df)

        return df

    def get_congestion_rate(self) -> pd.DataFrame:
        """
        获取大盘拥挤度指标
        """
        cache_key = "congestion_rate"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            df = ak.stock_a_congestion_lg()
            if self.cache:
                self.cache.put(cache_key, df)
            return df
        except Exception as e:
            print(f"获取拥挤度数据失败: {e}")
            return pd.DataFrame()

    def get_margin_balance(self, start_date: str = "20100101") -> pd.DataFrame:
        """
        获取融资融券余额
        """
        cache_key = f"margin_{start_date}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        df_sse = ak.stock_margin_sse(start_date=start_date)
        df_szse = ak.stock_margin_szse(start_date=start_date)

        if self.cache:
            self.cache.put(cache_key, df_sse)

        return df_sse
