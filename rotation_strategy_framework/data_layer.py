# -*- coding: utf-8 -*-
"""
数据层: 统一数据加载接口、多级缓存、数据对齐、批量加载、数据验证

核心类:
- DataConfig: 数据配置 (缓存路径、过期时间、数据源)
- DataCache: 多级缓存管理器 (内存+磁盘，版本控制)
- DataLoader: 统一数据加载器 (akshare封装，批量加载，数据对齐)
- DataValidator: 数据验证器 (完整性检查、异常值检测)

支持模式:
- 历史回测模式: load_history() 加载指定时间范围的历史数据
- 实盘实时模式: load_latest() 加载最近N个交易日的数据

数据格式标准:
DataFrame columns: ['datetime', 'open', 'high', 'low', 'close', 'volume', 'amount', 'openinterest']
索引: datetime (DatetimeIndex)
"""

import os
import pickle
import hashlib
import logging
import datetime
import time
from typing import Optional, Dict, List, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import OrderedDict

import numpy as np
import pandas as pd
import akshare as ak

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
# 标准列名映射 (akshare 中文列名 -> 标准英文列名)
AKSHARE_COLUMN_MAP = {
    "日期": "datetime",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
    "换手率": "turnover",
    "涨跌幅": "pct_change",
    "涨跌额": "change",
    "振幅": "amplitude",
}

# 标准 OHLCV 列
STANDARD_COLUMNS = [
    "datetime",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "openinterest",
]

# 缓存版本号 (结构变更时递增，使旧缓存失效)
CACHE_VERSION = "v1.0.0"

# 内存缓存默认最大条目数
MAX_MEMORY_CACHE_SIZE = 100


# ---------------------------------------------------------------------------
# 数据类型枚举
# ---------------------------------------------------------------------------
class AssetType(Enum):
    """资产类型"""

    ETF = "etf"
    STOCK = "stock"
    INDEX = "index"
    FUND = "fund"


