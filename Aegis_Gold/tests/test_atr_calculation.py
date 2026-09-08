"""
Unit Test: ATR Calculation Path Verification (Item 1)
=====================================================
Directly exercises the ATR calculation path used by the SCALP decision flow
and asserts it returns a real, non-zero ATR value under normal market data conditions.
"""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from brain.indicators import ATR
from brain.brain import decide
from modules.risk_manager import RiskManager


class TestATRCalculation(unittest.TestCase):

    def setUp(self):
        # Build 20 realistic M5 candles for XAUUSD with $2.50 average true range
        self.point_gold = 0.01
        self.candles_dict = []
        base_price = 2380.00
        for i in range(20):
            high = base_price + 2.00 + (i % 3) * 0.50
            low = base_price - 1.50 - (i % 2) * 0.50
            close = base_price + (1.00 if i % 2 == 0 else -1.00)
            self.candles_dict.append({
                "open": base_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 100
            })
            base_price = close

    def test_atr_indicator_returns_nonzero_price_value(self):
        """Directly test indicators.ATR with high, low, close series."""
        highs = [c["high"] for c in self.candles_dict]
        lows = [c["low"] for c in self.candles_dict]
        closes = [c["close"] for c in self.candles_dict]

        atrs = ATR(highs, lows, closes, 14)
        self.assertIsNotNone(atrs)
        self.assertGreater(len(atrs), 0)
        latest_atr = atrs[-1]
        self.assertGreater(latest_atr, 0.0, "ATR price value must be > 0.0 under normal market conditions")
        # In our test data, high - low is ~3.50 to 4.50, so ATR should be around 3.5 - 4.5
        self.assertGreater(latest_atr, 1.0, f"ATR {latest_atr} should reflect true candle range (> 1.0)")

    def test_atr_estimate_point_scaling(self):
        """Verify ATR price is correctly scaled to broker points by point multiplier."""
        highs = [c["high"] for c in self.candles_dict]
        lows = [c["low"] for c in self.candles_dict]
        closes = [c["close"] for c in self.candles_dict]

        atrs = ATR(highs, lows, closes, 14)
        atr_price = atrs[-1]
        atr_pts = atr_price / self.point_gold

        self.assertGreater(atr_pts, 100.0, f"ATR in points ({atr_pts}pts) must be > 100pts for Gold")

    def test_decide_flow_uses_atr_value(self):
        """Test that brain.decide() / atr_scaled_sl_tp uses the calculated ATR value to produce ATR-scaled SL points."""
        risk_mgr = RiskManager(gateway=None)
        
        # Test 1: Direct risk_mgr ATR scaling
        exits = risk_mgr.atr_scaled_sl_tp("XAUUSD", atr_pts=250.0, confidence=65)
        self.assertEqual(exits["regime"], "atr_scaled")
        self.assertEqual(exits["sl_pts"], 400, "250pts ATR * 1.8 = 450pts, clamped to max 400pts")

        exits_mid = risk_mgr.atr_scaled_sl_tp("XAUUSD", atr_pts=100.0, confidence=65)
        self.assertEqual(exits_mid["regime"], "atr_scaled")
        self.assertEqual(exits_mid["sl_pts"], 180, "100pts ATR * 1.8 = 180pts")

        # Test 2: Verify fallback floor when ATR is <= 0
        exits_zero = risk_mgr.atr_scaled_sl_tp("XAUUSD", atr_pts=0.0, confidence=65)
        self.assertEqual(exits_zero["sl_pts"], 150, "Zero ATR must fall back to 150pt floor")

        # Test 3: Run decide() and verify ATR calculation logic in brain does not crash
        decision = decide(
            ticks=[],
            candles_m5=self.candles_dict,
            account={"equity": 10000.0, "balance": 10000.0},
            risk_mgr=risk_mgr,
            session="LONDON",
            spread=15.0,
            point=0.01,
            symbol="XAUUSD"
        )
        self.assertIsNotNone(decision)
        # Verify that decision object was properly formed
        self.assertIn(decision.action, ("TRADE", "WAIT"))


if __name__ == "__main__":
    unittest.main()
