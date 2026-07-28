"""
===========================================================================
🛡️ KRONOS ALPHA ENGINE — RISK SUPERVISOR (risk_manager.py)
===========================================================================
Fractional Kelly sizing, hard non-overridable ATR-scaled SL/TP floors,
and Hurst/Entropy market regime filtering guardrails.
"""

import math
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from kronos_engine.kronos_brain import KronosSignalVector
from kronos_engine.data_pipeline import MarketWindow

logger = logging.getLogger("kronos.risk")


@dataclass
class RiskApproval:
    """Dataclass holding Risk Supervisor trade approval decision."""
    approved: bool
    lot_size: float
    sl_points: int
    tp_points: int
    regime: str                       # "TRENDING", "MEAN_REVERTING", "VOLATILE_NOISE"
    hurst_exponent: float
    entropy: float
    kelly_fraction: float
    rejection_reason: str = ""


class RiskSupervisor:
    """
    Institutional Risk Supervisor enforcing non-overridable execution guardrails,
    Fractional Kelly sizing, and market regime entropy filtering.
    """

    def __init__(
        self,
        fractional_kelly: float = 0.25,      # Quarter-Kelly for institutional safety
        max_risk_per_trade_pct: float = 0.02, # 2% max portfolio risk
        max_lot_cap: float = 2.0,
        min_lot_floor: float = 0.01
    ):
        self.fractional_kelly = fractional_kelly
        self.max_risk_pct = max_risk_per_trade_pct
        self.max_lot = max_lot_cap
        self.min_lot = min_lot_floor

    def calculate_hurst_exponent(self, prices: np.ndarray) -> float:
        """
        Calculates Hurst Exponent (H) via Rescaled Range (R/S) analysis.
        H < 0.45: Mean-Reverting | 0.45 <= H <= 0.55: Random Walk | H > 0.55: Trending
        """
        if len(prices) < 20:
            return 0.50

        log_returns = np.log(prices[1:] / prices[:-1])
        lags = range(2, min(20, len(log_returns) // 2))
        tau = []
        
        for lag in lags:
            # Calculate standard deviation of differences at lag
            diff = log_returns[lag:] - log_returns[:-lag]
            std = np.std(diff)
            if std > 1e-8:
                tau.append(std)
            else:
                tau.append(1e-8)

        if len(tau) < 2:
            return 0.50

        # Fit line log(tau) vs log(lag)
        poly = np.polyfit(np.log(lags[:len(tau)]), np.log(tau), 1)
        hurst = float(poly[0])
        return max(0.0, min(1.0, hurst))

    def classify_regime(self, window: MarketWindow, signal: KronosSignalVector) -> Tuple[str, float, float]:
        """
        Classifies market state into TRENDING, MEAN_REVERTING, or VOLATILE_NOISE.
        """
        hurst = self.calculate_hurst_exponent(window.closes)
        entropy = signal.forecast_entropy

        if entropy > 0.85 or (0.43 <= hurst <= 0.52 and abs(signal.p50_volatility_bound) < 10):
            regime = "VOLATILE_NOISE"
        elif hurst > 0.55:
            regime = "TRENDING"
        else:
            regime = "MEAN_REVERTING"

        return regime, round(hurst, 4), round(entropy, 4)

    def calculate_fractional_kelly_lot(
        self,
        equity: float,
        win_prob: float,
        reward_risk_ratio: float,
        sl_points: int,
        point: float = 0.01,
        symbol: str = "XAUUSD"
    ) -> float:
        """
        Calculates position size using Fractional Kelly Criterion scaled by volatility.
        """
        if equity <= 0 or win_prob <= 0.50 or reward_risk_ratio <= 0 or sl_points <= 0:
            return self.min_lot

        b = reward_risk_ratio
        p = win_prob
        q = 1.0 - p

        # Full Kelly formula: f* = (b*p - q) / b
        f_star = (b * p - q) / b
        if f_star <= 0:
            return self.min_lot

        # Scaled by fractional Kelly multiplier (e.g. 0.25)
        k_fraction = f_star * self.fractional_kelly

        # Convert risk percentage to lot size
        is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()
        dollar_risk_target = equity * min(k_fraction, self.max_risk_pct)
        
        # Dollar risk per 0.01 lot for sl_points
        tick_value_per_001 = (sl_points * point) * (100.0 if is_gold else 1000.0)
        if tick_value_per_001 <= 0:
            return self.min_lot

        calculated_lot = round((dollar_risk_target / tick_value_per_001) * 0.01, 2)
        return max(self.min_lot, min(self.max_lot, calculated_lot))

    def evaluate_risk(
        self,
        window: MarketWindow,
        signal: KronosSignalVector,
        account_equity: float = 10000.0,
        current_open_positions: int = 0,
        max_allowed_positions: int = 3
    ) -> RiskApproval:
        """
        Executes end-to-end Risk Verification pass:
        1. Checks Regime Noise Filter (suspends execution if VOLATILE_NOISE).
        2. Enforces Deterministic Hard ATR-Scaled SL/TP Floor (Gold: 150pts / $1.50).
        3. Calculates Fractional Kelly Lot Sizing.
        """
        symbol = window.symbol
        is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()

        # -------------------------------------------------------------------
        # HARD SL/TP FLOOR ENFORCEMENT (Deterministic & Non-Overridable)
        # -------------------------------------------------------------------
        min_sl_floor = 150 if is_gold else 40
        min_tp_floor = 300 if is_gold else 80

        # Calculate ATR-scaled SL/TP points
        recent_atr_pts = float(np.mean(window.hl_ranges[-14:])) if len(window.hl_ranges) >= 14 else min_sl_floor
        scaled_sl = int(max(min_sl_floor, round(recent_atr_pts * 1.5)))
        scaled_tp = int(max(min_tp_floor, round(scaled_sl * 2.0)))

        # -------------------------------------------------------------------
        # REGIME FILTER
        # -------------------------------------------------------------------
        regime, hurst, entropy = self.classify_regime(window, signal)

        if regime == "VOLATILE_NOISE":
            reason = f"SUSPENDED: Market regime classified as VOLATILE_NOISE (Entropy={entropy:.2f}, Hurst={hurst:.2f})"
            logger.warning(f"[RISK REJECTED] {reason}")
            return RiskApproval(
                approved=False,
                lot_size=0.0,
                sl_points=scaled_sl,
                tp_points=scaled_tp,
                regime=regime,
                hurst_exponent=hurst,
                entropy=entropy,
                kelly_fraction=0.0,
                rejection_reason=reason
            )

        if signal.direction == "HOLD":
            return RiskApproval(
                approved=False,
                lot_size=0.0,
                sl_points=scaled_sl,
                tp_points=scaled_tp,
                regime=regime,
                hurst_exponent=hurst,
                entropy=entropy,
                kelly_fraction=0.0,
                rejection_reason="Signal direction is HOLD"
            )

        if current_open_positions >= max_allowed_positions:
            return RiskApproval(
                approved=False,
                lot_size=0.0,
                sl_points=scaled_sl,
                tp_points=scaled_tp,
                regime=regime,
                hurst_exponent=hurst,
                entropy=entropy,
                kelly_fraction=0.0,
                rejection_reason=f"Open positions limit reached ({current_open_positions}/{max_allowed_positions})"
            )

        # -------------------------------------------------------------------
        # DYNAMIC FRACTIONAL KELLY SIZING
        # -------------------------------------------------------------------
        rr_ratio = scaled_tp / scaled_sl
        lot = self.calculate_fractional_kelly_lot(
            equity=account_equity,
            win_prob=signal.confidence,
            reward_risk_ratio=rr_ratio,
            sl_points=scaled_sl,
            point=window.point,
            symbol=symbol
        )

        logger.info(
            f"[RISK APPROVED] {signal.direction} {symbol} | Lot: {lot} | "
            f"SL: {scaled_sl}pts TP: {scaled_tp}pts | Regime: {regime} (H={hurst:.2f})"
        )

        return RiskApproval(
            approved=True,
            lot_size=lot,
            sl_points=scaled_sl,
            tp_points=scaled_tp,
            regime=regime,
            hurst_exponent=hurst,
            entropy=entropy,
            kelly_fraction=self.fractional_kelly,
            rejection_reason="APPROVED_BY_RISK_SUPERVISOR"
        )
