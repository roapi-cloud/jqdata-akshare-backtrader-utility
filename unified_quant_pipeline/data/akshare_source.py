"""AKShare数据源实现"""

import logging
import pandas as pd
from typing import List, Optional
from datetime import datetime

from .base import BaseDataSource
from .cache import DataCache

logger = logging.getLogger(__name__)


class AKShareSource(BaseDataSource):
    """AKShare数据源

    基于AKShare SDK获取A股数据，支持本地缓存。
    """

    name: str = "akshare"

    def __init__(self, cache_dir: str = "./data_cache", force_update: bool = False):
        """初始化AKShare数据源

        Args:
            cache_dir: 缓存目录路径
            force_update: 是否强制更新
        """
        self.cache = DataCache(cache_dir, force_update)
        self._trade_dates_cache: Optional[pd.DataFrame] = None

    def get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取A股交易日历

        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            List[str]: 交易日期列表
        """
        import akshare as ak

        cache_key = f"trade_dates_{start_date}_{end_date}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            df = ak.tool_trade_date_hist_sina()
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            mask = (df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)
            dates = df.loc[mask, "trade_date"].dt.strftime("%Y-%m-%d").tolist()
        except Exception as e:
            logger.warning(f"Failed to get trade dates from AKShare: {e}")
            dates = []

        self.cache.set(cache_key, dates)
        return dates

    def get_index_components(
        self, index_code: str, date: Optional[str] = None
    ) -> List[str]:
        """获取指数成分股

        Args:
            index_code: 指数代码，如 000300
            date: 日期，None表示最新

        Returns:
            List[str]: 股票代码列表
        """
        import akshare as ak

        cache_key = f"index_components_{index_code}_{date}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            if index_code == "000300":
                df = ak.index_stock_cons_weight_csindex(symbol="000300")
            elif index_code == "000905":
                df = ak.index_stock_cons_weight_csindex(symbol="000905")
            elif index_code == "000852":
                df = ak.index_stock_cons_weight_csindex(symbol="000852")
            else:
                df = ak.index_stock_cons_weight_csindex(symbol=index_code)

            stocks = df["成分券代码"].tolist()
            stocks = [s.zfill(6) for s in stocks]
        except Exception as e:
            logger.warning(f"Failed to get index components for {index_code}: {e}")
            stocks = []

        self.cache.set(cache_key, stocks)
        return stocks

    def get_stock_data(
        self, stocks: List[str], dates: List[str], fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """获取股票日线数据

        Args:
            stocks: 股票代码列表
            dates: 日期列表
            fields: 字段列表，None表示默认字段

        Returns:
            pd.DataFrame: 股票日线数据
        """
        import akshare as ak

        if fields is None:
            fields = ["open", "high", "low", "close", "volume", "amount"]

        all_data = []
        for stock in stocks:
            cache_key = f"stock_daily_{stock}"
            cached = self.cache.get(cache_key)

            if cached is not None:
                df = cached
            else:
                try:
                    df = ak.stock_zh_a_hist(
                        symbol=stock,
                        period="daily",
                        start_date=dates[0].replace("-", ""),
                        end_date=dates[-1].replace("-", ""),
                        adjust="qfq",
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
                except Exception as e:
                    logger.warning(f"Failed to get data for {stock}: {e}")
                    continue

                self.cache.set(cache_key, df)

            df = df[df["date"].isin(pd.to_datetime(dates))].copy()
            df["code"] = stock
            all_data.append(df[fields + ["date", "code"]])

        if not all_data:
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)
        return result

    def get_fundamentals(
        self, stocks: List[str], date: str, fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """获取基本面数据（估值指标）

        Args:
            stocks: 股票代码列表
            date: 财报日期
            fields: 字段列表

        Returns:
            pd.DataFrame: 基本面数据
        """
        import akshare as ak

        all_data = []
        for stock in stocks:
            try:
                df = ak.stock_individual_info_em(symbol=stock)
                data = {"code": stock, "date": date}
                for _, row in df.iterrows():
                    key = row["item"]
                    value = row["value"]
                    data[key] = value

                all_data.append(data)
            except Exception as e:
                logger.warning(f"Failed to get fundamentals for {stock}: {e}")
                continue

        if not all_data:
            return pd.DataFrame()

        return pd.DataFrame(all_data)
