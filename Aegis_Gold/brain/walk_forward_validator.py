import math
import numpy as np
import random
from typing import List, Tuple, Dict

class PurgedWalkForwardCV:
    """
    Purged and Embargoed Time Series Cross-Validation (de Prado, 2018).
    Prevents information leakage between adjacent training and validation splits
    due to overlapping labels or features.
    """
    def __init__(self, n_splits: int = 5, embargo_pct: float = 0.05):
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct

    def split(self, X: np.ndarray, y: np.ndarray, times: List[float]) -> List[Tuple[np.ndarray, np.ndarray]]:
        n_samples = len(X)
        indices = np.arange(n_samples)
        splits = []
        
        # Simple walk forward boundaries
        step = n_samples // (self.n_splits + 1)
        embargo = int(n_samples * self.embargo_pct)

        for i in range(1, self.n_splits + 1):
            train_end = i * step
            # Purge/Embargo step: skip embargo period immediately following training
            test_start = train_end + embargo
            test_end = min(test_start + step, n_samples)
            
            if test_start < n_samples:
                train_idx = indices[:train_end]
                test_idx = indices[test_start:test_end]
                splits.append((train_idx, test_idx))
                
        return splits


def probabilistic_sharpe_ratio(returns: List[float], benchmark_sharpe: float = 0.0) -> float:
    """
    Computes the Probabilistic Sharpe Ratio (PSR) of Bailey and Lopez de Prado (2012).
    Corrects for non-normality, skewness, and kurtosis of returns.
    """
    n = len(returns)
    if n < 5:
        return 0.0
    
    ret_arr = np.array(returns)
    mean_ret = np.mean(ret_arr)
    std_ret = np.std(ret_arr, ddof=1)
    
    if std_ret == 0:
        return 0.0
        
    sr = mean_ret / std_ret
    
    # Compute skewness & kurtosis
    skew = np.mean((ret_arr - mean_ret)**3) / (std_ret**3)
    kurt = np.mean((ret_arr - mean_ret)**4) / (std_ret**4)
    
    # Standard deviation of Sharpe Ratio under non-normality
    sr_variance = (1.0 + (0.5 * sr**2) - (skew * sr) + ((kurt - 3.0)/4.0 * sr**2)) / (n - 1.0)
    sr_std = math.sqrt(max(1e-8, sr_variance))
    
    # Calculate Z score vs benchmark
    z_score = (sr - benchmark_sharpe) / sr_std
    
    # Approximation of normal CDF
    psr = 0.5 * (1.0 + math.erf(z_score / math.sqrt(2.0)))
    return psr


def bootstrap_trade_sequence(trades_pnl: List[float], n_iterations: int = 1000) -> Dict[str, Tuple[float, float]]:
    """
    Monte Carlo bootstrap resampling of trade sequences to construct
    confidence intervals for performance metrics.
    """
    if not trades_pnl:
        return {}
        
    sampled_sharpes = []
    sampled_winrates = []
    
    n = len(trades_pnl)
    
    for _ in range(n_iterations):
        sample = [random.choice(trades_pnl) for _ in range(n)]
        
        # Metrics
        wins = sum(1 for p in sample if p > 0)
        winrate = wins / n
        
        mean_p = np.mean(sample)
        std_p = np.std(sample, ddof=1)
        sr = mean_p / std_p if std_p > 0 else 0.0
        
        sampled_sharpes.append(sr)
        sampled_winrates.append(winrate)
        
    # Get 95% Confidence Intervals
    sampled_sharpes.sort()
    sampled_winrates.sort()
    
    return {
        "sharpe_ci_95": (sampled_sharpes[int(n_iterations * 0.025)], sampled_sharpes[int(n_iterations * 0.975)]),
        "winrate_ci_95": (sampled_winrates[int(n_iterations * 0.025)] * 100.0, sampled_winrates[int(n_iterations * 0.975)] * 100.0)
    }


# ---------------------------------------------------------------------------
# Module 5: Additional metric helpers for backtest_runner.py
# ---------------------------------------------------------------------------

def compute_max_drawdown(cumulative_pnl: List[float]) -> float:
    """
    Compute the maximum drawdown from a cumulative P&L series.

    Parameters
    ----------
    cumulative_pnl : List of cumulative USD P&L values (e.g. [0, 5, 12, 8, 15]).

    Returns
    -------
    float — maximum drawdown as a negative USD value (e.g. -4.0).
            Returns 0.0 if the series is empty or monotonically increasing.
    """
    if not cumulative_pnl or len(cumulative_pnl) < 2:
        return 0.0

    peak       = cumulative_pnl[0]
    max_dd     = 0.0

    for val in cumulative_pnl:
        if val > peak:
            peak = val
        dd = val - peak
        if dd < max_dd:
            max_dd = dd

    return round(max_dd, 4)


def compute_sortino(returns: List[float], risk_free: float = 0.0) -> float:
    """
    Compute the Sortino ratio: mean excess return / downside deviation.

    Parameters
    ----------
    returns    : Per-trade P&L values (USD).
    risk_free  : Risk-free rate per trade (default 0.0).

    Returns
    -------
    float — Sortino ratio. 0.0 if insufficient data or no downside.
    """
    if not returns or len(returns) < 5:
        return 0.0

    arr        = np.array(returns)
    excess     = arr - risk_free
    mean_exc   = np.mean(excess)

    downside   = excess[excess < 0]
    if len(downside) == 0:
        return float("inf")

    downside_std = np.std(downside, ddof=1)
    if downside_std == 0:
        return 0.0

    return round(mean_exc / downside_std, 4)


def compute_calmar(total_pnl: float, max_drawdown: float, n_years: float = 1.0) -> float:
    """
    Compute the Calmar ratio: annualised return / absolute max drawdown.

    Parameters
    ----------
    total_pnl    : Total USD P&L over the period.
    max_drawdown : Max drawdown as a negative USD value (from compute_max_drawdown).
    n_years      : Duration in years (used to annualise; default 1.0).

    Returns
    -------
    float — Calmar ratio. 0.0 if drawdown is zero or positive.
    """
    if max_drawdown >= 0:
        return 0.0
    annual_return = total_pnl / max(n_years, 1.0)
    return round(annual_return / abs(max_drawdown), 4)
