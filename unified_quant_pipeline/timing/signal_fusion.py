"""信号融合 - 多择时信号融合"""

import logging
import numpy as np
from typing import List, Dict, Optional
from .market_timing import TimingSignal, TimingCatalog

logger = logging.getLogger(__name__)


class SignalFusion:
    """多择时信号融合器

    支持多种融合方法：
    - weighted: 加权平均
    - vote: 多数投票
    - resonance: 共振检测（所有信号同向才触发）
    """

    def __init__(
        self, method: str = "weighted", weights: Optional[Dict[str, float]] = None
    ):
        """初始化信号融合器

        Args:
            method: 融合方法 ('weighted', 'vote', 'resonance')
            weights: 各模型权重字典，默认为等权
        """
        self.method = method
        self.weights = weights or {}

    def fuse(self, signals: List[TimingSignal]) -> TimingSignal:
        """融合多个择时信号

        Args:
            signals: 择时信号列表

        Returns:
            TimingSignal: 融合后的信号
        """
        if not signals:
            return TimingSignal("fused", 0, 0)

        if self.method == "weighted":
            return self._weighted_fusion(signals)
        elif self.method == "vote":
            return self._vote_fusion(signals)
        elif self.method == "resonance":
            return self._resonance_fusion(signals)
        else:
            raise ValueError(f"Unknown fusion method: {self.method}")

    def _weighted_fusion(self, signals: List[TimingSignal]) -> TimingSignal:
        """加权平均融合

        Args:
            signals: 择时信号列表

        Returns:
            TimingSignal: 加权融合后的信号
        """
        total_weight = 0.0
        weighted_sum = 0.0
        weighted_confidence = 0.0

        for s in signals:
            w = self.weights.get(s.name, 1.0)
            weighted_sum += s.strength * w
            weighted_confidence += s.confidence * w
            total_weight += w

        if total_weight == 0:
            return TimingSignal("fused", 0, 0)

        strength = weighted_sum / total_weight
        confidence = weighted_confidence / total_weight

        direction = 1 if strength > 0.1 else (-1 if strength < -0.1 else 0)

        return TimingSignal("fused", direction, strength, confidence)

    def _vote_fusion(self, signals: List[TimingSignal]) -> TimingSignal:
        """多数投票融合

        Args:
            signals: 择时信号列表

        Returns:
            TimingSignal: 投票融合后的信号
        """
        buy_votes = sum(1 for s in signals if s.direction > 0)
        sell_votes = sum(1 for s in signals if s.direction < 0)
        total = len(signals)

        if buy_votes > total * 0.6:
            direction, strength = 1, buy_votes / total
        elif sell_votes > total * 0.6:
            direction, strength = -1, -sell_votes / total
        else:
            direction, strength = 0, (buy_votes - sell_votes) / total

        avg_confidence = np.mean([s.confidence for s in signals])
        return TimingSignal("fused", direction, strength, avg_confidence)

    def _resonance_fusion(self, signals: List[TimingSignal]) -> TimingSignal:
        """共振融合 - 所有信号同向才触发

        Args:
            signals: 择时信号列表

        Returns:
            TimingSignal: 共振融合后的信号
        """
        directions = [s.direction for s in signals]

        if all(d > 0 for d in directions):
            strength = float(np.mean([s.strength for s in signals]))
            confidence = float(np.min([s.confidence for s in signals]))
            return TimingSignal("fused", 1, strength, confidence)
        elif all(d < 0 for d in directions):
            strength = float(np.mean([s.strength for s in signals]))
            confidence = float(np.min([s.confidence for s in signals]))
            return TimingSignal("fused", -1, strength, confidence)
        else:
            return TimingSignal("fused", 0, 0)
