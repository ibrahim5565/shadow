"""
Test: BUY/SELL Symmetry

Verify that both BUY and SELL patterns are detected over sufficient history.
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


def test_buy_sell_symmetry():
    """
    Test that both BUY and SELL patterns are detected.
    
    Generate data with clear uptrend and downtrend sections.
    """
    base_time = 1700000000.0
    bar_duration = 300  # 5 minutes
    
    data = []
    
    # Create uptrend (should trigger BUY patterns)
    price = 2500.0
    for i in range(50):
        price += np.random.uniform(0.5, 2.0)  # Trending up
        data.append({
            'time': base_time + (i * bar_duration),
            'open': price - 1.0,
            'high': price + 1.0,
            'low': price - 2.0,
            'close': price,
            'spread': 20
        })
    
    # Create downtrend (should trigger SELL patterns)
    for i in range(50, 100):
        price -= np.random.uniform(0.5, 2.0)  # Trending down
        data.append({
            'time': base_time + (i * bar_duration),
            'open': price + 1.0,
            'high': price + 2.0,
            'low': price - 1.0,
            'close': price,
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
    
    # Count BUY and SELL
    buy_count = sum(1 for p in patterns if p.direction == "BUY")
    sell_count = sum(1 for p in patterns if p.direction == "SELL")
    
    print(f"[INFO] Detected {buy_count} BUY patterns, {sell_count} SELL patterns")
    
    # Assert both directions detected
    assert buy_count > 0, "No BUY patterns detected (symmetry failure)"
    assert sell_count > 0, "No SELL patterns detected (symmetry failure)"
    
    # Check that ratio is not extremely skewed (within 10:1)
    ratio = max(buy_count, sell_count) / max(min(buy_count, sell_count), 1)
    assert ratio < 10, f"BUY/SELL ratio too skewed: {ratio:.2f}"
    
    print(f"[PASS] BUY/SELL symmetry: Both directions detected, ratio {ratio:.2f}")


if __name__ == "__main__":
    test_buy_sell_symmetry()
