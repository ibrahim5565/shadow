"""
Unit Tests — AEGIS GOLD AI: Fix Breakeven-Exit Trailing Logic + Shadow Auditor Data Filtering
"""

import unittest
from dataclasses import dataclass
from modules.risk_manager import RiskManager
from brain.shadow_auditor import ShadowAuditor


class MockGateway:
    def __init__(self):
        self.symbols_data = {
            "XAUUSD": {"point": 0.01, "digits": 2},
            "EURUSD": {"point": 0.00001, "digits": 5}
        }
        self.modified_sl_calls = []

    def get_account_info(self):
        return {"equity": 10000.0, "balance": 10000.0}

    def modify_sl(self, ticket, symbol, new_sl):
        self.modified_sl_calls.append((ticket, symbol, new_sl))
        return True


@dataclass
class MockPosition:
    ticket: int
    symbol: str
    type: int          # 0 = BUY, 1 = SELL
    price_open: float
    price_current: float
    sl: float
    tp: float
    pattern_tier: str = "scalp"


class TestBreakevenTrailingFix(unittest.TestCase):

    def setUp(self):
        self.gateway = MockGateway()
        self.risk_mgr = RiskManager(gateway=self.gateway)

    def test_scalp_tier_bypasses_breakeven_below_1r(self):
        """Test that Scalp tier positions with profit < 1R do NOT move SL to breakeven."""
        # Scalp BUY position with 300 pts SL, but only 100 pts profit (< 1R)
        pos = MockPosition(
            ticket=1001,
            symbol="XAUUSD",
            type=0,
            price_open=2000.00,
            price_current=2001.00,  # +100 pts profit (< 300 pts SL)
            sl=1997.00,             # 300 pts SL
            tp=2010.00,
            pattern_tier="scalp"
        )
        
        self.risk_mgr.check_breakeven(pos)
        self.assertEqual(len(self.gateway.modified_sl_calls), 0, "Scalp position with profit < 1R should NOT modify SL at breakeven")

    def test_pro_trend_profit_below_1r_does_not_trigger_breakeven(self):
        """Test that Pro Trend positions with profit < 1R (initial SL distance) do NOT move SL to breakeven."""
        # Pro Trend BUY position with 300 pts SL, but only 100 pts profit (< 1R)
        pos = MockPosition(
            ticket=1002,
            symbol="XAUUSD",
            type=0,
            price_open=2000.00,
            price_current=2001.00,  # +100 pts profit (< 300 pts SL)
            sl=1997.00,             # 300 pts SL (1R = 300 pts)
            tp=2015.00,
            pattern_tier="pro_trend"
        )
        
        self.risk_mgr.check_breakeven(pos)
        self.assertEqual(len(self.gateway.modified_sl_calls), 0, "Pro Trend position with profit < 1R should NOT move SL to breakeven")

    def test_pro_trend_profit_below_1_5r_does_not_trigger_breakeven(self):
        """Test that Pro Trend positions with profit < 1.5R (was 1.0R) do NOT move SL to breakeven."""
        # Pro Trend BUY position with 300 pts SL, and 350 pts profit (1.17R -- below new 1.5R threshold)
        pos = MockPosition(
            ticket=1003,
            symbol="XAUUSD",
            type=0,
            price_open=2000.00,
            price_current=2003.50,  # +350 pts profit (1.17R -- below 1.5R gate)
            sl=1997.00,             # 300 pts SL (1R = 300 pts)
            tp=2015.00,
            pattern_tier="pro_trend"
        )

        self.risk_mgr.check_breakeven(pos)
        self.assertEqual(len(self.gateway.modified_sl_calls), 0,
                         "Pro Trend position with profit < 1.5R should NOT move SL to breakeven (Aug-6 fix)")

    def test_pro_trend_profit_above_1_5r_triggers_breakeven(self):
        """Test that Pro Trend positions with profit >= 1.5R DO move SL to breakeven."""
        # Pro Trend BUY position with 300 pts SL, and 460 pts profit (1.53R > 1.5R)
        pos = MockPosition(
            ticket=1004,
            symbol="XAUUSD",
            type=0,
            price_open=2000.00,
            price_current=2004.60,  # +460 pts profit (1.53R >= 1.5R gate)
            sl=1997.00,             # 300 pts SL (1R = 300 pts)
            tp=2015.00,
            pattern_tier="pro_trend"
        )

        self.risk_mgr.check_breakeven(pos)
        self.assertEqual(len(self.gateway.modified_sl_calls), 1,
                         "Pro Trend position with profit >= 1.5R MUST trigger breakeven")
        ticket, symbol, new_sl = self.gateway.modified_sl_calls[0]
        self.assertEqual(ticket, 1004)
        self.assertEqual(new_sl, 2000.10)  # Open + 10 pts buffer

    def test_shadow_auditor_data_filtering_and_sample_guard(self):
        """Test that ShadowAuditor strictly isolates dual_tier_v1 trades and displays INSUFFICIENT SAMPLE for N < 30."""
        auditor = ShadowAuditor()
        report = auditor.run_full_audit(target_pipeline_id="dual_tier_v1")
        
        self.assertIn("metadata", report)
        self.assertEqual(report["metadata"]["pipeline_id"], "dual_tier_v1")
        
        # Confirm that N < 30 yields INSUFFICIENT SAMPLE decision
        if report["metadata"]["sample_size"] < 30:
            self.assertEqual(report["final_decision"], "INSUFFICIENT SAMPLE -- DO NOT INTERPRET")



if __name__ == "__main__":
    unittest.main()
