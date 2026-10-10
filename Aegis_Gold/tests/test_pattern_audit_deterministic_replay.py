"""
Test: Deterministic Replay

Verify that two runs on identical data produce identical signals.
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


def test_deterministic_replay():
    """
    Test that two runs with state reset produce identical results.
    """
    # Generate test data
    np.random.seed(42)  # Fixed seed for reproducibility
    base_time = 1700000000.0
    bar_duration = 300  # 5 minutes
    
    data = []
    price = 2500.0
    for i in range(100):
        # Trending price
        price += np.random.uniform(-1, 1.5)
        data.append({
            'time': base_time + (i * bar_duration),
            'open': price - 0.5,
            'high': price + 1.0,
            'low': price - 1.5,
            'close': price,
            'spread': 20
        })
    
    df = pd.DataFrame(data)
    
    # Run 1
    reset_pattern_state()
    np.random.seed(42)  # Reset RNG if pattern detection uses randomness
    patterns_run1 = detect_patterns_closed_candles_only(
        candles=df,
        symbol="XAUUSD",
        point=0.01,
        timeframe="M5"
    )
    
    # Run 2 (reset state between runs)
    reset_pattern_state()
    np.random.seed(42)  # Reset RNG again
    patterns_run2 = detect_patterns_closed_candles_only(
        candles=df,
        symbol="XAUUSD",
        point=0.01,
        timeframe="M5"
    )
    
    # Compare results
    assert len(patterns_run1) == len(patterns_run2), \
        f"Pattern count differs: {len(patterns_run1)} vs {len(patterns_run2)}"
    
    for p1, p2 in zip(patterns_run1, patterns_run2):
        assert p1.timestamp == p2.timestamp, f"Timestamp mismatch: {p1.timestamp} vs {p2.timestamp}"
        assert p1.direction == p2.direction, f"Direction mismatch at {p1.timestamp}"
        assert p1.pattern_name == p2.pattern_name, f"Pattern name mismatch at {p1.timestamp}"
        assert p1.candle_index == p2.candle_index, f"Candle index mismatch at {p1.timestamp}"
        assert abs(p1.confidence - p2.confidence) < 0.01, f"Confidence mismatch at {p1.timestamp}"
        assert abs(p1.entry_price - p2.entry_price) < 0.01, f"Entry price mismatch at {p1.timestamp}"
    
    print(f"[PASS] Deterministic replay: {len(patterns_run1)} patterns identical across runs")


if __name__ == "__main__":
    test_deterministic_replay()
