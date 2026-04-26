"""ETF轮动策略 - 基于动量的ETF选择和权重分配"""

import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from .base import StrategyCatalog, BaseSelectionStrategy

logger = logging.getLogger(__name__)


@StrategyCatalog.register("etf_momentum")
class ETFMomentumRotation(BaseSelectionStrategy):
    """ETF动量轮动策略 - 根据动量得分选择Top N只ETF进行配置"""

    name = "etf_momentum"

    def __init__(self, momentum_period: int = 20, method: str = "simple"):
        """初始化ETF动量轮动策略

        Args:
            momentum_period: 动量计算周期
            method: 动量计算方法 (simple/regression/risk_adjusted)
        """
        self.momentum_period = momentum_period
        self.method = method

    def select_stocks(
        self,
        data: pd.DataFrame,
        date: str,
        n_stocks: int = 3,
        min_stocks: int = 1,
        score_col: str = "momentum",
        **kwargs,
    ) -> List[str]:
        """根据动量选择ETF

        Args:
            data: ETF截面数据
            date: 当前日期
            n_stocks: 目标选择数量
            min_stocks: 最少选择数量
            score_col: 动量字段名

        Returns:
            List[str]: 选中的ETF代码列表
        """
        df = data.copy()

        if score_col not in df.columns:
            df["momentum"] = df["close"].pct_change(self.momentum_period)
            score_col = "momentum"

        df = df.sort_values(score_col, ascending=False)

        n = min(n_stocks, len(df))
        n = max(n, min_stocks)

        selected = df.head(n)["code"].tolist()
        logger.info(f"[{date}] ETF Rotation: Selected {selected}")

        return selected

    def compute_weights(
        self,
        data: pd.DataFrame,
        selected: List[str],
        method: str = "momentum",
        **kwargs,
    ) -> Dict[str, float]:
        """根据动量计算权重

        Args:
            data: ETF截面数据
            selected: 选中的ETF列表
            method: 权重计算方法 (equal/momentum)

        Returns:
            Dict[str, float]: {etf_code: weight}
        """
        if method == "equal":
            return {s: 1.0 / len(selected) for s in selected}

        df = data[data["code"].isin(selected)].copy()
        df["momentum"] = df["close"].pct_change(self.momentum_period)

        df = df[df["momentum"] > 0]

        if len(df) == 0:
            return {s: 1.0 / len(selected) for s in selected}

        df["weight"] = df["momentum"] / df["momentum"].sum()
        return df.set_index("code")["weight"].to_dict()
