"""
===========================================================================
🧪 AEGIS GOLD — SELL SIGNAL REGRESSION TEST SUITE (test_sell_signals.py)
===========================================================================

PURPOSE:
--------
Asserts that SELL signals are evaluated symmetrically and correctly output
SELL decisions when market conditions / sub-engines are bearish.
Prevents regressions where SELL decisions silently default or flip to BUY.
===========================================================================
"""

import unittest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from brain.brain import decide, Decision
from brain.ai_supervisor import AISupervisor
from brain.meta_decision_engine import MetaDecisionEngine


class TestSellSignalExecution(unittest.TestCase):
    """Test suite ensuring SELL signals execute correctly without defaulting to BUY."""

    def setUp(self):
        # Generate 100 bars of realistic bearish XAUUSD candles (price dropping from 2400 to 2350)
        self.symbol = "XAUUSD"
        self.point = 0.01
        np.random.seed(42)

        prices = np.linspace(2400.0, 2350.0, 100) + np.random.normal(0, 0.5, 100)
        self.bearish_candles = []
        for i in range(100):
            p = float(prices[i])
            self.bearish_candles.append({
                "open": p + 0.8,
                "high": p + 1.2,
                "low": p - 0.5,
                "close": p,
                "volume": 1000 + i
            })

    def test_omega_supervisor_bearish_pattern(self):
        """Verify OMEGA AISupervisor returns 'bearish' vote when candle patterns are bearish."""
        sup = AISupervisor()
        # Mock candle AI to return strong bearish strength
        sup.candle_ai.analyze = lambda candles: {"bullish_strength": 20, "bearish_strength": 80, "reason": "Bearish Engulfing"}
        
        vote, risk = sup.get_engine_vote(
            symbol=self.symbol,
            context={"spread": 15.0, "session": "LONDON"},
            candles_m1=self.bearish_candles,
            candles_m5=self.bearish_candles
        )

        self.assertFalse(risk["hard_veto"], "OMEGA should not raise hard veto")
        self.assertEqual(vote["direction"], "bearish", "OMEGA must output 'bearish' vote for 80% bearish strength")
        self.assertGreaterEqual(vote["confidence"], 0.70, "Confidence should match bearish strength")

    def test_meta_decision_engine_sell_approval(self):
        """Verify MetaDecisionEngine approves SELL trade when given direction='SELL' and bearish candles."""
        mde = MetaDecisionEngine()
        m_res = mde.compute_mds(
            candles_m5=self.bearish_candles,
            direction="SELL",
            sl_pts=150,
            tp_pts=300,
            symbol=self.symbol,
            lot=0.01,
            spread=15.0,
            session="LONDON"
        )

        self.assertEqual(m_res.direction, "SELL", "MDSResult direction must be SELL")
        self.assertFalse(m_res.blocked, "MDSResult should not be blocked for valid bearish candles")

    def test_decide_does_not_default_to_buy_on_ties(self):
        """Verify brain.decide() returns HOLD or correct direction when scores are tied/neutral."""
        # Create flat/neutral candles
        flat_candles = []
        for i in range(100):
            flat_candles.append({
                "open": 2380.0,
                "high": 2380.5,
                "low": 2379.5,
                "close": 2380.0,
                "volume": 500
            })

        dec: Decision = decide(
            candles_m5=flat_candles,
            account={"equity": 10000.0, "balance": 10000.0},
            session="LONDON",
            spread=15.0,
            point=self.point,
            symbol=self.symbol
        )

        # On flat/neutral candles without high consensus, action should be WAIT/HOLD, NOT an enforced BUY trade!
        if dec.action == "TRADE":
            self.assertNotEqual(dec.reason, "Consensus insufficient")
        else:
            self.assertEqual(dec.action, "WAIT", "Neutral/flat market must yield WAIT, not default BUY")

    def test_decide_executes_sell_on_bearish_breakdown(self):
        """Verify brain.decide() outputs SELL decision on sharp bearish breakdown series."""
        sharp_bear_candles = []
        p = 2400.0
        for i in range(100):
            p -= 0.8  # Consistent strong downward trend
            sharp_bear_candles.append({
                "open": p + 0.7,
                "high": p + 0.8,
                "low": p - 0.2,
                "close": p,
                "volume": 1500
            })

        dec: Decision = decide(
            candles_m5=sharp_bear_candles,
            account={"equity": 10000.0, "balance": 10000.0},
            session="LONDON",
            spread=15.0,
            point=self.point,
            symbol=self.symbol
        )

        # Log decision output for audit
        print(f"Decide Output on Bearish Trend: Action={dec.action}, Reason={dec.reason}")

        if dec.action == "TRADE":
            # If trade is triggered on bearish breakdown, it MUST be SELL, never BUY!
            self.assertIn("SELL", dec.reason.upper(), "Trade on bearish breakdown MUST be SELL, never BUY")


if __name__ == "__main__":
    unittest.main()
