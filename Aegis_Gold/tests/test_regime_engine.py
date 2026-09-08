"""
tests/test_regime_engine.py
============================
AEGIS GOLD — Regime Engine Unit Tests

Verifies:
1. RegimeEngine causal regime detection (TREND, RANGE, EXPANSION, COMPRESSION, HIGH_VOLATILITY).
"""

import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.regime_engine import RegimeEngine
from brain.frozen_snapshot import build_snapshot


class TestRegimeEngine(unittest.TestCase):

    def test_regime_detection(self):
        """RegimeEngine returns valid regime string on closed snapshot."""
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        candles = [{"time": int(now.timestamp()) - i*300, "open": 2000.0 + i, "high": 2005.0 + i, "low": 1995.0 + i, "close": 2000.0 + i, "volume": 100} for i in range(20)][::-1]
        snap = build_snapshot("XAUUSD", candles, candles, now)

        engine = RegimeEngine()
        regime = engine.detect_regime(snap)
        self.assertIn(regime, ("TREND", "RANGE", "EXPANSION", "COMPRESSION", "HIGH_VOLATILITY", "LOW_VOLATILITY"))
