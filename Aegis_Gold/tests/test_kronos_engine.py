"""
===========================================================================
🧪 KRONOS ALPHA ENGINE — UNIT TEST SUITE (test_kronos_engine.py)
===========================================================================
"""

import sys
import os
import unittest
import numpy as np

# Add Aegis_Gold root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kronos_engine.data_pipeline import DataPipeline, KronosTokenizer, MarketWindow
from kronos_engine.kronos_brain import KronosBrain, KronosSignalVector
from kronos_engine.calibration_audit import CalibrationAuditEngine, AuditResult
from kronos_engine.risk_manager import RiskSupervisor, RiskApproval
from kronos_engine.main_execution import KronosExecutionEngine


class TestKronosEngine(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        self.raw_candles = []
        p = 4000.0
        for _ in range(100):
            p += np.random.normal(loc=0.02, scale=1.0)
            self.raw_candles.append({
                "open": p - 0.2,
                "high": p + 0.8,
                "low": p - 0.8,
                "close": p,
                "volume": 100
            })

    def test_data_pipeline_and_tokenizer(self):
        pipeline = DataPipeline(history_window=100)
        window = pipeline.process_candles(self.raw_candles, symbol="XAUUSD", point=0.01)
        
        self.assertEqual(window.symbol, "XAUUSD")
        self.assertEqual(len(window.closes), 100)
        self.assertEqual(window.normalized_tensor.shape, (100, 4))
        
        coarse_tokens, fine_tokens = pipeline.tokenize_window(window)
        self.assertEqual(len(coarse_tokens), 100)
        self.assertEqual(len(fine_tokens), 100)
        self.assertTrue(np.all(coarse_tokens >= 0))
        self.assertTrue(np.all(fine_tokens >= 0))

    def test_kronos_brain_inference(self):
        pipeline = DataPipeline(history_window=100)
        window = pipeline.process_candles(self.raw_candles, symbol="XAUUSD", point=0.01)
        
        brain = KronosBrain(model_name="Kronos-small")
        signal = brain.generate_signal(window, mc_samples=50)
        
        self.assertIn(signal.direction, ["LONG", "SHORT", "HOLD"])
        self.assertTrue(0.0 <= signal.confidence <= 1.0)
        self.assertTrue(0.0 <= signal.forecast_entropy <= 1.0)
        self.assertIsInstance(signal.p10_volatility_bound, float)
        self.assertIsInstance(signal.p90_volatility_bound, float)

    def test_calibration_audit_anti_overfitting_gates(self):
        audit_engine = CalibrationAuditEngine(
            target_win_rate_range=(0.48, 0.60),
            target_pf_range=(1.60, 2.50)
        )
        
        # Test Case 1: Catastrophic Overfitting Rejection (WR > 70%)
        pnls_overfitted = np.array([5.0] * 80 + [-2.0] * 20)  # 80% Win Rate
        durations = np.array([120.0] * 100)
        res_overfitted = audit_engine.run_walk_forward_audit(pnls_overfitted, durations)
        
        self.assertFalse(res_overfitted.passed)
        self.assertTrue(res_overfitted.curve_fitting_flag)
        self.assertIn("CATASTROPHIC OVERFITTING", res_overfitted.rejection_reason)
        
        # Test Case 2: Realistic Institutional Target Passing (WR 55%, PF 1.83)
        pnls_realistic = np.array([3.5] * 55 + [-1.5] * 45)
        res_realistic = audit_engine.run_walk_forward_audit(pnls_realistic, durations)
        self.assertTrue(res_realistic.passed)
        self.assertFalse(res_realistic.curve_fitting_flag)

    def test_risk_supervisor_hard_sl_floor_and_kelly(self):
        risk = RiskSupervisor(fractional_kelly=0.25)
        pipeline = DataPipeline(history_window=100)
        window = pipeline.process_candles(self.raw_candles, symbol="XAUUSD", point=0.01)
        
        signal = KronosSignalVector(
            symbol="XAUUSD", direction="LONG", expected_return_pts=25.0,
            confidence=0.58, p10_volatility_bound=-15.0, p50_volatility_bound=5.0,
            p90_volatility_bound=35.0, forecast_entropy=0.45, rank_ic=0.12
        )
        
        approval = risk.evaluate_risk(window, signal, account_equity=10000.0)
        
        self.assertTrue(approval.approved)
        self.assertGreaterEqual(approval.sl_points, 150)  # Hard SL Floor for Gold: 150 points
        self.assertGreaterEqual(approval.tp_points, 300)
        self.assertGreater(approval.lot_size, 0.0)

    def test_main_execution_orchestrator(self):
        engine = KronosExecutionEngine()
        payload = engine.process_market_cycle(
            raw_candles=self.raw_candles,
            symbol="XAUUSD",
            point=0.01,
            current_price=4030.0,
            account_equity=10000.0
        )
        
        self.assertIn(payload.execution_status, ["READY", "WAIT", "REJECTED_AUDIT", "REJECTED_RISK"])
        if payload.execution_status == "READY":
            self.assertEqual(payload.symbol, "XAUUSD")
            self.assertIn(payload.action, ["BUY", "SELL"])
            self.assertGreater(payload.volume, 0.0)
            self.assertNotEqual(payload.sl, 0.0)


if __name__ == "__main__":
    unittest.main()
