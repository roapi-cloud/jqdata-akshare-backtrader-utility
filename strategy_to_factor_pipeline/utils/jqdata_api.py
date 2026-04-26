"""
聚宽API封装
提供聚宽数据接口的统一访问
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger


class JQDataAPI:
    """聚宽数据API封装"""

    def __init__(self, username: str = "", password: str = ""):
        self.username = username
        self.password = password
        self.authenticated = False

    def authenticate(self) -> bool:
        """认证登录"""
        try:
            import jqdatasdk

            jqdatasdk.auth(self.username, self.password)
            self.authenticated = True
            logger.info("聚宽数据认证成功")
            return True
        except Exception as e:
            logger.error(f"聚宽认证失败: {e}")
            return False

    def get_price(
        self,
        security: str,
        start_date: str,
        end_date: str,
        frequency: str = "daily",
        fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """获取价格数据"""
        if not self.authenticated:
            logger.warning("未认证，请先调用authenticate()")
            return pd.DataFrame()

        try:
            import jqdatasdk

            return jqdatasdk.get_price(
                security,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                fields=fields,
            )
        except Exception as e:
            logger.error(f"获取价格数据失败: {e}")
            return pd.DataFrame()

    def get_all_securities(self, date: Optional[str] = None) -> pd.DataFrame:
        """获取所有股票列表"""
        if not self.authenticated:
            return pd.DataFrame()

        try:
            import jqdatasdk

            return jqdatasdk.get_all_securities(["stock"], date=date)
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return pd.DataFrame()

    def get_index_stocks(
        self, index_code: str, date: Optional[str] = None
    ) -> List[str]:
        """获取指数成份股"""
        if not self.authenticated:
            return []

        try:
            import jqdatasdk

            return jqdatasdk.get_index_stocks(index_code, date=date)
        except Exception as e:
            logger.error(f"获取指数成份股失败: {e}")
            return []

    def get_fundamentals(
        self,
        query_obj,
        date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """获取基本面数据"""
        if not self.authenticated:
            return pd.DataFrame()

        try:
            import jqdatasdk

            return jqdatasdk.get_fundamentals(
                query_obj,
                date=date,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"获取基本面数据失败: {e}")
            return pd.DataFrame()

    def get_factor_values(
        self,
        securities: List[str],
        factors: List[str],
        start_date: str,
        end_date: str,
    ) -> Dict:
        """获取因子值"""
        if not self.authenticated:
            return {}

        try:
            import jqdatasdk

            return jqdatasdk.get_factor_values(
                securities,
                factors,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"获取因子值失败: {e}")
            return {}

    def get_current_data(self) -> Dict:
        """获取当前行情数据"""
        if not self.authenticated:
            return {}

        try:
            import jqdatasdk

            return jqdatasdk.get_current_data()
        except Exception as e:
            logger.error(f"获取当前数据失败: {e}")
            return {}

    def logout(self):
        """登出"""
        try:
            import jqdatasdk

            jqdatasdk.logout()
            self.authenticated = False
        except Exception:
            pass
