"""
tests/test_backtest_live_parity.py
===================================
AEGIS GOLD — Backtest / Live Parity Unit Tests

Verifies:
1. Decision invariance across Backtest, Shadow, and Live Decision Engine paths.
2. Identical snapshot inputs produce 100% identical outputs across all environments.
"""

import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backtest.parity_checker import BacktestLiveParityChecker
from brain.frozen_snapshot import build_snapshot


class TestBacktestLiveParity(unittest.TestCase):

    def test_backtest_shadow_live_parity(self):
        """Identical snapshots must yield 100% identical decisions across all modes."""
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        candles = [{"time": int(now.timestamp()) - i*300, "open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2000.0, "volume": 100} for i in range(20)][::-1]
        snap = build_snapshot("XAUUSD", candles, candles, now)

        checker = BacktestLiveParityChecker()
        res = checker.verify_parity([snap])
        self.assertTrue(res.passed)
        self.assertEqual(res.discrepancies, [])
