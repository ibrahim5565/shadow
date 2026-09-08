"""
AEGIS GOLD — Phase F Verification: Pattern Scale Classification

Tests pattern scale classification (SMALL/MEDIUM/LARGE), horizon estimation,
and entry timing validation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_small_pattern_classification():
    """
    Test: M5 pattern with 6 candles, 25-point target classified as SMALL
    
    Expected:
    - Scale = SMALL
    - Horizon = 5-15 minutes
    - Entry window = 2-10 minutes
    - Valid entry on M1/M5 only
    """
    from brain.pattern_scale_classifier import PatternScaleClassifier, PatternScale
    
    classifier = PatternScaleClassifier()
    
    result = classifier.classify(
        detection_timeframe="M5",
        candle_count=6,
        price_range_atr=1.5,
        target_points=25.0,
        invalidation_points=12.0,
        htf_aligned=False,
        time_since_detection=3
    )
    
    assert result.scale == PatternScale.SMALL, \
        f"M5 pattern with 6 candles and 25pt target should be SMALL: got {result.scale}"
    
    assert 5 <= result.estimated_horizon_minutes <= 15, \
        f"SMALL pattern horizon should be 5-15 min: got {result.estimated_horizon_minutes}"
    
    assert 2 <= result.entry_window_minutes <= 10, \
        f"SMALL pattern entry window should be 2-10 min: got {result.entry_window_minutes}"
    
    assert result.entry_timing_valid == True, \
        "Entry at 3 min should be valid for SMALL pattern"
    
    assert result.confidence >= 0.6, \
        f"Classification confidence should be high: got {result.confidence}"
    
    print("✓ SMALL pattern classification works")


def test_medium_pattern_classification():
    """
    Test: M15 pattern with 10 candles, 50-point target classified as MEDIUM
    
    Expected:
    - Scale = MEDIUM
    - Horizon = 15-60 minutes
    - Entry window = 5-30 minutes
    - Valid entry on M1/M5/M15
    """
    from brain.pattern_scale_classifier import PatternScaleClassifier, PatternScale
    
    classifier = PatternScaleClassifier()
    
    result = classifier.classify(
        detection_timeframe="M15",
        candle_count=10,
        price_range_atr=2.5,
        target_points=50.0,
        invalidation_points=22.0,
        htf_aligned=False,
        time_since_detection=12
    )
    
    assert result.scale == PatternScale.MEDIUM, \
        f"M15 pattern with 10 candles and 50pt target should be MEDIUM: got {result.scale}"
    
    assert 15 <= result.estimated_horizon_minutes <= 60, \
        f"MEDIUM pattern horizon should be 15-60 min: got {result.estimated_horizon_minutes}"
    
    assert 5 <= result.entry_window_minutes <= 30, \
        f"MEDIUM pattern entry window should be 5-30 min: got {result.entry_window_minutes}"
    
    assert result.entry_timing_valid == True, \
        "Entry at 12 min should be valid for MEDIUM pattern"
    
    print("✓ MEDIUM pattern classification works")


def test_large_pattern_classification():
    """
    Test: H1 pattern with 15 candles, 120-point target, HTF aligned = LARGE
    
    Expected:
    - Scale = LARGE
    - Horizon = 60-240 minutes
    - Entry window = 15-90 minutes
    - Requires patient entry (>= 10 min delay)
    """
    from brain.pattern_scale_classifier import PatternScaleClassifier, PatternScale
    
    classifier = PatternScaleClassifier()
    
    result = classifier.classify(
        detection_timeframe="H1",
        candle_count=15,
        price_range_atr=4.0,
        target_points=120.0,
        invalidation_points=45.0,
        htf_aligned=True,
        time_since_detection=25
    )
    
    assert result.scale == PatternScale.LARGE, \
        f"H1 pattern with 15 candles, 120pt target, HTF aligned should be LARGE: got {result.scale}"
    
    assert 60 <= result.estimated_horizon_minutes <= 240, \
        f"LARGE pattern horizon should be 60-240 min: got {result.estimated_horizon_minutes}"
    
    assert 15 <= result.entry_window_minutes <= 90, \
        f"LARGE pattern entry window should be 15-90 min: got {result.entry_window_minutes}"
    
    assert result.entry_timing_valid == True, \
        "Entry at 25 min should be valid for LARGE pattern"
    
    assert result.confidence >= 0.7, \
        f"HTF-aligned LARGE pattern should have high confidence: got {result.confidence}"
    
    print("✓ LARGE pattern classification works")


def test_stale_pattern_rejection():
    """
    Test: Pattern detected 20 minutes ago with 10-minute entry window = STALE
    
    Expected:
    - Lifecycle state = STALE
    - Entry timing valid = False
    - Entry window remaining = 0
    """
    from brain.pattern_scale_classifier import PatternScaleClassifier, PatternLifecycleState
    
    classifier = PatternScaleClassifier()
    
    result = classifier.classify(
        detection_timeframe="M5",
        candle_count=8,
        price_range_atr=1.8,
        target_points=30.0,
        invalidation_points=15.0,
        htf_aligned=False,
        time_since_detection=20  # Pattern is 20 min old
    )
    
    # Entry window for SMALL M5 pattern should be ~5-10 min
    assert result.lifecycle_state == PatternLifecycleState.STALE, \
        f"Pattern 20 min old should be STALE: got {result.lifecycle_state}"
    
    assert result.entry_timing_valid == False, \
        "Entry timing should be invalid for STALE pattern"
    
    assert result.entry_window_remaining == 0, \
        f"STALE pattern should have 0 minutes remaining: got {result.entry_window_remaining}"
    
    print("✓ Stale pattern rejection works")


def test_entry_timing_validation_by_scale():
    """
    Test: Entry timeframe validation for different pattern scales
    
    SMALL (M5):  ✅ M1/M5  ❌ M15/M30/H1
    MEDIUM (M15): ✅ M1/M5/M15  ❌ M30/H1
    LARGE (H1):  ❌ M1 (immediate)  ✅ M1 (after setup)  ✅ M5/M15/M30
    """
    from brain.pattern_scale_classifier import (
        PatternScaleClassifier,
        PatternScale,
        validate_entry_for_pattern_scale
    )
    
    classifier = PatternScaleClassifier()
    
    # SMALL pattern (M5, 5 candles, 20pt target)
    small_pattern = classifier.classify(
        detection_timeframe="M5",
        candle_count=5,
        price_range_atr=1.2,
        target_points=20.0,
        invalidation_points=10.0,
        htf_aligned=False,
        time_since_detection=3
    )
    
    # SMALL should allow M1/M5 only
    valid_m1, reason = validate_entry_for_pattern_scale(small_pattern, "M1")
    assert valid_m1 == True, f"SMALL pattern should allow M1 entry: {reason}"
    
    valid_m15, reason = validate_entry_for_pattern_scale(small_pattern, "M15")
    assert valid_m15 == False, f"SMALL pattern should reject M15 entry"
    
    # MEDIUM pattern (M15, 10 candles, 50pt target)
    medium_pattern = classifier.classify(
        detection_timeframe="M15",
        candle_count=10,
        price_range_atr=2.0,
        target_points=50.0,
        invalidation_points=20.0,
        htf_aligned=False,
        time_since_detection=10
    )
    
    # MEDIUM should allow M1/M5/M15
    valid_m5, reason = validate_entry_for_pattern_scale(medium_pattern, "M5")
    assert valid_m5 == True, f"MEDIUM pattern should allow M5 entry: {reason}"
    
    valid_m30, reason = validate_entry_for_pattern_scale(medium_pattern, "M30")
    assert valid_m30 == False, f"MEDIUM pattern should reject M30 entry"
    
    # LARGE pattern (H1, 15 candles, 100pt target)
    # Test immediate entry (should fail)
    large_pattern_immediate = classifier.classify(
        detection_timeframe="H1",
        candle_count=15,
        price_range_atr=3.5,
        target_points=100.0,
        invalidation_points=40.0,
        htf_aligned=True,
        time_since_detection=3  # Too early
    )
    
    valid_m1_early, reason = validate_entry_for_pattern_scale(large_pattern_immediate, "M1")
    assert valid_m1_early == False, \
        f"LARGE pattern should reject immediate M1 entry: {reason}"
    
    # Test after setup formed
    large_pattern_ready = classifier.classify(
        detection_timeframe="H1",
        candle_count=15,
        price_range_atr=3.5,
        target_points=100.0,
        invalidation_points=40.0,
        htf_aligned=True,
        time_since_detection=20  # Entry setup formed
    )
    
    valid_m1_late, reason = validate_entry_for_pattern_scale(large_pattern_ready, "M1")
    assert valid_m1_late == True, \
        f"LARGE pattern should allow M1 entry after setup: {reason}"
    
    print("✓ Entry timing validation by scale works")


def test_horizon_estimation_accuracy():
    """
    Test: Horizon estimation is reasonable for different pattern scales
    
    SMALL M5 6-candle: ~6-12 minutes
    MEDIUM M15 10-candle: ~20-40 minutes
    LARGE H1 15-candle: ~120-180 minutes
    """
    from brain.pattern_scale_classifier import PatternScaleClassifier
    
    classifier = PatternScaleClassifier()
    
    # SMALL: M5 with 6 candles = 30 min base * 1.2 = 36 min? No, should be clamped to 5-15
    small = classifier.classify(
        detection_timeframe="M5",
        candle_count=6,
        price_range_atr=1.5,
        target_points=25.0,
        invalidation_points=12.0,
        htf_aligned=False,
        time_since_detection=0
    )
    
    # M5 * 6 candles * 1.2 multiplier = 36 min, but SMALL is clamped to max 15 min
    assert 5 <= small.estimated_horizon_minutes <= 15, \
        f"SMALL horizon should be 5-15 min: got {small.estimated_horizon_minutes}"
    
    # MEDIUM: M15 with 10 candles = 150 min base * 1.5 = 225? No, clamped to 15-60
    medium = classifier.classify(
        detection_timeframe="M15",
        candle_count=10,
        price_range_atr=2.5,
        target_points=50.0,
        invalidation_points=22.0,
        htf_aligned=False,
        time_since_detection=0
    )
    
    assert 15 <= medium.estimated_horizon_minutes <= 60, \
        f"MEDIUM horizon should be 15-60 min: got {medium.estimated_horizon_minutes}"
    
    # LARGE: H1 with 15 candles = 900 min base * 2.0 = 1800? No, clamped to 60-240
    large = classifier.classify(
        detection_timeframe="H1",
        candle_count=15,
        price_range_atr=4.0,
        target_points=120.0,
        invalidation_points=45.0,
        htf_aligned=True,
        time_since_detection=0
    )
    
    assert 60 <= large.estimated_horizon_minutes <= 240, \
        f"LARGE horizon should be 60-240 min: got {large.estimated_horizon_minutes}"
    
    print("✓ Horizon estimation accuracy works")


def test_lifecycle_state_transitions():
    """
    Test: Pattern lifecycle states transition correctly
    
    t=0:  FORMING
    t=1:  TRIGGERED (if timing not yet valid) or VALID_ENTRY (if valid)
    t>window: STALE
    """
    from brain.pattern_scale_classifier import (
        PatternScaleClassifier,
        PatternLifecycleState
    )
    
    classifier = PatternScaleClassifier()
    
    # t=0: FORMING
    forming = classifier.classify(
        detection_timeframe="M5",
        candle_count=6,
        price_range_atr=1.5,
        target_points=25.0,
        invalidation_points=12.0,
        htf_aligned=False,
        time_since_detection=0
    )
    
    assert forming.lifecycle_state == PatternLifecycleState.FORMING, \
        f"t=0 should be FORMING: got {forming.lifecycle_state}"
    
    # t=2: VALID_ENTRY (within entry window, timing valid)
    valid_entry = classifier.classify(
        detection_timeframe="M5",
        candle_count=6,
        price_range_atr=1.5,
        target_points=25.0,
        invalidation_points=12.0,
        htf_aligned=False,
        time_since_detection=2
    )
    
    assert valid_entry.lifecycle_state == PatternLifecycleState.VALID_ENTRY, \
        f"t=2 with valid timing should be VALID_ENTRY: got {valid_entry.lifecycle_state}"
    
    # t=20: STALE (entry window expired)
    stale = classifier.classify(
        detection_timeframe="M5",
        candle_count=6,
        price_range_atr=1.5,
        target_points=25.0,
        invalidation_points=12.0,
        htf_aligned=False,
        time_since_detection=20
    )
    
    assert stale.lifecycle_state == PatternLifecycleState.STALE, \
        f"t=20 (expired window) should be STALE: got {stale.lifecycle_state}"
    
    print("✓ Lifecycle state transitions work")


def test_htf_alignment_increases_confidence():
    """
    Test: HTF alignment increases classification confidence
    
    Same pattern:
    - Without HTF alignment: confidence ~0.6
    - With HTF alignment: confidence ~0.75+
    """
    from brain.pattern_scale_classifier import PatternScaleClassifier
    
    classifier = PatternScaleClassifier()
    
    # Without HTF alignment
    no_htf = classifier.classify(
        detection_timeframe="M15",
        candle_count=10,
        price_range_atr=2.5,
        target_points=50.0,
        invalidation_points=22.0,
        htf_aligned=False,
        time_since_detection=5
    )
    
    # With HTF alignment
    with_htf = classifier.classify(
        detection_timeframe="M15",
        candle_count=10,
        price_range_atr=2.5,
        target_points=50.0,
        invalidation_points=22.0,
        htf_aligned=True,
        time_since_detection=5
    )
    
    assert with_htf.confidence > no_htf.confidence, \
        f"HTF alignment should increase confidence: {no_htf.confidence:.2f} → {with_htf.confidence:.2f}"
    
    assert with_htf.confidence >= 0.7, \
        f"HTF-aligned pattern should have confidence >= 0.7: got {with_htf.confidence}"
    
    print("✓ HTF alignment increases confidence")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE F: PATTERN SCALE CLASSIFICATION VERIFICATION")
    print("="*70 + "\n")
    
    try:
        test_small_pattern_classification()
        test_medium_pattern_classification()
        test_large_pattern_classification()
        test_stale_pattern_rejection()
        test_entry_timing_validation_by_scale()
        test_horizon_estimation_accuracy()
        test_lifecycle_state_transitions()
        test_htf_alignment_increases_confidence()
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED - Pattern scale classification working correctly")
        print("="*70 + "\n")
        
        print("VERIFICATION SUMMARY:")
        print("- SMALL pattern classification (5-15 min horizon) ✓")
        print("- MEDIUM pattern classification (15-60 min horizon) ✓")
        print("- LARGE pattern classification (1-4 hour horizon) ✓")
        print("- Stale pattern rejection (expired entry window) ✓")
        print("- Entry timeframe validation by scale ✓")
        print("- Horizon estimation accuracy ✓")
        print("- Lifecycle state transitions ✓")
        print("- HTF alignment increases confidence ✓")
        print("\nPhase F: Pattern Scale Classification COMPLETE")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
