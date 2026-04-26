# -*- coding: utf-8 -*-
"""
统一择时模型库 (Unified Timing Model Library)

大盘择时 (Market Timing):
    - RSRS 家族 (基础/成交量加权/高级)
    - 波动率+换手率牛熊指标
    - C-VIX 恐慌指数
    - FED 模型 + 格雷厄姆指数
    - 拥挤率指标
    - 市场宽度/扩散指标
    - 投资者情绪指数
    - 市场底部特征
    - 北向资金择时
    - MACD 择时
    - 布林带择时
    - 顶底判断 (MACD背离+EMA通道)

个股择时 (Stock Timing):
    - 技术指标择时 (RSI/MA/BOLL/MACD)
    - 因子择时
    - 机器学习择时 (SVR/随机森林)
    - 扩散指数择时

信号融合:
    - 多信号融合 (加权/投票/共振/分层)
    - 仓位管理 (固定/强度/Kelly/波动率/分层)
"""

__version__ = "1.0.0"

from .base import (
    BaseTimingModel,
    BaseCompositeModel,
    TimingSignal,
    TimingResult,
    SignalDirection,
    TimingScope,
)

from .market_timing import (
    RSRSModel,
    VolumeWeightedRSRS,
    AdvancedRSRS,
    VolatilityTurnoverBullBear,
    CVIXModel,
    FEDModel,
    CongestionModel,
    MarketBreadthModel,
    DiffusionIndexModel,
    SentimentModel,
    BottomFeaturesModel,
    NorthboundModel,
    MACDTimingModel,
    BOLLTimingModel,
    TopBottomModel,
)

from .stock_timing import (
    TechnicalTimingModel,
    FactorTimingModel,
    MLTimingModel,
    StockDiffusionTimingModel,
)

from .signal_fusion import (
    SignalEnsemble,
    PositionManager,
)
