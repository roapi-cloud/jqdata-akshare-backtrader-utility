"""
参数敏感性分析框架
分析策略参数对策略表现的影响
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict
import itertools


class ParameterAnalyzer:
    def __init__(self, strategy_dir):
        self.strategy_dir = Path(strategy_dir)
        self.strategy_params = {}

    def extract_parameters_from_file(self, file_path):
        """从策略文件中提取参数"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"读取文件失败 {file_path}: {e}")
            return {}

        params = {}

        # 1. 提取g.xxx = value 形式的参数
        g_param_pattern = r"g\.(\w+)\s*=\s*([^#\n]+)"
        g_matches = re.findall(g_param_pattern, content)
        for param_name, param_value in g_matches:
            # 尝试解析值
            try:
                # 处理数字
                if "." in param_value:
                    value = float(param_value.strip())
                else:
                    value = int(param_value.strip())
            except:
                # 处理字符串
                value = param_value.strip().strip('"').strip("'")

            params[f"g.{param_name}"] = {
                "value": value,
                "type": type(value).__name__,
                "line": content[: content.find(f"g.{param_name}")].count("\n") + 1,
            }

        # 2. 提取params元组中的参数
        params_tuple_pattern = r"params\s*=\s*\(([^)]+)\)"
        params_matches = re.findall(params_tuple_pattern, content, re.DOTALL)
        for params_str in params_matches:
            # 解析元组中的参数
            param_pattern = r"['\"](\w+)['\"]\s*,\s*([^,\)]+)"
            param_matches = re.findall(param_pattern, params_str)
            for param_name, param_value in param_matches:
                try:
                    if "." in param_value:
                        value = float(param_value.strip())
                    else:
                        value = int(param_value.strip())
                except:
                    value = param_value.strip().strip('"').strip("'")

                params[f"params.{param_name}"] = {
                    "value": value,
                    "type": type(value).__name__,
                    "line": content[: content.find(f"('{param_name}'")].count("\n") + 1,
                }

        # 3. 提取函数参数默认值
        func_pattern = r"def\s+(\w+)\s*\(([^)]+)\):"
        func_matches = re.findall(func_pattern, content)
        for func_name, args_str in func_matches:
            # 解析参数默认值
            args = args_str.split(",")
            for arg in args:
                if "=" in arg:
                    param_name, param_value = arg.split("=", 1)
                    param_name = param_name.strip()
                    param_value = param_value.strip()

                    try:
                        if "." in param_value:
                            value = float(param_value)
                        else:
                            value = int(param_value)
                    except:
                        value = param_value.strip('"').strip("'")

                    params[f"{func_name}.{param_name}"] = {
                        "value": value,
                        "type": type(value).__name__,
                        "line": content[: content.find(f"def {func_name}")].count("\n")
                        + 1,
                    }

        return params

    def scan_all_strategies(self):
        """扫描所有策略文件"""
        print(f"开始扫描策略参数: {self.strategy_dir}")

        txt_files = list(self.strategy_dir.glob("*.txt"))
        print(f"找到 {len(txt_files)} 个策略文件")

        for file_path in txt_files:
            if "场景适配" in file_path.name or "配套资料" in file_path.name:
                continue

            params = self.extract_parameters_from_file(file_path)
            if params:
                strategy_name = file_path.stem
                self.strategy_params[strategy_name] = params
                print(f"从 {file_path.name} 中提取到 {len(params)} 个参数")

    def generate_parameter_report(self, output_file="parameter_report.txt"):
        """生成参数报告"""
        report_path = self.strategy_dir / output_file

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("策略参数分析报告\n")
            f.write("=" * 80 + "\n\n")

            # 统计汇总
            total_params = 0
            param_types = defaultdict(int)
            param_ranges = defaultdict(list)

            for strategy, params in self.strategy_params.items():
                total_params += len(params)
                for param_name, param_info in params.items():
                    param_types[param_info["type"]] += 1
                    param_ranges[param_name].append(param_info["value"])

            f.write(f"1. 总体统计\n")
            f.write(f"   策略总数: {len(self.strategy_params)}\n")
            f.write(f"   参数总数: {total_params}\n\n")

            f.write(f"2. 参数类型分布\n")
            for param_type, count in sorted(param_types.items()):
                f.write(f"   {param_type}: {count} 个\n")
            f.write("\n")

            f.write(f"3. 各策略参数详情\n")
            f.write("-" * 80 + "\n")

            for strategy, params in sorted(self.strategy_params.items()):
                f.write(f"\n策略: {strategy}\n")
                f.write(f"参数数量: {len(params)}\n")

                # 按类型分组
                params_by_type = defaultdict(list)
                for param_name, param_info in params.items():
                    params_by_type[param_info["type"]].append((param_name, param_info))

                for param_type, param_list in sorted(params_by_type.items()):
                    f.write(f"  {param_type}参数:\n")
                    for param_name, param_info in sorted(param_list):
                        f.write(
                            f"    {param_name}: {param_info['value']} (行号: {param_info['line']})\n"
                        )

            f.write("\n" + "=" * 80 + "\n")
            f.write("4. 常用参数分析\n")
            f.write("-" * 80 + "\n")

            # 分析常用参数
            common_params = defaultdict(int)
            for params in self.strategy_params.values():
                for param_name in params.keys():
                    # 提取基础参数名
                    base_name = param_name.split(".")[-1]
                    common_params[base_name] += 1

            for param_name, count in sorted(
                common_params.items(), key=lambda x: x[1], reverse=True
            ):
                if count > 1:
                    f.write(f"{param_name}: 在 {count} 个策略中使用\n")

            f.write("\n" + "=" * 80 + "\n")
            f.write("5. 参数范围分析\n")
            f.write("-" * 80 + "\n")

            # 分析参数范围
            for param_name, values in sorted(param_ranges.items()):
                if len(values) > 1:
                    numeric_values = [v for v in values if isinstance(v, (int, float))]
                    if numeric_values:
                        min_val = min(numeric_values)
                        max_val = max(numeric_values)
                        avg_val = sum(numeric_values) / len(numeric_values)
                        f.write(
                            f"{param_name}: 范围 [{min_val}, {max_val}], 平均值 {avg_val:.2f}, 样本数 {len(numeric_values)}\n"
                        )

        print(f"参数报告已生成: {report_path}")
        return report_path

    def generate_sensitivity_analysis(self, strategy_name, param_ranges=None):
        """生成参数敏感性分析建议"""
        if strategy_name not in self.strategy_params:
            print(f"未找到策略: {strategy_name}")
            return None

        params = self.strategy_params[strategy_name]
        analysis = {"strategy": strategy_name, "parameters": {}, "suggestions": []}

        for param_name, param_info in params.items():
            param_analysis = {
                "current_value": param_info["value"],
                "type": param_info["type"],
                "sensitivity_level": "low",
                "test_range": None,
                "recommendation": "",
            }

            # 根据参数类型和名称提供建议
            base_name = param_name.split(".")[-1].lower()

            if "num" in base_name or "count" in base_name:
                param_analysis["sensitivity_level"] = "medium"
                param_analysis["test_range"] = [1, 2, 3, 5, 8, 10, 15, 20]
                param_analysis["recommendation"] = (
                    "持股数量对策略表现有显著影响，建议测试不同持股数量"
                )

            elif "percent" in base_name or "ratio" in base_name:
                param_analysis["sensitivity_level"] = "high"
                if isinstance(param_info["value"], float):
                    base_val = param_info["value"]
                    param_analysis["test_range"] = [
                        base_val * 0.5,
                        base_val * 0.8,
                        base_val,
                        base_val * 1.2,
                        base_val * 1.5,
                    ]
                param_analysis["recommendation"] = (
                    "比例参数对仓位控制和风险收益比有重要影响"
                )

            elif "period" in base_name or "days" in base_name or "lag" in base_name:
                param_analysis["sensitivity_level"] = "high"
                param_analysis["test_range"] = [5, 10, 20, 30, 60, 120, 250]
                param_analysis["recommendation"] = (
                    "时间周期参数对择时和动量策略效果有显著影响"
                )

            elif "threshold" in base_name:
                param_analysis["sensitivity_level"] = "high"
                if isinstance(param_info["value"], float):
                    base_val = param_info["value"]
                    param_analysis["test_range"] = [
                        base_val * 0.5,
                        base_val * 0.8,
                        base_val,
                        base_val * 1.2,
                        base_val * 1.5,
                    ]
                param_analysis["recommendation"] = (
                    "阈值参数直接影响信号触发频率，需要仔细调整"
                )

            elif "weight" in base_name:
                param_analysis["sensitivity_level"] = "medium"
                param_analysis["test_range"] = [1, 2, 3, 5, 8, 10]
                param_analysis["recommendation"] = (
                    "权重参数影响因子重要性排序，建议使用网格搜索"
                )

            else:
                param_analysis["sensitivity_level"] = "low"
                param_analysis["recommendation"] = (
                    "该参数可能对策略表现影响较小，可保持默认值"
                )

            analysis["parameters"][param_name] = param_analysis

        # 生成整体建议
        high_sensitivity = [
            p
            for p, info in analysis["parameters"].items()
            if info["sensitivity_level"] == "high"
        ]
        if high_sensitivity:
            analysis["suggestions"].append(
                f"重点关注高敏感性参数: {', '.join(high_sensitivity)}"
            )
            analysis["suggestions"].append("建议使用网格搜索或贝叶斯优化进行参数调优")
            analysis["suggestions"].append("进行参数敏感性分析时，注意避免过拟合")

        return analysis

    def generate_sensitivity_report(self, output_file="sensitivity_analysis.txt"):
        """生成参数敏感性分析报告"""
        report_path = self.strategy_dir / output_file

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("参数敏感性分析报告\n")
            f.write("=" * 80 + "\n\n")

            f.write("1. 分析概述\n")
            f.write("   本报告分析策略参数对表现的影响程度，提供参数调优建议。\n\n")

            f.write("2. 参数敏感性分级\n")
            f.write("   - 高敏感性: 参数变化对策略表现有显著影响，需要仔细调整\n")
            f.write("   - 中敏感性: 参数变化对策略表现有一定影响，建议测试\n")
            f.write("   - 低敏感性: 参数变化对策略表现影响较小，可保持默认值\n\n")

            f.write("3. 各策略参数敏感性分析\n")
            f.write("-" * 80 + "\n")

            for strategy_name in sorted(self.strategy_params.keys()):
                analysis = self.generate_sensitivity_analysis(strategy_name)
                if analysis:
                    f.write(f"\n策略: {strategy_name}\n")
                    f.write(f"参数数量: {len(analysis['parameters'])}\n")

                    # 按敏感性分组
                    by_sensitivity = defaultdict(list)
                    for param_name, param_info in analysis["parameters"].items():
                        by_sensitivity[param_info["sensitivity_level"]].append(
                            (param_name, param_info)
                        )

                    for sensitivity in ["high", "medium", "low"]:
                        if sensitivity in by_sensitivity:
                            f.write(f"  {sensitivity}敏感性参数:\n")
                            for param_name, param_info in by_sensitivity[sensitivity]:
                                f.write(
                                    f"    {param_name}: {param_info['current_value']}\n"
                                )
                                f.write(
                                    f"      建议测试范围: {param_info['test_range']}\n"
                                )
                                f.write(f"      建议: {param_info['recommendation']}\n")

                    if analysis["suggestions"]:
                        f.write(f"  整体建议:\n")
                        for suggestion in analysis["suggestions"]:
                            f.write(f"    - {suggestion}\n")

            f.write("\n" + "=" * 80 + "\n")
            f.write("4. 参数调优方法\n")
            f.write("-" * 80 + "\n")
            f.write("   1. 网格搜索: 在参数范围内系统测试所有组合\n")
            f.write("   2. 随机搜索: 随机采样参数空间，效率较高\n")
            f.write("   3. 贝叶斯优化: 基于历史结果智能选择下一个测试点\n")
            f.write("   4. 遗传算法: 模拟自然选择，适合高维参数空间\n\n")
            f.write("5. 注意事项\n")
            f.write("-" * 80 + "\n")
            f.write("   1. 避免过拟合: 使用样本外测试验证参数稳定性\n")
            f.write("   2. 参数交互: 注意参数之间的相互影响\n")
            f.write("   3. 计算成本: 参数组合数量随参数数量指数增长\n")
            f.write("   4. 市场适应性: 参数可能随市场环境变化而失效\n")

        print(f"参数敏感性分析报告已生成: {report_path}")
        return report_path


def main():
    strategy_dir = r"E:\jqdata_akshare_backtrader_utility\聚宽有价值策略558"

    analyzer = ParameterAnalyzer(strategy_dir)
    analyzer.scan_all_strategies()

    # 生成参数报告
    param_report = analyzer.generate_parameter_report()

    # 生成参数敏感性分析报告
    sensitivity_report = analyzer.generate_sensitivity_report()

    # 示例：对特定策略进行详细分析
    sample_strategy = "01 7年40倍模拟超过两年年化高回撤低"
    if sample_strategy in analyzer.strategy_params:
        analysis = analyzer.generate_sensitivity_analysis(sample_strategy)
        print(f"\n示例策略 '{sample_strategy}' 的参数敏感性分析:")
        print(json.dumps(analysis, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
