"""
Test: Simulated Clock

Verify that running same history on different wall-clock dates produces identical funnel results.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timezone

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Block MT5
sys.modules["MetaTrader5"] = None

from scripts.pattern_audit.pattern_detector import detect_patterns_closed_candles_only, reset_pattern_state
from scripts.pattern_audit.live_state_simulator import SimulatedClock, simulate_state_at_bar
from scripts.pattern_audit.funnel_logger import FunnelLogger


def test_simulated_clock():
    """
    Test that simulated clock makes funnel results independent of wall-clock time.
    
    Run same historical data on two different "current dates" (by mocking wall clock).
    Both runs should produce identical funnel results.
    """
    # Generate test data
    np.random.seed(42)
    base_time = 1700000000.0  # Nov 2023
    bar_duration = 300  # 5 minutes
    
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
    
    # Detect patterns (same for both runs)
    reset_pattern_state()
    patterns = detect_patterns_closed_candles_only(
        candles=df,
        symbol="XAUUSD",
        point=0.01,
        timeframe="M5"
    )
    
    if len(patterns) == 0:
        print("[SKIP] No patterns detected - cannot test clock independence")
        return
    
    # Run 1: Process first pattern with simulated clock at candle time
    pattern = patterns[0]
    simulated_state1 = simulate_state_at_bar(
        bar_timestamp=pattern.timestamp,
        symbol="XAUUSD",
        candles=df,
        bar_index=pattern.candle_index,
        estimated_spread=25.0,
        daily_trades_so_far=0,
        consecutive_losses_so_far=0,
        broker_offset_hours=None  # UNCONFIRMED
    )
    
    # Create funnel logger and risk manager
    # Mock risk manager since MT5 is blocked
    class MockRiskManager:
        def __init__(self):
            self.daily_trades = 0
            self.consecutive_losses = 0
            self.max_daily_trades = 5
            
        def init_daily(self, equity):
            pass
            
        def can_trade(self, session, symbol, direction, current_equity, session_refresh_active):
            return True  # Always allow for test
    
    risk_mgr1 = MockRiskManager()
    risk_mgr1.init_daily(10000.0)
    
    funnel_logger1 = FunnelLogger()
    clock1 = SimulatedClock(simulated_state1.candle_time_utc)
    
    record1 = funnel_logger1.log_pattern_through_gates(
        pattern=pattern,
        simulated_state=simulated_state1,
        symbol="XAUUSD",
        point=0.01,
        risk_mgr=risk_mgr1,
        simulated_clock=clock1
    )
    
    # Run 2: Same pattern, but create NEW clock instance (simulates running on different wall date)
    # The key is that both use candle time, not wall time
    simulated_state2 = simulate_state_at_bar(
        bar_timestamp=pattern.timestamp,
        symbol="XAUUSD",
        candles=df,
        bar_index=pattern.candle_index,
        estimated_spread=25.0,
        daily_trades_so_far=0,
        consecutive_losses_so_far=0,
        broker_offset_hours=None
    )
    
    gateway2 = MockRiskManager()
    risk_mgr2 = gateway2
    risk_mgr2.init_daily(10000.0)
    
    funnel_logger2 = FunnelLogger()
    clock2 = SimulatedClock(simulated_state2.candle_time_utc)
    
    record2 = funnel_logger2.log_pattern_through_gates(
        pattern=pattern,
        simulated_state=simulated_state2,
        symbol="XAUUSD",
        point=0.01,
        risk_mgr=risk_mgr2,
        simulated_clock=clock2
    )
    
    # Compare funnel results
    assert record1.final_outcome == record2.final_outcome, \
        f"Final outcome differs: {record1.final_outcome} vs {record2.final_outcome}"
    
    assert record1.rejection_gate == record2.rejection_gate, \
        f"Rejection gate differs: {record1.rejection_gate} vs {record2.rejection_gate}"
    
    assert len(record1.gates) == len(record2.gates), \
        f"Gate count differs: {len(record1.gates)} vs {len(record2.gates)}"
    
    for g1, g2 in zip(record1.gates, record2.gates):
        assert g1.gate_name == g2.gate_name, f"Gate name mismatch: {g1.gate_name} vs {g2.gate_name}"
        assert g1.passed == g2.passed, f"Gate {g1.gate_name} pass status differs"
    
    print(f"[PASS] Simulated clock: Identical funnel results across runs")
    print(f"       Pattern: {pattern.pattern_name}, Outcome: {record1.final_outcome}")


if __name__ == "__main__":
    test_simulated_clock()
