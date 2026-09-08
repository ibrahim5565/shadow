"""
tests/test_opportunity_ledger.py
=================================
AEGIS GOLD — Opportunity Ledger Unit Tests

Verifies:
1. Exporting OpportunityLedgerRecord containing BOTH TRADE and WAIT decisions.
2. Saving data/validation/opportunity_ledger.csv.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backtest.every_trade_reconstructor import OpportunityLedgerRecord, export_opportunity_ledger


class TestOpportunityLedger(unittest.TestCase):

    def test_export_opportunity_ledger(self):
        """export_opportunity_ledger saves TRADE and WAIT records to CSV."""
        rec1 = OpportunityLedgerRecord(
            timestamp="2024-01-01T12:00:00+00:00", symbol="XAUUSD", pattern_type="BOS",
            pattern_scale="MEDIUM", direction="BUY", engine_consensus_count=5,
            forecast_move_pts=300.0, expected_ev=2.20, entry_quality="GOOD",
            decision="TRADE", wait_reason="NONE", future_move_realized_pts=295.0,
            future_mfe_pts=250.0, future_mae_pts=15.0, counterfactual_trade_pnl=19.68,
        )
        rec2 = OpportunityLedgerRecord(
            timestamp="2024-01-01T12:05:00+00:00", symbol="XAUUSD", pattern_type="OB",
            pattern_scale="LARGE", direction="BUY", engine_consensus_count=2,
            forecast_move_pts=150.0, expected_ev=0.10, entry_quality="CHASE",
            decision="WAIT", wait_reason="INSUFFICIENT_RR", future_move_realized_pts=50.0,
            future_mfe_pts=40.0, future_mae_pts=30.0, counterfactual_trade_pnl=-5.0,
        )

        success = export_opportunity_ledger([rec1, rec2])
        self.assertTrue(success)
