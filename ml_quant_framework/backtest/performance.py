"""绩效分析模块。

提供年化收益、最大回撤、夏普比率、Alpha、Beta、信息比率等
常见量化绩效指标的计算。
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional


class PerformanceAnalyzer:
    """绩效分析器。

    提供静态方法计算各类绩效指标，输入为月度收益序列。
    """

    @staticmethod
    def cumulative_returns(returns: pd.Series) -> pd.Series:
        """计算累计收益曲线。

        Args:
            returns: 月度收益序列。

        Returns:
            累计收益序列。
        """
        return (1 + returns).cumprod()

    @staticmethod
    def annualized_return(returns: pd.Series, periods_per_year: int = 12) -> float:
        """计算年化收益率。

        Args:
            returns: 月度收益序列。
            periods_per_year: 每年期数，月度数据为 12。

        Returns:
            年化收益率。
        """
        n = len(returns)
        if n == 0:
            return 0.0
        cum_ret = (1 + returns).prod()
        return cum_ret ** (periods_per_year / n) - 1

    @staticmethod
    def max_drawdown(returns: pd.Series) -> float:
        """计算最大回撤。

        Args:
            returns: 月度收益序列。

        Returns:
            最大回撤值。
        """
        cum_ret = (1 + returns).cumprod()
        cummax = cum_ret.cummax()
        drawdown = (cummax - cum_ret) / cummax
        return drawdown.max()

    @staticmethod
    def sharpe_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.04,
        periods_per_year: int = 12,
    ) -> float:
        """计算夏普比率。

        Args:
            returns: 月度收益序列。
            risk_free_rate: 无风险利率（年化）。
            periods_per_year: 每年期数。

        Returns:
            夏普比率。
        """
        ann_ret = PerformanceAnalyzer.annualized_return(returns, periods_per_year)
        vol = returns.std() * np.sqrt(periods_per_year)
        if vol == 0:
            return 0.0
        return (ann_ret - risk_free_rate) / vol

    @staticmethod
    def alpha(
        returns: pd.Series,
        benchmark: pd.Series,
        risk_free_rate: float = 0.04,
        periods_per_year: int = 12,
    ) -> float:
        """计算 Alpha（年化超额收益）。

        Args:
            returns: 策略月度收益序列。
            benchmark: 基准月度收益序列。
            risk_free_rate: 无风险利率（年化）。
            periods_per_year: 每年期数。

        Returns:
            Alpha 值。
        """
        excess = returns - benchmark
        ann_excess = (1 + excess).prod() ** (periods_per_year / len(returns)) - 1
        return ann_excess

    @staticmethod
    def beta(returns: pd.Series, benchmark: pd.Series) -> float:
        """计算 Beta。

        Args:
            returns: 策略月度收益序列。
            benchmark: 基准月度收益序列。

        Returns:
            Beta 值。
        """
        cov = returns.cov(benchmark)
        var = benchmark.var()
        if var == 0:
            return 1.0
        return cov / var

    @staticmethod
    def information_ratio(
        returns: pd.Series,
        benchmark: pd.Series,
        periods_per_year: int = 12,
    ) -> float:
        """计算信息比率。

        Args:
            returns: 策略月度收益序列。
            benchmark: 基准月度收益序列。
            periods_per_year: 每年期数。

        Returns:
            信息比率。
        """
        excess = returns - benchmark
        ann_excess = PerformanceAnalyzer.alpha(
            returns, benchmark, periods_per_year=periods_per_year
        )
        tracking_error = excess.std() * np.sqrt(periods_per_year)
        if tracking_error == 0:
            return 0.0
        return ann_excess / tracking_error

    @staticmethod
    def win_rate(returns: pd.Series) -> float:
        """计算胜率（正收益月份占比）。

        Args:
            returns: 月度收益序列。

        Returns:
            胜率。
        """
        return (returns > 0).sum() / len(returns)

    @staticmethod
    def beat_rate(returns: pd.Series, benchmark: pd.Series) -> float:
        """计算跑赢基准月份占比。

        Args:
            returns: 策略月度收益序列。
            benchmark: 基准月度收益序列。

        Returns:
            跑赢基准占比。
        """
        return (returns > benchmark).sum() / len(returns)

    @staticmethod
    def calmar_ratio(returns: pd.Series, periods_per_year: int = 12) -> float:
        """计算 Calmar 比率（年化收益 / 最大回撤）。

        Args:
            returns: 月度收益序列。
            periods_per_year: 每年期数。

        Returns:
            Calmar 比率。
        """
        ann_ret = PerformanceAnalyzer.annualized_return(returns, periods_per_year)
        mdd = PerformanceAnalyzer.max_drawdown(returns)
        if mdd == 0:
            return 0.0
        return ann_ret / mdd

    @staticmethod
    def full_report(
        returns: pd.Series,
        benchmark: pd.Series = None,
        risk_free_rate: float = 0.04,
        periods_per_year: int = 12,
    ) -> Dict:
        """生成完整绩效报告。

        Args:
            returns: 策略月度收益序列。
            benchmark: 基准月度收益序列（可选）。
            risk_free_rate: 无风险利率（年化）。
            periods_per_year: 每年期数。

        Returns:
            包含各项绩效指标的字典。
        """
        report = {
            "累计收益率": (1 + returns).prod() - 1,
            "年化收益率": PerformanceAnalyzer.annualized_return(
                returns, periods_per_year
            ),
            "最大回撤": PerformanceAnalyzer.max_drawdown(returns),
            "夏普比率": PerformanceAnalyzer.sharpe_ratio(
                returns, risk_free_rate, periods_per_year
            ),
            "Calmar比率": PerformanceAnalyzer.calmar_ratio(returns, periods_per_year),
            "胜率": PerformanceAnalyzer.win_rate(returns),
            "月数": len(returns),
        }

        if benchmark is not None:
            report["Alpha"] = PerformanceAnalyzer.alpha(
                returns, benchmark, risk_free_rate, periods_per_year
            )
            report["Beta"] = PerformanceAnalyzer.beta(returns, benchmark)
            report["信息比率"] = PerformanceAnalyzer.information_ratio(
                returns, benchmark, periods_per_year
            )
            report["跑赢基准占比"] = PerformanceAnalyzer.beat_rate(returns, benchmark)

        return report
