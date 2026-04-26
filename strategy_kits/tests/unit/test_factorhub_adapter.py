from __future__ import annotations

import pandas as pd

from strategy_kits.integrations.factorhub import (
    load_factorhub_panel,
    merge_cross_sectional_with_temporal_score,
    pool_panel_to_prediction_frame,
    score_panel_to_prediction_frame,
)


def test_pool_panel_to_prediction_frame_topn_and_weight_sum():
    panel = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02", "2024-01-02", "2024-01-03", "2024-01-03"],
            "code": ["1", "2", "3", "1", "2"],
            "score": [0.4, 0.2, 0.1, 0.7, 0.3],
            "rank": [1, 2, 3, 1, 2],
        }
    )

    pred = pool_panel_to_prediction_frame(panel, top_n=2, weight_mode="score")
    assert set(pred.columns) >= {"date", "code", "weight"}
    assert pred["date"].dtype.kind == "M"

    grouped = pred.groupby("date")["weight"].sum()
    assert all(abs(v - 1.0) < 1e-8 for v in grouped.tolist())
    assert pred["code"].tolist()[:2] == ["000001", "000002"]


def test_score_panel_alias_ts_score_and_loader(tmp_path):
    panel = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02", "2024-01-03"],
            "code": ["600000.SH", "000001.SZ", "600000.SH"],
            "ts_score": [0.8, 0.2, 0.6],
        }
    )
    csv_path = tmp_path / "score_panel.csv"
    panel.to_csv(csv_path, index=False)

    loaded = load_factorhub_panel(csv_path, panel_type="auto")
    assert "score" in loaded.columns

    pred = score_panel_to_prediction_frame(loaded, top_n=1, weight_mode="equal")
    assert len(pred) == 2
    assert set(pred["code"]) == {"600000.SH"}
    assert pred["weight"].eq(1.0).all()


def test_merge_cross_sectional_with_temporal_score():
    cs_df = pd.DataFrame(
        {
            "date": ["2024-01-03", "2024-01-03"],
            "code": ["000001", "000002"],
            "cs_score": [1.0, 0.5],
        }
    )
    ts_panel = pd.DataFrame(
        {
            "date": ["2024-01-03", "2024-01-03"],
            "code": ["000001", "000002"],
            "score": [0.2, -0.1],
        }
    )
    merged = merge_cross_sectional_with_temporal_score(cs_df, ts_panel, lambda_ts=0.5)

    expected = {"000001": 1.1, "000002": 0.45}
    got = dict(zip(merged["code"], merged["final_score"]))
    assert abs(got["000001"] - expected["000001"]) < 1e-8
    assert abs(got["000002"] - expected["000002"]) < 1e-8
