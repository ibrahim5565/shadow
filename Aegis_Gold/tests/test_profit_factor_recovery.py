import unittest
from unittest.mock import MagicMock
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.risk_manager import RiskManager

class MockPosition:
    def __init__(self, ticket=1001, symbol="XAUUSD", pos_type=0, price_open=2000.0, price_current=2000.0, sl=1998.0, tp=2005.0, volume=0.10):
        self.ticket = ticket
        self.symbol = symbol
        self.type = pos_type  # 0 for BUY, 1 for SELL
        self.price_open = price_open
        self.price_current = price_current
        self.sl = sl
        self.tp = tp
        self.volume = volume
        self.magic = 999999
        self.pattern_tier = "scalp"

class TestProfitFactorRecovery(unittest.TestCase):
    def setUp(self):
        self.gateway = MagicMock()
        self.gateway.symbols_data = {
            "XAUUSD": {"point": 0.01, "digits": 2, "lot_step": 0.01},
            "EURUSD": {"point": 0.00001, "digits": 5, "lot_step": 0.01}
        }
        self.gateway.modify_sl.return_value = True
        self.gateway.close_partial_position.return_value = MagicMock(retcode=0)
        self.risk_mgr = RiskManager(self.gateway)

    def test_breakeven_requires_1r_minimum(self):
        """Verify break-even does NOT trigger if profit is below 1.0R (initial SL distance)."""
        pos = MockPosition(symbol="XAUUSD", pos_type=0, price_open=2000.0, sl=1998.0, tp=2005.0, volume=0.10)
        # Initial SL distance = (2000 - 1998)/0.01 = 200 points (2.00 Gold move)
        # Set price_current to 2001.0 (100 points gain = 0.5R)
        pos.price_current = 2001.0
        
        self.risk_mgr.check_breakeven(pos)
        
        # Verify SL modification was NOT called because profit < 1.0R
        self.gateway.modify_sl.assert_not_called()
        self.gateway.close_partial_position.assert_not_called()

    def test_breakeven_and_partial_tp_at_1r(self):
        """Verify break-even and partial TP trigger when profit reaches 1.0R (200 points)."""
        pos = MockPosition(symbol="XAUUSD", pos_type=0, price_open=2000.0, sl=1998.0, tp=2005.0, volume=0.10)
        # Set price_current to 2002.0 (200 points gain = 1.0R)
        pos.price_current = 2002.0
        
        self.risk_mgr.check_breakeven(pos)
        
        # Verify partial TP closed 50% (0.05 lots out of 0.10)
        self.gateway.close_partial_position.assert_called_once_with(pos, 0.05)
        # Verify SL was moved to breakeven + buffer (2000.10)
        self.gateway.modify_sl.assert_called_once_with(1001, "XAUUSD", 2000.10)

    def test_trailing_stop_activates_at_1_2r(self):
        """Verify trailing stop activates after profit reaches 1.2R."""
        pos = MockPosition(symbol="XAUUSD", pos_type=0, price_open=2000.0, sl=1998.0, tp=2005.0, volume=0.05)
        # Initial SL distance = 200 points (2.00 Gold)
        # 1.2R trigger = 240 points gain (price = 2002.40)
        pos.price_current = 2002.50
        
        self.risk_mgr.check_trailing_stop(pos)
        
        # 0.8R trailing distance = 160 points behind current price (2002.50 - 1.60 = 2000.90)
        self.gateway.modify_sl.assert_called_once_with(1001, "XAUUSD", 2000.90)

    def test_atr_scaled_sl_tp_guarantees_2r_minimum(self):
        """Verify atr_scaled_sl_tp enforces minimum 2.0R TP:SL ratio floor."""
        res = self.risk_mgr.atr_scaled_sl_tp("XAUUSD", atr_pts=200.0, confidence=60)
        sl = res["sl_pts"]
        tp = res["tp_pts"]
        rr = res["rr_ratio"]
        
        self.assertGreaterEqual(rr, 2.0, f"R:R ratio {rr} must be >= 2.0R")
        self.assertGreaterEqual(tp, int(sl * 2.0), f"TP ({tp}) must be >= 2.0 * SL ({sl})")

if __name__ == "__main__":
    unittest.main()
