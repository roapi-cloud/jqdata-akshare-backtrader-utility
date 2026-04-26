from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

bt = pytest.importorskip("backtrader")

from strategy_kits.execution.backtrader_runtime import BacktraderConfig, run_backtest
from strategy_kits.portfolio.position_state.portfolio_builder import PortfolioBuilder, PortfolioSpec
from strategy_kits.portfolio.runtime_state import compute_rebalance_diff
from strategy_kits.signals.factor_preprocess import FactorPreprocessPipeline, PreprocessConfig, ScoreConfig
from strategy_kits.strategy_templates.presets import WeightedTopNStrategy
from strategy_kits.universe.stock_pool_filters import apply_filters


def _make_feed(name: str, start: str = "2024-01-01", periods: int = 8) -> bt.feeds.PandasData:
    dates = pd.date_range(start=start, periods=periods, freq="D")
    base = 10.0 + hash(name) % 7
    df = pd.DataFrame(
        {
            "datetime": dates,
            "open": [base + i * 0.1 for i in range(periods)],
            "high": [base + i * 0.1 + 0.2 for i in range(periods)],
            "low": [base + i * 0.1 - 0.2 for i in range(periods)],
            "close": [base + i * 0.1 + 0.05 for i in range(periods)],
            "volume": [100000 + i * 100 for i in range(periods)],
            "openinterest": [0 for _ in range(periods)],
        }
    )
    return bt.feeds.PandasData(
        dataname=df,
        datetime="datetime",
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest="openinterest",
        name=name,
    )


def test_single_strategy_e2e_smoke():
    # 1) 输入池 -> 过滤
    base_universe = ["000001.XSHE", "000002.XSHE", "688001.XSHG"]
    filtered = apply_filters(
        base_universe=base_universe,
        date=date(2024, 1, 5),
        filter_config={
            "st": {"enabled": True, "is_st_map": {"000002.XSHE": True}, "check_name": False},
            "paused": {"enabled": True, "paused_map": {"000001.XSHE": 0}},
            "new_stock": {
                "enabled": True,
                "min_days": 250,
                "listing_date_map": {"000001.XSHE": "2010-01-01", "688001.XSHG": "2018-01-01"},
            },
            "limitup": {"enabled": False},
            "limitdown": {"enabled": False},
            "kcbj": {"enabled": True},
        },
    )
    assert filtered.filtered_universe == ["000001.XSHE"]

    # 2) 打分
    features = pd.DataFrame(
        {
            "date": ["2024-01-04", "2024-01-05"],
            "code": ["000001.XSHE", "000001.XSHE"],
            "industry": ["bank", "bank"],
            "factor_a": [0.2, 0.4],
            "factor_b": [1.2, 1.1],
        }
    )
    pipe = FactorPreprocessPipeline(
        factor_cols=["factor_a", "factor_b"],
        preprocess_config=PreprocessConfig(
            fill_method="median",
            fill_group_col="industry",
            winsorize_method="quantile",
            winsorize_quantiles=(0.05, 0.95),
            standardize_method="zscore",
            standardize_group_col=None,
        ),
        score_config=ScoreConfig(method="equal", direction="ascending"),
        date_col="date",
    )
    scored = pipe.fit_transform(features)
    latest = scored[scored["date"] == pd.Timestamp("2024-01-05")][["code", "score"]]
    assert not latest.empty

    # 3) 配仓 + 调仓差分
    builder = PortfolioBuilder(PortfolioSpec(max_positions=10, max_single=1.0))
    target = builder.build(latest, cash_target=0.1)
    current = pd.DataFrame(columns=["code", "weight"])
    orders = compute_rebalance_diff(target=target, current=current)
    assert len(orders) >= 1

    # 4) 策略模板 -> 回测
    pred_df = target.copy()
    pred_df = pred_df.rename(columns={"target_weight": "weight"})
    pred_df["date"] = pd.Timestamp("2024-01-05")

    data_bundle = {"000001.XSHE": _make_feed("000001.XSHE")}
    cfg = BacktraderConfig(
        start_date="2024-01-01",
        end_date="2024-01-10",
        symbols=[],
        initial_cash=1000000,
        benchmark=None,
        printlog=False,
        tradehistory=False,
        strategy_params={"pred_df": pred_df, "rebalance_threshold": 0.0, "hold_days": 1},
    )
    result = run_backtest(cfg, WeightedTopNStrategy, data_bundle=data_bundle)
    assert "portfolio_value" in result
    assert result["portfolio_value"] > 0
    assert "metrics" in result

