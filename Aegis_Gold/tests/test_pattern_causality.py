"""
tests/test_pattern_causality.py
================================
AEGIS GOLD — Pattern Causality Unit Tests

Verifies:
1. Every pattern object contains valid information_available_time <= decision_time.
2. Futures lookups during pattern formation are strictly forbidden.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.pattern_library import StructuralPattern, PatternType, PatternCategory


class TestPatternCausality(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_causal_pattern_assertion(self):
        """Pattern with information_available_time <= decision_time passes causality assertion."""
        pattern = StructuralPattern(
            pattern_id="p_causal",
            pattern_type=PatternType.BOS_BULLISH,
            category=PatternCategory.SMC_STRUCTURE,
            direction="BUY",
            symbol="XAUUSD",
            formation_time=self.now - timedelta(minutes=10),
            confirmation_time=self.now - timedelta(minutes=5),
            information_available_time=self.now - timedelta(minutes=5),
            price_level=2015.0,
            invalidation_level=2010.0,
            target_level=2035.0,
            strength_score=8.5,
        )
        self.assertTrue(pattern.is_causal(self.now))

    def test_non_causal_pattern_fails_assertion(self):
        """Pattern with future information_available_time > decision_time fails causality assertion."""
        pattern = StructuralPattern(
            pattern_id="p_non_causal",
            pattern_type=PatternType.BOS_BULLISH,
            category=PatternCategory.SMC_STRUCTURE,
            direction="BUY",
            symbol="XAUUSD",
            formation_time=self.now,
            confirmation_time=self.now + timedelta(minutes=5),
            information_available_time=self.now + timedelta(minutes=5),
            price_level=2015.0,
            invalidation_level=2010.0,
            target_level=2035.0,
            strength_score=8.5,
        )
        self.assertFalse(pattern.is_causal(self.now))
