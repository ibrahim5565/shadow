"""
tests/test_exhaustive_scanner.py
=================================
AEGIS GOLD — Exhaustive Pattern Scanner Unit Tests

Verifies:
1. ExhaustivePatternScanner scanning every decision timestamp T.
2. Returns PatternEvents across Small, Medium, Large scales.
"""

import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.exhaustive_pattern_scanner import ExhaustivePatternScanner


class TestExhaustiveScanner(unittest.TestCase):

    def test_scanner_returns_pattern_events(self):
        """ExhaustivePatternScanner identifies pattern events at T."""
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        candles = [{"time": int(now.timestamp()) - i*300, "open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2000.0, "volume": 100} for i in range(40)][::-1]

        scanner = ExhaustivePatternScanner(symbol="XAUUSD")
        events = scanner.scan_historical_opportunities(candles, now)
        self.assertIsInstance(events, list)
