"""
Unit Tests — AEGIS GOLD AI: Dual-Tier Pattern Engine (M1 Small Pattern + M5/HTF Big Pattern)
"""

import unittest
import math
import pandas as pd
import numpy as np

from brain.smc_engine import (
    detect_big_pattern,
    detect_small_pattern,
    BigPatternResult,
    SmallPatternResult,
    SMCEngine
)
from brain.regime import get_pattern_regime_bias
from modules.risk_manager import RiskManager


class DummyGateway:
    def get_account_info(self):
        return {"equity": 10000.0, "balance": 10000.0, "margin_level": 500.0}
    def get_open_positions(self):
        return []


class TestDualTierPatternEngine(unittest.TestCase):

    def setUp(self):
        self.symbol = "XAUUSD"
        self.point = 0.01
        self.gateway = DummyGateway()
        self.risk_mgr = RiskManager(gateway=self.gateway)

    def _generate_candles(self, n=50, base_price=2000.0, trend="neutral"):
        closes, highs, lows, opens = [], [], [], []
        curr = base_price
        
        if trend == "neutral":
            for i in range(n):
                c = base_price + math.sin(i / 2.0) * 0.2
                o = c - 0.05 if i % 2 == 0 else c + 0.05
                h = max(o, c) + 0.1
                l = min(o, c) - 0.1
                opens.append(o)
                closes.append(c)
                highs.append(h)
                lows.append(l)
        elif trend == "bullish":
            for i in range(n):
                if i < 10:
                    curr = base_price + i * 0.5
                elif i < 15:
                    curr = base_price + 5.0 - (i - 10) * 0.2
                else:
                    curr = base_price + 4.0 + (i - 15) * 0.8
                o = curr - 0.1
                c = curr + 0.1
                h = curr + 0.3
                l = curr - 0.3
                opens.append(o)
                closes.append(c)
                highs.append(h)
                lows.append(l)
        elif trend == "bearish":
            for i in range(n):
                if i < 10:
                    curr = base_price - i * 0.5
                elif i < 15:
                    curr = base_price - 5.0 + (i - 10) * 0.2
                else:
                    curr = base_price - 4.0 - (i - 15) * 0.8
                o = curr + 0.1
                c = curr - 0.1
                h = curr + 0.3
                l = curr - 0.3
                opens.append(o)
                closes.append(c)
                highs.append(h)
                lows.append(l)

        return pd.DataFrame({
            "open": opens, "high": highs, "low": lows, "close": closes
        })



    def test_big_pattern_neutral_bias(self):
        """Test that neutral candles produce neutral Big Pattern bias."""
        candles_m5 = self._generate_candles(n=30, trend="neutral")
        res = detect_big_pattern(symbol=self.symbol, candles_m5=candles_m5, point=self.point)
        self.assertIsInstance(res, BigPatternResult)
        self.assertEqual(res.bias, "neutral")
        self.assertEqual(res.confidence, 0.0)

    def test_big_pattern_bullish_and_h1_veto(self):
        """Test Big Pattern bullish bias detection and H1 veto logic."""
        candles_m5 = self._generate_candles(n=30, trend="bullish")
        res_m5_only = detect_big_pattern(symbol=self.symbol, candles_m5=candles_m5, point=self.point)
        self.assertEqual(res_m5_only.bias, "bullish")
        self.assertGreater(res_m5_only.confidence, 0.0)

        # H1 opposes M5 -> Veto forces neutral bias
        candles_h1_bearish = self._generate_candles(n=20, trend="bearish")
        res_vetoed = detect_big_pattern(symbol=self.symbol, candles_m5=candles_m5, candles_h1=candles_h1_bearish, point=self.point)
        self.assertEqual(res_vetoed.bias, "neutral")

    def test_small_pattern_hard_filter_neutral_bias(self):
        """Test that Small Pattern returns None immediately if required_bias is neutral."""
        candles_m1 = self._generate_candles(n=20, trend="bullish")
        res = detect_small_pattern(symbol=self.symbol, candles_m1=candles_m1, required_bias="neutral", point=self.point)
        self.assertIsNone(res)

    def test_small_pattern_direction_mismatch_returns_none(self):
        """Test that Small Pattern returns None if pattern direction != required_bias."""
        # Bullish m1 candles should not trigger a bearish small pattern
        candles_m1 = self._generate_candles(n=20, trend="bullish")
        res = detect_small_pattern(symbol=self.symbol, candles_m1=candles_m1, required_bias="bearish", point=self.point)
        self.assertIsNone(res)

    def test_dual_tier_sl_tp_scalp_tier(self):
        """Test Scalp Tier SL/TP calculation and min R:R >= 2.0 enforcement."""
        entry_price = 2000.0
        invalidation_level = 1998.0  # 200 pts structural SL
        res = self.risk_mgr.dual_tier_sl_tp(
            symbol="XAUUSD",
            tier="scalp",
            direction="BUY",
            entry_price=entry_price,
            invalidation_level=invalidation_level,
            point=0.01
        )
        self.assertTrue(res["approved"])
        self.assertGreaterEqual(res["rr_ratio"], 2.0)
        self.assertGreaterEqual(res["sl_pts"], 150)

    def test_dual_tier_sl_tp_pro_trend_tier(self):
        """Test Pro Trend Tier SL/TP calculation and min R:R >= 3.0 enforcement."""
        entry_price = 2000.0
        invalidation_level = 1996.0  # 400 pts structural SL
        res = self.risk_mgr.dual_tier_sl_tp(
            symbol="XAUUSD",
            tier="pro_trend",
            direction="BUY",
            entry_price=entry_price,
            invalidation_level=invalidation_level,
            point=0.01
        )
        self.assertTrue(res["approved"])
        self.assertGreaterEqual(res["rr_ratio"], 3.0)
        self.assertGreaterEqual(res["sl_pts"], 300)

    def test_dual_tier_sl_tp_rejection_low_rr(self):
        """Test that setups below tier min R:R are rejected without shrinking SL."""
        entry_price = 2000.0
        invalidation_level = 1990.0  # 1000 pts SL for scalp tier cap
        res = self.risk_mgr.dual_tier_sl_tp(
            symbol="XAUUSD",
            tier="scalp",
            direction="BUY",
            entry_price=entry_price,
            invalidation_level=invalidation_level,
            point=0.01
        )
        self.assertFalse(res["approved"])
        self.assertIn("below tier 'scalp' minimum", res["rejection_reason"])


if __name__ == "__main__":
    unittest.main()
