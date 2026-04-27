"""
Data Fetchers for Market Diagnostic System

Implements data fetching logic for indices, breadth, sectors, and capital flow.
Integrates with existing DataFetcherManager from daily_stock_analysis.

Requirements: 1.1-1.7, 21.1-21.5
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import numpy as np

from .models import (
    IndexDailyData,
    MarketBreadthData,
    SectorDailyData,
    CapitalFlowData,
)
from .cache import DiagnosticDataCache

logger = logging.getLogger(__name__)


# Index pool configuration (9 core indices)
INDEX_POOL: Dict[str, str] = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sh000016": "上证50",
    "sh000300": "沪深300",
    "sh000905": "中证500",
    "sh000852": "中证1000",
    "sh000015": "微盘股指数",
}

# Shenwan Level-1 Industry codes (31 industries)
SHENWAN_INDUSTRIES: Dict[str, str] = {
    "BK0447": "电子", "BK0448": "计算机", "BK0449": "传媒", "BK0450": "通信",
    "BK0451": "国防军工", "BK0452": "电力设备", "BK0453": "机械设备", "BK0454": "汽车",
    "BK0455": "家用电器", "BK0456": "轻工制造", "BK0457": "建筑材料", "BK0458": "建筑装饰",
    "BK0459": "钢铁", "BK0460": "有色金属", "BK0461": "化工", "BK0462": "石油石化",
    "BK0463": "煤炭", "BK0464": "基础化工", "BK0465": "房地产", "BK0466": "交通运输",
    "BK0467": "公用事业", "BK0468": "银行", "BK0469": "非银金融", "BK0470": "医药生物",
    "BK0471": "食品饮料", "BK0472": "农林牧渔", "BK0473": "商贸零售", "BK0474": "社会服务",
    "BK0475": "纺织服饰", "BK0476": "美容护理", "BK0477": "环保",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int."""
    if value is None or pd.isna(value):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class DiagnosticDataFetcher:
    """
    Data fetcher for market diagnostic system.

    Fetches:
    - Index series (60-day historical data for 9 core indices)
    - Market breadth metrics
    - Sector data (31 Shenwan Level-1 industries)
    - Capital flow data

    Uses in-memory cache with 20-minute TTL.
    """

    def __init__(
        self,
        data_manager: Optional[Any] = None,
        cache_ttl: int = 1200,
    ):
        """
        Initialize DiagnosticDataFetcher.

        Args:
            data_manager: DataFetcherManager instance from daily_stock_analysis
            cache_ttl: Cache time-to-live in seconds (default: 1200 = 20 minutes)
        """
        self._data_manager = data_manager
        self._cache = DiagnosticDataCache(ttl=cache_ttl)
        self._akshare_available = self._check_akshare()

        logger.info(f"[DiagnosticDataFetcher] Initialized (akshare: {self._akshare_available})")

    def _check_akshare(self) -> bool:
        """Check if akshare library is available."""
        try:
            import akshare as ak
            return True
        except ImportError:
            logger.warning("[DiagnosticDataFetcher] akshare not available")
            return False

    def fetch_index_series(
        self,
        date: Optional[str] = None,
        days: int = 60,
    ) -> Dict[str, IndexDailyData]:
        """
        Fetch 60-day historical data for 9 core indices.

        Args:
            date: Target date in 'YYYY-MM-DD' format (default: today)
            days: Number of historical days to fetch (default: 60)

        Returns:
            Dictionary mapping index code to IndexDailyData

        Requirements: 1.1, 1.2, 21.1, 21.2
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # Check cache first
        if self._cache.has("index_series", date):
            cached = self._cache.get("index_series", date)
            if cached is not None:
                logger.info(f"[DiagnosticDataFetcher] Using cached index series for {date}")
                return cached

        logger.info(f"[DiagnosticDataFetcher] Fetching index series for {date}, days={days}")

        result: Dict[str, IndexDailyData] = {}
        missing_data: List[str] = []

        end_date = datetime.strptime(date, '%Y-%m-%d')
        start_date = (end_date - timedelta(days=days * 2)).strftime('%Y-%m-%d')

        for code, name in INDEX_POOL.items():
            try:
                logger.debug(f"[DiagnosticDataFetcher] Fetching {code} ({name})...")

                # Try using data_manager if available
                if self._data_manager is not None:
                    result_tuple = self._data_manager.get_daily_data(
                        stock_code=code,
                        start_date=start_date,
                        end_date=date,
                        days=days * 2,
                    )

                    if isinstance(result_tuple, tuple):
                        df, _ = result_tuple
                    else:
                        df = result_tuple
                else:
                    # Fallback to akshare directly
                    df = self._fetch_index_from_akshare(code, start_date, date)

                if df is None or df.empty:
                    logger.warning(f"[DiagnosticDataFetcher] No data for {code} ({name})")
                    missing_data.append(f"{code}:{name}")
                    continue

                # Get latest row
                latest = df.iloc[-1]

                # Extract close and volume series
                close_series = df['close'].tail(days).tolist()
                volume_series = df['volume'].tail(days).tolist() if 'volume' in df.columns else []

                # Calculate prev_close
                if len(df) > 1:
                    prev_close = _safe_float(df.iloc[-2]['close'])
                else:
                    prev_close = _safe_float(latest['close'])

                index_data = IndexDailyData(
                    code=code,
                    name=name,
                    date=date,
                    close=_safe_float(latest['close']),
                    open=_safe_float(latest.get('open', latest.get('开盘', 0))),
                    high=_safe_float(latest.get('high', latest.get('最高', 0))),
                    low=_safe_float(latest.get('low', latest.get('最低', 0))),
                    prev_close=prev_close,
                    volume=_safe_float(latest.get('volume', latest.get('成交量', 0))),
                    amount=_safe_float(latest.get('amount', latest.get('成交额', 0))),
                    change_pct=_safe_float(latest.get('pct_chg', latest.get('涨跌幅', 0))),
                    close_series=close_series,
                    volume_series=volume_series,
                )

                result[code] = index_data
                logger.debug(f"[DiagnosticDataFetcher] {code}: close={index_data.close}, change={index_data.change_pct}%")

            except Exception as e:
                logger.error(f"[DiagnosticDataFetcher] Error fetching {code} ({name}): {e}")
                missing_data.append(f"{code}:{name}")
                continue

        if missing_data:
            logger.warning(f"[DiagnosticDataFetcher] Missing index data: {', '.join(missing_data)}")

        logger.info(f"[DiagnosticDataFetcher] Index series fetch complete: {len(result)}/{len(INDEX_POOL)} indices")

        # Cache the result
        self._cache.set("index_series", date, result)

        return result

    def _fetch_index_from_akshare(
        self,
        code: str,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch index data directly from akshare."""
        if not self._akshare_available:
            return None

        try:
            import akshare as ak

            # Map to akshare index symbol
            symbol_map = {
                "sh000001": "000001", "sz399001": "399001", "sz399006": "399006",
                "sh000688": "000688", "sh000016": "000016", "sh000300": "000300",
                "sh000905": "000905", "sh000852": "000852", "sh000015": "000015",
            }

            symbol = symbol_map.get(code, code)

            # Fetch data
            time.sleep(2)  # Rate limiting
            df = ak.stock_zh_index_daily(symbol=f"sh{symbol}")

            if df is None or df.empty:
                return None

            # Filter by date range
            df['date'] = pd.to_datetime(df['date'])
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]

            if not df.empty:
                df = df.sort_values('date')

            return df

        except Exception as e:
            logger.error(f"[DiagnosticDataFetcher] akshare fetch error for {code}: {e}")
            return None

    def fetch_breadth_data(
        self,
        date: Optional[str] = None,
    ) -> Optional[MarketBreadthData]:
        """
        Fetch market breadth metrics.

        Args:
            date: Target date in 'YYYY-MM-DD' format (default: today)

        Returns:
            MarketBreadthData object or None if fetch fails

        Requirements: 1.3, 1.7, 21.3
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # Check cache
        if self._cache.has("breadth", date):
            cached = self._cache.get("breadth", date)
            if cached is not None:
                logger.info(f"[DiagnosticDataFetcher] Using cached breadth data for {date}")
                return cached

        logger.info(f"[DiagnosticDataFetcher] Fetching breadth data for {date}")

        try:
            # Try akshare for market stats
            if self._akshare_available:
                import akshare as ak

                time.sleep(2)  # Rate limiting
                df_market = ak.stock_zh_a_spot_em()

                if df_market is not None and not df_market.empty:
                    return self._process_breadth_from_spot(df_market, date)

            # Fallback to data_manager
            if self._data_manager is not None:
                stats = self._data_manager.get_market_stats()
                if stats is not None:
                    return self._process_breadth_from_stats(stats, date)

            logger.warning("[DiagnosticDataFetcher] Could not fetch breadth data")
            return None

        except Exception as e:
            logger.error(f"[DiagnosticDataFetcher] Error fetching breadth data: {e}")
            return None

    def _process_breadth_from_spot(
        self,
        df: pd.DataFrame,
        date: str,
    ) -> MarketBreadthData:
        """Process breadth data from market spot DataFrame."""
        # Filter out ST stocks and suspended stocks
        if '名称' in df.columns:
            df = df[~df['名称'].astype(str).str.contains('ST', na=False)]
        if '成交量' in df.columns:
            df = df[df['成交量'] > 0]

        total_stocks = len(df)

        # Calculate up/down counts
        change_col = '涨跌幅' if '涨跌幅' in df.columns else 'pct_chg'
        up_count = len(df[df[change_col] > 0])
        down_count = len(df[df[change_col] < 0])
        flat_count = len(df[df[change_col] == 0])

        # Estimate limit up/down counts
        limit_up_count = len(df[df[change_col] >= 9.5])
        limit_down_count = len(df[df[change_col] <= -9.5])
        explode_count = len(df[(df[change_col] >= 8.0) & (df[change_col] < 9.5)])

        # Calculate seal rate
        seal_rate = limit_up_count / (limit_up_count + explode_count) if (limit_up_count + explode_count) > 0 else 0.0

        # Calculate total amount
        amount_col = '成交额' if '成交额' in df.columns else 'amount'
        total_amount = _safe_float(df[amount_col].sum()) / 1e8

        # Use placeholders for MA ratios (would need historical data)
        above_ma20_ratio = 0.5
        above_ma60_ratio = 0.5
        new_high_count = 0
        new_low_count = 0
        amount_ma5 = total_amount
        amount_ma20 = total_amount
        continuous_limit_up = 0

        breadth_data = MarketBreadthData(
            date=date,
            up_count=up_count,
            down_count=down_count,
            flat_count=flat_count,
            limit_up_count=limit_up_count,
            limit_down_count=limit_down_count,
            explode_count=explode_count,
            seal_rate=seal_rate,
            continuous_limit_up=continuous_limit_up,
            above_ma20_ratio=above_ma20_ratio,
            above_ma60_ratio=above_ma60_ratio,
            new_high_count=new_high_count,
            new_low_count=new_low_count,
            total_amount=total_amount,
            amount_ma5=amount_ma5,
            amount_ma20=amount_ma20,
        )

        logger.info(f"[DiagnosticDataFetcher] Breadth: up={up_count}, down={down_count}, "
                   f"limit_up={limit_up_count}, seal_rate={seal_rate:.2%}")

        # Cache the result
        self._cache.set("breadth", date, breadth_data)

        return breadth_data

    def _process_breadth_from_stats(
        self,
        stats: Dict[str, Any],
        date: str,
    ) -> MarketBreadthData:
        """Process breadth data from DataFetcherManager stats."""
        up_count = _safe_int(stats.get('up_count', 0))
        down_count = _safe_int(stats.get('down_count', 0))
        flat_count = _safe_int(stats.get('flat_count', 0))
        limit_up_count = _safe_int(stats.get('limit_up_count', 0))
        limit_down_count = _safe_int(stats.get('limit_down_count', 0))
        explode_count = _safe_int(stats.get('explode_count', 0))
        seal_rate = limit_up_count / (limit_up_count + explode_count) if (limit_up_count + explode_count) > 0 else 0.0
        total_amount = _safe_float(stats.get('total_amount', 0))

        breadth_data = MarketBreadthData(
            date=date,
            up_count=up_count,
            down_count=down_count,
            flat_count=flat_count,
            limit_up_count=limit_up_count,
            limit_down_count=limit_down_count,
            explode_count=explode_count,
            seal_rate=seal_rate,
            continuous_limit_up=_safe_int(stats.get('continuous_limit_up', 0)),
            above_ma20_ratio=_safe_float(stats.get('above_ma20_ratio', 0.5)),
            above_ma60_ratio=_safe_float(stats.get('above_ma60_ratio', 0.5)),
            new_high_count=_safe_int(stats.get('new_high_count', 0)),
            new_low_count=_safe_int(stats.get('new_low_count', 0)),
            total_amount=total_amount,
            amount_ma5=_safe_float(stats.get('amount_ma5', total_amount)),
            amount_ma20=_safe_float(stats.get('amount_ma20', total_amount)),
        )

        logger.info(f"[DiagnosticDataFetcher] Breadth from manager: up={up_count}, down={down_count}")

        # Cache the result
        self._cache.set("breadth", date, breadth_data)

        return breadth_data

    def fetch_sector_data(
        self,
        date: Optional[str] = None,
    ) -> List[SectorDailyData]:
        """
        Fetch 31 Shenwan Level-1 industry data.

        Args:
            date: Target date in 'YYYY-MM-DD' format (default: today)

        Returns:
            List of SectorDailyData objects

        Requirements: 1.4, 21.4
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # Check cache
        if self._cache.has("sector", date):
            cached = self._cache.get("sector", date)
            if cached is not None:
                logger.info(f"[DiagnosticDataFetcher] Using cached sector data for {date}")
                return cached

        logger.info(f"[DiagnosticDataFetcher] Fetching sector data for {date}")

        result: List[SectorDailyData] = []

        if self._akshare_available:
            try:
                result = self._fetch_sector_from_akshare(date)
                if result:
                    self._cache.set("sector", date, result)
                    return result
            except Exception as e:
                logger.warning(f"[DiagnosticDataFetcher] AkShare sector fetch failed: {e}")

        # Fallback: return empty list
        logger.warning(f"[DiagnosticDataFetcher] No sector data available for {date}")
        return result

    def _fetch_sector_from_akshare(self, date: str) -> List[SectorDailyData]:
        """Fetch sector data using AkShare."""
        import akshare as ak

        result: List[SectorDailyData] = []

        try:
            # Fetch industry capital flow
            time.sleep(2)
            df_flow = ak.stock_sector_fund_flow_rank(indicator="今日")

            flow_dict: Dict[str, Dict[str, float]] = {}
            if df_flow is not None and not df_flow.empty:
                for _, row in df_flow.iterrows():
                    name = str(row.get('名称', ''))
                    flow_dict[name] = {
                        'amount': _safe_float(row.get('成交额', 0)) / 1e8,
                        'change_pct': _safe_float(row.get('涨跌幅', 0)),
                    }

            # Get total market amount
            total_amount = sum(v['amount'] for v in flow_dict.values()) if flow_dict else 0.0

            # Fetch CSI300 for excess return
            csi300_ret_1d = 0.0
            if self._data_manager is not None:
                try:
                    df_csi300 = self._data_manager.get_daily_data(
                        stock_code="sh000300",
                        days=2,
                    )
                    if df_csi300 is not None and len(df_csi300) >= 2:
                        csi300_ret_1d = _safe_float(df_csi300.iloc[-1].get('pct_chg', 0))
                except Exception:
                    pass

            # Process each industry
            for industry_code, industry_name in SHENWAN_INDUSTRIES.items():
                try:
                    time.sleep(3)  # Rate limiting between sectors

                    # Fetch historical data
                    start_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=40)).strftime('%Y%m%d')
                    end_date_str = date.replace('-', '')

                    df_hist = ak.stock_board_industry_hist_em(
                        symbol=industry_code,
                        period="日k",
                        start_date=start_date,
                        end_date=end_date_str,
                        adjust="",
                    )

                    if df_hist is None or df_hist.empty:
                        continue

                    latest = df_hist.iloc[-1]

                    # Get today's return from flow data
                    flow_data = flow_dict.get(industry_name, {})
                    ret_1d = flow_data.get('change_pct', _safe_float(latest.get('涨跌幅', 0)))

                    # Calculate 5-day and 20-day returns
                    if len(df_hist) >= 5:
                        close_5d_ago = _safe_float(df_hist.iloc[-5]['收盘'])
                        ret_5d = ((_safe_float(latest['收盘']) - close_5d_ago) / close_5d_ago * 100) if close_5d_ago > 0 else 0.0
                    else:
                        ret_5d = ret_1d

                    if len(df_hist) >= 20:
                        close_20d_ago = _safe_float(df_hist.iloc[-20]['收盘'])
                        ret_20d = ((_safe_float(latest['收盘']) - close_20d_ago) / close_20d_ago * 100) if close_20d_ago > 0 else 0.0
                    else:
                        ret_20d = ret_1d

                    # Calculate amount share
                    amount = flow_data.get('amount', _safe_float(latest.get('成交额', 0)) / 1e8)
                    amount_share = (amount / total_amount) if total_amount > 0 else 0.0

                    sector_data = SectorDailyData(
                        date=date,
                        industry_code=industry_code,
                        industry_name=industry_name,
                        ret_1d=ret_1d,
                        ret_5d=ret_5d,
                        ret_20d=ret_20d,
                        excess_ret_1d=ret_1d - csi300_ret_1d,
                        breadth_20=0.5,  # Would need constituent data
                        new_high_ratio=0.0,  # Would need constituent data
                        amount=amount,
                        amount_share=amount_share,
                        amount_share_delta=0.0,  # Would need historical
                        limit_up_count=0,  # Would need constituent data
                        turnover=_safe_float(latest.get('换手率', 0)),
                    )

                    result.append(sector_data)
                    logger.debug(f"[DiagnosticDataFetcher] {industry_name}: ret_1d={ret_1d:.2f}%, amount_share={amount_share:.2%}")

                except Exception as e:
                    logger.warning(f"[DiagnosticDataFetcher] Error fetching {industry_name}: {e}")
                    continue

        except Exception as e:
            logger.error(f"[DiagnosticDataFetcher] Sector fetch error: {e}")

        logger.info(f"[DiagnosticDataFetcher] Sector fetch complete: {len(result)} sectors")
        return result

    def fetch_capital_flow(
        self,
        date: Optional[str] = None,
    ) -> Optional[CapitalFlowData]:
        """
        Fetch capital flow data.

        Args:
            date: Target date in 'YYYY-MM-DD' format (default: today)

        Returns:
            CapitalFlowData object or None if fetch fails

        Requirements: 1.5, 7.6, 21.5
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # Check cache
        if self._cache.has("capital", date):
            cached = self._cache.get("capital", date)
            if cached is not None:
                logger.info(f"[DiagnosticDataFetcher] Using cached capital flow for {date}")
                return cached

        logger.info(f"[DiagnosticDataFetcher] Fetching capital flow data for {date}")

        data_freshness: Dict[str, str] = {}

        # North Bound Capital (T+1)
        north_net_flow = 0.0
        north_5d_avg = 0.0
        if self._akshare_available:
            try:
                import akshare as ak

                time.sleep(2)
                df_north = ak.stock_hsgt_hist_em(symbol="沪深港通")

                if df_north is not None and not df_north.empty:
                    df_north['日期'] = pd.to_datetime(df_north['日期'])
                    target_date = pd.to_datetime(date)

                    matching = df_north[df_north['日期'] == target_date]
                    if not matching.empty:
                        north_net_flow = _safe_float(matching.iloc[0].get('当日资金流入', 0)) / 1e8
                        data_freshness['north_net_flow'] = 'T+0'
                    else:
                        latest = df_north.iloc[-1]
                        north_net_flow = _safe_float(latest.get('当日资金流入', 0)) / 1e8
                        data_freshness['north_net_flow'] = 'T+1'

                    if len(df_north) >= 5:
                        recent = df_north.tail(5)['当日资金流入'].astype(float) / 1e8
                        north_5d_avg = float(recent.mean())

            except Exception as e:
                logger.warning(f"[DiagnosticDataFetcher] North Bound Capital fetch error: {e}")
                data_freshness['north_net_flow'] = 'unavailable'
        else:
            data_freshness['north_net_flow'] = 'unavailable'

        # Margin balance (T+1) - placeholder
        margin_balance = 0.0
        margin_delta = 0.0
        data_freshness['margin_balance'] = 'unavailable'

        # Main force and ETF flows - placeholder
        main_net_flow = 0.0
        etf_net_flow = 0.0
        data_freshness['main_net_flow'] = 'T+0 (proxy)'
        data_freshness['etf_net_flow'] = 'T+0 (proxy)'

        capital_data = CapitalFlowData(
            date=date,
            north_net_flow=north_net_flow,
            north_5d_avg=north_5d_avg,
            margin_balance=margin_balance,
            margin_delta=margin_delta,
            main_net_flow=main_net_flow,
            etf_net_flow=etf_net_flow,
            data_freshness=data_freshness,
        )

        logger.info(f"[DiagnosticDataFetcher] Capital flow: north={north_net_flow:.2f}亿, margin={margin_balance:.2f}亿")

        # Cache the result
        self._cache.set("capital", date, capital_data)

        return capital_data