class DataFrequency(Enum):
    """数据频率"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    MINUTE_60 = "60m"


class DataSource(Enum):
    """数据源"""

    AKSHARE = "akshare"


class Mode(Enum):
    """运行模式"""

    BACKTEST = "backtest"  # 历史回测模式
    LIVE = "live"  # 实盘实时模式


# ---------------------------------------------------------------------------
# DataConfig: 数据配置
# ---------------------------------------------------------------------------
@dataclass
class DataConfig:
    """
    数据配置类

    Attributes:
        cache_dir: 磁盘缓存目录路径
        cache_expire_days: 缓存过期天数 (0=永不过期)
        max_memory_cache_size: 内存缓存最大条目数
        data_source: 数据源 (默认 akshare)
        mode: 运行模式 (BACKTEST/LIVE)
        default_frequency: 默认数据频率
        parallel_workers: 并行加载线程数
        retry_count: 网络请求重试次数
        retry_delay: 重试间隔 (秒)
        fill_missing_method: 缺失数据填充方法 (ffill/interpolate/drop)
        validate_on_load: 加载时是否自动验证数据
        log_level: 日志级别
    """

    cache_dir: str = "./data_cache"
    cache_expire_days: int = 7
    max_memory_cache_size: int = MAX_MEMORY_CACHE_SIZE
    data_source: DataSource = DataSource.AKSHARE
    mode: Mode = Mode.BACKTEST
    default_frequency: DataFrequency = DataFrequency.DAILY
    parallel_workers: int = 4
    retry_count: int = 3
    retry_delay: float = 1.0
    fill_missing_method: str = "ffill"
    validate_on_load: bool = True
    log_level: int = logging.INFO

    def __post_init__(self):
        """初始化后处理: 创建缓存目录、配置日志"""
        os.makedirs(self.cache_dir, exist_ok=True)
        logging.basicConfig(
            level=self.log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )


# ---------------------------------------------------------------------------
# DataCache: 多级缓存管理器
# ---------------------------------------------------------------------------
class DataCache:
    """
    多级缓存管理器

    层级:
    1. L1 - 内存缓存 (LRU OrderedDict, 快速访问)
    2. L2 - 磁盘缓存 (pickle 文件, 持久化)

    特性:
    - 版本控制: 缓存带版本号，结构变更时自动失效
    - 过期时间: 支持设置缓存过期时间
    - 缓存键: 基于参数生成唯一哈希键
    """

    def __init__(self, config: DataConfig):
        """
        初始化缓存管理器

        Args:
            config: 数据配置
        """
        self.config = config
        # L1: 内存缓存 (LRU)
        self._memory_cache: OrderedDict[str, Tuple[pd.DataFrame, datetime.datetime]] = (
            OrderedDict()
        )
        # L2: 磁盘缓存目录
        self._disk_cache_dir = os.path.join(config.cache_dir, "disk")
        os.makedirs(self._disk_cache_dir, exist_ok=True)
        # 缓存统计
        self._stats = {"hits": 0, "misses": 0, "disk_hits": 0, "disk_misses": 0}

    def _make_cache_key(self, **kwargs) -> str:
        """
        生成缓存键 (基于参数的 MD5 哈希)

        Args:
            **kwargs: 缓存参数 (symbol, start, end, frequency, asset_type 等)

        Returns:
            缓存键字符串
        """
        # 将参数排序后拼接，确保相同参数生成相同键
        sorted_items = sorted(kwargs.items(), key=lambda x: x[0])
        param_str = "|".join(f"{k}={v}" for k, v in sorted_items)
        # 加入版本号，版本变更时自动失效
        key_raw = f"{CACHE_VERSION}|{param_str}"
        return hashlib.md5(key_raw.encode("utf-8")).hexdigest()

    def _disk_path(self, cache_key: str) -> str:
        """获取磁盘缓存文件路径"""
        return os.path.join(self._disk_cache_dir, f"{cache_key}.pkl")

    def _is_expired(self, cached_time: datetime.datetime) -> bool:
        """
        检查缓存是否过期

        Args:
            cached_time: 缓存时间

        Returns:
            是否过期
        """
        if self.config.cache_expire_days <= 0:
            return False  # 永不过期
        expire_threshold = datetime.datetime.now() - datetime.timedelta(
            days=self.config.cache_expire_days
        )
        return cached_time < expire_threshold

    def get(self, cache_key: str) -> Optional[pd.DataFrame]:
        """
        获取缓存数据 (L1 -> L2 逐级查找)

        Args:
            cache_key: 缓存键

        Returns:
            缓存的 DataFrame 或 None
        """
        # L1: 内存缓存
        if cache_key in self._memory_cache:
            data, cached_time = self._memory_cache[cache_key]
            if not self._is_expired(cached_time):
                # 移动到末尾 (LRU)
                self._memory_cache.move_to_end(cache_key)
                self._stats["hits"] += 1
                logger.debug(f"内存缓存命中: {cache_key[:8]}...")
                return data.copy()  # 返回副本防止外部修改
            else:
                # 过期则删除
                del self._memory_cache[cache_key]

        self._stats["misses"] += 1

        # L2: 磁盘缓存
        disk_path = self._disk_path(cache_key)
        if os.path.exists(disk_path):
            try:
                with open(disk_path, "rb") as f:
                    data, cached_time, version = pickle.load(f)
                if version == CACHE_VERSION and not self._is_expired(cached_time):
                    self._stats["disk_hits"] += 1
                    logger.debug(f"磁盘缓存命中: {cache_key[:8]}...")
                    # 同时加载到内存缓存
                    self._put_memory(cache_key, data)
                    return data.copy()
                else:
                    # 版本不匹配或过期，删除旧缓存
                    os.remove(disk_path)
            except (pickle.UnpicklingError, EOFError, KeyError) as e:
                logger.warning(f"磁盘缓存读取失败: {e}")
                try:
                    os.remove(disk_path)
                except OSError:
                    pass

        self._stats["disk_misses"] += 1
        return None

    def put(self, cache_key: str, data: pd.DataFrame) -> None:
        """
        存储数据到缓存 (L1 + L2)

        Args:
            cache_key: 缓存键
            data: 要缓存的 DataFrame
        """
        if data is None or data.empty:
            return

        # 写入 L1 内存缓存
        self._put_memory(cache_key, data)

        # 写入 L2 磁盘缓存
        disk_path = self._disk_path(cache_key)
        try:
            with open(disk_path, "wb") as f:
                pickle.dump((data, datetime.datetime.now(), CACHE_VERSION), f)
            logger.debug(f"磁盘缓存写入: {cache_key[:8]}...")
        except Exception as e:
            logger.warning(f"磁盘缓存写入失败: {e}")

    def _put_memory(self, cache_key: str, data: pd.DataFrame) -> None:
        """写入内存缓存 (LRU 淘汰)"""
        # 如果已存在，先删除
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
        # 如果超出容量，淘汰最旧的
        while len(self._memory_cache) >= self.config.max_memory_cache_size:
            self._memory_cache.popitem(last=False)
        # 插入新数据
        self._memory_cache[cache_key] = (data.copy(), datetime.datetime.now())

    def invalidate(self, cache_key: Optional[str] = None) -> None:
        """
        使缓存失效

        Args:
            cache_key: 指定缓存键，None 则清除所有缓存
        """
        if cache_key:
            self._memory_cache.pop(cache_key, None)
            disk_path = self._disk_path(cache_key)
            if os.path.exists(disk_path):
                os.remove(disk_path)
        else:
            self._memory_cache.clear()
            # 清除所有磁盘缓存
            for f in os.listdir(self._disk_cache_dir):
                if f.endswith(".pkl"):
                    os.remove(os.path.join(self._disk_cache_dir, f))
            logger.info("所有缓存已清除")

    def get_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0
        return {
            **self._stats,
            "memory_size": len(self._memory_cache),
            "hit_rate": round(hit_rate, 4),
        }

    def clear_memory(self) -> None:
        """仅清除内存缓存"""
        self._memory_cache.clear()


# ---------------------------------------------------------------------------
# DataValidator: 数据验证器
# ---------------------------------------------------------------------------
class DataValidator:
    """
    数据验证器

    功能:
    - 完整性检查: 检查必需列、空值、日期连续性
    - 异常值检测: 价格异常、成交量异常、涨跌幅异常
    - 数据质量评分
    """

    def __init__(self, config: DataConfig):
        """
        初始化数据验证器

        Args:
            config: 数据配置
        """
        self.config = config
        # 异常值检测阈值
        self._price_change_threshold = 0.20  # 单日涨跌幅超过 20% 视为异常
        self._volume_spike_threshold = 10.0  # 成交量超过均值 10 倍视为异常
        self._zero_price_threshold = 0.01  # 价格低于此值视为异常
        self._max_consecutive_nan = 5  # 最大连续 NaN 天数

    def validate(
        self, df: pd.DataFrame, symbol: str = "", strict: bool = False
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        验证数据质量

        Args:
            df: 待验证的 DataFrame
            symbol: 标的代码 (用于日志)
            strict: 严格模式 (发现异常则抛出异常)

        Returns:
            (清洗后的 DataFrame, 验证报告字典)

        Raises:
            ValueError: 严格模式下数据不合格时
        """
        report = {
            "symbol": symbol,
            "valid": True,
            "issues": [],
            "quality_score": 100.0,
        }

        if df is None or df.empty:
            report["valid"] = False
            report["issues"].append("数据为空")
            report["quality_score"] = 0.0
            if strict:
                raise ValueError(f"[{symbol}] 数据为空")
            return df, report

        df = df.copy()

        # 1. 检查必需列
        df, report = self._check_required_columns(df, report, symbol, strict)

        # 2. 检查日期索引
        df, report = self._check_datetime_index(df, report, symbol, strict)

        # 3. 检查空值
        df, report = self._check_nan_values(df, report, symbol, strict)

        # 4. 检查价格异常
        df, report = self._check_price_anomalies(df, report, symbol, strict)

        # 5. 检查成交量异常
        df, report = self._check_volume_anomalies(df, report, symbol, strict)

        # 6. 检查时间顺序
        df, report = self._check_time_order(df, report, symbol, strict)

        # 计算质量评分
        penalty = len(report["issues"]) * 10
        report["quality_score"] = max(0.0, 100.0 - penalty)
        if report["quality_score"] < 50:
            report["valid"] = False

        logger.info(
            f"[{symbol}] 数据验证: 质量评分={report['quality_score']:.1f}, "
            f"问题数={len(report['issues'])}"
        )

        return df, report

    def _check_required_columns(
        self, df: pd.DataFrame, report: Dict, symbol: str, strict: bool
    ) -> Tuple[pd.DataFrame, Dict]:
        """检查必需列是否存在"""
        required = ["open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            msg = f"缺少必需列: {missing}"
            report["issues"].append(msg)
            logger.warning(f"[{symbol}] {msg}")
            if strict:
                raise ValueError(f"[{symbol}] {msg}")
        return df, report

    def _check_datetime_index(
        self, df: pd.DataFrame, report: Dict, symbol: str, strict: bool
    ) -> Tuple[pd.DataFrame, Dict]:
        """检查并修复日期索引"""
        # 如果 datetime 是列而非索引，设置为索引
        if "datetime" in df.columns and not isinstance(df.index, pd.DatetimeIndex):
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.set_index("datetime")
            logger.debug(f"[{symbol}] 已将 datetime 列设为索引")

        # 确保索引是 DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception as e:
                msg = f"无法转换为 DatetimeIndex: {e}"
                report["issues"].append(msg)
                if strict:
                    raise ValueError(f"[{symbol}] {msg}")

        # 检查是否有重复索引
        dup_count = df.index.duplicated().sum()
        if dup_count > 0:
            msg = f"存在 {dup_count} 个重复日期，已去重"
            report["issues"].append(msg)
            df = df[~df.index.duplicated(keep="first")]
            logger.warning(f"[{symbol}] {msg}")

        # 检查时间顺序
        if not df.index.is_monotonic_increasing:
            df = df.sort_index()
            report["issues"].append("日期已重新排序")

        return df, report

    def _check_nan_values(
        self, df: pd.DataFrame, report: Dict, symbol: str, strict: bool
    ) -> Tuple[pd.DataFrame, Dict]:
        """检查空值并填充"""
        nan_cols = df[["open", "high", "low", "close", "volume"]].isna().sum()
        total_nan = nan_cols.sum()

        if total_nan > 0:
            msg = f"发现 {total_nan} 个空值: {nan_cols[nan_cols > 0].to_dict()}"
            report["issues"].append(msg)
            logger.warning(f"[{symbol}] {msg}")

            # 检查连续 NaN
            for col in ["close", "volume"]:
                if col not in df.columns:
                    continue
                is_nan = df[col].isna()
                if is_nan.any():
                    # 找出最长连续 NaN 段
                    nan_groups = (~is_nan).cumsum()
                    nan_lengths = is_nan.groupby(nan_groups).sum()
                    max_nan_len = nan_lengths.max() if len(nan_lengths) > 0 else 0
                    if max_nan_len > self._max_consecutive_nan:
                        msg = f"{col} 存在连续 {max_nan_len} 天 NaN (阈值: {self._max_consecutive_nan})"
                        report["issues"].append(msg)
                        if strict:
                            raise ValueError(f"[{symbol}] {msg}")

            # 填充空值
            method = self.config.fill_missing_method
            if method == "ffill":
                df = df.ffill()
            elif method == "interpolate":
                df = df.interpolate(method="linear")
            # 'drop' 不填充，保留 NaN

            # 填充后仍有 NaN 则用 0 填充 volume/amount
            if "volume" in df.columns:
                df["volume"] = df["volume"].fillna(0)
            if "amount" in df.columns:
                df["amount"] = df["amount"].fillna(0)

        return df, report

    def _check_price_anomalies(
        self, df: pd.DataFrame, report: Dict, symbol: str, strict: bool
    ) -> Tuple[pd.DataFrame, Dict]:
        """检查价格异常 (零价格、涨跌幅过大)"""
        price_cols = ["open", "high", "low", "close"]
        available_cols = [c for c in price_cols if c in df.columns]

        if not available_cols:
            return df, report

        # 检查零/负价格
        for col in available_cols:
            zero_mask = df[col] <= self._zero_price_threshold
            zero_count = zero_mask.sum()
            if zero_count > 0:
                msg = f"{col} 有 {zero_count} 个异常低价 (<= {self._zero_price_threshold})"
                report["issues"].append(msg)
                # 将异常价格替换为 NaN，后续会被填充
                df.loc[zero_mask, col] = np.nan
                logger.warning(f"[{symbol}] {msg}")

        # 检查涨跌幅异常 (仅当有 close 列时)
        if "close" in df.columns and len(df) > 1:
            pct_change = df["close"].pct_change().abs()
            extreme_mask = pct_change > self._price_change_threshold
            extreme_count = extreme_mask.sum()
            if extreme_count > 0:
                extreme_dates = df.index[extreme_mask].tolist()
                msg = f"发现 {extreme_count} 个异常涨跌幅 (> {self._price_change_threshold:.0%}): {extreme_dates[:3]}"
                report["issues"].append(msg)
                logger.warning(f"[{symbol}] {msg}")

        return df, report

    def _check_volume_anomalies(
        self, df: pd.DataFrame, report: Dict, symbol: str, strict: bool
    ) -> Tuple[pd.DataFrame, Dict]:
        """检查成交量异常"""
        if "volume" not in df.columns:
            return df, report

        vol = df["volume"]
        # 排除零成交量 (停牌日)
        nonzero_vol = vol[vol > 0]
        if len(nonzero_vol) < 10:
            return df, report

        mean_vol = nonzero_vol.mean()
        std_vol = nonzero_vol.std()

        # 成交量突增检测 (超过均值 N 倍)
        spike_mask = vol > mean_vol * self._volume_spike_threshold
        spike_count = spike_mask.sum()
        if spike_count > 0:
            msg = f"发现 {spike_count} 个成交量突增日 (> 均值{self._volume_spike_threshold:.0f}倍)"
            report["issues"].append(msg)
            logger.debug(f"[{symbol}] {msg}")

        # 成交量为负
        neg_mask = vol < 0
        neg_count = neg_mask.sum()
        if neg_count > 0:
            msg = f"发现 {neg_count} 个负成交量"
            report["issues"].append(msg)
            df.loc[neg_mask, "volume"] = 0

        return df, report

    def _check_time_order(
        self, df: pd.DataFrame, report: Dict, symbol: str, strict: bool
    ) -> Tuple[pd.DataFrame, Dict]:
        """检查时间顺序和日期连续性"""
        if not isinstance(df.index, pd.DatetimeIndex) or len(df) < 2:
            return df, report

        # 检查是否有未来数据
        today = pd.Timestamp(datetime.date.today())
        future_mask = df.index > today
        future_count = future_mask.sum()
        if future_count > 0:
            msg = f"发现 {future_count} 个未来日期"
            report["issues"].append(msg)
            df = df[~future_mask]
            logger.warning(f"[{symbol}] {msg}")

        return df, report


# ---------------------------------------------------------------------------
# DataLoader: 统一数据加载器
# ---------------------------------------------------------------------------
class DataLoader:
    """
    统一数据加载器

    功能:
    - 封装 akshare 数据获取接口
    - 支持 ETF/股票/指数等多种资产类型
    - 批量并行加载
    - 数据对齐 (统一日期索引)
    - 支持历史回测和实盘实时两种模式
    """

    def __init__(self, config: Optional[DataConfig] = None):
        """
        初始化数据加载器

        Args:
            config: 数据配置，None 则使用默认配置
        """
        self.config = config or DataConfig()
        self.cache = DataCache(self.config)
        self.validator = DataValidator(self.config)

    # ===================================================================
    # 核心公共方法
    # ===================================================================

    def load_history(
        self,
        symbols: Union[str, List[str]],
        start: str,
        end: Optional[str] = None,
        frequency: DataFrequency = DataFrequency.DAILY,
        asset_type: AssetType = AssetType.STOCK,
        validate: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """
        加载历史数据 (回测模式)

        Args:
            symbols: 标的代码列表 (单个字符串或列表)
            start: 开始日期 (YYYYMMDD 或 YYYY-MM-DD)
            end: 结束日期 (YYYYMMDD 或 YYYY-MM-DD)，None 则为今天
            frequency: 数据频率
            asset_type: 资产类型
            validate: 是否验证数据

        Returns:
            dict[symbol, DataFrame] 每个标的数据
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        if end is None:
            end = datetime.date.today().strftime("%Y%m%d")

        start = self._normalize_date(start)
        end = self._normalize_date(end)

        logger.info(f"加载历史数据: {len(symbols)} 个标的, {start} ~ {end}")

        # 批量加载
        results = self._batch_load(
            symbols=symbols,
            start=start,
            end=end,
            frequency=frequency,
            asset_type=asset_type,
        )

        # 可选验证
        if validate:
            validated = {}
            for sym, df in results.items():
                cleaned, report = self.validator.validate(df, symbol=sym, strict=False)
                validated[sym] = cleaned
            results = validated

        return results

    def load_latest(
        self,
        symbols: Union[str, List[str]],
        lookback_days: int = 120,
        asset_type: AssetType = AssetType.STOCK,
        validate: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """
        加载最新数据 (实盘模式)

        从当前日期往前推 lookback_days 个自然日的数据

        Args:
            symbols: 标的代码列表
            lookback_days: 回溯天数 (自然日)
            asset_type: 资产类型
            validate: 是否验证数据

        Returns:
            dict[symbol, DataFrame] 每个标的最新数据
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=lookback_days)

        start = start_date.strftime("%Y%m%d")
        end = end_date.strftime("%Y%m%d")

        logger.info(
            f"加载最新数据 (实盘): {len(symbols)} 个标的, 回溯 {lookback_days} 天"
        )

        # 使用较短的缓存过期时间 (实盘模式需要更新的数据)
        return self.load_history(
            symbols=symbols,
            start=start,
            end=end,
            asset_type=asset_type,
            validate=validate,
        )

    def get_unified_data(
        self,
        symbols: Union[str, List[str]],
        start: str,
        end: Optional[str] = None,
        asset_type: AssetType = AssetType.STOCK,
        fill_method: str = "ffill",
    ) -> pd.DataFrame:
        """
        获取对齐后的统一数据面板

        将多个标的的数据对齐到统一的日期索引，返回 MultiIndex DataFrame
        或宽表格式的 close 价格矩阵

        Args:
            symbols: 标的代码列表
            start: 开始日期
            end: 结束日期
            asset_type: 资产类型
            fill_method: 缺失值填充方法

        Returns:
            对齐后的 DataFrame (columns 为 MultiIndex: [symbol, field])
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        # 加载所有标的
        data_dict = self.load_history(
            symbols=symbols,
            start=start,
            end=end,
            asset_type=asset_type,
            validate=True,
        )

        if not data_dict:
            return pd.DataFrame()

        # 对齐数据
        aligned = self._align_data(data_dict, fill_method=fill_method)
        return aligned

    def get_close_matrix(
        self,
        symbols: Union[str, List[str]],
        start: str,
        end: Optional[str] = None,
        asset_type: AssetType = AssetType.STOCK,
    ) -> pd.DataFrame:
        """
        获取收盘价矩阵 (columns=标的, index=日期)

        用于组合优化、相关性分析等场景

        Args:
            symbols: 标的代码列表
            start: 开始日期
            end: 结束日期
            asset_type: 资产类型

        Returns:
            DataFrame (index=datetime, columns=symbols, values=close)
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        data_dict = self.load_history(
            symbols=symbols,
            start=start,
            end=end,
            asset_type=asset_type,
            validate=True,
        )

        # 提取 close 列并对齐
        close_dict = {}
        for sym, df in data_dict.items():
            if "close" in df.columns:
                close_dict[sym] = df["close"]

        if not close_dict:
            return pd.DataFrame()

        # 合并为宽表
        close_df = pd.DataFrame(close_dict)
        # 前向填充缺失值 (停牌日)
        close_df = close_df.ffill()
        # 删除全 NaN 的行和列
        close_df = close_df.dropna(how="all").dropna(axis=1, how="all")

        return close_df

    # ===================================================================
    # 内部方法: 数据获取
    # ===================================================================

    def _fetch_single(
        self,
        symbol: str,
        start: str,
        end: str,
        frequency: DataFrequency,
        asset_type: AssetType,
    ) -> pd.DataFrame:
        """
        获取单个标的数据 (带缓存)

        Args:
            symbol: 标的代码
            start: 开始日期
            end: 结束日期
            frequency: 数据频率
            asset_type: 资产类型

        Returns:
            原始 DataFrame
        """
        # 生成缓存键
        cache_key = self.cache._make_cache_key(
            symbol=symbol,
            start=start,
            end=end,
            frequency=frequency.value,
            asset_type=asset_type.value,
        )

        # 尝试从缓存获取
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # 从数据源获取
        df = self._fetch_from_source(symbol, start, end, frequency, asset_type)

        if df is not None and not df.empty:
            # 标准化列名
            df = self._standardize_columns(df)
            # 存入缓存
            self.cache.put(cache_key, df)

        return df

    def _fetch_from_source(
        self,
        symbol: str,
        start: str,
        end: str,
        frequency: DataFrequency,
        asset_type: AssetType,
    ) -> Optional[pd.DataFrame]:
        """
        从 akshare 获取数据

        Args:
            symbol: 标的代码
            start: 开始日期
            end: 结束日期
            frequency: 数据频率
            asset_type: 资产类型

        Returns:
            原始 DataFrame
        """
        for attempt in range(self.config.retry_count):
            try:
                if asset_type == AssetType.INDEX:
                    return self._fetch_index(symbol, start, end, frequency)
                elif asset_type == AssetType.ETF:
                    return self._fetch_etf(symbol, start, end, frequency)
                elif asset_type == AssetType.STOCK:
                    return self._fetch_stock(symbol, start, end, frequency)
                elif asset_type == AssetType.FUND:
                    return self._fetch_fund(symbol, start, end, frequency)
                else:
                    logger.warning(f"不支持的资产类型: {asset_type}")
                    return None
            except Exception as e:
                logger.warning(
                    f"获取 {symbol} 数据失败 (尝试 {attempt + 1}/{self.config.retry_count}): {e}"
                )
                if attempt < self.config.retry_count - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    logger.error(f"获取 {symbol} 数据最终失败: {e}")
                    return None

    def _fetch_index(
        self, symbol: str, start: str, end: str, frequency: DataFrequency
    ) -> pd.DataFrame:
        """获取指数数据"""
        # 确保 symbol 是纯数字 (去掉 sh/sz 前缀)
        clean_symbol = (
            symbol.replace("sh", "")
            .replace("sz", "")
            .replace("SH", "")
            .replace("SZ", "")
        )

        period = self._frequency_to_akshare_period(frequency)

        df = ak.index_zh_a_hist(
            symbol=clean_symbol,
            period=period,
            start_date=start,
            end_date=end,
        )
        return df

    def _fetch_etf(
        self, symbol: str, start: str, end: str, frequency: DataFrequency
    ) -> pd.DataFrame:
        """获取 ETF 数据"""
        # 确保 symbol 是纯数字
        clean_symbol = (
            symbol.replace("sh", "")
            .replace("sz", "")
            .replace("SH", "")
            .replace("SZ", "")
        )

        # ETF 使用基金接口或指数接口
        # akshare 的 fund_etf_hist_em 支持 ETF 历史数据
        try:
            df = ak.fund_etf_hist_em(
                symbol=clean_symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq",  # 前复权
            )
            return df
        except Exception:
            # 回退到指数接口
            logger.debug(f"ETF {symbol} fund_etf_hist_em 失败，尝试 index_zh_a_hist")
            return self._fetch_index(clean_symbol, start, end, frequency)

    def _fetch_stock(
        self, symbol: str, start: str, end: str, frequency: DataFrequency
    ) -> pd.DataFrame:
        """获取股票数据"""
        # 确保 symbol 格式正确
        clean_symbol = (
            symbol.replace("sh", "")
            .replace("sz", "")
            .replace("SH", "")
            .replace("SZ", "")
        )

        try:
            df = ak.stock_zh_a_hist(
                symbol=clean_symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq",  # 前复权
            )
            return df
        except Exception as e:
            logger.error(f"获取股票 {symbol} 数据失败: {e}")
            raise

    def _fetch_fund(
        self, symbol: str, start: str, end: str, frequency: DataFrequency
    ) -> pd.DataFrame:
        """获取基金数据"""
        clean_symbol = (
            symbol.replace("sh", "")
            .replace("sz", "")
            .replace("SH", "")
            .replace("SZ", "")
        )

        try:
            df = ak.fund_open_fund_info_em(
                symbol=clean_symbol, indicator="单位净值走势"
            )
            return df
        except Exception as e:
            logger.error(f"获取基金 {symbol} 数据失败: {e}")
            raise

    # ===================================================================
    # 内部方法: 批量加载 & 对齐
    # ===================================================================

    def _batch_load(
        self,
        symbols: List[str],
        start: str,
        end: str,
        frequency: DataFrequency,
        asset_type: AssetType,
    ) -> Dict[str, pd.DataFrame]:
        """
        批量并行加载多个标的数据

        Args:
            symbols: 标的列表
            start: 开始日期
            end: 结束日期
            frequency: 数据频率
            asset_type: 资产类型

        Returns:
            dict[symbol, DataFrame]
        """
        results = {}
        workers = min(self.config.parallel_workers, len(symbols))

        if workers <= 1 or len(symbols) <= 1:
            # 单线程模式
            for sym in symbols:
                df = self._fetch_single(sym, start, end, frequency, asset_type)
                if df is not None and not df.empty:
                    results[sym] = df
                else:
                    logger.warning(f"标的 {sym} 无数据")
        else:
            # 多线程并行加载
            logger.info(f"使用 {workers} 个线程并行加载 {len(symbols)} 个标的")
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        self._fetch_single, sym, start, end, frequency, asset_type
                    ): sym
                    for sym in symbols
                }
                for future in as_completed(futures):
                    sym = futures[future]
                    try:
                        df = future.result()
                        if df is not None and not df.empty:
                            results[sym] = df
                        else:
                            logger.warning(f"标的 {sym} 无数据")
                    except Exception as e:
                        logger.error(f"标的 {sym} 加载异常: {e}")

        logger.info(f"批量加载完成: {len(results)}/{len(symbols)} 个标的成功")
        return results

    def _align_data(
        self,
        data_dict: Dict[str, pd.DataFrame],
        fill_method: str = "ffill",
    ) -> pd.DataFrame:
        """
        将多个标的数据对齐到统一日期索引

        Args:
            data_dict: dict[symbol, DataFrame]
            fill_method: 缺失值填充方法

        Returns:
            MultiIndex DataFrame (columns: [symbol, field])
        """
        if not data_dict:
            return pd.DataFrame()

        # 确保所有 DataFrame 有 datetime 索引
        for sym, df in data_dict.items():
            if not isinstance(df.index, pd.DatetimeIndex):
                if "datetime" in df.columns:
                    df = df.set_index("datetime")
                else:
                    df.index = pd.to_datetime(df.index)
                data_dict[sym] = df

        # 使用 pandas concat 创建 MultiIndex DataFrame
        aligned = pd.concat(data_dict, axis=1)
        aligned.columns.names = ["symbol", "field"]

        # 按日期排序
        aligned = aligned.sort_index()

        # 填充缺失值
        if fill_method == "ffill":
            aligned = aligned.ffill()
        elif fill_method == "interpolate":
            aligned = aligned.interpolate(method="linear")

        return aligned

    # ===================================================================
    # 内部方法: 工具函数
    # ===================================================================

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化 DataFrame 列名

        将 akshare 返回的中文列名转换为标准英文列名

        Args:
            df: 原始 DataFrame

        Returns:
            标准化后的 DataFrame
        """
        df = df.copy()

        # 重命名列
        rename_map = {}
        for cn_col, en_col in AKSHARE_COLUMN_MAP.items():
            if cn_col in df.columns:
                rename_map[cn_col] = en_col

        if rename_map:
            df = df.rename(columns=rename_map)

        # 确保 datetime 列为索引
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.set_index("datetime")

        # 确保索引是 DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # 排序
        df = df.sort_index()

        # 添加 openinterest 列 (如果不存在，A股通常为 0 或空)
        if "openinterest" not in df.columns:
            df["openinterest"] = 0.0

        # 确保数值列为数值类型
        numeric_cols = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "openinterest",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def _normalize_date(self, date_str: str) -> str:
        """
        标准化日期格式为 YYYYMMDD

        Args:
            date_str: 日期字符串 (支持 YYYYMMDD, YYYY-MM-DD)

        Returns:
            YYYYMMDD 格式
        """
        date_str = date_str.strip().replace("-", "").replace("/", "")
        return date_str

    def _frequency_to_akshare_period(self, frequency: DataFrequency) -> str:
        """
        将 DataFrequency 转换为 akshare 的 period 参数

        Args:
            frequency: 数据频率枚举

        Returns:
            akshare period 字符串
        """
        mapping = {
            DataFrequency.DAILY: "daily",
            DataFrequency.WEEKLY: "weekly",
            DataFrequency.MONTHLY: "monthly",
        }
        return mapping.get(frequency, "daily")

    # ===================================================================
    # 辅助方法
    # ===================================================================

    def get_trading_dates(
        self,
        start: str,
        end: str,
        reference_symbol: str = "000300",
    ) -> pd.DatetimeIndex:
        """
        获取交易日历 (基于参考指数的交易日)

        Args:
            start: 开始日期
            end: 结束日期
            reference_symbol: 参考指数代码 (默认沪深300)

        Returns:
            交易日 DatetimeIndex
        """
        start = self._normalize_date(start)
        end = self._normalize_date(end)

        df = self._fetch_index(reference_symbol, start, end, DataFrequency.DAILY)
        df = self._standardize_columns(df)
        return df.index

    def get_symbol_list(
        self,
        asset_type: AssetType = AssetType.ETF,
    ) -> List[str]:
        """
        获取标的列表

        Args:
            asset_type: 资产类型

        Returns:
            标的代码列表
        """
        try:
            if asset_type == AssetType.ETF:
                # 获取 ETF 列表
                df = ak.fund_etf_spot_em()
                if "代码" in df.columns:
                    return df["代码"].tolist()
                elif "symbol" in df.columns:
                    return df["symbol"].tolist()
            elif asset_type == AssetType.INDEX:
                # 常用指数列表
                return ["000300", "000905", "000852", "000001", "399006"]
            elif asset_type == AssetType.STOCK:
                # 获取 A 股列表
                df = ak.stock_zh_a_spot_em()
                if "代码" in df.columns:
                    return df["代码"].tolist()
        except Exception as e:
            logger.error(f"获取标的列表失败: {e}")

        return []

    def invalidate_cache(self, symbol: Optional[str] = None) -> None:
        """
        使缓存失效

        Args:
            symbol: 指定标的，None 则清除所有缓存
        """
        if symbol:
            # 清除该标的所有缓存 (需要遍历，简化处理: 清除全部)
            logger.info(f"清除 {symbol} 相关缓存 (全量清除)")
            self.cache.invalidate()
        else:
            self.cache.invalidate()

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return self.cache.get_stats()


# ---------------------------------------------------------------------------
# 便捷函数 (模块级 API)
# ---------------------------------------------------------------------------


def create_loader(config: Optional[DataConfig] = None) -> DataLoader:
    """
    创建数据加载器 (工厂函数)

    Args:
        config: 数据配置

    Returns:
        DataLoader 实例
    """
    return DataLoader(config)


def load_history_data(
    symbols: Union[str, List[str]],
    start: str,
    end: Optional[str] = None,
    cache_dir: str = "./data_cache",
    asset_type: AssetType = AssetType.STOCK,
) -> Dict[str, pd.DataFrame]:
    """
    便捷函数: 加载历史数据

    Args:
        symbols: 标的代码
        start: 开始日期
        end: 结束日期
        cache_dir: 缓存目录
        asset_type: 资产类型

    Returns:
        dict[symbol, DataFrame]
    """
    config = DataConfig(cache_dir=cache_dir, mode=Mode.BACKTEST)
    loader = DataLoader(config)
    return loader.load_history(symbols, start, end, asset_type=asset_type)


def load_live_data(
    symbols: Union[str, List[str]],
    lookback_days: int = 120,
    cache_dir: str = "./data_cache",
    asset_type: AssetType = AssetType.STOCK,
) -> Dict[str, pd.DataFrame]:
    """
    便捷函数: 加载实盘数据

    Args:
        symbols: 标的代码
        lookback_days: 回溯天数
        cache_dir: 缓存目录
        asset_type: 资产类型

    Returns:
        dict[symbol, DataFrame]
    """
    config = DataConfig(
        cache_dir=cache_dir,
        mode=Mode.LIVE,
        cache_expire_days=1,  # 实盘模式缓存仅 1 天有效
    )
    loader = DataLoader(config)
    return loader.load_latest(symbols, lookback_days, asset_type=asset_type)


# ---------------------------------------------------------------------------
# 使用示例
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 示例 1: 历史回测模式
    print("=" * 60)
    print("示例 1: 历史回测模式")
    print("=" * 60)

    config = DataConfig(
        cache_dir="./data_cache",
        mode=Mode.BACKTEST,
        parallel_workers=2,
        cache_expire_days=7,
    )
    loader = DataLoader(config)

    # 加载沪深300和中证500指数历史数据
    symbols = ["000300", "000905"]
    data = loader.load_history(
        symbols=symbols,
        start="20230101",
        end="20231231",
        asset_type=AssetType.INDEX,
    )

    for sym, df in data.items():
        print(f"\n{sym}: {len(df)} 条记录")
        print(df.tail(3))

    # 示例 2: 获取对齐数据
    print("\n" + "=" * 60)
    print("示例 2: 获取对齐数据面板")
    print("=" * 60)

    unified = loader.get_unified_data(
        symbols=symbols,
        start="20230101",
        end="20230331",
        asset_type=AssetType.INDEX,
    )
    print(f"对齐数据形状: {unified.shape}")
    print(unified.tail(3))

    # 示例 3: 获取收盘价矩阵
    print("\n" + "=" * 60)
    print("示例 3: 收盘价矩阵")
    print("=" * 60)

    close_matrix = loader.get_close_matrix(
        symbols=symbols,
        start="20230101",
        end="20230331",
        asset_type=AssetType.INDEX,
    )
    print(f"收盘价矩阵形状: {close_matrix.shape}")
    print(close_matrix.tail(3))

    # 示例 4: 缓存统计
    print("\n" + "=" * 60)
    print("示例 4: 缓存统计")
    print("=" * 60)

    stats = loader.get_cache_stats()
    print(f"缓存统计: {stats}")

    # 示例 5: 获取交易日历
    print("\n" + "=" * 60)
    print("示例 5: 交易日历")
    print("=" * 60)

    trading_dates = loader.get_trading_dates("20230101", "20230131")
    print(f"2023年1月交易日: {len(trading_dates)} 天")
    print(trading_dates)
