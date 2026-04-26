"""仓位控制"""

import logging
import numpy as np
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PositionController:
    """仓位控制器

    管理单票最大仓位、行业集中度、总仓位限制。
    """

    def __init__(
        self,
        max_single_weight: float = 0.15,
        max_industry_weight: float = 0.30,
        max_total_position: float = 1.0,
    ):
        """初始化仓位控制器

        Args:
            max_single_weight: 单票最大权重
            max_industry_weight: 行业最大权重
            max_total_position: 总仓位上限
        """
        self.max_single_weight = max_single_weight
        self.max_industry_weight = max_industry_weight
        self.max_total_position = max_total_position

    def adjust_weights(
        self, weights: Dict[str, float], industries: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """调整权重以符合风控要求

        Args:
            weights: 原始权重 {code: weight}
            industries: 行业映射 {code: industry}

        Returns:
            Dict: 调整后的权重
        """
        adjusted = dict(weights)

        # 单票限制
        for code in list(adjusted.keys()):
            if adjusted[code] > self.max_single_weight:
                adjusted[code] = self.max_single_weight

        # 行业限制
        if industries:
            industry_weights = {}
            for code, weight in adjusted.items():
                industry = industries.get(code, "unknown")
                industry_weights[industry] = industry_weights.get(industry, 0) + weight

            for industry, total_w in industry_weights.items():
                if total_w > self.max_industry_weight:
                    # 按比例缩减
                    scale = self.max_industry_weight / total_w
                    for code in list(adjusted.keys()):
                        if industries.get(code) == industry:
                            adjusted[code] *= scale

        # 总仓位限制
        total = sum(adjusted.values())
        if total > self.max_total_position:
            scale = self.max_total_position / total
            adjusted = {k: v * scale for k, v in adjusted.items()}

        return adjusted
