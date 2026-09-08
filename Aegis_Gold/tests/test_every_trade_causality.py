"""
tests/test_every_trade_causality.py
====================================
AEGIS GOLD — Every Trade Causality Unit Tests

Verifies:
1. Zero temporal leakage assertion: information_available_time <= decision_time.
2. Every candidate record verifies causal integrity before outcome simulation.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.pattern_event import PatternEvent
from brain.pattern_library import PatternType, PatternScale


class TestEveryTradeCausality(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_causal_pattern_event_assertion(self):
        """PatternEvent with info_available_time <= decision_time passes causality check."""
        event = PatternEvent(
            symbol="XAUUSD", pattern_id="pe1", pattern_type=PatternType.BOS_BULLISH,
            direction="BUY", scale=PatternScale.MEDIUM, detection_time=self.now - timedelta(minutes=10),
            confirmation_time=self.now - timedelta(minutes=5),
            information_available_time=self.now - timedelta(minutes=5),
            timeframe="M5", price_level=2015.0, invalidation_level=2010.0, target_level=2035.0,
            strength_score=8.0, earliest_entry_time=self.now, expiry_time=self.now + timedelta(minutes=45),
        )
        self.assertTrue(event.is_causal(self.now))
