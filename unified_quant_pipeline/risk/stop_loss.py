"""止损机制"""

import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class StopLossManager:
    """止损管理器

    支持多种止损方式：
    - 固定比例止损
    - 追踪止损（从最高点回撤）
    - 时间止损（持有超过N天无条件卖出）
    """

    def __init__(
        self,
        stop_loss_pct: float = 0.08,
        trailing_stop_pct: float = 0.10,
        max_hold_days: int = 60,
    ):
        """初始化止损管理器

        Args:
            stop_loss_pct: 固定止损比例
            trailing_stop_pct: 追踪止损回撤比例
            max_hold_days: 最大持有天数
        """
        self.stop_loss_pct = stop_loss_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.max_hold_days = max_hold_days
        self._entry_prices: Dict[str, float] = {}
        self._high_prices: Dict[str, float] = {}
        self._entry_dates: Dict[str, str] = {}

    def record_entry(self, code: str, price: float, date: str) -> None:
        """记录买入

        Args:
            code: 股票代码
            price: 买入价格
            date: 买入日期
        """
        self._entry_prices[code] = price
        self._high_prices[code] = price
        self._entry_dates[code] = date

    def update_high(self, code: str, price: float) -> None:
        """更新最高价

        Args:
            code: 股票代码
            price: 当前价格
        """
        if code in self._high_prices:
            self._high_prices[code] = max(self._high_prices[code], price)

    def check_stop(
        self, code: str, current_price: float, current_date: str
    ) -> Optional[str]:
        """检查是否触发止损

        Args:
            code: 股票代码
            current_price: 当前价格
            current_date: 当前日期

        Returns:
            Optional[str]: 止损原因，None表示不触发
        """
        if code not in self._entry_prices:
            return None

        entry_price = self._entry_prices[code]

        # 固定止损
        if current_price < entry_price * (1 - self.stop_loss_pct):
            return "stop_loss"

        # 追踪止损
        if code in self._high_prices:
            high = self._high_prices[code]
            if current_price < high * (1 - self.trailing_stop_pct):
                return "trailing_stop"

        # 时间止损
        if code in self._entry_dates:
            entry = datetime.strptime(self._entry_dates[code], "%Y-%m-%d")
            current = datetime.strptime(current_date, "%Y-%m-%d")
            if (current - entry).days > self.max_hold_days:
                return "time_stop"

        return None

    def clear(self, code: str) -> None:
        """清除记录（卖出后）

        Args:
            code: 股票代码
        """
        self._entry_prices.pop(code, None)
        self._high_prices.pop(code, None)
        self._entry_dates.pop(code, None)
