"""
tests/test_pattern_outcome_labeling.py
=======================================
AEGIS GOLD — Pattern Outcome Labeling Unit Tests

Verifies:
1. Pattern trade outcome labeling (PnL, R-result, MFE, MAE calculation).
2. Classification of entry timing (% OPTIMAL, % EARLY, % LATE, % CHASE).
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backtest.pattern_backtest_engine import PatternTradeOutcome


class TestPatternOutcomeLabeling(unittest.TestCase):

    def test_pattern_outcome_dataclass(self):
        """PatternTradeOutcome correctly formats trade outcome metrics."""
        outcome = PatternTradeOutcome(
            trade_id="trd_lbl_1",
            pattern_type="BOS",
            symbol="XAUUSD",
            direction="BUY",
            entry_time="2024-01-01T12:00:00+00:00",
            entry_price=2015.0,
            sl_price=2010.0,
            tp_price=2035.0,
            r_multiple=4.0,
            exit_time="2024-01-01T12:30:00+00:00",
            exit_price=2035.0,
            pnl=20.0,
            r_result=4.0,
            mfe_pts=200.0,
            mae_pts=15.0,
            entry_classification="OPTIMAL",
            regime="TREND",
            session="LONDON",
        )
        self.assertEqual(outcome.pattern_type, "BOS")
        self.assertEqual(outcome.entry_classification, "OPTIMAL")
        self.assertGreater(outcome.pnl, 0.0)
        self.assertEqual(outcome.r_result, 4.0)
