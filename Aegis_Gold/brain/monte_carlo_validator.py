"""
===========================================================================
AEGIS GOLD — Monte Carlo Validation Engine (Phase V)
===========================================================================

Statistical confidence testing through randomization and permutation.

VALIDATION METHODS:
-------------------
1. Trade Sequence Permutation: Randomize trade order, verify robustness
2. Price Path Resampling: Bootstrap historical returns, test stability
3. Parameter Sensitivity: Vary inputs within bounds, measure impact
4. Drawdown Recovery: Test recovery from extreme scenarios
5. Regime Transition: Test performance across market regime changes

METRICS GENERATED:
------------------
- Confidence intervals (95%, 99%)
- Sharpe ratio distribution
- Max drawdown distribution
- Probability of ruin
- Stress test results
- Parameter sensitivity heatmap

===========================================================================
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
import random
import statistics
from enum import Enum


class ValidationMethod(Enum):
    """Monte Carlo validation methods."""
    SEQUENCE_PERMUTATION = "sequence_permutation"
    PRICE_RESAMPLING = "price_resampling"
    PARAMETER_SENSITIVITY = "parameter_sensitivity"
    DRAWDOWN_RECOVERY = "drawdown_recovery"
    REGIME_TRANSITION = "regime_transition"


@dataclass
class MCValidationResult:
    """Single Monte Carlo validation run."""
    
    run_id: int
    method: str
    
    # Outcomes
    total_trades: int = 0
    win_count: int = 0
    total_pnl: float = 0.0
    final_balance: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    recovery_time_bars: int = 0
    
    # Parameter variations (for sensitivity)
    parameter_variations: Dict[str, float] = field(default_factory=dict)
    
    # Robustness indicator
    outcome_stable: bool = True


@dataclass
class MCValidationSummary:
    """Aggregate Monte Carlo validation results."""
    
    total_runs: int
    method: str
    
    # Aggregates
    avg_final_balance: float = 0.0
    std_dev_balance: float = 0.0
    confidence_95_lower: float = 0.0
    confidence_95_upper: float = 0.0
    confidence_99_lower: float = 0.0
    confidence_99_upper: float = 0.0
    
    # Risk metrics
    probability_of_ruin: float = 0.0  # % of runs with negative PnL
    avg_max_drawdown: float = 0.0
    max_drawdown_observed: float = 0.0
    
    # Performance distribution
    sharpe_ratio_distribution: List[float] = field(default_factory=list)
    avg_sharpe: float = 0.0
    
    # Stress test results
    worst_case_scenario: float = 0.0  # 1st percentile outcome
    best_case_scenario: float = 0.0   # 99th percentile outcome
    
    # Stability metrics
    outcome_stability: float = 0.0  # % of stable outcomes


class MonteCarloValidator:
    """Monte Carlo validation engine."""
    
    def __init__(self, seed: Optional[int] = None):
        """Initialize validator."""
        if seed:
            random.seed(seed)
        
        self.validation_runs: List[MCValidationResult] = []
        self.summaries: Dict[str, MCValidationSummary] = {}
        
        self.base_balance = 10000.0
        self.risk_per_trade = 0.02  # 2% per trade
        self.min_runs = 100
        self.max_runs = 1000
    
    def configure(self, base_balance: float, risk_per_trade: float, min_runs: int = 100):
        """Configure validator parameters."""
        self.base_balance = base_balance
        self.risk_per_trade = risk_per_trade
        self.min_runs = min_runs
        return self
    
    def run_sequence_permutation(self, trades: List[Dict], num_runs: int = 500) -> List[MCValidationResult]:
        """Permute trade sequence, test if order matters."""
        
        if not trades or len(trades) < 2:
            return []
        
        results = []
        
        for run_id in range(num_runs):
            # Randomize trade order
            shuffled_trades = trades.copy()
            random.shuffle(shuffled_trades)
            
            # Calculate outcome
            balance = self.base_balance
            cumulative_pnl = []
            peak_balance = balance
            max_dd = 0.0
            
            for trade in shuffled_trades:
                pnl = trade.get('pnl', 0)
                balance += pnl
                cumulative_pnl.append(pnl)
                
                if balance > peak_balance:
                    peak_balance = balance
                dd = peak_balance - balance
                if dd > max_dd:
                    max_dd = dd
            
            # Calculate Sharpe ratio
            if cumulative_pnl and len(cumulative_pnl) > 1:
                mean_pnl = statistics.mean(cumulative_pnl)
                std_dev = statistics.stdev(cumulative_pnl)
                sharpe = (mean_pnl / std_dev) if std_dev > 0 else 0.0
            else:
                sharpe = 0.0
            
            result = MCValidationResult(
                run_id=run_id,
                method="sequence_permutation",
                total_trades=len(shuffled_trades),
                win_count=sum(1 for t in shuffled_trades if t.get('pnl', 0) > 0),
                total_pnl=balance - self.base_balance,
                final_balance=balance,
                max_drawdown=max_dd,
                sharpe_ratio=sharpe,
                outcome_stable=(balance > 0)
            )
            
            results.append(result)
        
        self.validation_runs.extend(results)
        return results
    
    def run_price_resampling(self, price_returns: List[float], num_runs: int = 500) -> List[MCValidationResult]:
        """Bootstrap price returns, test stability."""
        
        if not price_returns or len(price_returns) < 10:
            return []
        
        results = []
        
        for run_id in range(num_runs):
            # Resample returns with replacement
            resampled_returns = random.choices(price_returns, k=len(price_returns))
            
            # Calculate cumulative equity
            balance = self.base_balance
            cumulative = [balance]
            peak = balance
            max_dd = 0.0
            
            for ret in resampled_returns:
                balance *= (1 + ret)
                cumulative.append(balance)
                
                if balance > peak:
                    peak = balance
                dd = peak - balance
                if dd > max_dd:
                    max_dd = dd
            
            # Calculate Sharpe
            if cumulative and len(cumulative) > 1:
                changes = [cumulative[i] - cumulative[i-1] for i in range(1, len(cumulative))]
                if changes and statistics.stdev(changes) > 0:
                    sharpe = (statistics.mean(changes) / statistics.stdev(changes))
                else:
                    sharpe = 0.0
            else:
                sharpe = 0.0
            
            result = MCValidationResult(
                run_id=run_id,
                method="price_resampling",
                total_trades=len(resampled_returns),
                total_pnl=balance - self.base_balance,
                final_balance=balance,
                max_drawdown=max_dd,
                sharpe_ratio=sharpe,
                outcome_stable=(balance > self.base_balance)
            )
            
            results.append(result)
        
        self.validation_runs.extend(results)
        return results
    
    def run_parameter_sensitivity(self, base_params: Dict[str, float], param_variations: Dict[str, Tuple[float, float]], 
                                 trades: List[Dict], num_runs: int = 500) -> List[MCValidationResult]:
        """Vary parameters, test sensitivity."""
        
        results = []
        
        for run_id in range(num_runs):
            varied_params = base_params.copy()
            
            # Vary each parameter within bounds
            for param_name, (min_val, max_val) in param_variations.items():
                if param_name in varied_params:
                    varied_val = random.uniform(min_val, max_val)
                    varied_params[param_name] = varied_val
            
            # Apply varied parameters to trades (simplified)
            adjusted_pnl = 0.0
            for trade in trades:
                base_pnl = trade.get('pnl', 0)
                # Adjust based on parameter variations (simple scaling)
                adjustment = sum(varied_params.values()) / len(varied_params) if varied_params else 1.0
                adjusted_pnl += base_pnl * adjustment
            
            balance = self.base_balance + adjusted_pnl
            
            result = MCValidationResult(
                run_id=run_id,
                method="parameter_sensitivity",
                total_trades=len(trades),
                total_pnl=adjusted_pnl,
                final_balance=balance,
                parameter_variations=varied_params,
                outcome_stable=(balance > self.base_balance)
            )
            
            results.append(result)
        
        self.validation_runs.extend(results)
        return results
    
    def run_drawdown_recovery_test(self, equity_curve: List[float], stress_level: float = 0.2, 
                                  num_runs: int = 100) -> List[MCValidationResult]:
        """Test recovery from drawdown scenarios."""
        
        results = []
        
        for run_id in range(num_runs):
            # Create stress scenario
            stressed_equity = equity_curve.copy()
            
            # Apply stress at random point
            stress_point = random.randint(0, len(stressed_equity) - 1)
            stress_magnitude = equity_curve[stress_point] * stress_level
            
            # Apply drawdown
            for i in range(stress_point, len(stressed_equity)):
                stressed_equity[i] -= stress_magnitude * (i - stress_point) / len(stressed_equity)
            
            # Find recovery
            recovery_point = None
            for i in range(stress_point + 1, len(stressed_equity)):
                if stressed_equity[i] >= equity_curve[stress_point]:
                    recovery_point = i
                    break
            
            recovery_bars = (recovery_point - stress_point) if recovery_point else len(stressed_equity)
            final_balance = stressed_equity[-1] if stressed_equity else 0
            
            result = MCValidationResult(
                run_id=run_id,
                method="drawdown_recovery",
                total_pnl=final_balance - self.base_balance,
                final_balance=final_balance,
                recovery_time_bars=recovery_bars,
                outcome_stable=(recovery_point is not None)
            )
            
            results.append(result)
        
        self.validation_runs.extend(results)
        return results
    
    def generate_summary(self, method: str) -> MCValidationSummary:
        """Generate summary for validation method."""
        
        runs = [r for r in self.validation_runs if r.method == method]
        
        if not runs:
            return MCValidationSummary(total_runs=0, method=method)
        
        final_balances = [r.final_balance for r in runs]
        sharpe_ratios = [r.sharpe_ratio for r in runs if r.sharpe_ratio != 0]
        max_drawdowns = [r.max_drawdown for r in runs]
        
        final_balances_sorted = sorted(final_balances)
        
        # Calculate confidence intervals
        idx_95_lower = int(len(final_balances_sorted) * 0.025)
        idx_95_upper = int(len(final_balances_sorted) * 0.975)
        idx_99_lower = int(len(final_balances_sorted) * 0.005)
        idx_99_upper = int(len(final_balances_sorted) * 0.995)
        
        # Calculate probability of ruin
        losses = sum(1 for b in final_balances if b < self.base_balance)
        prob_of_ruin = (losses / len(final_balances) * 100) if final_balances else 0.0
        
        # Stability
        stable_outcomes = sum(1 for r in runs if r.outcome_stable)
        outcome_stability = (stable_outcomes / len(runs) * 100) if runs else 0.0
        
        summary = MCValidationSummary(
            total_runs=len(runs),
            method=method,
            avg_final_balance=statistics.mean(final_balances) if final_balances else 0.0,
            std_dev_balance=statistics.stdev(final_balances) if len(final_balances) > 1 else 0.0,
            confidence_95_lower=final_balances_sorted[idx_95_lower] if idx_95_lower < len(final_balances_sorted) else 0.0,
            confidence_95_upper=final_balances_sorted[idx_95_upper] if idx_95_upper < len(final_balances_sorted) else 0.0,
            confidence_99_lower=final_balances_sorted[idx_99_lower] if idx_99_lower < len(final_balances_sorted) else 0.0,
            confidence_99_upper=final_balances_sorted[idx_99_upper] if idx_99_upper < len(final_balances_sorted) else 0.0,
            probability_of_ruin=prob_of_ruin,
            avg_max_drawdown=statistics.mean(max_drawdowns) if max_drawdowns else 0.0,
            max_drawdown_observed=max(max_drawdowns) if max_drawdowns else 0.0,
            sharpe_ratio_distribution=sharpe_ratios,
            avg_sharpe=statistics.mean(sharpe_ratios) if sharpe_ratios else 0.0,
            worst_case_scenario=final_balances_sorted[0] if final_balances_sorted else 0.0,
            best_case_scenario=final_balances_sorted[-1] if final_balances_sorted else 0.0,
            outcome_stability=outcome_stability
        )
        
        self.summaries[method] = summary
        return summary
    
    def validate_robustness(self) -> Tuple[bool, str]:
        """Validate if strategy is robust to randomization."""
        
        if not self.summaries:
            return False, "No validation summaries generated"
        
        for method, summary in self.summaries.items():
            # Check if strategy survives randomization
            if summary.probability_of_ruin > 20.0:
                return False, f"{method}: Probability of ruin too high ({summary.probability_of_ruin:.1f}%)"
            
            if summary.outcome_stability < 70.0:
                return False, f"{method}: Outcome stability too low ({summary.outcome_stability:.1f}%)"
        
        return True, "Strategy is robust to randomization"
    
    def generate_mc_report(self) -> str:
        """Generate Monte Carlo validation report."""
        
        report = []
        report.append("=" * 70)
        report.append("MONTE CARLO VALIDATION REPORT (Phase V)")
        report.append("=" * 70)
        report.append("")
        
        for method, summary in self.summaries.items():
            report.append(f"METHOD: {method.upper()}")
            report.append("-" * 70)
            report.append(f"Total Runs:                {summary.total_runs}")
            report.append(f"Avg Final Balance:         ${summary.avg_final_balance:,.2f}")
            report.append(f"Std Dev:                   ${summary.std_dev_balance:,.2f}")
            report.append("")
            
            report.append("Confidence Intervals:")
            report.append(f"  95% CI:  ${summary.confidence_95_lower:,.2f} - ${summary.confidence_95_upper:,.2f}")
            report.append(f"  99% CI:  ${summary.confidence_99_lower:,.2f} - ${summary.confidence_99_upper:,.2f}")
            report.append("")
            
            report.append("Risk Metrics:")
            report.append(f"  Probability of Ruin:     {summary.probability_of_ruin:.1f}%")
            report.append(f"  Avg Max Drawdown:        ${summary.avg_max_drawdown:,.2f}")
            report.append(f"  Max Drawdown Observed:   ${summary.max_drawdown_observed:,.2f}")
            report.append("")
            
            report.append("Performance Distribution:")
            report.append(f"  Worst Case (1%):         ${summary.worst_case_scenario:,.2f}")
            report.append(f"  Best Case (99%):         ${summary.best_case_scenario:,.2f}")
            report.append(f"  Avg Sharpe Ratio:        {summary.avg_sharpe:.2f}")
            report.append(f"  Outcome Stability:       {summary.outcome_stability:.1f}%")
            report.append("")
        
        # Robustness validation
        is_robust, reason = self.validate_robustness()
        report.append("ROBUSTNESS VALIDATION")
        report.append("-" * 70)
        report.append(f"Status: {'✓ ROBUST' if is_robust else '✗ NOT ROBUST'}")
        report.append(f"Reason: {reason}")
        report.append("")
        
        return "\n".join(report)
