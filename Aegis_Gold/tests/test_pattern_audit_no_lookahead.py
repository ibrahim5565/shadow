"""
Test: No Look-Ahead Bias

Verify that changing bars AFTER time t does not change the signal AT time t.
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


def test_no_lookahead_bias():
    """
    Test that pattern detection at bar t doesn't change when future bars (t+1, t+2...) change.
    """
    # Generate base data (100 bars)
    np.random.seed(42)  # Deterministic synthetic candles.
    base_time = 1700000000.0
    bar_duration = 300  # 5 minutes
    
    base_data = []
    for i in range(100):
        base_data.append({
            'time': base_time + (i * bar_duration),
            'open': 2500.0 + np.random.normal(0, 1),
            'high': 2502.0 + np.random.normal(0, 1),
            'low': 2498.0 + np.random.normal(0, 1),
            'close': 2500.0 + np.random.normal(0, 1),
            'spread': 20
        })
    
    df_base = pd.DataFrame(base_data)
    
    # Detect patterns on first 50 bars
    reset_pattern_state()
    df_first_50 = df_base.iloc[:50].copy()
    patterns_first_50 = detect_patterns_closed_candles_only(
        candles=df_first_50,
        symbol="XAUUSD",
        point=0.01,
        timeframe="M5"
    )
    
    # Now detect patterns on ALL 100 bars
    reset_pattern_state()
    patterns_all_100 = detect_patterns_closed_candles_only(
        candles=df_base,
        symbol="XAUUSD",
        point=0.01,
        timeframe="M5"
    )
    
    # Extract patterns from first 50 bars in the full run
    patterns_all_100_first_50 = [
        p for p in patterns_all_100 if p.candle_index < 50
    ]
    
    # Compare: patterns at bars 0-49 should be IDENTICAL
    assert len(patterns_first_50) == len(patterns_all_100_first_50), \
        f"Pattern count mismatch: {len(patterns_first_50)} vs {len(patterns_all_100_first_50)}"
    
    # Compare pattern details (timestamps, directions, names)
    for p1, p2 in zip(patterns_first_50, patterns_all_100_first_50):
        assert p1.timestamp == p2.timestamp, f"Timestamp mismatch at bar {p1.candle_index}"
        assert p1.direction == p2.direction, f"Direction mismatch at bar {p1.candle_index}"
        assert p1.pattern_name == p2.pattern_name, f"Pattern name mismatch at bar {p1.candle_index}"
        assert abs(p1.confidence - p2.confidence) < 0.01, f"Confidence mismatch at bar {p1.candle_index}"
    
    print("[PASS] No look-ahead bias: Future bars do not affect past signals")


if __name__ == "__main__":
    test_no_lookahead_bias()
