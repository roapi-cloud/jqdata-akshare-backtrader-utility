"""Stock selection signal generators.

Stock selection signals determine *which* stocks to trade based on
factor scores, filters, and portfolio construction methods.
"""

from typing import Any, Optional

import numpy as np
import pandas as pd

from .base import Signal, SignalResult, SignalType


class FactorRankSignal(Signal):
    """Stock selection signal based on factor ranking.

    Ranks all eligible stocks by a factor score and selects the top-N
    for BUY signals. Optionally selects bottom-N for SELL signals.

    Default parameters:
        factor_name: Name of the factor to rank by (e.g., 'ROE', 'momentum')
        top_n: Number of top-ranked stocks to select
        bottom_n: Number of bottom-ranked stocks to exclude (SELL)
        min_score: Minimum factor score to consider (filter noise)
        ascending: False for higher-is-better factors (default)
    """

    @property
    def name(self) -> str:
        return "FACTOR_RANK"

    def generate(
        self,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        params: Optional[dict[str, Any]] = None,
    ) -> SignalResult:
        """Generate rank-based stock selection signal.

        Args:
            factor_values: Dictionary containing factor data. The key
                           specified by `factor_name` should be a Series
                           indexed by stock code, or a DataFrame with
                           a column matching the factor name.
            params: Optional overrides for top_n, bottom_n, etc.

        Returns:
            SignalResult with BUY signal for top-ranked stocks,
            and SELL for bottom-ranked if bottom_n > 0.
        """
        defaults = {
            "factor_name": "score",
            "top_n": 10,
            "bottom_n": 0,
            "min_score": None,
            "ascending": False,
        }
        cfg = self._merge_params(defaults, params)

        scores = self._extract_factor_series(factor_values, cfg["factor_name"])
        if scores is None or scores.empty:
            return self._empty_result(f"No data for factor '{cfg['factor_name']}'")

        scores = scores.dropna()
        if scores.empty:
            return self._empty_result("All factor values are NaN")

        if cfg["min_score"] is not None:
            scores = scores[scores >= cfg["min_score"]]
            if scores.empty:
                return self._empty_result(f"No stocks with score >= {cfg['min_score']}")

        sorted_scores = scores.sort_values(ascending=cfg["ascending"])

        top_stocks = sorted_scores.tail(cfg["top_n"]).index.tolist()
        buy_stocks = (
            top_stocks
            if not cfg["ascending"]
            else sorted_scores.head(cfg["top_n"]).index.tolist()
        )

        result_stocks = list(buy_stocks)
        sell_stocks = []

        if cfg["bottom_n"] > 0:
            sell_stocks = sorted_scores.head(cfg["bottom_n"]).index.tolist()
            result_stocks = [s for s in result_stocks if s not in sell_stocks]

        if not result_stocks and not sell_stocks:
            return self._empty_result("No stocks selected after filtering")

        avg_score = scores.loc[result_stocks].mean() if result_stocks else 0.0
        score_range = scores.max() - scores.min()
        strength = (
            self._normalize_strength(avg_score, scores.min(), scores.max())
            if score_range > 0
            else 0.5
        )

        return SignalResult(
            date=scores.index[-1]
            if hasattr(scores.index[-1], "year")
            else pd.Timestamp.today(),
            signal_type=SignalType.BUY,
            strength=strength,
            stocks=result_stocks,
            metadata={
                "factor_name": cfg["factor_name"],
                "top_n": cfg["top_n"],
                "bottom_n": cfg["bottom_n"],
                "sell_stocks": sell_stocks,
                "avg_score": avg_score,
            },
        )

    def _extract_factor_series(
        self, factor_values: dict[str, pd.DataFrame | pd.Series], factor_name: str
    ) -> Optional[pd.Series]:
        """Extract a factor series by name from factor values."""
        if factor_name in factor_values:
            data = factor_values[factor_name]
            if isinstance(data, pd.DataFrame):
                if factor_name in data.columns:
                    return data[factor_name]
                return data.iloc[:, -1]
            if isinstance(data, pd.Series):
                return data
        for key, data in factor_values.items():
            if isinstance(data, pd.DataFrame) and factor_name in data.columns:
                return data[factor_name]
        return None

    def _empty_result(self, reason: str) -> SignalResult:
        """Return a neutral result when signal cannot be computed."""
        return SignalResult(
            date=pd.Timestamp.today(),
            signal_type=SignalType.HOLD,
            strength=0.0,
            metadata={"reason": reason},
        )


