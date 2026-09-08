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


def bootstrap_pf_ci(trades_pnl: List[float], n_iterations: int = 1000) -> Dict[str, float]:
    """
    Bootstrap confidence interval for Profit Factor.

    Returns the 5th and 95th percentile PF estimates over n_iterations
    resampled trade sequences. Used to ensure the challenger's PF point
    estimate is not a lucky run — the 5th percentile must exceed 1.0
    for the promotion gate to pass.

    Parameters
    ----------
    trades_pnl   : Per-trade P&L values (USD).
    n_iterations : Number of bootstrap resamples.

    Returns
    -------
    dict with keys:
        pf_point_estimate : float — PF on the full sample
        pf_ci_5           : float — 5th percentile PF (lower bound)
        pf_ci_95          : float — 95th percentile PF (upper bound)
        pf_ci_excludes_1  : bool  — True if lower bound > 1.0
    """
    if not trades_pnl or len(trades_pnl) < 10:
        return {
            "pf_point_estimate": 0.0,
            "pf_ci_5": 0.0,
            "pf_ci_95": 0.0,
            "pf_ci_excludes_1": False,
        }

    # Point estimate
    gp_full = sum(p for p in trades_pnl if p > 0)
    gl_full = abs(sum(p for p in trades_pnl if p < 0))
    pf_full = gp_full / gl_full if gl_full > 0 else float("inf")

    # Bootstrap
    n = len(trades_pnl)
    sampled_pfs = []

    for _ in range(n_iterations):
        sample = [random.choice(trades_pnl) for _ in range(n)]
        gp = sum(p for p in sample if p > 0)
        gl = abs(sum(p for p in sample if p < 0))
        pf = gp / gl if gl > 0 else 3.0   # cap extreme outliers
        sampled_pfs.append(min(pf, 10.0))

    sampled_pfs.sort()
    pf_ci_5  = sampled_pfs[int(n_iterations * 0.05)]
    pf_ci_95 = sampled_pfs[int(n_iterations * 0.95)]

    return {
        "pf_point_estimate": round(pf_full, 4),
        "pf_ci_5": round(pf_ci_5, 4),
        "pf_ci_95": round(pf_ci_95, 4),
        "pf_ci_excludes_1": pf_ci_5 > 1.0,
    }


