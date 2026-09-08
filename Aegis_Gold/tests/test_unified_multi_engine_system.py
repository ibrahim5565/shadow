"""
Unit Tests — AEGIS GOLD AI: Unified Multi-Engine Pattern Decision System (RL + Quant + ML + OMEGA + Kronos)
"""

import unittest
import math
import pandas as pd
import numpy as np

from brain.quant_feature_engine import QuantFeatureEngine
from brain import ml_ensemble
from brain.ai_supervisor import AISupervisor
from brain.kronos_forecaster import KronosForecaster
from brain.reinforcement_agent import AegisRLAgent
from modules.risk_manager import RiskManager


class DummyGateway:
    def get_account_info(self):
        return {"equity": 10000.0, "balance": 10000.0, "margin_level": 500.0}
    def get_open_positions(self):
        return []


class TestUnifiedMultiEngineSystem(unittest.TestCase):

    def setUp(self):
        self.symbol = "XAUUSD"
        self.point = 0.01
        self.gateway = DummyGateway()
        self.risk_mgr = RiskManager(gateway=self.gateway)

    def _generate_candles(self, n=50, base_price=2000.0):
        closes, highs, lows, opens = [], [], [], []
        for i in range(n):
            c = base_price + math.sin(i / 3.0) * 0.5 + (i * 0.05)
            o = c - 0.1
            h = c + 0.3
            l = c - 0.3
            opens.append(o)
            closes.append(c)
            highs.append(h)
            lows.append(l)

        return pd.DataFrame({
            "open": opens, "high": highs, "low": lows, "close": closes
        })

    def test_engine_vote_contract_quant(self):
        """Test EngineVote contract output from Quant Feature Engine."""
        candles = self._generate_candles(n=30)
        q_engine = QuantFeatureEngine()
        vote = q_engine.get_engine_vote(candles, symbol=self.symbol)
        
        self.assertEqual(vote["engine"], "quant")
        self.assertIn(vote["direction"], ("bullish", "bearish", "neutral"))
        self.assertGreaterEqual(vote["confidence"], 0.0)
        self.assertLessEqual(vote["confidence"], 1.0)
        self.assertIsInstance(vote["reasoning"], str)

    def test_engine_vote_contract_ml_ensemble(self):
        """Test EngineVote contract output from ML Ensemble."""
        candles = self._generate_candles(n=30)
        vote = ml_ensemble.get_engine_vote(candles, symbol=self.symbol)
        
        self.assertEqual(vote["engine"], "ml_ensemble")
        self.assertIn(vote["direction"], ("bullish", "bearish", "neutral"))
        self.assertGreaterEqual(vote["confidence"], 0.0)
        self.assertLessEqual(vote["confidence"], 1.0)

    def test_engine_vote_contract_omega(self):
        """Test EngineVote contract output from OMEGA AI Supervisor."""
        candles = self._generate_candles(n=30)
        omega = AISupervisor()
        vote, exec_risk = omega.get_engine_vote(
            symbol=self.symbol,
            direction_hint="BUY",
            context={"spread": 15.0, "session": "LONDON"},
            candles_m5=candles
        )
        
        self.assertEqual(vote["engine"], "omega")
        self.assertIn(vote["direction"], ("bullish", "bearish", "neutral"))
        self.assertIsInstance(exec_risk, dict)
        self.assertIn("hard_veto", exec_risk)

    def test_omega_execution_risk_hard_veto(self):
        """Test that OMEGA hard veto fires ONLY for execution risks (e.g. spread blowout)."""
        candles = self._generate_candles(n=30)
        omega = AISupervisor()
        
        # Normal spread -> No hard veto
        vote_normal, risk_normal = omega.get_engine_vote(
            symbol=self.symbol,
            direction_hint="BUY",
            context={"spread": 15.0, "session": "LONDON"},
            candles_m5=candles
        )
        self.assertFalse(risk_normal["hard_veto"])

        # Blowout spread (150 pts > 35 pts limit) -> Hard Veto
        vote_blowout, risk_blowout = omega.get_engine_vote(
            symbol=self.symbol,
            direction_hint="BUY",
            context={"spread": 150.0, "session": "LONDON"},
            candles_m5=candles
        )
        self.assertTrue(risk_blowout["hard_veto"])
        self.assertIn("Spread blowout", risk_blowout["reason"])

    def test_engine_vote_contract_kronos(self):
        """Test EngineVote contract output from Kronos Forecaster."""
        candles = self._generate_candles(n=30)
        kronos = KronosForecaster()
        vote = kronos.get_engine_vote(candles, symbol=self.symbol)
        
        self.assertEqual(vote["engine"], "kronos")
        self.assertIn(vote["direction"], ("bullish", "bearish", "neutral"))
        self.assertGreaterEqual(vote["confidence"], 0.0)

    def test_rl_parameter_tuning_not_live_vote(self):
        """Test that RL agent provides weight tuning parameters and updates weights without casting a live vote."""
        rl_agent = AegisRLAgent()
        weights = rl_agent.get_engine_weights(tier="scalp")
        
        self.assertIsInstance(weights, dict)
        self.assertIn("quant", weights)
        self.assertIn("ml_ensemble", weights)
        self.assertIn("omega", weights)
        self.assertIn("kronos", weights)
        
        # Verify weights sum close to 1.0
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=2)

        # Test updating weights from trade outcome
        outcome = {
            "tier": "scalp",
            "profit_usd": 25.0,
            "direction": "BUY",
            "engine_votes": {
                "quant": {"direction": "bullish", "confidence": 0.8},
                "ml_ensemble": {"direction": "bullish", "confidence": 0.7},
                "omega": {"direction": "bearish", "confidence": 0.5},
                "kronos": {"direction": "bullish", "confidence": 0.85}
            }
        }
        rl_agent.update_engine_weights(outcome)
        new_weights = rl_agent.get_engine_weights(tier="scalp")
        self.assertIsInstance(new_weights, dict)
        self.assertAlmostEqual(sum(new_weights.values()), 1.0, places=2)

    def test_weighted_consensus_calculation(self):
        """Test weighted consensus score calculation logic."""
        weights = {"quant": 0.25, "ml_ensemble": 0.25, "omega": 0.25, "kronos": 0.25}
        votes = {
            "quant": {"direction": "bullish", "confidence": 0.80},
            "ml_ensemble": {"direction": "bullish", "confidence": 0.80},
            "omega": {"direction": "bullish", "confidence": 0.75},
            "kronos": {"direction": "bullish", "confidence": 0.85}
        }
        
        target = "bullish"
        agree_w = sum(weights[k] * votes[k]["confidence"] for k in weights if votes[k]["direction"] == target)
        total_w = sum(weights.values())
        consensus_score = agree_w / total_w
        
        self.assertGreaterEqual(consensus_score, 0.75)


if __name__ == "__main__":
    unittest.main()