class MultiFactorSignal(Signal):
    """Stock selection signal based on weighted combination of multiple factors.

    Combines multiple factor scores using configurable weights to produce
    a composite score, then selects top-ranked stocks.

    Default parameters:
        weights: Dictionary mapping factor names to weights (default: equal weight)
        top_n: Number of top stocks to select
        normalization: 'zscore' | 'rank' | 'minmax' (how to normalize factors)
        min_stocks: Minimum number of stocks required to generate signal
    """

    @property
    def name(self) -> str:
        return "MULTI_FACTOR"

    def generate(
        self,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        params: Optional[dict[str, Any]] = None,
    ) -> SignalResult:
        """Generate multi-factor composite stock selection signal.

        Args:
            factor_values: Dictionary with factor names as keys. Each value
                           should be a Series indexed by stock code, or a
                           DataFrame with stock codes as index.
            params: Optional overrides for weights, top_n, normalization.

        Returns:
            SignalResult with BUY signal for top composite-score stocks.
        """
        defaults = {
            "weights": None,
            "top_n": 10,
            "normalization": "zscore",
            "min_stocks": 1,
        }
        cfg = self._merge_params(defaults, params)

        factor_series = self._collect_factor_series(factor_values)
        if not factor_series:
            return self._empty_result("No factor data available")

        if cfg["weights"] is None:
            cfg["weights"] = {name: 1.0 for name in factor_series.keys()}

        common_index = self._common_index(factor_series)
        if common_index.empty:
            return self._empty_result("No common stocks across all factors")

        normalized_factors = {}
        for fname, fdata in factor_series.items():
            aligned = fdata.reindex(common_index)
            normalized_factors[fname] = self._normalize_factor(
                aligned, cfg["normalization"]
            )

        composite = pd.Series(0.0, index=common_index)
        total_weight = 0.0
        for fname, norm_data in normalized_factors.items():
            w = cfg["weights"].get(fname, 0.0)
            if w > 0:
                composite = composite + norm_data * w
                total_weight += w

        if total_weight > 0:
            composite = composite / total_weight

        composite = composite.dropna()
        if len(composite) < cfg["min_stocks"]:
            return self._empty_result(
                f"Only {len(composite)} stocks, need at least {cfg['min_stocks']}"
            )

        selected = composite.sort_values(ascending=False).head(cfg["top_n"])
        selected_stocks = selected.index.tolist()

        strength = self._normalize_strength(
            selected.mean(), composite.min(), composite.max()
        )

        return SignalResult(
            date=pd.Timestamp.today(),
            signal_type=SignalType.BUY,
            strength=strength,
            stocks=selected_stocks,
            metadata={
                "weights": cfg["weights"],
                "normalization": cfg["normalization"],
                "composite_stats": {
                    "mean": composite.mean(),
                    "std": composite.std(),
                    "min": composite.min(),
                    "max": composite.max(),
                },
            },
        )

    def _collect_factor_series(
        self, factor_values: dict[str, pd.DataFrame | pd.Series]
    ) -> dict[str, pd.Series]:
        """Collect all factor data as Series indexed by stock code."""
        result = {}
        for name, data in factor_values.items():
            if isinstance(data, pd.Series):
                result[name] = data
            elif isinstance(data, pd.DataFrame):
                if len(data.columns) == 1:
                    result[name] = data.iloc[:, 0]
                else:
                    for col in data.columns:
                        result[f"{name}_{col}"] = data[col]
        return result

    def _common_index(self, factor_series: dict[str, pd.Series]) -> pd.Index:
        """Find the intersection of all factor indices."""
        if not factor_series:
            return pd.Index([])
        common = factor_series[list(factor_series.keys())[0]].index
        for name in list(factor_series.keys())[1:]:
            common = common.intersection(factor_series[name].index)
        return common

    def _normalize_factor(self, series: pd.Series, method: str) -> pd.Series:
        """Normalize a factor series using the specified method."""
        series = series.dropna()
        if series.empty:
            return series

        if method == "zscore":
            mean = series.mean()
            std = series.std()
            if std == 0 or np.isnan(std):
                return pd.Series(0.0, index=series.index)
            return (series - mean) / std

        if method == "rank":
            return series.rank(pct=True)

        if method == "minmax":
            min_val = series.min()
            max_val = series.max()
            if max_val == min_val:
                return pd.Series(0.5, index=series.index)
            return (series - min_val) / (max_val - min_val)

        return series

    def _empty_result(self, reason: str) -> SignalResult:
        """Return a neutral result when signal cannot be computed."""
        return SignalResult(
            date=pd.Timestamp.today(),
            signal_type=SignalType.HOLD,
            strength=0.0,
            metadata={"reason": reason},
        )


