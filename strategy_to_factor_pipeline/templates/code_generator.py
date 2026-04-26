# -*- coding: utf-8 -*-
"""
策略转因子代码生成器
====================
根据解析后的策略规则，生成可独立运行的因子计算 Python 脚本。

功能：
1. 为每个策略生成独立的因子计算代码
2. 支持批量生成所有策略的代码
3. 生成的代码包含完整的注释和说明
4. 支持数据加载、信号计算、结果保存

使用示例：
    from code_generator import CodeGenerator

    generator = CodeGenerator(
        template_dir="templates",
        output_dir="output/strategies",
    )

    # 生成单个策略
    generator.generate_strategy_code(
        strategy_name="小市值策略",
        parsed_rules={"universe": "399101.XSHE", "factors": ["circulating_market_cap"]},
        output_path="output/strategies/small_cap.py",
    )

    # 批量生成
    strategy_list = [
        {"name": "小市值策略", "file": "15 小市值策略.txt"},
        {"name": "红利策略", "file": "04 红利搬砖.txt"},
    ]
    generator.generate_all_strategy_codes(strategy_list, parsed_results, "output/strategies")
"""

import os
import re
import ast
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("CodeGenerator")


# ============================================================
# 代码生成器
# ============================================================
class CodeGenerator:
    """
    策略转因子代码生成器

    根据解析后的策略规则，生成可独立运行的因子计算脚本。
    """

    def __init__(self, template_dir: str, output_dir: str):
        """
        初始化代码生成器

        Args:
            template_dir: 模板文件目录路径
            output_dir: 生成代码的输出目录路径
        """
        self.template_dir = Path(template_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._template_cache = {}
        self._generation_log = []

        logger.info(f"代码生成器初始化完成")
        logger.info(f"  模板目录: {self.template_dir}")
        logger.info(f"  输出目录: {self.output_dir}")

    # ============================================================
    # 模板加载
    # ============================================================
    def load_template(self, template_name: str) -> str:
        """
        加载模板文件

        Args:
            template_name: 模板文件名（不含路径）

        Returns:
            模板文件内容字符串

        Raises:
            FileNotFoundError: 模板文件不存在
        """
        if template_name in self._template_cache:
            return self._template_cache[template_name]

        template_path = self.template_dir / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        self._template_cache[template_name] = content
        logger.debug(f"加载模板: {template_name}")
        return content

    # ============================================================
    # 模板填充
    # ============================================================
    def fill_template(self, template: str, strategy_info: Dict, rules: Dict) -> str:
        """
        填充模板占位符

        Args:
            template: 模板内容字符串
            strategy_info: 策略基本信息
                - name: 策略名称
                - desc: 策略描述
                - source_file: 源文件路径
            rules: 解析后的策略规则
                - data_source: 数据源 jqdata/akshare
                - output_format: 输出格式 parquet/csv
                - start_date: 开始日期
                - end_date: 结束日期
                - universe: 股票池
                - factors: 因子列表
                - filter_conditions: 过滤条件
                - scoring_logic: 评分逻辑
                - signal_generation: 信号生成逻辑

        Returns:
            填充后的代码字符串
        """
        code = template

        # 基本信息替换
        replacements = {
            "{{STRATEGY_NAME}}": strategy_info.get("name", "unknown_strategy"),
            "{{STRATEGY_DESC}}": strategy_info.get("desc", ""),
            "{{DATA_SOURCE}}": rules.get("data_source", "jqdata"),
            "{{OUTPUT_FORMAT}}": rules.get("output_format", "parquet"),
            "{{OUTPUT_PATH}}": rules.get("output_path", "output/factor_signal"),
            "{{START_DATE}}": rules.get("start_date", "2018-01-01"),
            "{{END_DATE}}": rules.get("end_date", "2024-12-31"),
            "{{UNIVERSE}}": rules.get("universe", "all"),
            "{{FACTOR_COLUMNS}}": ", ".join(rules.get("factors", [])),
        }

        for placeholder, value in replacements.items():
            code = code.replace(placeholder, str(value))

        # 代码块替换（需要特殊处理）
        code = self._fill_filter_conditions(code, rules)
        code = self._fill_scoring_logic(code, rules)
        code = self._fill_signal_generation(code, rules)

        return code

    def _fill_filter_conditions(self, code: str, rules: Dict) -> str:
        """填充过滤条件代码块"""
        filter_conditions = rules.get("filter_conditions", [])

        if not filter_conditions:
            filter_code = self._generate_default_filters(rules)
        else:
            filter_code = self._generate_filter_code(filter_conditions, rules)

        return code.replace("{{FILTER_CONDITIONS}}", filter_code)

    def _fill_scoring_logic(self, code: str, rules: Dict) -> str:
        """填充评分逻辑代码块"""
        scoring_logic = rules.get("scoring_logic", [])
        factors = rules.get("factors", [])

        if not scoring_logic and not factors:
            scoring_code = self._generate_default_scoring(rules)
        else:
            scoring_code = self._generate_scoring_code(scoring_logic, factors, rules)

        return code.replace("{{SCORING_LOGIC}}", scoring_code)

    def _fill_signal_generation(self, code: str, rules: Dict) -> str:
        """填充信号生成代码块"""
        signal_rules = rules.get("signal_generation", [])

        if not signal_rules:
            signal_code = self._generate_default_signal(rules)
        else:
            signal_code = self._generate_signal_code(signal_rules, rules)

        return code.replace("{{SIGNAL_GENERATION}}", signal_code)

    # ============================================================
    # 默认代码生成
    # ============================================================
    def _generate_default_filters(self, rules: Dict) -> str:
        """生成默认过滤条件代码"""
        return """        # 默认过滤条件已应用
        # - 停牌过滤（成交量为0）
        # - 涨跌停过滤（最高价等于最低价）
        #
        # 如需添加更多过滤条件，请在下方添加代码：
        # 示例：过滤市值小于10亿的股票
        # if fundamental_data is not None and not fundamental_data.empty:
        #     val_df = fundamental_data[fundamental_data["code"] == stock]
        #     if not val_df.empty:
        #         mcap = val_df.iloc[-1].get("market_cap", 0)
        #         if mcap < 10:
        #             continue
        pass"""

    def _generate_default_scoring(self, rules: Dict) -> str:
        """生成默认评分逻辑代码"""
        return """            # 默认评分逻辑
            # 基于技术指标计算综合评分
            score = 0.0

            # 均线多头排列加分
            if df["ma5"].iloc[-1] > df["ma10"].iloc[-1] > df["ma20"].iloc[-1"]:
                score += 1.0

            # 动量为正加分
            if df["momentum_20"].iloc[-1] > 0:
                score += 1.0

            # RSI 适中加分（30-70之间）
            rsi_val = df["rsi_14"].iloc[-1]
            if 30 < rsi_val < 70:
                score += 0.5

            df["factor_score"] = score"""

    def _generate_default_signal(self, rules: Dict) -> str:
        """生成默认信号生成代码"""
        return """        # 默认信号生成逻辑
        # factor_signal: 1=买入信号, 0=观望, -1=卖出信号
        if "factor_score" in df.columns:
            # 根据评分生成信号
            df["factor_signal"] = pd.cut(
                df["factor_score"],
                bins=[-float("inf"), 0.5, 1.5, float("inf")],
                labels=[-1, 0, 1],
            ).astype(int)
        else:
            df["factor_signal"] = 0"""

    def _generate_filter_code(self, conditions: List, rules: Dict) -> str:
        """根据解析的过滤条件生成代码"""
        lines = ["        # 策略特定过滤条件"]

        for cond in conditions:
            if isinstance(cond, dict):
                cond_type = cond.get("type", "")
                if cond_type == "market_cap":
                    min_cap = cond.get("min", 0)
                    max_cap = cond.get("max", float("inf"))
                    lines.append(f"        # 市值过滤: {min_cap} ~ {max_cap} 亿")
                    lines.append(f"        # 需要结合财务数据实现")
                elif cond_type == "pe_ratio":
                    min_pe = cond.get("min", 0)
                    max_pe = cond.get("max", float("inf"))
                    lines.append(f"        # PE过滤: {min_pe} ~ {max_pe}")
                elif cond_type == "not_st":
                    lines.append("        # ST过滤（需要额外数据源）")
                elif cond_type == "not_new":
                    days = cond.get("days", 60)
                    lines.append(f"        # 新股过滤（上市不足{days}天）")

        if len(lines) == 1:
            lines.append("        pass")

        return "\n".join(lines)

    def _generate_scoring_code(
        self, scoring_logic: List, factors: List, rules: Dict
    ) -> str:
        """根据解析的评分逻辑生成代码"""
        lines = ["            # 策略特定评分/选股逻辑"]
        lines.append("            score = 0.0")

        # 根据因子类型生成评分代码
        for factor in factors:
            factor_lower = factor.lower()

            if "market_cap" in factor_lower or "市值" in factor:
                lines.append("            # 市值因子（越小越好）")
                lines.append(
                    "            if 'money' in df.columns and df['money'].iloc[-1] > 0:"
                )
                lines.append(
                    "                score += 1.0 / (df['money'].iloc[-1] / 1e8 + 1)"
                )

            elif "pe" in factor_lower or "市盈" in factor:
                lines.append("            # PE因子（越低越好）")
                lines.append("            # 需要财务数据支持")

            elif "pb" in factor_lower or "市净" in factor:
                lines.append("            # PB因子（越低越好）")
                lines.append("            # 需要财务数据支持")

            elif "roe" in factor_lower:
                lines.append("            # ROE因子（越高越好）")
                lines.append("            # 需要财务数据支持")

            elif "momentum" in factor_lower or "动量" in factor:
                lines.append("            # 动量因子")
                lines.append("            if 'momentum_20' in df.columns:")
                lines.append("                score += df['momentum_20'].iloc[-1]")

            elif "volatility" in factor_lower or "波动" in factor:
                lines.append("            # 低波动因子")
                lines.append("            if 'volatility_20' in df.columns:")
                lines.append("                score -= df['volatility_20'].iloc[-1]")

            elif "dividend" in factor_lower or "股息" in factor or "红利" in factor:
                lines.append("            # 股息率因子（越高越好）")
                lines.append("            # 需要财务数据支持")

        lines.append("")
        lines.append("            df['factor_score'] = score")

        return "\n".join(lines)

    def _generate_signal_code(self, signal_rules: List, rules: Dict) -> str:
        """根据解析的信号规则生成代码"""
        lines = ["        # 策略特定信号生成逻辑"]

        strategy_type = rules.get("strategy_type", "factor_rank")

        if strategy_type == "factor_rank":
            top_n = rules.get("top_n", 10)
            lines.append(f"        # 按因子评分排序，选取前{top_n}只股票")
            lines.append("        if 'factor_score' in df.columns:")
            lines.append("            df['factor_signal'] = 0")
            lines.append(f"            # 这里需要在外部聚合后选取top{top_n}")
            lines.append("            # 本脚本输出所有股票的评分，由调用方选取")
        elif strategy_type == "threshold":
            threshold = rules.get("threshold", 0)
            lines.append(f"        # 信号阈值: factor_score > {threshold}")
            lines.append("        if 'factor_score' in df.columns:")
            lines.append(
                f"            df['factor_signal'] = (df['factor_score'] > {threshold}).astype(int)"
            )
        elif strategy_type == "cross":
            lines.append("        # 均线交叉信号")
            lines.append("        if 'ma5' in df.columns and 'ma10' in df.columns:")
            lines.append("            df['factor_signal'] = 0")
            lines.append(
                "            df.loc[df['ma5'] > df['ma10'], 'factor_signal'] = 1"
            )
            lines.append(
                "            df.loc[df['ma5'] < df['ma10'], 'factor_signal'] = -1"
            )
        else:
            lines.append("        # 使用默认信号生成逻辑")
            lines.append("        pass")

        return "\n".join(lines)

    # ============================================================
    # 单个策略代码生成
    # ============================================================
    def generate_strategy_code(
        self,
        strategy_name: str,
        parsed_rules: Dict,
        output_path: str = None,
    ) -> str:
        """
        为单个策略生成因子计算代码

        Args:
            strategy_name: 策略名称
            parsed_rules: 解析后的策略规则字典
                必需字段：
                - data_source: 数据源 jqdata/akshare
                - universe: 股票池
                可选字段：
                - output_format: 输出格式 parquet/csv
                - output_path: 输出路径
                - start_date: 开始日期
                - end_date: 结束日期
                - factors: 因子列表
                - filter_conditions: 过滤条件列表
                - scoring_logic: 评分逻辑列表
                - signal_generation: 信号生成规则列表
                - strategy_type: 策略类型 factor_rank/threshold/cross
                - top_n: 选取股票数量
                - threshold: 信号阈值
            output_path: 输出文件路径（可选，默认使用规则中的路径或自动生成）

        Returns:
            生成的代码文件路径
        """
        # 确定输出路径
        if output_path is None:
            output_path = parsed_rules.get("output_path")

        if output_path is None:
            safe_name = re.sub(r"[^\w\s-]", "", strategy_name).strip()
            safe_name = re.sub(r"[-\s]+", "_", safe_name)
            output_path = str(self.output_dir / f"{safe_name}.py")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 加载模板
        template = self.load_template("strategy_template.py")

        # 构建策略信息
        strategy_info = {
            "name": strategy_name,
            "desc": parsed_rules.get("description", f"策略: {strategy_name}"),
            "source_file": parsed_rules.get("source_file", ""),
        }

        # 确保规则中有必要的默认值
        rules = {
            "data_source": parsed_rules.get("data_source", "jqdata"),
            "output_format": parsed_rules.get("output_format", "parquet"),
            "output_path": str(output_path).replace(".py", "_signal"),
            "start_date": parsed_rules.get("start_date", "2018-01-01"),
            "end_date": parsed_rules.get("end_date", "2024-12-31"),
            "universe": parsed_rules.get("universe", "all"),
            "factors": parsed_rules.get("factors", []),
            "filter_conditions": parsed_rules.get("filter_conditions", []),
            "scoring_logic": parsed_rules.get("scoring_logic", []),
            "signal_generation": parsed_rules.get("signal_generation", []),
            "strategy_type": parsed_rules.get("strategy_type", "factor_rank"),
            "top_n": parsed_rules.get("top_n", 10),
            "threshold": parsed_rules.get("threshold", 0),
        }

        # 填充模板
        code = self.fill_template(template, strategy_info, rules)

        # 添加生成信息注释
        header = f"""# ============================================================
# 自动生成代码 - 请勿手动编辑
# ============================================================
# 策略名称: {strategy_name}
# 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# 数据源: {rules["data_source"]}
# 股票池: {rules["universe"]}
# 日期范围: {rules["start_date"]} ~ {rules["end_date"]}
# 输出格式: {rules["output_format"]}
# ============================================================

"""
        code = header + code

        # 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(code)

        # 记录生成日志
        log_entry = {
            "strategy": strategy_name,
            "output_path": str(output_path),
            "timestamp": datetime.now().isoformat(),
            "rules_summary": {
                "data_source": rules["data_source"],
                "universe": rules["universe"],
                "factors_count": len(rules["factors"]),
            },
        }
        self._generation_log.append(log_entry)

        logger.info(f"策略代码已生成: {output_path}")
        return str(output_path)

    # ============================================================
    # 批量策略代码生成
    # ============================================================
    def generate_all_strategy_codes(
        self,
        strategy_list: List[Dict],
        parsed_results: Dict[str, Dict],
        output_dir: str = None,
    ) -> List[str]:
        """
        批量生成所有策略的代码

        Args:
            strategy_list: 策略列表，每个元素为字典
                - name: 策略名称
                - file: 源文件路径（可选）
            parsed_results: 解析结果字典
                key 为策略名称，value 为解析后的规则字典
            output_dir: 输出目录（可选，默认使用初始化时的 output_dir）

        Returns:
            生成的代码文件路径列表
        """
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = self.output_dir

        generated_files = []
        total = len(strategy_list)

        logger.info(f"开始批量生成 {total} 个策略的代码")
        logger.info(f"输出目录: {output_dir}")

        for i, strategy in enumerate(strategy_list, 1):
            name = strategy.get("name", f"strategy_{i}")
            source_file = strategy.get("file", "")

            # 获取解析结果
            parsed_rules = parsed_results.get(name, {})
            if source_file:
                parsed_rules["source_file"] = source_file

            # 生成输出路径
            safe_name = re.sub(r"[^\w\s-]", "", name).strip()
            safe_name = re.sub(r"[-\s]+", "_", safe_name)
            output_path = str(output_dir / f"{safe_name}.py")

            try:
                file_path = self.generate_strategy_code(
                    strategy_name=name,
                    parsed_rules=parsed_rules,
                    output_path=output_path,
                )
                generated_files.append(file_path)
                logger.info(f"[{i}/{total}] 生成成功: {name}")
            except Exception as e:
                logger.error(f"[{i}/{total}] 生成失败: {name} - {e}")

        logger.info(f"批量生成完成: {len(generated_files)}/{total} 个策略")
        return generated_files

    # ============================================================
    # 代码验证
    # ============================================================
    def validate_generated_code(self, code: str) -> bool:
        """
        验证生成的代码是否合法

        检查项：
        1. Python 语法是否正确
        2. 是否还有未替换的占位符
        3. 是否包含必要的类和函数

        Args:
            code: 生成的代码字符串

        Returns:
            True 表示验证通过，False 表示验证失败
        """
        errors = []

        # 1. 检查语法
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"语法错误: 第 {e.lineno} 行 - {e.msg}")

        # 2. 检查未替换的占位符
        placeholder_pattern = r"\{\{[A-Z_]+\}\}"
        placeholders = re.findall(placeholder_pattern, code)
        if placeholders:
            errors.append(f"存在未替换的占位符: {placeholders}")

        # 3. 检查必要的类
        required_classes = ["DataLoader", "FactorEngine", "ResultSaver"]
        for cls in required_classes:
            if f"class {cls}" not in code:
                errors.append(f"缺少必要的类: {cls}")

        # 4. 检查必要的函数
        required_functions = ["def main"]
        for func in required_functions:
            if func not in code:
                errors.append(f"缺少必要的函数: {func}")

        # 5. 检查必要的导入
        required_imports = ["pandas", "numpy"]
        for imp in required_imports:
            if imp not in code:
                errors.append(f"缺少必要的导入: {imp}")

        if errors:
            logger.warning(f"代码验证失败:")
            for err in errors:
                logger.warning(f"  - {err}")
            return False

        logger.debug("代码验证通过")
        return True

    # ============================================================
    # 批量运行脚本生成
    # ============================================================
    def generate_batch_script(self, strategy_list: List[Dict], output_path: str) -> str:
        """
        生成批量运行脚本

        生成一个可以批量运行所有策略因子计算脚本的入口脚本。

        Args:
            strategy_list: 策略列表，每个元素为字典
                - name: 策略名称
                - file: 生成的脚本文件路径
            output_path: 批量运行脚本的输出路径

        Returns:
            批量运行脚本的文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 生成策略运行列表
        strategy_entries = []
        for strategy in strategy_list:
            name = strategy.get("name", "unknown")
            file_path = strategy.get("file", "")
            safe_name = re.sub(r"[^\w\s-]", "", name).strip()
            safe_name = re.sub(r"[-\s]+", "_", safe_name)
            strategy_entries.append(
                {
                    "name": name,
                    "file": f"{safe_name}.py",
                }
            )

        # 生成批量运行脚本
        batch_code = self._generate_batch_code(strategy_entries)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(batch_code)

        logger.info(f"批量运行脚本已生成: {output_path}")
        return str(output_path)

    def _generate_batch_code(self, strategies: List[Dict]) -> str:
        """生成批量运行脚本代码"""
        strategy_list_str = json.dumps(strategies, ensure_ascii=False, indent=4)

        batch_code = '''# -*- coding: utf-8 -*-
"""
批量运行策略因子计算脚本
========================
自动生成，请勿手动编辑

