"""
Test: Confidence Must Not Gate Trades

Verify that changing confidence values alone cannot change a pattern decision.
The decision must be based on pattern quality, not arbitrary confidence thresholds.

Test Strategy:
1. Create a valid pattern with all quality factors positive
2. Vary confidence from 0% to 100%
3. Verify decision remains TRADE throughout
4. Create an invalid pattern (negative EV)
5. Vary confidence from 0% to 100%
6. Verify decision remains WAIT throughout
"""

import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.pattern_quality import PatternQuality


class TestNoConfidenceGates(unittest.TestCase):
    """
    Verify confidence does not act as trade gate.
    """
    
    def test_valid_pattern_trades_regardless_of_confidence(self):
        """
        A structurally valid pattern with positive EV should trade
        regardless of confidence value.
        """
        
        # Create valid pattern (strong structure, positive edge, positive EV)
        for confidence_pct in [0, 10, 30, 50, 70, 90, 100]:
            confidence = confidence_pct / 100.0
            
            pq = PatternQuality(
                structure_strength=0.80,  # Strong
                pattern_type="BULLISH_BOS_OB_SWEEP",
                historical_edge=2.5,  # +2.5R expected
                pattern_sample_size=50,
                mtf_alignment=0.75,
                htf_bias="bullish",
                engine_consensus=0.70,  # 70% agree
                engines_agreeing=5,
                engines_total=7,
                entry_quality=0.80,  # Early entry
                distance_from_origin=5.0,
                expected_move_pts=100,
                consumed_move_pts=20,
                remaining_move_pct=0.80,  # 80% remaining
                target_validity=0.90,
                target_distance_pts=150,
                invalidation_distance_pts=50,
                rr_ratio=3.0,
                expected_value_usd=5.50,  # Positive EV
                win_probability=confidence,  # VARY THIS - should not affect decision
                avg_win_r=2.8,
                avg_loss_r=-1.0,
                regime_compatible=True,
                regime_type="TRENDING",
                vetoes=[]
            )
            
            # Decision should be TRADE regardless of confidence
            self.assertTrue(
                pq.is_tradeable(),
                f"Valid pattern should trade at confidence={confidence_pct}%"
            )
    
    def test_invalid_pattern_waits_regardless_of_confidence(self):
        """
        A pattern with negative EV should NOT trade regardless
        of confidence value.
        """
        
        # Create invalid pattern (negative EV)
        for confidence_pct in [0, 10, 30, 50, 70, 90, 100]:
            confidence = confidence_pct / 100.0
            
            pq = PatternQuality(
                structure_strength=0.80,
                pattern_type="BULLISH_BOS_OB_SWEEP",
                historical_edge=-0.5,  # Negative edge
                pattern_sample_size=50,
                mtf_alignment=0.75,
                htf_bias="bullish",
                engine_consensus=0.70,
                engines_agreeing=5,
                engines_total=7,
                entry_quality=0.80,
                distance_from_origin=5.0,
                expected_move_pts=100,
                consumed_move_pts=20,
                remaining_move_pct=0.80,
                target_validity=0.90,
                target_distance_pts=150,
                invalidation_distance_pts=50,
                rr_ratio=3.0,
                expected_value_usd=-2.50,  # NEGATIVE EV
                win_probability=confidence,  # VARY THIS - should not affect decision
                avg_win_r=2.0,
                avg_loss_r=-1.0,
                regime_compatible=True,
                regime_type="TRENDING",
                vetoes=[]
            )
            
            # Decision should be WAIT regardless of high confidence
            self.assertFalse(
                pq.is_tradeable(),
                f"Invalid pattern (negative EV) should NOT trade even at confidence={confidence_pct}%"
            )
    
    def test_structural_quality_gates_work(self):
        """
        Verify that actual quality factors (structure, EV, edge) do gate trades.
        """
        
        # Base valid pattern
        base_args = {
            "pattern_type": "BULLISH_BOS",
            "historical_edge": 2.0,
            "pattern_sample_size": 50,
            "mtf_alignment": 0.75,
            "htf_bias": "bullish",
            "engine_consensus": 0.70,
            "engines_agreeing": 5,
            "engines_total": 7,
            "entry_quality": 0.80,
            "distance_from_origin": 5.0,
            "expected_move_pts": 100,
            "consumed_move_pts": 20,
            "remaining_move_pct": 0.80,
            "target_validity": 0.90,
            "target_distance_pts": 150,
            "invalidation_distance_pts": 50,
            "rr_ratio": 3.0,
            "expected_value_usd": 5.0,
            "win_probability": 0.65,
            "avg_win_r": 2.5,
            "avg_loss_r": -1.0,
            "regime_compatible": True,
            "regime_type": "TRENDING",
            "vetoes": []
        }
        
        # Test 1: Weak structure should block
        pq = PatternQuality(structure_strength=0.30, **base_args)
        self.assertFalse(pq.is_tradeable(), "Weak structure should block trade")
        
        # Test 2: Strong structure should pass
        pq = PatternQuality(structure_strength=0.80, **base_args)
        self.assertTrue(pq.is_tradeable(), "Strong structure should allow trade")
        
        # Test 3: Negative EV should block (even with strong structure)
        args_negative_ev = {**base_args, "expected_value_usd": -2.0, "historical_edge": -0.5}
        pq = PatternQuality(structure_strength=0.80, **args_negative_ev)
        self.assertFalse(pq.is_tradeable(), "Negative EV should block trade")
        
        # Test 4: Move consumed should block
        args_consumed = {**base_args, "remaining_move_pct": 0.20}
        pq = PatternQuality(structure_strength=0.80, **args_consumed)
        self.assertFalse(pq.is_tradeable(), "Consumed move should block trade")
        
        # Test 5: Chase should block
        args_chase = {**base_args, "entry_quality": 0.10}
        pq = PatternQuality(structure_strength=0.80, **args_chase)
        self.assertFalse(pq.is_tradeable(), "Chase entry should block trade")


if __name__ == "__main__":
    unittest.main()
