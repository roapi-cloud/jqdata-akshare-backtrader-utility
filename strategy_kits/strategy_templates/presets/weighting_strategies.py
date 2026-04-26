"""Preset weighting strategies migrated from SBS for single-strategy research."""
from __future__ import annotations

from datetime import date
from typing import Dict, Optional, Union

import pandas as pd

from ...contracts import validate_prediction_frame
from ...execution.backtrader_runtime.compat import JQ2BTBaseStrategy


class BasePredictionStrategy(JQ2BTBaseStrategy):
    """Base strategy driven by prediction DataFrame.

    Expected prediction columns:
    - ``date`` (YYYY-MM-DD or datetime-like)
    - ``code`` (stock code)
    - ``weight`` (optional, defaults to 1.0)
    """

    params = (
        ("pred_df", None),
        ("weight_column", "weight"),
        ("rebalance_threshold", 0.01),
        ("hold_days", 1),
        ("top_n_stocks", 10),
    )

    def __init__(self):
        super().__init__()
        self.pred_df = self._prepare_pred_df(self.p.pred_df)
        self.holdings: Dict[str, date] = {}
        self.trade_history: list[dict] = []
        self.daily_holdings: list[dict] = []

    @staticmethod
    def _prepare_pred_df(pred_df: Optional[Union[pd.DataFrame, str]]) -> pd.DataFrame:
        if pred_df is None:
            return pd.DataFrame(columns=["date", "code", "weight"])

        if isinstance(pred_df, str):
            df = pd.read_json(pred_df)
        else:
            df = pred_df.copy()

        df = validate_prediction_frame(df)
        return df.dropna(subset=["date", "code"]).copy()

    def initialize(self, context):
        # We run strategy logic on each bar in ``next``.
        return None

    def _record_trade(self, code: str, action: str, size: int, price: float, value: float):
        self.trade_history.append(
            {
                "date": self.current_dt.date() if self.current_dt is not None else None,
                "code": code,
                "action": action,
                "size": size,
                "price": price,
                "value": value,
                "portfolio_value": self.broker.getvalue(),
            }
        )

    def _record_holdings(self):
        rows = []
        total_value = self.broker.getvalue()

        for code, buy_date in list(self.holdings.items()):
            try:
                data = self._find_data(code)
            except ValueError:
                continue

            position = self.getposition(data)
            if position.size <= 0:
                continue

            market_value = position.size * data.close[0]
            rows.append(
                {
                    "code": code,
                    "size": int(position.size),
                    "price": float(data.close[0]),
                    "value": float(market_value),
                    "weight": float(market_value / total_value) if total_value > 0 else 0.0,
                    "buy_date": buy_date,
                }
            )

        self.daily_holdings.append(
            {
                "date": self.current_dt.date() if self.current_dt is not None else None,
                "holdings": rows,
                "total_value": float(total_value),
                "cash": float(self.broker.getcash()),
            }
        )

    def execute_strategy(self):
        raise NotImplementedError("Subclasses must implement execute_strategy")

    def next(self):
        super().next()
        if self.current_dt is None:
            return
        self.execute_strategy()
        self._record_holdings()


class WeightedTopNStrategy(BasePredictionStrategy):
    """Weighted strategy using prediction weight as ranking + target allocation."""

    def execute_strategy(self):
        dt = self.current_dt.date()
        today_df = self.pred_df[self.pred_df["date"] == pd.Timestamp(dt)]
        if today_df.empty:
            return

        hold_days = max(1, int(self.p.hold_days))
        threshold = float(self.p.rebalance_threshold)
        weight_col = self.p.weight_column

        expired_codes = []
        for code, buy_date in list(self.holdings.items()):
            if (dt - buy_date).days < hold_days:
                continue
            try:
                data = self._find_data(code)
            except ValueError:
                continue
            position = self.getposition(data)
            if position.size > 0:
                self.order_target_value(data=data, target=0)
                self._record_trade(code, "SELL", int(-position.size), float(data.close[0]), float(position.size * data.close[0]))
            expired_codes.append(code)

        for code in expired_codes:
            self.holdings.pop(code, None)

        if weight_col in today_df.columns:
            today_df = today_df.sort_values(weight_col, ascending=False)

        total_weight = float(today_df[weight_col].sum()) if weight_col in today_df.columns else 0.0
        if total_weight <= 0:
            return

        total_value = float(self.broker.getvalue())
        if total_value <= 0:
            return

        for _, row in today_df.iterrows():
            code = str(row["code"]).zfill(6)
            try:
                data = self._find_data(code)
            except ValueError:
                continue

            weight = float(getattr(row, weight_col, 0.0))
            target_value = total_value * (weight / total_weight)
            position = self.getposition(data)
            current_value = float(position.size * data.close[0]) if position.size > 0 else 0.0

            if abs(target_value - current_value) / total_value <= threshold:
                continue

            size_change = int((target_value - current_value) / data.close[0])
            self.order_target_value(data=data, target=target_value)
            if size_change != 0:
                action = "BUY" if size_change > 0 else "SELL"
                traded_value = abs(size_change) * float(data.close[0])
                self._record_trade(code, action, size_change, float(data.close[0]), float(traded_value))
                if size_change > 0:
                    self.holdings[code] = dt


