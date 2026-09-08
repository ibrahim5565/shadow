"""
tests/test_pattern_sequence_discovery.py
=========================================
AEGIS GOLD — Pattern Sequence Discovery Unit Tests

Verifies:
1. PatternSequenceEngine multi-pattern sequence discovery.
2. Conversion of PatternEvent streams into pattern chains.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.pattern_event import PatternEvent
from brain.pattern_library import PatternType, PatternScale
from brain.pattern_sequence_engine import PatternSequenceEngine


class TestPatternSequenceDiscovery(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.engine = PatternSequenceEngine()

    def test_sequence_discovery_from_events(self):
        """PatternSequenceEngine discovers recurring multi-pattern chains."""
        e1 = PatternEvent(
            symbol="XAUUSD", pattern_id="pe1", pattern_type=PatternType.LIQUIDITY_SWEEP_BULLISH,
            direction="BUY", scale=PatternScale.MEDIUM, detection_time=self.now - timedelta(minutes=20),
            confirmation_time=self.now - timedelta(minutes=15), information_available_time=self.now - timedelta(minutes=15),
            timeframe="M5", price_level=2010.0, invalidation_level=2005.0, target_level=2030.0, strength_score=7.0,
            earliest_entry_time=self.now - timedelta(minutes=15), expiry_time=self.now + timedelta(minutes=30),
        )
        e2 = PatternEvent(
            symbol="XAUUSD", pattern_id="pe2", pattern_type=PatternType.BOS_BULLISH,
            direction="BUY", scale=PatternScale.MEDIUM, detection_time=self.now - timedelta(minutes=10),
            confirmation_time=self.now - timedelta(minutes=5), information_available_time=self.now - timedelta(minutes=5),
            timeframe="M5", price_level=2015.0, invalidation_level=2010.0, target_level=2035.0, strength_score=8.0,
            earliest_entry_time=self.now - timedelta(minutes=5), expiry_time=self.now + timedelta(minutes=45),
        )

        sequences = self.engine.discover_sequences([e1, e2])
        self.assertIsInstance(sequences, list)
        self.assertGreater(len(sequences), 0)
