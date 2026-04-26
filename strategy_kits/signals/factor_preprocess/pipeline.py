"""Pipeline orchestration for factor preprocessing and scoring."""
from __future__ import annotations
from typing import List, Optional, Dict, Any
import pandas as pd
import math

from ...core import get_logger, log_kv
from .config import PreprocessConfig, ScoreConfig
from .cleaners import fill_missing_by_group
from .transformers import winsorize_features, standardize_features
from .scoring import build_score_frame


_logger = get_logger("factor_preprocess.pipeline")


class FactorPreprocessPipeline:
    """因子预处理与打分流水线

    整合清洗 → 去极值 → 标准化 → 打分的完整流程。
    支持 fit/transform 模式，避免训练集信息泄露到测试集。

    Example:
        >>> pipeline = FactorPreprocessPipeline(
        ...     factor_cols=["roe", "pe", "pb"],
        ...     preprocess_config=PreprocessConfig(),
        ...     score_config=ScoreConfig(method="equal")
        ... )
        >>> # 拟合（在训练集上计算统计量）
        >>> pipeline.fit(train_df)
        >>> # 转换（应用到任意数据）
        >>> train_score = pipeline.transform(train_df)
        >>> test_score = pipeline.transform(test_df)
    """

    def __init__(
        self,
        factor_cols: List[str],
        preprocess_config: Optional[PreprocessConfig] = None,
        score_config: Optional[ScoreConfig] = None,
        date_col: Optional[str] = "date",
        code_col: str = "code",
    ):
        """
        Args:
            factor_cols: 因子列名列表
            preprocess_config: 预处理配置，默认使用 PreprocessConfig()
            score_config: 打分配置，默认使用 ScoreConfig()
            date_col: 日期列名，None 表示单截面
            code_col: 股票代码列名
        """
        self.factor_cols = factor_cols
        self.preprocess_config = preprocess_config or PreprocessConfig()
        self.score_config = score_config or ScoreConfig()
        self.date_col = date_col
        self.code_col = code_col

        # 存储训练集统计量（用于 transform）
        self._stats: Dict[str, Any] = {}
        self._fitted = False

    def _normalize_input_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        """规范输入列类型，冻结基础 contract。"""
        out = df.copy()
        if self.date_col and self.date_col in out.columns:
            out[self.date_col] = pd.to_datetime(out[self.date_col], errors="coerce")
        if self.code_col in out.columns:
            out[self.code_col] = out[self.code_col].astype(str).str.strip()
        return out

    def fit(self, df: pd.DataFrame) -> "FactorPreprocessPipeline":
        """拟合流水线（在训练集上计算统计量）

        Args:
            df: 训练数据框

        Returns:
            self
        """
        fit_df = self._normalize_input_frame(df)

        self._stats = {
            "fill_stats": {},
            "winsor_stats": {},
            "standardize_stats": {},
        }

        # 计算填充统计量
        fill_group_col = self.preprocess_config.fill_group_col
        valid_cols = [c for c in self.factor_cols if c in fit_df.columns]
        for col in valid_cols:
            if fill_group_col and fill_group_col in fit_df.columns:
                if self.preprocess_config.fill_method == "mean":
                    stats = fit_df.groupby(fill_group_col)[col].mean().to_dict()
                elif self.preprocess_config.fill_method == "median":
                    stats = fit_df.groupby(fill_group_col)[col].median().to_dict()
                else:
                    stats = {}
                self._stats["fill_stats"][col] = {
                    "group_col": fill_group_col,
                    "group_stats": stats,
                    "global": float(fit_df[col].mean()) if self.preprocess_config.fill_method == "mean" else float(fit_df[col].median()),
                }
            else:
                if self.preprocess_config.fill_method == "mean":
                    fill_val = float(fit_df[col].mean())
                elif self.preprocess_config.fill_method == "median":
                    fill_val = float(fit_df[col].median())
                elif self.preprocess_config.fill_method == "zero":
                    fill_val = 0.0
                else:
                    fill_val = 0.0
                if math.isnan(fill_val):
                    fill_val = 0.0
                self._stats["fill_stats"][col] = {
                    "group_col": None,
                    "group_stats": {},
                    "global": fill_val,
                }

        # 计算去极值统计量（训练集边界）
        for col in valid_cols:
            series = fit_df[col]
            method = self.preprocess_config.winsorize_method
            if method == "mad":
                median = float(series.median())
                mad = float((series - median).abs().median())
                scale = 1.4826 * mad
                lower = median - self.preprocess_config.winsorize_n * scale
                upper = median + self.preprocess_config.winsorize_n * scale
            else:
                ql, qh = self.preprocess_config.winsorize_quantiles
                lower = float(series.quantile(ql))
                upper = float(series.quantile(qh))
            self._stats["winsor_stats"][col] = {"lower": lower, "upper": upper}

        # 计算标准化统计量
        std_group_col = self.preprocess_config.standardize_group_col
        if self.preprocess_config.standardize_method == "zscore":
            for col in valid_cols:
                if std_group_col and std_group_col in fit_df.columns:
                    by_group = {}
                    for group, g in fit_df.groupby(std_group_col):
                        mean = float(g[col].mean())
                        std = float(g[col].std())
                        by_group[group] = {"mean": mean, "std": std if std > 1e-12 else 1.0}
                    self._stats["standardize_stats"][col] = {
                        "group_col": std_group_col,
                        "group_stats": by_group,
                        "global": {
                            "mean": float(fit_df[col].mean()) if not math.isnan(float(fit_df[col].mean())) else 0.0,
                            "std": (
                                float(fit_df[col].std())
                                if not math.isnan(float(fit_df[col].std())) and float(fit_df[col].std()) > 1e-12
                                else 1.0
                            ),
                        },
                    }
                else:
                    std = float(fit_df[col].std())
                    self._stats["standardize_stats"][col] = {
                        "group_col": None,
                        "group_stats": {},
                        "global": {
                            "mean": float(fit_df[col].mean()) if not math.isnan(float(fit_df[col].mean())) else 0.0,
                            "std": std if not math.isnan(std) and std > 1e-12 else 1.0,
                        },
                    }

        self._fitted = True
        log_kv(
            _logger,
            20,  # logging.INFO
            "factor_pipeline_fitted",
            rows=len(fit_df),
            factor_count=len(valid_cols),
            has_group_fill=bool(fill_group_col),
            has_group_std=bool(std_group_col),
        )
        return self

    def _apply_fitted_fill(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for col, meta in self._stats.get("fill_stats", {}).items():
            if col not in out.columns:
                continue
            series = pd.to_numeric(out[col], errors="coerce")
            group_col = meta.get("group_col")
            group_stats = meta.get("group_stats", {})
            global_val = meta.get("global", 0.0)
            if group_col and group_col in out.columns and group_stats:
                series = series.fillna(out[group_col].map(group_stats))
                out[col] = series.fillna(global_val)
            else:
                out[col] = series.fillna(global_val)
        return out

    def _apply_fitted_winsorize(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for col, bounds in self._stats.get("winsor_stats", {}).items():
            if col not in out.columns:
                continue
            out[col] = out[col].clip(lower=bounds["lower"], upper=bounds["upper"])
        return out

    def _apply_fitted_standardize(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for col, meta in self._stats.get("standardize_stats", {}).items():
            if col not in out.columns:
                continue
            group_col = meta.get("group_col")
            group_stats = meta.get("group_stats", {})
            global_meta = meta.get("global", {"mean": 0.0, "std": 1.0})
            if group_col and group_col in out.columns and group_stats:
                means = out[group_col].map({k: v["mean"] for k, v in group_stats.items()})
                stds = out[group_col].map({k: v["std"] for k, v in group_stats.items()})
                means = means.fillna(global_meta["mean"])
                stds = stds.fillna(global_meta["std"]).replace(0, 1.0)
                out[col] = (out[col] - means) / stds
            else:
                mean = global_meta.get("mean", 0.0)
                std = global_meta.get("std", 1.0) or 1.0
                out[col] = (out[col] - mean) / std
        return out

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """应用预处理与打分

        Args:
            df: 输入数据框

        Returns:
            含 'score' 列的结果数据框
        """
        in_df = self._normalize_input_frame(df)
        if self._fitted:
            result = self._apply_fitted_fill(in_df)
            result = self._apply_fitted_winsorize(result)
            if self.preprocess_config.standardize_method == "zscore":
                result = self._apply_fitted_standardize(result)
            else:
                # rank/minmax inherently recalculated on current cross-section
                result = standardize_features(
                    result,
                    self.factor_cols,
                    group_col=self.preprocess_config.standardize_group_col,
                    method=self.preprocess_config.standardize_method,
                )
        else:
            # Backward-compatible path for quick experiments.
            result = fill_missing_by_group(
                in_df,
                self.factor_cols,
                group_col=self.preprocess_config.fill_group_col,
                method=self.preprocess_config.fill_method,
            )
            result = winsorize_features(
                result,
                self.factor_cols,
                method=self.preprocess_config.winsorize_method,
                n_mad=self.preprocess_config.winsorize_n,
                quantile_limits=self.preprocess_config.winsorize_quantiles,
            )
            result = standardize_features(
                result,
                self.factor_cols,
                group_col=self.preprocess_config.standardize_group_col,
                method=self.preprocess_config.standardize_method,
            )

        # 步骤4: 打分
        result = build_score_frame(
            result,
            self.factor_cols,
            method=self.score_config.method,
            weights=self.score_config.weights,
            direction=self.score_config.direction,
            ic_window=self.score_config.ic_window,
            ret_col=self.score_config.ret_col,
            date_col=self.date_col,
            rank_first=self.score_config.rank_first,
        )

        log_kv(
            _logger,
            20,  # logging.INFO
            "factor_pipeline_transformed",
            rows=len(result),
            factor_count=len([c for c in self.factor_cols if c in result.columns]),
            fitted=self._fitted,
        )
        return result

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """拟合并转换（训练集使用）"""
        return self.fit(df).transform(df)

    def get_top_stocks(
        self,
        df: pd.DataFrame,
        n: int = 50,
        ascending: bool = False
    ) -> pd.DataFrame:
        """获取打分最高的 N 只股票

        Args:
            df: 已打分的数据框
            n: 选取数量
            ascending: 是否升序（True 表示选分数最低的）

        Returns:
            Top N 股票数据框
        """
        if "score" not in df.columns:
            raise ValueError("DataFrame must have 'score' column. Call transform() first.")

        if self.date_col and self.date_col in df.columns:
            # 按日期分组取 Top N
            def get_top_group(group):
                return group.sort_values("score", ascending=ascending).head(n)
            return df.groupby(self.date_col).apply(get_top_group).reset_index(drop=True)
        else:
            # 单截面
            return df.sort_values("score", ascending=ascending).head(n)

    def get_quantile_portfolio(
        self,
        df: pd.DataFrame,
        n_quantiles: int = 5,
        quantile: int = 5
    ) -> pd.DataFrame:
        """获取指定分位数的股票组合

        Args:
            df: 已打分的数据框
            n_quantiles: 分位数数量
            quantile: 选取的分位数（1=最低，n_quantiles=最高）

        Returns:
            指定分位数的股票数据框
        """
        if "score" not in df.columns:
            raise ValueError("DataFrame must have 'score' column. Call transform() first.")

        def select_quantile(group):
            group = group.copy()
            group["quantile"] = pd.qcut(
                group["score"], n_quantiles, labels=False, duplicates="drop"
            ) + 1
            return group[group["quantile"] == quantile]

        if self.date_col and self.date_col in df.columns:
            return df.groupby(self.date_col).apply(select_quantile).reset_index(drop=True)
        else:
            return select_quantile(df)
