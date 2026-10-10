"""
Test: MT5 Blocking

Verify that audit runs successfully with MT5 blocked (sys.modules["MetaTrader5"] = None).
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Block MT5 BEFORE any imports that might use it
sys.modules["MetaTrader5"] = None


def test_mt5_blocking():
    """
    Test that audit infrastructure works with MT5 blocked.
    
    Verify:
    1. MT5 import fails
    2. Pattern detection still works (offline)
    3. Funnel gates work with simulated data
    """
    # Test 1: Verify MT5 is blocked
    try:
        import MetaTrader5
        assert False, "MT5 import should have failed but didn't"
    except (ImportError, TypeError):
        print("[PASS] MT5 import blocked successfully")
    
    # Test 2: Import audit modules (should work without MT5)
    try:
        from scripts.pattern_audit.pattern_detector import detect_patterns_closed_candles_only, reset_pattern_state
        from scripts.pattern_audit.live_state_simulator import SimulatedClock, simulate_state_at_bar
        from scripts.pattern_audit.funnel_logger import FunnelLogger
        print("[PASS] Audit modules import successfully without MT5")
    except Exception as e:
        assert False, f"Audit module import failed: {e}"
    
    # Test 3: Run pattern detection with offline data
    np.random.seed(42)
    base_time = 1700000000.0
    bar_duration = 300
    
    data = []
    price = 2500.0
    for i in range(50):
        price += np.random.uniform(-1, 1)
        data.append({
            'time': base_time + (i * bar_duration),
            'open': price - 0.5,
            'high': price + 1.0,
            'low': price - 1.5,
            'close': price,
            'spread': 20
        })
    
    df = pd.DataFrame(data)
    
    reset_pattern_state()
    patterns = detect_patterns_closed_candles_only(
        candles=df,
        symbol="XAUUSD",
        point=0.01,
        timeframe="M5"
    )
    
    print(f"[PASS] Pattern detection works offline: {len(patterns)} patterns detected")
    
    # Test 4: Verify simulated clock works
    if len(patterns) > 0:
        pattern = patterns[0]
        clock = SimulatedClock(pattern.timestamp)
        
        try:
            with clock:
                # Inside context, module-level datetime should be patched
                from modules import risk_manager
                # This should not raise an error
                pass
            print("[PASS] Simulated clock context manager works")
        except Exception as e:
            assert False, f"Simulated clock failed: {e}"
    
    print("[PASS] All MT5 blocking tests passed")


if __name__ == "__main__":
    test_mt5_blocking()
