import unittest
from unittest.mock import MagicMock
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.risk_manager import RiskManager
from config.quant_x_config import QX

class MockPosition:
    def __init__(self, ticket=2001, symbol="XAUUSD", pos_type=0, price_open=2000.0, price_current=2000.0, sl=1998.0, tp=2005.0, volume=0.10):
        self.ticket = ticket
        self.symbol = symbol
        self.type = pos_type
        self.price_open = price_open
        self.price_current = price_current
        self.sl = sl
        self.tp = tp
        self.volume = volume
        self.pattern_tier = "scalp"

class TestDemoUnrestrictedMode(unittest.TestCase):
    def setUp(self):
        self.gateway = MagicMock()
        self.gateway.symbols_data = {
            "XAUUSD": {"point": 0.01, "digits": 2, "lot_step": 0.01},
            "EURUSD": {"point": 0.00001, "digits": 5, "lot_step": 0.01}
        }
        self.gateway.get_account_info.return_value = {"trade_mode": "DEMO", "equity": 10000.0}
        self.gateway.modify_sl.return_value = True
        self.gateway.close_partial_position.return_value = MagicMock(retcode=0)
        self.risk_mgr = RiskManager(self.gateway)

    def test_live_account_safety_rejection(self):
        """Verify that LIVE account status strictly rejects demo_unrestricted_mode."""
        import config.settings as cfg
        old_max = cfg.MAX_CONSECUTIVE_LOSSES
        cfg.MAX_CONSECUTIVE_LOSSES = 3
        try:
            self.gateway.get_account_info.return_value = {"trade_mode": "REAL", "equity": 10000.0}
            
            # Trigger consecutive losses up to MAX_CONSECUTIVE_LOSSES
            for _ in range(3):
                self.risk_mgr.on_trade_close(pnl_points=-100.0)
                
            # On a REAL account, system MUST activate auto-pause (is_paused = True)
            self.assertTrue(self.risk_mgr.is_paused, "LIVE account MUST trigger auto-pause on loss limit")
        finally:
            cfg.MAX_CONSECUTIVE_LOSSES = old_max

    def test_demo_account_unrestricted_consecutive_loss_bypass(self):
        """Verify DEMO account bypasses auto-pause and logs informational alert."""
        import config.settings as cfg
        old_max = cfg.MAX_CONSECUTIVE_LOSSES
        cfg.MAX_CONSECUTIVE_LOSSES = 3
        try:
            self.gateway.get_account_info.return_value = {"trade_mode": "DEMO", "equity": 10000.0}
            
            # Trigger consecutive losses up to MAX_CONSECUTIVE_LOSSES
            for _ in range(3):
                self.risk_mgr.on_trade_close(pnl_points=-100.0)
                
            # On DEMO account with demo_unrestricted_mode, auto-pause is BYPASSED
            self.assertFalse(self.risk_mgr.is_paused, "DEMO account must bypass auto-pause in unrestricted mode")
            self.assertEqual(self.risk_mgr.consecutive_losses, 3)
        finally:
            cfg.MAX_CONSECUTIVE_LOSSES = old_max

    def test_phase_1_exit_layer_remains_intact(self):
        """Verify Phase 1 exit layer (1.0R BE & partial TP) remains active in unrestricted mode."""
        pos = MockPosition(symbol="XAUUSD", pos_type=0, price_open=2000.0, sl=1998.0, tp=2005.0, volume=0.10)
        pos.price_current = 2002.0  # +200 points gain = 1.0R
        
        self.risk_mgr.check_breakeven(pos)
        
        # Verify 50% partial TP executed and SL moved to BE + buffer
        self.gateway.close_partial_position.assert_called_once_with(pos, 0.05)
        self.gateway.modify_sl.assert_called_once_with(2001, "XAUUSD", 2000.10)

if __name__ == "__main__":
    unittest.main()