class FilterSignal(Signal):
    """Stock selection signal based on fundamental filters.

    Filters stocks by conditions such as PE ratio, PB ratio, market cap,
    and other fundamental criteria. Only stocks passing all filters are
    included in the BUY signal.

    Default parameters:
        min_pe: Minimum PE ratio (None = no lower bound)
        max_pe: Maximum PE ratio (None = no upper bound)
        min_pb: Minimum PB ratio
        max_pb: Maximum PB ratio
        min_market_cap: Minimum market cap in yuan
        max_market_cap: Maximum market cap in yuan
        exclude_st: Whether to exclude ST (special treatment) stocks
        exclude_new: Whether to exclude newly listed stocks (< 60 days)
    """

    @property
    def name(self) -> str:
        return "FILTER"

    def generate(
        self,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        params: Optional[dict[str, Any]] = None,
    ) -> SignalResult:
        """Generate filter-based stock selection signal.

        Args:
            factor_values: Dictionary with keys like 'pe', 'pb',
                           'market_cap', 'is_st', 'days_since_ipo'.
                           Each should be a Series indexed by stock code.
            params: Optional overrides for filter thresholds.

        Returns:
            SignalResult with BUY signal for stocks passing all filters.
        """
        defaults = {
            "min_pe": None,
            "max_pe": None,
            "min_pb": None,
            "max_pb": None,
            "min_market_cap": None,
            "max_market_cap": None,
            "exclude_st": True,
            "exclude_new": True,
            "new_stock_days": 60,
        }
        cfg = self._merge_params(defaults, params)

        all_codes = self._collect_all_codes(factor_values)
        if not all_codes:
            return self._empty_result("No stock data available")

        mask = pd.Series(True, index=all_codes)

        mask = self._apply_filter(
            mask, factor_values, "pe", cfg["min_pe"], cfg["max_pe"]
        )
        mask = self._apply_filter(
            mask, factor_values, "pb", cfg["min_pb"], cfg["max_pb"]
        )
        mask = self._apply_filter(
            mask,
            factor_values,
            "market_cap",
            cfg["min_market_cap"],
            cfg["max_market_cap"],
        )

        if cfg["exclude_st"]:
            mask = self._apply_boolean_filter(
                mask, factor_values, "is_st", exclude_true=True
            )

        if cfg["exclude_new"]:
            mask = self._apply_threshold_filter(
                mask, factor_values, "days_since_ipo", cfg["new_stock_days"], below=True
            )

        selected = mask[mask].index.tolist()

        if not selected:
            return self._empty_result("No stocks passed all filters")

        return SignalResult(
            date=pd.Timestamp.today(),
            signal_type=SignalType.BUY,
            strength=0.5,
            stocks=selected,
            metadata={
                "total_universe": len(all_codes),
                "selected_count": len(selected),
                "filters_applied": {
                    "pe": (cfg["min_pe"], cfg["max_pe"]),
                    "pb": (cfg["min_pb"], cfg["max_pb"]),
                    "market_cap": (cfg["min_market_cap"], cfg["max_market_cap"]),
                    "exclude_st": cfg["exclude_st"],
                    "exclude_new": cfg["exclude_new"],
                },
            },
        )

    def _collect_all_codes(
        self, factor_values: dict[str, pd.DataFrame | pd.Series]
    ) -> pd.Index:
        """Collect union of all stock codes across factor data."""
        all_codes = set()
        for data in factor_values.values():
            if isinstance(data, pd.Series):
                all_codes.update(data.index.tolist())
            elif isinstance(data, pd.DataFrame):
                all_codes.update(data.index.tolist())
        return pd.Index(sorted(all_codes))

    def _apply_filter(
        self,
        mask: pd.Series,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        factor_name: str,
        min_val: Optional[float],
        max_val: Optional[float],
    ) -> pd.Series:
        """Apply a range filter on a factor."""
        if min_val is None and max_val is None:
            return mask

        data = self._get_series(factor_values, factor_name)
        if data is None:
            return mask

        data = data.reindex(mask.index)
        if min_val is not None:
            mask = mask & (data >= min_val)
        if max_val is not None:
            mask = mask & (data <= max_val)

        return mask

    def _apply_boolean_filter(
        self,
        mask: pd.Series,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        factor_name: str,
        exclude_true: bool = True,
    ) -> pd.Series:
        """Apply a boolean filter (e.g., exclude ST stocks)."""
        data = self._get_series(factor_values, factor_name)
        if data is None:
            return mask

        data = data.reindex(mask.index).fillna(False)
        if exclude_true:
            return mask & ~data.astype(bool)
        return mask & data.astype(bool)

    def _apply_threshold_filter(
        self,
        mask: pd.Series,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        factor_name: str,
        threshold: float,
        below: bool = True,
    ) -> pd.Series:
        """Apply a threshold filter (e.g., exclude stocks below N days since IPO)."""
        data = self._get_series(factor_values, factor_name)
        if data is None:
            return mask

        data = data.reindex(mask.index)
        if below:
            return mask & (data >= threshold)
        return mask & (data <= threshold)

    def _get_series(
        self, factor_values: dict[str, pd.DataFrame | pd.Series], name: str
    ) -> Optional[pd.Series]:
        """Get a Series by name from factor values."""
        if name in factor_values:
            data = factor_values[name]
            if isinstance(data, pd.DataFrame):
                if name in data.columns:
                    return data[name]
                return data.iloc[:, 0]
            return data
        return None

    def _empty_result(self, reason: str) -> SignalResult:
        """Return a neutral result when signal cannot be computed."""
        return SignalResult(
            date=pd.Timestamp.today(),
            signal_type=SignalType.HOLD,
            strength=0.0,
            metadata={"reason": reason},
        )


