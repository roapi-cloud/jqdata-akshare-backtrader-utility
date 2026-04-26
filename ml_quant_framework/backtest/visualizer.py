"""回测可视化模块。

提供累计收益曲线、分层收益柱状图、回撤曲线、
特征重要性、月度收益热力图等可视化功能。
"""

import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
import pandas as pd
from typing import Dict, List, Optional

# 设置中文字体
mpl.rcParams["font.family"] = "SimHei"
mpl.rcParams["axes.unicode_minus"] = False


class BacktestVisualizer:
    """回测可视化器。

    提供多种静态方法绘制回测相关图表。
    """

    @staticmethod
    def plot_cumulative_returns(
        returns_dict: Dict[str, pd.Series],
        title: str = "累计收益曲线",
        figsize: tuple = (12, 6),
    ):
        """绘制累计收益曲线。

        Args:
            returns_dict: {名称: 收益序列} 字典。
            title: 图表标题。
            figsize: 图表尺寸。

        Returns:
            matplotlib Figure 对象。
        """
        plt.figure(figsize=figsize)
        for name, returns in returns_dict.items():
            cum_ret = (1 + returns).cumprod()
            plt.plot(cum_ret.index, cum_ret.values, label=name, linewidth=2)
        plt.title(title, fontsize=14)
        plt.xlabel("日期", fontsize=12)
        plt.ylabel("累计收益", fontsize=12)
        plt.legend(fontsize=10)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        return plt.gcf()

    @staticmethod
    def plot_group_returns(
        group_stats: pd.DataFrame,
        title: str = "分层回测收益",
        figsize: tuple = (10, 6),
    ):
        """绘制分层收益柱状图。

        Args:
            group_stats: 分层收益统计 DataFrame。
            title: 图表标题。
            figsize: 图表尺寸。

        Returns:
            matplotlib Figure 对象。
        """
        plt.figure(figsize=figsize)
        groups = group_stats.index
        returns = group_stats["mean_return"].values

        colors = ["red" if r > 0 else "green" for r in returns]
        plt.bar(groups, returns, color=colors, alpha=0.7, edgecolor="black")
        plt.axhline(y=0, color="black", linewidth=1)
        plt.title(title, fontsize=14)
        plt.xlabel("分组", fontsize=12)
        plt.ylabel("平均收益", fontsize=12)
        plt.xticks(groups, [f"G{i + 1}" for i in groups])
        plt.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        return plt.gcf()

    @staticmethod
    def plot_drawdown(
        returns: pd.Series,
        title: str = "回撤曲线",
        figsize: tuple = (12, 6),
    ):
        """绘制回撤曲线。

        Args:
            returns: 月度收益序列。
            title: 图表标题。
            figsize: 图表尺寸。

        Returns:
            matplotlib Figure 对象。
        """
        plt.figure(figsize=figsize)
        cum_ret = (1 + returns).cumprod()
        cummax = cum_ret.cummax()
        drawdown = (cummax - cum_ret) / cummax

        plt.fill_between(drawdown.index, -drawdown.values, 0, alpha=0.3, color="red")
        plt.plot(drawdown.index, -drawdown.values, color="red", linewidth=1)
        plt.title(title, fontsize=14)
        plt.xlabel("日期", fontsize=12)
        plt.ylabel("回撤", fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        return plt.gcf()

    @staticmethod
    def plot_feature_importance(
        importance: pd.Series,
        top_n: int = 20,
        title: str = "特征重要性",
        figsize: tuple = (10, 8),
    ):
        """绘制特征重要性条形图。

        Args:
            importance: 特征重要性序列。
            top_n: 显示前 N 个特征。
            title: 图表标题。
            figsize: 图表尺寸。

        Returns:
            matplotlib Figure 对象。
        """
        importance = importance.abs().sort_values(ascending=False).head(top_n)

        plt.figure(figsize=figsize)
        plt.barh(range(len(importance)), importance.values, color="steelblue")
        plt.yticks(range(len(importance)), importance.index)
        plt.xlabel("重要性", fontsize=12)
        plt.title(title, fontsize=14)
        plt.gca().invert_yaxis()
        plt.grid(True, alpha=0.3, axis="x")
        plt.tight_layout()
        return plt.gcf()

    @staticmethod
    def plot_monthly_returns(
        returns: pd.Series,
        figsize: tuple = (12, 8),
    ):
        """绘制月度收益热力图。

        Args:
            returns: 月度收益序列（index 需为 datetime）。
            figsize: 图表尺寸。

        Returns:
            matplotlib Figure 对象。
        """
        df = returns.to_frame("return")
        df["year"] = df.index.year
        df["month"] = df.index.month

        pivot = df.pivot(index="year", columns="month", values="return")

        plt.figure(figsize=figsize)
        plt.imshow(pivot.values, cmap="RdYlGn", aspect="auto")
        plt.colorbar(label="月度收益")
        plt.xticks(
            range(12),
            [
                "1月",
                "2月",
                "3月",
                "4月",
                "5月",
                "6月",
                "7月",
                "8月",
                "9月",
                "10月",
                "11月",
                "12月",
            ],
        )
        plt.yticks(range(len(pivot.index)), pivot.index)
        plt.title("月度收益热力图", fontsize=14)
        plt.tight_layout()
        return plt.gcf()

    @staticmethod
    def save_all_plots(
        returns: pd.Series,
        benchmark: pd.Series,
        group_stats: pd.DataFrame = None,
        feature_importance: pd.Series = None,
        output_dir: str = "output/backtest",
    ):
        """保存所有图表到指定目录。

        Args:
            returns: 策略月度收益序列。
            benchmark: 基准月度收益序列。
            group_stats: 分层收益统计 DataFrame（可选）。
            feature_importance: 特征重要性序列（可选）。
            output_dir: 输出目录。
        """
        from pathlib import Path

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 累计收益
        fig = BacktestVisualizer.plot_cumulative_returns(
            {"策略": returns, "基准": benchmark}
        )
        fig.savefig(f"{output_dir}/cumulative_returns.png", dpi=150)
        plt.close()

        # 分层收益
        if group_stats is not None:
            fig = BacktestVisualizer.plot_group_returns(group_stats)
            fig.savefig(f"{output_dir}/group_returns.png", dpi=150)
            plt.close()

        # 回撤
        fig = BacktestVisualizer.plot_drawdown(returns)
        fig.savefig(f"{output_dir}/drawdown.png", dpi=150)
        plt.close()

        # 特征重要性
        if feature_importance is not None:
            fig = BacktestVisualizer.plot_feature_importance(feature_importance)
            fig.savefig(f"{output_dir}/feature_importance.png", dpi=150)
            plt.close()
