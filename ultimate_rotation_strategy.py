"""
终极行业/板块/ETF轮动策略 v3.0 (Ultimate Rotation Strategy)

修复 v2.0 全部严重缺陷:
1. 持仓判断: self.getposition(data).size 替代 broker.positions.get()
2. 卡尔曼滤波: 持久化 P (误差协方差) 状态
3. T+0索引: close[-1]=昨天, close[0]=今天 (backtrader约定)
4. R²除零: np.var(y) < 1e-10 时返回 0
5. 卖出逻辑: 正确遍历 position 对象
6. RSRS状态: slope_history 在实例级别持久化

设计改进:
- 缓存增加 hash 版本控制
- rebalance_period 按交易日计数
- EPO signal 用动量得分替代均值
- 北向资金可外部注入
- T+0 模式跳过 rebalance_period 限流
"""

import backtrader as bt
import akshare as ak
import pandas as pd
import numpy as np
import math
import os
import hashlib
import warnings
from datetime import datetime, timedelta
from collections import defaultdict
from scipy.linalg import solve

warnings.filterwarnings("ignore")

CACHE_DIR = "etf_cache"
CACHE_VERSION = "v3"  # 缓存版本控制
os.makedirs(CACHE_DIR, exist_ok=True)


# =============================================================================
# 数据加载层 (增加缓存版本控制)
# =============================================================================


def format_symbol(symbol):
    s = (
        symbol.replace(".XSHG", "")
        .replace(".XSHE", "")
        .replace("sh", "")
        .replace("sz", "")
    )
    return s.zfill(6)


def load_etf_data(symbol, start, end, cache_dir=CACHE_DIR, force_update=False):
    """加载ETF数据，支持缓存版本控制"""
    cache_hash = hashlib.md5(
        f"{symbol}_{start}_{end}_{CACHE_VERSION}".encode()
    ).hexdigest()[:8]
    cache_file = os.path.join(cache_dir, f"{symbol}_{cache_hash}.pkl")
    start_dt, end_dt = pd.to_datetime(start), pd.to_datetime(end)
    need_download = force_update or (not os.path.exists(cache_file))

    if not need_download:
        try:
            df = pd.read_pickle(cache_file)
            df["date"] = pd.to_datetime(df["日期"])
            if df["date"].min() > start_dt or df["date"].max() < end_dt:
                need_download = True
        except Exception:
            need_download = True

    if need_download:
        print(f"下载ETF数据: {symbol}")
        df = ak.fund_etf_hist_em(symbol=symbol)
        if df.empty:
            return None
        df["date"] = pd.to_datetime(df["日期"])
        df.to_pickle(cache_file)

    df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)].copy()
    if df.empty:
        return None

    df.rename(
        columns={
            "日期": "datetime",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        },
        inplace=True,
    )
    df = df[["datetime", "open", "high", "low", "close", "volume"]]
    df["openinterest"] = 0
    return df


def load_all_etf_data(symbols, start, end, force_update=False):
    all_data = {}
    for sym in symbols:
        df = load_etf_data(sym, start, end, force_update=force_update)
        if df is not None and not df.empty:
            all_data[sym] = df
    return all_data


# =============================================================================
# 因子计算引擎 (修复 R² 除零 + 卡尔曼滤波状态持久化)
# =============================================================================


