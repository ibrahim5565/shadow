"""
AEGIS GOLD — Phase E Verification: Multi-Timeframe Hierarchy

Tests that HTF bias properly filters LTF patterns and alignment scoring works correctly.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_strong_htf_bias_blocks_opposite_ltf_pattern():
    """
    Test: Strong H4 bullish bias blocks bearish M5 pattern
    
    Scenario:
    - H4: STRONG_BULLISH (ADX=35, clear HH/HL)
    - H1: BULLISH (ADX=28)
    - M5: BEARISH pattern detected
    
    Expected: WAIT (HTF wins, don't trade against strong H4 bias)
    Old Behavior: Would trade M5 pattern ignoring H4
    """
    from brain.mtf_context import MTFContextAggregator, TimeframeState, TimeframeBias
    
    # Mock strong bullish HTF
    h4 = TimeframeState(
        timeframe="H4",
        bias=TimeframeBias.STRONG_BULLISH,
        trend_strength=0.85,
        structure="HH_HL",
        ema_aligned=True,
        adx=35.0,
        rsi=62.0,
        recent_high=2700.0,
        recent_low=2680.0,
        reliability=0.90
    )
    
    h1 = TimeframeState(
        timeframe="H1",
        bias=TimeframeBias.BULLISH,
        trend_strength=0.70,
        structure="HH_HL",
        ema_aligned=True,
        adx=28.0,
        rsi=58.0,
        recent_high=2698.0,
        recent_low=2685.0,
        reliability=0.80
    )
    
    # Mock bearish M5 (counter-trend)
    m5 = TimeframeState(
        timeframe="M5",
        bias=TimeframeBias.BEARISH,
        trend_strength=0.60,
        structure="LH_LL",
        ema_aligned=True,
        adx=24.0,
        rsi=42.0,
        recent_high=2695.0,
        recent_low=2688.0,
        reliability=0.70
    )
    
    m1 = TimeframeState(
        timeframe="M1",
        bias=TimeframeBias.BEARISH,
        trend_strength=0.55,
        structure="LH_LL",
        ema_aligned=True,
        adx=22.0,
        rsi=38.0,
        recent_high=2693.0,
        recent_low=2690.0,
        reliability=0.65
    )
    
    aggregator = MTFContextAggregator()
    
    # Manually construct context (simulating analyze() result)
    htf_bias, htf_strength = aggregator._determine_htf_bias(h4, h1)
    buy_compat, sell_compat = aggregator._check_compatibility(htf_bias, htf_strength, [h4, h1, m5, m1])
    
    # Strong bullish HTF should block SELL
    assert htf_bias == "BULLISH", f"HTF bias should be BULLISH: got {htf_bias}"
    assert htf_strength > 0.7, f"HTF strength should be strong: got {htf_strength}"
    assert sell_compat == False, "SELL should be blocked by strong bullish HTF bias"
    assert buy_compat == True, "BUY should be allowed with bullish HTF"
    
    print("✓ Strong HTF bias blocks opposite LTF pattern")


def test_mtf_alignment_scoring():
    """
    Test: Alignment score correctly calculates timeframe agreement
    
    Scenario 1: All 6 timeframes bullish → alignment = 1.0
    Scenario 2: 4 bullish, 2 neutral → alignment = 0.67
    Scenario 3: 3 bullish, 3 bearish → alignment = 0.5 (no consensus)
    """
    from brain.mtf_context import MTFContextAggregator, TimeframeState, TimeframeBias
    
    aggregator = MTFContextAggregator()
    
    # Scenario 1: Perfect alignment
    all_bullish = [
        TimeframeState("H4", TimeframeBias.BULLISH, 0.8, "HH_HL", True, 30, 60, 2700, 2680, 0.9),
        TimeframeState("H1", TimeframeBias.BULLISH, 0.75, "HH_HL", True, 28, 58, 2698, 2682, 0.85),
        TimeframeState("M30", TimeframeBias.BULLISH, 0.70, "HH_HL", True, 26, 56, 2696, 2684, 0.80),
        TimeframeState("M15", TimeframeBias.BULLISH, 0.65, "HH_HL", True, 24, 54, 2694, 2686, 0.75),
        TimeframeState("M5", TimeframeBias.BULLISH, 0.60, "HH_HL", True, 22, 52, 2692, 2688, 0.70),
        TimeframeState("M1", TimeframeBias.BULLISH, 0.55, "HH_HL", True, 20, 50, 2691, 2689, 0.65),
    ]
    
    alignment1, bull1, bear1, neutral1 = aggregator._calculate_alignment(all_bullish)
    assert alignment1 == 1.0, f"Perfect alignment should be 1.0: got {alignment1}"
    assert bull1 == 6, f"All 6 should be bullish: got {bull1}"
    
    # Scenario 2: 4 bullish, 2 neutral
    mixed = [
        TimeframeState("H4", TimeframeBias.BULLISH, 0.8, "HH_HL", True, 30, 60, 2700, 2680, 0.9),
        TimeframeState("H1", TimeframeBias.BULLISH, 0.75, "HH_HL", True, 28, 58, 2698, 2682, 0.85),
        TimeframeState("M30", TimeframeBias.NEUTRAL, 0.30, "RANGE", False, 18, 50, 2696, 2684, 0.50),
        TimeframeState("M15", TimeframeBias.BULLISH, 0.65, "HH_HL", True, 24, 54, 2694, 2686, 0.75),
        TimeframeState("M5", TimeframeBias.BULLISH, 0.60, "HH_HL", True, 22, 52, 2692, 2688, 0.70),
        TimeframeState("M1", TimeframeBias.NEUTRAL, 0.25, "RANGE", False, 16, 49, 2691, 2689, 0.45),
    ]
    
    alignment2, bull2, bear2, neutral2 = aggregator._calculate_alignment(mixed)
    assert alignment2 >= 0.65 and alignment2 <= 0.70, f"4/6 agreement should be ~0.67: got {alignment2}"
    assert bull2 == 4 and neutral2 == 2, f"Should have 4 bull, 2 neutral: got {bull2}, {neutral2}"
    
    # Scenario 3: No consensus (3 vs 3)
    no_consensus = [
        TimeframeState("H4", TimeframeBias.BULLISH, 0.7, "HH_HL", True, 28, 58, 2700, 2680, 0.85),
        TimeframeState("H1", TimeframeBias.BULLISH, 0.65, "HH_HL", True, 26, 56, 2698, 2682, 0.80),
        TimeframeState("M30", TimeframeBias.BULLISH, 0.60, "HH_HL", True, 24, 54, 2696, 2684, 0.75),
        TimeframeState("M15", TimeframeBias.BEARISH, 0.55, "LH_LL", True, 22, 46, 2694, 2686, 0.70),
        TimeframeState("M5", TimeframeBias.BEARISH, 0.50, "LH_LL", True, 20, 44, 2692, 2688, 0.65),
        TimeframeState("M1", TimeframeBias.BEARISH, 0.45, "LH_LL", True, 18, 42, 2691, 2689, 0.60),
    ]
    
    alignment3, bull3, bear3, neutral3 = aggregator._calculate_alignment(no_consensus)
    assert alignment3 == 0.5, f"3/6 vs 3/6 should be 0.5: got {alignment3}"
    assert bull3 == 3 and bear3 == 3, f"Should have 3 bull, 3 bear: got {bull3}, {bear3}"
    
    print("✓ MTF alignment scoring works correctly")


def test_htf_divergence_detection():
    """
    Test: System detects dangerous HTF/LTF divergences
    
    Scenario: H4 bearish but M5 bullish (divergence)
    
    Expected: Divergence flag TRUE, recommendation = WAIT
    """
    from brain.mtf_context import MTFContextAggregator, TimeframeState, TimeframeBias
    
    aggregator = MTFContextAggregator()
    
    # H4 bearish
    h4 = TimeframeState(
        timeframe="H4",
        bias=TimeframeBias.STRONG_BEARISH,
        trend_strength=0.80,
        structure="LH_LL",
        ema_aligned=True,
        adx=32.0,
        rsi=38.0,
        recent_high=2700.0,
        recent_low=2680.0,
        reliability=0.85
    )
    
    h1 = TimeframeState(
        timeframe="H1",
        bias=TimeframeBias.BEARISH,
        trend_strength=0.70,
        structure="LH_LL",
        ema_aligned=True,
        adx=28.0,
        rsi=42.0,
        recent_high=2695.0,
        recent_low=2682.0,
        reliability=0.80
    )
    
    # M5 bullish (divergence!)
    m5 = TimeframeState(
        timeframe="M5",
        bias=TimeframeBias.BULLISH,
        trend_strength=0.65,
        structure="HH_HL",
        ema_aligned=True,
        adx=26.0,
        rsi=58.0,
        recent_high=2693.0,
        recent_low=2688.0,
        reliability=0.75
    )
    
    m1 = TimeframeState(
        timeframe="M1",
        bias=TimeframeBias.BULLISH,
        trend_strength=0.60,
        structure="HH_HL",
        ema_aligned=True,
        adx=24.0,
        rsi=54.0,
        recent_high=2691.0,
        recent_low=2689.0,
        reliability=0.70
    )
    
    divergence, details = aggregator._detect_divergence(h4, h1, m5, m1)
    
    assert divergence == True, "Divergence should be detected when H4 bearish but M5 bullish"
    assert "H4 bearish but M5 bullish" in details or "H1 bearish but M5 bullish" in details, \
        f"Divergence details should mention H4/M5 conflict: {details}"
    
    print("✓ HTF divergence detection works")


def test_pattern_quality_mtf_gate():
    """
    Test: PatternQuality now includes MTF alignment gate
    
    Scenario: Excellent pattern but low MTF alignment (< 0.5)
    
    Expected: NOT TRADEABLE (fails Gate 9: MTF alignment)
    """
    from brain.pattern_quality import PatternQuality
    
    # Excellent pattern fundamentals
    pq = PatternQuality(
        structure_strength=0.85,
        pattern_type="BULLISH_BOS_OB",
        historical_edge=2.5,
        pattern_sample_size=50,
        mtf_alignment=0.40,  # LOW - only 40% alignment
        htf_bias="neutral",
        engine_consensus=0.75,
        engines_agreeing=5,
        engines_total=7,
        entry_quality=0.70,
        distance_from_origin=8.0,
        expected_move_pts=50.0,
        consumed_move_pts=10.0,
        remaining_move_pct=0.80,
        target_validity=0.85,
        target_distance_pts=40.0,
        invalidation_distance_pts=10.0,
        rr_ratio=3.0,
        expected_value_usd=45.0,
        win_probability=0.65,
        avg_win_r=2.5,
        avg_loss_r=-1.0,
        regime_compatible=True,
        regime_type="TRENDING_UP",
        vetoes=[]
    )
    
    # Should fail despite excellent fundamentals
    assert not pq.is_tradeable(), \
        "Pattern with MTF alignment < 0.5 should NOT be tradeable (Gate 9 failure)"
    
    # Now test with good alignment
    pq_good = PatternQuality(
        structure_strength=0.85,
        pattern_type="BULLISH_BOS_OB",
        historical_edge=2.5,
        pattern_sample_size=50,
        mtf_alignment=0.75,  # GOOD - 75% alignment
        htf_bias="bullish",
        engine_consensus=0.75,
        engines_agreeing=5,
        engines_total=7,
        entry_quality=0.70,
        distance_from_origin=8.0,
        expected_move_pts=50.0,
        consumed_move_pts=10.0,
        remaining_move_pct=0.80,
        target_validity=0.85,
        target_distance_pts=40.0,
        invalidation_distance_pts=10.0,
        rr_ratio=3.0,
        expected_value_usd=45.0,
        win_probability=0.65,
        avg_win_r=2.5,
        avg_loss_r=-1.0,
        regime_compatible=True,
        regime_type="TRENDING_UP",
        vetoes=[]
    )
    
    # Should pass all gates
    assert pq_good.is_tradeable(), \
        "Pattern with MTF alignment >= 0.5 and good fundamentals should be tradeable"
    
    print("✓ Pattern quality MTF gate works")


def test_moderate_htf_allows_strong_ltf_counter_pattern():
    """
    Test: Moderate HTF bias allows strong counter-LTF pattern
    
    Scenario:
    - H4: BULLISH (moderate, strength=0.5)
    - H1: BULLISH (moderate, strength=0.45)
    - M5: STRONG_BEARISH (strength=0.75)
    - M1: STRONG_BEARISH (strength=0.70)
    
    Expected: SELL allowed (LTF strong enough to override moderate HTF)
    """
    from brain.mtf_context import MTFContextAggregator, TimeframeState, TimeframeBias
    
    aggregator = MTFContextAggregator()
    
    h4 = TimeframeState(
        timeframe="H4",
        bias=TimeframeBias.BULLISH,
        trend_strength=0.50,  # Moderate
        structure="HH_HL",
        ema_aligned=True,
        adx=22.0,
        rsi=54.0,
        recent_high=2700.0,
        recent_low=2680.0,
        reliability=0.65
    )
    
    h1 = TimeframeState(
        timeframe="H1",
        bias=TimeframeBias.BULLISH,
        trend_strength=0.45,  # Moderate
        structure="HH_HL",
        ema_aligned=True,
        adx=20.0,
        rsi=52.0,
        recent_high=2698.0,
        recent_low=2682.0,
        reliability=0.60
    )
    
    m5 = TimeframeState(
        timeframe="M5",
        bias=TimeframeBias.STRONG_BEARISH,
        trend_strength=0.75,  # Strong
        structure="LH_LL",
        ema_aligned=True,
        adx=32.0,
        rsi=38.0,
        recent_high=2695.0,
        recent_low=2686.0,
        reliability=0.85
    )
    
    m1 = TimeframeState(
        timeframe="M1",
        bias=TimeframeBias.STRONG_BEARISH,
        trend_strength=0.70,  # Strong
        structure="LH_LL",
        ema_aligned=True,
        adx=28.0,
        rsi=36.0,
        recent_high=2693.0,
        recent_low=2688.0,
        reliability=0.80
    )
    
    htf_bias, htf_strength = aggregator._determine_htf_bias(h4, h1)
    buy_compat, sell_compat = aggregator._check_compatibility(htf_bias, htf_strength, [h4, h1, m5, m1])
    
    # Moderate HTF should allow strong counter-LTF
    assert htf_bias == "BULLISH", f"HTF bias should be BULLISH: got {htf_bias}"
    assert htf_strength < 0.6, f"HTF strength should be moderate: got {htf_strength}"
    assert sell_compat == True, "SELL should be allowed when M5/M1 both strong bearish despite moderate bullish HTF"
    
    print("✓ Moderate HTF allows strong counter-LTF pattern")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE E: MULTI-TIMEFRAME HIERARCHY VERIFICATION")
    print("="*70 + "\n")
    
    try:
        test_strong_htf_bias_blocks_opposite_ltf_pattern()
        test_mtf_alignment_scoring()
        test_htf_divergence_detection()
        test_pattern_quality_mtf_gate()
        test_moderate_htf_allows_strong_ltf_counter_pattern()
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED - MTF hierarchy working correctly")
        print("="*70 + "\n")
        
        print("VERIFICATION SUMMARY:")
        print("- Strong HTF bias blocks opposite LTF patterns ✓")
        print("- MTF alignment scoring calculates correctly ✓")
        print("- HTF/LTF divergence detection works ✓")
        print("- Pattern quality includes MTF gate (Gate 9) ✓")
        print("- Moderate HTF allows strong counter-LTF ✓")
        print("\nPhase E: Multi-Timeframe Hierarchy COMPLETE")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
