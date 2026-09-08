"""
tests/test_trade_reconstruction.py
===================================
AEGIS GOLD — Trade Reconstruction Unit Tests

Verifies:
1. ReconstructedTradeRecord creation.
2. Export to canonical JSON and CSV files (data/validation/pattern_trade_database.json).
"""

import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backtest.every_trade_reconstructor import EveryTradeReconstructor, ReconstructedTradeRecord


class TestTradeReconstruction(unittest.TestCase):

    def test_trade_reconstruction_export(self):
        """EveryTradeReconstructor exports candidate ledger to JSON and CSV."""
        rec = ReconstructedTradeRecord(
            trade_id="rec_1", symbol="XAUUSD", pattern_type="BOS", pattern_scale="MEDIUM",
            direction="BUY", detection_time="2024-01-01T12:00:00+00:00", confirmation_time="2024-01-01T12:05:00+00:00",
            earliest_entry_time="2024-01-01T12:05:00+00:00", entry_time="2024-01-01T12:05:00+00:00",
            entry_price=2015.0, sl_price=2010.0, tp_price=2035.0, expected_move_pts=200.0, expected_r=4.0,
            forecast_mfe=180.0, forecast_mae=15.0, smc_vote="BUY", kronos_vote="BUY", quant_context="TREND",
            ml_vote="BUY", omega_vote="BUY", unified_decision="TRADE", rl_weight=1.0, engine_consensus_count=5,
            entry_timing="GOOD", exit_time="2024-01-01T12:35:00+00:00", exit_price=2035.0, exit_reason="TP",
            gross_pnl=20.0, costs=0.32, net_pnl=19.68, r_result=3.94, actual_mfe_pts=200.0, actual_mae_pts=15.0,
            holding_time_sec=1800, outcome="WIN",
        )

        reconstructor = EveryTradeReconstructor()
        success = reconstructor.export_trade_database([rec])
        self.assertTrue(success)