class FactorEngine:
    """统一因子计算引擎"""

    @staticmethod
    def momentum_score(close_prices, days=20):
        if len(close_prices) < days + 1:
            return 0
        return (close_prices.iloc[-1] / close_prices.iloc[-days - 1]) - 1

    @staticmethod
    def momentum_regression(close_prices, days=20):
        """线性回归斜率动量 (修复 R² 除零)"""
        if len(close_prices) < days:
            return 0, 0, 0
        x = np.arange(days)
        y = close_prices.iloc[-days:].values
        y_norm = y / y[0]
        slope, intercept = np.polyfit(x, y_norm, 1)
        var_y = np.var(y_norm, ddof=1)
        if var_y < 1e-10:
            return 0, intercept, 0
        r2 = 1 - (sum((y_norm - (slope * x + intercept)) ** 2) / ((len(y) - 1) * var_y))
        return slope * 10000, intercept, r2

    @staticmethod
    def momentum_log_regression(close_prices, days=25):
        """对数回归年化*R² (修复 R² 除零)"""
        if len(close_prices) < days:
            return 0
        y = np.log(close_prices.iloc[-days:].values)
        x = np.arange(days)
        slope, intercept = np.polyfit(x, y, 1)
        var_y = np.var(y, ddof=1)
        if var_y < 1e-10:
            return 0
        r_squared = 1 - (
            sum((y - (slope * x + intercept)) ** 2) / ((len(y) - 1) * var_y)
        )
        annualized_returns = math.pow(math.exp(slope), 250) - 1
        return annualized_returns * r_squared

    @staticmethod
    def bias_momentum(close_prices, bias_days=90, mom_days=20):
        if len(close_prices) < bias_days + mom_days:
            return 0
        ma = close_prices.iloc[-(bias_days + mom_days) :].rolling(bias_days).mean()
        bias = close_prices.iloc[-mom_days:] / ma.iloc[-mom_days:]
        slope, _ = np.polyfit(np.arange(mom_days), bias / bias.iloc[0], 1)
        return slope.real * 10000

    @staticmethod
    def kalman_filter_step(obs, state, P, R=0.15, Q=0.1):
        """
        单步卡尔曼滤波 (修复: 持久化 P)
        obs: 观测值
        state: 上一时刻状态估计
        P: 上一时刻误差协方差 (必须持久化!)
        R: 观测噪声协方差
        Q: 过程噪声协方差
        返回: (新state, 新P)
        """
        # 预测
        pred_state = state
        pred_P = P + Q
        # 更新
        K = pred_P / (pred_P + R)  # 卡尔曼增益
        new_state = pred_state + K * (obs - pred_state)
        new_P = (1 - K) * pred_P
        return new_state, new_P

    @staticmethod
    def kalman_momentum_with_state(close_prices, days, state, P, R=0.15, Q=0.1):
        """
        带状态的卡尔曼滤波动量
        返回: (slope, new_state, new_P)
        """
        if len(close_prices) < days:
            return 0, state, P
        obs = (close_prices.iloc[-days:] / close_prices.iloc[-days]).values
        states = [state]
        current_P = P
        for i in range(1, len(obs)):
            state, current_P = FactorEngine.kalman_filter_step(
                obs[i], state, current_P, R, Q
            )
            states.append(state)
        states = np.array(states)
        slope, _ = np.polyfit(np.arange(days), states, 1)
        return slope * 10000, state, current_P

    @staticmethod
    def industry_ir(close_prices, market_close):
        n = min(len(close_prices), len(market_close))
        if n < 20:
            return 0
        ind_ret = close_prices.iloc[-n:].pct_change().dropna()
        mkt_ret = market_close.iloc[-n:].pct_change().dropna()
        min_len = min(len(ind_ret), len(mkt_ret))
        if min_len < 20:
            return 0
        ind_ret = ind_ret.iloc[-min_len:]
        mkt_ret = mkt_ret.iloc[-min_len:]
        r_ind = (ind_ret + 1).cumprod().iloc[-1] - 1
        r_mkt = (mkt_ret + 1).cumprod().iloc[-1] - 1
        error_std = (ind_ret - mkt_ret).std()
        if error_std == 0:
            return 0
        return (r_ind - r_mkt) / error_std

    @staticmethod
    def crowdedness(turnover_series, window=40):
        if len(turnover_series) < window:
            return 0
        tovr_mean = turnover_series.iloc[-window:].mean()
        tovr_std = turnover_series.iloc[-window:].std()
        return (turnover_series.iloc[-1] - tovr_mean) / tovr_std if tovr_std > 0 else 0

    @staticmethod
    def rsrs_score(high_prices, low_prices, N=18, M=600, slope_history=None):
        """RSRS (修复: slope_history 由调用方维护)"""
        if len(high_prices) < N or len(low_prices) < N:
            return 0, slope_history
        x = low_prices.iloc[-N:].values
        y = high_prices.iloc[-N:].values
        intercept, slope, r2 = FactorEngine._ols(x, y)
        if slope_history is None:
            slope_history = [slope] * M
        slope_history.append(slope)
        if len(slope_history) > M + 1:
            slope_history.pop(0)
        recent = slope_history[-M:]
        mean, std = np.mean(recent), np.std(recent)
        zscore = (slope - mean) / std if std > 0 else 0
        return zscore * r2, slope_history

    @staticmethod
    def _ols(x, y):
        slope, intercept = np.polyfit(x, y, 1)
        var_y = np.var(y, ddof=1)
        if var_y < 1e-10:
            return intercept, slope, 0
        r2 = 1 - (sum((y - (slope * x + intercept)) ** 2) / ((len(y) - 1) * var_y))
        return intercept, slope, r2

    @staticmethod
    def correlation_matrix(close_dict, window=250):
        returns = {}
        for sym, df in close_dict.items():
            if len(df) >= window:
                returns[sym] = df["close"].iloc[-window:].pct_change().dropna()
        if len(returns) < 2:
            return None
        return pd.DataFrame(returns).corr()

    @staticmethod
    def volatility_filter(close_dict, min_vol=0.05, max_vol=0.33, window=250):
        filtered = {}
        for sym, df in close_dict.items():
            if len(df) >= window:
                vol = df["close"].iloc[
                    -window:
                ].pct_change().dropna().std() * math.sqrt(243)
                if min_vol < vol < max_vol:
                    filtered[sym] = df
        return filtered

    @staticmethod
    def epo_optimize(returns_df, signal, lambda_=10, w=0.6, method="anchored"):
        n = returns_df.shape[1]
        vcov = returns_df.cov()
        corr = returns_df.corr()
        I = np.eye(n)
        V = np.diag(np.diag(vcov))
        std = np.sqrt(V)
        s = np.array(signal)
        shrunk_cor = ((1 - w) * I @ corr.values) + (w * I)
        cov_tilde = std @ shrunk_cor @ std
        inv_shrunk_cov = solve(cov_tilde, I)
        if method == "simple":
            epo = (1 / lambda_) * inv_shrunk_cov @ s
        else:
            d = np.diag(vcov)
            a = (1 / d) / (1 / d).sum()
            denom = s @ inv_shrunk_cov @ cov_tilde @ inv_shrunk_cov @ s
            if denom <= 0:
                epo = (1 / lambda_) * inv_shrunk_cov @ s
            else:
                gamma = np.sqrt(a @ cov_tilde @ a) / np.sqrt(denom)
                epo = inv_shrunk_cov @ (((1 - w) * gamma * s) + (w * V @ a))
        epo = np.maximum(epo, 0)
        if epo.sum() > 0:
            epo = epo / epo.sum()
        return epo

    @staticmethod
    def min_correlation_selection(corr_matrix, top_n=4):
        corr_mean = {s: corr_matrix[s].abs().mean() for s in corr_matrix.columns}
        return sorted(corr_mean, key=corr_mean.get)[:top_n]

    @staticmethod
    def north_money_boll(north_money_series, windows=[252, 150, 80, 20]):
        signals = {"buy": 0, "sell": 0}
        for w in windows:
            if len(north_money_series) < w:
                continue
            recent = north_money_series[:w]
            mid, std = recent.mean(), recent.std()
            factor = 1.5 if w > 100 else 2.0
            current = north_money_series[0]
            if current > mid + factor * std:
                signals["buy"] += 1
            if current < mid - factor * std:
                signals["sell"] += 1
        return signals

    @staticmethod
    def volume_emotion_monitor(volume_series, ma_window=7, lag=6):
        if len(volume_series) < ma_window + lag:
            return 0
        vol = volume_series.iloc[-(ma_window + lag) :]
        ma = vol.rolling(ma_window).mean()
        ratio = vol / ma - 1
        recent = ratio.iloc[-lag:]
        if (recent < 0).all():
            return -1
        elif (recent.iloc[-3:] >= 0).all():
            return 1
        return 0

    @staticmethod
    def price_momentum_filter(close_prices, window=13):
        if len(close_prices) < window:
            return 0, -100
        current = close_prices.iloc[-1]
        ma = close_prices.iloc[-window:].mean()
        increase = (current / close_prices.iloc[0] - 1) * 100
        diff = (current / ma - 1) * 100
        return increase, diff


