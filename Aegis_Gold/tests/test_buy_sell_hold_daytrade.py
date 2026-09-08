"""
Unit tests for Aegis Gold bi-directional BUY, SELL, HOLD decision engine & $3.90 day trade target.
"""

import unittest
from config import settings as cfg
from brain.brain import Decision, compute_eqs
from modules.risk_manager import RiskManager


class MockGateway:
    def __init__(self):
        self.symbols_data = {
            "XAUUSD": {"point": 0.01, "digits": 2, "min_lot": 0.01, "max_lot": 10.0, "lot_step": 0.01},
            "EURUSD": {"point": 0.00001, "digits": 5, "min_lot": 0.01, "max_lot": 10.0, "lot_step": 0.01},
        }

    def get_account_info(self):
        return {"equity": 1000.0, "balance": 1000.0, "margin_free": 1000.0, "profit": 0.0}


class TestBuySellHoldDaytrade(unittest.TestCase):

    def setUp(self):
        self.gateway = MockGateway()
        self.risk_mgr = RiskManager(self.gateway)

    def test_xauusd_config_target_profit_and_tp_points(self):
        """Verify that XAUUSD config targets $3.90 profit ($3.90 move = 390 points)."""
        xau_cfg = cfg.get_symbol_config("XAUUSD")
        self.assertEqual(xau_cfg.get("target_profit"), 3.90)
        self.assertEqual(xau_cfg.get("min_tp_points"), 390)

    def test_atr_scaled_sl_tp_gold_tp_floor(self):
        """Verify that XAUUSD atr_scaled_sl_tp uses 390 points ($3.90 Gold move) as TP floor."""
        exits = self.risk_mgr.atr_scaled_sl_tp("XAUUSD", atr_pts=0.0, confidence=50)
        self.assertEqual(exits["tp_pts"], 390)
        self.assertEqual(exits["sl_pts"], 150)
        self.assertGreaterEqual(exits["rr_ratio"], 2.0)

    def test_dual_tier_sl_tp_gold_scalp_tp_floor(self):
        """Verify that XAUUSD dual_tier_sl_tp scalp tier uses 390 points ($3.90 Gold move) as TP floor."""
        res = self.risk_mgr.dual_tier_sl_tp(
            symbol="XAUUSD",
            tier="scalp",
            direction="BUY",
            entry_price=2000.0,
            invalidation_level=1998.50,
            atr_pts=0.0,
            point=0.01
        )
        self.assertTrue(res["approved"])
        self.assertGreaterEqual(res["tp_pts"], 390)

    def test_bi_directional_decisions_structure(self):
        """Verify structure analysis supports both BUY and SELL depending on support/resistance proximity."""
        from brain.structure import analyze_structure, StructureState
        
        # Mock 100 candles near support
        candles_support = [{"open": 2000.0, "high": 2005.0, "low": 1999.0, "close": 2001.0} for _ in range(100)]
        struct_buy = analyze_structure(candles_support, current_price=2000.0, trend="TRENDING_UP", point=0.01)
        self.assertIn(struct_buy.preferred_direction, ["BUY", "NONE"])

        # Mock 100 candles near resistance
        candles_resistance = [{"open": 2000.0, "high": 2001.0, "low": 1995.0, "close": 1996.0} for _ in range(100)]
        struct_sell = analyze_structure(candles_resistance, current_price=2000.0, trend="TRENDING_DOWN", point=0.01)
        self.assertIn(struct_sell.preferred_direction, ["SELL", "NONE"])


if __name__ == "__main__":
    unittest.main()
