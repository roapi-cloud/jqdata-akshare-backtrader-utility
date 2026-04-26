"""
数据源适配层 (DataFeed Adapter)
================================

统一的数据加载接口，支持多种数据源（AkShare 为主）。
提供缓存机制避免重复下载。
"""

import backtrader as bt
import pandas as pd
from typing import List, Dict, Union, Optional
from datetime import date, datetime
import os

from ..data_gateways.symbol import format_stock_symbol, to_ak


def format_symbol_for_akshare(symbol: str) -> str:
    """
    将聚宽/多种格式的股票代码统一转为6位数字

    支持格式：
    - sh600000 / sz000001
    - 600000.XSHG / 000001.XSHE
    - 600000 / 000001
    """
    numeric = format_stock_symbol(symbol)
    if numeric is None:
        raise ValueError(f"无法识别股票代码: {symbol}")
    return numeric


def add_prefix_symbol(symbol: str) -> str:
    """为纯数字代码添加 sh/sz 前缀"""
    return to_ak(symbol)


class AkshareDataFeed:
    """
    AkShare 数据源适配器

    提供统一的 K 线数据获取接口，支持：
    - A股日线/分钟线
    - ETF/基金
    - 指数
    """

    def __init__(self, cache_dir: str = "./data_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_stock_daily(
        self,
        symbol: str,
        start_date: Union[str, date],
        end_date: Union[str, date],
        adjust: str = "qfq",
        force_update: bool = False
    ) -> bt.feeds.PandasData:
        """
        获取 A 股日线数据

        Args:
            symbol: 股票代码（支持多种格式）
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权方式 ('qfq', 'hfq', '')
            force_update: 强制更新缓存

        Returns:
            Backtrader PandasData 对象
        """
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")

        # 标准化代码
        ak_code = format_symbol_for_akshare(symbol)
        prefix_code = add_prefix_symbol(symbol)

        # 缓存文件
        cache_file = os.path.join(
            self.cache_dir,
            f"{prefix_code}_daily_{adjust}.pkl"
        )

        # 解析日期
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')

        # 检查缓存
        need_download = force_update or not os.path.exists(cache_file)
        df = None

        if not need_download:
            try:
                df = pd.read_pickle(cache_file)
                df['date'] = pd.to_datetime(df['date'])
                # 允许最早日期在 start_date 后 7 天内（非交易日偏移）
                from datetime import timedelta
                if df['date'].min().date() > (start_date + timedelta(days=7)):
                    need_download = True
            except Exception:
                need_download = True

        # 下载数据
        if need_download:
            df = ak.stock_zh_a_hist(
                symbol=ak_code,
                period="daily",
                start_date=start_str,
                end_date=end_str,
                adjust=adjust if adjust != 'none' else None
            )
            if df.empty:
                raise ValueError(f"无数据返回: {symbol}")

            df['date'] = pd.to_datetime(df['日期'])
            df.to_pickle(cache_file)

        # 筛选日期并标准化列名
        df['date'] = pd.to_datetime(df['date'])
        df = df[(df['date'] >= pd.Timestamp(start_date)) & (df['date'] <= pd.Timestamp(end_date))]

        # 兼容中文列名（缓存可能保留原始 akshare 格式）
        col_map = {
            'date': 'datetime',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
        }
        df.rename(columns=col_map, inplace=True)

        df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
        df['openinterest'] = 0

        return bt.feeds.PandasData(
            dataname=df,
            datetime='datetime',
            open='open',
            high='high',
            low='low',
            close='close',
            volume='volume',
            openinterest='openinterest',
            name=prefix_code
        )

    def get_etf_daily(
        self,
        symbol: str,
        start_date: Union[str, date],
        end_date: Union[str, date],
        force_update: bool = False
    ) -> bt.feeds.PandasData:
        """
        获取 ETF 日线数据

        Args:
            symbol: ETF 代码（如 '510300'）
            start_date: 开始日期
            end_date: 结束日期
            force_update: 强制更新缓存

        Returns:
            Backtrader PandasData 对象
        """
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")

        cache_file = os.path.join(
            self.cache_dir,
            f"etf_{symbol}.pkl"
        )

        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        need_download = force_update or not os.path.exists(cache_file)
        df = None

        if not need_download:
            try:
                df = pd.read_pickle(cache_file)
                df['date'] = pd.to_datetime(df['date'])
                if df['date'].min().date() > start_date or df['date'].max().date() < end_date:
                    need_download = True
            except Exception:
                need_download = True

        if need_download:
            df = ak.fund_etf_hist_em(symbol=symbol)
            if df.empty:
                raise ValueError(f"无数据返回: {symbol}")
            df['date'] = pd.to_datetime(df['日期'])
            df.to_pickle(cache_file)

        df['date'] = pd.to_datetime(df['date'])
        df = df[(df['date'] >= pd.Timestamp(start_date)) & (df['date'] <= pd.Timestamp(end_date))]

        df.rename(columns={
            'date': 'datetime',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume'
        }, inplace=True)

        df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
        df['openinterest'] = 0

        return bt.feeds.PandasData(
            dataname=df,
            datetime='datetime',
            open='open',
            high='high',
            low='low',
            close='close',
            volume='volume',
            openinterest='openinterest',
            name=symbol
        )

    def get_index_daily(
        self,
        symbol: str,
        start_date: Union[str, date],
        end_date: Union[str, date]
    ) -> pd.Series:
        """
        获取指数日线数据（用于基准对比）

        Returns:
            净值序列（归一化到起始日）
        """
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")

        df = ak.index_zh_a_hist(symbol=symbol, period='daily')
        df['date'] = pd.to_datetime(df['日期'])

        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        df = df[(df['date'] >= pd.Timestamp(start_date)) & (df['date'] <= pd.Timestamp(end_date))]
        df = df.sort_values('date')
        df['nav'] = df['收盘'] / df['收盘'].iloc[0]

        return df.set_index('date')['nav']


