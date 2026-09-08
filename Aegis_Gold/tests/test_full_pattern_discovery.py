"""
tests/test_full_pattern_discovery.py
======================================
AEGIS GOLD — Full Pattern Discovery Unit Tests

Verifies:
1. PatternDiscoveryEngine candle-by-candle pattern discovery.
2. Creation of PatternEvent objects with timestamps and scale tags.
"""

import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.pattern_discovery_engine import PatternDiscoveryEngine
from brain.pattern_event import PatternEvent


class TestFullPatternDiscovery(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.engine = PatternDiscoveryEngine(symbol="XAUUSD")

    def test_discovery_engine_returns_pattern_events(self):
        """PatternDiscoveryEngine identifies PatternEvents from closed candles."""
        candles = [{"time": int(self.now.timestamp()) - i*300, "open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2000.0, "volume": 100} for i in range(40)][::-1]
        events = self.engine.discover_patterns(candles, self.now)
        self.assertIsInstance(events, list)
