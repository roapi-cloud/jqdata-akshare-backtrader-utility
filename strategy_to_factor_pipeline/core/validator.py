"""因子质量验证模块。

提供因子信号的质量检查、有效性分析和验证报告生成功能。
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import os
import warnings

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class FactorValidator:
    """因子质量验证器。

    对因子信号进行全面的质量检查，包括覆盖率、分布、稳定性、缺失值等，
    并评估因子的有效性（相关性、周期性、趋势），最终生成验证报告。

    Args:
        factor_database: FactorDatabase 实例，用于加载因子信号数据。

    Example:
        >>> db = FactorDatabase("metadata.db", "data/")
        >>> validator = FactorValidator(db)
        >>> report = validator.validate_factor("momentum_20d")
        >>> all_report = validator.validate_all_factors()
    """

    def __init__(self, factor_database: Any):
        self.factor_database = factor_database
        self._cache: Dict[str, pd.DataFrame] = {}
        self._validation_cache: Dict[str, Dict] = {}

    def _load_factor_data(self, factor_name: str) -> pd.DataFrame:
        """加载因子信号数据。

        Args:
            factor_name: 因子名称。

        Returns:
            因子数据 DataFrame，包含 date, stock_code, signal 列。

        Raises:
            KeyError: 因子不存在。
            ValueError: 因子数据格式不正确。
        """
        if factor_name in self._cache:
            return self._cache[factor_name]

        try:
            if hasattr(self.factor_database, "load_factor_signals"):
                data = self.factor_database.load_factor_signals(factor_name)
            elif isinstance(self.factor_database, dict):
                data = self.factor_database.get(factor_name)
                if data is None:
                    raise KeyError(f"因子 '{factor_name}' 不存在于数据库中")
            else:
                raise ValueError("factor_database 必须是 FactorDatabase 实例或 dict")
        except FileNotFoundError:
            raise KeyError(f"因子 '{factor_name}' 的数据文件不存在")

        if data is None or (isinstance(data, pd.DataFrame) and data.empty):
            raise ValueError(f"因子 '{factor_name}' 的数据为空")

        if not isinstance(data, pd.DataFrame):
            raise ValueError(f"因子 '{factor_name}' 的数据必须是 DataFrame")

        required = {"date", "stock_code", "signal"}
        if not required.issubset(data.columns):
            raise ValueError(
                f"因子 '{factor_name}' 缺少必要列: {required - set(data.columns)}"
            )

        data = data.copy()
        data["date"] = pd.to_datetime(data["date"])
        data = data.sort_values(["date", "stock_code"]).reset_index(drop=True)

        self._cache[factor_name] = data
        return data

    def _get_pivot_table(self, factor_name: str) -> pd.DataFrame:
        """获取因子透视表（日期 x 股票）。

        Args:
            factor_name: 因子名称。

        Returns:
            透视表 DataFrame，行为日期，列为股票，值为 signal。
        """
        data = self._load_factor_data(factor_name)
        pivot = data.pivot_table(index="date", columns="stock_code", values="signal")
        return pivot

    def _get_all_factor_names(self) -> List[str]:
        """获取数据库中所有因子名称。

        Returns:
            因子名称列表。
        """
        if isinstance(self.factor_database, dict):
            return list(self.factor_database.keys())
        elif hasattr(self.factor_database, "list_all_factors"):
            factors = self.factor_database.list_all_factors()
            return [f["factor_name"] for f in factors]
        else:
            raise ValueError("无法获取因子名称列表")

    def check_signal_coverage(self, factor_name: str) -> float:
        """检查信号覆盖率。

        计算有多少日期/股票组合有非空信号。

        Args:
            factor_name: 因子名称。

        Returns:
            覆盖率，范围 [0, 1]。
        """
        pivot = self._get_pivot_table(factor_name)
        total_cells = pivot.size
        if total_cells == 0:
            return 0.0
        valid_cells = int(pivot.notna().sum().sum())
        return float(valid_cells / total_cells)

    def check_signal_distribution(self, factor_name: str) -> Dict[str, Any]:
        """检查信号分布。

        对于二值信号，计算 0/1 的比例；对于连续信号，计算分位数统计。

        Args:
            factor_name: 因子名称。

        Returns:
            分布统计字典。
        """
        data = self._load_factor_data(factor_name)
        values = data["signal"].dropna()

        if len(values) == 0:
            return {"type": "unknown", "count": 0}

        unique_values = set(values.unique())
        is_binary = unique_values.issubset({0, 1, 0.0, 1.0}) or len(unique_values) <= 2

        result: Dict[str, Any] = {"count": len(values)}

        if is_binary:
            result["type"] = "binary"
            zero_count = int((values == 0).sum())
            one_count = int((values == 1).sum())
            total = zero_count + one_count
            result["zero_ratio"] = float(zero_count / total) if total > 0 else 0.0
            result["one_ratio"] = float(one_count / total) if total > 0 else 0.0
            result["imbalance"] = abs(result["zero_ratio"] - result["one_ratio"])
        else:
            result["type"] = "continuous"
            result["mean"] = float(values.mean())
            result["std"] = float(values.std())
            result["skewness"] = float(stats.skew(values))
            result["kurtosis"] = float(stats.kurtosis(values))
            result["min"] = float(values.min())
            result["max"] = float(values.max())
            percentiles = values.quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
            result["percentiles"] = {str(k): float(v) for k, v in percentiles.items()}

        return result

    def check_signal_stability(self, factor_name: str) -> float:
        """检查信号稳定性。

        计算相邻日期之间信号变化的比例。值越低表示信号越稳定。

        Args:
            factor_name: 因子名称。

        Returns:
            不稳定性指标，范围 [0, 1]。值越小表示信号越稳定。
        """
        pivot = self._get_pivot_table(factor_name)
        pivot = pivot.sort_index()

        if len(pivot) < 2:
            return 0.0

        diff = pivot.diff().iloc[1:]
        total_comparable = int(diff.notna().sum().sum())
        if total_comparable == 0:
            return 0.0

        changed = int((diff.abs() > 1e-10).sum().sum())
        return float(changed / total_comparable)

    def check_missing_values(self, factor_name: str) -> int:
        """检查缺失值数量。

        Args:
            factor_name: 因子名称。

        Returns:
            缺失值总数。
        """
        data = self._load_factor_data(factor_name)
        return int(data["signal"].isna().sum())

    def check_signal_correlation(self, factor_name: str) -> Dict[str, Any]:
        """检查信号与股票特征的相关性。

        计算因子值的横截面自相关性和离散程度。

        Args:
            factor_name: 因子名称。

        Returns:
            相关性分析结果字典。
        """
        pivot = self._get_pivot_table(factor_name)
        result: Dict[str, Any] = {}

        cross_sectional_means = pivot.mean(axis=1).dropna()
        if len(cross_sectional_means) < 10:
            result["warning"] = "数据量不足，无法计算相关性"
            return result

        result["autocorrelation_lag1"] = float(
            cross_sectional_means.autocorr(lag=1)
            if len(cross_sectional_means) > 1
            else 0.0
        )
        result["autocorrelation_lag5"] = float(
            cross_sectional_means.autocorr(lag=5)
            if len(cross_sectional_means) > 5
            else 0.0
        )
        result["autocorrelation_lag20"] = float(
            cross_sectional_means.autocorr(lag=20)
            if len(cross_sectional_means) > 20
            else 0.0
        )

        daily_std = pivot.std(axis=1).dropna()
        valid_mask = daily_std.index.intersection(cross_sectional_means.index)
        if len(valid_mask) > 10:
            corr, p_value = stats.pearsonr(
                cross_sectional_means.loc[valid_mask], daily_std.loc[valid_mask]
            )
            result["mean_std_correlation"] = float(corr)
            result["mean_std_pvalue"] = float(p_value)

        cross_sectional_std = pivot.std().dropna()
        if len(cross_sectional_std) > 0:
            result["cross_sectional_dispersion_mean"] = float(
                cross_sectional_std.mean()
            )
            result["cross_sectional_dispersion_std"] = float(cross_sectional_std.std())

        return result

    def check_signal_periodicity(self, factor_name: str) -> Dict[str, Any]:
        """检查信号的周期性。

        使用自相关函数检测信号是否存在明显的周期性模式。

        Args:
            factor_name: 因子名称。

        Returns:
            周期性分析结果字典。
        """
        pivot = self._get_pivot_table(factor_name)
        cross_sectional_mean = pivot.mean(axis=1).dropna()

        result: Dict[str, Any] = {"has_periodicity": False}

        if len(cross_sectional_mean) < 30:
            result["warning"] = "数据量不足，无法检测周期性"
            result["max_autocorrelation"] = 0.0
            return result

        max_lag = min(len(cross_sectional_mean) // 2, 60)
        acf_values = []
        for lag in range(1, max_lag + 1):
            acf = cross_sectional_mean.autocorr(lag=lag)
            acf_values.append(acf)

        acf_series = pd.Series(acf_values, index=range(1, max_lag + 1))
        max_acf_idx = int(acf_series.idxmax())
        max_acf_val = float(acf_series.max())

        result["max_autocorrelation"] = max_acf_val
        result["max_autocorrelation_lag"] = max_acf_idx

        threshold = 2.0 / np.sqrt(len(cross_sectional_mean))
        significant_peaks = acf_series[acf_series > threshold]
        result["significant_peaks"] = significant_peaks.index.tolist()

        if len(significant_peaks) >= 2:
            result["has_periodicity"] = True
            peak_diffs = significant_peaks.index.diff().dropna()
            if len(peak_diffs) > 0:
                result["dominant_period"] = int(round(float(peak_diffs.mean())))

        return result

    def check_signal_trend(self, factor_name: str) -> Dict[str, Any]:
        """检查信号是否存在趋势。

        使用线性回归检测信号的趋势性。

        Args:
            factor_name: 因子名称。

        Returns:
            趋势分析结果字典。
        """
        pivot = self._get_pivot_table(factor_name)
        cross_sectional_mean = pivot.mean(axis=1).dropna()

        result: Dict[str, Any] = {"has_trend": False, "trend_direction": "none"}

        if len(cross_sectional_mean) < 10:
            result["warning"] = "数据量不足，无法检测趋势"
            return result

        x = np.arange(len(cross_sectional_mean))
        y = cross_sectional_mean.values

        valid_mask = np.isfinite(y)
        if valid_mask.sum() < 10:
            result["warning"] = "有效数据点不足"
            return result

        x_valid = x[valid_mask]
        y_valid = y[valid_mask]

        slope, intercept, r_value, p_value, std_err = stats.linregress(x_valid, y_valid)

        result["slope"] = float(slope)
        result["r_squared"] = float(r_value**2)
        result["p_value"] = float(p_value)
        result["std_err"] = float(std_err)

        if p_value < 0.05:
            result["has_trend"] = True
            result["trend_direction"] = "up" if slope > 0 else "down"

        y_std = float(y_valid.std())
        if y_std > 0:
            result["normalized_slope"] = float(slope / y_std)

        return result

    def calculate_quality_score(self, factor_name: str) -> float:
        """计算因子质量综合评分。

        基于覆盖率、分布均衡性、稳定性、缺失值等多个维度计算综合评分。

        Args:
            factor_name: 因子名称。

        Returns:
            质量评分，范围 [0, 1]。分数越高表示因子质量越好。
        """
        coverage = self.check_signal_coverage(factor_name)
        distribution = self.check_signal_distribution(factor_name)
        instability = self.check_signal_stability(factor_name)
        missing_count = self.check_missing_values(factor_name)

        pivot = self._get_pivot_table(factor_name)
        total_cells = pivot.size
        missing_ratio = missing_count / total_cells if total_cells > 0 else 1.0

        score_coverage = coverage

        if distribution["type"] == "binary":
            imbalance = distribution.get("imbalance", 0)
            score_distribution = 1.0 - imbalance
        elif distribution["type"] == "continuous":
            skewness = abs(distribution.get("skewness", 0))
            score_distribution = max(0.0, 1.0 - skewness / 5.0)
        else:
            score_distribution = 0.5

        score_stability = 1.0 - instability
        score_missing = max(0.0, 1.0 - missing_ratio * 2)

        weights = {
            "coverage": 0.25,
            "distribution": 0.25,
            "stability": 0.25,
            "missing": 0.25,
        }

        total_score = (
            weights["coverage"] * score_coverage
            + weights["distribution"] * score_distribution
            + weights["stability"] * score_stability
            + weights["missing"] * score_missing
        )

        return float(np.clip(total_score, 0.0, 1.0))

    def validate_factor(self, factor_name: str) -> Dict:
        """对单个因子进行全面验证。

        Args:
            factor_name: 因子名称。

        Returns:
            验证结果字典。
        """
        if factor_name in self._validation_cache:
            return self._validation_cache[factor_name]

        issues: List[str] = []
        suggestions: List[str] = []

        coverage = self.check_signal_coverage(factor_name)
        distribution = self.check_signal_distribution(factor_name)
        stability = self.check_signal_stability(factor_name)
        missing_count = self.check_missing_values(factor_name)
        quality_score = self.calculate_quality_score(factor_name)
        correlation = self.check_signal_correlation(factor_name)
        periodicity = self.check_signal_periodicity(factor_name)
        trend = self.check_signal_trend(factor_name)

        if coverage < 0.5:
            issues.append(f"信号覆盖率过低 ({coverage:.2%})")
            suggestions.append("检查数据源或因子计算逻辑，确保更多股票/日期有信号")

        if distribution["type"] == "binary" and distribution.get("imbalance", 0) > 0.8:
            issues.append(
                f"二值信号严重不平衡 (imbalance={distribution['imbalance']:.2f})"
            )
            suggestions.append("调整信号阈值或使用分层采样平衡信号分布")

        if stability > 0.7:
            issues.append(f"信号过于不稳定 (变化率={stability:.2%})")
            suggestions.append("考虑添加信号平滑处理或增加信号生成条件的持续性要求")

        pivot = self._get_pivot_table(factor_name)
        missing_ratio = missing_count / pivot.size if pivot.size > 0 else 1.0
        if missing_ratio > 0.3:
            issues.append(f"缺失值比例过高 ({missing_ratio:.2%})")
            suggestions.append("使用适当方法填充缺失值（前向填充、截面均值填充等）")

        if periodicity.get("has_periodicity"):
            period = periodicity.get("dominant_period", "unknown")
            issues.append(f"检测到周期性模式 (周期={period})")
            suggestions.append("检查是否与数据发布周期相关，考虑去周期化处理")

        if trend.get("has_trend"):
            direction = trend["trend_direction"]
            p_val = trend["p_value"]
            issues.append(f"检测到显著{direction}行趋势 (p={p_val:.4f})")
            suggestions.append("考虑对因子进行去趋势处理（差分或回归残差）")

        result = {
            "factor_name": factor_name,
            "quality_score": quality_score,
            "coverage": coverage,
            "distribution": distribution,
            "stability": stability,
            "missing_count": missing_count,
            "correlation": correlation,
            "periodicity": periodicity,
            "trend": trend,
            "issues": issues,
            "suggestions": suggestions,
            "timestamp": datetime.now().isoformat(),
        }

        self._validation_cache[factor_name] = result
        return result

    def validate_all_factors(self) -> pd.DataFrame:
        """验证数据库中所有因子。

        Returns:
            验证结果 DataFrame，每行一个因子，包含主要质量指标。
        """
        factor_names = self._get_all_factor_names()
        results = []

        for factor_name in factor_names:
            try:
                validation = self.validate_factor(factor_name)
                row = {
                    "factor_name": factor_name,
                    "quality_score": validation["quality_score"],
                    "coverage": validation["coverage"],
                    "stability": validation["stability"],
                    "missing_count": validation["missing_count"],
                    "signal_type": validation["distribution"]["type"],
                    "issue_count": len(validation["issues"]),
                    "has_periodicity": validation["periodicity"].get(
                        "has_periodicity", False
                    ),
                    "has_trend": validation["trend"].get("has_trend", False),
                    "issues": "; ".join(validation["issues"]),
                    "suggestions": "; ".join(validation["suggestions"]),
                }
                results.append(row)
            except Exception as e:
                logger.error("验证因子 '%s' 时出错: %s", factor_name, e)
                results.append(
                    {
                        "factor_name": factor_name,
                        "quality_score": 0.0,
                        "coverage": 0.0,
                        "stability": 0.0,
                        "missing_count": -1,
                        "signal_type": "error",
                        "issue_count": 1,
                        "has_periodicity": False,
                        "has_trend": False,
                        "issues": str(e),
                        "suggestions": "检查因子数据格式和完整性",
                    }
                )

        df = pd.DataFrame(results)
        df = df.sort_values("quality_score", ascending=False).reset_index(drop=True)
        return df

    def generate_validation_report(
        self, output_path: Optional[str] = None
    ) -> pd.DataFrame:
        """生成完整的验证报告并可选保存到文件。

        Args:
            output_path: 输出文件路径。支持 .csv 和 .xlsx 格式。
                如果为 None，则不保存文件。

        Returns:
            验证结果 DataFrame。
        """
        report = self.validate_all_factors()

        summary = {
            "total_factors": len(report),
            "avg_quality_score": float(report["quality_score"].mean()),
            "high_quality_count": int(len(report[report["quality_score"] >= 0.7])),
            "medium_quality_count": int(
                len(
                    report[
                        (report["quality_score"] >= 0.4)
                        & (report["quality_score"] < 0.7)
                    ]
                )
            ),
            "low_quality_count": int(len(report[report["quality_score"] < 0.4])),
            "factors_with_issues": int(len(report[report["issue_count"] > 0])),
            "factors_with_periodicity": int(
                len(report[report["has_periodicity"] == True])
            ),
            "factors_with_trend": int(len(report[report["has_trend"] == True])),
            "report_timestamp": datetime.now().isoformat(),
        }

        report.attrs["summary"] = summary

        if output_path:
            output_path = str(output_path)
            if output_path.endswith(".csv"):
                report.to_csv(output_path, index=False, encoding="utf-8-sig")
            elif output_path.endswith((".xlsx", ".xls")):
                with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                    report.to_excel(writer, sheet_name="factor_validation", index=False)
                    summary_df = pd.DataFrame([summary])
                    summary_df.to_excel(writer, sheet_name="summary", index=False)
            else:
                warnings.warn(f"不支持的文件格式: {output_path}，仅返回 DataFrame")

            logger.info("验证报告已保存到: %s", output_path)

        return report

    def get_problematic_factors(self, threshold: float = 0.5) -> List[str]:
        """获取质量评分低于阈值的因子列表。

        Args:
            threshold: 质量评分阈值，默认 0.5。

        Returns:
            问题因子名称列表，按质量评分升序排列。
        """
        report = self.validate_all_factors()
        problematic = report[report["quality_score"] < threshold]
        return problematic["factor_name"].tolist()

    def clear_cache(self) -> None:
        """清除所有缓存数据。"""
        self._cache.clear()
        self._validation_cache.clear()

    def get_factor_summary(self, factor_name: str) -> str:
        """获取因子的可读性摘要。

        Args:
            factor_name: 因子名称。

        Returns:
            因子验证摘要字符串。
        """
        validation = self.validate_factor(factor_name)
        score = validation["quality_score"]

        if score >= 0.8:
            grade = "优秀"
        elif score >= 0.6:
            grade = "良好"
        elif score >= 0.4:
            grade = "一般"
        else:
            grade = "较差"

        lines = [
            f"因子: {factor_name}",
            f"质量评分: {score:.3f} ({grade})",
            f"信号覆盖率: {validation['coverage']:.2%}",
            f"信号类型: {validation['distribution']['type']}",
            f"信号稳定性: {1 - validation['stability']:.2%}",
            f"缺失值数量: {validation['missing_count']}",
        ]

        if validation["issues"]:
            lines.append("")
            lines.append("问题:")
            for issue in validation["issues"]:
                lines.append(f"  - {issue}")

        if validation["suggestions"]:
            lines.append("")
            lines.append("建议:")
            for suggestion in validation["suggestions"]:
                lines.append(f"  - {suggestion}")

        return "\n".join(lines)
