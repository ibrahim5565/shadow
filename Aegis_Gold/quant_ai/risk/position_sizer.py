"""AEGIS QUANT AI — position sizing (Section 14).

Supported: fixed fractional risk, ATR-based sizing, volatility targeting,
full Kelly, fractional Kelly and drawdown-adjusted sizing.
Raw model confidence NEVER directly determines lot size.
"""
from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("quant_ai.risk.sizer")

METHODS = ("fixed_fractional", "atr", "vol_target", "kelly", "fractional_kelly", "drawdown_adjusted")


def _equity_lot(equity: float, risk_usd: float, sl_points: int,
                point_value_per_lot: float, min_lot: float = 0.01) -> float:
    if sl_points <= 0 or risk_usd <= 0:
        return 0.0
    # point_value_per_lot = account currency per lot per 1 point move
    # (1.0 for standard EURUSD and XAUUSD contracts)
    loss_per_lot = sl_points * point_value_per_lot
    if loss_per_lot <= 0:
        return 0.0
    lot = risk_usd / loss_per_lot
    return max(min_lot, round(lot / 0.01) * 0.01)


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float,
                   fraction: float = 1.0, prior_weight: int = 100,
                   prior_win: float = 0.5) -> float:
    """Kelly(b* = win/loss ratio) = p - q/b; returns a bounded fraction."""
    n_examples = prior_weight
    p = (win_rate * n_examples + prior_win * prior_weight) / (n_examples + prior_weight)
    b = (avg_win / (avg_loss + 1e-12)) if avg_loss > 0 else 1.0
    kelly = p - (1 - p) / (b + 1e-12)
    return max(0.0, min(1.0, kelly * fraction))


class PositionSizer:
    """Pure functions + a small stateful wrapper for Kelly inputs."""

    def __init__(self, method: str = "fixed_fractional"):
        if method not in METHODS:
            raise ValueError(f"unknown sizing method {method!r}")
        self.method = method

    def size(self, *, equity: float, risk_per_trade: float, sl_points: int,
             point_value_per_lot: float = 1.0, atr_points: float = 0.0,
             vol_ratio: float = 1.0, drawdown_pct: float = 0.0,
             kelly: Optional[Tuple[float, float, float]] = None,
             kelly_frac: float = 1.0, min_lot: float = 0.01) -> float:
        """Return lot size in broker units (rounded to 0.01).

        point_value_per_lot: account currency per lot per 1 point move.
        """
        equity = max(equity, 1.0)
        risk_usd = equity * risk_per_trade

        # Kelly inputs = (win_rate, avg_win_pct, avg_loss_pct)
        if kelly is not None and self.method in ("kelly", "fractional_kelly"):
            win_rate, avg_win, avg_loss = kelly
            frac = kelly_frac if self.method == "fractional_kelly" else 1.0
            f = kelly_fraction(win_rate, avg_win, avg_loss, frac)
            risk_usd = equity * risk_per_trade * f

        if self.method == "atr" and atr_points > 0:
            # scale risk proportionally to ATR width (wider = fewer lots)
            scale = max(0.25, min(2.0, sl_points / (atr_points + 1e-9)))
            risk_usd *= scale
        elif self.method == "vol_target" and vol_ratio > 0:
            risk_usd *= max(0.25, min(2.0, 1.0 / vol_ratio))
        elif self.method == "drawdown_adjusted":
            risk_usd *= max(0.0, 1.0 - drawdown_pct)

        return _equity_lot(equity, risk_usd, sl_points, point_value_per_lot, min_lot)


def kelly_from_history(pnls: Iterable[float], fraction: float = 1.0) -> Tuple[float, float, float]:
    """Estimate (win_rate, avg_win_pct, avg_loss_pct) from a PnL series."""
    arr = np.asarray(list(pnls), dtype=float)
    if len(arr) < 10:
        return 0.5, 0.01, 0.01
    wins = arr[arr > 0]
    losses = arr[arr < 0]
    wr = len(wins) / len(arr)
    avg_win = float(wins.mean()) if len(wins) else 0.01
    avg_loss = float(abs(losses.mean())) if len(losses) else 0.01
    return wr, avg_win, avg_loss