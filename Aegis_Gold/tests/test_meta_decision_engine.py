"""
Unit tests for Meta Decision Score Engine (MDS), ModelReliabilityTracker, and SystemDiagnostics.
"""

import unittest
import numpy as np
import tempfile
import os

from brain.meta_decision_engine import MetaDecisionEngine, MDSResult
from brain.model_reliability import ModelReliabilityTracker
from brain.diagnostics import SystemDiagnostics


class TestMetaDecisionEngine(unittest.TestCase):

    def setUp(self):
        self.mde = MetaDecisionEngine()
        self.dummy_candles = [
            {"open": 1900.0 + i * 0.5, "high": 1902.0 + i * 0.5, "low": 1899.0 + i * 0.5, "close": 1901.0 + i * 0.5, "volume": 100}
            for i in range(50)
        ]

    def test_mds_computation_basic(self):
        res = self.mde.compute_mds(
            candles_m5=self.dummy_candles,
            direction="BUY",
            sl_pts=150,
            tp_pts=300,
            symbol="XAUUSD",
            lot=0.01
        )
        self.assertIsInstance(res, MDSResult)
        self.assertGreaterEqual(res.mds, 0.0)
        self.assertLessEqual(res.mds, 1.0)
        self.assertIn("quant", res.component_scores)
        self.assertIn("kronos", res.component_scores)
        self.assertIn("ml_ev", res.component_scores)

    def test_macro_blackout_hard_block(self):
        res = self.mde.compute_mds(
            candles_m5=self.dummy_candles,
            direction="BUY",
            sl_pts=150,
            tp_pts=300,
            symbol="XAUUSD",
            macro_blackout=True
        )
        self.assertTrue(res.blocked)
        self.assertFalse(res.approved)
        self.assertIn("blackout", res.block_reason.lower())

    def test_model_reliability_tracker(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
            tmp_db = tmp.name

        try:
            tracker = ModelReliabilityTracker(db_path=tmp_db)
            # Default factor should be 1.0
            self.assertEqual(tracker.get_reliability_factor("quant"), 1.0)

            # Record 6 winning trades
            for _ in range(6):
                tracker.record_outcome("quant", won=True, pnl=50.0)

            factor = tracker.get_reliability_factor("quant")
            self.assertGreater(factor, 1.0)  # Should boost reliability factor above 1.0

            stats = tracker.get_all_stats()
            self.assertIn("quant", stats)
            self.assertEqual(stats["quant"]["wins"], 6)
        finally:
            try:
                if os.path.exists(tmp_db):
                    os.remove(tmp_db)
            except PermissionError:
                pass

    def test_system_diagnostics(self):
        diag = SystemDiagnostics()
        health = diag.get_overall_health()
        self.assertIn(health, ["HEALTHY", "DEGRADED", "CRITICAL"])
        res = diag.run_diagnostics()
        self.assertIn("quant", res)
        self.assertIn("kronos", res)
        self.assertIn("ml_ev", res)


if __name__ == "__main__":
    unittest.main()
