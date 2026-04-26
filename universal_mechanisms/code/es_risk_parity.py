# ES风险平价仓位管理
# 来源：聚宽策略 07 致敬经典作品——小兵哥《一致性风险度量》——极速版.txt
# 文档：docs/universal_mechanisms/27_es_risk_parity.md

import math
import numpy as np
from jqdata import *


class ESRiskParity:
    """
    基于ES（Expected Shortfall）的风险平价仓位管理
    权重 ∝ 1/ES(资产)，让每类资产的极端风险贡献相等
    """

    ALPHA_MAP = {
        1.96: 0.05, 2.06: 0.04, 2.18: 0.03,
        2.34: 0.02, 2.58: 0.01, 5.0: 0.00001
    }

    def __init__(self, confidence_level=2.58, lookback=120,
                 rebalance_threshold=0.15, rebalance_cycle=30):
        self.confidence_level = confidence_level
        self.lookback = lookback
        self.rebalance_threshold = rebalance_threshold
        self.rebalance_cycle = rebalance_cycle

    def calculate_es(self, security):
        """计算单个资产的ES（预期亏损）"""
        alpha = self.ALPHA_MAP.get(self.confidence_level, 0.05)

        h = history(self.lookback, '1d', 'close', security, df=True)
        returns = h.resample('D').last().pct_change().fillna(0).iloc[:, 0].values

        if len(returns) == 0:
            return 0.01

        sorted_returns = sorted(returns)
        n = len(sorted_returns)
        cutoff = int(n * alpha)

        if cutoff == 0:
            return abs(sorted_returns[0])

        es = -sum(sorted_returns[:cutoff]) / (n * alpha)
        return max(es, 1e-6)

    def calculate_weights(self, asset_groups):
        """
        计算各资产组的ES风险平价权重

        参数:
        asset_groups: dict，格式 {'equity': ['510300.XSHG'], 'bond': ['511010.XSHG']}

        返回:
        weights: dict，各资产代码 → 目标权重
        """
        group_es = {}
        for group_name, assets in asset_groups.items():
            if not assets:
                continue
            es = self.calculate_es(assets[0])
            if math.isnan(es):
                es = 0.01
            group_es[group_name] = es

        if not group_es:
            return {}

        max_es = max(group_es.values())
        group_positions = {g: max_es / es for g, es in group_es.items()}
        total = sum(group_positions.values())

        weights = {}
        for group_name, position in group_positions.items():
            group_weight = position / total
            assets = asset_groups[group_name]
            per_asset = group_weight / len(assets)
            for asset in assets:
                weights[asset] = round(per_asset, 4)

        return weights

    def need_rebalance(self, context, target_weights):
        """判断是否需要再平衡（任一资产偏离超过阈值）"""
        total_value = context.portfolio.total_value
        if total_value <= 0:
            return False

        for asset, target_w in target_weights.items():
            if asset in context.portfolio.positions:
                current_w = context.portfolio.positions[asset].value / total_value
                if abs(current_w - target_w) / max(target_w, 0.01) > self.rebalance_threshold:
                    return True
        return False

    def execute_rebalance(self, context, asset_groups):
        """执行再平衡"""
        weights = self.calculate_weights(asset_groups)
        if not weights:
            return

        log.info('ES风险平价权重: ' + ', '.join(
            [f'{k}:{v:.1%}' for k, v in weights.items()]
        ))

        total_value = context.portfolio.total_value

        # 先卖出超配
        for asset, weight in weights.items():
            target_value = total_value * weight
            if asset in context.portfolio.positions:
                if context.portfolio.positions[asset].value > target_value * 1.05:
                    order_target_value(asset, target_value)

        # 再买入低配
        for asset, weight in weights.items():
            order_target_value(asset, total_value * weight)
