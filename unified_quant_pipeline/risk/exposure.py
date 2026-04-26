"""风险敞口监控"""

import logging
import pandas as pd
from typing import Dict, List

logger = logging.getLogger(__name__)


class ExposureMonitor:
    """风险敞口监控器

    监控组合在因子、行业、市值等维度的暴露。
    """

    def analyze_factor_exposure(
        self, weights: Dict[str, float], factor_data: pd.DataFrame
    ) -> Dict[str, float]:
        """分析因子暴露

        Args:
            weights: 持仓权重 {code: weight}
            factor_data: 因子数据，columns包含因子值

        Returns:
            Dict: 各因子的加权暴露
        """
        exposures = {}

        for col in factor_data.columns:
            if col in ["code", "date"]:
                continue

            df = factor_data[factor_data["code"].isin(weights.keys())].copy()
            df["weight"] = df["code"].map(weights)
            df = df.dropna(subset=[col, "weight"])

            if len(df) > 0:
                exposures[col] = (df[col] * df["weight"]).sum()

        return exposures

    def analyze_concentration(self, weights: Dict[str, float]) -> Dict:
        """分析持仓集中度

        Args:
            weights: 持仓权重 {code: weight}

        Returns:
            Dict: 集中度指标
        """
        if not weights:
            return {}

        sorted_weights = sorted(weights.values(), reverse=True)

        return {
            "top1_weight": sorted_weights[0] if sorted_weights else 0,
            "top3_weight": sum(sorted_weights[:3]),
            "top5_weight": sum(sorted_weights[:5]),
            "herfindahl_index": sum(w**2 for w in sorted_weights),
            "n_holdings": len(weights),
        }