class EqualWeightStrategy(BasePredictionStrategy):
    """Equal-weight strategy over top-N prediction rows each day."""

    def execute_strategy(self):
        dt = self.current_dt.date()
        today_df = self.pred_df[self.pred_df["date"] == pd.Timestamp(dt)]
        if today_df.empty:
            return

        top_n = max(1, int(self.p.top_n_stocks))
        threshold = float(self.p.rebalance_threshold)

        if len(today_df) > top_n:
            today_df = today_df.head(top_n)

        current_codes = set(today_df["code"].astype(str).str.zfill(6))
        removed_codes = []

        for code in list(self.holdings.keys()):
            if code in current_codes:
                continue
            try:
                data = self._find_data(code)
            except ValueError:
                continue
            position = self.getposition(data)
            if position.size > 0:
                self.order_target_value(data=data, target=0)
                self._record_trade(code, "SELL", int(-position.size), float(data.close[0]), float(position.size * data.close[0]))
            removed_codes.append(code)

        for code in removed_codes:
            self.holdings.pop(code, None)

        total_value = float(self.broker.getvalue())
        n_stocks = len(today_df)
        if n_stocks == 0 or total_value <= 0:
            return

        target_value = total_value * (1.0 / n_stocks)

        for _, row in today_df.iterrows():
            code = str(row["code"]).zfill(6)
            try:
                data = self._find_data(code)
            except ValueError:
                continue

            position = self.getposition(data)
            current_value = float(position.size * data.close[0]) if position.size > 0 else 0.0
            if abs(target_value - current_value) / total_value <= threshold:
                continue

            size_change = int((target_value - current_value) / data.close[0])
            self.order_target_value(data=data, target=target_value)
            if size_change != 0:
                action = "BUY" if size_change > 0 else "SELL"
                self._record_trade(code, action, size_change, float(data.close[0]), float(abs(size_change) * data.close[0]))
                if size_change > 0:
                    self.holdings[code] = dt


class DirectExecutionStrategy(BasePredictionStrategy):
    """Directly execute prediction weights as daily full target."""

    def execute_strategy(self):
        dt = self.current_dt.date()
        today_df = self.pred_df[self.pred_df["date"] == pd.Timestamp(dt)]
        if today_df.empty:
            return

        threshold = float(self.p.rebalance_threshold)
        weight_col = self.p.weight_column
        total_value = float(self.broker.getvalue())
        if total_value <= 0:
            return

        for _, row in today_df.iterrows():
            code = str(row["code"]).zfill(6)
            try:
                data = self._find_data(code)
            except ValueError:
                continue

            weight = float(getattr(row, weight_col, 0.0))
            if weight <= 0:
                continue

            target_value = total_value * weight
            position = self.getposition(data)
            current_value = float(position.size * data.close[0]) if position.size > 0 else 0.0
            if abs(target_value - current_value) / total_value <= threshold:
                continue

            size_change = int((target_value - current_value) / data.close[0])
            self.order_target_value(data=data, target=target_value)
            if size_change != 0:
                action = "BUY" if size_change > 0 else "SELL"
                traded_value = abs(size_change) * float(data.close[0])
                self._record_trade(code, action, size_change, float(data.close[0]), float(traded_value))
                if size_change > 0:
                    self.holdings[code] = dt


__all__ = [
    "BasePredictionStrategy",
    "WeightedTopNStrategy",
    "EqualWeightStrategy",
    "DirectExecutionStrategy",
]
