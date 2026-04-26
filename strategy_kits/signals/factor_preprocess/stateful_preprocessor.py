"""Feature preprocessing utilities for ML pipeline.

Provides FeaturePreprocessor supporting:
- Missing value imputation (mean or median)
- Standardization (z-score)
- Industry neutralization (demean within industry or regression residual)

Design notes:
- Fit only on training data to avoid leakage.
- Transform can be applied to train/validation/test.
- Industry neutralization expects an 'industry' column; if missing and neutralization requested, it is skipped.
- Regression residual neutralization is more robust but we start with simple de-mean per industry for stability.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Literal, Dict
import pandas as pd
import numpy as np

ImputeMethod = Literal["mean", "median"]
NeutralizeMethod = Literal["demean", "residual"]

@dataclass
class PreprocessConfig:
    impute: Optional[ImputeMethod] = "mean"
    standardize: bool = True
    neutralize_industry: bool = False
    neutralize_method: NeutralizeMethod = "demean"
    industry_col: str = "industry"

class FeaturePreprocessor:
    def __init__(self, config: PreprocessConfig, feature_cols: List[str]):
        self.config = config
        self.feature_cols = feature_cols
        self._impute_values: Dict[str, float] = {}
        self._mean: Dict[str, float] = {}
        self._std: Dict[str, float] = {}
        self._fitted = False

    def fit(self, df: pd.DataFrame) -> None:
        """Fit preprocessing statistics on training dataframe."""
        use_df = df[self.feature_cols]
        if self.config.impute:
            for c in self.feature_cols:
                series = use_df[c]
                if self.config.impute == "mean":
                    self._impute_values[c] = float(series.mean())
                else:
                    self._impute_values[c] = float(series.median())
        else:
            self._impute_values = {c: np.nan for c in self.feature_cols}
        # Standardization stats
        if self.config.standardize:
            for c in self.feature_cols:
                col = use_df[c]
                self._mean[c] = float(col.mean())
                std = float(col.std(ddof=0))
                self._std[c] = std if std > 1e-12 else 1.0
        self._fitted = True

    def _apply_impute(self, df: pd.DataFrame) -> None:
        if not self.config.impute:
            return
        for c in self.feature_cols:
            val = self._impute_values.get(c, np.nan)
            if pd.isna(val):
                continue
            mask = df[c].isna()
            if mask.any():
                df.loc[mask, c] = val

    def _apply_standardize(self, df: pd.DataFrame) -> None:
        if not self.config.standardize:
            return
        for c in self.feature_cols:
            mean = self._mean[c]
            std = self._std[c]
            df[c] = (df[c] - mean) / std

    def _apply_industry_neutral(self, df: pd.DataFrame) -> None:
        if not self.config.neutralize_industry:
            return
        ind_col = self.config.industry_col
        if ind_col not in df.columns:
            return  # silently skip if industry not available
        if self.config.neutralize_method == "demean":
            # subtract industry mean per feature
            grouped = df.groupby(ind_col)
            for c in self.feature_cols:
                df[c] = df[c] - grouped[c].transform("mean")
        else:  # residual method: regress each feature on industry one-hot
            inds = df[ind_col].astype(str)
            dummies = pd.get_dummies(inds, drop_first=True)
            for c in self.feature_cols:
                y = df[c].values
                X = dummies.values
                # Add small ridge term via normal equation
                XtX = X.T @ X + 1e-6 * np.eye(X.shape[1])
                try:
                    beta = np.linalg.solve(XtX, X.T @ y)
                    fitted = X @ beta
                    df[c] = y - fitted
                except Exception:
                    # fallback to demean
                    df[c] = df[c] - df.groupby(ind_col)[c].transform("mean")

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self._fitted:
            raise RuntimeError("FeaturePreprocessor must be fit before transform")
        out = df.copy()
        self._apply_impute(out)
        self._apply_standardize(out)
        self._apply_industry_neutral(out)
        return out

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        self.fit(df)
        return self.transform(df)

__all__ = ["FeaturePreprocessor", "PreprocessConfig"]
