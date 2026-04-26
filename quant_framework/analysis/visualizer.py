"""Visualization utilities for strategy performance analysis."""

from __future__ import annotations

from typing import Optional

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec

# ------------------------------------------------------------------
# Chinese font configuration
# ------------------------------------------------------------------


def _setup_chinese_font() -> None:
    """Configure matplotlib to use a Chinese-capable font."""
    candidates = [
        "SimHei",
        "Microsoft YaHei",
        "PingFang SC",
        "WenQuanYi Micro Hei",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
    ]
    for font in candidates:
        if font in matplotlib.font_manager.get_font_names():
            plt.rcParams["font.sans-serif"] = [font, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            return
    # Fallback: warn and use default
    plt.rcParams["axes.unicode_minus"] = False


_setup_chinese_font()

# ------------------------------------------------------------------
# Colour palette
# ------------------------------------------------------------------

_COLORS = {
    "primary": "#2196F3",
    "secondary": "#FF9800",
    "red": "#E53935",
    "green": "#43A047",
    "gray": "#9E9E9E",
    "light_gray": "#E0E0E0",
    "bg": "#FAFAFA",
}


class Visualizer:
    """Publication-quality charting utilities for backtest analysis."""

    def __init__(self, dpi: int = 150, style: str = "default") -> None:
        """Initialise visualizer.

        Args:
            dpi: Resolution for saved figures.
            style: Matplotlib style name.
        """
        self.dpi = dpi
        self.style = style

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_series(values, label: str = "value") -> pd.Series:
        """Convert various inputs to a datetime-indexed Series."""
        if isinstance(values, pd.Series):
            s = values.copy()
        elif isinstance(values, pd.DataFrame):
            s = values.iloc[:, 0].copy()
        elif isinstance(values, (list, tuple, np.ndarray)):
            s = pd.Series(values, name=label)
        else:
            s = pd.Series(values, name=label)

        if not isinstance(s.index, pd.DatetimeIndex):
            try:
                s.index = pd.to_datetime(s.index)
            except (ValueError, TypeError):
                s.index = pd.RangeIndex(len(s))
        s.sort_index(inplace=True)
        return s

    def _save_or_show(self, fig: plt.Figure, save_path: Optional[str] = None) -> None:
        """Save figure or display interactively."""
        if save_path:
            fig.savefig(save_path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        else:
            plt.show()
        plt.close(fig)

    # ------------------------------------------------------------------
    # Chart methods
    # ------------------------------------------------------------------

    def plot_equity_curve(
        self,
        strategy_values,
        benchmark_values=None,
        title: str = "Equity Curve",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot strategy and optional benchmark equity curves.

        Args:
            strategy_values: Series / DataFrame / array of strategy portfolio values.
            benchmark_values: Optional benchmark values.
            title: Chart title.
            save_path: If provided, save figure to this path.

        Returns:
            The matplotlib Figure object.
        """
        strat = self._to_series(strategy_values, "Strategy")
        strat = strat / strat.iloc[0]  # Normalise to 1

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(
            strat.index,
            strat.values,
            color=_COLORS["primary"],
            linewidth=1.5,
            label="Strategy",
        )

        if benchmark_values is not None:
            bench = self._to_series(benchmark_values, "Benchmark")
            bench = bench / bench.iloc[0]
            ax.plot(
                bench.index,
                bench.values,
                color=_COLORS["secondary"],
                linewidth=1.2,
                label="Benchmark",
                linestyle="--",
            )

        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_ylabel("Normalised Value", fontsize=12)
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()

        self._save_or_show(fig, save_path)
        return fig

    def plot_drawdown(
        self,
        drawdown_series,
        title: str = "Drawdown",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot drawdown over time (filled area below zero).

        Args:
            drawdown_series: Series of drawdown values (negative or zero).
            title: Chart title.
            save_path: Optional output path.

        Returns:
            The matplotlib Figure object.
        """
        dd = self._to_series(drawdown_series, "Drawdown")

        fig, ax = plt.subplots(figsize=(12, 4))
        ax.fill_between(dd.index, dd.values, 0, color=_COLORS["red"], alpha=0.4)
        ax.plot(dd.index, dd.values, color=_COLORS["red"], linewidth=0.8)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_ylabel("Drawdown", fontsize=12)
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()

        self._save_or_show(fig, save_path)
        return fig

    def plot_monthly_returns(
        self,
        monthly_returns: pd.DataFrame,
        title: str = "Monthly Return Heatmap",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot a heatmap of monthly returns.

        Args:
            monthly_returns: DataFrame with columns ``year``, ``month``, ``return``.
            title: Chart title.
            save_path: Optional output path.

        Returns:
            The matplotlib Figure object.
        """
        if monthly_returns.empty:
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.text(
                0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes
            )
            ax.axis("off")
            self._save_or_show(fig, save_path)
            return fig

        pivot = monthly_returns.pivot(index="year", columns="month", values="return")
        pivot = pivot.reindex(columns=range(1, 13))

        fig, ax = plt.subplots(figsize=(12, max(4, len(pivot) * 0.5)))
        im = ax.imshow(
            pivot.values,
            cmap="RdYlGn",
            aspect="auto",
            vmin=-0.15,
            vmax=0.15,
        )

        ax.set_xticks(range(12))
        ax.set_xticklabels([f"{m}月" for m in range(1, 13)])
        ax.set_yticks(range(len(pivot)))
        ax.set_yticklabels(pivot.index)

        # Annotate cells
        for i in range(len(pivot)):
            for j in range(12):
                val = pivot.values[i, j]
                if np.isnan(val):
                    continue
                color = "white" if abs(val) > 0.08 else "black"
                ax.text(
                    j,
                    i,
                    f"{val:.1%}",
                    ha="center",
                    va="center",
                    fontsize=9,
                    color=color,
                )

        ax.set_title(title, fontsize=14, fontweight="bold")
        fig.colorbar(im, ax=ax, label="Return")
        plt.tight_layout()

        self._save_or_show(fig, save_path)
        return fig

    def plot_trade_distribution(
        self,
        trade_returns,
        title: str = "Trade Return Distribution",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot histogram / KDE of individual trade returns.

        Args:
            trade_returns: Array-like of trade PnL or percentage returns.
            title: Chart title.
            save_path: Optional output path.

        Returns:
            The matplotlib Figure object.
        """
        data = np.asarray(trade_returns, dtype=float)
        if len(data) == 0:
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.text(
                0.5, 0.5, "No trades", ha="center", va="center", transform=ax.transAxes
            )
            ax.axis("off")
            self._save_or_show(fig, save_path)
            return fig

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(
            data,
            bins=min(50, max(10, len(data) // 3)),
            color=_COLORS["primary"],
            alpha=0.7,
            edgecolor="white",
            density=True,
        )

        # KDE overlay
        try:
            from scipy import stats

            kde = stats.gaussian_kde(data)
            xs = np.linspace(data.min(), data.max(), 200)
            ax.plot(xs, kde(xs), color=_COLORS["red"], linewidth=2, label="KDE")
            ax.legend()
        except ImportError:
            pass

        ax.axvline(0, color="black", linestyle="--", linewidth=1)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel("Trade Return", fontsize=12)
        ax.set_ylabel("Density", fontsize=12)
        ax.grid(True, alpha=0.3)

        self._save_or_show(fig, save_path)
        return fig

    def plot_position_history(
        self,
        positions: pd.DataFrame,
        title: str = "Position History",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """Plot the number of open positions over time.

        Args:
            positions: DataFrame with at least ``date`` and ``quantity`` (or
                       ``num_positions``) columns.
            title: Chart title.
            save_path: Optional output path.

        Returns:
            The matplotlib Figure object.
        """
        if positions.empty:
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.text(
                0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes
            )
            ax.axis("off")
            self._save_or_show(fig, save_path)
            return fig

        df = positions.copy()
        if "date" in df.columns:
            df = df.set_index("date")
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        if "num_positions" in df.columns:
            series = df["num_positions"]
        elif "quantity" in df.columns:
            series = df.groupby(df.index)["quantity"].sum()
        else:
            series = pd.Series(0, index=df.index)

        fig, ax = plt.subplots(figsize=(12, 4))
        ax.fill_between(
            series.index, series.values, 0, color=_COLORS["primary"], alpha=0.3
        )
        ax.plot(series.index, series.values, color=_COLORS["primary"], linewidth=1.2)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_ylabel("Number of Positions", fontsize=12)
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()

        self._save_or_show(fig, save_path)
        return fig
