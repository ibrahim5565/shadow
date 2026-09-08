"""
===========================================================================
AEGIS GOLD — Expected Value (EV) Decision Engine (Phase 6)
===========================================================================

PURPOSE:
  Replaces flat confidence gates with rigorous Expected Value (EV) calculation.

FORMULA:
  EV = P(win) * ExpectedProfit - P(loss) * ExpectedLoss - TotalExecutionCost

EXECUTION COST COMPONENTS:
  1. Spread Cost         — (Ask - Bid) * lot_size * contract_size
  2. Commission Cost     — $7.00 / lot round-turn (broker standard)
  3. Estimated Slippage  — 10 pts Gold ($0.10) / 2 pts EURUSD ($0.00002)
  4. Latency Buffer      — Execution latency penalty based on volatility

APPROVAL RULE:
  Trade is APPROVED if EV > required_edge (default $0.50 per trade).
  Trades with EV <= 0 after execution costs are strictly REJECTED.
===========================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional

logger = logging.getLogger("aegis.ev_engine")

DEFAULT_CONTRACT_SIZE = {
    "XAUUSD": 100,    # 1 lot Gold = 100 oz
    "EURUSD": 100000, # 1 lot EURUSD = 100,000 units
}

DEFAULT_COMMISSION_PER_LOT = 7.0  # $7 per lot round-turn
DEFAULT_REQUIRED_EDGE = 0.50       # Minimum $0.50 positive EV required


@dataclass
class EVResult:
    approved: bool
    ev: float
    win_probability: float
    loss_probability: float
    expected_profit: float
    expected_loss: float
    total_execution_cost: float
    spread_cost: float
    commission_cost: float
    slippage_cost: float
    net_rr_ratio: float
    reason: str


class EVDecisionEngine:
    """
    Calculates net Expected Value after subtracting all execution friction.
    """

    def __init__(
        self,
        required_edge: float = DEFAULT_REQUIRED_EDGE,
        commission_per_lot: float = DEFAULT_COMMISSION_PER_LOT,
    ):
        self.required_edge = required_edge
        self.commission_per_lot = commission_per_lot

    def evaluate_ev(
        self,
        direction: str,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        win_prob: float,
        symbol: str = "XAUUSD",
        lot_size: float = 0.01,
        spread_pts: float = 20.0,
        point: float = 0.01,
        slippage_pts: float = 10.0,
    ) -> EVResult:
        """
        Evaluates EV for a proposed trade setup after deducting full execution costs.
        """
        contract_size = DEFAULT_CONTRACT_SIZE.get(symbol, 100)

        # 1. Price distance calculations
        sl_dist = abs(entry_price - sl_price)
        tp_dist = abs(tp_price - entry_price)

        if sl_dist == 0 or entry_price <= 0:
            return EVResult(
                approved=False, ev=0.0, win_probability=0.0, loss_probability=1.0,
                expected_profit=0.0, expected_loss=0.0, total_execution_cost=0.0,
                spread_cost=0.0, commission_cost=0.0, slippage_cost=0.0,
                net_rr_ratio=0.0, reason="Invalid zero SL distance or entry price",
            )

        # 2. Financial profit/loss expectations (gross)
        gross_profit = tp_dist * lot_size * contract_size
        gross_loss = sl_dist * lot_size * contract_size

        # 3. Execution costs
        spread_cost = (spread_pts * point) * lot_size * contract_size
        commission_cost = self.commission_per_lot * lot_size
        slippage_cost = (slippage_pts * point) * lot_size * contract_size
        total_execution_cost = spread_cost + commission_cost + slippage_cost

        # 4. Probabilities & EV
        p_win = max(0.05, min(0.95, win_prob))
        p_loss = 1.0 - p_win

        # EV = P(win) * GrossProfit - P(loss) * GrossLoss - TotalExecutionCost
        ev = (p_win * gross_profit) - (p_loss * gross_loss) - total_execution_cost

        net_rr = round(tp_dist / sl_dist, 2)
        approved = ev >= self.required_edge

        if approved:
            reason = (
                f"EV APPROVED | EV=${ev:.2f} >= ${self.required_edge:.2f} edge | "
                f"P(win)={p_win*100:.1f}% Profit=${gross_profit:.2f} Loss=${gross_loss:.2f} "
                f"Costs=${total_execution_cost:.2f} R:R={net_rr}R"
            )
        else:
            reason = (
                f"EV REJECTED | EV=${ev:.2f} < ${self.required_edge:.2f} required edge | "
                f"P(win)={p_win*100:.1f}% Costs=${total_execution_cost:.2f}"
            )

        logger.info(f"[EV ENGINE] {reason}")

        return EVResult(
            approved=approved,
            ev=round(ev, 4),
            win_probability=round(p_win, 4),
            loss_probability=round(p_loss, 4),
            expected_profit=round(gross_profit, 2),
            expected_loss=round(gross_loss, 2),
            total_execution_cost=round(total_execution_cost, 2),
            spread_cost=round(spread_cost, 2),
            commission_cost=round(commission_cost, 2),
            slippage_cost=round(slippage_cost, 2),
            net_rr_ratio=net_rr,
            reason=reason,
        )
