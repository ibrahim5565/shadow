"""Unit tests for fail-closed DEMO account verification."""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from quant_ai.execution.demo_guard import DemoGuard


class TestDemoGuardFailClosed(unittest.TestCase):
    def setUp(self):
        self.guard = DemoGuard(
            trading_mode="DEMO",
            allow_live=False,
            demo_trade_mode=0,
        )

    def test_verified_demo_account_passes(self):
        result = self.guard.check({
            "server": "Broker-Demo",
            "login": 123456,
            "trade_mode": 0,
        })
        self.assertTrue(result["ok"])

    def test_live_account_is_rejected(self):
        result = self.guard.check({
            "server": "Broker-Live",
            "login": 123456,
            "trade_mode": 2,
        })
        self.assertFalse(result["ok"])

    def test_missing_account_is_rejected(self):
        self.assertFalse(self.guard.check(None)["ok"])

    def test_missing_trade_mode_is_rejected(self):
        result = self.guard.check({"server": "Broker-Demo", "login": 123456})
        self.assertFalse(result["ok"])

    def test_missing_identity_is_rejected(self):
        result = self.guard.check({"server": "", "login": 0, "trade_mode": 0})
        self.assertFalse(result["ok"])

    def test_live_override_configuration_is_rejected(self):
        guard = DemoGuard(trading_mode="DEMO", allow_live=True, demo_trade_mode=0)
        result = guard.check({
            "server": "Broker-Demo",
            "login": 123456,
            "trade_mode": 0,
        })
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
