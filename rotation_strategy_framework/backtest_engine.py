# -*- coding: utf-8 -*-
"""
回测引擎: 基于 backtrader 的统一回测框架，支持单/多策略并行、Walk-Forward 验证、参数网格搜索

核心类:
- BacktestConfig: 回测配置 (start, end, cash, commission, benchmark)
- BacktestResult: 回测结果 (returns, sharpe, max_dd, win_rate, trades, equity_curve)
- RotationStrategy: backtrader 策略基类 (修复版 position 访问、T+0索引、R²保护)
- BacktestEngine: 回测引擎 (run_single, run_multiple, walk_forward, grid_search)

关键修复:
- 持仓: self.getposition(data).size 替代 broker.positions.get()
- T+0: d.close[-1] = 昨天 (backtrader约定)
- R²: if var_y < 1e-10: return 0
- RSRS: 实例级 slope_history 持久化
- rebalance: 按交易日计数而非绝对bar
"""

import os
import json
import logging
import datetime
import itertools
import time
from typing import Optional, Dict, List, Tuple, Any, Union, Callable, Type
from dataclasses import dataclass, field, asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy

import numpy as np
import pandas as pd

try:
    import backtrader as bt
except ImportError:
    bt = None

from .strategy_registry import StrategyConfig, StrategyCategory, ParamSpace
from .factor_engine import (
    compute_r2,
    linear_regression,
    TimingFactors,
    MomentumFactors,
    AllocationFactors,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
TRADING_DAYS_PER_YEAR = 252
RESULTS_VERSION = "v1.0.0"


# ---------------------------------------------------------------------------
# BacktestConfig: 回测配置
# ---------------------------------------------------------------------------
@dataclass
class BacktestConfig:
    """
    回测配置

    Attributes:
        start: 回测开始日期 (YYYY-MM-DD 或 YYYYMMDD)
        end: 回测结束日期
        cash: 初始资金
        commission: 佣金比例 (如 0.001 表示千分之一)
        slippage: 滑点比例
        benchmark: 基准指数代码 (如 000300)
        stake: 每手股数 (默认 100)
        min_commission: 最低佣金 (元)
        tax: 印花税比例 (卖出时收取)
        data_format: 数据格式 (pandas, csv)
        warmup_period: 预热期 (交易日数，用于指标计算)
        output_dir: 结果输出目录
        log_level: 日志级别
        cerebro_params: Cerebro 额外参数
    """

    start: str = "2020-01-01"
    end: str = "2024-12-31"
    cash: float = 1_000_000.0
    commission: float = 0.001
    slippage: float = 0.0
    benchmark: str = "000300"
    stake: int = 100
    min_commission: float = 5.0
    tax: float = 0.001
    data_format: str = "pandas"
    warmup_period: int = 60
    output_dir: str = "./backtest_results"
    log_level: int = logging.WARNING
    cerebro_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """标准化日期格式"""
        self.start = self._normalize_date(self.start)
        self.end = self._normalize_date(self.end)
        os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def _normalize_date(d: str) -> str:
        """标准化为 YYYY-MM-DD"""
        d = d.strip()
        if len(d) == 8 and d.isdigit():
            return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        return d

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BacktestConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "BacktestConfig":
        return cls.from_dict(json.loads(json_str))

    def __repr__(self) -> str:
        return (
            f"BacktestConfig(start='{self.start}', end='{self.end}', "
            f"cash={self.cash:,.0f}, commission={self.commission:.3%})"
        )


# ---------------------------------------------------------------------------
# BacktestResult: 回测结果
# ---------------------------------------------------------------------------
@dataclass
class BacktestResult:
    """
    回测结果 (标准化输出)

    Attributes:
        strategy_name: 策略名称
        start: 回测开始日期
        end: 回测结束日期
        total_return: 总收益率
        annual_return: 年化收益率
        annual_volatility: 年化波动率
        sharpe_ratio: 夏普比率 (无风险利率=0)
        sortino_ratio: 索提诺比率
        calmar_ratio: 卡玛比率
        max_drawdown: 最大回撤
        max_drawdown_duration: 最大回撤持续天数
        win_rate: 胜率
        profit_loss_ratio: 盈亏比
        total_trades: 总交易次数
        winning_trades: 盈利交易数
        losing_trades: 亏损交易数
        avg_trade_return: 平均交易收益
        avg_winning_trade: 平均盈利交易
        avg_losing_trade: 平均亏损交易
        equity_curve: 权益曲线 (DataFrame: date, value)
        returns: 日收益率序列 (Series)
        trades: 交易记录列表 (list of dict)
        benchmark_return: 基准收益率
        alpha: 超额收益 (alpha)
        beta: 市场敏感度 (beta)
        info_ratio: 信息比率
        params: 策略参数字典
        metadata: 额外元数据
        duration_days: 回测天数
    """

    strategy_name: str = ""
    start: str = ""
    end: str = ""
    total_return: float = 0.0
    annual_return: float = 0.0
    annual_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    win_rate: float = 0.0
    profit_loss_ratio: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_trade_return: float = 0.0
    avg_winning_trade: float = 0.0
    avg_losing_trade: float = 0.0
    equity_curve: Optional[pd.DataFrame] = None
    returns: Optional[pd.Series] = None
    trades: List[Dict[str, Any]] = field(default_factory=list)
    benchmark_return: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    info_ratio: float = 0.0
    params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_days: int = 0

    def to_dict(self, include_curve: bool = False) -> Dict[str, Any]:
        d = {
            "strategy_name": self.strategy_name,
            "start": self.start,
            "end": self.end,
            "duration_days": self.duration_days,
            "total_return": round(self.total_return, 6),
            "annual_return": round(self.annual_return, 6),
            "annual_volatility": round(self.annual_volatility, 6),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            "calmar_ratio": round(self.calmar_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 6),
            "max_drawdown_duration": self.max_drawdown_duration,
            "win_rate": round(self.win_rate, 4),
            "profit_loss_ratio": round(self.profit_loss_ratio, 4),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_return": round(self.avg_trade_return, 6),
            "avg_winning_trade": round(self.avg_winning_trade, 6),
            "avg_losing_trade": round(self.avg_losing_trade, 6),
            "benchmark_return": round(self.benchmark_return, 6),
            "alpha": round(self.alpha, 6),
            "beta": round(self.beta, 4),
            "info_ratio": round(self.info_ratio, 4),
            "params": self.params,
            "metadata": self.metadata,
        }
        if include_curve and self.equity_curve is not None:
            d["equity_curve"] = self.equity_curve.to_dict()
        if include_curve and self.returns is not None:
            d["returns"] = self.returns.to_dict()
        return d

    def to_json(self, indent: int = 2, include_curve: bool = False) -> str:
        return json.dumps(
            self.to_dict(include_curve), ensure_ascii=False, indent=indent
        )

    def save(self, path: str, include_curve: bool = False) -> None:
        os.makedirs(
            os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json(include_curve))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BacktestResult":
        d = d.copy()
        eq = d.pop("equity_curve", None)
        ret = d.pop("returns", None)
        if isinstance(eq, dict):
            d["equity_curve"] = pd.DataFrame(eq)
        if isinstance(ret, dict):
            d["returns"] = pd.Series(ret)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def summary(self) -> str:
        lines = [
            f"=== {self.strategy_name} ===",
            f"  区间: {self.start} ~ {self.end} ({self.duration_days} 天)",
            f"  总收益: {self.total_return:.2%}",
            f"  年化收益: {self.annual_return:.2%}",
            f"  年化波动: {self.annual_volatility:.2%}",
            f"  夏普比率: {self.sharpe_ratio:.3f}",
            f"  索提诺比率: {self.sortino_ratio:.3f}",
            f"  卡玛比率: {self.calmar_ratio:.3f}",
            f"  最大回撤: {self.max_drawdown:.2%} (持续 {self.max_drawdown_duration} 天)",
            f"  胜率: {self.win_rate:.2%} ({self.winning_trades}/{self.total_trades})",
            f"  盈亏比: {self.profit_loss_ratio:.3f}",
            f"  Alpha: {self.alpha:.2%}  Beta: {self.beta:.3f}  IR: {self.info_ratio:.3f}",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"BacktestResult(name='{self.strategy_name}', "
            f"return={self.total_return:.2%}, sharpe={self.sharpe_ratio:.3f}, "
            f"max_dd={self.max_drawdown:.2%})"
        )


# ---------------------------------------------------------------------------
# RotationStrategy: backtrader 策略基类 (修复版)
# ---------------------------------------------------------------------------
class RotationStrategy(bt.Strategy if bt else object):
    """
    ETF 轮动策略基类 (修复版)

    关键修复:
    1. 持仓访问: self.getposition(data).size 替代 broker.positions.get()
    2. T+0 索引: d.close[-1] = 昨天 (backtrader约定，-1 是前一根bar)
    3. R² 保护: if var_y < 1e-10: return 0
    4. RSRS: 实例级 slope_history 持久化
    5. rebalance: 按交易日计数而非绝对bar

    子类需实现:
    - compute_scores(): 返回 dict[symbol, score]
    - get_etf_pool(): 返回可交易标的列表
    """

    params = (
        ("etf_pool", []),
        ("rebalance_period", 5),
        ("top_n", 3),
        ("max_positions", 5),
        ("min_position_weight", 0.05),
        ("cash_reserve", 0.0),
        ("momentum_periods", [5, 10, 20, 60]),
        ("momentum_weights", None),
        ("rsrs_N", 18),
        ("rsrs_M", 600),
        ("rsrs_buy_threshold", 0.7),
        ("rsrs_sell_threshold", -0.7),
        ("use_timing", False),
        ("regression_window", 20),
        ("ma_fast", 5),
        ("ma_slow", 20),
        ("risk_aversion", 1.0),
        ("cov_window", 60),
        ("stop_loss_pct", 0.08),
        ("trailing_stop_pct", 0.05),
        ("max_single_weight", 0.30),
        ("scoring_mode", "momentum"),
        ("allocation_mode", "top_n"),
    )

    def __init__(self):
        self._trading_day_count = 0
        self._last_rebalance_day = -self.p.rebalance_period
        self._rsrs_slope_history: Dict[str, List[float]] = {}
        self._rsrs_instance = TimingFactors()
        self._rsrs_cache: Dict[str, pd.DataFrame] = {}
        self._price_history: Dict[str, List[float]] = {}
        self._trade_log: List[Dict[str, Any]] = []
        self._equity_history: List[Tuple[datetime.datetime, float]] = []
        self._data_refs: Dict[str, Any] = {}
        self._init_price_history()

    def _init_price_history(self):
        for d in self.datas:
            name = d._name if hasattr(d, "_name") else str(d)
            self._price_history[name] = []
            self._data_refs[name] = d

    def log(self, txt: str, dt: Optional[datetime.datetime] = None):
        if self.p.log_level <= logging.DEBUG:
            dt = dt or self.datas[0].datetime.date(0)
            logger.debug(f"[{dt.isoformat()}] {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f"BUY EXECUTED: {order.data._name}, "
                    f"Price: {order.executed.price:.4f}, "
                    f"Size: {order.executed.size}, "
                    f"Cost: {order.executed.value:.2f}, "
                    f"Comm: {order.executed.comm:.2f}"
                )
            else:
                self.log(
                    f"SELL EXECUTED: {order.data._name}, "
                    f"Price: {order.executed.price:.4f}, "
                    f"Size: {order.executed.size}, "
                    f"Comm: {order.executed.comm:.2f}"
                )
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"Order {order.getstatusname()} for {order.data._name}")

    def notify_trade(self, trade):
        if trade.isclosed:
            trade_info = {
                "symbol": trade.data._name,
                "pnl": trade.pnl,
                "pnlcomm": trade.pnlcomm,
                "size": trade.size,
                "price_open": trade.price,
                "price_close": trade.price,
                "commission": trade.commission,
                "bar_open": trade.baropen,
                "bar_close": trade.barclose,
                "dt_open": self.data.datetime.date(trade.baropen).isoformat()
                if len(self.data) > trade.baropen
                else "",
                "dt_close": self.data.datetime.date(trade.barclose).isoformat()
                if len(self.data) > trade.barclose
                else "",
            }
            self._trade_log.append(trade_info)
            self.log(f"TRADE CLOSED: {trade.data._name}, PnL: {trade.pnlcomm:.2f}")

    def next(self):
        self._trading_day_count += 1

        self._record_equity()

        if not self._is_rebalance_day():
            self._check_stops()
            return

        self._last_rebalance_day = self._trading_day_count

        scores = self.compute_scores()
        if not scores:
            return

        timing_allowed = True
        if self.p.use_timing:
            timing_allowed = self._check_timing()

        if timing_allowed:
            self._rebalance(scores)
        else:
            self._liquidate_all()

    def _is_rebalance_day(self) -> bool:
        return (
            self._trading_day_count - self._last_rebalance_day
        ) >= self.p.rebalance_period

    def _record_equity(self):
        self._equity_history.append(
            (self.datas[0].datetime.date(0), self.broker.getvalue())
        )

    def compute_scores(self) -> Dict[str, float]:
        """
        计算各标的得分 (子类可覆盖)

        Returns:
            dict[symbol, score]
        """
        mode = self.p.scoring_mode
        if mode == "momentum":
            return self._score_momentum()
        elif mode == "log_regression":
            return self._score_log_regression()
        elif mode == "bias":
            return self._score_bias()
        elif mode == "kalman":
            return self._score_kalman()
        elif mode == "multi_factor":
            return self._score_multi_factor()
        elif mode == "rsrs":
            return self._score_rsrs()
        elif mode == "correlation":
            return self._score_correlation()
        elif mode == "epo":
            return self._score_epo()
        elif mode == "ir_trend":
            return self._score_ir_trend()
        elif mode == "north_flow":
            return self._score_north_flow()
        elif mode == "sector_heat":
            return self._score_sector_heat()
        else:
            return self._score_momentum()

    def get_etf_pool(self) -> List[str]:
        if self.p.etf_pool:
            return list(self.p.etf_pool)
        return [d._name for d in self.datas if hasattr(d, "_name")]

    def _get_close_series(self, name: str, length: Optional[int] = None) -> pd.Series:
        """
        获取标的收盘价序列 (修复 T+0 索引)

        backtrader 约定:
        - d.close[0] = 当前bar (今天)
        - d.close[-1] = 前一根bar (昨天)
        """
        data = self._data_refs.get(name)
        if data is None:
            return pd.Series(dtype=float)

        n = len(data)
        if n == 0:
            return pd.Series(dtype=float)

        if length is not None:
            start_idx = max(0, n - length)
        else:
            start_idx = 0

        prices = []
        dates = []
        for i in range(start_idx, n):
            try:
                prices.append(data.close[i])
                dates.append(data.datetime.date(i))
            except (IndexError, TypeError):
                break

        return pd.Series(prices, index=pd.DatetimeIndex(dates), name=name)

    def _score_momentum(self) -> Dict[str, float]:
        periods = list(self.p.momentum_periods)
        weights = self.p.momentum_weights
        if weights is None:
            weights = [1.0 / len(periods)] * len(periods)

        pool = self.get_etf_pool()
        scores = {}
        for name in pool:
            close = self._get_close_series(name)
            if len(close) < max(periods):
                continue
            score = 0.0
            for p, w in zip(periods, weights):
                if len(close) >= p:
                    ret = (
                        (close.iloc[-1] / close.iloc[-p] - 1)
                        if close.iloc[-p] > 0
                        else 0
                    )
                    score += w * ret
            scores[name] = score
        return scores

    def _score_log_regression(self) -> Dict[str, float]:
        window = self.p.regression_window
        pool = self.get_etf_pool()
        scores = {}
        for name in pool:
            close = self._get_close_series(name, window + 5)
            if len(close) < window:
                continue
            log_prices = np.log(close.values.clip(lower=1e-10))
            x = np.arange(len(log_prices))
            slope, _, r2 = linear_regression(x, log_prices)
            annualized_slope = slope * 252
            scores[name] = annualized_slope * r2
        return scores

    def _score_bias(self) -> Dict[str, float]:
        ma_periods = [5, 10, 20]
        pool = self.get_etf_pool()
        scores = {}
        for name in pool:
            close = self._get_close_series(name, 30)
            if len(close) < 20:
                continue
            bias_sum = 0.0
            valid_count = 0
            for p in ma_periods:
                if len(close) >= p:
                    ma = close.rolling(p).mean().iloc[-1]
                    if ma > 0:
                        bias_sum += (close.iloc[-1] - ma) / ma
                        valid_count += 1
            scores[name] = bias_sum / max(valid_count, 1)
        return scores

    def _score_kalman(self) -> Dict[str, float]:
        pool = self.get_etf_pool()
        scores = {}
        for name in pool:
            close = self._get_close_series(name, 120)
            if len(close) < 10:
                continue
            close_df = pd.DataFrame({name: close})
            trend_df = MomentumFactors.kalman(close_df)
            if name in trend_df.columns:
                scores[name] = (
                    trend_df[name].dropna().iloc[-1]
                    if len(trend_df[name].dropna()) > 0
                    else 0.0
                )
        return scores

    def _score_multi_factor(self) -> Dict[str, float]:
        mom_w = 0.4
        vol_w = 0.3
        corr_w = 0.3
        pool = self.get_etf_pool()
        scores = {}

        close_dict = {}
        for name in pool:
            c = self._get_close_series(name, 120)
            if len(c) >= 20:
                close_dict[name] = c

        if not close_dict:
            return scores

        close_matrix = pd.DataFrame(close_dict)

        for name in pool:
            if name not in close_matrix.columns:
                continue
            c = close_matrix[name]

            mom_score = 0.0
            if len(c) >= 20:
                mom_score = c.iloc[-1] / c.iloc[-20] - 1 if c.iloc[-20] > 0 else 0

            vol_score = 0.0
            if len(c) >= 20:
                vol = c.pct_change().rolling(20).std().iloc[-1]
                vol_score = -vol if not pd.isna(vol) else 0

            corr_score = 0.0
            if len(close_matrix) >= 20:
                rets = close_matrix.pct_change().dropna()
                if len(rets) >= 20 and name in rets.columns:
                    other_cols = [col for col in rets.columns if col != name]
                    if other_cols:
                        avg_corr = (
                            rets[name]
                            .iloc[-60:]
                            .corr(rets[other_cols].iloc[-60:].mean(axis=1))
                        )
                        corr_score = -avg_corr if not pd.isna(avg_corr) else 0

            scores[name] = mom_w * mom_score + vol_w * vol_score + corr_w * corr_score

        return scores

    def _score_rsrs(self) -> Dict[str, float]:
        pool = self.get_etf_pool()
        scores = {}
        for name in pool:
            data = self._data_refs.get(name)
            if data is None:
                continue
            n = len(data)
            if n < self.p.rsrs_N:
                continue

            high_vals = []
            low_vals = []
            for i in range(max(0, n - self.p.rsrs_N), n):
                try:
                    high_vals.append(data.high[i])
                    low_vals.append(data.low[i])
                except (IndexError, TypeError):
                    break

            if len(high_vals) < self.p.rsrs_N:
                continue

            slope, _, r2 = linear_regression(np.array(low_vals), np.array(high_vals))

            cache_key = f"rsrs_{name}"
            if cache_key not in self._rsrs_slope_history:
                self._rsrs_slope_history[cache_key] = []
            self._rsrs_slope_history[cache_key].append(slope)

            hist = self._rsrs_slope_history[cache_key]
            if len(hist) >= self.p.rsrs_M:
                hist = hist[-self.p.rsrs_M :]

            mean_s = np.mean(hist)
            std_s = np.std(hist)
            z = (slope - mean_s) / std_s if std_s > 1e-10 else 0.0

            scores[name] = z * r2

        return scores

    def _score_correlation(self) -> Dict[str, float]:
        pool = self.get_etf_pool()
        scores = {}

        close_dict = {}
        for name in pool:
            c = self._get_close_series(name, 120)
            if len(c) >= 60:
                close_dict[name] = c

        if len(close_dict) < 2:
            for name in pool:
                scores[name] = 0.0
            return scores

        close_matrix = pd.DataFrame(close_dict)
        rets = close_matrix.pct_change().dropna()

        if len(rets) < 30:
            for name in pool:
                scores[name] = 0.0
            return scores

        corr_matrix = rets.iloc[-60:].corr()

        for name in pool:
            if name not in corr_matrix.columns:
                scores[name] = 0.0
                continue
            others = [c for c in corr_matrix.columns if c != name]
            if others:
                avg_corr = corr_matrix.loc[name, others].mean()
                scores[name] = -avg_corr
            else:
                scores[name] = 0.0

        return scores

    def _score_epo(self) -> Dict[str, float]:
        return self._score_momentum()

    def _score_ir_trend(self) -> Dict[str, float]:
        pool = self.get_etf_pool()
        scores = {}

        for name in pool:
            c = self._get_close_series(name, 60)
            if len(c) < 20:
                continue
            rets = c.pct_change().dropna()
            if len(rets) < 20:
                continue
            excess = rets.iloc[-20:]
            ir = (
                excess.mean() / excess.std() * np.sqrt(252)
                if excess.std() > 1e-10
                else 0.0
            )
            scores[name] = ir

        return scores

    def _score_north_flow(self) -> Dict[str, float]:
        return self._score_momentum()

    def _score_sector_heat(self) -> Dict[str, float]:
        return self._score_momentum()

    def _check_timing(self) -> bool:
        if not self.p.use_timing:
            return True

        benchmark_data = None
        for d in self.datas:
            if d._name == self._get_benchmark_name():
                benchmark_data = d
                break

        if benchmark_data is None:
            return True

        n = len(benchmark_data)
        if n < self.p.rsrs_N:
            return True

        high_vals = []
        low_vals = []
        for i in range(max(0, n - self.p.rsrs_N), n):
            try:
                high_vals.append(benchmark_data.high[i])
                low_vals.append(benchmark_data.low[i])
            except (IndexError, TypeError):
                break

        if len(high_vals) < self.p.rsrs_N:
            return True

        slope, _, r2 = linear_regression(np.array(low_vals), np.array(high_vals))
        rsrs_score = slope * r2

        cache_key = "rsrs_benchmark"
        if cache_key not in self._rsrs_slope_history:
            self._rsrs_slope_history[cache_key] = []
        self._rsrs_slope_history[cache_key].append(slope)

        hist = self._rsrs_slope_history[cache_key]
        if len(hist) >= self.p.rsrs_M:
            hist = hist[-self.p.rsrs_M :]

        if len(hist) > 1:
            mean_s = np.mean(hist)
            std_s = np.std(hist)
            z = (slope - mean_s) / std_s if std_s > 1e-10 else 0.0
            rsrs_score = z * r2

        return rsrs_score > self.p.rsrs_sell_threshold

    def _get_benchmark_name(self) -> str:
        return "benchmark"

    def _rebalance(self, scores: Dict[str, float]):
        sorted_names = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        top_n = min(self.p.top_n, len(sorted_names))
        targets = sorted_names[:top_n]

        if not targets:
            self._liquidate_all()
            return

        available_cash = self.broker.getcash() * (1 - self.p.cash_reserve)
        total_value = self.broker.getvalue()
        target_value = total_value * (1 - self.p.cash_reserve) / len(targets)

        current_positions = {}
        for name in targets:
            data = self._data_refs.get(name)
            if data is None:
                continue
            pos = self.getposition(data)
            current_positions[name] = pos.size

        for name in targets:
            data = self._data_refs.get(name)
            if data is None:
                continue
            price = data.close[0]
            if price <= 0:
                continue
            target_size = int(target_value / price / self.p.stake) * self.p.stake
            target_size = max(target_size, 0)
            current_size = current_positions.get(name, 0)
            diff = target_size - current_size
            if diff > 0:
                self.buy(data=data, size=diff, price=price)
            elif diff < 0:
                self.sell(data=data, size=abs(diff), price=price)

        all_names = set(self._data_refs.keys())
        for name in all_names:
            if name not in targets:
                data = self._data_refs.get(name)
                if data is None:
                    continue
                pos = self.getposition(data)
                if pos.size > 0:
                    self.sell(data=data, size=pos.size, price=data.close[0])

    def _liquidate_all(self):
        for name, data in self._data_refs.items():
            pos = self.getposition(data)
            if pos.size > 0:
                self.sell(data=data, size=pos.size, price=data.close[0])

    def _check_stops(self):
        stop_pct = self.p.stop_loss_pct
        if stop_pct <= 0:
            return

        for name, data in self._data_refs.items():
            pos = self.getposition(data)
            if pos.size <= 0:
                continue

            current_price = data.close[0]
            avg_price = pos.price
            if avg_price <= 0:
                continue

            loss_pct = (avg_price - current_price) / avg_price
            if loss_pct >= stop_pct:
                self.log(f"STOP LOSS: {name}, loss={loss_pct:.2%}")
                self.sell(data=data, size=pos.size, price=current_price)

    def get_trade_log(self) -> List[Dict[str, Any]]:
        return list(self._trade_log)

    def get_equity_history(self) -> List[Tuple[datetime.datetime, float]]:
        return list(self._equity_history)