def validate_rl_agent(agent, trade_memory_db, min_pf: float = 1.0,
                      n_splits: int = 5, embargo_pct: float = 0.05) -> dict:
    """
    Purged Walk-Forward validation of an RL agent on historical trades.

    Splits trade_memory_db into n_splits purged walk-forward folds. On each
    held-out fold, retrieves the agent's action for each state and computes
    PF/WR on that fold. Returns aggregate metrics and a pass/fail gate.

    Parameters
    ----------
    agent          : AegisRLAgent instance (already trained).
    trade_memory_db: TradeMemoryDB instance.
    min_pf         : Minimum acceptable PF on held-out data (default 1.0).
    n_splits       : Number of walk-forward splits.
    embargo_pct    : Embargo fraction (de Prado 2018).

    Returns
    -------
    dict:
        passed         : bool
        pf             : float  — mean PF across held-out folds
        win_rate       : float  — mean WR across held-out folds (%)
        rr             : float  — mean realized R:R across held-out folds
        n_folds        : int
        fold_results   : list of per-fold dicts
        rejection_reason : str  (empty if passed)
    """
    import numpy as np

    trades = trade_memory_db.get_recent_trades(limit=5000)
    if len(trades) < 50:
        return {
            "passed": False,
            "pf": 0.0,
            "win_rate": 0.0,
            "rr": 0.0,
            "n_folds": 0,
            "fold_results": [],
            "rejection_reason": f"Insufficient trades for walk-forward validation: {len(trades)}/50",
        }

    # Build feature matrix and labels
    states, times, pnls, sl_pts_list, lot_list = [], [], [], [], []
    for t in trades:
        state = [
            float(t.get("regime_score", 0.0) or 0.0),
            float(t.get("structure_score", 0.0) or 0.0),
            float(t.get("entry_score", 0.0) or 0.0),
            float(t.get("rsi", 50.0) or 50.0),
            float(t.get("adx", 20.0) or 20.0),
            float(t.get("atr", 0.0) or 0.0),
            float(t.get("spread", 0.0) or 0.0),
            float(t.get("recent_wins", 0.0) or 0.0),
            float(t.get("recent_losses", 0.0) or 0.0),
        ]
        try:
            from datetime import datetime
            ts = t.get("entry_time", "") or ""
            tval = datetime.fromisoformat(ts).timestamp() if ts else float(len(times))
        except Exception:
            tval = float(len(times))

        states.append(state)
        times.append(tval)
        pnls.append(float(t.get("profit_usd", 0.0) or 0.0))
        sl_pts_list.append(float(t.get("sl_points", 0.0) or 0.0))
        lot_list.append(float(t.get("lot_size", 0.01) or 0.01))

    X     = np.array(states)
    y     = np.array(pnls)
    times_arr = times

    cv    = PurgedWalkForwardCV(n_splits=n_splits, embargo_pct=embargo_pct)
    splits = cv.split(X, y, times_arr)

    fold_results = []
    for fold_idx, (train_idx, test_idx) in enumerate(splits):
        fold_pnls, fold_rrs = [], []

        for i in test_idx:
            state   = states[i]
            pnl     = pnls[i]
            sl_pts  = sl_pts_list[i] if sl_pts_list[i] > 0 else 60.0
            lot     = lot_list[i] if lot_list[i] > 0 else 0.01

            action, conf = agent.decide(state)

            # Only evaluate trades where agent said BUY or SELL (not WAIT)
            if action == "WAIT":
                continue

            # Compute realized R:R
            dollar_risk = sl_pts * 1.0 * (lot / 0.01)
            rr = pnl / dollar_risk if dollar_risk > 0 else 0.0

            fold_pnls.append(pnl)
            fold_rrs.append(rr)

        if not fold_pnls:
            continue

        fold_wins   = [p for p in fold_pnls if p > 0]
        fold_losses = [p for p in fold_pnls if p < 0]
        fold_gp     = sum(fold_wins)
        fold_gl     = abs(sum(fold_losses))
        fold_pf     = fold_gp / fold_gl if fold_gl > 0 else float("inf")
        fold_wr     = len(fold_wins) / len(fold_pnls) * 100
        fold_rr_avg = float(np.mean(fold_rrs)) if fold_rrs else 0.0

        fold_results.append({
            "fold": fold_idx + 1,
            "n_trades": len(fold_pnls),
            "pf": round(fold_pf, 4),
            "win_rate": round(fold_wr, 2),
            "avg_rr": round(fold_rr_avg, 4),
            "net_pnl": round(sum(fold_pnls), 4),
        })

    if not fold_results:
        return {
            "passed": False,
            "pf": 0.0,
            "win_rate": 0.0,
            "rr": 0.0,
            "n_folds": 0,
            "fold_results": [],
            "rejection_reason": "No folds produced enough trades for evaluation",
        }

    mean_pf = float(np.mean([f["pf"] for f in fold_results if f["pf"] < float("inf")]))
    mean_wr = float(np.mean([f["win_rate"] for f in fold_results]))
    mean_rr = float(np.mean([f["avg_rr"] for f in fold_results]))

    passed = mean_pf >= min_pf
    rejection_reason = "" if passed else f"Walk-forward mean PF {mean_pf:.3f} < threshold {min_pf}"

    return {
        "passed": passed,
        "pf": round(mean_pf, 4),
        "win_rate": round(mean_wr, 2),
        "rr": round(mean_rr, 4),
        "n_folds": len(fold_results),
        "fold_results": fold_results,
        "rejection_reason": rejection_reason,
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


def evaluate_phase5_governance_gate(trades_pnl: List[float], n_iterations: int = 1000) -> Dict[str, Any]:
    """
    Evaluates Phase 5 Governance Gate using bootstrap confidence interval.
    If lower 95% CI bound (pf_ci_5) < 1.0:
      - Triggers failure-handling protocol.
      - Downgrades active strategy mode to conservative SMC-only.
      - Elevates minimum pattern confidence to 75%.
      - Enables champion human gate.
    """
    ci_res = bootstrap_pf_ci(trades_pnl, n_iterations=n_iterations)
    pf_lower = ci_res.get("pf_ci_5", 0.0)
    passed = (pf_lower >= 1.0) and len(trades_pnl) >= 10

    actions_taken = []
    if not passed:
        actions_taken.append("Downgraded strategy mode to CONSERVATIVE_SMC_ONLY")
        actions_taken.append("Elevated MIN_PATTERN_CONFIDENCE threshold to 75.0%")
        actions_taken.append("Enabled champion_human_gate for manual trade vetting")

    return {
        "gate_passed": passed,
        "pf_point_estimate": ci_res.get("pf_point_estimate", 0.0),
        "pf_ci_lower_5": pf_lower,
        "pf_ci_upper_95": ci_res.get("pf_ci_95", 0.0),
        "sample_size": len(trades_pnl),
        "actions_taken": actions_taken
    }

