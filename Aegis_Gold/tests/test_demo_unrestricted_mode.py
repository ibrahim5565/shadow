"""Regression tests: DEMO mode must never bypass risk pauses."""
import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import modules.risk_manager as risk_manager_module
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

    def test_daily_loss_gate_fails_closed_without_starting_equity(self):
        self.assertTrue(self.risk.is_daily_loss_limit_reached(10000.0))

    def test_daily_loss_gate_fails_closed_when_account_equity_is_unavailable(self):
        self.risk.start_equity = 10000.0
        self.gateway.get_account_info.return_value = None
        self.assertTrue(self.risk.is_daily_loss_limit_reached(None))

    def test_manual_resume_cannot_remove_persisted_daily_loss_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lockfile = os.path.join(temp_dir, "lockfile.json")
            with open(lockfile, "w", encoding="utf-8") as f:
                json.dump({"locked_at": time.time(), "reason": "daily_loss_limit"}, f)

            with patch.object(risk_manager_module, "LOCKFILE", lockfile):
                self.risk.stop_today = True
                self.assertFalse(self.risk.manual_resume())
                self.assertTrue(os.path.exists(lockfile))
                self.assertTrue(self.risk.stop_today)

    def test_daily_loss_trigger_remains_locked_after_manual_resume(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lockfile = os.path.join(temp_dir, "lockfile.json")
            with patch.object(risk_manager_module, "LOCKFILE", lockfile):
                self.risk.start_equity = 10000.0
                self.assertTrue(self.risk.is_daily_loss_limit_reached(9970.0))
                self.assertTrue(self.risk.daily_loss_lock_active)
                self.assertFalse(self.risk.manual_resume())
                self.assertTrue(os.path.exists(lockfile))
                self.assertTrue(self.risk.stop_today)
                self.assertFalse(self.risk.force_unlock())
                self.assertTrue(os.path.exists(lockfile))


if __name__ == "__main__":
    unittest.main()
