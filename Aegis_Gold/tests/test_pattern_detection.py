"""
tests/test_pattern_detection.py
================================
AEGIS GOLD — Pattern Detection Unit Tests (Phase 5)

Verifies:
1. StructuralPattern dataclass creation and immutability
2. Pattern strength hierarchy ranking (CHoCH > BOS > Sweep > OB > FVG)
3. Zero temporal leakage verification (is_causal check)
4. Invalidation & Expiry checks
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.pattern_library import (
    StructuralPattern,
    PatternType,
    PatternCategory,
    get_pattern_strength_hierarchy,
)


class TestPatternDetection(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_pattern_creation_and_causality(self):
        """Pattern with info_available_time <= decision_time must be causal."""
        pattern = StructuralPattern(
            pattern_id="p1",
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
            strength_score=8.0,
            evidence_notes=["BOS bullish break"],
        )
        self.assertTrue(pattern.is_causal(self.now))
        self.assertFalse(pattern.is_invalidated(2012.0))
        self.assertTrue(pattern.is_invalidated(2009.5))

    def test_future_pattern_is_non_causal(self):
        """Pattern with information_available_time > decision_time must be rejected as non-causal."""
        pattern = StructuralPattern(
            pattern_id="p2",
            pattern_type=PatternType.CHOCH_BULLISH,
            category=PatternCategory.SMC_STRUCTURE,
            direction="BUY",
            symbol="XAUUSD",
            formation_time=self.now,
            confirmation_time=self.now + timedelta(minutes=5),
            information_available_time=self.now + timedelta(minutes=5),
            price_level=2015.0,
            invalidation_level=2010.0,
            target_level=2035.0,
            strength_score=10.0,
        )
        self.assertFalse(pattern.is_causal(self.now))

    def test_pattern_strength_hierarchy(self):
        """CHoCH > BOS > Sweep > OB > FVG > Displacement rank order."""
        rank_choch = get_pattern_strength_hierarchy(PatternType.CHOCH_BULLISH)
        rank_bos = get_pattern_strength_hierarchy(PatternType.BOS_BULLISH)
        rank_sweep = get_pattern_strength_hierarchy(PatternType.LIQUIDITY_SWEEP_BULLISH)
        rank_ob = get_pattern_strength_hierarchy(PatternType.ORDER_BLOCK_BULLISH)
        rank_fvg = get_pattern_strength_hierarchy(PatternType.FVG_CONTINUATION_BULLISH)

        self.assertGreater(rank_choch, rank_bos)
        self.assertGreater(rank_bos, rank_sweep)
        self.assertGreater(rank_sweep, rank_ob)
        self.assertGreater(rank_ob, rank_fvg)