def load_datafeeds(
    symbols: List[str],
    start_date: Union[str, date],
    end_date: Union[str, date],
    data_config: Optional[Dict] = None
) -> List[bt.feeds.PandasData]:
    """
    批量加载数据

    这是最小接口之一：
    - 输入：标的列表、时间范围
    - 输出：Backtrader DataFeed 列表

    Args:
        symbols: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        data_config: 数据源配置

    Returns:
        DataFeed 列表
    """
    data_config = data_config or {}
    source = data_config.get('source', 'akshare')
    cache_dir = data_config.get('cache_dir', './data_cache')
    adjust = data_config.get('adjust', 'qfq')
    force_update = data_config.get('force_update', False)

    if source != 'akshare':
        raise NotImplementedError(f"暂不支持数据源: {source}")

    feed = AkshareDataFeed(cache_dir=cache_dir)
    datafeeds = []

    for symbol in symbols:
        # 根据代码特征判断类型
        ak_code = format_symbol_for_akshare(symbol)

        # ETF 代码特征：510xxx, 511xxx, 159xxx, 518xxx
        if ak_code[:3] in ('510', '511', '159', '518', '512', '513', '515', '516', '560', '561', '562'):
            data = feed.get_etf_daily(symbol, start_date, end_date, force_update)
        else:
            data = feed.get_stock_daily(symbol, start_date, end_date, adjust, force_update)

        datafeeds.append(data)

    return datafeeds


def get_price(
    symbols: Union[str, List[str]],
    start_date: Union[str, date],
    end_date: Union[str, date],
    frequency: str = 'daily',
    fields: Optional[List[str]] = None,
    adjust: str = 'qfq',
    cache_dir: str = './data_cache',
    force_update: bool = False
) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """
    聚宽风格 get_price 兼容接口

    Args:
        symbols: 单个或多个股票代码
        start_date: 开始日期
        end_date: 结束日期
        frequency: 频率 ('daily', '1m', '5m'等)
        fields: 指定字段
        adjust: 复权方式
        cache_dir: 缓存目录
        force_update: 强制更新

    Returns:
        DataFrame 或 Dict[code, DataFrame]
    """
    if isinstance(symbols, str):
        symbols = [symbols]
        return_dict = False
    else:
        return_dict = True

    feed = AkshareDataFeed(cache_dir=cache_dir)
    result = {}

    for symbol in symbols:
        ak_code = format_symbol_for_akshare(symbol)
        prefix_code = add_prefix_symbol(symbol)

        # 简化实现：仅支持日线
        if frequency == 'daily':
            data = feed.get_stock_daily(symbol, start_date, end_date, adjust, force_update)
            # 从 DataFeed 中提取 DataFrame
            df = data._dataname.copy()
        else:
            raise NotImplementedError(f"暂不支持频率: {frequency}")

        if fields:
            keep = ['datetime'] + [f for f in fields if f in df.columns]
            df = df[keep]

        result[prefix_code] = df

    return result if return_dict else result[symbols[0]]
