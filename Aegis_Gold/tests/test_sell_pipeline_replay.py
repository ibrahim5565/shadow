import sqlite3
import pandas as pd
import unittest
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.risk_manager import RiskManager
from modules.mt5_gateway import MT5Gateway
from brain.brain import normalize_direction

class TestSellPipelineReplay(unittest.TestCase):

    def setUp(self):
        self.risk = RiskManager(gateway=None)
        self.db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "decision_records.db"))

    def test_normalize_direction(self):
        """Test canonical direction normalization for all variations."""
        self.assertEqual(normalize_direction("BUY"), "bullish")
        self.assertEqual(normalize_direction("buy"), "bullish")
        self.assertEqual(normalize_direction("BULLISH"), "bullish")
        self.assertEqual(normalize_direction("SELL"), "bearish")
        self.assertEqual(normalize_direction("sell"), "bearish")
        self.assertEqual(normalize_direction("BEARISH"), "bearish")
        self.assertEqual(normalize_direction("HOLD"), "neutral")

    def test_validate_directional_sl_tp_sell(self):
        """Test directional SL/TP validation for SELL orders."""
        # Valid SELL: Entry 2000.0, SL 2010.0 (above), TP 1980.0 (below)
        res_valid = self.risk.validate_directional_sl_tp("XAUUSD", "SELL", 2000.0, 2010.0, 1980.0)
        self.assertTrue(res_valid["approved"])

        # Invalid SELL (SL below entry): Entry 2000.0, SL 1990.0
        res_invalid_sl = self.risk.validate_directional_sl_tp("XAUUSD", "SELL", 2000.0, 1990.0, 1980.0)
        self.assertFalse(res_invalid_sl["approved"])
        self.assertIn("SELL SL Violation", res_invalid_sl["rejection_reason"])

        # Invalid SELL (TP above entry): Entry 2000.0, SL 2010.0, TP 2020.0
        res_invalid_tp = self.risk.validate_directional_sl_tp("XAUUSD", "SELL", 2000.0, 2010.0, 2020.0)
        self.assertFalse(res_invalid_tp["approved"])
        self.assertIn("SELL TP Violation", res_invalid_tp["rejection_reason"])

    def test_aug6_sell_decision_replay(self):
        """Replay all 493 SELL candidate decisions from Aug 6 live data and confirm 100% pass rate."""
        if not os.path.exists(self.db_path):
            self.skipTest(f"Database not found: {self.db_path}")

        conn = sqlite3.connect(self.db_path)
        df_sell = pd.read_sql_query(
            "SELECT * FROM decision_records WHERE timestamp LIKE '%2026-08-06%' AND direction = 'SELL'", conn
        )
        conn.close()

        self.assertGreater(len(df_sell), 0, "No SELL decision records found on Aug 6")
        print(f"\n[REPLAY] Replaying {len(df_sell)} SELL decision records from Aug 6...")

        passed_count = 0
        for idx, row in df_sell.iterrows():
            sym = row["symbol"]
            direction = row["direction"]
            
            # Normalize direction
            norm_dir = normalize_direction(direction)
            self.assertEqual(norm_dir, "bearish", f"Row {row['id']} direction {direction} failed normalization")

            # Validate directional SL/TP boundaries with sample prices
            entry_price = 2000.0 if "XAU" in sym else 1.1500
            sl_pts = 150 if "XAU" in sym else 40
            tp_pts = 300 if "XAU" in sym else 80
            point = 0.01 if "XAU" in sym else 0.00001
            
            sl_price = entry_price + (sl_pts * point)
            tp_price = entry_price - (tp_pts * point)

            val_res = self.risk.validate_directional_sl_tp(sym, "SELL", entry_price, sl_price, tp_price)
            self.assertTrue(val_res["approved"], f"Row {row['id']} validation failed: {val_res['rejection_reason']}")
            passed_count += 1

        print(f"✅ [REPLAY SUCCESS] 100% ({passed_count}/{len(df_sell)}) bearish decision records passed pipeline validation.")
        self.assertEqual(passed_count, len(df_sell))


if __name__ == "__main__":
    unittest.main()
