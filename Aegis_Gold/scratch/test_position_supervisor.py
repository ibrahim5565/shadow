import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.position_supervisor import PositionSupervisor
from config import settings as cfg

# Mock objects for testing
class MockPosition:
    def __init__(self, ticket, symbol, type_, volume, price_open, price_current, profit, sl=0.0, tp=0.0):
        self.ticket = ticket
        self.symbol = symbol
        self.type = type_  # 0 = BUY, 1 = SELL
        self.volume = volume
        self.price_open = price_open
        self.price_current = price_current
        self.profit = profit
        self.sl = sl
        self.tp = tp

class MockGateway:
    def __init__(self):
        self.symbols_data = {
            "XAUUSD": {"point": 0.01, "digits": 2},
            "EURUSD": {"point": 0.00001, "digits": 5}
        }
    def close_position(self, pos):
        print(f"[Gateway] Closing position #{pos.ticket}")
        return True
    def modify_sl(self, ticket, symbol, sl):
        print(f"[Gateway] Modifying SL for #{ticket} to {sl}")
        return True
    def modify_tp(self, ticket, symbol, tp):
        print(f"[Gateway] Modifying TP for #{ticket} to {tp}")
        return True

class MockRiskMgr:
    def __init__(self):
        self.start_equity = 10000.0
    def check_breakeven(self, pos):
        pass
    def check_trailing_stop(self, pos):
        pass
    def check_dynamic_tp(self, pos, gateway):
        pass
    def calculate_current_drawdown(self, equity):
        return ((self.start_equity - equity) / self.start_equity) * 100.0 if equity < self.start_equity else 0.0

def run_tests():
    print("=" * 60)
    print("RUNNING AEGIS V10.0 POSITION SUPERVISOR TESTS")
    print("=" * 60)

    gateway = MockGateway()
    risk_mgr = MockRiskMgr()
    supervisor = PositionSupervisor(gateway, risk_mgr)

    # 1. Test Volatility limits mapping
    print("\nTEST 1: Volatility limits mapping")
    print("-" * 40)
    limits = {
        "COMPRESSED": supervisor.get_dynamic_trade_limit("COMPRESSED"),
        "NORMAL": supervisor.get_dynamic_trade_limit("NORMAL"),
        "VOLATILE": supervisor.get_dynamic_trade_limit("VOLATILE"),
        "EMERGENCY": supervisor.get_dynamic_trade_limit("NORMAL", is_emergency=True)
    }
    print(f"Compressed Volatility Limit : {limits['COMPRESSED']} (Expected: 2)")
    print(f"Normal Volatility Limit     : {limits['NORMAL']} (Expected: 3)")
    print(f"High Volatility Limit       : {limits['VOLATILE']} (Expected: 4)")
    print(f"Emergency Limit             : {limits['EMERGENCY']} (Expected: 1)")
    
    assert limits["COMPRESSED"] == 2
    assert limits["NORMAL"] == 3
    assert limits["VOLATILE"] == 4
    assert limits["EMERGENCY"] == 1
    print("[OK] TEST 1 PASSED")

    # 2. Test Signal Scoring
    print("\nTEST 2: Signal Scoring & Ranking")
    print("-" * 40)
    score1 = supervisor.score_signal("EURUSD", "BUY", confidence=75, trend_score=80, volatility_score=40, spread=10, momentum_score=60)
    score2 = supervisor.score_signal("XAUUSD", "BUY", confidence=70, trend_score=80, volatility_score=50, spread=25, momentum_score=70)
    print(f"EURUSD Buy Score: {score1}")
    print(f"XAUUSD Buy Score (Gold boost applied): {score2}")
    
    assert score1 > 0
    assert score2 > 0
    print("[OK] TEST 2 PASSED")

    # 3. Test Exit Evaluator: Trend Reversal
    print("\nTEST 3: Reversal Exit Evaluator")
    print("-" * 40)
    pos_buy = MockPosition(ticket=1001, symbol="EURUSD", type_=0, volume=0.1, price_open=1.0850, price_current=1.0830, profit=-2.0)
    
    # Evaluate with opposite strong trend (bearish)
    trend_res = {"trend": "TRENDING_DOWN", "trend_score": 60}
    vol_res = {"volatility_state": "NORMAL", "volatility_ratio": 1.0}
    mom_res = {"momentum_score": 50, "tps": 2.0}
    
    eval_res = supervisor.evaluate_position(
        pos_buy, ticks=[{} for _ in range(100)], 
        candles_m1=[{'close': 1.0850} for _ in range(30)], 
        candles_m5=[{'close': 1.0850} for _ in range(100)], 
        current_spread=10, trend_res=trend_res, volatility_res=vol_res, momentum_res=mom_res,
        session="LONDON"
    )
    print(f"Evaluation Action: {eval_res['action']}")
    print(f"Reason: {eval_res['reason']}")
    
    assert eval_res["action"] == "CLOSE"
    assert "Trend reversal" in eval_res["reason"]
    print("[OK] TEST 3 PASSED")

    # 4. Test Exit Evaluator: Spread Spike
    print("\nTEST 4: Spread Spike Exit Evaluator")
    print("-" * 40)
    eval_res_spread = supervisor.evaluate_position(
        pos_buy, ticks=[{} for _ in range(100)], 
        candles_m1=[{'close': 1.0850} for _ in range(30)], 
        candles_m5=[{'close': 1.0850} for _ in range(100)], 
        current_spread=95, trend_res={"trend": "BULLISH", "trend_score": 60}, 
        volatility_res=vol_res, momentum_res=mom_res,
        session="LONDON"
    )
    print(f"Evaluation Action (Spread=95 vs max 8): {eval_res_spread['action']}")
    print(f"Reason: {eval_res_spread['reason']}")
    
    assert eval_res_spread["action"] == "CLOSE"
    assert "Spread spike" in eval_res_spread["reason"]
    print("[OK] TEST 4 PASSED")

    # 5. Test Dry run compilation of main imports
    print("\nTEST 5: Core Imports and Compilation check")
    print("-" * 40)
    try:
        import core.main
        print("[OK] core/main.py compiled & imported successfully")
    except Exception as e:
        print(f"[FAIL] core/main.py failed to import: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
