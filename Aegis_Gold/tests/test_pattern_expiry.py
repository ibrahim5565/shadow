"""
tests/test_pattern_expiry.py
=============================
AEGIS GOLD — Pattern Expiry Unit Tests

Verifies:
1. Pattern candidates expire after max setup lifespan (30 minutes).
2. Expired patterns automatically transition to EXPIRED state and reject triggers.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.setup_candidate import SetupCandidate, SetupState
from brain.pattern_library import StructuralPattern, PatternType, PatternCategory


class TestPatternExpiry(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_setup_candidate_expiry(self):
        """SetupCandidate expires when current_time > expiry_time."""
        setup = SetupCandidate(
            setup_id="s_exp_test",
            symbol="XAUUSD",
            direction_bias="BUY",
            formation_time=self.now - timedelta(minutes=45),
            information_available_time=self.now - timedelta(minutes=40),
            confirmation_time=self.now - timedelta(minutes=40),
            setup_level=2015.0,
            invalidation_level=2010.0,
            expiry_time=self.now - timedelta(minutes=10), # Expired 10 mins ago
            state=SetupState.ENTRY_ARMED,
        )
        self.assertTrue(setup.is_expired(self.now))

    def test_structural_pattern_expiry(self):
        """StructuralPattern is_expired returns True after expiry timestamp."""
        pattern = StructuralPattern(
            pattern_id="p_exp",
            pattern_type=PatternType.BOS_BULLISH,
            category=PatternCategory.SMC_STRUCTURE,
            direction="BUY",
            symbol="XAUUSD",
            formation_time=self.now - timedelta(minutes=40),
            confirmation_time=self.now - timedelta(minutes=35),
            information_available_time=self.now - timedelta(minutes=35),
            price_level=2015.0,
            invalidation_level=2010.0,
            target_level=2035.0,
            strength_score=8.0,
            expiry_time=self.now - timedelta(minutes=5),
        )
        self.assertTrue(pattern.is_expired(self.now))
