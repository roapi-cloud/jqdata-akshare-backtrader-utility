"""策略代码解析模块

解析聚宽策略代码（.txt）和 Backtrader 策略代码（.py），
提取选股条件、排序条件、权重配置、调仓周期、持仓数量、因子/指标等，
并转换为结构化的选股规则字典。
"""

import ast
import re
import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class StrategyParser:
    """策略代码解析器

    支持解析聚宽策略（.txt）和 Backtrader 策略（.py），
    提取策略逻辑并输出结构化结果。
    """

    JQ_QUERY_PATTERNS = [
        re.compile(r"query\s*\((.*?)\)", re.DOTALL),
        re.compile(r"q\s*=\s*query\s*\((.*?)\)", re.DOTALL),
    ]

    JQ_FILTER_PATTERNS = [
        re.compile(r"\.filter\s*\((.*?)\)", re.DOTALL),
        re.compile(r"\.filter\(\s*\n(.*?)\)", re.DOTALL),
    ]

    JQ_ORDER_BY_PATTERNS = [
        re.compile(r"\.order_by\s*\((.*?)\)", re.DOTALL),
    ]

    JQ_LIMIT_PATTERNS = [
        re.compile(r"\.limit\s*\((.*?)\)"),
    ]

    JQ_GLOBAL_VAR_PATTERNS = [
        re.compile(r"g\.(\w+)\s*=\s*(.+)"),
    ]

    JQ_RUN_PATTERNS = [
        re.compile(r"run_(daily|weekly|monthly)\s*\((.*?)\)"),
    ]

    JQ_FACTOR_PATTERNS = [
        re.compile(r"get_factor_values\s*\([^,]+,\s*['\"](\w+)['\"]"),
        re.compile(r"jqfactor\s*=\s*['\"](\w+)['\"]"),
        re.compile(r"['\"](\w+)['\"]\s*:\s*get_factor_values"),
    ]

    JQ_TECH_INDICATORS = [
        "MACD",
        "KDJ",
        "RSI",
        "BOLL",
        "CCI",
        "WR",
        "BIAS",
        "ROC",
        "MTM",
        "EMA",
        "SMA",
        "DMA",
        "TRIX",
        "BRAR",
        "CR",
        "PSY",
        "DMA",
        "OBV",
        "ASI",
        "UOS",
        "ROC",
        "MIKE",
        "ENE",
        "STOCHRSI",
        "DIFF",
        "DEA",
        "ATR",
        "DPO",
        "VHF",
        "RVI",
        "FI",
        "EMV",
        "ADTM",
        "MASS",
        "CRC",
        "MA",
        "MOM",
        "DBCB",
        "XSHT",
        "VOL",
        "AVG",
        "COUNT",
        "SUM",
        "STD",
        "VAR",
        "SKEWNESS",
        "KURTOSIS",
    ]

    JQ_FUNDAMENTAL_FIELDS = [
        "market_cap",
        "circulating_market_cap",
        "pe_ratio",
        "pb_ratio",
        "ps_ratio",
        "pcf_ratio",
        "net_profit_ratio",
        "gross_profit_margin",
        "operating_profit_margin",
        "net_profit_margin",
        "roe",
        "roa",
        "roic",
        "inc_revenue_year_on_year",
        "inc_net_profit_year_on_year",
        "total_asset",
        "total_liability",
        "development_expenditure",
        "net_profit",
        "operating_revenue",
        "eps",
        "bps",
    ]

    BT_PARAM_PATTERNS = [
        re.compile(r"params\s*=\s*\(\s*\n((?:.*?\n)*?)\s*\)", re.DOTALL),
        re.compile(r"self\.params\s*=\s*\{([^}]*)\}", re.DOTALL),
    ]

    BT_REBALANCE_PATTERNS = [
        re.compile(r"rebalance_period.*?=\s*(\d+)"),
        re.compile(r"rebalance_freq.*?=\s*['\"](\w+)['\"]"),
        re.compile(r"self\.schedule_function.*?date_rules\.(\w+)"),
    ]

    def __init__(self, output_dir: str = "./output"):
        """初始化策略解析器

        Args:
            output_dir: 解析结果输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def parse_jq_strategy(self, file_path: str) -> Dict:
        """解析聚宽策略代码

        Args:
            file_path: 策略文件路径（.txt 或 .py）

        Returns:
            解析结果字典
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        result = {
            "strategy_type": "joinquant",
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "parsed_at": datetime.now().isoformat(),
            "meta": self._extract_meta(content),
            "stock_selection_rules": self.extract_stock_selection_rules(content),
            "rebalance_frequency": self.extract_rebalance_frequency(content),
            "portfolio_size": self.extract_portfolio_size(content),
            "weights_config": self._extract_weights_config(content),
            "factors_and_indicators": self._extract_factors_and_indicators(content),
            "global_variables": self._extract_global_variables(content),
            "trading_logic": self._extract_trading_logic(content),
            "risk_control": self._extract_risk_control(content),
            "raw_code_snippets": self._extract_key_snippets(content),
        }

        return result

    def parse_backtrader_strategy(self, file_path: str) -> Dict:
        """解析 Backtrader 策略代码

        Args:
            file_path: 策略文件路径（.py）

        Returns:
            解析结果字典
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        result = {
            "strategy_type": "backtrader",
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "parsed_at": datetime.now().isoformat(),
            "meta": self._extract_bt_meta(content),
            "stock_selection_rules": self._extract_bt_selection_rules(content),
            "rebalance_frequency": self._extract_bt_rebalance_frequency(content),
            "portfolio_size": self._extract_bt_portfolio_size(content),
            "parameters": self._extract_bt_parameters(content),
            "factors_and_indicators": self._extract_bt_factors_and_indicators(content),
            "scoring_logic": self._extract_bt_scoring_logic(content),
            "allocation_logic": self._extract_bt_allocation_logic(content),
            "timing_logic": self._extract_bt_timing_logic(content),
            "risk_control": self._extract_bt_risk_control(content),
            "class_structure": self._extract_bt_class_structure(content),
            "raw_code_snippets": self._extract_bt_key_snippets(content),
        }

        return result

    def extract_stock_selection_rules(self, content: str) -> List[Dict]:
        """提取选股规则

        Args:
            content: 策略代码内容

        Returns:
            选股规则列表，每个规则是一个字典
        """
        rules = []

        query_matches = self.JQ_QUERY_PATTERNS[0].finditer(content)

        for match in query_matches:
            query_text = match.group(1)
            query_start = match.start()
            query_line = content[:query_start].count("\n") + 1

            rule = {
                "type": "query",
                "line_number": query_line,
                "selected_fields": self._extract_query_fields(query_text),
                "filters": self._extract_filters_from_query(query_text, content),
                "order_by": self._extract_order_by_from_context(query_text, content),
                "limit": self._extract_limit_from_context(query_text, content),
                "raw_query": query_text.strip()[:500],
            }

            rules.append(rule)

        filter_rules = self._extract_standalone_filters(content)
        rules.extend(filter_rules)

        factor_filter_rules = self._extract_factor_filter_rules(content)
        rules.extend(factor_filter_rules)

        if not rules:
            rules = self._extract_implicit_selection_rules(content)

        return rules

    def extract_rebalance_frequency(self, content: str) -> str:
        """提取调仓周期

        Args:
            content: 策略代码内容

        Returns:
            调仓周期描述字符串
        """
        frequencies = []

        for match in self.JQ_RUN_PATTERNS[0].finditer(content):
            freq_type = match.group(1)
            args = match.group(2)

            time_match = re.search(r"time\s*=\s*['\"]([^'\"]+)['\"]", args)
            ref_match = re.search(r"reference_security\s*=\s*['\"]([^'\"]+)['\"]", args)
            weekday_match = re.search(r"weekday\s*=\s*(\d+)", args)

            freq_desc = {
                "type": freq_type,
                "time": time_match.group(1) if time_match else None,
                "reference": ref_match.group(1) if ref_match else None,
                "weekday": int(weekday_match.group(1)) if weekday_match else None,
            }
            frequencies.append(freq_desc)

        if not frequencies:
            daily_match = re.search(r"rebalance_period.*?=\s*(\d+)", content)
            if daily_match:
                periods = daily_match.group(1)
                frequencies.append(
                    {
                        "type": "daily",
                        "period": int(periods),
                        "time": None,
                        "reference": None,
                        "weekday": None,
                    }
                )

        if not frequencies:
            if "run_daily" in content:
                frequencies.append(
                    {"type": "daily", "time": None, "reference": None, "weekday": None}
                )
            elif "run_weekly" in content:
                frequencies.append(
                    {"type": "weekly", "time": None, "reference": None, "weekday": None}
                )
            elif "run_monthly" in content:
                frequencies.append(
                    {
                        "type": "monthly",
                        "time": None,
                        "reference": None,
                        "weekday": None,
                    }
                )

        if frequencies:
            return self._format_rebalance_frequency(frequencies)

        return "unknown"

    def extract_portfolio_size(self, content: str) -> int:
        """提取持仓数量

        Args:
            content: 策略代码内容

        Returns:
            持仓数量，未找到返回 0
        """
        patterns = [
            re.compile(
                r"g\.(\w*stock_num\w*|buy_stock_count|n_position|hold_count|position_count)\s*=\s*(\d+)"
            ),
            re.compile(r"stock_num\s*=\s*(\d+)"),
            re.compile(r"n_position\s*=\s*(\d+)"),
            re.compile(r"hold_num\s*=\s*(\d+)"),
            re.compile(r"num_stocks\s*=\s*(\d+)"),
            re.compile(r"top_n\s*=\s*(\d+)"),
            re.compile(r"\.limit\s*\(\s*g\.\w*\s*\*\s*(\d+)\s*\)"),
        ]

        for pattern in patterns:
            match = pattern.search(content)
            if match:
                try:
                    return int(
                        match.group(2) if len(match.groups()) > 1 else match.group(1)
                    )
                except (ValueError, IndexError):
                    continue

        limit_matches = re.findall(r"\.limit\s*\(\s*(\d+)\s*\)", content)
        if limit_matches:
            try:
                return int(limit_matches[0])
            except ValueError:
                pass

        return 0

    def save_parsed_result(self, result: Dict, output_path: str) -> str:
        """保存解析结果到 JSON 文件

        Args:
            result: 解析结果字典
            output_path: 输出文件路径

        Returns:
            实际保存的文件路径
        """
        output_path = str(output_path)
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        serializable_result = self._make_serializable(result)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serializable_result, f, ensure_ascii=False, indent=2)

        logger.info(f"解析结果已保存至: {output_path}")
        return output_path

    def _extract_meta(self, content: str) -> Dict:
        """提取策略元数据（标题、作者、来源等）"""
        meta = {}

        title_match = re.search(r"#\s*标题[：:]\s*(.+)", content)
        if title_match:
            meta["title"] = title_match.group(1).strip()

        author_match = re.search(r"#\s*作者[：:]\s*(.+)", content)
        if author_match:
            meta["author"] = author_match.group(1).strip()

        url_match = re.search(r"https://www\.joinquant\.com/post/(\d+)", content)
        if url_match:
            meta["joinquant_post_id"] = url_match.group(1)

        url_full_match = re.search(r"(https://www\.joinquant\.com/[^\s]+)", content)
        if url_full_match:
            meta["source_url"] = url_full_match.group(1)

        benchmark_match = re.search(
            r"set_benchmark\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", content
        )
        if benchmark_match:
            meta["benchmark"] = benchmark_match.group(1)

        cost_match = re.search(r"set_order_cost\s*\((.*?)\)", content, re.DOTALL)
        if cost_match:
            cost_text = cost_match.group(1)
            meta["transaction_cost"] = {
                "close_tax": self._extract_cost_value(cost_text, "close_tax"),
                "open_commission": self._extract_cost_value(
                    cost_text, "open_commission"
                ),
                "close_commission": self._extract_cost_value(
                    cost_text, "close_commission"
                ),
                "min_commission": self._extract_cost_value(cost_text, "min_commission"),
            }

        return meta

    def _extract_cost_value(self, text: str, field: str) -> Optional[float]:
        """从成本配置中提取字段值"""
        match = re.search(rf"{field}\s*=\s*([\d.]+)", text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    def _extract_query_fields(self, query_text: str) -> List[str]:
        """从 query 语句中提取选择的字段"""
        fields = []

        field_patterns = [
            re.findall(r"(\w+)\.(\w+)", query_text),
        ]

        for matches in field_patterns:
            for table, field in matches:
                if table in (
                    "valuation",
                    "indicator",
                    "income",
                    "balance",
                    "cash_flow",
                    "bank_indicator",
                    "security",
                ):
                    fields.append(f"{table}.{field}")

        return list(set(fields))

    def _extract_filters_from_query(
        self, query_text: str, full_content: str
    ) -> List[Dict]:
        """从 query 上下文中提取过滤条件"""
        filters = []

        query_start = full_content.find(query_text)
        context_window = full_content[query_start : query_start + 2000]

        for filter_match in self.JQ_FILTER_PATTERNS[0].finditer(context_window):
            filter_text = filter_match.group(1)
            parsed_filters = self._parse_filter_conditions(filter_text)
            filters.extend(parsed_filters)

        return filters

    def _parse_filter_conditions(self, filter_text: str) -> List[Dict]:
        """解析过滤条件文本"""
        conditions = []

        conditions = re.split(r",\s*\n?", filter_text.strip())

        parsed = []
        for cond in conditions:
            cond = cond.strip().strip("()")
            if not cond:
                continue

            filter_info = self._parse_single_condition(cond)
            if filter_info:
                parsed.append(filter_info)

        return parsed

    def _parse_single_condition(self, cond: str) -> Optional[Dict]:
        """解析单个过滤条件"""
        cond = cond.strip()

        in_match = re.search(r"(\w+\.\w+)\.in_\s*\(([^)]+)\)", cond)
        if in_match:
            return {
                "type": "in_list",
                "field": in_match.group(1),
                "source": in_match.group(2).strip()[:200],
                "raw": cond[:200],
            }

        cmp_match = re.search(r"(\w+\.\w+)\s*([><=!]+)\s*(.+)", cond)
        if cmp_match:
            return {
                "type": "comparison",
                "field": cmp_match.group(1),
                "operator": cmp_match.group(2),
                "value": cmp_match.group(3).strip()[:100],
                "raw": cond[:200],
            }

        if cond and len(cond) < 500:
            return {
                "type": "expression",
                "raw": cond,
            }

        return None

    def _extract_order_by_from_context(
        self, query_text: str, full_content: str
    ) -> Optional[Dict]:
        """从 query 上下文中提取排序条件"""
        query_pos = full_content.find(query_text)
        search_end = min(query_pos + 2000, len(full_content))
        context = full_content[query_pos:search_end]

        for order_match in self.JQ_ORDER_BY_PATTERNS[0].finditer(context):
            order_text = order_match.group(1).strip()

            field_match = re.search(r"(\w+\.\w+)", order_text)
            direction = (
                "asc"
                if "asc()" in order_text
                else "desc"
                if "desc()" in order_text
                else "asc"
            )

            return {
                "field": field_match.group(1) if field_match else order_text,
                "direction": direction,
                "raw": order_text[:200],
            }

        return None

    def _extract_limit_from_context(
        self, query_text: str, full_content: str
    ) -> Optional[int]:
        """从 query 上下文中提取 limit"""
        query_pos = full_content.find(query_text)
        search_end = min(query_pos + 2000, len(full_content))
        context = full_content[query_pos:search_end]

        for limit_match in self.JQ_LIMIT_PATTERNS[0].finditer(context):
            limit_text = limit_match.group(1).strip()

            g_var_match = re.search(r"g\.(\w+)", limit_text)
            if g_var_match:
                var_name = g_var_match.group(1)
                var_match = re.search(rf"g\.{var_name}\s*=\s*(\d+)", full_content)
                if var_match:
                    return int(var_match.group(1))
                return None

            try:
                return int(limit_text)
            except ValueError:
                return None

        return None

    def _extract_standalone_filters(self, content: str) -> List[Dict]:
        """提取独立的过滤函数调用"""
        filters = []

        filter_func_patterns = [
            re.compile(r"(filter_\w+)\s*\(([^)]*)\)"),
            re.compile(r"(get_index_stocks)\s*\(([^)]*)\)"),
            re.compile(r"(get_all_securities)\s*\(([^)]*)\)"),
        ]

        for pattern in filter_func_patterns:
            for match in pattern.finditer(content):
                func_name = match.group(1)
                args = match.group(2).strip()

                if func_name.startswith("filter_"):
                    filters.append(
                        {
                            "type": "filter_function",
                            "function": func_name,
                            "arguments": args[:200],
                            "line_number": content[: match.start()].count("\n") + 1,
                        }
                    )

        return filters

    def _extract_factor_filter_rules(self, content: str) -> List[Dict]:
        """提取基于因子的过滤规则"""
        rules = []

        factor_call_matches = re.finditer(r"get_factor_values\s*\(([^)]+)\)", content)

        for match in factor_call_matches:
            args = match.group(1)
            factor_names = re.findall(r"['\"](\w+)['\"]", args)

            rules.append(
                {
                    "type": "factor_filter",
                    "factors": factor_names,
                    "arguments": args[:300],
                    "line_number": content[: match.start()].count("\n") + 1,
                }
            )

        return rules

    def _extract_implicit_selection_rules(self, content: str) -> List[Dict]:
        """提取隐式的选股规则（非 query 形式）"""
        rules = []

        if "get_index_stocks" in content:
            index_matches = re.finditer(
                r"get_index_stocks\s*\(\s*['\"]?([^'\")]+)['\"]?\s*\)", content
            )
            for match in index_matches:
                rules.append(
                    {
                        "type": "index_constituents",
                        "index": match.group(1).strip().strip("'\""),
                        "line_number": content[: match.start()].count("\n") + 1,
                    }
                )

        if "get_all_securities" in content:
            sec_matches = re.finditer(
                r"get_all_securities\s*\(\s*(?:types\s*=\s*)?\[?([^\]]*)\]?", content
            )
            for match in sec_matches:
                rules.append(
                    {
                        "type": "all_securities",
                        "types": match.group(1).strip()[:100],
                        "line_number": content[: match.start()].count("\n") + 1,
                    }
                )

        return rules

    def _extract_weights_config(self, content: str) -> Dict:
        """提取权重配置"""
        weights = {}

        weight_patterns = [
            re.compile(r"g\.weights\s*=\s*\{([^}]+)\}", re.DOTALL),
            re.compile(r"g\.weight\s*=\s*(.+)"),
            re.compile(r"weights?\s*=\s*\{([^}]+)\}", re.DOTALL),
            re.compile(r"w_\w+\s*=\s*([\d.]+)"),
        ]

        for pattern in weight_patterns:
            for match in pattern.finditer(content):
                if "{" in match.group(0):
                    dict_text = match.group(1)
                    kv_pairs = re.findall(r"['\"](\w+)['\"]\s*:\s*([\d.]+)", dict_text)
                    for k, v in kv_pairs:
                        weights[k] = float(v)
                else:
                    val = match.group(1).strip()
                    try:
                        weights["default"] = float(val)
                    except ValueError:
                        weights["expression"] = val

        equal_weight_match = re.search(
            r"total_value\s*/\s*len\s*\(|cash\s*/\s*\(|value\s*/\s*\(", content
        )
        if equal_weight_match:
            weights["allocation_method"] = "equal_weight"

        return weights

    def _extract_factors_and_indicators(self, content: str) -> Dict:
        """提取使用的因子和指标"""
        result = {
            "jq_factors": [],
            "technical_indicators": [],
            "fundamental_fields": [],
            "custom_factors": [],
            "ml_models": [],
        }

        for match in self.JQ_FACTOR_PATTERNS[0].finditer(content):
            factor = match.group(1)
            if factor not in result["jq_factors"]:
                result["jq_factors"].append(factor)

        for match in self.JQ_FACTOR_PATTERNS[1].finditer(content):
            factor = match.group(1)
            if factor not in result["jq_factors"]:
                result["jq_factors"].append(factor)

        for indicator in self.JQ_TECH_INDICATORS:
            if re.search(rf"\b{indicator}\s*\(", content) or re.search(
                rf"\b{indicator}\b", content
            ):
                if indicator not in result["technical_indicators"]:
                    result["technical_indicators"].append(indicator)

        for field in self.JQ_FUNDAMENTAL_FIELDS:
            if re.search(rf"\b{field}\b", content):
                if field not in result["fundamental_fields"]:
                    result["fundamental_fields"].append(field)

        custom_patterns = [
            re.compile(r"def\s+(\w+_factor|factor_\w+|calc_\w+|compute_\w+)\s*\("),
            re.compile(r"def\s+(\w+_score|score_\w+)\s*\("),
            re.compile(r"def\s+(\w+_momentum|momentum_\w+)\s*\("),
        ]

        for pattern in custom_patterns:
            for match in pattern.finditer(content):
                func_name = match.group(1)
                if func_name not in result["custom_factors"]:
                    result["custom_factors"].append(func_name)

        ml_patterns = [
            re.compile(
                r"(LinearRegression|RandomForest|SVR|XGBoost|LightGBM|LSTM|NeuralNet)\s*\("
            ),
            re.compile(r"from\s+(sklearn|xgboost|lightgbm|tensorflow|pytorch)"),
        ]

        for pattern in ml_patterns:
            for match in pattern.finditer(content):
                model = match.group(1) if match.lastindex else match.group(0)
                if model not in result["ml_models"]:
                    result["ml_models"].append(model)

        return result

    def _extract_global_variables(self, content: str) -> Dict:
        """提取全局变量（g.xxx）配置"""
        variables = {}

        for match in self.JQ_GLOBAL_VAR_PATTERNS[0].finditer(content):
            var_name = match.group(1)
            var_value = match.group(2).strip()

            if var_value.startswith("{"):
                dict_match = re.search(r"\{([^}]*)\}", var_value)
                if dict_match:
                    try:
                        variables[var_name] = eval(f"{{{dict_match.group(1)}}}")
                    except Exception:
                        variables[var_name] = var_value
            elif var_value.startswith("["):
                list_match = re.search(r"\[([^\]]*)\]", var_value)
                if list_match:
                    variables[var_name] = list_match.group(1)[:200]
            elif var_value.startswith("'") or var_value.startswith('"'):
                variables[var_name] = var_value.strip("'\"")
            else:
                try:
                    variables[var_name] = int(var_value)
                except ValueError:
                    try:
                        variables[var_name] = float(var_value)
                    except ValueError:
                        variables[var_name] = var_value[:200]

        return variables

    def _extract_trading_logic(self, content: str) -> Dict:
        """提取交易逻辑"""
        logic = {
            "buy_functions": [],
            "sell_functions": [],
            "adjust_functions": [],
            "order_methods": [],
        }

        func_patterns = [
            (
                "buy_functions",
                re.compile(r"def\s+(buy_\w+|open_position|buy_logic|my_buy)\s*\("),
            ),
            (
                "sell_functions",
                re.compile(r"def\s+(sell_\w+|close_position|sell_logic|my_sell)\s*\("),
            ),
            (
                "adjust_functions",
                re.compile(r"def\s+(adjust_\w+|rebalance|my_trade|handle_data)\s*\("),
            ),
        ]

        for key, pattern in func_patterns:
            for match in pattern.finditer(content):
                logic[key].append(match.group(1))

        order_methods = re.findall(
            r"(order_target_value|order_value|order|order_market|order_target)\s*\(",
            content,
        )
        logic["order_methods"] = list(set(order_methods))

        return logic

    def _extract_risk_control(self, content: str) -> Dict:
        """提取风控逻辑"""
        risk = {
            "stop_loss": False,
            "take_profit": False,
            "max_drawdown": None,
            "position_limit": None,
            "filters": [],
        }

        if re.search(r"stop_loss|止损", content):
            risk["stop_loss"] = True

        if re.search(r"take_profit|止盈", content):
            risk["take_profit"] = True

        dd_match = re.search(r"(max_drawdown|最大回撤)\s*[=:]\s*([\d.]+)", content)
        if dd_match:
            risk["max_drawdown"] = float(dd_match.group(2))

        filter_funcs = re.findall(r"def\s+(filter_\w+)\s*\(", content)
        risk["filters"] = filter_funcs

        if re.search(r"filter_st_stock|filter_paused|filter_limit", content):
            risk["filters"].append("standard_filters")

        risk["filters"] = list(set(risk["filters"]))

        return risk

    def _extract_key_snippets(self, content: str) -> Dict:
        """提取关键代码片段"""
        snippets = {}

        lines = content.split("\n")

        for i, line in enumerate(lines):
            if "def initialize" in line:
                snippets["initialize"] = self._extract_function_body(lines, i)
            elif "def handle_data" in line:
                snippets["handle_data"] = self._extract_function_body(lines, i)
            elif "def before_trading_start" in line:
                snippets["before_trading_start"] = self._extract_function_body(lines, i)
            elif "def before_market_open" in line:
                snippets["before_market_open"] = self._extract_function_body(lines, i)
            elif "def market_open" in line:
                snippets["market_open"] = self._extract_function_body(lines, i)
            elif "def after_market_close" in line:
                snippets["after_market_close"] = self._extract_function_body(lines, i)

        return snippets

    def _extract_function_body(
        self, lines: List[str], start: int, max_lines: int = 50
    ) -> str:
        """提取函数体"""
        body_lines = []
        indent_level = None

        for i in range(start, min(start + max_lines, len(lines))):
            line = lines[i]
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                body_lines.append(line)
                continue

            current_indent = len(line) - len(line.lstrip())

            if indent_level is None:
                indent_level = current_indent
                body_lines.append(line)
            elif current_indent > indent_level:
                body_lines.append(line)
            else:
                if i > start:
                    break

        return "\n".join(body_lines[:30])

    def _format_rebalance_frequency(self, frequencies: List[Dict]) -> str:
        """格式化调仓周期描述"""
        if not frequencies:
            return "unknown"

        parts = []
        for freq in frequencies:
            freq_type = freq.get("type", "daily")
            time_val = freq.get("time")
            period = freq.get("period")
            weekday = freq.get("weekday")

            desc = freq_type
            if period and period > 1:
                desc = f"every_{period}_{freq_type}s"
            if time_val:
                desc += f"@{time_val}"
            if weekday is not None:
                weekday_names = [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]
                desc += (
                    f"({weekday_names[weekday] if weekday < 7 else f'day_{weekday}'})"
                )

            parts.append(desc)

        return ", ".join(parts)

    def _make_serializable(self, obj: Any) -> Any:
        """将对象转换为 JSON 可序列化格式"""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, (datetime,)):
            return obj.isoformat()
        elif isinstance(obj, set):
            return list(obj)
        else:
            return obj

    def _extract_bt_meta(self, content: str) -> Dict:
        """提取 Backtrader 策略元数据"""
        meta = {}

        class_match = re.search(r"class\s+(\w+)\s*\(\s*bt\.Strategy", content)
        if class_match:
            meta["class_name"] = class_match.group(1)

        doc_match = re.search(r'class\s+\w+.*?"""(.*?)"""', content, re.DOTALL)
        if doc_match:
            meta["docstring"] = doc_match.group(1).strip()[:500]

        imports = re.findall(r"import\s+(\w+)|from\s+(\w+)\s+import", content)
        meta["imports"] = list(set(imp for group in imports for imp in group if imp))

        return meta

    def _extract_bt_selection_rules(self, content: str) -> List[Dict]:
        """提取 Backtrader 策略的选股逻辑"""
        rules = []

        etf_pool_match = re.search(r'"etf_pool".*?\[([^\]]+)\]', content)
        if etf_pool_match:
            pool_items = re.findall(r'"([^"]+)"', etf_pool_match.group(1))
            rules.append(
                {
                    "type": "fixed_pool",
                    "pool": pool_items,
                    "source": "params",
                }
            )

        index_match = re.search(r"get_index_stocks|get_all_securities", content)
        if index_match:
            rules.append(
                {
                    "type": "dynamic_pool",
                    "method": index_match.group(),
                }
            )

        scoring_match = re.search(r"scoring_mode.*?=\s*['\"]?(\w+\.?\w*)", content)
        if scoring_match:
            rules.append(
                {
                    "type": "scoring",
                    "mode": scoring_match.group(1),
                }
            )

        rotation_match = re.search(r"rotation_mode.*?=\s*['\"](\w+)['\"]", content)
        if rotation_match:
            rules.append(
                {
                    "type": "rotation",
                    "mode": rotation_match.group(1),
                }
            )

        if not rules:
            next_match = re.search(
                r"def\s+next\s*\(.*?\):\s*\n((?:.*\n)*?)\n\s{4}def\s+",
                content,
                re.DOTALL,
            )
            if next_match:
                rules.append(
                    {
                        "type": "custom_logic",
                        "description": "选股逻辑在 next() 方法中实现",
                    }
                )

        return rules

    def _extract_bt_rebalance_frequency(self, content: str) -> str:
        """提取 Backtrader 策略的调仓周期"""
        period_match = re.search(r"rebalance_period.*?=\s*(\d+)", content)
        if period_match:
            period = int(period_match.group(1))
            if period == 1:
                return "daily"
            return f"every_{period}_trading_days"

        schedule_matches = re.findall(
            r"self\.schedule_function.*?date_rules\.(\w+)\(\)", content
        )
        if schedule_matches:
            return f"scheduled: {', '.join(schedule_matches)}"

        if "run_daily" in content or "every_bar" in content:
            return "daily"
        if "run_weekly" in content:
            return "weekly"

        return "unknown"

    def _extract_bt_portfolio_size(self, content: str) -> int:
        """提取 Backtrader 策略的持仓数量"""
        patterns = [
            re.compile(r"stock_num.*?=\s*(\d+)"),
            re.compile(r"n_position.*?=\s*(\d+)"),
            re.compile(r"top_n.*?=\s*(\d+)"),
            re.compile(r"corr_top_n.*?=\s*(\d+)"),
        ]

        for pattern in patterns:
            match = pattern.search(content)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue

        return 0

    def _extract_bt_parameters(self, content: str) -> Dict:
        """提取 Backtrader 策略的参数配置"""
        params = {}

        tuple_match = re.search(
            r"params\s*=\s*\(\s*\n((?:.*?\n)*?)\s*\)", content, re.DOTALL
        )
        if tuple_match:
            param_text = tuple_match.group(1)
            param_matches = re.findall(r'\("(\w+)",\s*(.+?)\)', param_text)
            for name, value in param_matches:
                value = value.strip()
                if value.startswith("["):
                    items = re.findall(r'"([^"]+)"', value)
                    params[name] = items if items else value
                elif value.startswith("{"):
                    params[name] = value
                elif value.startswith("'") or value.startswith('"'):
                    params[name] = value.strip("'\"")
                elif value in ("True", "False"):
                    params[name] = value == "True"
                elif value == "None":
                    params[name] = None
                else:
                    try:
                        params[name] = int(value)
                    except ValueError:
                        try:
                            params[name] = float(value)
                        except ValueError:
                            params[name] = value

        dict_match = re.search(r"self\.params\s*=\s*\{([^}]*)\}", content, re.DOTALL)
        if dict_match:
            dict_text = dict_match.group(1)
            kv_matches = re.findall(r'"(\w+)":\s*([^,}]+)', dict_text)
            for name, value in kv_matches:
                params[name] = value.strip().strip("'\"")

        return params

    def _extract_bt_factors_and_indicators(self, content: str) -> Dict:
        """提取 Backtrader 策略使用的因子和指标"""
        result = {
            "technical_indicators": [],
            "custom_indicators": [],
            "data_sources": [],
            "ml_models": [],
        }

        bt_indicators = [
            "SMA",
            "EMA",
            "WMA",
            "RSI",
            "MACD",
            "Stochastic",
            "BollingerBands",
            "ATR",
            "CCI",
            "WilliamsR",
            "ROC",
            "Momentum",
            "UltimateOscillator",
            "ADX",
            "Ichimoku",
            "ParabolicSAR",
            "KeltnerChannels",
        ]

        for indicator in bt_indicators:
            if re.search(rf"bt\.indicators\.{indicator}|{indicator}\s*\(", content):
                result["technical_indicators"].append(indicator)

        custom_ind_matches = re.findall(
            r"def\s+(\w+_indicator|indicator_\w+|calc_\w+|compute_\w+)\s*\(", content
        )
        result["custom_indicators"] = list(set(custom_ind_matches))

        factor_engine_match = re.search(
            r"class\s+(FactorEngine|FactorCalculator)", content
        )
        if factor_engine_match:
            methods = re.findall(r"def\s+(\w+)\s*\(.*?close_prices", content)
            result["custom_indicators"].extend(methods)

        data_sources = re.findall(
            r"bt\.feeds\.(\w+)|ak\.(\w+)|get_price|get_bars", content
        )
        result["data_sources"] = list(
            set(src for group in data_sources for src in group if src)
        )

        ml_patterns = [
            re.compile(r"(LinearRegression|RandomForest|SVR|XGBoost|LightGBM|LSTM)"),
            re.compile(r"from\s+(sklearn|xgboost|lightgbm|tensorflow)"),
        ]
        for pattern in ml_patterns:
            for match in pattern.finditer(content):
                model = match.group(1) if match.lastindex else match.group(0)
                if model not in result["ml_models"]:
                    result["ml_models"].append(model)

        return result

    def _extract_bt_scoring_logic(self, content: str) -> Dict:
        """提取 Backtrader 策略的评分逻辑"""
        scoring = {
            "scorer_class": None,
            "scoring_modes": [],
            "scoring_methods": [],
        }

        scorer_match = re.search(r"class\s+(\w*Scorer\w*|RotationScorer)", content)
        if scorer_match:
            scoring["scorer_class"] = scorer_match.group(1)

        mode_matches = re.findall(r'(\w+)\s*=\s*["\'](\w+)["\']', content)
        seen_modes = set()
        for var, mode in mode_matches:
            if (
                "mode" in var.lower() or "scoring" in var.lower()
            ) and mode not in seen_modes:
                scoring["scoring_modes"].append(mode)
                seen_modes.add(mode)

        score_method_match = re.search(
            r"def\s+(score|_calc|calculate_score)\s*\(", content
        )
        if score_method_match:
            scoring["scoring_methods"].append(score_method_match.group(1))

        momentum_matches = re.findall(r"def\s+(\w*momentum\w*)\s*\(", content)
        scoring["scoring_methods"].extend(momentum_matches)

        return scoring

    def _extract_bt_allocation_logic(self, content: str) -> Dict:
        """提取 Backtrader 策略的仓位分配逻辑"""
        allocation = {
            "allocator_class": None,
            "allocation_modes": [],
            "methods": [],
        }

        allocator_match = re.search(r"class\s+(\w*Allocat\w*)", content)
        if allocator_match:
            allocation["allocator_class"] = allocator_match.group(1)

        mode_matches = re.findall(r'(\w+)\s*=\s*["\'](\w+)["\']', content)
        for var, mode in mode_matches:
            if "allocat" in var.lower() or "mode" in var.lower():
                if mode not in ["etf", "industry", "hybrid", "t0", "chase"]:
                    allocation["allocation_modes"].append(mode)

        alloc_methods = re.findall(r"def\s+(_\w+|allocate)\s*\(", content)
        allocation["methods"] = alloc_methods

        return allocation

    def _extract_bt_timing_logic(self, content: str) -> Dict:
        """提取 Backtrader 策略的择时逻辑"""
        timing = {
            "timing_engine_class": None,
            "timing_methods": [],
            "indicators": [],
        }

        timing_match = re.search(r"class\s+(\w*Timing\w*)", content)
        if timing_match:
            timing["timing_engine_class"] = timing_match.group(1)

        method_matches = re.findall(r'["\'](\w+)["\']', content)
        timing_indicators = [
            "rsrs",
            "ma_cross",
            "macd",
            "boll",
            "volume",
            "north_money",
        ]
        seen = set()
        for method in method_matches:
            if method in timing_indicators and method not in seen:
                timing["indicators"].append(method)
                seen.add(method)

        get_signal_match = re.search(
            r"def\s+(get_signal|_rsrs|_ma|_macd)\s*\(", content
        )
        if get_signal_match:
            timing["timing_methods"].append(get_signal_match.group(1))

        return timing

    def _extract_bt_risk_control(self, content: str) -> Dict:
        """提取 Backtrader 策略的风控逻辑"""
        risk = {
            "risk_control_class": None,
            "stop_loss_pct": None,
            "max_drawdown": None,
            "methods": [],
        }

        risk_match = re.search(r"class\s+(\w*Risk\w*)", content)
        if risk_match:
            risk["risk_control_class"] = risk_match.group(1)

        sl_match = re.search(r"stop_loss_pct.*?=\s*([\d.]+)", content)
        if sl_match:
            risk["stop_loss_pct"] = float(sl_match.group(1))

        dd_match = re.search(r"max_drawdown.*?=\s*([\d.]+)", content)
        if dd_match:
            risk["max_drawdown"] = float(dd_match.group(1))

        risk_methods = re.findall(
            r"def\s+(stop_loss|drawdown|momentum_change|drawdown_check)\s*\(", content
        )
        risk["methods"] = risk_methods

        return risk

    def _extract_bt_class_structure(self, content: str) -> Dict:
        """提取 Backtrader 策略的类结构"""
        structure = {
            "strategy_classes": [],
            "helper_classes": [],
            "preset_configs": [],
        }

        class_matches = re.findall(r"class\s+(\w+)(?:\s*\(\s*([^)]*)\s*\))?", content)
        for class_name, base in class_matches:
            if "Strategy" in base:
                structure["strategy_classes"].append(class_name)
            elif base:
                structure["helper_classes"].append(class_name)
            else:
                structure["helper_classes"].append(class_name)

        preset_matches = re.findall(r"class\s+(\w*Preset\w*|StrategyPresets)", content)
        structure["preset_configs"] = preset_matches

        return structure

    def _extract_bt_key_snippets(self, content: str) -> Dict:
        """提取 Backtrader 策略的关键代码片段"""
        snippets = {}

        lines = content.split("\n")

        for i, line in enumerate(lines):
            if re.search(r"class\s+\w+\(bt\.Strategy", line):
                snippets["strategy_class"] = self._extract_bt_class_body(lines, i)
            elif "def next(self)" in line or "def next(self," in line:
                snippets["next_method"] = self._extract_function_body(
                    lines, i, max_lines=80
                )
            elif "def __init__" in line and "bt.Strategy" in "\n".join(
                lines[max(0, i - 20) : i]
            ):
                snippets["strategy_init"] = self._extract_function_body(
                    lines, i, max_lines=60
                )
            elif "def notify_order" in line:
                snippets["notify_order"] = self._extract_function_body(
                    lines, i, max_lines=30
                )
            elif "def notify_trade" in line:
                snippets["notify_trade"] = self._extract_function_body(
                    lines, i, max_lines=30
                )

        return snippets

    def _extract_bt_class_body(
        self, lines: List[str], start: int, max_lines: int = 100
    ) -> str:
        """提取类体"""
        body_lines = []
        class_indent = None

        for i in range(start, min(start + max_lines, len(lines))):
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                body_lines.append(line)
                continue

            current_indent = len(line) - len(line.lstrip())

            if class_indent is None:
                class_indent = current_indent
                body_lines.append(line)
            elif current_indent > class_indent:
                body_lines.append(line)
            elif stripped.startswith("class ") and i > start:
                break

        return "\n".join(body_lines[:80])
