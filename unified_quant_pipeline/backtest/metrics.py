"""风险指标计算"""

import numpy as np
import pandas as pd
from typing import Dict, Optional


def calculate_returns(nav: pd.Series) -> pd.Series:
    """计算日收益率"""
    return nav.pct_change()


def calculate_annual_return(nav: pd.Series) -> float:
    """计算年化收益率"""
    if len(nav) < 2:
        return 0.0
    days = (nav.index[-1] - nav.index[0]).days
    if days == 0:
        return 0.0
    total_return = nav.iloc[-1] / nav.iloc[0] - 1
    return (1 + total_return) ** (365 / days) - 1


def calculate_max_drawdown(nav: pd.Series) -> float:
    """计算最大回撤"""
    rolling_max = nav.cummax()
    drawdown = (nav - rolling_max) / rolling_max
    return drawdown.min()


def calculate_volatility(nav: pd.Series, annualize: bool = True) -> float:
    """计算波动率"""
    returns = nav.pct_change().dropna()
    vol = returns.std()
    if annualize:
        vol *= np.sqrt(252)
    return vol


def calculate_sharpe(nav: pd.Series, risk_free: float = 0.02) -> float:
    """计算夏普比率"""
    returns = nav.pct_change().dropna()
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    excess_return = returns.mean() - risk_free / 252
    return excess_return / returns.std() * np.sqrt(252)


def calculate_sortino(nav: pd.Series, risk_free: float = 0.02) -> float:
    """计算索提诺比率"""
    returns = nav.pct_change().dropna()
    if len(returns) == 0:
        return 0.0
    downside = returns[returns < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    excess_return = returns.mean() - risk_free / 252
    return excess_return / downside.std() * np.sqrt(252)


def calculate_calmar(nav: pd.Series) -> float:
    """计算卡尔马比率（年化收益/最大回撤）"""
    ann_return = calculate_annual_return(nav)
    max_dd = abs(calculate_max_drawdown(nav))
    if max_dd == 0:
        return 0.0
    return ann_return / max_dd


def calculate_win_rate(nav: pd.Series) -> float:
    """计算胜率"""
    returns = nav.pct_change().dropna()
    if len(returns) == 0:
        return 0.0
    return (returns > 0).sum() / len(returns)


def calculate_profit_loss_ratio(nav: pd.Series) -> float:
    """计算盈亏比"""
    returns = nav.pct_change().dropna()
    profits = returns[returns > 0]
    losses = returns[returns < 0]
    if len(losses) == 0 or losses.mean() == 0:
        return 0.0
    return profits.mean() / abs(losses.mean())


def calculate_turnover(weights_prev: Dict, weights_curr: Dict) -> float:
    """计算换手率"""
    all_codes = set(list(weights_prev.keys()) + list(weights_curr.keys()))
    turnover = sum(
        abs(weights_prev.get(c, 0) - weights_curr.get(c, 0)) for c in all_codes
    )
    return turnover / 2


def calculate_beta(nav: pd.Series, benchmark_nav: pd.Series) -> float:
    """计算Beta"""
    returns = nav.pct_change().dropna()
    bench_returns = benchmark_nav.pct_change().dropna()
    common_idx = returns.index.intersection(bench_returns.index)
    if len(common_idx) < 10:
        return 1.0
    cov = returns.loc[common_idx].cov(bench_returns.loc[common_idx])
    var = bench_returns.loc[common_idx].var()
    if var == 0:
        return 1.0
    return cov / var


def calculate_alpha(
    nav: pd.Series, benchmark_nav: pd.Series, risk_free: float = 0.02
) -> float:
    """计算Alpha（年化）"""
    ann_return = calculate_annual_return(nav)
    bench_return = calculate_annual_return(benchmark_nav)
    beta = calculate_beta(nav, benchmark_nav)
    return ann_return - (risk_free + beta * (bench_return - risk_free))


def calculate_all_metrics(
    nav: pd.Series, benchmark_nav: Optional[pd.Series] = None, risk_free: float = 0.02
) -> Dict[str, float]:
    """计算所有指标"""
    metrics = {
        "total_return": nav.iloc[-1] / nav.iloc[0] - 1,
        "annual_return": calculate_annual_return(nav),
        "max_drawdown": calculate_max_drawdown(nav),
        "volatility": calculate_volatility(nav),
        "sharpe": calculate_sharpe(nav, risk_free),
        "sortino": calculate_sortino(nav, risk_free),
        "calmar": calculate_calmar(nav),
        "win_rate": calculate_win_rate(nav),
        "profit_loss_ratio": calculate_profit_loss_ratio(nav),
        "n_days": len(nav),
    }

    if benchmark_nav is not None:
        excess_nav = nav / benchmark_nav
        metrics["excess_return"] = calculate_annual_return(
            nav
        ) - calculate_annual_return(benchmark_nav)
        metrics["information_ratio"] = calculate_sharpe(excess_nav)
        metrics["tracking_error"] = calculate_volatility(excess_nav)
        metrics["beta"] = calculate_beta(nav, benchmark_nav)
        metrics["alpha"] = calculate_alpha(nav, benchmark_nav, risk_free)

    return metrics
