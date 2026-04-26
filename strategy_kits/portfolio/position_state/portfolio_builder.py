"""portfolio_builder: advanced portfolio construction with comprehensive constraints
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
import logging
from enum import Enum


logger = logging.getLogger(__name__)


class OptimizationObjective(Enum):
    MAXIMUM_SHARPE = "max_sharpe"
    MINIMUM_VARIANCE = "min_variance"
    MAXIMUM_DIVERSIFICATION = "max_diversification"
    RISK_PARITY = "risk_parity"
    EQUAL_WEIGHT = "equal_weight"


@dataclass
class PortfolioSpec:
    # Concentration limits
    max_single: float = 0.08  # Max single stock weight
    max_industry: float = 0.25  # Max industry weight
    hhi_ceiling: float = 0.10  # Herfindahl-Hirschman Index ceiling

    # Risk constraints
    max_volatility: float = 0.25  # Max portfolio volatility
    max_var: float = 0.05  # Max Value at Risk
    max_drawdown: float = 0.20  # Max drawdown
    min_sharpe: float = 0.5  # Minimum Sharpe ratio

    # Factor constraints
    max_factor_exposure: Dict[str, float] = None  # Factor exposure limits
    sector_neutral: bool = False  # Sector neutral constraint

    # Trading constraints
    max_turnover: float = 0.50  # Max portfolio turnover
    min_position_size: float = 0.001  # Min position size
    max_positions: int = 50  # Max number of positions

    # Liquidity constraints
    min_liquidity_score: float = 0.3  # Min liquidity score
    max_illiquidity_pct: float = 0.20  # Max illiquid assets percentage

    # Transaction costs
    transaction_cost_bps: float = 5.0  # Transaction cost in basis points

    # Tax optimization
    tax_aware: bool = False  # Enable tax-aware optimization
    tax_rate: float = 0.20  # Capital gains tax rate

    # Rebalancing
    rebalance_threshold: float = 0.02  # Rebalance when deviation > 2%
    adaptive_rebalancing: bool = False  # Adaptive rebalancing based on market conditions

    # Multi-period optimization
    multi_period_horizon: int = 1  # Optimization horizon in periods
    risk_aversion: float = 2.0  # Risk aversion parameter

    # Optimization settings
    objective: OptimizationObjective = OptimizationObjective.EQUAL_WEIGHT
    solver_tolerance: float = 1e-6
    max_iterations: int = 1000


class PortfolioBuilder:
    def __init__(self, spec: PortfolioSpec | None = None):
        self.spec = spec or PortfolioSpec()
        self.max_factor_exposure = self.spec.max_factor_exposure or {
            'value': 0.3,
            'growth': 0.3,
            'size': 0.2,
            'momentum': 0.2,
            'quality': 0.2,
            'volatility': 0.15
        }

    def build(self, picks: pd.DataFrame, cash_target: float = 0.1,
              current_portfolio: Optional[pd.DataFrame] = None,
              market_data: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """Advanced portfolio construction with comprehensive constraints

        Args:
            picks: DataFrame with columns [code, score] and optional additional data
            cash_target: Target cash position (0.0 to 1.0)
            current_portfolio: Current portfolio DataFrame [code, weight]
            market_data: Additional market data for constraints

        Returns:
            DataFrame [code, target_weight] with optimized weights
        """
        if picks.empty:
            return pd.DataFrame(columns=["code", "target_weight"])

        # Start with basic ranking and equal weighting
        portfolio = self._initial_allocation(picks, cash_target)

        # Apply comprehensive constraints
        portfolio = self._apply_concentration_constraints(portfolio, market_data)
        portfolio = self._apply_risk_constraints(portfolio, market_data)
        portfolio = self._apply_factor_constraints(portfolio, market_data)
        portfolio = self._apply_trading_constraints(portfolio, current_portfolio)
        portfolio = self._apply_liquidity_constraints(portfolio, market_data)
        portfolio = self._apply_transaction_cost_optimization(portfolio, current_portfolio)
        portfolio = self._apply_tax_optimization(portfolio, current_portfolio, market_data)

        # Final normalization and validation
        portfolio = self._normalize_and_validate(portfolio, cash_target)

        return portfolio

    def _initial_allocation(self, picks: pd.DataFrame, cash_target: float) -> pd.DataFrame:
        """Create initial portfolio allocation based on optimization objective"""
        df = picks.copy()
        df = df.sort_values("score", ascending=False)

        # Limit number of positions
        if len(df) > self.spec.max_positions:
            df = df.head(self.spec.max_positions)

        # Apply objective-based weighting
        if self.spec.objective == OptimizationObjective.EQUAL_WEIGHT:
            alloc = (1.0 - cash_target) / len(df)
            df["target_weight"] = alloc
        elif self.spec.objective == OptimizationObjective.MAXIMUM_SHARPE:
            # Simplified Sharpe optimization (would use proper optimizer in production)
            df["target_weight"] = self._optimize_for_sharpe(df, cash_target)
        elif self.spec.objective == OptimizationObjective.MINIMUM_VARIANCE:
            df["target_weight"] = self._optimize_for_minimum_variance(df, cash_target)
        else:
            # Default to equal weight
            alloc = (1.0 - cash_target) / len(df)
            df["target_weight"] = alloc

        return df[["code", "target_weight"]]

    def _apply_concentration_constraints(self, portfolio: pd.DataFrame,
                                       market_data: Optional[Dict[str, Any]]) -> pd.DataFrame:
        """Apply concentration constraints (single stock, industry, HHI)"""
        df = portfolio.copy()

        # Single stock constraint
        if self.spec.max_single > 0:
            df['target_weight'] = df['target_weight'].clip(upper=self.spec.max_single)

        # Industry concentration constraint
        if market_data and 'industry_data' in market_data:
            df = self._apply_industry_constraints(df, market_data['industry_data'])

        # HHI constraint
        if self.spec.hhi_ceiling > 0:
            df = self._apply_hhi_constraint(df)

        # Renormalize after constraints
        total_weight = df['target_weight'].sum()
        if total_weight > 0:
            df['target_weight'] = df['target_weight'] / total_weight * (1.0 - 0.1)  # Leave room for cash

        return df

    def _apply_industry_constraints(self, portfolio: pd.DataFrame,
                                  industry_data: pd.DataFrame) -> pd.DataFrame:
        """Apply industry concentration constraints"""
        df = portfolio.copy()

        # Merge with industry data
        merged = df.merge(industry_data, on='code', how='left')

        # Group by industry and adjust weights
        industry_weights = merged.groupby('industry')['target_weight'].sum()

        # Scale down industries exceeding limit
        for industry, weight in industry_weights.items():
            if weight > self.spec.max_industry:
                scale_factor = self.spec.max_industry / weight
                merged.loc[merged['industry'] == industry, 'target_weight'] *= scale_factor

        return merged[['code', 'target_weight']]

    def _apply_hhi_constraint(self, portfolio: pd.DataFrame) -> pd.DataFrame:
        """Apply Herfindahl-Hirschman Index constraint"""
        df = portfolio.copy()

        # Calculate current HHI
        hhi = (df['target_weight'] ** 2).sum()

        if hhi > self.spec.hhi_ceiling:
            # Scale down largest positions
            scale_factor = np.sqrt(self.spec.hhi_ceiling / hhi)
            df['target_weight'] *= scale_factor

        return df

    def _apply_risk_constraints(self, portfolio: pd.DataFrame,
                              market_data: Optional[Dict[str, Any]]) -> pd.DataFrame:
        """Apply risk-based constraints"""
        df = portfolio.copy()

        if not market_data:
            return df

        # Volatility constraint
        if 'returns_data' in market_data and self.spec.max_volatility > 0:
            df = self._apply_volatility_constraint(df, market_data['returns_data'])

        # VaR constraint
        if 'returns_data' in market_data and self.spec.max_var > 0:
            df = self._apply_var_constraint(df, market_data['returns_data'])

        # Maximum drawdown constraint
        if 'historical_returns' in market_data and self.spec.max_drawdown > 0:
            df = self._apply_drawdown_constraint(df, market_data['historical_returns'])

        return df

    def _apply_volatility_constraint(self, portfolio: pd.DataFrame,
                                   returns_data: pd.DataFrame) -> pd.DataFrame:
        """Apply portfolio volatility constraint"""
        df = portfolio.copy()

        try:
            # Calculate portfolio volatility
            portfolio_vol = self._calculate_portfolio_volatility(df, returns_data)

            if portfolio_vol > self.spec.max_volatility:
                scale_factor = self.spec.max_volatility / portfolio_vol
                df['target_weight'] *= scale_factor

        except Exception as e:
            logger.warning(f"Volatility constraint calculation failed: {e}")

        return df

    def _apply_var_constraint(self, portfolio: pd.DataFrame,
                            returns_data: pd.DataFrame) -> pd.DataFrame:
        """Apply Value at Risk constraint"""
        df = portfolio.copy()

        try:
            # Calculate portfolio VaR
            portfolio_var = self._calculate_portfolio_var(df, returns_data)

            if portfolio_var > self.spec.max_var:
                scale_factor = self.spec.max_var / portfolio_var
                df['target_weight'] *= scale_factor

        except Exception as e:
            logger.warning(f"VaR constraint calculation failed: {e}")

        return df

    def _apply_drawdown_constraint(self, portfolio: pd.DataFrame,
                                 historical_returns: pd.DataFrame) -> pd.DataFrame:
        """Apply maximum drawdown constraint"""
        df = portfolio.copy()

        try:
            # Calculate maximum drawdown
            max_dd = self._calculate_max_drawdown(df, historical_returns)

            if max_dd > self.spec.max_drawdown:
                scale_factor = self.spec.max_drawdown / max_dd
                df['target_weight'] *= scale_factor

        except Exception as e:
            logger.warning(f"Drawdown constraint calculation failed: {e}")

        return df

    def _apply_factor_constraints(self, portfolio: pd.DataFrame,
                                market_data: Optional[Dict[str, Any]]) -> pd.DataFrame:
        """Apply factor exposure constraints"""
        df = portfolio.copy()

        if not market_data or 'factor_data' not in market_data:
            return df

        factor_data = market_data['factor_data']

        # Check each factor constraint
        for factor, max_exposure in self.max_factor_exposure.items():
            if factor in factor_data.columns:
                exposure = self._calculate_factor_exposure(df, factor_data, factor)
                if abs(exposure) > max_exposure:
                    # Adjust weights to reduce exposure (simplified)
                    scale_factor = max_exposure / abs(exposure)
                    df['target_weight'] *= scale_factor

        # Sector neutrality
        if self.spec.sector_neutral and 'sector_data' in market_data:
            df = self._apply_sector_neutrality(df, market_data['sector_data'])

        return df

    def _apply_sector_neutrality(self, portfolio: pd.DataFrame,
                               sector_data: pd.DataFrame) -> pd.DataFrame:
        """Apply sector neutrality constraint"""
        df = portfolio.copy()

        # Merge with sector data
        merged = df.merge(sector_data, on='code', how='left')

        # Calculate sector exposures
        sector_weights = merged.groupby('sector')['target_weight'].sum()
        market_sector_weights = merged.groupby('sector')['market_weight'].sum()

        # Adjust for neutrality (simplified implementation)
        for sector in sector_weights.index:
            current_exposure = sector_weights[sector]
            market_exposure = market_sector_weights.get(sector, 0)

            if market_exposure > 0:
                neutral_exposure = market_exposure
                adjustment = (neutral_exposure - current_exposure) * 0.1  # Partial adjustment

                sector_codes = merged[merged['sector'] == sector]['code']
                if len(sector_codes) > 0:
                    adjustment_per_stock = adjustment / len(sector_codes)
                    for code in sector_codes:
                        df.loc[df['code'] == code, 'target_weight'] += adjustment_per_stock

        return df

    def _apply_trading_constraints(self, portfolio: pd.DataFrame,
                                 current_portfolio: Optional[pd.DataFrame]) -> pd.DataFrame:
        """Apply trading and rebalancing constraints"""
        df = portfolio.copy()

        if current_portfolio is None:
            return df

        # Calculate turnover
        merged = df.merge(current_portfolio, on='code', how='outer', suffixes=('_new', '_current'))
        merged['current_weight'] = merged['current_weight'].fillna(0)
        merged['target_weight'] = merged['target_weight'].fillna(0)
        merged['trade_size'] = abs(merged['target_weight'] - merged['current_weight'])

        total_turnover = merged['trade_size'].sum()

        # Apply turnover constraint
        if total_turnover > self.spec.max_turnover:
            scale_factor = self.spec.max_turnover / total_turnover
            df['target_weight'] = merged['current_weight'] + \
                                (merged['target_weight'] - merged['current_weight']) * scale_factor

        # Apply rebalancing threshold
        if self.spec.rebalance_threshold > 0:
            df = self._apply_rebalancing_threshold(df, current_portfolio)

        # Apply minimum position size
        df = df[df['target_weight'] >= self.spec.min_position_size]

        return df

    def _apply_rebalancing_threshold(self, portfolio: pd.DataFrame,
                                   current_portfolio: pd.DataFrame) -> pd.DataFrame:
        """Apply rebalancing threshold - only trade if deviation exceeds threshold"""
        df = portfolio.copy()

        merged = df.merge(current_portfolio, on='code', how='left', suffixes=('_new', '_current'))
        merged['current_weight'] = merged['current_weight'].fillna(0)

        # Only change positions where deviation exceeds threshold
        deviation = abs(merged['target_weight_new'] - merged['current_weight'])
        needs_rebalance = deviation > self.spec.rebalance_threshold

        # Keep current weights for positions below threshold
        df.loc[~needs_rebalance[df.index], 'target_weight'] = \
            merged.loc[~needs_rebalance[df.index], 'current_weight']

        return df

    def _apply_liquidity_constraints(self, portfolio: pd.DataFrame,
                                   market_data: Optional[Dict[str, Any]]) -> pd.DataFrame:
        """Apply liquidity-based constraints"""
        df = portfolio.copy()

        if not market_data or 'liquidity_data' not in market_data:
            return df

        liquidity_data = market_data['liquidity_data']

        # Merge with liquidity data
        merged = df.merge(liquidity_data, on='code', how='left')

        # Filter by minimum liquidity score
        if self.spec.min_liquidity_score > 0:
            merged = merged[merged['liquidity_score'].fillna(0) >= self.spec.min_liquidity_score]

        # Limit illiquid assets
        if self.spec.max_illiquidity_pct > 0:
            illiquid_mask = merged['liquidity_score'].fillna(1) < 0.5  # Define illiquid
            illiquid_weight = merged.loc[illiquid_mask, 'target_weight'].sum()

            if illiquid_weight > self.spec.max_illiquidity_pct:
                # Scale down illiquid positions
                scale_factor = self.spec.max_illiquidity_pct / illiquid_weight
                merged.loc[illiquid_mask, 'target_weight'] *= scale_factor

        return merged[['code', 'target_weight']]

    def _apply_transaction_cost_optimization(self, portfolio: pd.DataFrame,
                                           current_portfolio: Optional[pd.DataFrame]) -> pd.DataFrame:
        """Optimize for transaction costs"""
        df = portfolio.copy()

        if current_portfolio is None:
            return df

        # Calculate transaction costs
        merged = df.merge(current_portfolio, on='code', how='outer', suffixes=('_new', '_current'))
        merged['current_weight'] = merged['current_weight'].fillna(0)
        merged['trade_size'] = abs(merged['target_weight_new'] - merged['current_weight'])

        # Apply transaction cost penalty (simplified)
        cost_penalty = merged['trade_size'] * self.spec.transaction_cost_bps / 10000
        df['target_weight'] = merged['target_weight_new'] * (1 - cost_penalty)

        return df

    def _apply_tax_optimization(self, portfolio: pd.DataFrame,
                              current_portfolio: Optional[pd.DataFrame],
                              market_data: Optional[Dict[str, Any]]) -> pd.DataFrame:
        """Apply tax-aware optimization"""
        df = portfolio.copy()

        if not self.spec.tax_aware or current_portfolio is None:
            return df

        # Simplified tax-aware optimization
        # In practice, this would consider capital gains, loss harvesting, etc.
        merged = df.merge(current_portfolio, on='code', how='outer', suffixes=('_new', '_current'))
        merged['current_weight'] = merged['current_weight'].fillna(0)

        # Prefer positions with losses (simplified)
        if market_data and 'unrealized_gains' in market_data:
            gains_data = market_data['unrealized_gains']
            merged = merged.merge(gains_data, on='code', how='left')
            merged['unrealized_gain'] = merged['unrealized_gain'].fillna(0)

            # Reduce positions with large gains, increase positions with losses
            tax_factor = np.where(merged['unrealized_gain'] > 0, 0.9, 1.1)
            df['target_weight'] = merged['target_weight_new'] * tax_factor

        return df

    def _normalize_and_validate(self, portfolio: pd.DataFrame, cash_target: float) -> pd.DataFrame:
        """Final normalization and validation"""
        df = portfolio.copy()

        # Remove positions below minimum size
        df = df[df['target_weight'] >= self.spec.min_position_size]

        # Renormalize weights
        total_weight = df['target_weight'].sum()
        if total_weight > 0:
            df['target_weight'] = df['target_weight'] / total_weight * (1.0 - cash_target)

        # Round to reasonable precision
        df['target_weight'] = df['target_weight'].round(6)

        # Validate constraints
        self._validate_constraints(df)

        return df

    def _validate_constraints(self, portfolio: pd.DataFrame):
        """Validate that all constraints are satisfied"""
        # Check single stock limit
        if self.spec.max_single > 0:
            max_weight = portfolio['target_weight'].max()
            if max_weight > self.spec.max_single:
                logger.warning(f"Single stock constraint violated: {max_weight} > {self.spec.max_single}")

        # Check total weight
        total_weight = portfolio['target_weight'].sum()
        if abs(total_weight - (1.0 - 0.1)) > 0.01:  # Allow small tolerance
            logger.warning(f"Total weight constraint violated: {total_weight}")

    # Helper methods for calculations
    def _calculate_portfolio_volatility(self, portfolio: pd.DataFrame,
                                      returns_data: pd.DataFrame) -> float:
        """Calculate annualized portfolio volatility"""
        portfolio_returns = self._calculate_portfolio_returns(portfolio, returns_data)
        return np.std(portfolio_returns) * np.sqrt(252)

    def _calculate_portfolio_var(self, portfolio: pd.DataFrame,
                               returns_data: pd.DataFrame) -> float:
        """Calculate portfolio Value at Risk"""
        portfolio_returns = self._calculate_portfolio_returns(portfolio, returns_data)
        return abs(np.percentile(portfolio_returns, 5))  # 95% VaR

    def _calculate_max_drawdown(self, portfolio: pd.DataFrame,
                              historical_returns: pd.DataFrame) -> float:
        """Calculate maximum drawdown"""
        portfolio_returns = self._calculate_portfolio_returns(portfolio, historical_returns)
        cumulative = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return abs(np.min(drawdown))

    def _calculate_factor_exposure(self, portfolio: pd.DataFrame,
                                 factor_data: pd.DataFrame, factor: str) -> float:
        """Calculate portfolio exposure to a factor"""
        merged = portfolio.merge(factor_data, on='code', how='left')
        return (merged['target_weight'] * merged[factor].fillna(0)).sum()

    def _calculate_portfolio_returns(self, portfolio: pd.DataFrame,
                                   returns_data: pd.DataFrame) -> np.ndarray:
        """Calculate portfolio returns"""
        weighted_returns = pd.DataFrame()

        for _, row in portfolio.iterrows():
            code = str(row['code'])
            weight = row['target_weight']
            if code in returns_data.columns:
                weighted_returns[code] = returns_data[code] * weight

        return weighted_returns.sum(axis=1).values

    def _optimize_for_sharpe(self, picks: pd.DataFrame, cash_target: float) -> pd.Series:
        """Optimize portfolio for maximum Sharpe ratio (simplified)"""
        # Simplified implementation - in practice would use proper optimization
        n = len(picks)
        base_weight = (1.0 - cash_target) / n

        # Adjust weights based on score (proxy for expected return)
        scores = picks['score'].values
        score_weights = scores / scores.sum()
        weights = base_weight + (score_weights - 1/n) * 0.1  # Small adjustment

        return pd.Series(weights, index=picks.index)

    def _optimize_for_minimum_variance(self, picks: pd.DataFrame, cash_target: float) -> pd.Series:
        """Optimize portfolio for minimum variance (simplified)"""
        # Simplified implementation
        n = len(picks)
        return pd.Series([1.0 - cash_target] / n, index=picks.index)

    def get_portfolio_metrics(self, portfolio: pd.DataFrame,
                            market_data: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """Calculate portfolio metrics"""
        metrics = {
            'num_positions': len(portfolio),
            'total_weight': portfolio['target_weight'].sum(),
            'max_weight': portfolio['target_weight'].max(),
            'concentration_ratio': portfolio['target_weight'].max() / portfolio['target_weight'].sum(),
            'effective_bets': 1 / (portfolio['target_weight'] ** 2).sum()  # Inverse Herfindahl
        }

        if market_data and 'returns_data' in market_data:
            metrics['expected_volatility'] = self._calculate_portfolio_volatility(
                portfolio, market_data['returns_data']
            )

        return metrics
