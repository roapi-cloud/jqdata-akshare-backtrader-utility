"""
策略-因子映射表生成器

功能：
1. 生成策略到因子的映射关系表
2. 生成因子分类表
3. 生成可追溯的对应关系
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

import pandas as pd


class MappingGenerator:
    """策略-因子映射表生成器"""

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._traceability_records = []

    def generate_strategy_factor_mapping(
        self,
        strategy_list: List[Dict[str, Any]],
        parsed_results: Dict[str, Dict[str, Any]],
    ) -> pd.DataFrame:
        """生成策略到因子的映射关系表

        Args:
            strategy_list: 策略列表，每个元素包含策略名称、文件路径等信息
            parsed_results: 策略解析结果，key 为策略名称

        Returns:
            映射关系 DataFrame
        """
        rows = []

        for strategy in strategy_list:
            strategy_name = strategy.get("name", "")
            strategy_path = strategy.get("path", "")
            parsed = parsed_results.get(strategy_name, {})

            factors = parsed.get("factors", [])
            params = parsed.get("parameters", {})
            code_snippets = parsed.get("code_snippets", {})

            for factor in factors:
                factor_name = factor.get("name", "")
                factor_type = factor.get("type", "")
                signal_type = factor.get("signal_type", "unknown")
                factor_params = factor.get("parameters", {})

                row = {
                    "策略名称": strategy_name,
                    "策略文件路径": strategy_path,
                    "因子名称": factor_name,
                    "因子类型": factor_type,
                    "信号类型": signal_type,
                    "策略参数": json.dumps(params, ensure_ascii=False),
                    "因子参数": json.dumps(factor_params, ensure_ascii=False),
                    "生成代码路径": self._derive_code_path(strategy_name, factor_name),
                    "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                rows.append(row)

        df = pd.DataFrame(rows)
        return df

    def generate_factor_category_table(
        self,
        factor_metadata: List[Dict[str, Any]],
    ) -> pd.DataFrame:
        """生成因子分类表

        Args:
            factor_metadata: 因子元数据列表

        Returns:
            因子分类 DataFrame
        """
        rows = []

        for meta in factor_metadata:
            factor_name = meta.get("name", "")
            factor_type = meta.get("type", "")
            source_strategy = meta.get("source_strategy", "")
            signal_type = meta.get("signal_type", "")
            description = meta.get("description", "")
            frequency = meta.get("frequency", "daily")
            data_source = meta.get("data_source", "")
            line_number = meta.get("line_number", None)
            code_snippet = meta.get("code_snippet", "")

            row = {
                "因子名称": factor_name,
                "因子类型": factor_type,
                "来源策略": source_strategy,
                "信号类型": signal_type,
                "描述": description,
                "频率": frequency,
                "数据源": data_source,
                "策略代码行号": line_number,
                "关键代码片段": code_snippet,
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        return df

    def generate_traceability_map(
        self,
        strategy_name: str,
        parsed_result: Dict[str, Any],
        factor_name: str,
    ) -> Dict[str, Any]:
        """生成可追溯的对应关系

        Args:
            strategy_name: 策略名称
            parsed_result: 策略解析结果
            factor_name: 因子名称

        Returns:
            追溯关系字典
        """
        factors = parsed_result.get("factors", [])
        strategy_path = parsed_result.get("path", "")
        full_code = parsed_result.get("full_code", "")
        code_lines = full_code.split("\n") if full_code else []

        target_factor = None
        for f in factors:
            if f.get("name") == factor_name:
                target_factor = f
                break

        if target_factor is None:
            return {
                "策略名称": strategy_name,
                "因子名称": factor_name,
                "状态": "not_found",
                "追溯信息": {},
            }

        line_number = target_factor.get("line_number")
        line_range = target_factor.get("line_range", [])
        logic_snippet = target_factor.get("logic_snippet", "")

        context_lines = []
        if line_number:
            start = max(0, line_number - 5)
            end = min(len(code_lines), line_number + 5)
            for i in range(start, end):
                context_lines.append(
                    {
                        "line_number": i + 1,
                        "code": code_lines[i].rstrip(),
                        "is_target": (i + 1) == line_number,
                    }
                )

        key_logic = self._extract_key_logic(target_factor, code_lines, line_range)

        traceability = {
            "策略名称": strategy_name,
            "策略文件路径": strategy_path,
            "因子名称": factor_name,
            "因子类型": target_factor.get("type", ""),
            "信号类型": target_factor.get("signal_type", ""),
            "因子参数": target_factor.get("parameters", {}),
            "策略代码行号": line_number,
            "代码行范围": line_range,
            "上下文代码": context_lines,
            "关键逻辑片段": key_logic,
            "逻辑描述": target_factor.get("description", ""),
            "生成代码路径": self._derive_code_path(strategy_name, factor_name),
        }

        record = {
            "strategy_name": strategy_name,
            "factor_name": factor_name,
            "traceability": traceability,
            "timestamp": datetime.now().isoformat(),
        }
        self._traceability_records.append(record)

        return record

    def save_mapping_table(
        self,
        mapping_df: pd.DataFrame,
        output_path: Optional[str] = None,
    ) -> str:
        """保存映射表到 CSV

        Args:
            mapping_df: 映射关系 DataFrame
            output_path: 输出路径，默认生成带时间戳的文件名

        Returns:
            实际保存的文件路径
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.output_dir / f"mapping_table_{timestamp}.csv")

        output_path = str(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        mapping_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path

    def save_traceability_report(
        self,
        output_path: Optional[str] = None,
    ) -> str:
        """保存追溯报告到 JSON

        Args:
            output_path: 输出路径

        Returns:
            实际保存的文件路径
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.output_dir / f"traceability_report_{timestamp}.json")

        output_path = str(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        report = {
            "generated_at": datetime.now().isoformat(),
            "total_records": len(self._traceability_records),
            "records": self._traceability_records,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return output_path

    def export_to_excel(
        self,
        output_path: Optional[str] = None,
        mapping_df: Optional[pd.DataFrame] = None,
        category_df: Optional[pd.DataFrame] = None,
    ) -> str:
        """导出到 Excel，包含多个 sheet

        Args:
            output_path: 输出路径
            mapping_df: 映射关系表
            category_df: 因子分类表

        Returns:
            实际保存的文件路径
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(
                self.output_dir / f"strategy_factor_mapping_{timestamp}.xlsx"
            )

        output_path = str(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            if mapping_df is not None and not mapping_df.empty:
                mapping_df.to_excel(writer, sheet_name="策略因子映射", index=False)
                self._auto_adjust_width(writer, "策略因子映射")

            if category_df is not None and not category_df.empty:
                category_df.to_excel(writer, sheet_name="因子分类", index=False)
                self._auto_adjust_width(writer, "因子分类")

            if self._traceability_records:
                trace_df = self._build_traceability_df()
                trace_df.to_excel(writer, sheet_name="追溯关系", index=False)
                self._auto_adjust_width(writer, "追溯关系")

            summary_df = self._build_summary_df(mapping_df, category_df)
            summary_df.to_excel(writer, sheet_name="汇总", index=False)
            self._auto_adjust_width(writer, "汇总")

        return output_path

    def _derive_code_path(self, strategy_name: str, factor_name: str) -> str:
        """根据策略名和因子名推导生成的代码路径"""
        safe_strategy = re.sub(r"[^\w]", "_", strategy_name)
        safe_factor = re.sub(r"[^\w]", "_", factor_name)
        return f"generated_factors/{safe_strategy}/{safe_factor}.py"

    def _extract_key_logic(
        self,
        factor: Dict[str, Any],
        code_lines: List[str],
        line_range: List[int],
    ) -> List[Dict[str, Any]]:
        """提取关键逻辑片段"""
        snippets = []
        if line_range and len(line_range) == 2:
            start, end = line_range
            for i in range(start - 1, min(end, len(code_lines))):
                snippets.append(
                    {
                        "line_number": i + 1,
                        "code": code_lines[i].rstrip(),
                    }
                )
        return snippets

    def _build_traceability_df(self) -> pd.DataFrame:
        """构建追溯关系 DataFrame"""
        rows = []
        for record in self._traceability_records:
            t = record["traceability"]
            row = {
                "策略名称": t.get("策略名称", ""),
                "因子名称": t.get("因子名称", ""),
                "因子类型": t.get("因子类型", ""),
                "信号类型": t.get("信号类型", ""),
                "策略代码行号": t.get("策略代码行号", ""),
                "代码行范围": str(t.get("代码行范围", [])),
                "关键逻辑片段": json.dumps(
                    t.get("关键逻辑片段", []), ensure_ascii=False
                ),
                "生成代码路径": t.get("生成代码路径", ""),
                "追溯时间": record["timestamp"],
            }
            rows.append(row)
        return pd.DataFrame(rows)

    def _build_summary_df(
        self,
        mapping_df: Optional[pd.DataFrame],
        category_df: Optional[pd.DataFrame],
    ) -> pd.DataFrame:
        """构建汇总信息 DataFrame"""
        rows = []
        rows.append(
            {
                "指标": "生成时间",
                "值": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

        if mapping_df is not None and not mapping_df.empty:
            rows.append({"指标": "策略数量", "值": mapping_df["策略名称"].nunique()})
            rows.append({"指标": "因子数量", "值": mapping_df["因子名称"].nunique()})
            rows.append({"指标": "映射关系数", "值": len(mapping_df)})

            type_counts = mapping_df["因子类型"].value_counts()
            for ftype, count in type_counts.items():
                rows.append({"指标": f"因子类型_{ftype}", "值": count})

        if category_df is not None and not category_df.empty:
            rows.append({"指标": "因子分类数", "值": len(category_df)})
            signal_counts = category_df["信号类型"].value_counts()
            for sig, count in signal_counts.items():
                rows.append({"指标": f"信号类型_{sig}", "值": count})

        rows.append(
            {
                "指标": "追溯记录数",
                "值": len(self._traceability_records),
            }
        )

        return pd.DataFrame(rows)

    @staticmethod
    def _auto_adjust_width(writer, sheet_name):
        """自动调整 Excel 列宽"""
        worksheet = writer.sheets[sheet_name]
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    cell_length = len(str(cell.value))
                    max_length = max(max_length, cell_length)
                except (ValueError, AttributeError):
                    pass
            adjusted_width = min(max_length + 4, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