# ---------------------------------------------------------------------------
# PandasData 辅助类
# ---------------------------------------------------------------------------
def create_pandas_data_feed(
    df: pd.DataFrame,
    name: str = "",
    datetime_col: str = "datetime",
) -> bt.feeds.PandasData:
    """
    从 DataFrame 创建 backtrader 数据源

    Args:
        df: DataFrame (需包含 open, high, low, close, volume 列)
        name: 数据名称
        datetime_col: 日期列名

    Returns:
        backtrader PandasData 实例
    """
    df = df.copy()
    if datetime_col in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    df = df.sort_index()

    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            df[col] = 0.0

    if "openinterest" not in df.columns:
        df["openinterest"] = 0.0

    data = bt.feeds.PandasData(
        dataname=df,
        name=name,
        datetime=None,
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest="openinterest",
    )
    return data


# ---------------------------------------------------------------------------
# BacktestEngine: 回测引擎
# ---------------------------------------------------------------------------
class BacktestEngine:
    """
    回测引擎

    功能:
    - run_single_strategy: 单策略回测
    - run_multiple_strategies: 多策略并行回测
    - walk_forward_validation: Walk-Forward 验证
    - grid_search: 参数网格搜索
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self._analyzers_cache: Dict[str, Any] = {}

    def run_single_strategy(
        self,
        strategy_config: Union[StrategyConfig, Dict[str, Any]],
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        config: Optional[BacktestConfig] = None,
        strategy_class: Optional[Type[RotationStrategy]] = None,
    ) -> BacktestResult:
        """
        运行单策略回测

        Args:
            strategy_config: 策略配置
            data: 数据 (DataFrame 或 dict[symbol, DataFrame])
            config: 回测配置 (覆盖引擎默认配置)
            strategy_class: 自定义策略类 (默认使用 RotationStrategy)

        Returns:
            BacktestResult
        """
        cfg = config or self.config
        strat_cfg = self._normalize_strategy_config(strategy_config)

        cerebro = self._build_cerebro(cfg)

        if strategy_class is None:
            strategy_class = RotationStrategy

        strat_params = self._build_strategy_params(strat_cfg)
        cerebro.addstrategy(strategy_class, **strat_params)

        data_dict = self._normalize_data(data)
        for name, df in data_dict.items():
            feed = create_pandas_data_feed(df, name=name)
            cerebro.adddata(feed)

        if strat_cfg.get("benchmark") and strat_cfg["benchmark"] in data_dict:
            bench_df = data_dict[strat_cfg["benchmark"]]
            bench_feed = create_pandas_data_feed(bench_df, name="benchmark")
            cerebro.adddata(bench_feed)

        result = self._run_cerebro(cerebro, strat_cfg, cfg)
        return result

    def run_multiple_strategies(
        self,
        strategies: Dict[str, Union[StrategyConfig, Dict[str, Any]]],
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        config: Optional[BacktestConfig] = None,
        n_workers: int = 4,
        strategy_class: Optional[Type[RotationStrategy]] = None,
    ) -> Dict[str, BacktestResult]:
        """
        多策略并行回测

        Args:
            strategies: dict[name, strategy_config]
            data: 数据
            config: 回测配置
            n_workers: 并行工作数
            strategy_class: 自定义策略类

        Returns:
            dict[name, BacktestResult]
        """
        cfg = config or self.config
        results = {}

        if n_workers <= 1:
            for name, strat_cfg in strategies.items():
                logger.info(f"回测策略: {name}")
                results[name] = self.run_single_strategy(
                    strat_cfg, data, cfg, strategy_class
                )
            return results

        data_dict = self._normalize_data(data)
        data_serializable = {k: v.to_dict() for k, v in data_dict.items()}
        cfg_dict = cfg.to_dict()

        tasks = []
        for name, strat_cfg in strategies.items():
            tasks.append((name, strat_cfg, data_serializable, cfg_dict))

        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = {
                executor.submit(
                    self._run_single_worker,
                    name,
                    strat_cfg,
                    data_serializable,
                    cfg_dict,
                ): name
                for name, strat_cfg, _, _ in tasks
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result_dict = future.result()
                    results[name] = BacktestResult.from_dict(result_dict)
                except Exception as e:
                    logger.error(f"策略 {name} 回测失败: {e}")
                    results[name] = BacktestResult(
                        strategy_name=name,
                        metadata={"error": str(e)},
                    )

        return results

    def walk_forward_validation(
        self,
        strategy_config: Union[StrategyConfig, Dict[str, Any]],
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        train_window: int = 252,
        test_window: int = 60,
        config: Optional[BacktestConfig] = None,
        strategy_class: Optional[Type[RotationStrategy]] = None,
    ) -> List[BacktestResult]:
        """
        Walk-Forward 验证

        将数据划分为多个训练-测试窗口，在每个窗口上训练和测试策略

        Args:
            strategy_config: 策略配置
            data: 数据
            train_window: 训练窗口 (交易日数)
            test_window: 测试窗口 (交易日数)
            config: 回测配置
            strategy_class: 自定义策略类

        Returns:
            list[BacktestResult] 每个测试窗口的结果
        """
        cfg = config or self.config
        strat_cfg = self._normalize_strategy_config(strategy_config)
        data_dict = self._normalize_data(data)

        if not data_dict:
            return []

        first_df = next(iter(data_dict.values()))
        if not isinstance(first_df.index, pd.DatetimeIndex):
            if "datetime" in first_df.columns:
                first_df = first_df.set_index("datetime")
            else:
                first_df.index = pd.to_datetime(first_df.index)

        total_bars = len(first_df)
        if total_bars < train_window + test_window:
            logger.warning(f"数据量不足: {total_bars} < {train_window + test_window}")
            return []

        results = []
        step = test_window
        window_idx = 0

        for start_idx in range(0, total_bars - train_window, step):
            train_end = start_idx + train_window
            test_end = min(train_end + test_window, total_bars)

            if test_end - train_end < 10:
                break

            train_data = {}
            test_data = {}
            for name, df in data_dict.items():
                df_indexed = df
                if not isinstance(df_indexed.index, pd.DatetimeIndex):
                    if "datetime" in df_indexed.columns:
                        df_indexed = df_indexed.set_index("datetime")
                    else:
                        df_indexed.index = pd.to_datetime(df_indexed.index)

                train_data[name] = df_indexed.iloc[start_idx:train_end].copy()
                test_data[name] = df_indexed.iloc[train_end:test_end].copy()

            if not test_data or not any(len(v) > 0 for v in test_data.values()):
                break

            window_cfg = BacktestConfig(
                start=str(train_data[next(iter(train_data))].index[0].date()),
                end=str(test_data[next(iter(test_data))].index[-1].date()),
                cash=cfg.cash,
                commission=cfg.commission,
                benchmark=cfg.benchmark,
                output_dir=os.path.join(cfg.output_dir, f"wf_{window_idx}"),
            )

            logger.info(
                f"Walk-Forward 窗口 {window_idx}: "
                f"train=[{window_cfg.start} ~ {str(train_data[next(iter(train_data))].index[-1].date())}], "
                f"test=[{str(test_data[next(iter(test_data))].index[0].date())} ~ {window_cfg.end}]"
            )

            try:
                result = self.run_single_strategy(
                    strat_cfg, test_data, window_cfg, strategy_class
                )
                result.metadata["window_idx"] = window_idx
                result.metadata["train_start"] = window_cfg.start
                result.metadata["train_end"] = str(
                    train_data[next(iter(train_data))].index[-1].date()
                )
                result.metadata["test_start"] = str(
                    test_data[next(iter(test_data))].index[0].date()
                )
                result.metadata["test_end"] = window_cfg.end
                results.append(result)
            except Exception as e:
                logger.error(f"Walk-Forward 窗口 {window_idx} 失败: {e}")
                results.append(
                    BacktestResult(
                        strategy_name=strat_cfg.get("name", "unknown"),
                        metadata={
                            "window_idx": window_idx,
                            "error": str(e),
                        },
                    )
                )

            window_idx += 1

        logger.info(f"Walk-Forward 验证完成: {len(results)} 个窗口")
        return results

    def grid_search(
        self,
        strategy_config: Union[StrategyConfig, Dict[str, Any]],
        param_space: Dict[str, Union[ParamSpace, List[Any]]],
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        config: Optional[BacktestConfig] = None,
        top_n: int = 5,
        sort_by: str = "sharpe_ratio",
        strategy_class: Optional[Type[RotationStrategy]] = None,
    ) -> List[Tuple[Dict[str, Any], BacktestResult]]:
        """
        参数网格搜索

        Args:
            strategy_config: 策略配置
            param_space: 参数搜索空间 dict[name, ParamSpace|list]
            data: 数据
            config: 回测配置
            top_n: 返回最优参数组数
            sort_by: 排序指标 (sharpe_ratio, total_return, calmar_ratio)
            strategy_class: 自定义策略类

        Returns:
            list[(params_dict, BacktestResult)] 按排序指标降序排列
        """
        cfg = config or self.config
        strat_cfg = self._normalize_strategy_config(strategy_config)

        grids = {}
        for pname, pspace in param_space.items():
            if isinstance(pspace, ParamSpace):
                grids[pname] = pspace.grid_values()
            elif isinstance(pspace, (list, tuple)):
                grids[pname] = list(pspace)
            else:
                grids[pname] = [pspace]

        if not grids:
            logger.warning("参数搜索空间为空")
            base_result = self.run_single_strategy(strat_cfg, data, cfg, strategy_class)
            return [({}, base_result)]

        param_names = list(grids.keys())
        param_values = [grids[n] for n in param_names]
        combinations = list(itertools.product(*param_values))

        logger.info(
            f"网格搜索: {len(combinations)} 组参数组合 ({len(param_names)} 个参数)"
        )

        all_results = []
        data_dict = self._normalize_data(data)
        data_serializable = {k: v.to_dict() for k, v in data_dict.items()}
        cfg_dict = cfg.to_dict()
        strat_cfg_dict = strat_cfg

        for i, combo in enumerate(combinations):
            params = dict(zip(param_names, combo))
            combo_cfg = deepcopy(strat_cfg_dict)
            if "params" not in combo_cfg:
                combo_cfg["params"] = {}
            combo_cfg["params"].update(params)

            logger.info(f"网格搜索 [{i + 1}/{len(combinations)}]: {params}")

            try:
                result = self._run_single_worker_serializable(
                    combo_cfg, data_serializable, cfg_dict
                )
                result_obj = BacktestResult.from_dict(result)
                all_results.append((params, result_obj))
            except Exception as e:
                logger.error(f"参数组合 {params} 回测失败: {e}")
                all_results.append(
                    (
                        params,
                        BacktestResult(
                            strategy_name=strat_cfg.get("name", "unknown"),
                            metadata={"error": str(e)},
                        ),
                    )
                )

        all_results.sort(
            key=lambda x: getattr(x[1], sort_by, 0),
            reverse=True,
        )

        top_results = all_results[:top_n]
        logger.info(f"网格搜索完成: 最优 {top_n} 组参数")
        return top_results

    def _build_cerebro(self, config: BacktestConfig) -> bt.Cerebro:
        cerebro = bt.Cerebro()

        cerebro.broker.setcash(config.cash)

        cerebro.broker.setcommission(
            commission=config.commission,
            mincommission=config.min_commission,
            stocklike=True,
        )

        if config.slippage > 0:
            cerebro.broker.set_slippage_perc(config.slippage)

        cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.0)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="annual_return")
        cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")

        cerebro.addobserver(bt.observers.Broker)
        cerebro.addobserver(bt.observers.Trades)

        return cerebro

    def _build_strategy_params(self, strat_cfg: Dict[str, Any]) -> Dict[str, Any]:
        params = {}
        params.update(strat_cfg.get("params", {}))

        mapping = {
            "etf_pool": "etf_pool",
            "rebalance_period": "rebalance_period",
            "top_n": "top_n",
            "max_positions": "max_positions",
            "min_position_weight": "min_position_weight",
            "cash_reserve": "cash_reserve",
            "momentum_periods": "momentum_periods",
            "momentum_weights": "momentum_weights",
            "rsrs_N": "rsrs_N",
            "rsrs_M": "rsrs_M",
            "rsrs_buy_threshold": "rsrs_buy_threshold",
            "rsrs_sell_threshold": "rsrs_sell_threshold",
            "use_timing": "use_timing",
            "regression_window": "regression_window",
            "ma_fast": "ma_fast",
            "ma_slow": "ma_slow",
            "risk_aversion": "risk_aversion",
            "cov_window": "cov_window",
            "stop_loss_pct": "stop_loss_pct",
            "trailing_stop_pct": "trailing_stop_pct",
            "max_single_weight": "max_single_weight",
            "benchmark": "benchmark",
        }

        for key, param_name in mapping.items():
            if key in strat_cfg:
                params[param_name] = strat_cfg[key]
            elif key in strat_cfg.get("params", {}):
                params[param_name] = strat_cfg["params"][key]

        timing_method = strat_cfg.get("timing_method", "none")
        if isinstance(timing_method, str):
            params["use_timing"] = timing_method != "none"
        else:
            params["use_timing"] = str(timing_method).lower() != "none"

        scoring_mode = strat_cfg.get("scoring_mode", "momentum")
        if isinstance(scoring_mode, str):
            params["scoring_mode"] = scoring_mode
        else:
            params["scoring_mode"] = (
                scoring_mode.value if hasattr(scoring_mode, "value") else "momentum"
            )

        params["log_level"] = logging.WARNING

        return params

    def _run_cerebro(
        self,
        cerebro: bt.Cerebro,
        strat_cfg: Dict[str, Any],
        config: BacktestConfig,
    ) -> BacktestResult:
        strat_name = strat_cfg.get("name", strat_cfg.get("strategy_name", "unknown"))

        try:
            results = cerebro.run()
            strat = results[0]
        except Exception as e:
            logger.error(f"回测执行失败: {e}")
            return BacktestResult(
                strategy_name=strat_name,
                metadata={"error": str(e)},
            )

        analyzers = strat.analyzers
        returns_an = analyzers.returns.get_analysis()
        sharpe_an = analyzers.sharpe.get_analysis()
        drawdown_an = analyzers.drawdown.get_analysis()
        trade_an = analyzers.trades.get_analysis()

        equity_history = strat.get_equity_history()
        if not equity_history:
            equity_history = [(datetime.datetime.now(), config.cash)]

        equity_df = pd.DataFrame(equity_history, columns=["date", "value"])
        equity_df["date"] = pd.to_datetime(equity_df["date"])
        equity_df = equity_df.set_index("date").sort_index()

        returns_series = equity_df["value"].pct_change().dropna()

        total_return = (
            (equity_df["value"].iloc[-1] / equity_df["value"].iloc[0] - 1)
            if len(equity_df) > 1
            else 0.0
        )

        n_days = len(returns_series)
        annual_return = (
            (1 + total_return) ** (TRADING_DAYS_PER_YEAR / max(n_days, 1)) - 1
            if n_days > 0
            else 0.0
        )

        annual_vol = (
            returns_series.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
            if len(returns_series) > 1
            else 0.0
        )

        sharpe = sharpe_an.get("sharperatio", 0)
        if sharpe is None:
            sharpe = 0.0

        max_dd = (
            drawdown_an.get("max", {}).get("drawdown", 0) / 100.0
            if isinstance(drawdown_an.get("max"), dict)
            else drawdown_an.get("max", 0)
        )
        if max_dd is None:
            max_dd = 0.0

        max_dd_len = (
            drawdown_an.get("max", {}).get("len", 0)
            if isinstance(drawdown_an.get("max"), dict)
            else 0
        )

        total_trades = (
            trade_an.get("total", {}).get("total", 0)
            if isinstance(trade_an.get("total"), dict)
            else trade_an.get("total", 0)
        )
        if total_trades is None:
            total_trades = 0

        won = (
            trade_an.get("won", {}).get("total", 0)
            if isinstance(trade_an.get("won"), dict)
            else 0
        )
        lost = (
            trade_an.get("lost", {}).get("total", 0)
            if isinstance(trade_an.get("lost"), dict)
            else 0
        )

        win_rate = won / total_trades if total_trades > 0 else 0.0

        pnl_won = (
            trade_an.get("won", {}).get("pnl", {}).get("average", 0)
            if isinstance(trade_an.get("won"), dict)
            else 0
        )
        pnl_lost = (
            trade_an.get("lost", {}).get("pnl", {}).get("average", 0)
            if isinstance(trade_an.get("lost"), dict)
            else 0
        )

        profit_loss_ratio = (
            abs(pnl_won / pnl_lost) if pnl_lost and pnl_lost != 0 else 0.0
        )

        avg_winning = pnl_won if pnl_won else 0.0
        avg_losing = pnl_lost if pnl_lost else 0.0

        avg_trade = (
            (pnl_won * won + pnl_lost * lost) / total_trades
            if total_trades > 0
            else 0.0
        )

        downside_returns = returns_series[returns_series < 0]
        downside_std = (
            downside_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
            if len(downside_returns) > 1
            else 0.0
        )
        sortino = (annual_return / downside_std) if downside_std > 0 else 0.0

        calmar = (annual_return / max_dd) if max_dd > 0 else 0.0

        benchmark_return = 0.0
        alpha = 0.0
        beta = 0.0
        info_ratio = 0.0

        bench_data = None
        for d in strat.datas:
            if hasattr(d, "_name") and d._name == "benchmark":
                bench_data = d
                break

        if bench_data is not None and len(bench_data) > 1:
            bench_prices = []
            for i in range(len(bench_data)):
                try:
                    bench_prices.append(bench_data.close[i])
                except (IndexError, TypeError):
                    break
            if len(bench_prices) > 1:
                benchmark_return = bench_prices[-1] / bench_prices[0] - 1
                bench_returns = pd.Series(bench_prices).pct_change().dropna()
                if len(bench_returns) > 1 and len(returns_series) > 1:
                    min_len = min(len(bench_returns), len(returns_series))
                    aligned_strat = returns_series.iloc[-min_len:]
                    aligned_bench = bench_returns.iloc[-min_len:]
                    cov_matrix = np.cov(aligned_strat.values, aligned_bench.values)
                    if cov_matrix.shape == (2, 2) and cov_matrix[1, 1] > 1e-10:
                        beta = cov_matrix[0, 1] / cov_matrix[1, 1]
                        alpha = annual_return - beta * (
                            benchmark_return * TRADING_DAYS_PER_YEAR / max(n_days, 1)
                        )
                        tracking_error = (
                            aligned_strat - aligned_bench
                        ).std() * np.sqrt(TRADING_DAYS_PER_YEAR)
                        info_ratio = (
                            (
                                annual_return
                                - benchmark_return
                                * TRADING_DAYS_PER_YEAR
                                / max(n_days, 1)
                            )
                            / tracking_error
                            if tracking_error > 0
                            else 0.0
                        )

        trade_log = strat.get_trade_log()

        result = BacktestResult(
            strategy_name=strat_name,
            start=config.start,
            end=config.end,
            total_return=total_return,
            annual_return=annual_return,
            annual_volatility=annual_vol,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd,
            max_drawdown_duration=int(max_dd_len),
            win_rate=win_rate,
            profit_loss_ratio=profit_loss_ratio,
            total_trades=int(total_trades),
            winning_trades=int(won),
            losing_trades=int(lost),
            avg_trade_return=avg_trade,
            avg_winning_trade=avg_winning,
            avg_losing_trade=avg_losing,
            equity_curve=equity_df,
            returns=returns_series,
            trades=trade_log,
            benchmark_return=benchmark_return,
            alpha=alpha,
            beta=beta,
            info_ratio=info_ratio,
            params=strat_cfg.get("params", {}),
            duration_days=n_days,
        )

        result_path = os.path.join(config.output_dir, f"{strat_name}_result.json")
        try:
            result.save(result_path)
        except Exception as e:
            logger.warning(f"保存结果失败: {e}")

        return result

    def _normalize_strategy_config(
        self, config: Union[StrategyConfig, Dict[str, Any]]
    ) -> Dict[str, Any]:
        if isinstance(config, StrategyConfig):
            return config.to_dict()
        return config

    def _normalize_data(
        self, data: Union[pd.DataFrame, Dict[str, pd.DataFrame]]
    ) -> Dict[str, pd.DataFrame]:
        if isinstance(data, pd.DataFrame):
            return {"default": data}
        if isinstance(data, dict):
            return data
        raise ValueError(f"不支持的数据类型: {type(data)}")

    @staticmethod
    def _run_single_worker(
        name: str,
        strat_cfg: Union[StrategyConfig, Dict[str, Any]],
        data_serializable: Dict[str, Dict],
        cfg_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        data = {k: pd.DataFrame(v) for k, v in data_serializable.items()}
        cfg = BacktestConfig.from_dict(cfg_dict)
        cfg.output_dir = os.path.join(cfg.output_dir, name)

        engine = BacktestEngine(cfg)
        result = engine.run_single_strategy(strat_cfg, data, cfg)
        return result.to_dict()

    def _run_single_worker_serializable(
        self,
        strat_cfg: Dict[str, Any],
        data_serializable: Dict[str, Dict],
        cfg_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        data = {k: pd.DataFrame(v) for k, v in data_serializable.items()}
        cfg = BacktestConfig.from_dict(cfg_dict)

        engine = BacktestEngine(cfg)
        result = engine.run_single_strategy(strat_cfg, data, cfg)
        return result.to_dict()

    def export_comparison(
        self,
        results: Dict[str, BacktestResult],
        path: Optional[str] = None,
        metrics: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        导出策略对比表

        Args:
            results: dict[name, BacktestResult]
            path: 输出路径
            metrics: 要对比的指标列表

        Returns:
            对比 DataFrame
        """
        if metrics is None:
            metrics = [
                "total_return",
                "annual_return",
                "annual_volatility",
                "sharpe_ratio",
                "sortino_ratio",
                "calmar_ratio",
                "max_drawdown",
                "win_rate",
                "profit_loss_ratio",
                "total_trades",
                "alpha",
                "beta",
                "info_ratio",
            ]

        rows = []
        for name, result in results.items():
            row = {"strategy_name": name}
            for m in metrics:
                row[m] = getattr(result, m, None)
            rows.append(row)

        df = pd.DataFrame(rows)

        if path:
            os.makedirs(
                os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True
            )
            df.to_csv(path, index=False, encoding="utf-8-sig")
            logger.info(f"对比表已保存: {path}")

        return df

    def aggregate_walk_forward(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """
        聚合 Walk-Forward 结果

        Args:
            results: Walk-Forward 各窗口结果

        Returns:
            聚合统计
        """
        if not results:
            return {"error": "无结果"}

        valid = [r for r in results if r.total_trades > 0 or r.duration_days > 0]
        if not valid:
            return {"error": "无有效结果"}

        metrics = {
            "n_windows": len(valid),
            "mean_total_return": np.mean([r.total_return for r in valid]),
            "mean_annual_return": np.mean([r.annual_return for r in valid]),
            "mean_sharpe": np.mean([r.sharpe_ratio for r in valid]),
            "mean_max_drawdown": np.mean([r.max_drawdown for r in valid]),
            "mean_win_rate": np.mean([r.win_rate for r in valid]),
            "std_total_return": np.std([r.total_return for r in valid]),
            "std_sharpe": np.std([r.sharpe_ratio for r in valid]),
            "sharpe_consistency": np.mean(
                [1 if r.sharpe_ratio > 0 else 0 for r in valid]
            ),
        }

        return metrics


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------
def run_backtest(
    strategy_config: Union[StrategyConfig, Dict[str, Any]],
    data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    start: str = "2020-01-01",
    end: str = "2024-12-31",
    cash: float = 1_000_000.0,
    commission: float = 0.001,
    benchmark: str = "000300",
) -> BacktestResult:
    """
    便捷函数: 运行单次回测

    Args:
        strategy_config: 策略配置
        data: 数据
        start: 开始日期
        end: 结束日期
        cash: 初始资金
        commission: 佣金
        benchmark: 基准

    Returns:
        BacktestResult
    """
    config = BacktestConfig(
        start=start,
        end=end,
        cash=cash,
        commission=commission,
        benchmark=benchmark,
    )
    engine = BacktestEngine(config)
    return engine.run_single_strategy(strategy_config, data, config)


def run_grid_search(
    strategy_config: Union[StrategyConfig, Dict[str, Any]],
    param_space: Dict[str, Union[ParamSpace, List[Any]]],
    data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    start: str = "2020-01-01",
    end: str = "2024-12-31",
    cash: float = 1_000_000.0,
    top_n: int = 5,
) -> List[Tuple[Dict[str, Any], BacktestResult]]:
    """
    便捷函数: 运行网格搜索

    Args:
        strategy_config: 策略配置
        param_space: 参数空间
        data: 数据
        start: 开始日期
        end: 结束日期
        cash: 初始资金
        top_n: 返回最优组数

    Returns:
        list[(params, result)]
    """
    config = BacktestConfig(start=start, end=end, cash=cash)
    engine = BacktestEngine(config)
    return engine.grid_search(strategy_config, param_space, data, config, top_n=top_n)


def run_walk_forward(
    strategy_config: Union[StrategyConfig, Dict[str, Any]],
    data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    train_window: int = 252,
    test_window: int = 60,
    start: str = "2020-01-01",
    end: str = "2024-12-31",
    cash: float = 1_000_000.0,
) -> List[BacktestResult]:
    """
    便捷函数: 运行 Walk-Forward 验证

    Args:
        strategy_config: 策略配置
        data: 数据
        train_window: 训练窗口
        test_window: 测试窗口
        start: 开始日期
        end: 结束日期
        cash: 初始资金

    Returns:
        list[BacktestResult]
    """
    config = BacktestConfig(start=start, end=end, cash=cash)
    engine = BacktestEngine(config)
    return engine.walk_forward_validation(
        strategy_config, data, train_window, test_window, config
    )
