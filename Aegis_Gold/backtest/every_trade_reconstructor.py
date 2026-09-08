"""
===========================================================================
AEGIS GOLD — Every-Trade Reconstructor (Phase 4)
===========================================================================

PURPOSE:
  Reconstructs every historical trade candidate (winning, losing, breakeven,
  expired, invalidated, chased) into canonical database files:
    - data/validation/pattern_trade_database.json
    - data/validation/pattern_trade_database.csv

ZERO SURVIVORSHIP BIAS:
  Saves candidate setups regardless of whether they resulted in a trade or wait.
===========================================================================
"""

from __future__ import annotations

import csv
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.pattern_event import PatternEvent
from backtest.pattern_outcome_engine import RealizedTradeOutcome

logger = logging.getLogger("aegis.trade_reconstructor")


@dataclass
class ReconstructedTradeRecord:
    trade_id: str
    symbol: str
    pattern_type: str
    pattern_scale: str
    direction: str
    detection_time: str
    confirmation_time: str
    earliest_entry_time: str
    entry_time: str
    entry_price: float
    sl_price: float
    tp_price: float
    expected_move_pts: float
    expected_r: float
    forecast_mfe: float
    forecast_mae: float
    smc_vote: str
    kronos_vote: str
    quant_context: str
    ml_vote: str
    omega_vote: str
    unified_decision: str
    rl_weight: float
    engine_consensus_count: int
    entry_timing: str                  # "EARLIEST", "TRIGGER", "CONFIRMATION", "LATE", "CHASE"
    exit_time: str
    exit_price: float
    exit_reason: str
    gross_pnl: float
    costs: float
    net_pnl: float
    r_result: float
    actual_mfe_pts: float
    actual_mae_pts: float
    holding_time_sec: int
    outcome: str                       # "WIN", "LOSS", "BREAKEVEN"
    causal_valid: bool = True
    future_leakage_detected: bool = False


class EveryTradeReconstructor:
    """
    Historical Trade Reconstruction & Database Export Engine.
    """

    def export_trade_database(
        self,
        records: List[ReconstructedTradeRecord],
        json_path: str = "data/validation/pattern_trade_database.json",
        csv_path: str = "data/validation/pattern_trade_database.csv",
    ) -> bool:
        """
        Exports reconstructed trade ledger to canonical JSON and CSV.
        """
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        dict_records = [asdict(r) for r in records]

        # 1. Export JSON
        with open(json_path, "w") as f:
            json.dump({"total_candidates": len(records), "records": dict_records}, f, indent=2)

        # 2. Export CSV
        if records:
            fieldnames = list(dict_records[0].keys())
            with open(csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(dict_records)

        logger.info(f"💾 [TRADE RECONSTRUCTOR] Exported {len(records)} candidate trade records to {json_path} and {csv_path}.")
        return True


@dataclass
class OpportunityLedgerRecord:
    timestamp: str
    symbol: str
    pattern_type: str
    pattern_scale: str
    direction: str
    engine_consensus_count: int
    forecast_move_pts: float
    expected_ev: float
    entry_quality: str
    decision: str                      # "TRADE" or "WAIT"
    wait_reason: str                   # e.g. "INSUFFICIENT_RR", "MOVE_CONSUMED", "STALE_TRIGGER"
    future_move_realized_pts: float
    future_mfe_pts: float
    future_mae_pts: float
    counterfactual_trade_pnl: float


def export_opportunity_ledger(
    records: List[OpportunityLedgerRecord],
    csv_path: str = "data/validation/opportunity_ledger.csv",
) -> bool:
    """Exports opportunity ledger containing BOTH TRADE and WAIT decisions."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    dict_records = [asdict(r) for r in records]

    if records:
        fieldnames = list(dict_records[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(dict_records)

    logger.info(f"💾 [OPPORTUNITY LEDGER] Exported {len(records)} opportunity records (TRADE + WAIT) to {csv_path}.")
    return True
