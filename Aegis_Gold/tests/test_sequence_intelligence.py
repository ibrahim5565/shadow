"""
AEGIS GOLD — Phase H Verification: Pattern Sequence Intelligence

Tests multi-step pattern sequence detection, template matching, and quality scoring.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_institutional_entry_sequence_detection():
    """
    Test: Detect "Institutional Entry" sequence (H1 BOS → M15 OB → M5 Sweep)
    
    Expected:
    - 3-step sequence detected
    - Quality score ≥ 0.7
    - Confidence boost = 0.15
    """
    from brain.pattern_sequence_engine import PatternSequenceEngine
    from dataclasses import dataclass
    
    # Mock pattern class
    @dataclass
    class MockPattern:
        pattern_type: str
        detection_timeframe: str
        scale: str
        detection_timestamp: datetime
        structure_strength: float = 0.75
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        engine = PatternSequenceEngine(storage_path=temp_path)
        
        base_time = datetime(2026, 8, 11, 10, 0, 0)
        
        # Create institutional entry sequence
        patterns = [
            MockPattern("BOS_BULLISH", "H1", "LARGE", base_time),
            MockPattern("ORDER_BLOCK_BULLISH", "M15", "MEDIUM", base_time + timedelta(minutes=25)),
            MockPattern("LIQUIDITY_SWEEP_BULLISH", "M5", "SMALL", base_time + timedelta(minutes=35)),
        ]
        
        # Detect sequences
        detected = engine.detect_sequences(patterns, max_lookback_minutes=120)
        
        assert len(detected) > 0, "Should detect at least one sequence"
        
        # Find institutional entry sequence
        inst_seq = next((s for s in detected if s.template.name == "Institutional Entry"), None)
        assert inst_seq is not None, "Should detect Institutional Entry sequence"
        
        assert len(inst_seq.patterns) == 3, \
            f"Should have 3 patterns in sequence: got {len(inst_seq.patterns)}"
        
        assert inst_seq.is_complete, "Sequence should be complete (all 3 steps)"
        
        assert inst_seq.quality_score >= 0.7, \
            f"Quality score should be ≥ 0.7: got {inst_seq.quality_score}"
        
        assert inst_seq.template.confidence_boost == 0.15, \
            "Institutional Entry should have 0.15 confidence boost"
        
        print("✓ Institutional Entry sequence detection works")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_trend_continuation_sequence():
    """
    Test: Detect "Trend Continuation" sequence (H1 BOS → M30 Pullback → M15 BOS)
    """
    from brain.pattern_sequence_engine import PatternSequenceEngine
    from dataclasses import dataclass
    
    @dataclass
    class MockPattern:
        pattern_type: str
        detection_timeframe: str
        scale: str
        detection_timestamp: datetime
        structure_strength: float = 0.75
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        engine = PatternSequenceEngine(storage_path=temp_path)
        
        base_time = datetime(2026, 8, 11, 10, 0, 0)
        
        patterns = [
            MockPattern("BOS_BULLISH", "H1", "LARGE", base_time),
            MockPattern("ORDER_BLOCK_BULLISH", "M30", "MEDIUM", base_time + timedelta(minutes=40)),
            MockPattern("BOS_BULLISH", "M15", "MEDIUM", base_time + timedelta(minutes=55)),
        ]
        
        detected = engine.detect_sequences(patterns)
        
        trend_seq = next((s for s in detected if s.template.name == "Trend Continuation"), None)
        assert trend_seq is not None, "Should detect Trend Continuation sequence"
        
        assert trend_seq.template.historical_win_rate == 0.71, \
            "Trend Continuation has 71% historical win rate"
        
        print("✓ Trend Continuation sequence detection works")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_incomplete_sequence_detection():
    """
    Test: Partial sequence detected with next expected step identified
    
    Scenario: Only first 2 steps of 3-step sequence present
    Expected: Sequence detected as partial (meets min_steps_required), next_expected_step set
    """
    from brain.pattern_sequence_engine import PatternSequenceEngine
    from dataclasses import dataclass
    
    @dataclass
    class MockPattern:
        pattern_type: str
        detection_timeframe: str
        scale: str
        detection_timestamp: datetime
        structure_strength: float = 0.75
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        engine = PatternSequenceEngine(storage_path=temp_path)
        
        base_time = datetime(2026, 8, 11, 10, 0, 0)
        
        # Only 2 of 3 steps - but Trend Continuation has min_steps_required=2
        patterns = [
            MockPattern("BOS_BULLISH", "H1", "LARGE", base_time),
            MockPattern("ORDER_BLOCK_BULLISH", "M30", "MEDIUM", base_time + timedelta(minutes=40)),
            # Missing: BOS_BULLISH on M15 (3rd step)
        ]
        
        detected = engine.detect_sequences(patterns)
        
        # Should detect Trend Continuation (min 2 steps)
        trend_seq = next((s for s in detected if s.template.name == "Trend Continuation"), None)
        
        assert trend_seq is not None, \
            "Should detect Trend Continuation with 2 steps (min_steps_required=2)"
        
        assert trend_seq.is_complete == False, \
            "Sequence should be incomplete (2/3 steps)"
        
        assert trend_seq.next_expected_step is not None, \
            "Should identify next expected step"
        
        assert "BOS" in str(trend_seq.next_expected_step.pattern_types), \
            f"Next step should include BOS: got {trend_seq.next_expected_step.pattern_types}"
        
        print("✓ Incomplete sequence detection works")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_timing_validation():
    """
    Test: Sequence rejected if timing between steps is wrong
    
    Scenario: Patterns correct but delays too long
    Expected: Sequence not detected or low quality score
    """
    from brain.pattern_sequence_engine import PatternSequenceEngine
    from dataclasses import dataclass
    
    @dataclass
    class MockPattern:
        pattern_type: str
        detection_timeframe: str
        scale: str
        detection_timestamp: datetime
        structure_strength: float = 0.75
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        engine = PatternSequenceEngine(storage_path=temp_path)
        
        base_time = datetime(2026, 8, 11, 10, 0, 0)
        
        # Correct patterns but delays WAY too long
        patterns = [
            MockPattern("BOS_BULLISH", "H1", "LARGE", base_time),
            MockPattern("ORDER_BLOCK_BULLISH", "M15", "MEDIUM", base_time + timedelta(hours=3)),  # 3 hours! (max is 60 min)
            MockPattern("LIQUIDITY_SWEEP_BULLISH", "M5", "SMALL", base_time + timedelta(hours=4)),
        ]
        
        detected = engine.detect_sequences(patterns)
        
        # Either no detection or very low quality
        inst_seq = next((s for s in detected if s.template.name == "Institutional Entry"), None)
        
        if inst_seq:
            # If detected, quality should be low due to bad timing
            assert inst_seq.quality_score < 0.5, \
                f"Quality should be low with bad timing: got {inst_seq.quality_score}"
        
        print("✓ Timing validation works")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_template_persistence():
    """
    Test: Templates save to disk and load correctly
    """
    from brain.pattern_sequence_engine import PatternSequenceEngine
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        # Create engine (creates default templates)
        engine1 = PatternSequenceEngine(storage_path=temp_path)
        initial_count = len(engine1.templates)
        
        assert initial_count >= 3, f"Should have at least 3 default templates: got {initial_count}"
        
        # Verify file created
        assert os.path.exists(temp_path), "Template file should be created"
        
        # Create new engine (should load from disk)
        engine2 = PatternSequenceEngine(storage_path=temp_path)
        loaded_count = len(engine2.templates)
        
        assert loaded_count == initial_count, \
            f"Loaded templates count should match: {loaded_count} vs {initial_count}"
        
        # Verify template details preserved
        inst_template = next(
            (t for t in engine2.templates if t.name == "Institutional Entry"),
            None
        )
        assert inst_template is not None, "Should load Institutional Entry template"
        assert inst_template.historical_win_rate == 0.74, \
            "Win rate should be preserved"
        assert len(inst_template.steps) == 3, \
            "Should have 3 steps"
        
        print("✓ Template persistence works")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_failed_breakout_trap_sequence():
    """
    Test: Detect "Failed Breakout Trap" (reversal sequence)
    
    M15 BOS one direction → M5 BOS opposite direction = trap
    """
    from brain.pattern_sequence_engine import PatternSequenceEngine
    from dataclasses import dataclass
    
    @dataclass
    class MockPattern:
        pattern_type: str
        detection_timeframe: str
        scale: str
        detection_timestamp: datetime
        structure_strength: float = 0.75
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        engine = PatternSequenceEngine(storage_path=temp_path)
        
        base_time = datetime(2026, 8, 11, 10, 0, 0)
        
        # Bullish breakout that fails → Bearish reversal
        patterns = [
            MockPattern("BOS_BULLISH", "M15", "MEDIUM", base_time),
            MockPattern("BOS_BEARISH", "M5", "SMALL", base_time + timedelta(minutes=12)),
        ]
        
        detected = engine.detect_sequences(patterns)
        
        trap_seq = next((s for s in detected if s.template.name == "Failed Breakout Trap"), None)
        assert trap_seq is not None, "Should detect Failed Breakout Trap"
        
        assert trap_seq.template.confidence_boost == 0.10, \
            "Failed trap should have 0.10 boost"
        
        print("✓ Failed Breakout Trap detection works")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE H: PATTERN SEQUENCE INTELLIGENCE VERIFICATION")
    print("="*70 + "\n")
    
    try:
        test_institutional_entry_sequence_detection()
        test_trend_continuation_sequence()
        test_incomplete_sequence_detection()
        test_timing_validation()
        test_template_persistence()
        test_failed_breakout_trap_sequence()
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED - Pattern sequence intelligence working correctly")
        print("="*70 + "\n")
        
        print("VERIFICATION SUMMARY:")
        print("- Institutional Entry sequence (3-step) ✓")
        print("- Trend Continuation sequence ✓")
        print("- Incomplete sequence with next step prediction ✓")
        print("- Timing validation between steps ✓")
        print("- Template persistence (save/load) ✓")
        print("- Failed Breakout Trap (reversal) ✓")
        print("\nPhase H: Pattern Sequence Intelligence COMPLETE")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
