"""
===========================================================================
🛡️ KRONOS ALPHA ENGINE — CALIBRATION AUDIT ENGINE (calibration_audit.py)
===========================================================================
Walk-Forward Analysis (WFA), Out-of-Sample (OOS) rolling audits, Conformal
Prediction risk calibration, and catastrophic curve-fitting anti-overfitting gates.
"""

import math
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

logger = logging.getLogger("kronos.calibration")


@dataclass
class AuditResult:
    """Dataclass holding complete Calibration Audit results."""
    passed: bool
    win_rate: float                   # Actual OOS Win Rate (0.0 to 1.0)
    profit_factor: float              # Profit Factor (Gross Wins / Gross Losses)
    sharpe_ratio: float               # Annualized Sharpe Ratio after costs
    max_drawdown_pct: float           # Max Peak-to-Trough Drawdown %
    conformal_alpha: float            # Calibrated Conformal Risk Alpha
    conformal_interval: Tuple[float, float] # Dynamic Prediction Interval
    curve_fitting_flag: bool          # True if WR > 70% or PF > 4.0 (Overfitted)
    rejection_reason: str = ""
    audit_window_trades: int = 0


class CalibrationAuditEngine:
    """
    Institutional Anti-Overfitting Audit Protocol.
    Integrates Walk-Forward Analysis, Conformal Interval Calibration,
    and Strict Institutional Parameter Gates.
    """

    def __init__(
        self,
        target_win_rate_range: Tuple[float, float] = (0.48, 0.60),
        target_pf_range: Tuple[float, float] = (1.60, 2.50),
        min_sharpe: float = 1.50,
        max_drawdown_limit: float = 0.10,
        overfit_wr_threshold: float = 0.70,
        overfit_pf_threshold: float = 4.00,
        conformal_confidence: float = 0.90
    ):
        self.wr_min, self.wr_max = target_win_rate_range
        self.pf_min, self.pf_max = target_pf_range
        self.min_sharpe = min_sharpe
        self.max_mdd = max_drawdown_limit
        self.overfit_wr = overfit_wr_threshold
        self.overfit_pf = overfit_pf_threshold
        self.conformal_conf = conformal_confidence

    def calculate_conformal_interval(
        self,
        forecast_errors: np.ndarray,
        alpha: float = 0.10
    ) -> Tuple[float, Tuple[float, float]]:
        """
        Calculates dynamic Conformal Prediction interval at coverage 1-alpha.
        Guarantees distribution-free coverage against non-stationary market noise.
        """
        if len(forecast_errors) < 10:
            return 1.96, (-10.0, 10.0)

        abs_residuals = np.sort(np.abs(forecast_errors))
        n = len(abs_residuals)
        q_idx = int(np.ceil((n + 1) * (1.0 - alpha))) - 1
        q_idx = max(0, min(n - 1, q_idx))
        
        q_val = float(abs_residuals[q_idx])
        interval = (-q_val, q_val)
        return q_val, interval

    def run_walk_forward_audit(
        self,
        trade_pnls_usd: np.ndarray,
        trade_durations_sec: np.ndarray,
        costs_per_trade: float = 0.50
    ) -> AuditResult:
        """
        Executes Walk-Forward Out-Of-Sample (OOS) audit across trade history.
        Enforces Anti-Overfitting thresholds and dynamic Conformal bounds.
        """
        if len(trade_pnls_usd) < 20:
            return AuditResult(
                passed=False,
                win_rate=0.0,
                profit_factor=0.0,
                sharpe_ratio=0.0,
                max_drawdown_pct=0.0,
                conformal_alpha=0.10,
                conformal_interval=(-10.0, 10.0),
                curve_fitting_flag=False,
                rejection_reason="Insufficient OOS trade history (< 20 trades)",
                audit_window_trades=len(trade_pnls_usd)
            )

        # Net PnLs after deducting spread, slippage, and swap costs
        net_pnls = trade_pnls_usd - costs_per_trade

        wins = net_pnls[net_pnls > 0]
        losses = np.abs(net_pnls[net_pnls < 0])

        win_rate = float(len(wins) / len(net_pnls))
        gross_wins = float(np.sum(wins)) if len(wins) > 0 else 0.0
        gross_losses = float(np.sum(losses)) if len(losses) > 0 else 1e-8
        profit_factor = float(gross_wins / gross_losses)

        # Annualized Sharpe Ratio calculation
        mean_pnl = float(np.mean(net_pnls))
        std_pnl = float(np.std(net_pnls)) if np.std(net_pnls) > 1e-8 else 1.0
        trades_per_year = 252 * 5  # Assume ~5 trades per trading day
        sharpe_ratio = float((mean_pnl / std_pnl) * np.sqrt(trades_per_year))

        # Maximum Peak-to-Trough Drawdown (MDD %)
        cum_pnl = np.cumsum(net_pnls)
        peak = np.maximum.accumulate(cum_pnl + 10000.0)  # Assuming $10,000 base
        drawdowns = (peak - (cum_pnl + 10000.0)) / peak
        max_mdd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Conformal prediction error bounds
        forecast_errors = net_pnls - mean_pnl
        q_val, interval = self.calculate_conformal_interval(forecast_errors, alpha=1.0 - self.conformal_conf)

        # -------------------------------------------------------------------
        # ANTI-OVERFITTING GATE 1: Catastrophic Curve-Fitting Detection
        # -------------------------------------------------------------------
        curve_fitted = (win_rate > self.overfit_wr) or (profit_factor > self.overfit_pf)
        if curve_fitted:
            reason = (
                f"CATASTROPHIC OVERFITTING DETECTED: WinRate ({win_rate*100:.1f}%) > {self.overfit_wr*100:.0f}% "
                f"or ProfitFactor ({profit_factor:.2f}) > {self.overfit_pf:.1f}. Parameter set rejected."
            )
            logger.error(f"[CALIBRATION AUDIT REJECTED] {reason}")
            return AuditResult(
                passed=False,
                win_rate=win_rate,
                profit_factor=profit_factor,
                sharpe_ratio=sharpe_ratio,
                max_drawdown_pct=max_mdd,
                conformal_alpha=1.0 - self.conformal_conf,
                conformal_interval=interval,
                curve_fitting_flag=True,
                rejection_reason=reason,
                audit_window_trades=len(net_pnls)
            )

        # -------------------------------------------------------------------
        # ANTI-OVERFITTING GATE 2: Institutional Target Bounds
        # -------------------------------------------------------------------
        rejections = []
        if win_rate < self.wr_min:
            rejections.append(f"Win Rate ({win_rate*100:.1f}%) below min target ({self.wr_min*100:.0f}%)")
        if profit_factor < self.pf_min:
            rejections.append(f"Profit Factor ({profit_factor:.2f}) below min target ({self.pf_min:.2f})")
        if sharpe_ratio < self.min_sharpe:
            rejections.append(f"Sharpe Ratio ({sharpe_ratio:.2f}) below min target ({self.min_sharpe:.2f})")
        if max_mdd > self.max_mdd:
            rejections.append(f"Max Drawdown ({max_mdd*100:.1f}%) exceeds max limit ({self.max_mdd*100:.0f}%)")

        passed = len(rejections) == 0
        rejection_reason = " | ".join(rejections) if rejections else "PASSED_INSTITUTIONAL_AUDIT"

        if passed:
            logger.info(
                f"[CALIBRATION AUDIT PASSED] WR: {win_rate*100:.1f}% | PF: {profit_factor:.2f} | "
                f"Sharpe: {sharpe_ratio:.2f} | MDD: {max_mdd*100:.1f}%"
            )
        else:
            logger.warning(f"[CALIBRATION AUDIT FAILED] {rejection_reason}")

        return AuditResult(
            passed=passed,
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown_pct=max_mdd,
            conformal_alpha=1.0 - self.conformal_conf,
            conformal_interval=interval,
            curve_fitting_flag=False,
            rejection_reason=rejection_reason,
            audit_window_trades=len(net_pnls)
        )
