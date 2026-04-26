"""
分析器集合 (Analyzers)
======================

提供策略绩效分析和交易记录功能。
"""

import backtrader as bt
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional


class TradeRecordAnalyzer(bt.Analyzer):
    """
    详细交易记录分析器

    记录每笔交易的完整信息：
    - 入场/出场时间和价格
    - 盈亏金额和比例
    - 持仓周期
    - 最大有利/不利变动 (MFE/MAE)
    """

    def __init__(self):
        super().__init__()
        self.trades: List[Dict[str, Any]] = []
        self.cumprofit = 0.0
        self._current_trade = None

    def notify_trade(self, trade: bt.Trade):
        """交易状态更新"""
        self._current_trade = trade

        if not trade.isclosed:
            return

        record = self._get_trade_record(trade)
        self.trades.append(record)

    def stop(self):
        """处理未平仓交易"""
        trade = self._current_trade
        if trade and trade.isopen:
            record = self._get_trade_record(trade, closed=False)
            self.trades.append(record)

    def _get_trade_record(self, trade: bt.Trade, closed: bool = True) -> Dict[str, Any]:
        """生成交易记录"""
        brokervalue = self.strategy.broker.getvalue()
        history = trade.history or []
        size = len(history)

        # 方向（history 可能为空，fallback 到 trade.size）
        if size > 0:
            dir_str = "long" if history[0].event.size > 0 else "short"
        else:
            dir_str = "long" if (getattr(trade, 'size', 0) or 0) >= 0 else "short"

        # 基础信息
        barlen = history[size - 1].status.barlen if size > 0 else 0
        pricein = history[0].status.price if size > 0 else 0
        datein = bt.num2date(history[0].status.dt) if size > 0 else None

        if closed and size > 0:
            dateout = bt.num2date(history[size - 1].status.dt)
            priceout = history[size - 1].event.price
            # 计算 MFE/MAE
            try:
                highest = max(trade.data.high.get(ago=0, size=barlen + 1))
                lowest = min(trade.data.low.get(ago=0, size=barlen + 1))
                hp = 100 * (highest - pricein) / pricein if pricein else 0
                lp = 100 * (lowest - pricein) / pricein if pricein else 0
            except Exception:
                hp, lp = np.nan, np.nan
        else:
            dateout = pd.to_datetime(trade.data.datetime.date(0))
            priceout = trade.data.close[0]
            hp = np.nan
            lp = np.nan
            barlen = np.nan

        # 转换日期格式
        if trade.data._timeframe >= bt.TimeFrame.Days:
            datein = datein.date() if datein else None
            dateout = dateout.date() if hasattr(dateout, 'date') else dateout

        # 盈亏计算
        pcntchange = 100 * priceout / pricein - 100 if pricein else 0
        pnl = history[size - 1].status.pnlcomm if size > 0 else 0
        pnlpcnt = 100 * pnl / brokervalue if brokervalue else 0

        self.cumprofit += pnl

        # 最大持仓
        max_size = 0
        max_value = 0.0
        for record in history:
            if abs(max_size) < abs(record.status.size):
                max_size = record.status.size
                max_value = record.status.value

        # MFE/MAE
        if dir_str == "long":
            mfe = hp
            mae = lp
        else:
            mfe = -lp
            mae = -hp

        return {
            "status": "closed" if closed else "open",
            "ref": trade.ref,
            "ticker": trade.data._name,
            "direction": dir_str,
            "date_in": datein,
            "price_in": round(pricein, 3),
            "date_out": dateout,
            "price_out": round(priceout, 3),
            "return_pct": round(pcntchange, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnlpcnt, 2),
            "size": max_size,
            "value": round(max_value, 2),
            "cum_pnl": round(self.cumprofit, 2),
            "bars": barlen,
            "pnl_per_bar": round(pnl / barlen, 2) if barlen and not np.isnan(barlen) else np.nan,
            "mfe_pct": round(mfe, 2),
            "mae_pct": round(mae, 2),
        }

    def get_analysis(self) -> List[Dict[str, Any]]:
        """返回交易记录列表"""
        return self.trades

    def get_dataframe(self) -> pd.DataFrame:
        """返回交易记录 DataFrame"""
        return pd.DataFrame(self.trades)


