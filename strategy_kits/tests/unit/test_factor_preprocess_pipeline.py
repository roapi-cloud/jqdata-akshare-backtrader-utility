from __future__ import annotations

import pandas as pd

from strategy_kits.signals.factor_preprocess import (
    FactorPreprocessPipeline,
    PreprocessConfig,
    ScoreConfig,
)


def test_pipeline_fit_transform_uses_train_statistics():
    train = pd.DataFrame(
        {
            "date": ["2024-01-01"] * 4,
            "code": ["000001", "000002", "000003", "000004"],
            "industry": ["A", "A", "B", "B"],
            "factor1": [1.0, 3.0, 10.0, 14.0],
        }
    )
    test = pd.DataFrame(
        {
            "date": ["2024-01-02"] * 2,
            "code": ["000005", "000006"],
            "industry": ["A", "B"],
            "factor1": [2.0, 12.0],
        }
    )
    pipe = FactorPreprocessPipeline(
        factor_cols=["factor1"],
        preprocess_config=PreprocessConfig(
            fill_method="mean",
            fill_group_col="industry",
            winsorize_method="quantile",
            winsorize_quantiles=(0.01, 0.99),
            standardize_method="zscore",
            standardize_group_col="industry",
        ),
        score_config=ScoreConfig(method="equal", direction="ascending", rank_first=False),
        date_col="date",
    )

    pipe.fit(train)
    out = pipe.transform(test)

    # A 组训练均值=2/std~=1.414; B 组训练均值=12/std~=2.828
    a_val = float(out.loc[out["industry"] == "A", "factor1"].iloc[0])
    b_val = float(out.loc[out["industry"] == "B", "factor1"].iloc[0])
    assert abs(a_val) < 0.3
    assert abs(b_val) < 0.3
    assert "score" in out.columns


def test_pipeline_fill_uses_fitted_group_stats_for_missing_values():
    train = pd.DataFrame(
        {
            "date": ["2024-01-01"] * 4,
            "code": ["000001", "000002", "000003", "000004"],
            "industry": ["A", "A", "B", "B"],
            "factor1": [1.0, 3.0, 10.0, 14.0],
        }
    )
    test = pd.DataFrame(
        {
            "date": ["2024-01-02"] * 2,
            "code": ["000005", "000006"],
            "industry": ["A", "B"],
            "factor1": [None, None],
        }
    )
    pipe = FactorPreprocessPipeline(
        factor_cols=["factor1"],
        preprocess_config=PreprocessConfig(
            fill_method="mean",
            fill_group_col="industry",
            winsorize_method="quantile",
            winsorize_quantiles=(0.01, 0.99),
            standardize_method="zscore",
            standardize_group_col=None,
        ),
        score_config=ScoreConfig(method="equal", direction="ascending"),
        date_col="date",
    )
    pipe.fit(train)
    out = pipe.transform(test)

    assert out["factor1"].notna().all()
    assert "score" in out.columns
