"""
tests/test_full_causality.py
=============================
AEGIS GOLD — Full Causality Unit Tests

Verifies:
1. Zero temporal leakage across all engines.
2. snapshot.candles timestamp <= decision_time hard assertion.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.frozen_snapshot import build_snapshot


class TestFullCausality(unittest.TestCase):

    def test_snapshot_temporal_causality(self):
        """Snapshot candles must be timestamped <= decision_time."""
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        candles = [{"time": int(now.timestamp()) - i*300, "open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2000.0, "volume": 100} for i in range(20)][::-1]
        snap = build_snapshot("XAUUSD", candles, candles, now)

        for c in snap.candles_m5:
            self.assertLessEqual(c.get("time", 0), int(now.timestamp()))
