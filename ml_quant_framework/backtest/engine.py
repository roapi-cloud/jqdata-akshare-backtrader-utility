"""回测引擎模块。

整合绩效分析、分层回测和可视化，提供一键式回测流程。
"""

import pandas as pd
import numpy as np
from datetime import date
from typing import Dict, List, Optional
from ml_quant_framework.core.config import BacktestConfig
from .performance import PerformanceAnalyzer
from .attribution import StratifiedBacktester
from .visualizer import BacktestVisualizer


class BacktestEngine:
    """回测引擎。

    整合绩效分析、分层回测和可视化功能，
    支持从组合历史数据计算策略收益并生成完整回测报告。
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        """初始化回测引擎。

        Args:
            config: 回测配置对象，默认使用 BacktestConfig 默认值。
        """
        self.config = config or BacktestConfig()
        self.results: Dict = {}

    def run(
        self,
        portfolio_history: Dict[date, Dict],
        prices_data: pd.DataFrame,
        benchmark_returns: Optional[pd.Series] = None,
    ) -> Dict:
        """执行回测。

        Args:
            portfolio_history: 组合历史，格式为
                {date: {"stocks": [...], "weights": {...}}}。
            prices_data: 价格数据 DataFrame，列为股票代码，index 为日期。
            benchmark_returns: 基准收益序列（可选）。

        Returns:
            回测结果字典，包含策略收益、基准收益和绩效报告。
        """
        # 计算策略收益
        strategy_returns = self._calculate_strategy_returns(
            portfolio_history, prices_data
        )

        # 绩效分析
        report = PerformanceAnalyzer.full_report(
            strategy_returns,
            benchmark=benchmark_returns,
            periods_per_year=12,
        )

        self.results = {
            "strategy_returns": strategy_returns,
            "benchmark_returns": benchmark_returns,
            "report": report,
        }

        return self.results

    def _calculate_strategy_returns(
        self,
        portfolio_history: Dict[date, Dict],
        prices_data: pd.DataFrame,
    ) -> pd.Series:
        """计算策略月度收益。

        根据组合权重和价格数据，计算每个调仓期的策略收益。

        Args:
            portfolio_history: 组合历史字典。
            prices_data: 价格数据 DataFrame。

        Returns:
            策略月度收益序列。
        """
        returns = {}
        sorted_dates = sorted(portfolio_history.keys())

        for i, current_date in enumerate(sorted_dates[:-1]):
            portfolio = portfolio_history[current_date]
            weights = portfolio.get("weights", {})
            if not weights:
                continue

            next_date = sorted_dates[i + 1]

            # 计算该组合从当前日期到下一个日期的收益
            port_ret = 0.0
            for stock, weight in weights.items():
                if stock in prices_data.columns:
                    try:
                        price_current = prices_data.loc[current_date, stock]
                        price_next = prices_data.loc[next_date, stock]
                        if price_current > 0:
                            stock_ret = (price_next - price_current) / price_current
                            port_ret += weight * stock_ret
                    except (KeyError, TypeError):
                        continue

            returns[next_date] = port_ret

        return pd.Series(returns)

    def run_stratified(
        self,
        df: pd.DataFrame,
        n_groups: int = 5,
        score_col: str = "predict",
        return_col: str = "return",
    ) -> Dict:
        """执行分层回测。

        Args:
            df: 包含预测分数和实际收益的 DataFrame。
            n_groups: 分组数。
            score_col: 预测分数列名。
            return_col: 实际收益列名。

        Returns:
            分层回测结果字典。
        """
        result = StratifiedBacktester.run_full_stratified(
            df, n_groups, score_col, return_col
        )
        self.results["stratified"] = result
        return result

    def get_report(self) -> Dict:
        """获取回测报告。

        Returns:
            绩效报告字典。
        """
        return self.results.get("report", {})

    def print_report(self):
        """打印回测报告到控制台。"""
        report = self.get_report()
        print("=" * 50)
        print("回 测 绩 效 报 告")
        print("=" * 50)
        for metric, value in report.items():
            if isinstance(value, float):
                print(f"{metric}: {value:.4f}")
            else:
                print(f"{metric}: {value}")
        print("=" * 50)

    def save_plots(
        self,
        output_dir: str = "output/backtest",
        group_stats: Optional[pd.DataFrame] = None,
        feature_importance: Optional[pd.Series] = None,
    ):
        """保存所有回测图表。

        Args:
            output_dir: 输出目录。
            group_stats: 分层收益统计 DataFrame（可选）。
            feature_importance: 特征重要性序列（可选）。
        """
        strategy_returns = self.results.get("strategy_returns")
        benchmark_returns = self.results.get("benchmark_returns")

        if strategy_returns is None:
            raise ValueError("请先执行 run() 方法生成回测结果")

        BacktestVisualizer.save_all_plots(
            returns=strategy_returns,
            benchmark=benchmark_returns,
            group_stats=group_stats,
            feature_importance=feature_importance,
            output_dir=output_dir,
        )