class PerformanceAnalyzer(bt.Analyzer):
    """
    绩效分析器

    计算关键绩效指标：
    - 总收益率、年化收益率
    - 夏普比率、索提诺比率
    - 最大回撤
    - Alpha、Beta
    """

    def __init__(self):
        super().__init__()
        self.returns: List[float] = []
        self.dates: List[Any] = []
        self.values: List[float] = []

    def next(self):
        """记录每个 bar 的权益"""
        self.values.append(self.strategy.broker.getvalue())
        self.dates.append(self.strategy.datas[0].datetime.date(0))

    def stop(self):
        """计算绩效指标"""
        if len(self.values) < 2:
            self.ret = pd.Series()
            return

        self.values_series = pd.Series(self.values, index=self.dates)
        self.ret = self.values_series.pct_change().dropna()

    def get_analysis(self) -> Dict[str, float]:
        """返回绩效指标字典"""
        if len(self.ret) < 2:
            return self._empty_metrics()

        total_return = self.values[-1] / self.values[0] - 1 if self.values[0] != 0 else 0
        days = len(self.ret)
        annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0

        # 夏普比率
        sharpe = self.ret.mean() / self.ret.std() * np.sqrt(252) if self.ret.std() != 0 else 0

        # 最大回撤
        roll_max = self.values_series.cummax()
        drawdown = (self.values_series - roll_max) / roll_max
        max_dd = drawdown.min()

        # 索提诺比率
        neg_ret = self.ret[self.ret < 0]
        downside_std = np.sqrt(np.mean(neg_ret ** 2)) if len(neg_ret) > 0 else 0
        sortino = self.ret.mean() / downside_std * np.sqrt(252) if downside_std != 0 else 0

        # 胜率
        win_rate = len(self.ret[self.ret > 0]) / len(self.ret) if len(self.ret) > 0 else 0

        return {
            "total_return": total_return,
            "annual_return": annual_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "sortino_ratio": sortino,
            "win_rate": win_rate,
            "volatility": self.ret.std() * np.sqrt(252),
            "total_days": days,
        }

    def _empty_metrics(self) -> Dict[str, float]:
        """空指标"""
        return {
            "total_return": 0.0,
            "annual_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "sortino_ratio": 0.0,
            "win_rate": 0.0,
            "volatility": 0.0,
            "total_days": 0,
        }

    def get_nav_series(self) -> pd.Series:
        """返回净值序列"""
        return pd.Series(self.values, index=self.dates)


def analyze_performance(
    strategy_nav: pd.Series,
    benchmark_nav: Optional[pd.Series] = None
) -> pd.DataFrame:
    """
    绩效分析函数

    Args:
        strategy_nav: 策略净值序列
        benchmark_nav: 基准净值序列（可选）

    Returns:
        绩效指标 DataFrame
    """
    strategy_nav = pd.Series(strategy_nav)

    if len(strategy_nav) < 2:
        return pd.DataFrame([{
            "总收益率": np.nan, "年化收益率": np.nan,
            "夏普比率": np.nan, "信息比率": np.nan,
            "Alpha(年化)": np.nan, "Beta": np.nan,
            "最大回撤": np.nan, "索提诺比率": np.nan
        }])

    strategy_ret = strategy_nav.pct_change().dropna()

    total_return = strategy_nav.iloc[-1] / strategy_nav.iloc[0] - 1
    days = len(strategy_ret)
    annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else np.nan

    # 基础指标
    sharpe = strategy_ret.mean() / strategy_ret.std() * np.sqrt(252) if strategy_ret.std() != 0 else np.nan

    # 最大回撤
    roll_max = strategy_nav.cummax()
    drawdown = (strategy_nav - roll_max) / roll_max
    max_dd = drawdown.min()

    # 索提诺
    neg_ret = strategy_ret[strategy_ret < 0]
    downside_std = np.sqrt(np.mean(neg_ret ** 2)) if len(neg_ret) > 0 else np.nan
    sortino = strategy_ret.mean() / downside_std * np.sqrt(252) if downside_std and downside_std != 0 else np.nan

    result = {
        "总收益率": total_return,
        "年化收益率": annual_return,
        "夏普比率": sharpe,
        "最大回撤": max_dd,
        "索提诺比率": sortino,
    }

    # 基准相关指标
    if benchmark_nav is not None:
        benchmark_nav = pd.Series(benchmark_nav).reindex(strategy_nav.index).ffill()
        benchmark_ret = benchmark_nav.pct_change().dropna().reindex(strategy_ret.index).fillna(0)

        excess_ret = strategy_ret - benchmark_ret
        info_ratio = excess_ret.mean() / excess_ret.std() * np.sqrt(252) if excess_ret.std() != 0 else np.nan

        # Alpha/Beta
        try:
            import statsmodels.api as sm
            X = sm.add_constant(benchmark_ret)
            model = sm.OLS(strategy_ret, X).fit()
            alpha = model.params['const'] * 252
            beta = model.params.get(benchmark_ret.name, np.nan)
        except ImportError:
            alpha, beta = np.nan, np.nan

        result.update({
            "信息比率": info_ratio,
            "Alpha(年化)": alpha,
            "Beta": beta,
        })

    return pd.DataFrame([result])


# ====== 其他实用分析器 ======

class SQNAnalyzer(bt.Analyzer):
    """
    系统质量数 (System Quality Number)
    Van K. Tharp 提出，用于评估交易系统质量

    SQN < 1.7    : 较差
    1.7 ~ 2.0    : 一般
    2.0 ~ 2.5    : 良好
    2.5 ~ 3.0    : 优秀
    > 3.0        : 卓越
    """

    def __init__(self):
        self.pnls = []

    def notify_trade(self, trade):
        if trade.isclosed:
            self.pnls.append(trade.pnlcomm)

    def get_analysis(self):
        if len(self.pnls) < 2:
            return {"sqn": 0, "count": len(self.pnls)}

        arr = np.array(self.pnls)
        mean = arr.mean()
        std = arr.std()
        sqn = np.sqrt(len(arr)) * mean / std if std != 0 else 0

        return {
            "sqn": sqn,
            "count": len(arr),
            "mean": mean,
            "std": std,
        }
