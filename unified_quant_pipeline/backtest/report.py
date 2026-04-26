"""报告生成 - 生成回测报告"""

import logging
import pandas as pd
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ReportGenerator:
    """回测报告生成器"""

    def __init__(self, output_dir: str = "./reports"):
        """初始化报告生成器

        Args:
            output_dir: 输出目录路径
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_html(
        self, backtest_result: Dict, filename: str = "backtest_report.html"
    ) -> str:
        """生成HTML报告

        Args:
            backtest_result: 回测结果字典
            filename: 输出文件名

        Returns:
            str: 生成的文件路径
        """
        metrics = backtest_result["metrics"]
        nav = backtest_result["nav"]

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>量化策略回测报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        .metric {{ font-size: 1.2em; margin: 10px 0; }}
        .positive {{ color: green; }}
        .negative {{ color: red; }}
    </style>
</head>
<body>
    <h1>量化策略回测报告</h1>

    <h2>核心指标</h2>
    <table>
        <tr><th>指标</th><th>值</th></tr>
        <tr><td>总收益率</td><td class="{"positive" if metrics.get("total_return", 0) > 0 else "negative"}">{metrics.get("total_return", 0) * 100:.2f}%</td></tr>
        <tr><td>年化收益</td><td>{metrics.get("annual_return", 0) * 100:.2f}%</td></tr>
        <tr><td>最大回撤</td><td class="negative">{metrics.get("max_drawdown", 0) * 100:.2f}%</td></tr>
        <tr><td>夏普比率</td><td>{metrics.get("sharpe", 0):.2f}</td></tr>
        <tr><td>胜率</td><td>{metrics.get("win_rate", 0) * 100:.2f}%</td></tr>
        <tr><td>回测天数</td><td>{metrics.get("n_days", 0)}</td></tr>
    </table>

    <h2>净值曲线</h2>
    <p>起始净值: {nav.iloc[0]:,.2f}</p>
    <p>结束净值: {nav.iloc[-1]:,.2f}</p>

    <hr>
    <p><i>报告生成时间: {pd.Timestamp.now()}</i></p>
</body>
</html>"""

        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"HTML report saved to {filepath}")
        return str(filepath)

    def generate_csv(
        self, backtest_result: Dict, filename: str = "backtest_detail.csv"
    ) -> str:
        """生成CSV明细

        Args:
            backtest_result: 回测结果字典
            filename: 输出文件名

        Returns:
            str: 生成的文件路径
        """
        nav = backtest_result["nav"]
        returns = backtest_result.get("daily_returns", pd.Series())

        df = pd.DataFrame(
            {
                "date": nav.index,
                "nav": nav.values,
                "daily_return": returns.values
                if len(returns) == len(nav)
                else [0] * len(nav),
            }
        )

        filepath = self.output_dir / filename
        df.to_csv(filepath, index=False)

        logger.info(f"CSV detail saved to {filepath}")
        return str(filepath)
