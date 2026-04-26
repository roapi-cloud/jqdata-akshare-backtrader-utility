"""绩效分析 - 深度分析回测结果"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from .metrics import calculate_max_drawdown

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """绩效分析器"""

    @staticmethod
    def analyze_drawdown(nav: pd.Series) -> Dict:
        """分析回撤特征

        Args:
            nav: 净值序列

        Returns:
            Dict: 回撤分析结果
        """
        rolling_max = nav.cummax()
        drawdown = (nav - rolling_max) / rolling_max

        max_dd = drawdown.min()
        max_dd_end = drawdown.idxmin()
        max_dd_start = nav[:max_dd_end].idxmax()
        max_dd_duration = (max_dd_end - max_dd_start).days

        avg_dd = drawdown[drawdown < 0].mean()

        dd_periods = (drawdown < 0).astype(int).diff()
        n_dd = (dd_periods == 1).sum()

        return {
            "max_drawdown": max_dd,
            "max_dd_start": str(max_dd_start),
            "max_dd_end": str(max_dd_end),
            "max_dd_duration_days": max_dd_duration,
            "avg_drawdown": avg_dd,
            "n_drawdowns": n_dd,
        }

    @staticmethod
    def analyze_monthly_returns(nav: pd.Series) -> pd.DataFrame:
        """分析月度收益

        Args:
            nav: 净值序列

        Returns:
            pd.DataFrame: 月度收益数据
        """
        returns = nav.pct_change()
        monthly = returns.resample("M").apply(lambda x: (1 + x).prod() - 1)

        monthly_df = pd.DataFrame(
            {
                "year": monthly.index.year,
                "month": monthly.index.month,
                "return": monthly.values,
            }
        )

        return monthly_df

    @staticmethod
    def analyze_rolling_metrics(nav: pd.Series, window: int = 252) -> pd.DataFrame:
        """计算滚动指标

        Args:
            nav: 净值序列
            window: 滚动窗口大小

        Returns:
            pd.DataFrame: 滚动指标数据
        """
        returns = nav.pct_change()

        rolling_return = returns.rolling(window).sum()
        rolling_vol = returns.rolling(window).std() * np.sqrt(252)
        rolling_sharpe = rolling_return / rolling_vol

        return pd.DataFrame(
            {
                "rolling_return": rolling_return,
                "rolling_volatility": rolling_vol,
                "rolling_sharpe": rolling_sharpe,
            }
        )

    @staticmethod
    def generate_summary(backtest_result: Dict) -> str:
        """生成回测摘要文本

        Args:
            backtest_result: 回测结果字典

        Returns:
            str: 回测摘要文本
        """
        metrics = backtest_result["metrics"]

        summary = f"""
回测结果摘要
=============
总收益率:     {metrics.get("total_return", 0) * 100:.2f}%
年化收益:     {metrics.get("annual_return", 0) * 100:.2f}%
最大回撤:     {metrics.get("max_drawdown", 0) * 100:.2f}%
夏普比率:     {metrics.get("sharpe", 0):.2f}
索提诺比率:   {metrics.get("sortino", 0):.2f}
卡尔马比率:   {metrics.get("calmar", 0):.2f}
胜率:         {metrics.get("win_rate", 0) * 100:.2f}%
盈亏比:       {metrics.get("profit_loss_ratio", 0):.2f}
波动率:       {metrics.get("volatility", 0) * 100:.2f}%
回测天数:     {metrics.get("n_days", 0)}
"""
        if "excess_return" in metrics:
            summary += f"""
超额收益:     {metrics.get("excess_return", 0) * 100:.2f}%
信息比率:     {metrics.get("information_ratio", 0):.2f}
跟踪误差:     {metrics.get("tracking_error", 0) * 100:.2f}%
Beta:         {metrics.get("beta", 0):.2f}
Alpha:        {metrics.get("alpha", 0) * 100:.2f}%
"""
        return summary
