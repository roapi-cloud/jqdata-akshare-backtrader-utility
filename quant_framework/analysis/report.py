"""Report generation for backtest results."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from .metrics import PerformanceMetrics
from .visualizer import Visualizer


class ReportGenerator:
    """Generate text and HTML reports from backtest results.

    Args:
        metrics: A configured ``PerformanceMetrics`` instance.
        trades: Optional list of trade dicts for detailed trade analysis.
        visualizer: Optional ``Visualizer`` instance (created automatically if None).
    """

    def __init__(
        self,
        metrics: PerformanceMetrics,
        trades: Optional[List[Dict[str, Any]]] = None,
        visualizer: Optional[Visualizer] = None,
    ) -> None:
        self.metrics = metrics
        self.trades = trades or []
        self.visualizer = visualizer or Visualizer()

    # ------------------------------------------------------------------
    # Text report
    # ------------------------------------------------------------------

    def generate_text_report(self) -> str:
        """Generate a plain-text summary report.

        Returns:
            Formatted multi-line string.
        """
        m = self.metrics.all_metrics()
        lines = [
            "=" * 60,
            "  PERFORMANCE REPORT",
            f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "",
            "--- Return Metrics ---",
            f"  Total Return:          {m['total_return']:>10.2%}",
            f"  Annualized Return:     {m['annualized_return']:>10.2%}",
            "",
            "--- Risk Metrics ---",
            f"  Volatility:            {m['volatility']:>10.2%}",
            f"  Downside Deviation:    {m['downside_deviation']:>10.2%}",
            f"  Max Drawdown:          {m['max_drawdown']:>10.2%}",
            f"  Max DD Duration:       {m['max_drawdown_duration']:>10.0f} days",
            f"  Avg DD Duration:       {m['avg_drawdown_duration']:>10.1f} days",
            "",
            "--- Risk-Adjusted Ratios ---",
            f"  Sharpe Ratio:          {m['sharpe_ratio']:>10.4f}",
            f"  Sortino Ratio:         {m['sortino_ratio']:>10.4f}",
            f"  Calmar Ratio:          {m['calmar_ratio']:>10.4f}",
            f"  Omega Ratio:           {m['omega_ratio']:>10.4f}",
            f"  Treynor Ratio:         {m['treynor_ratio']:>10.4f}",
            "",
            "--- Trade Statistics ---",
            f"  Win Rate:              {m['win_rate']:>10.2%}",
            f"  Loss Rate:             {m['loss_rate']:>10.2%}",
            f"  Profit/Loss Ratio:     {m['profit_loss_ratio']:>10.4f}",
            f"  Profit Factor:         {m['profit_factor']:>10.4f}",
            f"  Avg Trade PnL:         {m['avg_trade_pnl']:>10.2f}",
            f"  Expectancy:            {m['expectancy']:>10.2f}",
            "",
            "--- Holding & Turnover ---",
            f"  Avg Holding Period:    {m['average_holding_period']:>10.1f} days",
            f"  Turnover Rate:         {m['turnover_rate']:>10.2%}",
            "",
            "--- Benchmark-Relative ---",
            f"  Information Ratio:     {m['information_ratio']:>10.4f}",
            f"  Tracking Error:        {m['tracking_error']:>10.2%}",
            f"  Alpha:                 {m['alpha']:>10.2%}",
            f"  Beta:                  {m['beta']:>10.4f}",
            "",
            "=" * 60,
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # HTML report
    # ------------------------------------------------------------------

    def generate_html_report(
        self,
        output_path: str = "report.html",
        strategy_name: str = "Strategy",
        benchmark_name: str = "Benchmark",
    ) -> str:
        """Generate a self-contained HTML report with embedded charts.

        Args:
            output_path: File path for the HTML output.
            strategy_name: Display name for the strategy.
            benchmark_name: Display name for the benchmark.

        Returns:
            The absolute path of the generated file.
        """
        output_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(output_dir, exist_ok=True)

        img_prefix = os.path.join(output_dir, "chart")
        os.makedirs(img_prefix, exist_ok=True)

        # Generate charts
        equity_path = os.path.join(img_prefix, "equity_curve.png")
        dd_path = os.path.join(img_prefix, "drawdown.png")
        monthly_path = os.path.join(img_prefix, "monthly_returns.png")
        trade_path = os.path.join(img_prefix, "trade_distribution.png")
        position_path = os.path.join(img_prefix, "position_history.png")

        self.visualizer.plot_equity_curve(
            self.metrics._values,
            self.metrics.benchmark,
            save_path=equity_path,
        )
        self.visualizer.plot_drawdown(
            self.metrics.drawdown_series(),
            save_path=dd_path,
        )

        monthly = self.metrics.monthly_returns()
        self.visualizer.plot_monthly_returns(monthly, save_path=monthly_path)

        trade_pnls = [
            t.get("pnl", 0) if isinstance(t, dict) else getattr(t, "pnl", 0)
            for t in self.trades
        ]
        self.visualizer.plot_trade_distribution(trade_pnls, save_path=trade_path)

        # Build position history DataFrame from equity curve if trades available
        position_df = pd.DataFrame()
        if self.trades:
            dates = sorted(
                set(
                    t.get("date", "") if isinstance(t, dict) else getattr(t, "date", "")
                    for t in self.trades
                )
            )
            position_df = pd.DataFrame({"date": dates})
        self.visualizer.plot_position_history(position_df, save_path=position_path)

        # Metrics table
        m = self.metrics.all_metrics()
        metric_rows = self._build_metric_rows(m)

        # Trade analysis table
        trade_rows = self._build_trade_rows()

        html = self._render_html(
            strategy_name=strategy_name,
            benchmark_name=benchmark_name,
            metric_rows=metric_rows,
            trade_rows=trade_rows,
            equity_img=os.path.relpath(equity_path, output_dir),
            dd_img=os.path.relpath(dd_path, output_dir),
            monthly_img=os.path.relpath(monthly_path, output_dir),
            trade_img=os.path.relpath(trade_path, output_dir),
            position_img=os.path.relpath(position_path, output_dir),
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        return os.path.abspath(output_path)

    # ------------------------------------------------------------------
    # HTML helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_metric_rows(m: Dict[str, Any]) -> List[Dict[str, str]]:
        """Format metrics into table rows."""
        fmt_pct = lambda v: (
            f"{v:.2%}" if isinstance(v, float) and abs(v) < 10 else f"{v:.4f}"
        )
        fmt_float = lambda v: f"{v:.4f}"
        fmt_int = lambda v: f"{v:.0f}"

        groups = [
            (
                "Return Metrics",
                [
                    ("Total Return", fmt_pct(m["total_return"])),
                    ("Annualized Return", fmt_pct(m["annualized_return"])),
                ],
            ),
            (
                "Risk Metrics",
                [
                    ("Volatility", fmt_pct(m["volatility"])),
                    ("Downside Deviation", fmt_pct(m["downside_deviation"])),
                    ("Max Drawdown", fmt_pct(m["max_drawdown"])),
                    ("Max DD Duration (days)", fmt_int(m["max_drawdown_duration"])),
                    ("Avg DD Duration (days)", f"{m['avg_drawdown_duration']:.1f}"),
                ],
            ),
            (
                "Risk-Adjusted Ratios",
                [
                    ("Sharpe Ratio", fmt_float(m["sharpe_ratio"])),
                    ("Sortino Ratio", fmt_float(m["sortino_ratio"])),
                    ("Calmar Ratio", fmt_float(m["calmar_ratio"])),
                    ("Omega Ratio", fmt_float(m["omega_ratio"])),
                    ("Treynor Ratio", fmt_float(m["treynor_ratio"])),
                ],
            ),
            (
                "Trade Statistics",
                [
                    ("Win Rate", fmt_pct(m["win_rate"])),
                    ("Loss Rate", fmt_pct(m["loss_rate"])),
                    ("Profit/Loss Ratio", fmt_float(m["profit_loss_ratio"])),
                    ("Profit Factor", fmt_float(m["profit_factor"])),
                    ("Avg Trade PnL", f"{m['avg_trade_pnl']:.2f}"),
                    ("Expectancy", f"{m['expectancy']:.2f}"),
                ],
            ),
            (
                "Holding & Turnover",
                [
                    ("Avg Holding Period (days)", f"{m['average_holding_period']:.1f}"),
                    ("Turnover Rate", fmt_pct(m["turnover_rate"])),
                ],
            ),
            (
                "Benchmark-Relative",
                [
                    ("Information Ratio", fmt_float(m["information_ratio"])),
                    ("Tracking Error", fmt_pct(m["tracking_error"])),
                    ("Alpha", fmt_pct(m["alpha"])),
                    ("Beta", fmt_float(m["beta"])),
                ],
            ),
        ]

        rows: List[Dict[str, str]] = []
        for group_name, items in groups:
            rows.append({"metric": f"<b>{group_name}</b>", "value": ""})
            for label, value in items:
                rows.append({"metric": label, "value": value})
        return rows

    def _build_trade_rows(self) -> List[Dict[str, str]]:
        """Build trade analysis rows."""
        if not self.trades:
            return [{"detail": "No trade data available"}]

        rows = []
        for i, t in enumerate(self.trades[:100]):  # Cap at 100 trades for readability
            if isinstance(t, dict):
                rows.append(
                    {
                        "detail": (
                            f"Trade {i + 1}: {t.get('side', '?')} {t.get('symbol', '')} "
                            f"PnL={t.get('pnl', 0):.2f} "
                            f"Hold={t.get('hold_days', 0)}d"
                        )
                    }
                )
            else:
                rows.append(
                    {
                        "detail": (
                            f"Trade {i + 1}: {getattr(t, 'side', '?')} {getattr(t, 'symbol', '')} "
                            f"PnL={getattr(t, 'pnl', 0):.2f} "
                            f"Hold={getattr(t, 'hold_days', 0)}d"
                        )
                    }
                )
        return rows

    @staticmethod
    def _render_html(
        strategy_name: str,
        benchmark_name: str,
        metric_rows: List[Dict[str, str]],
        trade_rows: List[Dict[str, str]],
        equity_img: str,
        dd_img: str,
        monthly_img: str,
        trade_img: str,
        position_img: str,
    ) -> str:
        """Render the full HTML page."""
        metric_table_rows = ""
        for r in metric_rows:
            cls = "group-header" if r["value"] == "" else ""
            metric_table_rows += (
                f'<tr class="{cls}"><td>{r["metric"]}</td><td>{r["value"]}</td></tr>\n'
            )

        trade_table_rows = ""
        for r in trade_rows:
            trade_table_rows += f"<tr><td>{r['detail']}</td></tr>\n"

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{strategy_name} Performance Report</title>
<style>
  body {{ font-family: "Microsoft YaHei", "SimHei", sans-serif; margin: 0; padding: 20px; background: #f5f5f5; color: #333; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ text-align: center; color: #1565C0; }}
  h2 {{ color: #1565C0; border-bottom: 2px solid #1565C0; padding-bottom: 4px; margin-top: 30px; }}
  table {{ width: 100%; border-collapse: collapse; background: white; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #e0e0e0; }}
  th {{ background: #1565C0; color: white; }}
  tr.group-header td {{ background: #E3F2FD; font-weight: bold; }}
  tr:hover {{ background: #f9f9f9; }}
  .chart {{ text-align: center; margin: 20px 0; }}
  .chart img {{ max-width: 100%; box-shadow: 0 2px 8px rgba(0,0,0,0.15); border-radius: 4px; }}
  .footer {{ text-align: center; color: #999; margin-top: 40px; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
<h1>{strategy_name} Performance Report</h1>
<p style="text-align:center;color:#666;">Benchmark: {benchmark_name} | Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

<h2>Key Metrics</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
{metric_table_rows}
</table>

<h2>Equity Curve</h2>
<div class="chart"><img src="{equity_img}" alt="Equity Curve"></div>

<h2>Drawdown</h2>
<div class="chart"><img src="{dd_img}" alt="Drawdown"></div>

<h2>Monthly Return Heatmap</h2>
<div class="chart"><img src="{monthly_img}" alt="Monthly Returns"></div>

<h2>Trade Distribution</h2>
<div class="chart"><img src="{trade_img}" alt="Trade Distribution"></div>

<h2>Position History</h2>
<div class="chart"><img src="{position_img}" alt="Position History"></div>

<h2>Trade Analysis</h2>
<table>
<tr><th>Detail</th></tr>
{trade_table_rows}
</table>

<div class="footer">Generated by Quant Framework Analysis Module</div>
</div>
</body>
</html>"""
