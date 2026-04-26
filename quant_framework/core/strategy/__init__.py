# -*- coding: utf-8 -*-
"""
Strategy layer: BaseStrategy and strategy utilities.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class PositionType(Enum):
    LONG = 1
    SHORT = -1
    FLAT = 0


@dataclass
class Position:
    """Represents a single position in the portfolio."""

    code: str
    weight: float
    entry_date: Optional[date] = None
    entry_price: float = 0.0
    current_price: float = 0.0

    @property
    def pnl_pct(self) -> float:
        if self.entry_price <= 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price


@dataclass
class StrategyConfig:
    """Configuration for a strategy run."""

    name: str = ""
    start_date: str = "2020-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 1_000_000.0
    benchmark: str = "000300"
    data_source: str = "akshare"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeRecord:
    """A single trade record."""

    date: date
    code: str
    action: str  # 'buy' or 'sell'
    price: float
    quantity: int
    amount: float
    commission: float = 0.0
    slippage: float = 0.0


class BaseStrategy(ABC):
    """
    Abstract base class for all strategies.

    Subclasses must implement:
        - name: Strategy name
        - generate_signals: Core signal generation logic
        - get_params: Parameter dictionary

    The framework handles data loading, backtesting, and performance analysis.
    """

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()
        self._positions: Dict[str, Position] = {}
        self._trades: List[TradeRecord] = []
        self._nav_history: List[float] = []
        self._signal_history: List[pd.DataFrame] = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the strategy name."""
        ...

    @abstractmethod
    def generate_signals(self, data: Dict[str, Any]) -> pd.DataFrame:
        """
        Generate trading signals from input data.

        Parameters:
            data: Dictionary containing price data, factors, indicators, etc.

        Returns:
            DataFrame with columns: date, code, signal (-1/0/1), weight
        """
        ...

    @abstractmethod
    def get_params(self) -> Dict[str, Any]:
        """Return current strategy parameters."""
        ...

    def set_params(self, **kwargs) -> None:
        """Update strategy parameters."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            self.config.params[key] = value

    def run_backtest(
        self,
        data: Dict[str, Any],
        initial_capital: float = 1_000_000.0,
    ) -> pd.DataFrame:
        """
        Run a simple event-driven backtest.

        Parameters:
            data: Input data dictionary
            initial_capital: Starting capital

        Returns:
            DataFrame with daily NAV, returns, drawdown
        """
        signals = self.generate_signals(data)
        if signals.empty:
            return pd.DataFrame()

        signals["date"] = pd.to_datetime(signals["date"])
        signals = signals.sort_values("date").reset_index(drop=True)

        capital = initial_capital
        positions: Dict[str, float] = {}
        nav_history = []
        dates = sorted(signals["date"].unique())

        for dt in dates:
            day_signals = signals[signals["date"] == dt]
            price_data = data.get("prices", {})

            target_codes = set()
            for _, row in day_signals.iterrows():
                code = row["code"]
                sig = row.get("signal", 0)
                weight = row.get("weight", 0.0)

                if sig > 0 and weight > 0:
                    target_codes.add(code)

            for code in list(positions.keys()):
                if code not in target_codes:
                    price = self._get_price(price_data, code, dt)
                    if price > 0:
                        capital += positions[code] * price
                    del positions[code]

            available = capital
            if target_codes:
                per_stock = available / len(target_codes)
                for code in target_codes:
                    price = self._get_price(price_data, code, dt)
                    if price > 0 and code not in positions:
                        qty = int(per_stock / price / 100) * 100
                        if qty > 0:
                            positions[code] = qty
                            capital -= qty * price * 1.001

            day_nav = capital
            for code, qty in positions.items():
                price = self._get_price(price_data, code, dt)
                day_nav += qty * price

            nav_history.append({"date": dt, "nav": day_nav})

        nav_df = pd.DataFrame(nav_history)
        if nav_df.empty:
            return nav_df

        nav_df["return"] = nav_df["nav"].pct_change()
        nav_df["cum_return"] = nav_df["nav"] / nav_df["nav"].iloc[0] - 1
        peak = nav_df["nav"].cummax()
        nav_df["drawdown"] = (nav_df["nav"] - peak) / peak
        self._nav_history = nav_history
        return nav_df

    def _get_price(
        self, price_data: Dict[str, pd.DataFrame], code: str, dt: pd.Timestamp
    ) -> float:
        if code in price_data:
            df = price_data[code]
            if isinstance(df.index, pd.DatetimeIndex):
                mask = df.index <= dt
                if mask.any():
                    return df.loc[mask, "close"].iloc[-1]
            elif "date" in df.columns:
                sub = df[df["date"] <= dt]
                if not sub.empty:
                    return sub["close"].iloc[-1]
            elif "close" in df.index.names or "close" in df.columns:
                if "close" in df.columns:
                    sub = df[df.index <= dt]
                    if not sub.empty:
                        return sub["close"].iloc[-1]
        return 0.0

    def compute_performance(self, nav_df: pd.DataFrame) -> Dict[str, float]:
        """Compute performance metrics from NAV series."""
        if nav_df.empty or len(nav_df) < 2:
            return {}

        returns = nav_df["return"].dropna()
        total_return = nav_df["nav"].iloc[-1] / nav_df["nav"].iloc[0] - 1
        n_days = len(returns)
        ann_return = (1 + total_return) ** (252 / max(n_days, 1)) - 1
        ann_vol = returns.std() * np.sqrt(252)
        sharpe = ann_return / ann_vol if ann_vol > 0 else 0.0
        max_dd = nav_df["drawdown"].min()

        positive_days = (returns > 0).sum()
        win_rate = positive_days / len(returns) if len(returns) > 0 else 0.0

        return {
            "total_return": total_return,
            "annual_return": ann_return,
            "annual_volatility": ann_vol,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "trading_days": n_days,
        }

    def prepare_data(
        self,
        data_manager,
        symbols: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Prepare data dictionary for signal generation.

        Parameters:
            data_manager: DataManager instance
            symbols: Stock symbols (None for all)
            start_date: Start date override
            end_date: End date override

        Returns:
            Dictionary with price data and derived indicators
        """
        sd = start_date or self.config.start_date
        ed = end_date or self.config.end_date

        data = {"start_date": sd, "end_date": ed}

        if symbols:
            data["prices"] = data_manager.get_stock_price(symbols, sd, ed)
        else:
            data["prices"] = {}

        return data