功能：
1. 按顺序运行所有策略的因子计算脚本
2. 记录运行结果和耗时
3. 支持失败重试
4. 生成运行报告

使用方法：
    python run_all_factors.py

    # 指定并发数
    python run_all_factors.py --workers 4

    # 指定日志级别
    python run_all_factors.py --log-level DEBUG
"""

import os
import sys
import time
import json
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# 配置
# ============================================================
STRATEGIES = __STRATEGY_LIST_PLACEHOLDER__

SCRIPT_DIR = Path(__file__).parent
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            LOG_DIR / ("batch_run_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("BatchRunner")


# ============================================================
# 批量运行器
# ============================================================
class BatchRunner:
    """批量运行策略因子计算脚本"""

    def __init__(self, strategies: List[Dict], max_workers: int = 1):
        self.strategies = strategies
        self.max_workers = max_workers
        self.results = []

    def run_single(self, strategy: Dict) -> Dict:
        """运行单个策略脚本"""
        name = strategy["name"]
        script_file = SCRIPT_DIR / strategy["file"]

        result = {
            "name": name,
            "file": strategy["file"],
            "success": False,
            "duration": 0,
            "error": None,
        }

        if not script_file.exists():
            result["error"] = "脚本文件不存在: " + str(script_file)
            logger.error("[" + name + "] " + result["error"])
            return result

        logger.info("[" + name + "] 开始运行: " + str(script_file))
        start_time = time.time()

        try:
            proc = subprocess.run(
                [sys.executable, str(script_file)],
                cwd=str(SCRIPT_DIR),
                capture_output=True,
                text=True,
                timeout=3600,
            )

            result["duration"] = time.time() - start_time
            result["success"] = proc.returncode == 0

            if proc.returncode != 0:
                result["error"] = proc.stderr[-500:] if proc.stderr else "未知错误"
                logger.error(
                    "[" + name + "] 运行失败 (" + str(round(result["duration"], 1)) + "s): "
                    + result["error"][:100]
                )
            else:
                logger.info("[" + name + "] 运行成功 (" + str(round(result["duration"], 1)) + "s)")

        except subprocess.TimeoutExpired:
            result["error"] = "运行超时 (3600s)"
            result["duration"] = time.time() - start_time
            logger.error("[" + name + "] " + result["error"])
        except Exception as e:
            result["error"] = str(e)
            result["duration"] = time.time() - start_time
            logger.error("[" + name + "] 运行异常: " + str(e))

        return result

    def run_all(self) -> List[Dict]:
        """运行所有策略"""
        total = len(self.strategies)
        logger.info("=" * 60)
        logger.info("批量运行策略因子计算")
        logger.info("策略数量: " + str(total))
        logger.info("并发数: " + str(self.max_workers))
        logger.info("=" * 60)

        overall_start = time.time()

        if self.max_workers > 1:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.run_single, s): s["name"]
                    for s in self.strategies
                }
                for future in as_completed(futures):
                    result = future.result()
                    self.results.append(result)
        else:
            for i, strategy in enumerate(self.strategies, 1):
                logger.info("[" + str(i) + "/" + str(total) + "] ", end="")
                result = self.run_single(strategy)
                self.results.append(result)

        overall_duration = time.time() - overall_start
        self._generate_report(overall_duration)

        return self.results

    def _generate_report(self, total_duration: float):
        """生成运行报告"""
        success_count = sum(1 for r in self.results if r["success"])
        fail_count = len(self.results) - success_count

        report_path = LOG_DIR / ("report_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")

        report = {
            "timestamp": datetime.now().isoformat(),
            "total_strategies": len(self.results),
            "success_count": success_count,
            "fail_count": fail_count,
            "total_duration": round(total_duration, 2),
            "results": self.results,
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info("=" * 60)
        logger.info("批量运行完成")
        logger.info("成功: " + str(success_count) + "/" + str(len(self.results)))
        logger.info("失败: " + str(fail_count))
        logger.info("总耗时: " + str(round(total_duration, 1)) + "s")
        logger.info("报告已保存至: " + str(report_path))
        logger.info("=" * 60)

        if fail_count > 0:
            logger.warning("失败的策略:")
            for r in self.results:
                if not r["success"]:
                    logger.warning("  - " + r["name"] + ": " + r.get("error", "未知错误"))


# ============================================================
# 主函数
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="批量运行策略因子计算脚本")
    parser.add_argument("--workers", type=int, default=1, help="并发数（默认1）")
    parser.add_argument("--log-level", default="INFO", help="日志级别")
    args = parser.parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log_level.upper(), logging.INFO))

    runner = BatchRunner(STRATEGIES, max_workers=args.workers)
    runner.run_all()


if __name__ == "__main__":
    main()
'''

        batch_code = batch_code.replace(
            "__STRATEGY_LIST_PLACEHOLDER__", strategy_list_str
        )
        return batch_code

    # ============================================================
    # 生成报告
    # ============================================================
    def get_generation_report(self) -> Dict:
        """
        获取代码生成报告

        Returns:
            包含生成统计信息的字典
        """
        return {
            "total_generated": len(self._generation_log),
            "generation_log": self._generation_log,
            "template_dir": str(self.template_dir),
            "output_dir": str(self.output_dir),
        }

    def save_generation_report(self, output_path: str = None) -> str:
        """
        保存代码生成报告

        Args:
            output_path: 报告输出路径

        Returns:
            报告文件路径
        """
        if output_path is None:
            output_path = str(self.output_dir / "generation_report.json")

        report = self.get_generation_report()
        report["generated_at"] = datetime.now().isoformat()

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"生成报告已保存: {output_path}")
        return output_path


# ============================================================
# 命令行入口
# ============================================================
def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="策略转因子代码生成器")
    parser.add_argument("--template-dir", default="templates", help="模板目录")
    parser.add_argument("--output-dir", default="output/strategies", help="输出目录")
    parser.add_argument("--config", help="策略配置文件（JSON）")
    parser.add_argument("--batch-script", help="批量运行脚本输出路径")
    args = parser.parse_args()

    generator = CodeGenerator(
        template_dir=args.template_dir,
        output_dir=args.output_dir,
    )

    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)

        strategy_list = config.get("strategies", [])
        parsed_results = config.get("parsed_results", {})

        generated_files = generator.generate_all_strategy_codes(
            strategy_list=strategy_list,
            parsed_results=parsed_results,
        )

        if args.batch_script:
            strategy_entries = [
                {"name": s.get("name", ""), "file": f}
                for s, f in zip(strategy_list, generated_files)
            ]
            generator.generate_batch_script(strategy_entries, args.batch_script)

        generator.save_generation_report()

    print(f"代码生成完成，输出目录: {args.output_dir}")


if __name__ == "__main__":
    main()
