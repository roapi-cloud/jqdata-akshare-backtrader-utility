import warnings
from datetime import date
from typing import Dict, List, Optional

import pandas as pd

from ml_quant_framework.core.config import DataConfig

from .base import DataSource


class AkShareDataSource(DataSource):
    """AkShare开源数据源适配器。

    适配AkShare开源数据API，作为JQData的备用数据源。
    注意：AkShare 不支持部分高级因子和行业数据，相关方法会返回空数据或抛出异常。
    """

    _INDEX_MAP = {
        "000300": "000300",
        "399905": "399905",
        "000985": "000985",
        "000016": "000016",
        "000905": "000905",
    }

    def __init__(self, config: Optional[DataConfig] = None):
        """初始化AkShareDataSource。

        Args:
            config: 数据配置对象。
        """
        self.config = config or DataConfig()
        self._cache: Dict[str, pd.DataFrame] = {}

    def _resolve_index(self, index: str) -> str:
        """解析指数代码。

        Args:
            index: 指数代码。

        Returns:
            标准化后的指数代码。
        """
        for key, value in self._INDEX_MAP.items():
            if key in index:
                return value
        return "000985"

    def get_stock_list(self, index: str, date: date) -> List[str]:
        """获取指数成分股列表。

        Args:
            index: 指数代码。
            date: 查询日期。

        Returns:
            成分股代码列表（带后缀格式，如 "000001.SZ"）。
        """
        import akshare as ak

        symbol = self._resolve_index(index)
        try:
            df = ak.index_stock_cons_weight_csindex(symbol=symbol)
            codes = df["成分券代码"].astype(str).tolist()
            return [self._add_suffix(c) for c in codes]
        except Exception as e:
            warnings.warn(f"Failed to fetch stock list for {index}: {e}")
            return []

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
            行情数据 DataFrame。
        """
        import akshare as ak

        all_data = []
        start_str = str(start_date).replace("-", "")
        end_str = str(end_date).replace("-", "")

        for stock in stocks:
            code = stock.split(".")[0]
            try:
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_str,
                    end_date=end_str,
                    adjust="qfq",
                )
                if df is not None and not df.empty:
                    df["code"] = stock
                    df["date"] = pd.to_datetime(df["日期"])
                    df = df.rename(
                        columns={
                            "开盘": "open",
                            "收盘": "close",
                            "最高": "high",
                            "最低": "low",
                            "成交量": "volume",
                            "成交额": "money",
                        }
                    )
                    all_data.append(df)
            except Exception as e:
                warnings.warn(f"Failed to fetch price for {stock}: {e}")

        if not all_data:
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)
        result = result.set_index(["code", "date"]).sort_index()

        keep_cols = fields or ["close", "volume", "open", "high", "low", "money"]
        available_cols = [c for c in keep_cols if c in result.columns]
        if available_cols:
            result = result[available_cols]

        return result

    def get_fundamentals(
        self,
        stocks: List[str],
        date: date,
        fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """获取财务基本面数据。

        注意：AkShare 提供的财务数据接口有限，仅支持部分基础字段。

        Args:
            stocks: 股票代码列表。
            date: 查询日期。
            fields: 需要获取的字段列表。

        Returns:
            基本面数据 DataFrame。
        """
        import akshare as ak

        all_data = []
        date_str = str(date).replace("-", "")

        for stock in stocks:
            code = stock.split(".")[0]
            try:
                df = ak.stock_a_indicator_lg(symbol=code)
                if df is not None and not df.empty:
                    df["code"] = stock
                    all_data.append(df)
            except Exception:
                pass

        if not all_data:
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)
        result = result.set_index("code")

        if fields:
            available = [f for f in fields if f in result.columns]
            if available:
                result = result[available]

        return result

    def get_factor_values(
        self,
        stocks: List[str],
        factors: List[str],
        date: date,
    ) -> pd.DataFrame:
        """获取因子值。

        注意：AkShare 不支持聚宽因子库，此方法返回空 DataFrame。
        建议使用 JQDataSource 获取因子数据。

        Args:
            stocks: 股票代码列表。
            factors: 因子名称列表。
            date: 查询日期。

        Returns:
            空的 DataFrame。
        """
        warnings.warn(
            "AkShare does not support factor values. "
            "Please use JQDataSource for factor data."
        )
        return pd.DataFrame(index=stocks, columns=factors)

    def get_industry(
        self,
        stocks: List[str],
        date: date,
        classification: str = "sw_l1",
    ) -> Dict[str, str]:
        """获取行业分类。

        注意：AkShare 不支持行业分类数据，此方法返回空字典。
        建议使用 JQDataSource 获取行业数据。

        Args:
            stocks: 股票代码列表。
            date: 查询日期。
            classification: 行业分类标准。

        Returns:
            空字典。
        """
        warnings.warn(
            "AkShare does not support industry classification. "
            "Please use JQDataSource for industry data."
        )
        return {stock: "" for stock in stocks}

    def get_extras(
        self,
        field: str,
        stocks: List[str],
        date: date,
    ) -> Dict[str, bool]:
        """获取额外信息。

        注意：AkShare 不支持 ST 标识等额外信息，此方法返回默认值。

        Args:
            field: 字段名称。
            stocks: 股票代码列表。
            date: 查询日期。

        Returns:
            默认值字典 (全部 False)。
        """
        warnings.warn(
            f"AkShare does not support extras field '{field}'. "
            "Returning default values."
        )
        return {stock: False for stock in stocks}

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
        import akshare as ak

        try:
            df = ak.tool_trade_date_hist_sina()
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            mask = (df["trade_date"] >= pd.Timestamp(start_date)) & (
                df["trade_date"] <= pd.Timestamp(end_date)
            )
            days = df.loc[mask, "trade_date"].dt.date.tolist()

            if frequency == "monthly":
                df_filtered = pd.DataFrame(days, index=days)
                df_filtered.index = pd.to_datetime(df_filtered.index)
                return list(df_filtered.resample("ME").last().dropna().index.date)
            elif frequency == "weekly":
                df_filtered = pd.DataFrame(days, index=days)
                df_filtered.index = pd.to_datetime(df_filtered.index)
                return list(df_filtered.resample("W-FRI").last().dropna().index.date)

            return days
        except Exception as e:
            warnings.warn(f"Failed to fetch trade days: {e}")
            return []

    def get_security_info(self, stock: str) -> dict:
        """获取证券信息。

        Args:
            stock: 股票代码。

        Returns:
            证券信息字典。
        """
        import akshare as ak

        try:
            code = stock.split(".")[0]
            df = ak.stock_individual_info_em(symbol=code)
            info = {}
            for _, row in df.iterrows():
                info[row["item"]] = row["value"]
            return info
        except Exception as e:
            warnings.warn(f"Failed to fetch security info for {stock}: {e}")
            return {}

    @staticmethod
    def _add_suffix(code: str) -> str:
        """为股票代码添加交易所后缀。

        Args:
            code: 纯数字股票代码。

        Returns:
            带后缀的代码，如 "000001.SZ" 或 "600000.SH"。
        """
        code = str(code).zfill(6)
        if code.startswith(("6", "9")):
            return f"{code}.XSHG"
        elif code.startswith(("0", "3")):
            return f"{code}.XSHE"
        return f"{code}.XSHE"
