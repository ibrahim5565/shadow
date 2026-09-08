"""
tests/test_pattern_backtest.py
===============================
AEGIS GOLD — Pattern Backtest Engine Unit Tests

Verifies:
1. PatternBacktestEngine runs chronological pattern replay.
2. Returns structured pattern performance metrics and breakdown by pattern type.
"""

import sys
import os
import unittest
import math
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backtest.pattern_backtest_engine import PatternBacktestEngine


class TestPatternBacktest(unittest.TestCase):

    def test_pattern_backtest_engine_execution(self):
        """PatternBacktestEngine executes simulation on candle history."""
        engine = PatternBacktestEngine(symbol="XAUUSD", spread_pts=15.0, slippage_pts=10.0)
        t0 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        bars = []
        curr = 2000.0
        trend = 1.0

        for i in range(120):
            if i % 30 == 0:
                trend = -trend
            imp = (20.0 * trend) if (i % 10 in (1, 2)) else (math.sin(i / 2.0) * 1.5)
            o = curr
            c = o + imp
            h = max(o, c) + 2.0
            l = min(o, c) - 2.0
            t = int((t0 + timedelta(minutes=5 * i)).timestamp())
            bars.append({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": 500})
            curr = c

        res = engine.run_pattern_backtest(bars)
        self.assertIn("total_trades", res)
        self.assertIn("win_rate", res)
        self.assertIn("profit_factor", res)
        self.assertIn("pattern_matrix", res)
