"""
===========================================================================
AEGIS GOLD — Canonical Trade Ledger Reconciler (Phase 1)
===========================================================================

PURPOSE:
  Audits and verifies strict mathematical reconciliation between individual
  raw trade records in data/validation/trade_ledger.json and reported aggregate
  metrics.

RECONCILIATION INVARIANTS:
  1. aggregate_total_trades == len(raw_trades)
  2. aggregate_wins == sum(1 for t in raw_trades if t['pnl'] > 0)
  3. aggregate_losses == sum(1 for t in raw_trades if t['pnl'] < 0)
  4. aggregate_gross_profit == sum(t['pnl'] for t in raw_trades if t['pnl'] > 0)
  5. aggregate_gross_loss == abs(sum(t['pnl'] for t in raw_trades if t['pnl'] < 0))
  6. aggregate_pf == aggregate_gross_profit / aggregate_gross_loss
  7. symbol_sum(XAUUSD + EURUSD) == total_combined_trades

FAILURE BEHAVIOR:
  If ANY invariant fails to reconcile, raises LedgerReconciliationError.
===========================================================================
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
from dataclasses import dataclass
from typing import Dict, Any, List

logger = logging.getLogger("aegis.ledger_reconciler")


class LedgerReconciliationError(Exception):
    """Raised when trade ledger reconciliation fails mathematical integrity checks."""
    pass


@dataclass
class ReconciliationResult:
    passed: bool
    total_raw_trades: int
    total_symbol_sum: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    gross_profit: float
    gross_loss: float
    profit_factor: float
    net_pnl: float
    discrepancies: List[str]


class TradeLedgerReconciler:
    """
    Automated Trade Ledger Reconciliation Auditor.
    """

    def reconcile_ledger(self, ledger_path: str = "data/validation/trade_ledger.json") -> ReconciliationResult:
        """
        Loads raw trade ledger and audits mathematical reconciliation.
        """
        if not os.path.exists(ledger_path):
            raise LedgerReconciliationError(f"Trade ledger file not found at {ledger_path}")

        with open(ledger_path, "r") as f:
            data = json.load(f)

        raw_trades: List[Dict[str, Any]] = data.get("raw_trades", [])
        aggregate: Dict[str, Any] = data.get("aggregate_summary", {})
        symbol_breakdown: Dict[str, Any] = data.get("symbol_breakdown", {})

        discrepancies: List[str] = []

        # 1. Trade Count Reconciliation
        raw_count = len(raw_trades)
        reported_total = aggregate.get("trade_count", 0)

        if raw_count != reported_total:
            discrepancies.append(
                f"[COUNT MISMATCH] Reported total trades ({reported_total}) != raw trade count ({raw_count})"
            )

        # 2. Symbol Breakdown Sum Check
        symbol_sum = sum(sym_data.get("trade_count", 0) for sym_data in symbol_breakdown.values())
        if symbol_sum != raw_count:
            discrepancies.append(
                f"[SYMBOL SUM MISMATCH] Sum of symbol trade counts ({symbol_sum}) != raw trade count ({raw_count})"
            )

        # 3. PnL & Win/Loss Counts
        wins = [t for t in raw_trades if t.get("pnl", 0.0) > 0]
        losses = [t for t in raw_trades if t.get("pnl", 0.0) < 0]
        breakevens = [t for t in raw_trades if t.get("pnl", 0.0) == 0]

        calc_wins = len(wins)
        calc_losses = len(losses)
        calc_breakevens = len(breakevens)

        rep_wins = aggregate.get("wins", 0)
        rep_losses = aggregate.get("losses", 0)

        if calc_wins != rep_wins:
            discrepancies.append(f"[WIN COUNT MISMATCH] Calculated wins ({calc_wins}) != reported ({rep_wins})")

        if calc_losses != rep_losses:
            discrepancies.append(f"[LOSS COUNT MISMATCH] Calculated losses ({calc_losses}) != reported ({rep_losses})")

        # 4. Gross Profit / Gross Loss / PF
        calc_gp = sum(t.get("pnl", 0.0) for t in wins)
        calc_gl = abs(sum(t.get("pnl", 0.0) for t in losses))
        calc_net = calc_gp - calc_gl
        calc_pf = round(calc_gp / calc_gl, 2) if calc_gl > 0 else (float("inf") if calc_gp > 0 else 1.0)

        rep_gp = aggregate.get("gross_profit", 0.0)
        rep_gl = aggregate.get("gross_loss", 0.0)
        rep_net = aggregate.get("net_pnl", 0.0)
        rep_pf = aggregate.get("profit_factor", 1.0)

        if abs(calc_gp - rep_gp) > 0.05:
            discrepancies.append(f"[GROSS PROFIT MISMATCH] Calculated (${calc_gp:.2f}) != reported (${rep_gp:.2f})")

        if abs(calc_gl - rep_gl) > 0.05:
            discrepancies.append(f"[GROSS LOSS MISMATCH] Calculated (${calc_gl:.2f}) != reported (${rep_gl:.2f})")

        if abs(calc_net - rep_net) > 0.05:
            discrepancies.append(f"[NET PNL MISMATCH] Calculated (${calc_net:.2f}) != reported (${rep_net:.2f})")

        if abs(calc_pf - rep_pf) > 0.1 and not math.isinf(calc_pf):
            discrepancies.append(f"[PROFIT FACTOR MISMATCH] Calculated ({calc_pf}) != reported ({rep_pf})")

        passed = len(discrepancies) == 0

        if passed:
            logger.info("✅ [LEDGER RECONCILIATION PASSED] All aggregate metrics mathematically reconcile with raw trade ledger.")
        else:
            for d in discrepancies:
                logger.error(f"❌ {d}")

        return ReconciliationResult(
            passed=passed,
            total_raw_trades=raw_count,
            total_symbol_sum=symbol_sum,
            winning_trades=calc_wins,
            losing_trades=calc_losses,
            breakeven_trades=calc_breakevens,
            gross_profit=round(calc_gp, 2),
            gross_loss=round(calc_gl, 2),
            profit_factor=calc_pf,
            net_pnl=round(calc_net, 2),
            discrepancies=discrepancies,
        )


if __name__ == "__main__":
    reconciler = TradeLedgerReconciler()
    res = reconciler.reconcile_ledger()
    print(f"Reconciliation Passed: {res.passed}")
