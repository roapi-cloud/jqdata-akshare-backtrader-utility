# -*- coding: utf-8 -*-
"""生成详细的策略风险分析表格"""

import os
import re
import csv
from typing import Dict, List


class StrategyRiskAnalyzer:
    """策略风险特征分析器"""

    def __init__(self, strategy_dir: str):
        self.strategy_dir = strategy_dir

    def scan_strategies(self) -> List[Dict]:
        """扫描目录中的所有策略文件"""
        strategies = []
        for filename in os.listdir(self.strategy_dir):
            if filename.endswith(".txt") or filename.endswith(".py"):
                filepath = os.path.join(self.strategy_dir, filename)
                if self._is_strategy_file(filepath):
                    strategies.append({"filename": filename, "filepath": filepath})
        return strategies

    def _is_strategy_file(self, filepath: str) -> bool:
        """检查文件是否是策略文件"""
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(2000)
                indicators = [
                    "def initialize",
                    "set_option",
                    "def handle_data",
                    "def before_trading_start",
                    "order_target_value",
                    "get_fundamentals",
                    "attribute_history",
                    "g.stocknum",
                    "g.bearpercent",
                    "run_daily",
                ]
                return any(indicator in content for indicator in indicators)
        except:
            return False

    def analyze_strategy(self, filepath: str) -> Dict:
        """分析单个策略的风险特征"""
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except:
            return {}

        # 提取策略标题（第一行注释）
        title = self._extract_title(content)

        # 策略类型
        strategy_types = self._detect_strategy_types(content)

        # 持仓数量
        stock_count = self._extract_stock_count(content)

        # 仓位控制
        bear_position = self._extract_bear_position(content)
        max_position = self._extract_max_position(content)

        # 止损机制
        stop_loss_types = self._extract_stop_loss(content)

        # 择时机制
        timing_methods = self._extract_timing(content)

        # 交易频率
        frequency = self._extract_frequency(content)

        # 风险过滤
        filters = self._extract_filters(content)

        # 因子类型
        factors = self._extract_factors(content)

        # 杠杆
        leverage = self._extract_leverage(content)

        # 计算风险评分
        risk_score = self._calculate_risk_score(
            stock_count,
            strategy_types,
            stop_loss_types,
            timing_methods,
            filters,
            leverage,
        )

        risk_level = "低" if risk_score <= 3 else ("中" if risk_score <= 6 else "高")

        return {
            "filename": os.path.basename(filepath),
            "title": title,
            "strategy_types": "; ".join(strategy_types) if strategy_types else "其他",
            "stock_count": stock_count if stock_count else "未指定",
            "concentration": self._get_concentration_level(stock_count),
            "bear_position": f"{bear_position * 100:.0f}%" if bear_position else "无",
            "max_position": f"{max_position * 100:.0f}%" if max_position else "无",
            "stop_loss": "; ".join(stop_loss_types) if stop_loss_types else "无",
            "timing": "; ".join(timing_methods) if timing_methods else "无",
            "frequency": frequency,
            "filters": "; ".join(filters) if filters else "无",
            "factors": "; ".join(factors[:5]) if factors else "无",
            "leverage": "; ".join(leverage) if leverage else "无",
            "risk_score": risk_score,
            "risk_level": risk_level,
        }

    def _extract_title(self, content: str) -> str:
        """提取策略标题"""
        lines = content.split("\n")
        for line in lines[:10]:
            if "标题" in line or "title" in line.lower():
                match = re.search(r"[：:]\s*(.+)", line)
                if match:
                    return match.group(1).strip()
        # 尝试从文件名推断
        return ""

    def _detect_strategy_types(self, content: str) -> List[str]:
        """检测策略类型"""
        types = []
        type_patterns = {
            "小市值策略": r"市值|market_cap|小盘|微盘",
            "ETF轮动": r"ETF|轮动",
            "打板/涨停": r"涨停|打板|连板|首板|龙头|high_limit",
            "价值投资": r"价值|股息|红利|高股息|低PE|低PB",
            "机器学习": r"机器学习|随机森林|XGBoost|SVR|神经网络|深度学习",
            "套利": r"套利|折价|溢价|对冲|期货",
            "动量/趋势": r"动量|趋势|均线|MA|BOLL|RSI|MACD",
        }
        for name, pattern in type_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                types.append(name)
        return types if types else ["其他"]

    def _extract_stock_count(self, content: str) -> int:
        """提取持股数量"""
        patterns = [
            r"g\.stocknum\s*=\s*(\d+)",
            r"stocknum\s*=\s*(\d+)",
            r"持股数量.*?(\d+)",
            r"limit\s*\(\s*(\d+)\s*\)",
            r"(\d+)\s*只.*?股票",
            r"count\s*=\s*(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                count = int(match.group(1))
                if 1 <= count <= 500:
                    return count
        return None

    def _extract_bear_position(self, content: str) -> float:
        """提取熊市仓位"""
        match = re.search(r"g\.bearpercent\s*=\s*([\d.]+)", content)
        if match:
            return float(match.group(1))
        return None

    def _extract_max_position(self, content: str) -> float:
        """提取最大仓位"""
        match = re.search(r"maxpercent\s*=\s*([\d.]+)", content)
        if match:
            return float(match.group(1))
        return None

    def _extract_stop_loss(self, content: str) -> List[str]:
        """提取止损机制"""
        types = []
        if re.search(r"止损|stop.?loss", content):
            types.append("止损")
        if re.search(r"止盈|take.?profit", content):
            types.append("止盈")
        if re.search(r"清仓|clear_position", content):
            types.append("清仓")
        return types

    def _extract_timing(self, content: str) -> List[str]:
        """提取择时机制"""
        methods = []
        if re.search(r"牛熊|bull.*?bear|isbull", content):
            methods.append("牛熊判断")
        if re.search(r"RSRS", content):
            methods.append("RSRS择时")
        if re.search(r"BOLL|布林", content):
            methods.append("BOLL择时")
        if re.search(r"均线.*?择时|MA.*?择时", content):
            methods.append("均线择时")
        if re.search(r"择时|timing|signal", content) and not methods:
            methods.append("其他择时")
        return methods

    def _extract_frequency(self, content: str) -> str:
        """提取交易频率"""
        if re.search(r"分钟|minute|handle_data", content):
            return "分钟级"
        if re.search(r"run_daily|每日|每天", content):
            return "每日"
        if re.search(r"每周|weekly", content):
            return "每周"
        if re.search(r"每月|monthly", content):
            return "每月"
        return "未知"

    def _extract_filters(self, content: str) -> List[str]:
        """提取风险过滤"""
        filters = []
        if re.search(r"filter_st|is_st|ST.*?过滤", content):
            filters.append("ST过滤")
        if re.search(r"filter_paused|paused|停牌", content):
            filters.append("停牌过滤")
        if re.search(r"filter_limitup|high_limit|涨停.*?过滤", content):
            filters.append("涨停过滤")
        if re.search(r"filter_new|次新|上市.*?天", content):
            filters.append("次新过滤")
        if re.search(r"filter_gem|创业板|300开头", content):
            filters.append("创业板过滤")
        return filters

    def _extract_factors(self, content: str) -> List[str]:
        """提取因子类型"""
        factors = []
        factor_patterns = {
            "市值": r"market_cap|市值",
            "市盈率": r"pe_ratio|市盈率|PE",
            "市净率": r"pb_ratio|市净率|PB",
            "ROE": r"\broe\b|ROE",
            "ROA": r"\broa\b|ROA",
            "股息率": r"股息率|红利|dividend",
            "PEG": r"PEG",
            "动量": r"momentum|动量|涨幅",
            "成交量": r"volume|成交量",
            "换手率": r"换手率|turnover",
            "北向资金": r"北向|北上",
            "涨停": r"涨停|high_limit",
            "均线": r"MA|均线",
            "RSI": r"RSI",
            "MACD": r"MACD",
            "BOLL": r"BOLL|布林",
        }
        for name, pattern in factor_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                factors.append(name)
        return factors

    def _extract_leverage(self, content: str) -> List[str]:
        """提取杠杆使用"""
        leverage = []
        if re.search(r"融资|融券|margin", content):
            leverage.append("融资融券")
        if re.search(r"期货|futures", content):
            leverage.append("期货")
        if re.search(r"期权|options", content):
            leverage.append("期权")
        return leverage

    def _get_concentration_level(self, count: int) -> str:
        """获取集中度等级"""
        if not count:
            return "未知"
        if count <= 5:
            return "高度集中"
        elif count <= 20:
            return "中等集中"
        elif count <= 50:
            return "适度分散"
        else:
            return "高度分散"

    def _calculate_risk_score(
        self, stock_count, strategy_types, stop_loss, timing, filters, leverage
    ) -> int:
        """计算风险评分"""
        score = 5

        if stock_count:
            if stock_count <= 5:
                score += 2
            elif stock_count <= 10:
                score += 1
            elif stock_count >= 50:
                score -= 1

        if stop_loss:
            score -= 1
        if timing:
            score -= 1
        score -= len(filters) * 0.5
        if leverage:
            score += 2

        if "打板/涨停" in strategy_types:
            score += 2
        if "小市值策略" in strategy_types:
            score += 1
        if "价值投资" in strategy_types:
            score -= 1
        if "套利" in strategy_types:
            score -= 2

        return max(1, min(10, int(score)))


def main():
    strategy_dir = r"E:\jqdata_akshare_backtrader_utility\聚宽有价值策略558"
    analyzer = StrategyRiskAnalyzer(strategy_dir)

    strategies = analyzer.scan_strategies()
    print(f"扫描到 {len(strategies)} 个策略文件，开始分析...")

    results = []
    for i, strategy in enumerate(strategies, 1):
        if i % 50 == 0:
            print(f"  已分析 {i}/{len(strategies)} 个策略...")
        analysis = analyzer.analyze_strategy(strategy["filepath"])
        if analysis:
            results.append(analysis)

    # 按风险评分排序
    results.sort(key=lambda x: x["risk_score"], reverse=True)

    # 生成CSV文件
    csv_file = os.path.join(strategy_dir, "策略风险分析详情.csv")
    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "序号",
                "文件名",
                "策略标题",
                "策略类型",
                "持股数量",
                "集中度",
                "熊市仓位",
                "最大仓位",
                "止损机制",
                "择时机制",
                "交易频率",
                "风险过滤",
                "使用因子",
                "杠杆使用",
                "风险评分",
                "风险等级",
            ]
        )
        for i, r in enumerate(results, 1):
            writer.writerow(
                [
                    i,
                    r["filename"],
                    r["title"],
                    r["strategy_types"],
                    r["stock_count"],
                    r["concentration"],
                    r["bear_position"],
                    r["max_position"],
                    r["stop_loss"],
                    r["timing"],
                    r["frequency"],
                    r["filters"],
                    r["factors"],
                    r["leverage"],
                    r["risk_score"],
                    r["risk_level"],
                ]
            )

    print(f"\nCSV文件已保存: {csv_file}")

    # 生成Markdown表格
    md_file = os.path.join(strategy_dir, "策略风险分析详情.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("# 策略风险分析详情表\n\n")
        f.write(f"共分析 {len(results)} 个策略\n\n")

        # 按风险等级分组统计
        high = [r for r in results if r["risk_score"] >= 7]
        mid = [r for r in results if 4 <= r["risk_score"] <= 6]
        low = [r for r in results if r["risk_score"] <= 3]

        f.write("## 统计摘要\n\n")
        f.write(f"| 风险等级 | 数量 | 占比 |\n")
        f.write(f"|---------|------|------|\n")
        f.write(
            f"| 高风险(7-10) | {len(high)} | {len(high) * 100 / len(results):.1f}% |\n"
        )
        f.write(
            f"| 中风险(4-6) | {len(mid)} | {len(mid) * 100 / len(results):.1f}% |\n"
        )
        f.write(
            f"| 低风险(1-3) | {len(low)} | {len(low) * 100 / len(results):.1f}% |\n"
        )

        f.write("\n---\n\n")

        # 高风险策略
        f.write("## 高风险策略 (评分 7-10)\n\n")
        f.write(
            "| 序号 | 文件名 | 策略类型 | 持股数 | 集中度 | 止损 | 择时 | 过滤 | 因子 | 杠杆 | 评分 |\n"
        )
        f.write(
            "|------|--------|----------|--------|--------|------|------|------|------|------|------|\n"
        )
        for i, r in enumerate([x for x in results if x["risk_score"] >= 7], 1):
            f.write(
                f"| {i} | {r['filename'][:30]} | {r['strategy_types'][:20]} | {r['stock_count']} | {r['concentration']} | {r['stop_loss'][:10]} | {r['timing'][:10]} | {r['filters'][:15]} | {r['factors'][:20]} | {r['leverage'][:10]} | {r['risk_score']} |\n"
            )

        f.write("\n---\n\n")

        # 中风险策略
        f.write("## 中风险策略 (评分 4-6)\n\n")
        f.write(
            "| 序号 | 文件名 | 策略类型 | 持股数 | 集中度 | 止损 | 择时 | 过滤 | 因子 | 杠杆 | 评分 |\n"
        )
        f.write(
            "|------|--------|----------|--------|--------|------|------|------|------|------|------|\n"
        )
        for i, r in enumerate([x for x in results if 4 <= x["risk_score"] <= 6], 1):
            f.write(
                f"| {i} | {r['filename'][:30]} | {r['strategy_types'][:20]} | {r['stock_count']} | {r['concentration']} | {r['stop_loss'][:10]} | {r['timing'][:10]} | {r['filters'][:15]} | {r['factors'][:20]} | {r['leverage'][:10]} | {r['risk_score']} |\n"
            )

        f.write("\n---\n\n")

        # 低风险策略
        f.write("## 低风险策略 (评分 1-3)\n\n")
        f.write(
            "| 序号 | 文件名 | 策略类型 | 持股数 | 集中度 | 止损 | 择时 | 过滤 | 因子 | 杠杆 | 评分 |\n"
        )
        f.write(
            "|------|--------|----------|--------|--------|------|------|------|------|------|------|\n"
        )
        for i, r in enumerate([x for x in results if x["risk_score"] <= 3], 1):
            f.write(
                f"| {i} | {r['filename'][:30]} | {r['strategy_types'][:20]} | {r['stock_count']} | {r['concentration']} | {r['stop_loss'][:10]} | {r['timing'][:10]} | {r['filters'][:15]} | {r['factors'][:20]} | {r['leverage'][:10]} | {r['risk_score']} |\n"
            )

    print(f"Markdown文件已保存: {md_file}")

    # 打印前20个高风险策略示例
    print("\n=== 高风险策略示例 (前20个) ===")
    print(f"{'序号':<4} {'文件名':<40} {'类型':<20} {'持股':<6} {'评分':<4}")
    print("-" * 80)
    for i, r in enumerate([x for x in results if x["risk_score"] >= 7][:20], 1):
        print(
            f"{i:<4} {r['filename'][:38]:<40} {r['strategy_types'][:18]:<20} {r['stock_count']:<6} {r['risk_score']:<4}"
        )


if __name__ == "__main__":
    main()
