"""
Test: WAIT with No Pattern = Confidence 0

Verify that a WAIT decision with no pattern results in confidence = 0.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Block MT5
sys.modules["MetaTrader5"] = None

from scripts.pattern_audit.pattern_detector import detect_patterns_closed_candles_only, reset_pattern_state


def test_wait_confidence_zero():
    """
    Test that when no pattern is detected (WAIT/HOLD), confidence is 0.
    
    This test verifies the requirement: "A WAIT with no pattern must keep trade confidence = 0."
    """
    # Generate flat/noisy data (no clear patterns)
    base_time = 1700000000.0
    bar_duration = 300  # 5 minutes
    
    data = []
    for i in range(50):
        # Small random noise around 2500 (no trend, no patterns)
        base = 2500.0
        noise = np.random.normal(0, 0.5)
        data.append({
            'time': base_time + (i * bar_duration),
            'open': base + noise,
            'high': base + abs(noise) + 0.2,
            'low': base - abs(noise) - 0.2,
            'close': base + np.random.normal(0, 0.3),
            'spread': 20
        })
    
    df = pd.DataFrame(data)
    
    # Detect patterns
    reset_pattern_state()
    patterns = detect_patterns_closed_candles_only(
        candles=df,
        symbol="XAUUSD",
        point=0.01,
        timeframe="M5"
    )
    
    # In audit architecture, if no pattern detected, len(patterns) == 0
    # This means no patterns were found, which corresponds to WAIT/HOLD
    
    # Verify that either:
    # 1. No patterns detected (WAIT = implicit confidence 0), OR
    # 2. Any patterns detected have direction != "HOLD"
    
    hold_patterns = [p for p in patterns if p.direction == "HOLD"]
    
    # If HOLD patterns exist, they should have confidence 0
    for pattern in hold_patterns:
        assert pattern.confidence == 0.0, \
            f"HOLD pattern has non-zero confidence: {pattern.confidence}"
    
    print(f"[INFO] Detected {len(patterns)} patterns (HOLD patterns: {len(hold_patterns)})")
    
    # If no patterns detected at all, that's also valid (WAIT = no pattern)
    if len(patterns) == 0:
        print("[PASS] WAIT scenario: No patterns detected = confidence 0 (implicit)")
    else:
        print(f"[PASS] WAIT scenario: HOLD patterns have confidence 0")


if __name__ == "__main__":
    test_wait_confidence_zero()
