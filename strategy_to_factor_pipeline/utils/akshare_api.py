"""
AkShare API封装
提供AkShare数据接口的统一访问
"""

from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
from loguru import logger


class AkShareAPI:
    """AkShare数据API封装"""

    def __init__(self):
        pass

    def get_stock_zh_a_hist(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20150101",
        end_date: str = "20241231",
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取A股历史行情"""
        try:
            import akshare as ak

            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            return df
        except Exception as e:
            logger.error(f"获取A股历史行情失败 {symbol}: {e}")
            return pd.DataFrame()

    def get_stock_zh_a_spot_em(self) -> pd.DataFrame:
        """获取A股实时行情"""
        try:
            import akshare as ak

            return ak.stock_zh_a_spot_em()
        except Exception as e:
            logger.error(f"获取A股实时行情失败: {e}")
            return pd.DataFrame()

    def get_stock_individual_info_em(self, symbol: str) -> pd.DataFrame:
        """获取个股信息"""
        try:
            import akshare as ak

            return ak.stock_individual_info_em(symbol=symbol)
        except Exception as e:
            logger.error(f"获取个股信息失败 {symbol}: {e}")
            return pd.DataFrame()

    def get_stock_financial_abstract_em(self, symbol: str) -> pd.DataFrame:
        """获取财务摘要"""
        try:
            import akshare as ak

            return ak.stock_financial_abstract_em(symbol=symbol)
        except Exception as e:
            logger.error(f"获取财务摘要失败 {symbol}: {e}")
            return pd.DataFrame()

    def get_index_stock_cons(self, symbol: str = "000300") -> pd.DataFrame:
        """获取指数成份股"""
        try:
            import akshare as ak

            return ak.index_stock_cons(symbol=symbol)
        except Exception as e:
            logger.error(f"获取指数成份股失败 {symbol}: {e}")
            return pd.DataFrame()

    def get_stock_board_industry_name_em(self) -> pd.DataFrame:
        """获取行业板块名称"""
        try:
            import akshare as ak

            return ak.stock_board_industry_name_em()
        except Exception as e:
            logger.error(f"获取行业板块失败: {e}")
            return pd.DataFrame()

    def get_stock_board_concept_name_em(self) -> pd.DataFrame:
        """获取概念板块名称"""
        try:
            import akshare as ak

            return ak.stock_board_concept_name_em()
        except Exception as e:
            logger.error(f"获取概念板块失败: {e}")
            return pd.DataFrame()

    def get_stock_zh_a_hist_min_em(
        self,
        symbol: str,
        period: str = "1",
        start_date: str = "",
        end_date: str = "",
        adjust: str = "",
    ) -> pd.DataFrame:
        """获取A股分钟级行情"""
        try:
            import akshare as ak

            return ak.stock_zh_a_hist_min_em(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        except Exception as e:
            logger.error(f"获取分钟行情失败 {symbol}: {e}")
            return pd.DataFrame()
