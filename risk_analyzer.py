# -*- coding: utf-8 -*-
"""
策略风险特征分析器
通过静态代码分析评估策略的风险特征，无需运行代码
"""

import os
import re
from typing import Dict, List, Optional


class StrategyRiskAnalyzer:
    """策略风险特征分析器"""

    def __init__(self, strategy_dir: str):
        self.strategy_dir = strategy_dir
        self.strategies = []

    def scan_strategies(self) -> List[Dict]:
        """扫描目录中的所有策略文件"""
        strategies = []
        for filename in os.listdir(self.strategy_dir):
            if filename.endswith(".txt") or filename.endswith(".py"):
                filepath = os.path.join(self.strategy_dir, filename)
                if self._is_strategy_file(filepath):
                    strategies.append({"filename": filename, "filepath": filepath})
        self.strategies = strategies
        return strategies

    def _is_strategy_file(self, filepath: str) -> bool:
        """检查文件是否是策略文件"""
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(2000)
                # 聚宽策略的特征
                indicators = [
                    "def initialize",
                    "set_option",
                    "def handle_data",
                    "def before_trading_start",
                    "def after_trading_end",
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
            return {"error": "无法读取文件"}

        analysis = {
            "strategy_type": self._detect_strategy_type(content),
            "holding_concentration": self._analyze_holding_concentration(content),
            "position_control": self._analyze_position_control(content),
            "stop_loss": self._analyze_stop_loss(content),
            "timing_mechanism": self._analyze_timing(content),
            "trading_frequency": self._analyze_trading_frequency(content),
            "risk_filtering": self._analyze_risk_filtering(content),
            "factor_types": self._analyze_factors(content),
            "leverage": self._analyze_leverage(content),
            "risk_score": 0,  # 综合风险评分
        }

        # 计算综合风险评分
        analysis["risk_score"] = self._calculate_risk_score(analysis)

        return analysis

    def _detect_strategy_type(self, content: str) -> Dict:
        """检测策略类型"""
        types = []

        # 小市值策略
        if re.search(r"市值|market_cap|circulating_market_cap|小盘|微盘", content):
            types.append("小市值策略")

        # ETF轮动策略
        if re.search(r"ETF|轮动|动量轮动|RSRS", content):
            types.append("ETF轮动策略")

        # 打板/涨停策略
        if re.search(r"涨停|打板|连板|首板|龙头|high_limit", content):
            types.append("打板/涨停策略")

        # 价值投资策略
        if re.search(r"价值|股息|红利|高股息|低PE|低PB|ROE|ROA", content):
            types.append("价值投资策略")

        # 机器学习策略
        if re.search(r"机器学习|随机森林|XGBoost|SVR|神经网络|深度学习|LSTM", content):
            types.append("机器学习策略")

        # 套利策略
        if re.search(r"套利|折价|溢价|对冲|期货", content):
            types.append("套利策略")

        # 动量策略
        if re.search(r"动量|趋势|均线|MA|BOLL|RSI|MACD", content):
            types.append("动量/趋势策略")

        return {
            "types": types if types else ["其他"],
            "primary_type": types[0] if types else "其他",
        }

    def _analyze_holding_concentration(self, content: str) -> Dict:
        """分析持仓集中度"""
        result = {"stock_count": None, "concentration_level": "未知"}

        # 查找持股数量设置
        patterns = [
            r"g\.stocknum\s*=\s*(\d+)",
            r"stocknum\s*=\s*(\d+)",
            r"持股数量.*?(\d+)",
            r"limit\s*\(\s*(\d+)\s*\)",
            r"持仓.*?(\d+).*?只",
            r"(\d+)\s*只.*?股票",
            r"count\s*=\s*(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                count = int(match.group(1))
                result["stock_count"] = count
                break

        # 判断集中度水平
        if result["stock_count"]:
            if result["stock_count"] <= 5:
                result["concentration_level"] = "高度集中"
            elif result["stock_count"] <= 20:
                result["concentration_level"] = "中等集中"
            elif result["stock_count"] <= 50:
                result["concentration_level"] = "适度分散"
            else:
                result["concentration_level"] = "高度分散"

        return result

    def _analyze_position_control(self, content: str) -> Dict:
        """分析仓位控制"""
        result = {
            "has_position_control": False,
            "bear_position": None,
            "max_position": None,
            "position_method": "未知",
        }

        # 熊市仓位控制
        bear_match = re.search(r"g\.bearpercent\s*=\s*([\d.]+)", content)
        if bear_match:
            result["has_position_control"] = True
            result["bear_position"] = float(bear_match.group(1))

        # 仓位限制
        max_pos_match = re.search(r"maxpercent\s*=\s*([\d.]+)", content)
        if max_pos_match:
            result["max_position"] = float(max_pos_match.group(1))

        # 仓位分配方式
        if re.search(r"总价值.*?除以|total_value.*?/", content):
            result["position_method"] = "等权分配"
        elif re.search(r"buycash.*?=.*?free_value.*?/", content):
            result["position_method"] = "动态等权"

        return result

    def _analyze_stop_loss(self, content: str) -> Dict:
        """分析止损机制"""
        result = {
            "has_stop_loss": False,
            "stop_loss_type": [],
            "stop_loss_threshold": None,
        }

        # 止损关键词
        if re.search(r"止损|stop.?loss|卖出|清仓", content):
            result["has_stop_loss"] = True

        # 止盈
        if re.search(r"止盈|take.?profit", content):
            result["stop_loss_type"].append("止盈")

        # 跌幅止损
        loss_match = re.search(r"跌幅.*?([\d.]+)%|loss.*?([\d.]+)%", content)
        if loss_match:
            threshold = loss_match.group(1) or loss_match.group(2)
            result["stop_loss_threshold"] = float(threshold)
            result["stop_loss_type"].append("跌幅止损")

        # 时间止损
        if re.search(r"持有.*?天|hold.*?day", content):
            result["stop_loss_type"].append("时间止损")

        # 价格止损
        if re.search(r"close.*?<|price.*?<", content):
            result["stop_loss_type"].append("价格止损")

        return result

    def _analyze_timing(self, content: str) -> Dict:
        """分析择时机制"""
        result = {
            "has_timing": False,
            "timing_methods": [],
            "bull_bear_detection": False,
        }

        # 牛熊判断
        if re.search(r"牛熊|bull.*?bear|isbull", content):
            result["has_timing"] = True
            result["bull_bear_detection"] = True
            result["timing_methods"].append("牛熊判断")

        # 均线择时
        if re.search(r"均线.*?择时|MA.*?择时|均线.*?突破", content):
            result["has_timing"] = True
            result["timing_methods"].append("均线择时")

        # RSRS择时
        if re.search(r"RSRS", content):
            result["has_timing"] = True
            result["timing_methods"].append("RSRS择时")

        # BOLL择时
        if re.search(r"BOLL|布林", content):
            result["has_timing"] = True
            result["timing_methods"].append("BOLL择时")

        # 其他择时
        if re.search(r"择时|timing|signal", content):
            result["has_timing"] = True

        return result

    def _analyze_trading_frequency(self, content: str) -> Dict:
        """分析交易频率"""
        result = {"frequency": "未知", "trading_time": [], "rebalance_cycle": None}

        # 每日交易
        if re.search(r"run_daily|每日|每天|daily", content):
            result["frequency"] = "每日"

        # 每周调仓
        if re.search(r"每周|weekly|周线", content):
            result["frequency"] = "每周"

        # 每月调仓
        if re.search(r"每月|monthly|月度", content):
            result["frequency"] = "每月"

        # 分钟级交易
        if re.search(r"分钟|minute|handle_data", content):
            result["frequency"] = "分钟级"

        # 交易时间点
        time_matches = re.findall(r"run_daily.*?'(\d+:\d+)'", content)
        if time_matches:
            result["trading_time"] = time_matches

        return result

    def _analyze_risk_filtering(self, content: str) -> Dict:
        """分析风险过滤机制"""
        result = {
            "filter_st": False,
            "filter_paused": False,
            "filter_limit_up": False,
            "filter_new_stock": False,
            "filter_gem": False,
            "filter_count": 0,
        }

        # ST股票过滤
        if re.search(r"filter_st|is_st|ST.*?过滤|过滤.*?ST", content):
            result["filter_st"] = True
            result["filter_count"] += 1

        # 停牌股票过滤
        if re.search(r"filter_paused|paused|停牌.*?过滤|过滤.*?停牌", content):
            result["filter_paused"] = True
            result["filter_count"] += 1

        # 涨停股票过滤
        if re.search(r"filter_limitup|high_limit|涨停.*?过滤|过滤.*?涨停", content):
            result["filter_limit_up"] = True
            result["filter_count"] += 1

        # 次新股过滤
        if re.search(r"filter_new|次新|上市.*?天|start_date", content):
            result["filter_new_stock"] = True
            result["filter_count"] += 1

        # 创业板过滤
        if re.search(r"filter_gem|创业板|300开头", content):
            result["filter_gem"] = True
            result["filter_count"] += 1

        return result

    def _analyze_factors(self, content: str) -> Dict:
        """分析使用的因子类型"""
        result = {
            "fundamental_factors": [],
            "technical_factors": [],
            "sentiment_factors": [],
        }

        # 基本面因子
        fundamental_patterns = {
            "市值": r"market_cap|市值",
            "市盈率": r"pe_ratio|市盈率|PE",
            "市净率": r"pb_ratio|市净率|PB",
            "ROE": r"roe|ROE",
            "ROA": r"roa|ROA",
            "营收增长": r"revenue.*?growth|营收.*?增长",
            "净利润增长": r"profit.*?growth|净利润.*?增长",
            "股息率": r"dividend.*?yield|股息率|红利",
            "PEG": r"PEG",
        }

        for name, pattern in fundamental_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                result["fundamental_factors"].append(name)

        # 技术面因子
        technical_patterns = {
            "动量": r"momentum|动量|涨幅",
            "均线": r"MA|均线|moving.*?average",
            "成交量": r"volume|成交量",
            "RSI": r"RSI",
            "MACD": r"MACD",
            "BOLL": r"BOLL|布林",
            "ATR": r"ATR",
        }

        for name, pattern in technical_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                result["technical_factors"].append(name)

        # 情绪因子
        sentiment_patterns = {
            "涨停": r"涨停|high_limit",
            "龙虎榜": r"龙虎榜|billboard",
            "北向资金": r"北向|北上|港资",
            "换手率": r"换手率|turnover",
        }

        for name, pattern in sentiment_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                result["sentiment_factors"].append(name)

        return result

    def _analyze_leverage(self, content: str) -> Dict:
        """分析杠杆使用"""
        result = {"uses_leverage": False, "leverage_type": []}

        # 融资融券
        if re.search(r"融资|融券|margin|杠杆", content):
            result["uses_leverage"] = True
            result["leverage_type"].append("融资融券")

        # 期货
        if re.search(r"期货|futures|股指期货", content):
            result["uses_leverage"] = True
            result["leverage_type"].append("期货")

        # 期权
        if re.search(r"期权|options", content):
            result["uses_leverage"] = True
            result["leverage_type"].append("期权")

        return result

    def _calculate_risk_score(self, analysis: Dict) -> int:
        """
        计算综合风险评分 (1-10)
        1-3: 低风险
        4-6: 中等风险
        7-10: 高风险
        """
        score = 5  # 基础分

        # 持仓集中度影响
        holding = analysis["holding_concentration"]
        if holding["stock_count"]:
            if holding["stock_count"] <= 5:
                score += 2
            elif holding["stock_count"] <= 10:
                score += 1
            elif holding["stock_count"] >= 50:
                score -= 1

        # 止损机制影响
        stop_loss = analysis["stop_loss"]
        if stop_loss["has_stop_loss"]:
            score -= 1

        # 择时机制影响
        timing = analysis["timing_mechanism"]
        if timing["has_timing"]:
            score -= 1

        # 风险过滤影响
        filtering = analysis["risk_filtering"]
        score -= filtering["filter_count"] * 0.5

        # 杠杆影响
        leverage = analysis["leverage"]
        if leverage["uses_leverage"]:
            score += 2

        # 策略类型影响
        strategy_types = analysis["strategy_type"]["types"]
        if "打板/涨停策略" in strategy_types:
            score += 2
        if "小市值策略" in strategy_types:
            score += 1
        if "价值投资策略" in strategy_types:
            score -= 1
        if "套利策略" in strategy_types:
            score -= 2

        # 限制在1-10范围内
        return max(1, min(10, int(score)))

    def generate_report(self, output_file: str = None) -> str:
        """生成风险评估报告"""
        if not self.strategies:
            self.scan_strategies()

        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("策略风险特征分析报告")
        report_lines.append("=" * 80)
        report_lines.append(f"\n共扫描到 {len(self.strategies)} 个策略文件\n")

        all_analyses = []

        for i, strategy in enumerate(self.strategies, 1):
            analysis = self.analyze_strategy(strategy["filepath"])
            analysis["filename"] = strategy["filename"]
            all_analyses.append(analysis)

        # 按风险评分排序
        all_analyses.sort(key=lambda x: x["risk_score"], reverse=True)

        # 统计摘要
        report_lines.append("\n【风险评分分布】")
        risk_levels = {"低风险(1-3)": 0, "中等风险(4-6)": 0, "高风险(7-10)": 0}
        for a in all_analyses:
            score = a["risk_score"]
            if score <= 3:
                risk_levels["低风险(1-3)"] += 1
            elif score <= 6:
                risk_levels["中等风险(4-6)"] += 1
            else:
                risk_levels["高风险(7-10)"] += 1

        for level, count in risk_levels.items():
            report_lines.append(f"  {level}: {count} 个策略")

        # 策略类型统计
        type_counts = {}
        for a in all_analyses:
            for t in a["strategy_type"]["types"]:
                type_counts[t] = type_counts.get(t, 0) + 1

        report_lines.append("\n【策略类型分布】")
        for t, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"  {t}: {count} 个策略")

        # 详细分析
        report_lines.append("\n" + "=" * 80)
        report_lines.append("【详细分析】")
        report_lines.append("=" * 80)

        for analysis in all_analyses:
            report_lines.append(f"\n{'-' * 60}")
            report_lines.append(f"策略: {analysis['filename']}")
            report_lines.append(f"{'-' * 60}")

            # 风险评分
            score = analysis["risk_score"]
            risk_level = "低" if score <= 3 else ("中" if score <= 6 else "高")
            report_lines.append(f"综合风险评分: {score}/10 ({risk_level}风险)")

            # 策略类型
            types = ", ".join(analysis["strategy_type"]["types"])
            report_lines.append(f"策略类型: {types}")

            # 持仓集中度
            holding = analysis["holding_concentration"]
            if holding["stock_count"]:
                report_lines.append(
                    f"持股数量: {holding['stock_count']} 只 ({holding['concentration_level']})"
                )

            # 仓位控制
            position = analysis["position_control"]
            if position["has_position_control"]:
                bear_pos = (
                    f"熊市仓位: {position['bear_position'] * 100:.0f}%"
                    if position["bear_position"]
                    else ""
                )
                report_lines.append(f"仓位控制: 是 {bear_pos}")

            # 止损机制
            stop_loss = analysis["stop_loss"]
            if stop_loss["has_stop_loss"]:
                types_str = (
                    ", ".join(stop_loss["stop_loss_type"])
                    if stop_loss["stop_loss_type"]
                    else "有"
                )
                report_lines.append(f"止损机制: {types_str}")

            # 择时机制
            timing = analysis["timing_mechanism"]
            if timing["has_timing"]:
                methods = (
                    ", ".join(timing["timing_methods"])
                    if timing["timing_methods"]
                    else "有"
                )
                report_lines.append(f"择时机制: {methods}")

            # 交易频率
            freq = analysis["trading_frequency"]
            if freq["frequency"] != "未知":
                report_lines.append(f"交易频率: {freq['frequency']}")

            # 风险过滤
            filtering = analysis["risk_filtering"]
            filters = []
            if filtering["filter_st"]:
                filters.append("ST")
            if filtering["filter_paused"]:
                filters.append("停牌")
            if filtering["filter_limit_up"]:
                filters.append("涨停")
            if filtering["filter_new_stock"]:
                filters.append("次新")
            if filtering["filter_gem"]:
                filters.append("创业板")
            if filters:
                report_lines.append(f"风险过滤: {', '.join(filters)}")

            # 因子类型
            factors = analysis["factor_types"]
            all_factors = (
                factors["fundamental_factors"]
                + factors["technical_factors"]
                + factors["sentiment_factors"]
            )
            if all_factors:
                report_lines.append(f"使用因子: {', '.join(all_factors[:5])}")

            # 杠杆
            leverage = analysis["leverage"]
            if leverage["uses_leverage"]:
                report_lines.append(f"杠杆使用: {', '.join(leverage['leverage_type'])}")

        report = "\n".join(report_lines)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report)

        return report


def main():
    """主函数"""
    strategy_dir = r"E:\jqdata_akshare_backtrader_utility\聚宽有价值策略558"
    analyzer = StrategyRiskAnalyzer(strategy_dir)

    # 扫描策略
    strategies = analyzer.scan_strategies()
    print(f"扫描到 {len(strategies)} 个策略文件")

    # 生成报告
    report = analyzer.generate_report()
    print(report)

    # 保存报告
    output_file = os.path.join(strategy_dir, "risk_analysis_report.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n报告已保存到: {output_file}")


if __name__ == "__main__":
    main()
