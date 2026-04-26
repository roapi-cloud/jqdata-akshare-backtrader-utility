"""risk_manager: advanced risk management with VaR, CVaR, stress testing, and portfolio analytics
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Union
import pandas as pd
import numpy as np
import logging


logger = logging.getLogger(__name__)


class PortfolioReturnsMixin:
    """Mixin providing common portfolio returns calculation for risk rules"""

    def _calculate_portfolio_returns(
        self, weights: pd.DataFrame, returns_data: pd.DataFrame
    ) -> Union[np.ndarray, pd.Series]:
        """Calculate portfolio returns from individual asset returns"""
        weighted_returns = pd.DataFrame()

        for _, row in weights.iterrows():
            code = str(row['code'])
            weight = row['target_weight']
            if code in returns_data.columns:
                weighted_returns[code] = returns_data[code] * weight

        return weighted_returns.sum(axis=1)


class RiskRule:
    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return ctx


class BlacklistRule(RiskRule):
    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        # ctx expects 'weights' DataFrame and 'blacklist' DataFrame
        weights: pd.DataFrame = ctx.get("weights", pd.DataFrame())
        blacklist: pd.DataFrame = ctx.get("blacklist", pd.DataFrame())
        if weights.empty or blacklist.empty:
            return ctx
        bad = set(blacklist.code.astype(str).tolist())
        ctx["weights"] = weights[~weights.code.astype(str).isin(bad)].reset_index(drop=True)
        ctx.setdefault("risk_logs", []).append({"rule": "blacklist", "removed": len(weights) - len(ctx["weights"])})
        return ctx


class MarketCapRule(RiskRule):
    def __init__(self, min_market_cap: float = 1e9):  # 1 billion RMB
        self.min_market_cap = min_market_cap

    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        weights: pd.DataFrame = ctx.get("weights", pd.DataFrame())
        panel: pd.DataFrame = ctx.get("panel", pd.DataFrame())
        if weights.empty or panel.empty:
            return ctx
        # Merge weights with panel on code
        merged = weights.merge(panel, on="code", how="left")
        valid = merged[merged.market_cap.fillna(0) >= self.min_market_cap]
        ctx["weights"] = valid[weights.columns].reset_index(drop=True)
        ctx.setdefault("risk_logs", []).append({"rule": "market_cap", "removed": len(weights) - len(ctx["weights"])})
        return ctx


class LiquidityRule(RiskRule):
    def __init__(self, min_volume: float = 1e6):  # 1 million shares
        self.min_volume = min_volume

    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        weights: pd.DataFrame = ctx.get("weights", pd.DataFrame())
        panel: pd.DataFrame = ctx.get("panel", pd.DataFrame())
        if weights.empty or panel.empty:
            return ctx
        # Merge weights with panel
        merged = weights.merge(panel, on="code", how="left")
        valid = merged[merged.volume.fillna(0) >= self.min_volume]
        ctx["weights"] = valid[weights.columns].reset_index(drop=True)
        ctx.setdefault("risk_logs", []).append({"rule": "liquidity", "removed": len(weights) - len(ctx["weights"])})
        return ctx


class IndustryConcentrationRule(RiskRule):
    def __init__(self, max_industry_pct: float = 0.3):  # 30%
        self.max_industry_pct = max_industry_pct

    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        weights: pd.DataFrame = ctx.get("weights", pd.DataFrame())
        industry: pd.DataFrame = ctx.get("industry", pd.DataFrame())
        if weights.empty or industry.empty:
            return ctx
        # Merge weights with industry
        merged = weights.merge(industry, on="code", how="left")
        # Group by industry and sum weights
        industry_weights = merged.groupby("industry")["target_weight"].sum()
        # Find industries exceeding limit
        over_limit = industry_weights[industry_weights > self.max_industry_pct]
        if over_limit.empty:
            return ctx
        # Scale down weights in over-limit industries proportionally
        for ind in over_limit.index:
            factor = self.max_industry_pct / over_limit[ind]
            merged.loc[merged.industry == ind, "target_weight"] *= factor
        # Normalize all weights
        total_weight = merged["target_weight"].sum()
        if total_weight > 0:
            merged["target_weight"] /= total_weight
        ctx["weights"] = merged[weights.columns].reset_index(drop=True)
        ctx.setdefault("risk_logs", []).append({"rule": "industry_concentration", "adjusted": len(over_limit)})
        return ctx


class VaRRule(PortfolioReturnsMixin, RiskRule):
    """Value at Risk rule"""
    def __init__(self, max_var: float = 0.05, confidence: float = 0.95, horizon: int = 1):
        self.max_var = max_var
        self.confidence = confidence
        self.horizon = horizon

    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        weights = ctx.get("weights", pd.DataFrame())
        returns_data = ctx.get("returns_data", pd.DataFrame())

        if weights.empty or returns_data.empty:
            return ctx

        try:
            var = self._calculate_var(weights, returns_data)
            if var > self.max_var:
                # Scale down positions to meet VaR limit
                scale_factor = self.max_var / var
                weights = weights.copy()
                weights['target_weight'] *= scale_factor
                ctx["weights"] = weights
                ctx.setdefault("risk_logs", []).append({
                    "rule": "var",
                    "var": var,
                    "max_var": self.max_var,
                    "scaled": True
                })
        except Exception as e:
            logger.warning(f"VaR calculation failed: {e}")

        return ctx

    def _calculate_var(self, weights: pd.DataFrame, returns_data: pd.DataFrame) -> float:
        """Calculate portfolio VaR"""
        # Simple historical VaR calculation
        portfolio_returns = self._calculate_portfolio_returns(weights, returns_data)
        return abs(np.percentile(portfolio_returns, (1 - self.confidence) * 100))


class CVaRRule(PortfolioReturnsMixin, RiskRule):
    """Conditional Value at Risk (Expected Shortfall) rule"""
    def __init__(self, max_cvar: float = 0.07, confidence: float = 0.95):
        self.max_cvar = max_cvar
        self.confidence = confidence

    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        weights = ctx.get("weights", pd.DataFrame())
        returns_data = ctx.get("returns_data", pd.DataFrame())

        if weights.empty or returns_data.empty:
            return ctx

        try:
            cvar = self._calculate_cvar(weights, returns_data)
            if cvar > self.max_cvar:
                scale_factor = self.max_cvar / cvar
                weights = weights.copy()
                weights['target_weight'] *= scale_factor
                ctx["weights"] = weights
                ctx.setdefault("risk_logs", []).append({
                    "rule": "cvar",
                    "cvar": cvar,
                    "max_cvar": self.max_cvar,
                    "scaled": True
                })
        except Exception as e:
            logger.warning(f"CVaR calculation failed: {e}")

        return ctx

    def _calculate_cvar(self, weights: pd.DataFrame, returns_data: pd.DataFrame) -> float:
        """Calculate portfolio CVaR"""
        portfolio_returns = self._calculate_portfolio_returns(weights, returns_data)
        var_threshold = np.percentile(portfolio_returns, (1 - self.confidence) * 100)
        tail_losses = portfolio_returns[portfolio_returns <= var_threshold]
        return abs(np.mean(tail_losses)) if len(tail_losses) > 0 else 0


class VolatilityRule(PortfolioReturnsMixin, RiskRule):
    """Portfolio volatility control rule"""
    def __init__(self, max_volatility: float = 0.25):  # 25% annual volatility
        self.max_volatility = max_volatility

    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        weights = ctx.get("weights", pd.DataFrame())
        returns_data = ctx.get("returns_data", pd.DataFrame())

        if weights.empty or returns_data.empty:
            return ctx

        try:
            vol = self._calculate_portfolio_volatility(weights, returns_data)
            if vol > self.max_volatility:
                scale_factor = self.max_volatility / vol
                weights = weights.copy()
                weights['target_weight'] *= scale_factor
                ctx["weights"] = weights
                ctx.setdefault("risk_logs", []).append({
                    "rule": "volatility",
                    "volatility": vol,
                    "max_volatility": self.max_volatility,
                    "scaled": True
                })
        except Exception as e:
            logger.warning(f"Volatility calculation failed: {e}")

        return ctx

    def _calculate_portfolio_volatility(self, weights: pd.DataFrame, returns_data: pd.DataFrame) -> float:
        """Calculate annualized portfolio volatility"""
        portfolio_returns = self._calculate_portfolio_returns(weights, returns_data)
        return np.std(portfolio_returns) * np.sqrt(252)  # Annualize


class StressTestRule(RiskRule):
    """Stress testing rule"""
    def __init__(self, stress_scenarios: Dict[str, Dict[str, float]] = None):
        self.stress_scenarios = stress_scenarios or {
            'market_crash': {'equity': -0.20, 'bond': -0.05},
            'rate_hike': {'equity': -0.10, 'bond': -0.15},
            'sector_crisis': {'tech': -0.30, 'financial': -0.25}
        }

    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        weights = ctx.get("weights", pd.DataFrame())
        sector_data = ctx.get("sector_data", pd.DataFrame())

        if weights.empty:
            return ctx

        try:
            max_loss = self._run_stress_tests(weights, sector_data)
            ctx.setdefault("risk_logs", []).append({
                "rule": "stress_test",
                "max_stress_loss": max_loss,
                "scenarios_tested": len(self.stress_scenarios)
            })
        except Exception as e:
            logger.warning(f"Stress test failed: {e}")

        return ctx

    def _run_stress_tests(self, weights: pd.DataFrame, sector_data: pd.DataFrame) -> float:
        """Run stress tests and return maximum loss"""
        max_loss = 0

        for scenario_name, scenario_shocks in self.stress_scenarios.items():
            loss = self._calculate_scenario_loss(weights, sector_data, scenario_shocks)
            max_loss = max(max_loss, loss)

        return max_loss

    def _calculate_scenario_loss(self, weights: pd.DataFrame, sector_data: pd.DataFrame, shocks: Dict[str, float]) -> float:
        """Calculate portfolio loss under a stress scenario"""
        # Simplified implementation - in practice would use more sophisticated modeling
        total_loss = 0

        for _, row in weights.iterrows():
            code = str(row['code'])
            weight = row['target_weight']

            # Find sector for this security
            sector = 'equity'  # Default
            if not sector_data.empty and code in sector_data['code'].values:
                sector = sector_data[sector_data['code'] == code]['sector'].iloc[0]

            shock = shocks.get(sector, shocks.get('equity', 0))
            loss = weight * abs(shock)
            total_loss += loss

        return total_loss


class MaximumDrawdownRule(RiskRule):
    """Maximum drawdown control rule"""
    def __init__(self, max_drawdown: float = 0.20):  # 20% max drawdown
        self.max_drawdown = max_drawdown

    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        weights = ctx.get("weights", pd.DataFrame())
        historical_returns = ctx.get("historical_returns", pd.DataFrame())

        if weights.empty or historical_returns.empty:
            return ctx

        try:
            drawdown = self._calculate_max_drawdown(weights, historical_returns)
            if drawdown > self.max_drawdown:
                scale_factor = self.max_drawdown / drawdown
                weights = weights.copy()
                weights['target_weight'] *= scale_factor
                ctx["weights"] = weights
                ctx.setdefault("risk_logs", []).append({
                    "rule": "max_drawdown",
                    "drawdown": drawdown,
                    "max_drawdown": self.max_drawdown,
                    "scaled": True
                })
        except Exception as e:
            logger.warning(f"Max drawdown calculation failed: {e}")

        return ctx

    def _calculate_max_drawdown(self, weights: pd.DataFrame, historical_returns: pd.DataFrame) -> float:
        """Calculate maximum drawdown of the portfolio"""
        portfolio_returns = self._calculate_portfolio_returns(weights, historical_returns)
        cumulative = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return abs(np.min(drawdown))


class BetaRule(PortfolioReturnsMixin, RiskRule):
    """Portfolio beta control rule"""
    def __init__(self, max_beta: float = 1.5, benchmark: str = '000001'):  # HS300
        self.max_beta = max_beta
        self.benchmark = benchmark

    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        weights = ctx.get("weights", pd.DataFrame())
        returns_data = ctx.get("returns_data", pd.DataFrame())
        benchmark_returns = ctx.get("benchmark_returns", pd.Series())

        if weights.empty or returns_data.empty or benchmark_returns is None:
            return ctx

        try:
            beta = self._calculate_portfolio_beta(weights, returns_data, benchmark_returns)
            if beta > self.max_beta:
                scale_factor = self.max_beta / beta
                weights = weights.copy()
                weights['target_weight'] *= scale_factor
                ctx["weights"] = weights
                ctx.setdefault("risk_logs", []).append({
                    "rule": "beta",
                    "beta": beta,
                    "max_beta": self.max_beta,
                    "scaled": True
                })
        except Exception as e:
            logger.warning(f"Beta calculation failed: {e}")

        return ctx

    def _calculate_portfolio_beta(self, weights: pd.DataFrame, returns_data: pd.DataFrame, benchmark_returns: pd.Series) -> float:
        """Calculate portfolio beta relative to benchmark"""
        portfolio_returns = self._calculate_portfolio_returns(weights, returns_data)

        # Align the series
        common_index = portfolio_returns.index.intersection(benchmark_returns.index)
        if len(common_index) < 30:  # Need minimum data points
            return 1.0  # Default beta

        port_ret = portfolio_returns.loc[common_index]
        bench_ret = benchmark_returns.loc[common_index]

        covariance = np.cov(port_ret, bench_ret)[0, 1]
        variance = np.var(bench_ret)

        return covariance / variance if variance > 0 else 1.0


class SharpeRatioRule(PortfolioReturnsMixin, RiskRule):
    """Minimum Sharpe ratio rule"""
    def __init__(self, min_sharpe: float = 0.5, risk_free_rate: float = 0.03):
        self.min_sharpe = min_sharpe
        self.risk_free_rate = risk_free_rate

    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        weights = ctx.get("weights", pd.DataFrame())
        returns_data = ctx.get("returns_data", pd.DataFrame())

        if weights.empty or returns_data.empty:
            return ctx

        try:
            sharpe = self._calculate_sharpe_ratio(weights, returns_data)
            if sharpe < self.min_sharpe:
                # Could implement position adjustments here
                ctx.setdefault("risk_logs", []).append({
                    "rule": "sharpe_ratio",
                    "sharpe": sharpe,
                    "min_sharpe": self.min_sharpe,
                    "warning": True
                })
        except Exception as e:
            logger.warning(f"Sharpe ratio calculation failed: {e}")

        return ctx

    def _calculate_sharpe_ratio(self, weights: pd.DataFrame, returns_data: pd.DataFrame) -> float:
        """Calculate portfolio Sharpe ratio"""
        portfolio_returns = self._calculate_portfolio_returns(weights, returns_data)
        excess_returns = portfolio_returns - self.risk_free_rate/252  # Daily risk-free rate

        if len(excess_returns) < 30:
            return 0.0

        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)  # Annualize


class TrackingErrorRule(PortfolioReturnsMixin, RiskRule):
    """Tracking error control rule"""
    def __init__(self, max_tracking_error: float = 0.08, benchmark: str = '000001'):
        self.max_tracking_error = max_tracking_error
        self.benchmark = benchmark

    def apply(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        weights = ctx.get("weights", pd.DataFrame())
        returns_data = ctx.get("returns_data", pd.DataFrame())
        benchmark_returns = ctx.get("benchmark_returns", pd.Series())

        if weights.empty or returns_data.empty or benchmark_returns is None:
            return ctx

        try:
            tracking_error = self._calculate_tracking_error(weights, returns_data, benchmark_returns)
            if tracking_error > self.max_tracking_error:
                # Could implement rebalancing here
                ctx.setdefault("risk_logs", []).append({
                    "rule": "tracking_error",
                    "tracking_error": tracking_error,
                    "max_tracking_error": self.max_tracking_error,
                    "warning": True
                })
        except Exception as e:
            logger.warning(f"Tracking error calculation failed: {e}")

        return ctx

    def _calculate_tracking_error(self, weights: pd.DataFrame, returns_data: pd.DataFrame, benchmark_returns: pd.Series) -> float:
        """Calculate portfolio tracking error"""
        portfolio_returns = self._calculate_portfolio_returns(weights, returns_data)

        # Align the series
        common_index = portfolio_returns.index.intersection(benchmark_returns.index)
        if len(common_index) < 30:
            return 0.0

        port_ret = portfolio_returns.loc[common_index]
        bench_ret = benchmark_returns.loc[common_index]

        differences = port_ret - bench_ret
        return np.std(differences) * np.sqrt(252)  # Annualize


class CompositeRiskEngine:
    def __init__(self, rules: List[RiskRule]):
        self.rules = rules

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        for r in self.rules:
            ctx = r.apply(ctx)
        return ctx

    def calculate_risk_metrics(self, weights: pd.DataFrame, returns_data: pd.DataFrame = None,
                             benchmark_returns: pd.Series = None, historical_returns: pd.DataFrame = None) -> Dict[str, float]:
        """Calculate comprehensive risk metrics for the portfolio"""
        metrics = {}

        if returns_data is not None and not weights.empty:
            # VaR
            try:
                portfolio_returns = self._calculate_portfolio_returns(weights, returns_data)
                metrics['var_95'] = abs(np.percentile(portfolio_returns, 5))
                metrics['var_99'] = abs(np.percentile(portfolio_returns, 1))
            except Exception:
                metrics['var_95'] = 0.0
                metrics['var_99'] = 0.0

            # Volatility
            try:
                metrics['volatility'] = np.std(portfolio_returns) * np.sqrt(252)
            except Exception:
                metrics['volatility'] = 0.0

            # Sharpe ratio (assuming 3% risk-free rate)
            try:
                risk_free_daily = 0.03 / 252
                excess_returns = portfolio_returns - risk_free_daily
                metrics['sharpe_ratio'] = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
            except Exception:
                metrics['sharpe_ratio'] = 0.0

        # Maximum drawdown
        if historical_returns is not None and not weights.empty:
            try:
                portfolio_returns = self._calculate_portfolio_returns(weights, historical_returns)
                cumulative = np.cumprod(1 + portfolio_returns)
                running_max = np.maximum.accumulate(cumulative)
                drawdown = (cumulative - running_max) / running_max
                metrics['max_drawdown'] = abs(np.min(drawdown))
            except Exception:
                metrics['max_drawdown'] = 0.0

        # Beta
        if returns_data is not None and benchmark_returns is not None and not weights.empty:
            try:
                portfolio_returns = self._calculate_portfolio_returns(weights, returns_data)
                common_index = portfolio_returns.index.intersection(benchmark_returns.index)
                if len(common_index) >= 30:
                    port_ret = portfolio_returns.loc[common_index]
                    bench_ret = benchmark_returns.loc[common_index]
                    covariance = np.cov(port_ret, bench_ret)[0, 1]
                    variance = np.var(bench_ret)
                    metrics['beta'] = covariance / variance if variance > 0 else 1.0
                else:
                    metrics['beta'] = 1.0
            except Exception:
                metrics['beta'] = 1.0

        return metrics

    def _calculate_portfolio_returns(self, weights: pd.DataFrame, returns_data: pd.DataFrame) -> pd.Series:
        """Calculate portfolio returns from weights and returns data"""
        weighted_returns = pd.DataFrame()

        for _, row in weights.iterrows():
            code = str(row['code'])
            weight = row['target_weight']
            if code in returns_data.columns:
                weighted_returns[code] = returns_data[code] * weight

        return weighted_returns.sum(axis=1)