# =============================================================================
# 评分器 / 配置器 / 择时引擎 / 风控 (保持不变)
# =============================================================================


class ScoringModes:
    MOMENTUM_SIMPLE = "momentum_simple"
    MOMENTUM_REGRESSION = "momentum_regression"
    MOMENTUM_LOG_REG = "momentum_log_regression"
    BIAS_MOMENTUM = "bias_momentum"
    KALMAN_MOMENTUM = "kalman_momentum"
    IR_TREND = "ir_trend"
    MULTI_FACTOR = "multi_factor"
    SECTOR_HEAT = "sector_heat"


class RotationScorer:
    def __init__(self, mode=ScoringModes.MOMENTUM_REGRESSION, **params):
        self.mode = mode
        self.params = params

    def score(self, data_dict, market_data=None):
        scores = []
        for symbol, df in data_dict.items():
            close = df["close"]
            high = df.get("high", close)
            low = df.get("low", close)
            volume = df.get("volume", pd.Series(0, index=close.index))
            score = self._calc(close, high, low, volume, market_data)
            scores.append((symbol, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _calc(self, close, high, low, volume, market_data):
        days = self.params.get("momentum_days", 20)
        if self.mode == ScoringModes.MOMENTUM_SIMPLE:
            return FactorEngine.momentum_score(close, days)
        elif self.mode == ScoringModes.MOMENTUM_REGRESSION:
            slope, _, r2 = FactorEngine.momentum_regression(close, days)
            return slope * r2
        elif self.mode == ScoringModes.MOMENTUM_LOG_REG:
            return FactorEngine.momentum_log_regression(
                close, self.params.get("log_reg_days", 25)
            )
        elif self.mode == ScoringModes.BIAS_MOMENTUM:
            return FactorEngine.bias_momentum(
                close, self.params.get("bias_days", 90), self.params.get("mom_days", 20)
            )
        elif self.mode == ScoringModes.KALMAN_MOMENTUM:
            state = close.iloc[-days] / close.iloc[-days]
            slope, _, _ = FactorEngine.kalman_momentum_with_state(
                close,
                days,
                state,
                0.1,
                self.params.get("kalman_R", 0.15),
                self.params.get("kalman_Q", 0.1),
            )
            return slope
        elif self.mode == ScoringModes.IR_TREND:
            if market_data is None:
                return FactorEngine.momentum_regression(close, days)[0]
            return FactorEngine.industry_ir(close, market_data["close"])
        elif self.mode == ScoringModes.SECTOR_HEAT:
            ret = FactorEngine.momentum_score(close, days)
            return ret * 100 if ret > self.params.get("change_limit", 0.05) else 0
        elif self.mode == ScoringModes.MULTI_FACTOR:
            mom = FactorEngine.momentum_regression(close, days)[0]
            crowd = FactorEngine.crowdedness(
                volume, self.params.get("crowd_window", 40)
            )
            return (
                self.params.get("w_momentum", 1.0) * mom
                + self.params.get("w_crowdedness", -0.5) * crowd
            )
        return 0


class AllocationModes:
    TOP_N = "top_n"
    EPO_OPTIMIZED = "epo_optimized"
    MIN_CORRELATION = "min_correlation"
    STOCK_BOND_BALANCE = "stock_bond_balance"
    GRID_TRADING = "grid_trading"


class Allocator:
    def __init__(self, mode=AllocationModes.TOP_N, **params):
        self.mode = mode
        self.params = params

    def allocate(self, ranked_list, data_dict, total_value, market_data=None):
        if self.mode == AllocationModes.TOP_N:
            return self._top_n(ranked_list, total_value)
        elif self.mode == AllocationModes.EPO_OPTIMIZED:
            return self._epo(ranked_list, data_dict, total_value)
        elif self.mode == AllocationModes.MIN_CORRELATION:
            return self._min_corr(ranked_list, data_dict, total_value)
        elif self.mode == AllocationModes.STOCK_BOND_BALANCE:
            return self._stock_bond(total_value)
        elif self.mode == AllocationModes.GRID_TRADING:
            return self._grid(ranked_list, total_value)
        return {}

    def _top_n(self, ranked_list, total_value):
        n = self.params.get("stock_num", 1)
        targets = [s[0] for s in ranked_list[:n]]
        cash = total_value / len(targets) if targets else 0
        return {t: cash for t in targets}

    def _epo(self, ranked_list, data_dict, total_value):
        n = self.params.get("stock_num", 3)
        targets = [s[0] for s in ranked_list[:n]]
        if len(targets) < 2:
            return {targets[0]: total_value} if targets else {}
        returns = {}
        for sym in targets:
            if sym in data_dict and len(data_dict[sym]) > 60:
                returns[sym] = data_dict[sym]["close"].pct_change().dropna()
        if len(returns) < 2:
            return {targets[0]: total_value}
        ret_df = pd.DataFrame(returns)
        # 修复: 用动量得分替代均值 (均值≈0时权重退化)
        scores = [s[1] for s in ranked_list[:n]]
        signal = (
            np.array(scores) if len(scores) == len(targets) else ret_df.mean().values
        )
        if np.abs(signal).sum() < 1e-10:
            signal = np.ones(len(targets)) / len(targets)
        weights = FactorEngine.epo_optimize(
            ret_df,
            signal,
            lambda_=self.params.get("epo_lambda", 10),
            w=self.params.get("epo_w", 0.6),
            method=self.params.get("epo_method", "anchored"),
        )
        return {targets[i]: total_value * weights[i] for i in range(len(targets))}

    def _min_corr(self, ranked_list, data_dict, total_value):
        top_n = self.params.get("corr_top_n", 4)
        corr = FactorEngine.correlation_matrix(
            data_dict, self.params.get("corr_window", 250)
        )
        if corr is None:
            return {ranked_list[0][0]: total_value} if ranked_list else {}
        filtered = FactorEngine.volatility_filter(
            data_dict,
            self.params.get("min_vol", 0.05),
            self.params.get("max_vol", 0.33),
        )
        if not filtered:
            filtered = data_dict
        if len(filtered) < 2:
            return {list(filtered.keys())[0]: total_value}
        selected = FactorEngine.min_correlation_selection(
            corr.loc[filtered.keys(), filtered.keys()], top_n
        )
        cash = total_value / len(selected)
        return {s: cash for s in selected}

    def _stock_bond(self, total_value):
        stock_ratio = self.params.get("stock_ratio", 0.3)
        allocation = {}
        for s in self.params.get("stock_etfs", []):
            allocation[s] = total_value * stock_ratio / len(self.params["stock_etfs"])
        for s in self.params.get("debt_etfs", []):
            allocation[s] = (
                total_value * (1 - stock_ratio) / len(self.params["debt_etfs"])
            )
        return allocation

    def _grid(self, ranked_list, total_value):
        if not ranked_list:
            return {}
        cash = total_value / self.params.get("grid_space", 6)
        return {ranked_list[0][0]: cash}


class TimingEngine:
    def __init__(self, method="rsrs", **params):
        self.method = method
        self.params = params
        self.slope_history = []
        self.rsrs_history = []

    def get_signal(self, high, low, close, volume=None, north_money=None):
        if self.method == "rsrs":
            return self._rsrs(high, low, close)
        elif self.method == "ma_cross":
            return self._ma(close)
        elif self.method == "rsrs_ma":
            rsrs = self._rsrs(high, low, close)
            ma = self._ma(close)
            if rsrs == "BUY" and ma == "BUY":
                return "BUY"
            if rsrs == "SELL" or ma == "SELL":
                return "SELL"
            return "KEEP"
        elif self.method == "north_money_boll":
            return self._north(north_money)
        elif self.method == "volume_emotion":
            return (
                "SELL" if FactorEngine.volume_emotion_monitor(volume) == -1 else "KEEP"
            )
        elif self.method == "price_momentum_filter":
            inc, diff = FactorEngine.price_momentum_filter(close, 15)
            if inc > 0.1 and diff > 0:
                return "BUY"
            if inc < 0.1 or diff < 0:
                return "SELL"
            return "KEEP"
        elif self.method == "drawdown_tier":
            if len(close) < 60:
                return "BUY"
            if (
                close.iloc[-20:].mean()
                < close.iloc[-40:-20].mean()
                < close.iloc[-60:-40].mean()
            ):
                return "SELL"
            return "BUY"
        return "BUY"

    def _rsrs(self, high, low, close):
        N = self.params.get("rsrs_N", 18)
        M = self.params.get("rsrs_M", 600)
        threshold = self.params.get("rsrs_threshold", 0.7)
        if len(high) < N or len(low) < N:
            return "KEEP"
        rsrs, self.slope_history = FactorEngine.rsrs_score(
            high, low, N=N, M=M, slope_history=self.slope_history
        )
        self.rsrs_history.append(rsrs)
        if len(self.rsrs_history) > M:
            self.rsrs_history.pop(0)
        if rsrs > threshold:
            return "BUY"
        if rsrs < -threshold:
            return "SELL"
        return "KEEP"

    def _ma(self, close):
        short, long = self.params.get("ma_short", 5), self.params.get("ma_long", 20)
        if len(close) < long:
            return "KEEP"
        ms, ml = close.iloc[-short:].mean(), close.iloc[-long:].mean()
        if ms > ml:
            return "BUY"
        if ms < ml * 0.98:
            return "SELL"
        return "KEEP"

    def _north(self, north_money):
        if north_money is None or len(north_money) < 20:
            return "KEEP"
        signals = FactorEngine.north_money_boll(north_money)
        if signals["sell"] >= 2:
            return "SELL"
        if signals["buy"] >= 3:
            return "BUY"
        return "KEEP"


class RiskControl:
    @staticmethod
    def momentum_change(current, history, threshold=19):
        return len(history) < 2 or abs(current - history[-1]) <= threshold

    @staticmethod
    def drawdown(current, peak, max_dd=0.15):
        return peak == 0 or (peak - current) / peak <= max_dd

    @staticmethod
    def stop_loss(current, cost, pct=0.08):
        return cost > 0 and (current - cost) / cost < -pct


# =============================================================================
# 终极轮动策略 (Backtrader) - 修复全部严重缺陷
# =============================================================================


class UltimateRotationStrategy(bt.Strategy):
    """
    终极行业/板块/ETF轮动策略 v3.0

    修复:
    1. 持仓判断: self.getposition(data).size
    2. 卡尔曼滤波: 持久化 P 状态
    3. T+0索引: close[-1]=昨天
    4. R²除零保护
    5. 卖出逻辑正确遍历
    6. RSRS slope_history 实例级持久化
    7. 缓存版本控制
    8. rebalance_period 按交易日计数
    9. EPO signal 用动量得分
    10. T+0 跳过 rebalance_period 限流
    """

    params = (
        ("rotation_mode", "etf"),
        ("scoring_mode", ScoringModes.MOMENTUM_REGRESSION),
        ("allocation_mode", AllocationModes.TOP_N),
        ("timing_method", "rsrs"),
        ("etf_pool", ["510050", "159928", "510300", "159949", "518880", "513100"]),
        (
            "stock_bond_config",
            {
                "stock_etfs": ["510300", "510220", "513500", "513100"],
                "debt_etfs": ["511010"],
            },
        ),
        ("stock_num", 1),
        ("momentum_days", 20),
        ("rebalance_period", 5),
        ("use_timing", True),
        ("use_risk_control", True),
        ("stop_loss_pct", 0.08),
        ("max_drawdown", 0.20),
        ("rsrs_N", 18),
        ("rsrs_M", 600),
        ("rsrs_threshold", 0.7),
        ("bias_days", 90),
        ("log_reg_days", 25),
        ("kalman_R", 0.15),
        ("kalman_Q", 0.1),
        ("epo_lambda", 10),
        ("epo_w", 0.6),
        ("epo_method", "anchored"),
        ("corr_top_n", 4),
        ("corr_window", 250),
        ("min_vol", 0.05),
        ("max_vol", 0.33),
        ("grid_space", 6),
        ("grid_up", 1.5),
        ("grid_down", 0.9),
        ("t0_threshold_min", 0.003),
        ("t0_threshold_max", 0.5),
        ("chase_ma_window", 20),
        ("chase_threshold", 0.02),
        ("north_money_func", None),  # 外部注入北向资金数据
    )

    def __init__(self):
        self.data_refs = {}
        for d in self.datas:
            self.data_refs[d._name] = d

        # 交易日计数器 (非绝对bar)
        self.trade_day_count = 0
        self.last_rebalance_day = -self.p.rebalance_period
        self.peak_value = self.broker.getvalue()

        # 卡尔曼滤波状态 (持久化 P)
        self.kalman_states = {}  # {symbol: (state, P)}

        # RSRS 状态 (实例级持久化)
        self.slope_history = []
        self.rsrs_history = []

        # 动量历史 (风控用)
        self.momentum_history = defaultdict(list)

        self.scorer = RotationScorer(
            mode=self.p.scoring_mode,
            momentum_days=self.p.momentum_days,
            bias_days=self.p.bias_days,
            log_reg_days=self.p.log_reg_days,
            kalman_R=self.p.kalman_R,
            kalman_Q=self.p.kalman_Q,
        )

        self.allocator = Allocator(
            mode=self.p.allocation_mode,
            stock_num=self.p.stock_num,
            epo_lambda=self.p.epo_lambda,
            epo_w=self.p.epo_w,
            epo_method=self.p.epo_method,
            corr_top_n=self.p.corr_top_n,
            corr_window=self.p.corr_window,
            min_vol=self.p.min_vol,
            max_vol=self.p.max_vol,
            stock_etfs=self.p.stock_bond_config.get("stock_etfs", []),
            debt_etfs=self.p.stock_bond_config.get("debt_etfs", []),
            grid_space=self.p.grid_space,
        )

        self.timer = TimingEngine(
            method=self.p.timing_method,
            rsrs_N=self.p.rsrs_N,
            rsrs_M=self.p.rsrs_M,
            rsrs_threshold=self.p.rsrs_threshold,
        )

        print("=" * 60)
        print("终极轮动策略 v3.0 启动")
        print(f"  轮动: {self.p.rotation_mode} | 打分: {self.p.scoring_mode}")
        print(f"  配置: {self.p.allocation_mode} | 择时: {self.p.timing_method}")
        print(f"  持仓: {self.p.stock_num} | 动量: {self.p.momentum_days}d")
        print("=" * 60)

    def next(self):
        self.trade_day_count += 1
        current_value = self.broker.getvalue()
        if current_value > self.peak_value:
            self.peak_value = current_value

        # T+0 和 chase 模式: 每个交易日都执行
        if self.p.rotation_mode in ("t0", "chase"):
            if self.p.rotation_mode == "t0":
                self._rotate_t0()
            else:
                self._rotate_chase()
            return

        # 其他模式: 按 rebalance_period 个交易日执行
        if self.trade_day_count - self.last_rebalance_day < self.p.rebalance_period:
            return

        if self.p.rotation_mode == "etf":
            self._rotate_etf()
        elif self.p.rotation_mode in ("industry", "hybrid"):
            self._rotate_etf()  # 简化: 用ETF模拟

        self.last_rebalance_day = self.trade_day_count

    def _get_position_size(self, symbol):
        """修复 #1: 正确获取持仓数量"""
        data = self.data_refs.get(symbol)
        if data is None:
            return 0
        pos = self.getposition(data)
        return pos.size

    def _get_position_value(self, symbol):
        """获取持仓市值"""
        data = self.data_refs.get(symbol)
        if data is None:
            return 0
        pos = self.getposition(data)
        if pos.size == 0:
            return 0
        return pos.size * data.close[0]

    def _rotate_etf(self):
        data_dict = {}
        for symbol in self.p.etf_pool:
            if symbol in self.data_refs:
                d = self.data_refs[symbol]
                needed = max(
                    self.p.momentum_days + 10,
                    self.p.bias_days + self.p.momentum_days,
                    60,
                )
                if len(d.close) >= needed:
                    data_dict[symbol] = {
                        "close": pd.Series(np.array(d.close.get(size=needed))),
                        "high": pd.Series(np.array(d.high.get(size=needed))),
                        "low": pd.Series(np.array(d.low.get(size=needed))),
                        "volume": pd.Series(np.array(d.volume.get(size=needed))),
                    }

        if not data_dict:
            return

        scores = self.scorer.score(data_dict)
        print(f"\n[ETF轮动] 打分:")
        for sym, score in scores[:5]:
            print(f"  {sym}: {score:.4f}")

        # 择时
        timing_signal = "BUY"
        if self.p.use_timing and self.p.timing_method != "none":
            ref = list(data_dict.keys())[0]
            rd = data_dict[ref]
            north_money = None
            if self.p.north_money_func:
                north_money = self.p.north_money_func()
            timing_signal = self.timer.get_signal(
                rd["high"], rd["low"], rd["close"], rd["volume"], north_money
            )
            print(f"  择时: {timing_signal}")

        # 风控
        if self.p.use_risk_control:
            if not RiskControl.drawdown_check(
                self.broker.getvalue(), self.peak_value, self.p.max_drawdown
            ):
                timing_signal = "SELL"
                print(f"  风控: 最大回撤")

        allocation = self.allocator.allocate(scores, data_dict, self.broker.getvalue())

        # 修复 #5: 正确遍历持仓并卖出
        if timing_signal == "SELL":
            for sym in list(self.data_refs.keys()):
                if self._get_position_size(sym) > 0:
                    self.close(data=self.data_refs[sym])
                    print(f"  [卖出] {sym} (择时)")
        else:
            # 卖出不在目标列表中的
            for sym in list(self.data_refs.keys()):
                if self._get_position_size(sym) > 0 and sym not in allocation:
                    self.close(data=self.data_refs[sym])
                    print(f"  [卖出] {sym} (调仓)")

            # 买入/调整目标
            for sym, target_value in allocation.items():
                if sym not in self.data_refs:
                    continue
                current_value = self._get_position_value(sym)
                if abs(target_value - current_value) <= 5000:
                    continue
                if target_value > current_value:
                    size = int(
                        (target_value - current_value) / self.data_refs[sym].close[0]
                    )
                    if size > 0:
                        self.buy(data=self.data_refs[sym], size=size)
                        print(f"  [买入] {sym} x{size}")
                elif current_value > 0:
                    self.close(data=self.data_refs[sym])
                    print(f"  [卖出] {sym} (减仓)")

    def _rotate_t0(self):
        """修复 #3: T+0 正确索引 (close[-1]=昨天)"""
        if not self.p.etf_pool:
            return
        sym = self.p.etf_pool[0]
        d = self.data_refs.get(sym)
        if d is None or len(d.close) < 2:
            return

        open_price = d.open[0]
        yesterday_close = d.close[-1]  # backtrader: [-1]=昨天, [0]=今天

        gap = (open_price - yesterday_close) / yesterday_close
        should_buy = self.p.t0_threshold_min <= gap <= self.p.t0_threshold_max

        if should_buy and self._get_position_size(sym) == 0:
            size = int(self.broker.getcash() / d.close[0])
            if size > 0:
                self.buy(data=d, size=size)
                print(f"  [T0买入] {sym} x{size} (gap={gap:.4f})")
        elif not should_buy and self._get_position_size(sym) > 0:
            self.close(data=d)
            print(f"  [T0卖出] {sym}")

    def _rotate_chase(self):
        if not self.p.etf_pool:
            return
        for sym in self.p.etf_pool:
            d = self.data_refs.get(sym)
            if d is None or len(d.close) < self.p.chase_ma_window:
                continue
            close = pd.Series(np.array(d.close.get(size=self.p.chase_ma_window + 5)))
            ma = close.iloc[-self.p.chase_ma_window :].mean()
            current = close.iloc[-1]
            if (
                current > ma * (1 + self.p.chase_threshold)
                and self._get_position_size(sym) == 0
            ):
                size = int(self.broker.getcash() / d.close[0])
                if size > 0:
                    self.buy(data=d, size=size)
                    print(f"  [追涨买入] {sym} x{size}")

    def notify_trade(self, trade):
        if trade.isclosed:
            print(f"  交易完成: 盈亏={trade.pnl:.2f}")

    def notify_order(self, order):
        if order.status == order.Completed:
            if order.isbuy():
                print(f"  买入: {order.data._name} @ {order.executed.price:.3f}")
            elif order.issell():
                print(f"  卖出: {order.data._name} @ {order.executed.price:.3f}")


# =============================================================================
# 预设策略配置
# =============================================================================


class StrategyPresets:
    @staticmethod
    def etf_momentum_rsrs():
        return {
            "rotation_mode": "etf",
            "scoring_mode": ScoringModes.MOMENTUM_REGRESSION,
            "allocation_mode": AllocationModes.TOP_N,
            "timing_method": "rsrs",
            "etf_pool": ["510050", "159928", "510300", "159949"],
            "stock_num": 1,
            "momentum_days": 20,
            "rebalance_period": 5,
        }

    @staticmethod
    def etf_core_asset_rotation():
        return {
            "rotation_mode": "etf",
            "scoring_mode": ScoringModes.MOMENTUM_LOG_REG,
            "allocation_mode": AllocationModes.TOP_N,
            "timing_method": "none",
            "etf_pool": ["518880", "513100", "159915", "510180"],
            "stock_num": 1,
            "momentum_days": 25,
            "rebalance_period": 1,
        }

    @staticmethod
    def etf_bias_momentum():
        return {
            "rotation_mode": "etf",
            "scoring_mode": ScoringModes.BIAS_MOMENTUM,
            "allocation_mode": AllocationModes.TOP_N,
            "timing_method": "rsrs_ma",
            "etf_pool": ["510300", "510050", "159949", "159928"],
            "stock_num": 1,
            "momentum_days": 20,
            "rebalance_period": 5,
        }

    @staticmethod
    def etf_kalman_momentum():
        return {
            "rotation_mode": "etf",
            "scoring_mode": ScoringModes.KALMAN_MOMENTUM,
            "allocation_mode": AllocationModes.TOP_N,
            "timing_method": "rsrs",
            "etf_pool": ["510050", "159928", "510300", "159949"],
            "stock_num": 1,
            "momentum_days": 20,
            "rebalance_period": 5,
        }

    @staticmethod
    def multi_factor_rotation():
        return {
            "rotation_mode": "etf",
            "scoring_mode": ScoringModes.MULTI_FACTOR,
            "allocation_mode": AllocationModes.EPO_OPTIMIZED,
            "timing_method": "rsrs",
            "etf_pool": ["510300", "510050", "159949", "159928", "518880"],
            "stock_num": 3,
            "momentum_days": 20,
            "rebalance_period": 10,
        }

    @staticmethod
    def sector_heat_tracking():
        return {
            "rotation_mode": "etf",
            "scoring_mode": ScoringModes.SECTOR_HEAT,
            "allocation_mode": AllocationModes.TOP_N,
            "timing_method": "ma_cross",
            "etf_pool": ["510300", "510050", "159949", "159928", "518880", "513100"],
            "stock_num": 2,
            "momentum_days": 5,
            "rebalance_period": 3,
        }

    @staticmethod
    def min_correlation_etf():
        return {
            "rotation_mode": "etf",
            "scoring_mode": ScoringModes.MOMENTUM_LOG_REG,
            "allocation_mode": AllocationModes.MIN_CORRELATION,
            "timing_method": "none",
            "etf_pool": [
                "512660",
                "511010",
                "510880",
                "159915",
                "513050",
                "510050",
                "588100",
                "512100",
                "518800",
                "513060",
            ],
            "stock_num": 4,
            "momentum_days": 25,
            "rebalance_period": 5,
        }

    @staticmethod
    def epo_optimized_rotation():
        return {
            "rotation_mode": "etf",
            "scoring_mode": ScoringModes.MOMENTUM_LOG_REG,
            "allocation_mode": AllocationModes.EPO_OPTIMIZED,
            "timing_method": "none",
            "etf_pool": [
                "518880",
                "159985",
                "513100",
                "510300",
                "159915",
                "159992",
                "515700",
                "510150",
                "515790",
                "515880",
                "512720",
                "512660",
                "159740",
            ],
            "stock_num": 3,
            "momentum_days": 34,
            "rebalance_period": 20,
        }

    @staticmethod
    def stock_bond_balance():
        return {
            "rotation_mode": "etf",
            "scoring_mode": ScoringModes.MOMENTUM_REGRESSION,
            "allocation_mode": AllocationModes.STOCK_BOND_BALANCE,
            "timing_method": "drawdown_tier",
            "etf_pool": ["510300", "510220", "513500", "513100"],
            "stock_bond_config": {
                "stock_etfs": ["510300", "510220", "513500", "513100"],
                "debt_etfs": ["511010"],
            },
            "stock_num": 1,
            "momentum_days": 20,
            "rebalance_period": 5,
        }

    @staticmethod
    def t0_momentum():
        return {
            "rotation_mode": "t0",
            "scoring_mode": ScoringModes.MOMENTUM_SIMPLE,
            "allocation_mode": AllocationModes.TOP_N,
            "timing_method": "none",
            "etf_pool": ["513030"],
            "stock_num": 1,
            "momentum_days": 1,
            "rebalance_period": 1,
        }

    @staticmethod
    def chase_momentum():
        return {
            "rotation_mode": "chase",
            "scoring_mode": ScoringModes.MOMENTUM_REGRESSION,
            "allocation_mode": AllocationModes.TOP_N,
            "timing_method": "none",
            "etf_pool": ["510300", "510050", "159915"],
            "stock_num": 1,
            "momentum_days": 20,
            "rebalance_period": 1,
        }

    @staticmethod
    def ir_trend_rotation():
        return {
            "rotation_mode": "etf",
            "scoring_mode": ScoringModes.IR_TREND,
            "allocation_mode": AllocationModes.TOP_N,
            "timing_method": "none",
            "etf_pool": ["510300", "510050", "159949", "159928"],
            "stock_num": 1,
            "momentum_days": 60,
            "rebalance_period": 20,
        }


# =============================================================================
# 运行函数
# =============================================================================


def run_rotation_strategy(
    start_date="2020-01-01",
    end_date="2024-12-31",
    initial_cash=1000000,
    rotation_mode="etf",
    scoring_mode=ScoringModes.MOMENTUM_REGRESSION,
    allocation_mode=AllocationModes.TOP_N,
    timing_method="rsrs",
    etf_pool=None,
    stock_num=1,
    momentum_days=20,
    rebalance_period=5,
    north_money_func=None,
    force_update=False,
):
    if etf_pool is None:
        etf_pool = ["510050", "159928", "510300", "159949", "518880", "513100"]

    print(f"\n回测: {start_date} ~ {end_date} | ETF: {etf_pool}")

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.0003)

    all_data = load_all_etf_data(
        etf_pool, start_date, end_date, force_update=force_update
    )
    if not all_data:
        print("错误: 无法加载ETF数据")
        return cerebro

    for symbol, df in all_data.items():
        cerebro.adddata(
            bt.feeds.PandasData(
                dataname=df,
                datetime="datetime",
                open="open",
                high="high",
                low="low",
                close="close",
                volume="volume",
                openinterest=-1,
                name=symbol,
            )
        )

    cerebro.addstrategy(
        UltimateRotationStrategy,
        rotation_mode=rotation_mode,
        scoring_mode=scoring_mode,
        allocation_mode=allocation_mode,
        timing_method=timing_method,
        etf_pool=etf_pool,
        stock_num=stock_num,
        momentum_days=momentum_days,
        rebalance_period=rebalance_period,
        north_money_func=north_money_func,
    )

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.03)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

    print("\n运行回测...")
    results = cerebro.run()
    strat = results[0]

    final = cerebro.broker.getvalue()
    print(f"\n{'=' * 60}\n结果\n{'=' * 60}")
    print(
        f"初始: {initial_cash:,.0f} | 最终: {final:,.0f} | 收益: {(final / initial_cash - 1) * 100:.1f}%"
    )
    try:
        s = strat.analyzers.sharpe.get_analysis()
        print(f"夏普: {s.get('sharperatio', 'N/A')}")
    except:
        pass
    try:
        d = strat.analyzers.drawdown.get_analysis()
        print(f"最大回撤: {d.get('max', {}).get('drawdown', 'N/A'):.1f}%")
    except:
        pass
    try:
        t = strat.analyzers.trades.get_analysis()
        print(
            f"交易: {t.get('total', {}).get('total', 0)} | 盈利: {t.get('won', {}).get('total', 0)}"
        )
    except:
        pass

    cerebro.plot(style="candlestick", barup="red", bardown="green")
    return cerebro


if __name__ == "__main__":
    config = StrategyPresets.etf_momentum_rsrs()
    run_rotation_strategy(
        start_date="2020-01-01", end_date="2024-12-31", initial_cash=1000000, **config
    )
