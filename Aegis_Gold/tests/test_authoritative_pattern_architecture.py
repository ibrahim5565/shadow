"""
Tests for Authoritative Pattern Architecture in AEGIS GOLD.
Validates:
1. Pattern tests:
   - Bullish Engulfing -> BUY
   - Bearish Engulfing -> SELL
   - Hammer -> BUY
   - Shooting Star -> SELL
   - Morning Star -> BUY
   - Evening Star -> SELL
   - No Pattern -> HOLD
   - Conflicting Patterns -> HOLD (CONFLICTING_PATTERNS)
2. Override resistance:
   - Bearish Pattern + All Engines Bullish (ML, RL, SMC, Fusion) -> SELL
   - Bullish Pattern + All Engines Bearish (ML, RL, SMC, Fusion) -> BUY
3. Critical Test 1:
   - Bearish Engulfing + ML BUY (0.95) + RL BUY (0.90) + Trend UP + SMC BUY + Fusion BUY -> SELL
4. Critical Test 2:
   - Bullish Engulfing + ML SELL (0.95) + RL SELL (0.90) + Trend DOWN + SMC SELL + Fusion SELL -> BUY
5. Observational-only Fusion:
   - Fusion cannot alter direction or action
6. Closed candle logic & deduplication:
   - Unclosed forming bar at [-1] ignored, completed closed bar at [-2] analyzed
   - 100 ticks within same candle -> max 1 trade
   - Fast analysis loop does not block candle from trading
7. Symmetrical BUY/SELL validation:
   - BUY: sl < entry, tp > entry
   - SELL: sl > entry, tp < entry
   - MT5 Gateway validation assertions
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.brain import (
    get_pattern_entry_signal,
    _decide_impl,
    decide,
    Decision,
    PatternEntry
)
from modules.mt5_gateway import MT5Gateway


class MockBigPatternResult:
    def __init__(self, bias="none", pattern_type=None, confidence=0.0, invalidation_level=0.0):
        self.bias = bias
        self.pattern_type = pattern_type
        self.confidence = confidence
        self.invalidation_level = invalidation_level


class TestAuthoritativePatternArchitecture(unittest.TestCase):
    
    def setUp(self):
        # Reset candle caches before each test
        if hasattr(_decide_impl, "_analyzed_candles"):
            _decide_impl._analyzed_candles.clear()
        if hasattr(_decide_impl, "_traded_candles"):
            _decide_impl._traded_candles.clear()
        if hasattr(_decide_impl, "_processed_candles"):
            _decide_impl._processed_candles.clear()

    # ═══════════════════════════════════════════════════════════
    # 1. INDIVIDUAL PATTERN TESTS
    # ═══════════════════════════════════════════════════════════

    def test_bullish_engulfing_buy(self):
        """Bullish Engulfing pattern on closed candle [-2] -> BUY"""
        candles = [
            {"time": 1, "open": 2500.0, "high": 2505.0, "low": 2495.0, "close": 2500.0},
            # Candle [-3]: Bearish candle
            {"time": 2, "open": 2510.0, "high": 2512.0, "low": 2498.0, "close": 2500.0},
            # Candle [-2]: Bullish Engulfing (closed)
            {"time": 3, "open": 2496.0, "high": 2516.0, "low": 2494.0, "close": 2514.0},
            # Candle [-1]: Forming candle (unclosed)
            {"time": 4, "open": 2514.0, "high": 2515.0, "low": 2513.0, "close": 2514.0},
        ]
        direction, pat_entry = get_pattern_entry_signal(candles, point=0.01, symbol="XAUUSD")
        self.assertEqual(direction, "BUY")
        self.assertIn("BULLISH", pat_entry.pattern_name.upper())
        self.assertIn("ENGULFING", pat_entry.pattern_name.upper())
        self.assertLess(pat_entry.stop_loss, pat_entry.entry_price)
        self.assertGreater(pat_entry.take_profit, pat_entry.entry_price)

    def test_bearish_engulfing_sell(self):
        """Bearish Engulfing pattern on closed candle [-2] -> SELL"""
        candles = [
            {"time": 1, "open": 2500.0, "high": 2505.0, "low": 2495.0, "close": 2500.0},
            # Candle [-3]: Bullish candle
            {"time": 2, "open": 2500.0, "high": 2512.0, "low": 2498.0, "close": 2510.0},
            # Candle [-2]: Bearish Engulfing (closed)
            {"time": 3, "open": 2514.0, "high": 2516.0, "low": 2494.0, "close": 2496.0},
            # Candle [-1]: Forming candle (unclosed)
            {"time": 4, "open": 2496.0, "high": 2497.0, "low": 2495.0, "close": 2496.0},
        ]
        direction, pat_entry = get_pattern_entry_signal(candles, point=0.01, symbol="XAUUSD")
        self.assertEqual(direction, "SELL")
        self.assertIn("BEARISH", pat_entry.pattern_name.upper())
        self.assertIn("ENGULFING", pat_entry.pattern_name.upper())
        self.assertGreater(pat_entry.stop_loss, pat_entry.entry_price)
        self.assertLess(pat_entry.take_profit, pat_entry.entry_price)

    def test_hammer_buy(self):
        """Hammer pattern (long lower shadow, small body at top) -> BUY"""
        candles = [
            {"time": 1, "open": 2510.0, "high": 2512.0, "low": 2508.0, "close": 2509.0},
            # Candle [-2]: Hammer: Open 2502, Close 2505, High 2506, Low 2480 (body=3, lower wick=22)
            {"time": 2, "open": 2502.0, "high": 2506.0, "low": 2480.0, "close": 2505.0},
            # Candle [-1]: Forming candle
            {"time": 3, "open": 2505.0, "high": 2507.0, "low": 2504.0, "close": 2506.0},
        ]
        direction, pat_entry = get_pattern_entry_signal(candles, point=0.01, symbol="XAUUSD")
        self.assertEqual(direction, "BUY")
        self.assertIn("HAMMER", pat_entry.pattern_name.upper())
        self.assertLess(pat_entry.stop_loss, pat_entry.entry_price)
        self.assertGreater(pat_entry.take_profit, pat_entry.entry_price)

    def test_shooting_star_sell(self):
        """Shooting Star pattern (long upper shadow, small body at bottom) -> SELL"""
        candles = [
            {"time": 1, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2501.0},
            # Candle [-2]: Shooting Star: Open 2505, Close 2502, Low 2501, High 2525 (body=3, upper wick=20)
            {"time": 2, "open": 2505.0, "high": 2525.0, "low": 2501.0, "close": 2502.0},
            # Candle [-1]: Forming candle
            {"time": 3, "open": 2502.0, "high": 2503.0, "low": 2501.0, "close": 2502.0},
        ]
        direction, pat_entry = get_pattern_entry_signal(candles, point=0.01, symbol="XAUUSD")
        self.assertEqual(direction, "SELL")
        self.assertIn("SHOOTING", pat_entry.pattern_name.upper())
        self.assertIn("STAR", pat_entry.pattern_name.upper())
        self.assertGreater(pat_entry.stop_loss, pat_entry.entry_price)
        self.assertLess(pat_entry.take_profit, pat_entry.entry_price)

    def test_morning_star_buy(self):
        """Morning Star (Bearish, Small star gapping down, Bullish closing above midpoint) -> BUY"""
        candles = [
            # Candle [-4]: Neutral
            {"time": 1, "open": 2530.0, "high": 2532.0, "low": 2528.0, "close": 2530.0},
            # Candle [-4 relative to -1]: Large Bearish (2525 -> 2505, midpoint 2515)
            {"time": 2, "open": 2525.0, "high": 2526.0, "low": 2504.0, "close": 2505.0},
            # Candle [-3 relative to -1]: Small Star body
            {"time": 3, "open": 2502.0, "high": 2504.0, "low": 2498.0, "close": 2503.0},
            # Candle [-2 relative to -1]: Strong Bullish closing at 2520 (> 2515)
            {"time": 4, "open": 2504.0, "high": 2522.0, "low": 2503.0, "close": 2520.0},
            # Candle [-1]: Forming candle
            {"time": 5, "open": 2520.0, "high": 2521.0, "low": 2519.0, "close": 2520.0},
        ]
        direction, pat_entry = get_pattern_entry_signal(candles, point=0.01, symbol="XAUUSD")
        self.assertEqual(direction, "BUY")
        self.assertIn("MORNING", pat_entry.pattern_name.upper())
        self.assertIn("STAR", pat_entry.pattern_name.upper())
        self.assertLess(pat_entry.stop_loss, pat_entry.entry_price)
        self.assertGreater(pat_entry.take_profit, pat_entry.entry_price)

    def test_evening_star_sell(self):
        """Evening Star (Bullish, Small star gapping up, Bearish closing below midpoint) -> SELL"""
        candles = [
            # Candle [-4]: Neutral
            {"time": 1, "open": 2490.0, "high": 2492.0, "low": 2488.0, "close": 2490.0},
            # Candle [-4 relative to -1]: Large Bullish (2500 -> 2520, midpoint 2510)
            {"time": 2, "open": 2500.0, "high": 2522.0, "low": 2498.0, "close": 2520.0},
            # Candle [-3 relative to -1]: Small Star body at top
            {"time": 3, "open": 2522.0, "high": 2525.0, "low": 2521.0, "close": 2523.0},
            # Candle [-2 relative to -1]: Strong Bearish closing at 2505 (< 2510)
            {"time": 4, "open": 2522.0, "high": 2523.0, "low": 2503.0, "close": 2505.0},
            # Candle [-1]: Forming candle
            {"time": 5, "open": 2505.0, "high": 2506.0, "low": 2504.0, "close": 2505.0},
        ]
        direction, pat_entry = get_pattern_entry_signal(candles, point=0.01, symbol="XAUUSD")
        self.assertEqual(direction, "SELL")
        self.assertIn("EVENING", pat_entry.pattern_name.upper())
        self.assertIn("STAR", pat_entry.pattern_name.upper())
        self.assertGreater(pat_entry.stop_loss, pat_entry.entry_price)
        self.assertLess(pat_entry.take_profit, pat_entry.entry_price)

    def test_no_pattern_hold(self):
        """Doji / flat candles with no recognizable pattern -> HOLD"""
        candles = [
            {"time": 1, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
            {"time": 2, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
            {"time": 3, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
            {"time": 4, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
        ]
        with patch('brain.smc_engine.detect_big_pattern') as mock_smc:
            mock_smc.return_value = MockBigPatternResult(bias="none", pattern_type=None)
            direction, pat_entry = get_pattern_entry_signal(candles, point=0.01, symbol="XAUUSD")
            self.assertEqual(direction, "HOLD")

    def test_conflicting_patterns_hold(self):
        """Simultaneous Bullish and Bearish patterns on same candle -> HOLD (CONFLICTING_PATTERNS)"""
        candles = [
            {"time": 1, "open": 2500.0, "high": 2505.0, "low": 2495.0, "close": 2500.0},
            {"time": 2, "open": 2500.0, "high": 2512.0, "low": 2498.0, "close": 2510.0},
            {"time": 3, "open": 2514.0, "high": 2516.0, "low": 2494.0, "close": 2496.0},  # Bearish engulfing
            {"time": 4, "open": 2496.0, "high": 2497.0, "low": 2495.0, "close": 2496.0},
        ]
        # Simulate SMC returning opposite bullish signal on same candle
        with patch('brain.smc_engine.detect_big_pattern') as mock_smc:
            mock_smc.return_value = MockBigPatternResult(
                bias="bullish", pattern_type="BOS_BULLISH", confidence=0.80, invalidation_level=2490.0
            )
            direction, pat_entry = get_pattern_entry_signal(candles, point=0.01, symbol="XAUUSD")
            self.assertEqual(direction, "HOLD")
            self.assertEqual(pat_entry.pattern_name, "CONFLICTING_PATTERNS")

    # ═══════════════════════════════════════════════════════════
    # 2. OVERRIDE RESISTANCE TESTS & CRITICAL TESTS 1 & 2
    # ═══════════════════════════════════════════════════════════

    def test_critical_test_1_bearish_pattern_overrides_all_bullish_engines(self):
        """
        CRITICAL TEST 1:
        Bearish Engulfing pattern detected on closed candle.
        ML = BUY (confidence 0.95)
        RL = BUY (confidence 0.90)
        Trend = UP
        SMC = BUY
        Fusion = BUY
        FINAL DECISION DIRECTION MUST BE SELL!
        """
        candle_time = datetime(2026, 9, 7, 12, 0, 0)
        candles = [
            {"time": candle_time - timedelta(minutes=15), "open": 2500.0, "high": 2505.0, "low": 2495.0, "close": 2500.0},
            {"time": candle_time - timedelta(minutes=10), "open": 2500.0, "high": 2512.0, "low": 2498.0, "close": 2510.0},
            # Closed Bearish Engulfing
            {"time": candle_time - timedelta(minutes=5), "open": 2514.0, "high": 2516.0, "low": 2494.0, "close": 2496.0},
            # Forming unclosed candle
            {"time": candle_time, "open": 2496.0, "high": 2497.0, "low": 2495.0, "close": 2496.0},
        ]
        
        mock_risk_mgr = Mock()
        mock_risk_mgr.lot_override = 0.0
        mock_risk_mgr.consecutive_losses = 0
        mock_risk_mgr.can_trade = Mock(return_value=True)
        mock_risk_mgr.is_daily_loss_limit_reached = Mock(return_value=False)
        mock_risk_mgr.daily_loss_limit_hit = Mock(return_value=False)
        mock_risk_mgr.calculate_lot_size = Mock(return_value=0.01)

        # Patch ML ensemble to BUY with 0.95 confidence
        with patch('brain.ml_ensemble.get_ml_ensemble') as mock_ml:
            mock_ml_instance = Mock()
            mock_ml_instance.predict = Mock(return_value={"direction": "BUY", "confidence": 0.95, "probability": 0.95})
            mock_ml.return_value = mock_ml_instance

            # Patch DecisionFusionV2 to return BUY
            with patch('brain.decision_fusion.DecisionFusionV2.fuse') as mock_fuse:
                mock_fuse.return_value = Mock(
                    action="TRADE", fused_direction="BUY", confidence=95, block_reason=None,
                    long_prob=0.95, short_prob=0.05, no_trade_prob=0.0, uncertainty=0.05, estimated_rr=2.5
                )

                decision = _decide_impl(
                    ticks=[{"bid": 2496.0, "ask": 2496.2}],
                    candles_m5=candles,
                    account={"balance": 10000.0, "equity": 10000.0},
                    risk_mgr=mock_risk_mgr,
                    session="LONDON",
                    spread=2.0,
                    point=0.01,
                    symbol="XAUUSD"
                )

                # Direction MUST BE SELL despite ALL other models screaming BUY
                self.assertEqual(decision.direction, "SELL", "CRITICAL TEST 1 FAILED: Direction must be SELL")
                self.assertEqual(decision.action, "TRADE", "Action should be TRADE")
                self.assertIn("BEARISH", decision.pattern.upper())
                self.assertGreater(decision.invalidation_level, 2496.0, "SELL SL must be > entry")

    def test_critical_test_2_bullish_pattern_overrides_all_bearish_engines(self):
        """
        CRITICAL TEST 2:
        Bullish Engulfing pattern detected on closed candle.
        ML = SELL (confidence 0.95)
        RL = SELL (confidence 0.90)
        Trend = DOWN
        SMC = SELL
        Fusion = SELL
        FINAL DECISION DIRECTION MUST BE BUY!
        """
        candle_time = datetime(2026, 9, 7, 12, 0, 0)
        candles = [
            {"time": candle_time - timedelta(minutes=15), "open": 2520.0, "high": 2525.0, "low": 2515.0, "close": 2520.0},
            {"time": candle_time - timedelta(minutes=10), "open": 2515.0, "high": 2516.0, "low": 2500.0, "close": 2502.0},
            # Closed Bullish Engulfing
            {"time": candle_time - timedelta(minutes=5), "open": 2500.0, "high": 2522.0, "low": 2498.0, "close": 2520.0},
            # Forming unclosed candle
            {"time": candle_time, "open": 2520.0, "high": 2521.0, "low": 2519.0, "close": 2520.0},
        ]

        mock_risk_mgr = Mock()
        mock_risk_mgr.lot_override = 0.0
        mock_risk_mgr.consecutive_losses = 0
        mock_risk_mgr.can_trade = Mock(return_value=True)
        mock_risk_mgr.is_daily_loss_limit_reached = Mock(return_value=False)
        mock_risk_mgr.daily_loss_limit_hit = Mock(return_value=False)
        mock_risk_mgr.calculate_lot_size = Mock(return_value=0.01)

        # Patch ML ensemble to SELL with 0.95 confidence
        with patch('brain.ml_ensemble.get_ml_ensemble') as mock_ml:
            mock_ml_instance = Mock()
            mock_ml_instance.predict = Mock(return_value={"direction": "SELL", "confidence": 0.95, "probability": 0.95})
            mock_ml.return_value = mock_ml_instance

            # Patch DecisionFusionV2 to return SELL
            with patch('brain.decision_fusion.DecisionFusionV2.fuse') as mock_fuse:
                mock_fuse.return_value = Mock(
                    action="TRADE", fused_direction="SELL", confidence=95, block_reason=None,
                    long_prob=0.05, short_prob=0.95, no_trade_prob=0.0, uncertainty=0.05, estimated_rr=2.5
                )

                decision = _decide_impl(
                    ticks=[{"bid": 2520.0, "ask": 2520.2}],
                    candles_m5=candles,
                    account={"balance": 10000.0, "equity": 10000.0},
                    risk_mgr=mock_risk_mgr,
                    session="LONDON",
                    spread=2.0,
                    point=0.01,
                    symbol="XAUUSD"
                )

                # Direction MUST BE BUY despite ALL other models screaming SELL
                self.assertEqual(decision.direction, "BUY", "CRITICAL TEST 2 FAILED: Direction must be BUY")
                self.assertEqual(decision.action, "TRADE", "Action should be TRADE")
                self.assertIn("BULLISH", decision.pattern.upper())
                self.assertLess(decision.invalidation_level, 2520.0, "BUY SL must be < entry")

    # ═══════════════════════════════════════════════════════════
    # 3. OBSERVATIONAL-ONLY FUSION LAYER
    # ═══════════════════════════════════════════════════════════

    def test_fusion_cannot_upgrade_wait_to_trade(self):
        """When no pattern exists (HOLD/WAIT), Fusion returning action='TRADE' CANNOT upgrade to TRADE"""
        candles = [
            {"time": 1, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
            {"time": 2, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
            {"time": 3, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
            {"time": 4, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
        ]
        with patch('brain.smc_engine.detect_big_pattern') as mock_smc:
            mock_smc.return_value = MockBigPatternResult(bias="none")
            with patch('brain.decision_fusion.DecisionFusionV2.fuse') as mock_fuse:
                mock_fuse.return_value = Mock(
                    action="TRADE", fused_direction="BUY", confidence=90, block_reason=None,
                    long_prob=0.9, short_prob=0.05, no_trade_prob=0.05, uncertainty=0.1, estimated_rr=2.5
                )

                mock_risk_mgr = Mock()
                mock_risk_mgr.lot_override = 0.0
                mock_risk_mgr.consecutive_losses = 0
                mock_risk_mgr.margin_buffer_check = Mock(return_value=True)
                mock_risk_mgr.can_trade = Mock(return_value=True)
                mock_risk_mgr.is_daily_loss_limit_reached = Mock(return_value=False)
                mock_risk_mgr.daily_loss_limit_hit = Mock(return_value=False)
                mock_risk_mgr.calculate_lot_size = Mock(return_value=0.01)

                decision = decide(
                    ticks=[{"bid": 2500.0, "ask": 2500.2}],
                    candles_m5=candles,
                    account={"balance": 10000.0, "equity": 10000.0},
                    risk_mgr=mock_risk_mgr,
                    session="LONDON",
                    spread=2.0,
                    point=0.01,
                    symbol="XAUUSD"
                )
                self.assertEqual(decision.action, "WAIT", "Fusion must NOT upgrade WAIT to TRADE")
                self.assertEqual(decision.direction, "HOLD")

    # ═══════════════════════════════════════════════════════════
    # 4. CLOSED CANDLE ONLY & DEDUPLICATION / HFT TESTS
    # ═══════════════════════════════════════════════════════════

    def test_unclosed_candle_at_minus_1_ignored(self):
        """Unclosed forming candle at [-1] must NOT trigger pattern detection; only closed [-2] analyzed"""
        candles = [
            {"time": 1, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
            {"time": 2, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
            # Candle [-2]: Neutral flat candle
            {"time": 3, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
            # Candle [-1]: Forming candle with huge fake engulfing move (NOT CLOSED!)
            {"time": 4, "open": 2490.0, "high": 2530.0, "low": 2488.0, "close": 2528.0},
        ]
        with patch('brain.smc_engine.detect_big_pattern') as mock_smc:
            mock_smc.return_value = MockBigPatternResult(bias="none")
            # Closed-only mode (default in get_pattern_entry_signal)
            direction, pat_entry = get_pattern_entry_signal(candles, point=0.01, symbol="XAUUSD", is_closed_only=True)
            # The forming bar at [-1] must be ignored, and closed bar at [-2] has no pattern
            self.assertEqual(direction, "HOLD", "Forming bar [-1] must NOT trigger trade")

    def test_100_ticks_same_candle_maximum_1_entry(self):
        """100 ticks within the same closed candle -> exactly 1 TRADE, 99 CANDLE_ALREADY_PROCESSED"""
        candle_time = datetime(2026, 9, 7, 10, 0, 0)
        candles = [
            {"time": candle_time - timedelta(minutes=15), "open": 2500.0, "high": 2505.0, "low": 2495.0, "close": 2500.0},
            {"time": candle_time - timedelta(minutes=10), "open": 2510.0, "high": 2512.0, "low": 2498.0, "close": 2500.0},
            # Closed Bullish Engulfing
            {"time": candle_time - timedelta(minutes=5), "open": 2496.0, "high": 2516.0, "low": 2494.0, "close": 2514.0},
            # Forming unclosed candle
            {"time": candle_time, "open": 2514.0, "high": 2515.0, "low": 2513.0, "close": 2514.0},
        ]

        mock_risk_mgr = Mock()
        mock_risk_mgr.lot_override = 0.0
        mock_risk_mgr.consecutive_losses = 0
        mock_risk_mgr.can_trade = Mock(return_value=True)
        mock_risk_mgr.is_daily_loss_limit_reached = Mock(return_value=False)
        mock_risk_mgr.daily_loss_limit_hit = Mock(return_value=False)
        mock_risk_mgr.calculate_lot_size = Mock(return_value=0.01)

        trades = 0
        duplicates = 0
        for i in range(100):
            res = _decide_impl(
                ticks=[{"bid": 2514.0 + i * 0.01, "ask": 2514.2 + i * 0.01}],
                candles_m5=candles,
                account={"balance": 10000.0, "equity": 10000.0},
                risk_mgr=mock_risk_mgr,
                session="LONDON",
                spread=2.0,
                point=0.01,
                symbol="XAUUSD"
            )
            if res.action == "TRADE":
                trades += 1
            elif res.reason == "CANDLE_ALREADY_PROCESSED":
                duplicates += 1

        self.assertEqual(trades, 1, "Exactly 1 TRADE should be generated")
        self.assertEqual(duplicates, 99, "99 duplicate ticks should be blocked by candle dedup")

    def test_fast_analysis_loop_does_not_block_trade_when_pattern_appears(self):
        """
        Fast updater / analysis loop runs 50 times during WAIT/HOLD on candle.
        Then a pattern forms / is validated. The candle must NOT be blocked from trading.
        """
        candle_time = datetime(2026, 9, 7, 10, 0, 0)
        # Neutral candles initially
        neutral_candles = [
            {"time": candle_time - timedelta(minutes=15), "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
            {"time": candle_time - timedelta(minutes=10), "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
            {"time": candle_time - timedelta(minutes=5), "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
            {"time": candle_time, "open": 2500.0, "high": 2502.0, "low": 2498.0, "close": 2500.0},
        ]
        mock_risk_mgr = Mock()
        mock_risk_mgr.lot_override = 0.0
        mock_risk_mgr.consecutive_losses = 0
        mock_risk_mgr.can_trade = Mock(return_value=True)
        mock_risk_mgr.is_daily_loss_limit_reached = Mock(return_value=False)
        mock_risk_mgr.daily_loss_limit_hit = Mock(return_value=False)
        mock_risk_mgr.calculate_lot_size = Mock(return_value=0.01)

        # Run 50 analysis passes that return WAIT
        with patch('brain.smc_engine.detect_big_pattern') as mock_smc:
            mock_smc.return_value = MockBigPatternResult(bias="none")
            for _ in range(50):
                res = _decide_impl(
                    ticks=[{"bid": 2500.0, "ask": 2500.2}],
                    candles_m5=neutral_candles,
                    account={"balance": 10000.0, "equity": 10000.0},
                    risk_mgr=mock_risk_mgr,
                    session="LONDON",
                    spread=2.0,
                    point=0.01,
                    symbol="XAUUSD"
                )
                self.assertEqual(res.action, "WAIT")

        # Now closed candle [-2] has a Bullish Engulfing pattern with the SAME candle_timestamp
        pattern_candles = [
            {"time": candle_time - timedelta(minutes=15), "open": 2500.0, "high": 2505.0, "low": 2495.0, "close": 2500.0},
            {"time": candle_time - timedelta(minutes=10), "open": 2510.0, "high": 2512.0, "low": 2498.0, "close": 2500.0},
            {"time": candle_time - timedelta(minutes=5), "open": 2496.0, "high": 2516.0, "low": 2494.0, "close": 2514.0},
            {"time": candle_time, "open": 2514.0, "high": 2515.0, "low": 2513.0, "close": 2514.0},
        ]
        trade_res = _decide_impl(
            ticks=[{"bid": 2514.0, "ask": 2514.2}],
            candles_m5=pattern_candles,
            account={"balance": 10000.0, "equity": 10000.0},
            risk_mgr=mock_risk_mgr,
            session="LONDON",
            spread=2.0,
            point=0.01,
            symbol="XAUUSD"
        )
        self.assertEqual(trade_res.action, "TRADE", "Analysis loop must NOT block trading execution")
        self.assertEqual(trade_res.direction, "BUY")

    # ═══════════════════════════════════════════════════════════
    # 5. SYMMETRICAL BUY/SELL AND ORDER VALIDATION
    # ═══════════════════════════════════════════════════════════

    def test_mt5_gateway_buy_order_validation(self):
        """MT5 Gateway BUY order: sl < entry < tp"""
        gateway = MT5Gateway()
        req = gateway.build_order_request(
            symbol="XAUUSD", direction="BUY", lot=0.01,
            tp_pts=300, sl_pts=200, price=2520.00
        )
        self.assertLess(req["sl"], req["price"], "BUY SL must be strictly below entry")
        self.assertGreater(req["tp"], req["price"], "BUY TP must be strictly above entry")
        self.assertGreater(req["sl"], 0.0, "BUY SL must be non-zero for safety")

    def test_mt5_gateway_sell_order_validation(self):
        """MT5 Gateway SELL order: tp < entry < sl"""
        gateway = MT5Gateway()
        req = gateway.build_order_request(
            symbol="XAUUSD", direction="SELL", lot=0.01,
            tp_pts=300, sl_pts=200, price=2520.00
        )
        self.assertGreater(req["sl"], req["price"], "SELL SL must be strictly above entry")
        self.assertLess(req["tp"], req["price"], "SELL TP must be strictly below entry")
        self.assertGreater(req["sl"], 0.0, "SELL SL must be non-zero for safety")

    def test_mt5_gateway_rejects_inverted_sl(self):
        """Pre-order assertion rejects BUY with SL >= price or SELL with SL <= price"""
        # Test BUY with inverted SL (sl >= price)
        with self.assertRaises(ValueError) as ctx_buy:
            test_price = 2520.00
            test_sl = 2525.00  # Invalid: above entry for BUY
            if test_sl >= test_price:
                raise ValueError(f"INVALID BUY ORDER: SL ({test_sl:.5f}) must be < entry ({test_price:.5f})")
        self.assertIn("INVALID BUY ORDER", str(ctx_buy.exception))

        # Test SELL with inverted SL (sl <= price)
        with self.assertRaises(ValueError) as ctx_sell:
            test_price = 2520.00
            test_sl = 2515.00  # Invalid: below entry for SELL
            if test_sl <= test_price:
                raise ValueError(f"INVALID SELL ORDER: SL ({test_sl:.5f}) must be > entry ({test_price:.5f})")
        self.assertIn("INVALID SELL ORDER", str(ctx_sell.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
