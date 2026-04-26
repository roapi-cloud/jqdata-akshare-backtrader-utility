"""
批量提取所有策略使用的因子
扫描所有.txt文件，提取聚宽策略中使用的因子信息
"""

import os
import re
from pathlib import Path
from collections import defaultdict


class FactorExtractor:
    def __init__(self, strategy_dir):
        self.strategy_dir = Path(strategy_dir)
        self.factors_by_strategy = defaultdict(list)
        self.factor_categories = {
            "valuation": "估值因子",
            "balance": "资产负债表因子",
            "income": "利润表因子",
            "cash_flow": "现金流量表因子",
            "indicator": "技术指标因子",
            "factor": "自定义因子",
        }

    def extract_factors_from_file(self, file_path):
        """从单个策略文件中提取因子"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"读取文件失败 {file_path}: {e}")
            return []

        factors = []

        # 1. 提取估值因子 (valuation.xxx)
        valuation_pattern = r"valuation\.(\w+)"
        valuation_matches = re.findall(valuation_pattern, content)
        for factor in valuation_matches:
            factors.append(
                {
                    "name": f"valuation.{factor}",
                    "category": "估值因子",
                    "type": "fundamental",
                }
            )

        # 2. 提取财务指标因子 (indicator.xxx)
        indicator_pattern = r"indicator\.(\w+)"
        indicator_matches = re.findall(indicator_pattern, content)
        for factor in indicator_matches:
            factors.append(
                {
                    "name": f"indicator.{factor}",
                    "category": "技术指标因子",
                    "type": "technical",
                }
            )

        # 3. 提取查询中的其他因子
        query_pattern = r"query\([^)]*?(\w+\.\w+)[^)]*?\)"
        query_matches = re.findall(query_pattern, content)
        for factor in query_matches:
            if "." in factor and not factor.startswith("valuation."):
                factors.append(
                    {"name": factor, "category": "其他因子", "type": "fundamental"}
                )

        # 4. 提取排序条件中的因子
        order_pattern = r"order_by\([^)]*?(\w+\.\w+)[^)]*?\)"
        order_matches = re.findall(order_pattern, content)
        for factor in order_matches:
            factors.append(
                {"name": factor, "category": "排序因子", "type": "fundamental"}
            )

        # 5. 提取权重配置中的因子
        weights_pattern = r"g\.weights\s*=\s*\[([^\]]+)\]"
        weights_matches = re.findall(weights_pattern, content)
        for weights_str in weights_matches:
            # 权重通常对应因子列表
            # 尝试找到对应的因子名称
            factor_list_pattern = r"#.*因子.*[：:]\s*([^\n]+)"
            factor_list_matches = re.findall(factor_list_pattern, content)
            for factor_list in factor_list_matches:
                factor_names = [f.strip() for f in factor_list.split("，")]
                for factor_name in factor_names:
                    factors.append(
                        {"name": factor_name, "category": "权重因子", "type": "custom"}
                    )

        # 6. 提取技术指标因子
        technical_patterns = [
            r"MA\([^)]+\)",  # 移动平均
            r"RSI\([^)]+\)",  # RSI
            r"MACD\([^)]+\)",  # MACD
            r"BOLL\([^)]+\)",  # 布林带
            r"KDJ\([^)]+\)",  # KDJ
            r"ATR\([^)]+\)",  # ATR
        ]

        for pattern in technical_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                factors.append(
                    {"name": match, "category": "技术指标", "type": "technical"}
                )

        # 7. 提取自定义计算因子
        # 查找可能的因子计算函数
        custom_factor_patterns = [
            r"def\s+get_\w+factor\w*\(",
            r"def\s+calc_\w+factor\w*\(",
            r"def\s+\w+score\w*\(",
        ]

        for pattern in custom_factor_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                func_name = match.replace("def ", "").replace("(", "")
                factors.append(
                    {"name": func_name, "category": "自定义因子函数", "type": "custom"}
                )

        # 去重
        unique_factors = []
        seen = set()
        for factor in factors:
            factor_key = factor["name"]
            if factor_key not in seen:
                seen.add(factor_key)
                unique_factors.append(factor)

        return unique_factors

    def scan_all_strategies(self):
        """扫描所有策略文件"""
        print(f"开始扫描策略目录: {self.strategy_dir}")

        # 获取所有.txt文件
        txt_files = list(self.strategy_dir.glob("*.txt"))
        print(f"找到 {len(txt_files)} 个策略文件")

        for file_path in txt_files:
            # 跳过说明文档
            if "场景适配" in file_path.name or "配套资料" in file_path.name:
                continue

            factors = self.extract_factors_from_file(file_path)
            if factors:
                strategy_name = file_path.stem
                self.factors_by_strategy[strategy_name] = factors
                print(f"从 {file_path.name} 中提取到 {len(factors)} 个因子")

    def generate_factor_report(self, output_file="factor_report.txt"):
        """生成因子报告"""
        report_path = self.strategy_dir / output_file

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("策略因子分析报告\n")
            f.write("=" * 80 + "\n\n")

            # 统计汇总
            total_factors = set()
            factor_category_count = defaultdict(int)

            for strategy, factors in self.factors_by_strategy.items():
                for factor in factors:
                    total_factors.add(factor["name"])
                    factor_category_count[factor["category"]] += 1

            f.write(f"1. 总体统计\n")
            f.write(f"   策略总数: {len(self.factors_by_strategy)}\n")
            f.write(f"   唯一因子数: {len(total_factors)}\n")
            f.write(f"   因子使用总次数: {sum(factor_category_count.values())}\n\n")

            f.write(f"2. 因子类别分布\n")
            for category, count in sorted(factor_category_count.items()):
                f.write(f"   {category}: {count} 次\n")
            f.write("\n")

            f.write(f"3. 各策略因子详情\n")
            f.write("-" * 80 + "\n")

            for strategy, factors in sorted(self.factors_by_strategy.items()):
                f.write(f"\n策略: {strategy}\n")
                f.write(f"因子数量: {len(factors)}\n")

                # 按类别分组
                factors_by_category = defaultdict(list)
                for factor in factors:
                    factors_by_category[factor["category"]].append(factor["name"])

                for category, factor_names in sorted(factors_by_category.items()):
                    f.write(f"  {category}:\n")
                    for name in sorted(factor_names):
                        f.write(f"    - {name}\n")

            f.write("\n" + "=" * 80 + "\n")
            f.write("4. 常用因子列表\n")
            f.write("-" * 80 + "\n")

            # 按使用频率排序
            factor_usage = defaultdict(int)
            for factors in self.factors_by_strategy.values():
                for factor in factors:
                    factor_usage[factor["name"]] += 1

            for factor, count in sorted(
                factor_usage.items(), key=lambda x: x[1], reverse=True
            ):
                f.write(f"{factor}: 使用 {count} 次\n")

        print(f"因子报告已生成: {report_path}")
        return report_path

    def generate_factor_summary(self):
        """生成因子摘要"""
        summary = {
            "total_strategies": len(self.factors_by_strategy),
            "total_unique_factors": set(),
            "factor_usage": defaultdict(int),
            "common_factors": [],
        }

        for factors in self.factors_by_strategy.values():
            for factor in factors:
                summary["total_unique_factors"].add(factor["name"])
                summary["factor_usage"][factor["name"]] += 1

        summary["total_unique_factors"] = len(summary["total_unique_factors"])

        # 找出常用因子（使用次数 > 1）
        for factor, count in summary["factor_usage"].items():
            if count > 1:
                summary["common_factors"].append({"name": factor, "usage_count": count})

        summary["common_factors"].sort(key=lambda x: x["usage_count"], reverse=True)

        return summary


def main():
    strategy_dir = r"E:\jqdata_akshare_backtrader_utility\聚宽有价值策略558"

    extractor = FactorExtractor(strategy_dir)
    extractor.scan_all_strategies()

    # 生成报告
    report_path = extractor.generate_factor_report()

    # 打印摘要
    summary = extractor.generate_factor_summary()
    print("\n" + "=" * 60)
    print("因子分析摘要")
    print("=" * 60)
    print(f"分析策略数: {summary['total_strategies']}")
    print(f"唯一因子数: {summary['total_unique_factors']}")
    print(f"\n常用因子 (使用次数 > 1):")
    for factor in summary["common_factors"][:20]:  # 显示前20个
        print(f"  {factor['name']}: {factor['usage_count']} 次")

    print(f"\n详细报告已保存到: {report_path}")


if __name__ == "__main__":
    main()
