"""
市场状态与情绪开关（Regime Filters）

让新策略先过一个可配置的总闸门，再执行 alpha 逻辑。
"""

from .contract import RegimeState, SubSignal, RiskFlag, RegimeFilterOutput
from .config import DEFAULT_REGIME_CONFIG, merge_config
from .engine import run_regime_gate

__all__ = [
    "RegimeState",
    "SubSignal",
    "RiskFlag",
    "RegimeFilterOutput",
    "DEFAULT_REGIME_CONFIG",
    "merge_config",
    "run_regime_gate",
]
