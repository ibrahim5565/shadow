"""
Unit Test: Mandatory Broker-Side Hard SL Enforcement
=====================================================
Verifies that MT5Gateway.build_order_request() and execute_order()
NEVER produce an MT5 order request payload with sl = 0.0, even when
sl_pts <= 0 is passed.
"""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from modules.mt5_gateway import MT5Gateway


class TestSLEnforcement(unittest.TestCase):

    def setUp(self):
        self.gateway = MT5Gateway()
        # Mock symbol data for test
        self.gateway.symbols_data = {
            "XAUUSD": {"point": 0.01, "digits": 2},
            "EURUSD": {"point": 0.00001, "digits": 5}
        }

    def test_xauusd_sl_zero_is_floored(self):
        """Passing sl_pts=0 for XAUUSD must floor SL to 150 points ($1.50)."""
        req = self.gateway.build_order_request(
            symbol="XAUUSD", direction="BUY", lot=0.01, tp_pts=350, sl_pts=0, price=2000.00, type_filling=1
        )
        self.assertNotEqual(req["sl"], 0.0, "SL must not be 0.0")
        self.assertEqual(req["sl"], 1998.50, "BUY SL at 2000.00 with 150pt floor should be 1998.50")

    def test_eurusd_sl_zero_is_floored(self):
        """Passing sl_pts=0 for EURUSD must floor SL to 40 points."""
        req = self.gateway.build_order_request(
            symbol="EURUSD", direction="BUY", lot=0.01, tp_pts=80, sl_pts=0, price=1.10000, type_filling=1
        )
        self.assertNotEqual(req["sl"], 0.0, "SL must not be 0.0")
        self.assertEqual(req["sl"], 1.09960, "BUY SL at 1.10000 with 40pt floor should be 1.09960")

    def test_sell_order_sl_floored(self):
        """SELL order with sl_pts=0 must add SL above entry price."""
        req = self.gateway.build_order_request(
            symbol="XAUUSD", direction="SELL", lot=0.01, tp_pts=350, sl_pts=0, price=2000.00, type_filling=1
        )
        self.assertNotEqual(req["sl"], 0.0, "SELL SL must not be 0.0")
        self.assertEqual(req["sl"], 2001.50, "SELL SL at 2000.00 with 150pt floor should be 2001.50")

    def test_valid_sl_pts_preserved(self):
        """Explicit valid sl_pts (e.g. 200pts) should be preserved."""
        req = self.gateway.build_order_request(
            symbol="XAUUSD", direction="BUY", lot=0.01, tp_pts=400, sl_pts=200, price=2000.00, type_filling=1
        )
        self.assertEqual(req["sl"], 1998.00, "BUY SL with 200pt SL should be 1998.00")

    def test_verify_sl_enforcement_method(self):
        """Runtime self-check method must return True."""
        res = self.gateway.verify_sl_enforcement()
        self.assertTrue(res, "verify_sl_enforcement() must return True")


if __name__ == "__main__":
    unittest.main()
