"""
===========================================================================
AEGIS GOLD — Forward-Only Pattern Outcome Engine (Phase 3)
===========================================================================

PURPOSE:
  Simulates trade exit outcomes strictly on future bars timestamped AFTER decision time T.
  Separates predicted forecast parameters from actual ground-truth realized outcomes.
===========================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger("aegis.pattern_outcome")


@dataclass
class RealizedTradeOutcome:
    trade_id: str
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    pnl: float
    r_result: float
    actual_mfe_pts: float
    actual_mae_pts: float
    holding_time_sec: int
    exit_reason: str                   # "TP", "SL", "TIMEOUT", "INVALIDATED"
    outcome_label: str                 # "WIN", "LOSS", "BREAKEVEN"


class PatternOutcomeEngine:
    """
    Forward-Only Trade Outcome Simulation Engine.
    """

    def simulate_forward_outcome(
        self,
        trade_id: str,
        direction: str,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        entry_time: datetime,
        future_bars: List[Dict[str, Any]],
        lot_size: float = 0.01,
        point: float = 0.01,
        symbol: str = "XAUUSD",
    ) -> RealizedTradeOutcome:
        """
        Simulates price path strictly on future_bars (t > T) until TP, SL, or timeout.
        """
        contract_size = 100 if "XAUUSD" in symbol else 100000
        mfe_pts = 0.0
        mae_pts = 0.0
        exit_price = entry_price
        exit_time = entry_time.isoformat()
        exit_reason = "TIMEOUT"
        hit = False

        for bar in future_bars:
            b_sec = bar.get("time", 0)
            b_time = datetime.fromtimestamp(b_sec, tz=timezone.utc).isoformat()
            high = float(bar.get("high", entry_price))
            low = float(bar.get("low", entry_price))

            if direction == "BUY":
                curr_mfe = (high - entry_price) / point if point > 0 else 0.0
                curr_mae = (entry_price - low) / point if point > 0 else 0.0
                if curr_mfe > mfe_pts: mfe_pts = curr_mfe
                if curr_mae > mae_pts: mae_pts = curr_mae

                if low <= sl_price:
                    exit_price = sl_price
                    exit_time = b_time
                    exit_reason = "SL"
                    hit = True
                    break
                elif high >= tp_price:
                    exit_price = tp_price
                    exit_time = b_time
                    exit_reason = "TP"
                    hit = True
                    break

            elif direction == "SELL":
                curr_mfe = (entry_price - low) / point if point > 0 else 0.0
                curr_mae = (high - entry_price) / point if point > 0 else 0.0
                if curr_mfe > mfe_pts: mfe_pts = curr_mfe
                if curr_mae > mae_pts: mae_pts = curr_mae

                if high >= sl_price:
                    exit_price = sl_price
                    exit_time = b_time
                    exit_reason = "SL"
                    hit = True
                    break
                elif low <= tp_price:
                    exit_price = tp_price
                    exit_time = b_time
                    exit_reason = "TP"
                    hit = True
                    break

        if not hit and future_bars:
            exit_price = float(future_bars[-1].get("close", entry_price))
            exit_time = datetime.fromtimestamp(future_bars[-1].get("time", 0), tz=timezone.utc).isoformat()

        sl_dist = abs(entry_price - sl_price)
        price_diff = (exit_price - entry_price) if direction == "BUY" else (entry_price - exit_price)
        net_pnl = round(price_diff * lot_size * contract_size, 2)
        r_res = round(net_pnl / (sl_dist * lot_size * contract_size), 2) if sl_dist > 0 else 0.0

        label = "WIN" if net_pnl > 0 else ("LOSS" if net_pnl < 0 else "BREAKEVEN")
        h_sec = int((datetime.fromisoformat(exit_time) - entry_time).total_seconds())

        return RealizedTradeOutcome(
            trade_id=trade_id,
            entry_time=entry_time.isoformat(),
            entry_price=entry_price,
            exit_time=exit_time,
            exit_price=exit_price,
            pnl=net_pnl,
            r_result=r_res,
            actual_mfe_pts=round(mfe_pts, 1),
            actual_mae_pts=round(mae_pts, 1),
            holding_time_sec=h_sec,
            exit_reason=exit_reason,
            outcome_label=label,
        )
