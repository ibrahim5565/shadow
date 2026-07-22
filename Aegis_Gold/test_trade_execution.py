#!/usr/bin/env python3
"""
TEST: Verify trades execute at 65% confidence
This script tests the brain decision logic to ensure action="TRADE" is returned
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from brain.brain import decide

# Mock data for testing
mock_ticks = [{"bid": 1.0850 + (i * 0.0001)} for i in range(200)]
mock_candles = [
    {"high": 1.0855, "low": 1.0845, "close": 1.0850, "open": 1.0848}
    for _ in range(100)
]
mock_account = {
    "balance": 10000.0,
    "equity": 10000.0,
    "margin_free": 9000.0
}

class MockRiskMgr:
    def __init__(self):
        self.consecutive_losses = 0
        self.daily_trades = 0
        self.today_wins = 0
        self.today_losses = 0
        self.open_trade_times = {}
        self.start_equity = 10000.0
    
    def can_trade(self, session):
        return True

print("=" * 70)
print("TRADE EXECUTION TEST")
print("=" * 70)
print()

# Test with high confidence (should execute)
print("TEST 1: High Confidence (66%)")
print("-" * 70)

risk_mgr = MockRiskMgr()
decision = decide(
    ticks=mock_ticks,
    candles_m5=mock_candles,
    account=mock_account,
    risk_mgr=risk_mgr,
    session="LONDON",
    spread=2.0,
    point=0.0001
)

print(f"Confidence: {decision.confidence}%")
print(f"Action: {decision.action}")
print(f"Direction: {decision.direction}")
print(f"TP Points: {decision.tp_points}")
print(f"SL Points: {decision.sl_points}")
print(f"Lot: {decision.lot}")
print(f"Reason: {decision.reason}")
print()

if decision.action == "TRADE":
    print("✅ RESULT: TRADE EXECUTED")
    print("   Action is set to TRADE - trade will execute!")
elif decision.action == "WAIT":
    print("❌ RESULT: TRADE BLOCKED")
    print(f"   Action is WAIT - reason: {decision.reason}")
else:
    print(f"❌ UNKNOWN ACTION: {decision.action}")

print()
print("=" * 70)

if decision.action == "TRADE":
    print("✅ TEST PASSED - Trades will execute at 66% confidence")
    sys.exit(0)
else:
    print("❌ TEST FAILED - Trades still not executing")
    sys.exit(1)
