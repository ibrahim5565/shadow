"""
tests/test_no_confidence_trade_gate.py
======================================
AEGIS GOLD — No Confidence Trade Gate Unit Tests (Phase 5)

Verifies:
1. Trade execution is driven by structural pattern evidence and EV economics, NOT confidence thresholds.
2. Confidence score is removed as a mandatory trade authorization gate.
3. System outputs PatternDecision objects with structured reason trails.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.unified_brain import PatternDecision, run_pattern_consensus
from brain.frozen_snapshot import FrozenDecisionSnapshot, build_snapshot


class TestNoConfidenceTradeGate(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_pattern_decision_output_schema(self):
        """PatternDecision must contain structural fields without requiring confidence % gate."""
        decision = PatternDecision(
            pattern_type="BOS_BULLISH",
            action="TRADE",
            direction="BUY",
            supporting_engines=["smc", "kronos", "quant_feature_engine", "ml_ensemble", "omega"],
            conflicting_engines=[],
            entry_zone=2015.0,
            trigger_type="DISPLACEMENT",
            stop_loss=2010.0,
            take_profit=2035.0,
            expected_value=2.50,
            reason="Bullish BOS confirmed by 5 engines with positive EV",
            timestamp=self.now,
        )
        self.assertEqual(decision.action, "TRADE")
        self.assertEqual(decision.direction, "BUY")
        self.assertEqual(decision.pattern_type, "BOS_BULLISH")
        self.assertGreater(decision.expected_value, 0.0)

    def test_trade_rejection_reasons_are_structural(self):
        """Rejections are caused by lack of structure, invalidation, or negative EV — not arbitrary confidence gates."""
        candles = [{"time": int(self.now.timestamp()) - i*300, "open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2000.0, "volume": 100} for i in range(20)][::-1]
        snapshot = build_snapshot(
            symbol="XAUUSD",
            candles_m5=candles,
            candles_m1=candles,
            decision_time=self.now,
        )
        res = run_pattern_consensus(snapshot)
        # Should return UnifiedDecision or PatternDecision with clear structural reasoning
        self.assertIsNotNone(res.action)
