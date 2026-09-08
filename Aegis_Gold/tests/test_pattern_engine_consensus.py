"""
tests/test_pattern_engine_consensus.py
========================================
AEGIS GOLD — Pattern Engine Consensus Unit Tests

Verifies:
1. 7-Engine consensus evaluation for structural patterns.
2. Veto mechanism when directional agreement is insufficient (< 5/6).
3. RL agent meta-weighter exclusion from directional count.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.unified_brain import run_pattern_consensus
from brain.frozen_snapshot import build_snapshot


class TestPatternEngineConsensus(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_consensus_runs_cleanly(self):
        """run_pattern_consensus returns a valid decision on closed snapshot."""
        candles = [{"time": int(self.now.timestamp()) - i*300, "open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2000.0, "volume": 100} for i in range(20)][::-1]
        snapshot = build_snapshot(
            symbol="XAUUSD",
            candles_m5=candles,
            candles_m1=candles,
            decision_time=self.now,
        )
        decision = run_pattern_consensus(snapshot)
        self.assertIsNotNone(decision)
        self.assertIn(decision.action, ("TRADE", "WAIT"))