class IndustryNeutralSignal(Signal):
    """Industry-neutral stock selection signal.

    Selects stocks within each industry based on factor rankings, ensuring
    the portfolio is balanced across industries. This avoids concentration
    risk in any single sector.

    Default parameters:
        factor_name: Factor to rank by within each industry
        top_n_per_industry: Number of stocks to select per industry
        industries: Dictionary mapping stock codes to industry names
        min_industries: Minimum number of industries required
        max_weight_per_industry: Maximum portfolio weight per industry
    """

    @property
    def name(self) -> str:
        return "INDUSTRY_NEUTRAL"

    def generate(
        self,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        params: Optional[dict[str, Any]] = None,
    ) -> SignalResult:
        """Generate industry-neutral stock selection signal.

        Args:
            factor_values: Must contain a factor Series indexed by stock code.
                           Should also contain 'industry' mapping (dict or Series).
            params: Optional overrides for industry parameters.

        Returns:
            SignalResult with BUY signal for industry-balanced stock picks.
        """
        defaults = {
            "factor_name": "score",
            "top_n_per_industry": 2,
            "industries": None,
            "min_industries": 3,
            "max_weight_per_industry": 0.25,
        }
        cfg = self._merge_params(defaults, params)

        scores = self._extract_factor_series(factor_values, cfg["factor_name"])
        if scores is None or scores.empty:
            return self._empty_result(f"No data for factor '{cfg['factor_name']}'")

        industry_map = self._extract_industry_map(factor_values, cfg["industries"])
        if industry_map is None:
            return self._empty_result("No industry mapping available")

        scores = scores.dropna()
        if scores.empty:
            return self._empty_result("All factor values are NaN")

        selected_stocks = []
        industry_counts = {}

        for stock_code in scores.index:
            industry = industry_map.get(stock_code, "UNKNOWN")
            if industry not in industry_counts:
                industry_counts[industry] = []
            industry_counts[industry].append((stock_code, scores[stock_code]))

        for industry, stock_scores in industry_counts.items():
            stock_scores.sort(key=lambda x: x[1], reverse=True)
            top_in_industry = stock_scores[: cfg["top_n_per_industry"]]
            selected_stocks.extend([code for code, _ in top_in_industry])

        if len(industry_counts) < cfg["min_industries"]:
            return self._empty_result(
                f"Only {len(industry_counts)} industries, need at least {cfg['min_industries']}"
            )

        total_selected = len(selected_stocks)
        if total_selected == 0:
            return self._empty_result("No stocks selected")

        industry_weights = {}
        for industry, stock_scores in industry_counts.items():
            selected_in_industry = [
                code
                for code, _ in stock_scores[: cfg["top_n_per_industry"]]
                if code in selected_stocks
            ]
            if selected_in_industry:
                industry_weights[industry] = len(selected_in_industry) / total_selected

        max_industry_weight = max(industry_weights.values()) if industry_weights else 0
        if max_industry_weight > cfg["max_weight_per_industry"]:
            selected_stocks = self._rebalance_industries(
                industry_counts,
                cfg["top_n_per_industry"],
                cfg["max_weight_per_industry"],
                total_selected,
            )

        avg_score = scores.loc[selected_stocks].mean() if selected_stocks else 0.0
        strength = self._normalize_strength(avg_score, scores.min(), scores.max())

        return SignalResult(
            date=pd.Timestamp.today(),
            signal_type=SignalType.BUY,
            strength=strength,
            stocks=selected_stocks,
            metadata={
                "factor_name": cfg["factor_name"],
                "top_n_per_industry": cfg["top_n_per_industry"],
                "industry_count": len(industry_counts),
                "industry_weights": industry_weights,
                "total_selected": len(selected_stocks),
            },
        )

    def _extract_factor_series(
        self, factor_values: dict[str, pd.DataFrame | pd.Series], factor_name: str
    ) -> Optional[pd.Series]:
        """Extract a factor series by name."""
        if factor_name in factor_values:
            data = factor_values[factor_name]
            if isinstance(data, pd.DataFrame):
                if factor_name in data.columns:
                    return data[factor_name]
                return data.iloc[:, -1]
            if isinstance(data, pd.Series):
                return data
        return None

    def _extract_industry_map(
        self,
        factor_values: dict[str, pd.DataFrame | pd.Series],
        industries_param: Optional[dict],
    ) -> Optional[dict]:
        """Extract industry mapping from factor values or params."""
        if industries_param is not None:
            return industries_param

        if "industry" in factor_values:
            data = factor_values["industry"]
            if isinstance(data, pd.Series):
                return data.to_dict()
            if isinstance(data, dict):
                return data

        for key, data in factor_values.items():
            if "industry" in key.lower() and isinstance(data, (pd.Series, dict)):
                if isinstance(data, pd.Series):
                    return data.to_dict()
                return data

        return None

    def _rebalance_industries(
        self,
        industry_counts: dict[str, list[tuple[str, float]]],
        top_n: int,
        max_weight: float,
        total_selected: int,
    ) -> list[str]:
        """Rebalance selection to respect max industry weight constraint."""
        selected = []
        max_per_industry = int(max_weight * total_selected)
        if max_per_industry < 1:
            max_per_industry = 1

        for industry, stock_scores in industry_counts.items():
            stock_scores.sort(key=lambda x: x[1], reverse=True)
            count = min(top_n, max_per_industry)
            selected.extend([code for code, _ in stock_scores[:count]])

        return selected

    def _empty_result(self, reason: str) -> SignalResult:
        """Return a neutral result when signal cannot be computed."""
        return SignalResult(
            date=pd.Timestamp.today(),
            signal_type=SignalType.HOLD,
            strength=0.0,
            metadata={"reason": reason},
        )
