"""
AEGIS GOLD — Phase G Verification: Pattern Outcome Tracking

Tests pattern outcome tracking, historical edge calculation, and missed opportunity analysis.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_pattern_tracking_lifecycle():
    """
    Test: Pattern goes through full lifecycle: PENDING → TP_HIT
    """
    from brain.pattern_outcome_tracker import PatternOutcomeTracker, PatternOutcome
    
    # Use temporary storage
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        tracker = PatternOutcomeTracker(storage_path=temp_path)
        
        detection_time = datetime(2026, 8, 11, 10, 0, 0)
        
        # Track new pattern
        pattern = tracker.track_pattern(
            pattern_id="test_pattern_1",
            symbol="XAUUSD",
            pattern_type="BOS_BULLISH",
            direction="BUY",
            detection_timestamp=detection_time,
            detection_timeframe="M5",
            detection_price=2650.0,
            scale="SMALL",
            estimated_horizon_minutes=10,
            entry_price=2650.0,
            stop_loss=2640.0,
            take_profit=2680.0,
            rr_ratio=3.0,
            regime="TRENDING_UP",
            mtf_alignment=0.75,
            htf_bias="BULLISH",
            structure_strength=0.80,
            was_traded=True
        )
        
        assert pattern.outcome == PatternOutcome.PENDING.value, \
            "New pattern should be PENDING"
        
        # Update: price moving favorably but not at TP yet
        outcome = tracker.update_pattern_outcome(
            "test_pattern_1",
            current_price=2670.0,
            current_timestamp=detection_time + timedelta(minutes=5)
        )
        
        assert outcome is None, "Outcome should still be None (PENDING)"
        assert pattern.max_favorable_r > 0, "Max favorable R should be tracked"
        
        # Update: price hits TP!
        outcome = tracker.update_pattern_outcome(
            "test_pattern_1",
            current_price=2680.0,
            current_timestamp=detection_time + timedelta(minutes=8)
        )
        
        assert outcome == PatternOutcome.TP_HIT, \
            f"Pattern should hit TP: got {outcome}"
        
        updated_pattern = tracker.tracked_patterns["test_pattern_1"]
        assert updated_pattern.outcome == PatternOutcome.TP_HIT.value
        assert updated_pattern.actual_r == 3.0, \
            f"Actual R should be 3.0: got {updated_pattern.actual_r}"
        assert updated_pattern.time_to_completion_minutes == 8, \
            "Time to completion should be 8 minutes"
        
        print("✓ Pattern tracking lifecycle works")
    
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_sl_hit_outcome():
    """
    Test: Pattern hits stop loss before target
    """
    from brain.pattern_outcome_tracker import PatternOutcomeTracker, PatternOutcome
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        tracker = PatternOutcomeTracker(storage_path=temp_path)
        
        detection_time = datetime(2026, 8, 11, 10, 0, 0)
        
        tracker.track_pattern(
            pattern_id="test_sl_pattern",
            symbol="XAUUSD",
            pattern_type="BOS_BULLISH",
            direction="BUY",
            detection_timestamp=detection_time,
            detection_timeframe="M5",
            detection_price=2650.0,
            scale="SMALL",
            estimated_horizon_minutes=10,
            entry_price=2650.0,
            stop_loss=2640.0,
            take_profit=2680.0,
            rr_ratio=3.0,
            regime="TRENDING_UP",
            mtf_alignment=0.75,
            htf_bias="BULLISH",
            structure_strength=0.80,
            was_traded=True
        )
        
        # Price reverses and hits SL
        outcome = tracker.update_pattern_outcome(
            "test_sl_pattern",
            current_price=2640.0,
            current_timestamp=detection_time + timedelta(minutes=5)
        )
        
        assert outcome == PatternOutcome.SL_HIT, \
            f"Pattern should hit SL: got {outcome}"
        
        pattern = tracker.tracked_patterns["test_sl_pattern"]
        assert pattern.actual_r == -1.0, \
            f"Actual R should be -1.0 on SL hit: got {pattern.actual_r}"
        
        print("✓ SL hit outcome works")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_stale_pattern_outcome():
    """
    Test: Pattern goes stale (no movement within 2x horizon)
    """
    from brain.pattern_outcome_tracker import PatternOutcomeTracker, PatternOutcome
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        tracker = PatternOutcomeTracker(storage_path=temp_path)
        
        detection_time = datetime(2026, 8, 11, 10, 0, 0)
        
        tracker.track_pattern(
            pattern_id="test_stale",
            symbol="XAUUSD",
            pattern_type="BOS_BULLISH",
            direction="BUY",
            detection_timestamp=detection_time,
            detection_timeframe="M5",
            detection_price=2650.0,
            scale="SMALL",
            estimated_horizon_minutes=10,
            entry_price=2650.0,
            stop_loss=2640.0,
            take_profit=2680.0,
            rr_ratio=3.0,
            regime="RANGING",
            mtf_alignment=0.55,
            htf_bias="NEUTRAL",
            structure_strength=0.65,
            was_traded=False,
            not_traded_reason="LOW_MTF_ALIGNMENT"
        )
        
        # 25 minutes pass (2.5x horizon), price barely moved
        outcome = tracker.update_pattern_outcome(
            "test_stale",
            current_price=2652.0,  # Only +2 points
            current_timestamp=detection_time + timedelta(minutes=25)
        )
        
        assert outcome == PatternOutcome.STALE, \
            f"Pattern should go STALE after 2x horizon: got {outcome}"
        
        pattern = tracker.tracked_patterns["test_stale"]
        assert pattern.outcome == PatternOutcome.STALE.value
        
        print("✓ Stale pattern outcome works")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_historical_edge_calculation():
    """
    Test: Historical edge calculation with multiple patterns
    
    Setup:
    - 10 patterns total
    - 7 winners (TP hit)
    - 3 losers (SL hit)
    - Win rate = 70%
    - Expected R should be positive
    """
    from brain.pattern_outcome_tracker import PatternOutcomeTracker, PatternOutcome
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        tracker = PatternOutcomeTracker(storage_path=temp_path)
        
        detection_time = datetime(2026, 8, 11, 10, 0, 0)
        
        # Create 7 winning patterns
        for i in range(7):
            pattern_id = f"win_pattern_{i}"
            tracker.track_pattern(
                pattern_id=pattern_id,
                symbol="XAUUSD",
                pattern_type="BOS_BULLISH",
                direction="BUY",
                detection_timestamp=detection_time + timedelta(hours=i),
                detection_timeframe="M5",
                detection_price=2650.0,
                scale="SMALL",
                estimated_horizon_minutes=10,
                entry_price=2650.0,
                stop_loss=2640.0,
                take_profit=2680.0,
                rr_ratio=3.0,
                regime="TRENDING_UP",
                mtf_alignment=0.75,
                htf_bias="BULLISH",
                structure_strength=0.80,
                was_traded=True
            )
            
            # Simulate TP hit
            tracker.update_pattern_outcome(
                pattern_id,
                current_price=2680.0,
                current_timestamp=detection_time + timedelta(hours=i, minutes=8)
            )
        
        # Create 3 losing patterns
        for i in range(3):
            pattern_id = f"loss_pattern_{i}"
            tracker.track_pattern(
                pattern_id=pattern_id,
                symbol="XAUUSD",
                pattern_type="BOS_BULLISH",
                direction="BUY",
                detection_timestamp=detection_time + timedelta(hours=7+i),
                detection_timeframe="M5",
                detection_price=2650.0,
                scale="SMALL",
                estimated_horizon_minutes=10,
                entry_price=2650.0,
                stop_loss=2640.0,
                take_profit=2680.0,
                rr_ratio=3.0,
                regime="TRENDING_UP",
                mtf_alignment=0.75,
                htf_bias="BULLISH",
                structure_strength=0.80,
                was_traded=True
            )
            
            # Simulate SL hit
            tracker.update_pattern_outcome(
                pattern_id,
                current_price=2640.0,
                current_timestamp=detection_time + timedelta(hours=7+i, minutes=5)
            )
        
        # Calculate historical edge
        edge = tracker.calculate_historical_edge(
            pattern_type="BOS_BULLISH",
            scale="SMALL",
            min_sample_size=5
        )
        
        assert edge['sufficient_data'] == True, "Should have sufficient data"
        assert edge['sample_size'] == 10, f"Should have 10 patterns: got {edge['sample_size']}"
        assert edge['win_count'] == 7, f"Should have 7 wins: got {edge['win_count']}"
        assert edge['loss_count'] == 3, f"Should have 3 losses: got {edge['loss_count']}"
        assert edge['win_rate'] == 70.0, f"Win rate should be 70%: got {edge['win_rate']}"
        
        # Expected R = (0.7 * 3.0) + (0.3 * -1.0) = 2.1 - 0.3 = 1.8
        expected_r = edge['expected_r']
        assert 1.7 <= expected_r <= 1.9, \
            f"Expected R should be ~1.8: got {expected_r}"
        
        assert edge['tradeable'] == True, "Pattern with positive edge should be tradeable"
        
        print("✓ Historical edge calculation works")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_missed_opportunity_analysis():
    """
    Test: Identify and calculate cost of missed opportunities
    
    Setup:
    - 5 patterns traded (3 win, 2 loss)
    - 3 patterns missed but would have won
    - Calculate opportunity cost
    """
    from brain.pattern_outcome_tracker import PatternOutcomeTracker
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        tracker = PatternOutcomeTracker(storage_path=temp_path)
        
        detection_time = datetime(2026, 8, 11, 10, 0, 0)
        
        # 3 traded winners
        for i in range(3):
            pattern_id = f"traded_win_{i}"
            tracker.track_pattern(
                pattern_id=pattern_id,
                symbol="XAUUSD",
                pattern_type="BOS_BULLISH",
                direction="BUY",
                detection_timestamp=detection_time + timedelta(hours=i),
                detection_timeframe="M5",
                detection_price=2650.0,
                scale="SMALL",
                estimated_horizon_minutes=10,
                entry_price=2650.0,
                stop_loss=2640.0,
                take_profit=2680.0,
                rr_ratio=3.0,
                regime="TRENDING_UP",
                mtf_alignment=0.75,
                htf_bias="BULLISH",
                structure_strength=0.80,
                was_traded=True
            )
            tracker.update_pattern_outcome(pattern_id, 2680.0, detection_time + timedelta(hours=i, minutes=8))
        
        # 3 missed opportunities (would have won)
        for i in range(3):
            pattern_id = f"missed_win_{i}"
            tracker.track_pattern(
                pattern_id=pattern_id,
                symbol="XAUUSD",
                pattern_type="BOS_BULLISH",
                direction="BUY",
                detection_timestamp=detection_time + timedelta(hours=3+i),
                detection_timeframe="M5",
                detection_price=2650.0,
                scale="SMALL",
                estimated_horizon_minutes=10,
                entry_price=2650.0,
                stop_loss=2640.0,
                take_profit=2680.0,
                rr_ratio=3.0,
                regime="TRENDING_UP",
                mtf_alignment=0.75,
                htf_bias="BULLISH",
                structure_strength=0.80,
                was_traded=False,
                not_traded_reason="IN_TRADE"
            )
            tracker.update_pattern_outcome(pattern_id, 2680.0, detection_time + timedelta(hours=3+i, minutes=8))
        
        # Calculate missed opportunity cost
        cost = tracker.calculate_missed_opportunity_cost()
        
        assert cost['total_patterns'] == 6, f"Should have 6 total patterns: got {cost['total_patterns']}"
        assert cost['patterns_traded'] == 3, f"Should have 3 traded: got {cost['patterns_traded']}"
        assert cost['patterns_missed'] == 3, f"Should have 3 missed: got {cost['patterns_missed']}"
        assert cost['profitable_missed'] == 3, \
            f"All 3 missed should be profitable: got {cost['profitable_missed']}"
        
        # 3 patterns * 3.0R each = 9.0R missed
        assert cost['total_r_missed'] == 9.0, \
            f"Total R missed should be 9.0: got {cost['total_r_missed']}"
        
        assert cost['avg_r_per_missed'] == 3.0, \
            f"Avg R per missed should be 3.0: got {cost['avg_r_per_missed']}"
        
        assert 'IN_TRADE' in cost['missed_reasons'], \
            "Should track IN_TRADE as missed reason"
        
        print("✓ Missed opportunity analysis works")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_insufficient_sample_size():
    """
    Test: Edge calculation returns insufficient data warning when sample size too small
    """
    from brain.pattern_outcome_tracker import PatternOutcomeTracker
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        tracker = PatternOutcomeTracker(storage_path=temp_path)
        
        # Only 3 patterns (less than min_sample_size=10)
        detection_time = datetime(2026, 8, 11, 10, 0, 0)
        
        for i in range(3):
            pattern_id = f"pattern_{i}"
            tracker.track_pattern(
                pattern_id=pattern_id,
                symbol="XAUUSD",
                pattern_type="BOS_BULLISH",
                direction="BUY",
                detection_timestamp=detection_time + timedelta(hours=i),
                detection_timeframe="M5",
                detection_price=2650.0,
                scale="SMALL",
                estimated_horizon_minutes=10,
                entry_price=2650.0,
                stop_loss=2640.0,
                take_profit=2680.0,
                rr_ratio=3.0,
                regime="TRENDING_UP",
                mtf_alignment=0.75,
                htf_bias="BULLISH",
                structure_strength=0.80,
                was_traded=True
            )
            tracker.update_pattern_outcome(pattern_id, 2680.0, detection_time + timedelta(hours=i, minutes=8))
        
        # Calculate edge with min_sample_size=10
        edge = tracker.calculate_historical_edge(
            pattern_type="BOS_BULLISH",
            min_sample_size=10
        )
        
        assert edge['sufficient_data'] == False, \
            "Should indicate insufficient data"
        assert edge['sample_size'] == 3, \
            f"Should show actual sample size of 3: got {edge['sample_size']}"
        assert 'message' in edge, \
            "Should include insufficient data message"
        
        print("✓ Insufficient sample size handling works")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE G: PATTERN OUTCOME TRACKER VERIFICATION")
    print("="*70 + "\n")
    
    try:
        test_pattern_tracking_lifecycle()
        test_sl_hit_outcome()
        test_stale_pattern_outcome()
        test_historical_edge_calculation()
        test_missed_opportunity_analysis()
        test_insufficient_sample_size()
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED - Pattern outcome tracking working correctly")
        print("="*70 + "\n")
        
        print("VERIFICATION SUMMARY:")
        print("- Pattern lifecycle tracking (PENDING→TP_HIT/SL_HIT/STALE) ✓")
        print("- TP hit outcome detection ✓")
        print("- SL hit outcome detection ✓")
        print("- Stale pattern detection (2x horizon) ✓")
        print("- Historical edge calculation (win rate, expected R) ✓")
        print("- Missed opportunity analysis ✓")
        print("- Insufficient sample size handling ✓")
        print("\nPhase G: Pattern Outcome Tracking Infrastructure COMPLETE")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
