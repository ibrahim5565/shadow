"""Regression tests: DEMO mode must never bypass risk pauses."""
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.risk_manager import RiskManager


class TestDemoRiskGates(unittest.TestCase):
    def setUp(self):
        self.gateway = MagicMock()
        self.gateway.get_account_info.return_value = {
            "trade_mode": "DEMO",
            "equity": 10000.0,
        }
        self.risk = RiskManager(self.gateway)

    def test_demo_account_does_not_bypass_consecutive_loss_pause(self):
        import config.settings as cfg
        original = cfg.MAX_CONSECUTIVE_LOSSES
        try:
            cfg.MAX_CONSECUTIVE_LOSSES = 2
            self.risk.on_trade_close(-10.0)
            self.risk.on_trade_close(-10.0)
            self.assertTrue(self.risk.is_paused)
        finally:
            cfg.MAX_CONSECUTIVE_LOSSES = original

    def test_can_trade_respects_pause_state(self):
        self.risk.is_paused = True
        self.assertFalse(self.risk.can_trade(session="LONDON", current_equity=10000.0))

    def test_can_trade_respects_manual_pause(self):
        self.risk.manual_pause = True
        self.assertFalse(self.risk.can_trade(session="LONDON", current_equity=10000.0))


if __name__ == "__main__":
    unittest.main()
