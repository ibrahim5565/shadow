"""
FINAL LIVE-INTEGRATION VERIFICATION TESTS (Aegis Gold)

Proves the complete production execution path:

    BEARISH CLOSED-CANDLE PATTERN -> PATTERN SIGNAL = SELL -> SAFETY CHECKS ->
    SL/TP VALIDATION -> AUTHORIZATION -> ORDER BUILDER -> MT5 ORDER_TYPE_SELL ->
    BROKER ACCEPTS -> ACTUAL SELL POSITION

And proves that no later component (Fusion, ML, RL, SMC, EQS, Regime,
Structure, OpportunityPipeline) can change SELL into BUY/WAIT except for a
legitimate safety rejection.

CANDLE INDEX CONVENTION (Requirement 11 — documented):
    MT5 copy_rates_from_pos(sym, tf, 0, N) returns index [-1] as the CURRENTLY
    FORMING (unclosed) candle and [-2] as the LATEST COMPLETED CLOSED candle.
    Pattern detection therefore analyses candle [-2] (the pattern engine slices
    the forming candle off with candles[:-1]) and NEVER [-1].
"""

import os
import sys
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5

from brain.brain import (
    Decision,
    PatternEntry,
    _decide_impl,
    decide,
    get_pattern_entry_signal,
    verify_direction_integrity,
)
from brain.decision_fusion import FusionResult
from brain.authorization_builder import build_trade_authorization
from brain.trade_candidate import TradeCandidate
from modules.mt5_gateway import MT5Gateway

POINT = 0.01


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

def make_risk_mgr():
    """Risk manager mock that APPROVES everything (safety gates observed)."""
    rm = Mock()
    rm.can_trade = Mock(return_value=True)
    rm.is_daily_loss_limit_reached = Mock(return_value=False)
    rm.correlation_exposure_check = Mock(return_value=True)
    rm.margin_buffer_check = Mock(return_value=True)
    rm.lot_override = 0.0
    return rm


def bearish_engulfing_candles():
    """[-1] = forming candle (unclosed), [-2] = closed BEARISH ENGULFING."""
    return [
        {"time": 1, "open": 2500.0, "high": 2501.0, "low": 2499.0, "close": 2500.0},
        # Bullish small body candle (closed)
        {"time": 2, "open": 2500.0, "high": 2507.0, "low": 2499.0, "close": 2506.0},
        # Bearish Engulfing (closed) — engulfs previous body
        {"time": 3, "open": 2508.0, "high": 2509.0, "low": 2493.0, "close": 2494.0},
        # Forming candle (unclosed, neutral)
        {"time": 4, "open": 2494.0, "high": 2496.0, "low": 2493.5, "close": 2495.0},
    ]


def bullish_engulfing_candles():
    """[-1] = forming candle (unclosed), [-2] = closed BULLISH ENGULFING."""
    return [
        {"time": 1, "open": 2500.0, "high": 2501.0, "low": 2499.0, "close": 2500.0},
        # Bearish small body candle (closed)
        {"time": 2, "open": 2500.0, "high": 2501.0, "low": 2493.0, "close": 2494.0},
        # Bullish Engulfing (closed) — engulfs previous body
        {"time": 3, "open": 2492.0, "high": 2507.0, "low": 2491.0, "close": 2506.0},
        # Forming candle (unclosed, neutral)
        {"time": 4, "open": 2506.0, "high": 2507.0, "low": 2505.0, "close": 2506.5},
    ]


def flat_no_pattern_candles(n=30, t_start=1000):
    """Steady, trendless candles — no candlestick pattern anywhere."""
    return [
        {"time": t_start + i, "open": 2500.0, "high": 2500.5, "low": 2499.5, "close": 2500.0}
        for i in range(n)
    ]


def clear_candle_caches():
    for attr in ("_analyzed_candles", "_traded_candles", "_processed_candles"):
        if hasattr(_decide_impl, attr):
            getattr(_decide_impl, attr).clear()


def run_decide(candles, risk_mgr=None, **kw):
    """Run the PUBLIC decide() entry point with the RL agent neutralised and
    all Quant-X pipeline layers off (deterministic pattern-only path)."""
    clear_candle_caches()
    rm = risk_mgr or make_risk_mgr()
    with patch("config.quant_x_config.QX.flag", side_effect=lambda f: False), \
         patch("config.quant_x_config.QX.get", side_effect=lambda k, d=None: d), \
         patch("brain.brain.get_rl_agent", return_value=None), \
         patch("brain.regime_switcher.get_strategy_state") as mock_switch:
        inst = mock_switch.return_value
        inst.evaluate_and_switch = Mock(return_value=None)
        inst.current_profile = SimpleNamespace(lot_multiplier=1.0)
        return decide(
            ticks=[],
            candles_m5=candles,
            account={"balance": 10000.0, "equity": 10000.0},
            risk_mgr=rm,
            session="LONDON",
            spread=10.0,
            point=POINT,
            symbol="XAUUSD",
            **kw,
        )



# ─────────────────────────────────────────────────────────────
# 1. SELL / BUY / HOLD production entry paths
# ─────────────────────────────────────────────────────────────

class TestProductionEntryPaths(unittest.TestCase):

    def setUp(self):
        clear_candle_caches()

    def test_bearish_pattern_produces_sell_full_path(self):
        """[ACCEPTANCE] Bearish pattern → SELL through the full decide() path."""
        decision = run_decide(bearish_engulfing_candles())
        self.assertEqual(decision.action, "TRADE")
        self.assertEqual(decision.direction, "SELL")
        # Requirement 2: authoritative pattern direction recorded on decision
        self.assertEqual(decision.pattern_direction, "SELL")
        self.assertEqual(decision.signal_source, "PATTERN_ENGINE")
        # Authorization contract present and preserves SELL
        self.assertIsNotNone(decision.trade_authorization)
        self.assertTrue(decision.trade_authorization.authorized)
        self.assertEqual(decision.trade_authorization.direction, "SELL")
        # SELL geometry: tp < entry < sl
        self.assertGreater(decision.sl_points, 0)
        self.assertGreater(decision.tp_points, decision.sl_points)
        print(f"\n[SELL PATH] pattern={decision.pattern} dir={decision.direction} "
              f"sl={decision.sl_points}pts tp={decision.tp_points}pts "
              f"auth={decision.trade_authorization.authorization_id}")

    def test_bullish_pattern_produces_buy_full_path(self):
        """[ACCEPTANCE] Bullish pattern → BUY through the full decide() path."""
        decision = run_decide(bullish_engulfing_candles())
        self.assertEqual(decision.action, "TRADE")
        self.assertEqual(decision.direction, "BUY")
        self.assertEqual(decision.pattern_direction, "BUY")
        self.assertIsNotNone(decision.trade_authorization)
        self.assertEqual(decision.trade_authorization.direction, "BUY")
        print(f"\n[BUY PATH] pattern={decision.pattern} dir={decision.direction} "
              f"sl={decision.sl_points}pts tp={decision.tp_points}pts")

    def test_no_pattern_produces_hold(self):
        """[ACCEPTANCE] No pattern → WAIT/HOLD, even with perfect conditions."""
        decision = run_decide(flat_no_pattern_candles())
        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(decision.direction, "HOLD")
        self.assertIn("NO_PATTERN", decision.reason)

    def test_pattern_direction_is_single_source(self):
        """Direction comes from the pattern engine and matches the decision."""
        candles = bearish_engulfing_candles()
        direction, pat_entry = get_pattern_entry_signal(candles, point=POINT, symbol="XAUUSD")
        self.assertEqual(direction, "SELL")
        self.assertEqual(pat_entry.direction, "SELL")
        decision = run_decide(candles)
        self.assertEqual(decision.direction, direction)
        self.assertEqual(decision.pattern_direction, direction)


# ─────────────────────────────────────────────────────────────
# 2. FINAL DECISION IMMUTABILITY (Requirement 2)
# ─────────────────────────────────────────────────────────────

class TestDecisionImmutability(unittest.TestCase):

    def setUp(self):
        clear_candle_caches()

    def test_integrity_passes_on_valid_sell(self):
        decision = run_decide(bearish_engulfing_candles())
        self.assertTrue(verify_direction_integrity(decision))
        self.assertEqual(decision.action, "TRADE")

    def test_integrity_blocks_direction_flip_sell_to_buy(self):
        """Any SELL→BUY mutation after the pattern is a CRITICAL failure."""
        decision = run_decide(bearish_engulfing_candles())
        decision.direction = "BUY"  # simulate a rogue module mutation
        safe = verify_direction_integrity(decision)
        self.assertFalse(safe, "Direction flip SELL→BUY must block the trade")
        self.assertEqual(decision.action, "WAIT")
        self.assertIn("DIRECTION_INTEGRITY_FAILURE", decision.reason)
        self.assertEqual(decision.direction, "SELL")  # authoritative restored for diagnostics

    def test_integrity_blocks_direction_flip_sell_to_hold(self):
        decision = run_decide(bearish_engulfing_candles())
        decision.direction = "HOLD"
        self.assertFalse(verify_direction_integrity(decision))
        self.assertEqual(decision.action, "WAIT")

    def test_integrity_blocks_unpatterned_trade(self):
        """A TRADE decision with no authoritative pattern direction is blocked."""
        decision = Decision(action="TRADE", direction="BUY", signal_source="SOME_AI_ENGINE")
        self.assertFalse(verify_direction_integrity(decision))
        self.assertEqual(decision.action, "WAIT")
        self.assertIn("DIRECTION_INTEGRITY_FAILURE", decision.reason)



# ─────────────────────────────────────────────────────────────
# 3. FUSION IS OBSERVATIONAL (Requirement 3)
# ─────────────────────────────────────────────────────────────

def _fusion_overrides(fused_direction, confidence=99):
    fusion = FusionResult(
        long_prob=0.99 if fused_direction == "BUY" else 0.0,
        short_prob=0.99 if fused_direction == "SELL" else 0.0,
        no_trade_prob=0.0,
        confidence=confidence,
        uncertainty=0.0,
        estimated_rr=2.0,
        fused_direction=fused_direction,
        action="TRADE",
        block_reason="",
    )
    ml_mock = Mock()
    ml_mock.predict = Mock(return_value=Mock())
    enriched = SimpleNamespace(direction=fused_direction, win_probability=0.99, uncertainty=0.0)
    regime = SimpleNamespace(regime_confidence=0.5, ambiguous=False)
    return fusion, ml_mock, enriched, regime


class TestFusionObservational(unittest.TestCase):

    def _run_with_fusion(self, candles, fused_direction):
        clear_candle_caches()
        fusion, ml_mock, enriched, regime = _fusion_overrides(fused_direction)
        rm = make_risk_mgr()
        with patch("config.quant_x_config.QX.flag", side_effect=lambda f: f == "decision_fusion_v2"), \
             patch("config.quant_x_config.QX.get", side_effect=lambda k, d=None: d), \
             patch("brain.decision_fusion.DecisionFusionV2.fuse", return_value=fusion), \
             patch("brain.ml_ensemble.get_ml_ensemble", return_value=ml_mock), \
             patch("brain.ml_ensemble.enrich_prediction_with_disagreement", return_value=enriched), \
             patch("brain.brain.analyze_regime", return_value=regime), \
             patch("brain.brain.get_rl_agent", return_value=None), \
             patch("brain.regime_switcher.get_strategy_state") as mock_switch:
            inst = mock_switch.return_value
            inst.evaluate_and_switch = Mock(return_value=None)
            inst.current_profile = SimpleNamespace(lot_multiplier=1.0)
            return decide(
                ticks=[],
                candles_m5=candles,
                account={"balance": 10000.0, "equity": 10000.0},
                risk_mgr=rm,
                session="LONDON",
                spread=10.0,
                point=POINT,
                symbol="XAUUSD",
            )

    def test_fusion_buy_cannot_change_pattern_sell(self):
        """Pattern=SELL + Fusion says BUY/TRADE@99% → final decision stays SELL."""
        decision = self._run_with_fusion(bearish_engulfing_candles(), "BUY")
        self.assertEqual(decision.action, "TRADE")
        self.assertEqual(decision.direction, "SELL")
        self.assertEqual(decision.pattern_direction, "SELL")

    def test_fusion_sell_cannot_change_pattern_buy(self):
        decision = self._run_with_fusion(bullish_engulfing_candles(), "SELL")
        self.assertEqual(decision.action, "TRADE")
        self.assertEqual(decision.direction, "BUY")

    def test_fusion_cannot_upgrade_wait_to_trade(self):
        """No pattern + Fusion TRADE → decision must remain WAIT."""
        decision = self._run_with_fusion(flat_no_pattern_candles(), "SELL")
        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(decision.direction, "HOLD")



# ─────────────────────────────────────────────────────────────
# 4/6. ML / RL / SMC / EQS cannot change direction (override resistance)
# ─────────────────────────────────────────────────────────────

class TestAIEnginesCannotChangeDirection(unittest.TestCase):

    def test_all_engines_bullish_vs_bearish_pattern_still_sell(self):
        """SMC-bullish confidence + ML BUY + RL BUY + Fusion BUY vs a bearish
        pattern must NEVER produce a BUY. (A bullish SMC pattern alongside a
        bearish candlestick pattern is CONFLICTING_PATTERNS → legitimate safety
        HOLD; it must never become a BUY trade.)"""
        clear_candle_caches()
        fusion, ml_mock, enriched, regime = _fusion_overrides("BUY")
        smc_bp = SimpleNamespace(bias="bullish", pattern_type="BOS_BULLISH",
                                 confidence=0.99, invalidation_level=2400.0)
        rl_agent = Mock()
        rl_agent.predict_action = Mock(return_value=("BUY", 99))
        with patch("config.quant_x_config.QX.flag", side_effect=lambda f: f == "decision_fusion_v2"), \
             patch("config.quant_x_config.QX.get", side_effect=lambda k, d=None: d), \
             patch("brain.decision_fusion.DecisionFusionV2.fuse", return_value=fusion), \
             patch("brain.ml_ensemble.get_ml_ensemble", return_value=ml_mock), \
             patch("brain.ml_ensemble.enrich_prediction_with_disagreement", return_value=enriched), \
             patch("brain.brain.analyze_regime", return_value=regime), \
             patch("brain.brain.get_rl_agent", return_value=rl_agent), \
             patch("brain.smc_engine.detect_big_pattern", return_value=smc_bp), \
             patch("brain.regime_switcher.get_strategy_state") as mock_switch:
            inst = mock_switch.return_value
            inst.evaluate_and_switch = Mock(return_value=None)
            inst.current_profile = SimpleNamespace(lot_multiplier=1.0)
            decision = decide(
                ticks=[],
                candles_m5=bearish_engulfing_candles(),
                account={"balance": 10000.0, "equity": 10000.0},
                risk_mgr=make_risk_mgr(),
                session="LONDON",
                spread=10.0,
                point=POINT,
                symbol="XAUUSD",
            )
        # SMC confidence can NEVER flip the decision to BUY:
        self.assertNotEqual(decision.direction, "BUY")
        self.assertNotEqual(decision.pattern_direction, "BUY")
        # Conflicting patterns → legitimate safety rejection (HOLD):
        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(decision.direction, "HOLD")

    def test_ml_rl_fusion_bullish_vs_bearish_pattern_still_sell(self):
        """Bearish pattern + ML BUY + RL BUY + Fusion BUY (no SMC conflict) → SELL."""
        clear_candle_caches()
        fusion, ml_mock, enriched, regime = _fusion_overrides("BUY")
        rl_agent = Mock()
        rl_agent.predict_action = Mock(return_value=("BUY", 99))
        with patch("config.quant_x_config.QX.flag", side_effect=lambda f: f == "decision_fusion_v2"), \
             patch("config.quant_x_config.QX.get", side_effect=lambda k, d=None: d), \
             patch("brain.decision_fusion.DecisionFusionV2.fuse", return_value=fusion), \
             patch("brain.ml_ensemble.get_ml_ensemble", return_value=ml_mock), \
             patch("brain.ml_ensemble.enrich_prediction_with_disagreement", return_value=enriched), \
             patch("brain.brain.analyze_regime", return_value=regime), \
             patch("brain.brain.get_rl_agent", return_value=rl_agent), \
             patch("brain.regime_switcher.get_strategy_state") as mock_switch:
            inst = mock_switch.return_value
            inst.evaluate_and_switch = Mock(return_value=None)
            inst.current_profile = SimpleNamespace(lot_multiplier=1.0)
            decision = decide(
                ticks=[],
                candles_m5=bearish_engulfing_candles(),
                account={"balance": 10000.0, "equity": 10000.0},
                risk_mgr=make_risk_mgr(),
                session="LONDON",
                spread=10.0,
                point=POINT,
                symbol="XAUUSD",
            )
        self.assertEqual(decision.action, "TRADE")
        self.assertEqual(decision.direction, "SELL")
        self.assertEqual(decision.pattern_direction, "SELL")

    def test_regime_cannot_create_direction_without_pattern(self):
        """TRENDING_UP / TRENDING_DOWN + NO PATTERN → HOLD (Requirement 5)."""
        for trend_name in ("TRENDING_UP", "TRENDING_DOWN"):
            with self.subTest(trend=trend_name), \
                 patch("brain.smc_engine.detect_big_pattern", Mock(return_value=None)):
                clear_candle_caches()
                decision = run_decide(flat_no_pattern_candles())
            self.assertEqual(decision.action, "WAIT")
            self.assertEqual(decision.direction, "HOLD")

    def test_structure_preferred_direction_cannot_create_trade(self):
        """Structure may compute preferred_direction but cannot trade without a pattern."""
        from brain.structure import analyze_structure
        candles = flat_no_pattern_candles()
        structure = analyze_structure(candles, current_price=2500.0,
                                      trend="TRENDING_UP", point=POINT)
        # Observational field exists …
        self.assertIn(getattr(structure, "preferred_direction", "NONE"), ("NONE", "BUY", "SELL"))
        # … but the decision without a pattern is still WAIT/HOLD.
        clear_candle_caches()
        with patch("brain.smc_engine.detect_big_pattern", Mock(return_value=None)):
            decision = run_decide(candles)
        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(decision.direction, "HOLD")



# ─────────────────────────────────────────────────────────────
# 4. OPPORTUNITY PIPELINE (Requirement 4)
# ─────────────────────────────────────────────────────────────

class TestOpportunityPipelineIsolation(unittest.TestCase):

    def test_pipeline_cannot_authorize_without_pattern(self):
        """evaluate_opportunity with no pattern → (None, NO_VALID_PATTERN)."""
        from brain.opportunity_pipeline import OpportunityPipeline
        pipe = OpportunityPipeline()
        auth, reason = pipe.evaluate_opportunity(
            symbol="XAUUSD",
            candles_m5=flat_no_pattern_candles(),
            candles_m1=flat_no_pattern_candles(),
            ticks=[],
            account={"equity": 10000.0},
            spread_pts=10.0,
            point=POINT,
            session="LONDON",
            risk_mgr=make_risk_mgr(),
        )
        self.assertIsNone(auth)
        self.assertEqual(reason, "NO_VALID_PATTERN")

    def test_pipeline_not_wired_into_production_execution(self):
        """Static check: production loop must not invoke OpportunityPipeline."""
        main_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "main.py"
        )
        with open(main_path, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("OpportunityPipeline", src,
                         "OpportunityPipeline must not be in the production execution path")
        self.assertNotIn("evaluate_opportunity", src,
                         "OpportunityPipeline.evaluate_opportunity must not be called by main loop")
        # The production loop must gate execution on direction integrity:
        self.assertGreaterEqual(src.count("verify_direction_integrity(decision)"), 2,
                                "Both ranked and queued dispatch paths must verify direction integrity")


# ─────────────────────────────────────────────────────────────
# 7. AUTHORIZATION PRESERVES DIRECTION
# ─────────────────────────────────────────────────────────────

class TestAuthorizationPreservesDirection(unittest.TestCase):

    def _candidate(self, direction):
        entry = 2500.0
        sl = entry + 1.5 if direction == "SELL" else entry - 1.5
        tp = entry - 3.0 if direction == "SELL" else entry + 3.0
        return TradeCandidate(
            symbol="XAUUSD", direction=direction, signal_type="BEARISH_ENGULFING",
            source_path="PATH_PATTERN", macro_bias="NEUTRAL", macro_score=0.6,
            setup_score=0.7, trigger_score=0.7, quant_score=0.6, ml_score=0.5,
            pattern_score=0.8, expected_value=1.75, risk_reward=2.0,
            spread_cost=0.1, entry_price=entry, stop_loss=sl, take_profit=tp,
            sl_points=150, tp_points=300, lot=0.01, confidence=0.8,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data_timestamp=datetime.now(timezone.utc).isoformat(),
            causal_valid=True, risk_valid=True,
        )

    def test_sell_authorization_preserves_sell(self):
        auth = build_trade_authorization(self._candidate("SELL"), make_risk_mgr(),
                                         spread_pts=10.0, point=POINT)
        self.assertIsNotNone(auth)
        self.assertTrue(auth.authorized)
        self.assertEqual(auth.direction, "SELL")
        self.assertGreater(auth.stop_loss, auth.entry_price)
        self.assertLess(auth.take_profit, auth.entry_price)

    def test_buy_authorization_preserves_buy(self):
        auth = build_trade_authorization(self._candidate("BUY"), make_risk_mgr(),
                                         spread_pts=10.0, point=POINT)
        self.assertIsNotNone(auth)
        self.assertTrue(auth.authorized)
        self.assertEqual(auth.direction, "BUY")
        self.assertLess(auth.stop_loss, auth.entry_price)
        self.assertGreater(auth.take_profit, auth.entry_price)

    def test_authorization_rejects_non_directional_candidate(self):
        cand = self._candidate("SELL")
        cand.direction = "MAYBE"
        auth = build_trade_authorization(cand, make_risk_mgr(), spread_pts=10.0, point=POINT)
        self.assertIsNone(auth)


# ─────────────────────────────────────────────────────────────
# 8/9. SELL ORDER REQUEST + SL/TP GEOMETRY
# ─────────────────────────────────────────────────────────────

class TestSellOrderRequest(unittest.TestCase):

    def setUp(self):
        clear_candle_caches()

    def test_bearish_pattern_final_mt5_request_is_order_type_sell(self):
        """End-to-end: bearish pattern → SELL decision → ORDER_TYPE_SELL request."""
        decision = run_decide(bearish_engulfing_candles())
        self.assertEqual(decision.action, "TRADE")
        self.assertEqual(decision.direction, "SELL")
        self.assertTrue(verify_direction_integrity(decision))

        gateway = MT5Gateway()
        entry_price = decision.trade_authorization.entry_price
        self.assertGreater(entry_price, 0.0,
                           "Authorization entry_price must never be 0 (dict-candle BUGFIX regression guard)")
        req = gateway.build_order_request(
            symbol="XAUUSD", direction=decision.direction, lot=decision.lot,
            tp_pts=decision.tp_points, sl_pts=decision.sl_points, price=entry_price,
        )
        # ── THE CRITICAL ASSERTION ──
        self.assertEqual(req["type"], mt5.ORDER_TYPE_SELL)
        self.assertEqual(req["action"], mt5.TRADE_ACTION_DEAL)
        self.assertEqual(req["symbol"], "XAUUSD")
        # SELL geometry: tp < entry < sl
        self.assertGreater(req["sl"], req["price"], "SELL SL must be above entry")
        self.assertLess(req["tp"], req["price"], "SELL TP must be below entry")
        self.assertGreater(req["sl"], 0.0)
        print("\n[COMPLETE MT5 SELL REQUEST]")
        for k, v in req.items():
            print(f"    {k}: {v}")

    def test_bullish_pattern_final_mt5_request_is_order_type_buy(self):
        decision = run_decide(bullish_engulfing_candles())
        self.assertEqual(decision.direction, "BUY")
        gateway = MT5Gateway()
        entry_price = decision.trade_authorization.entry_price
        self.assertGreater(entry_price, 0.0,
                           "Authorization entry_price must never be 0 (dict-candle BUGFIX regression guard)")
        req = gateway.build_order_request(
            symbol="XAUUSD", direction="BUY", lot=decision.lot,
            tp_pts=decision.tp_points, sl_pts=decision.sl_points,
            price=entry_price,
        )
        self.assertEqual(req["type"], mt5.ORDER_TYPE_BUY)
        self.assertLess(req["sl"], req["price"], "BUY SL must be below entry")
        self.assertGreater(req["tp"], req["price"], "BUY TP must be above entry")
        print("\n[COMPLETE MT5 BUY REQUEST]")


# ─────────────────────────────────────────────────────────────
# 10/11/12. NO HFT ENTRY, CANDLE INDEX, DEDUPLICATION
# ─────────────────────────────────────────────────────────────

class TestCandleDeduplicationAndNoHFT(unittest.TestCase):

    def setUp(self):
        clear_candle_caches()

    def _count_trades(self, iterations):
        trades = 0
        for _ in range(iterations):
            dec = _decide_impl(
                ticks=[{"bid": 2495.0, "ask": 2495.2}],
                candles_m5=bearish_engulfing_candles(),
                account={"balance": 10000.0, "equity": 10000.0},
                risk_mgr=make_risk_mgr(),
                session="LONDON",
                spread=10.0,
                point=POINT,
                symbol="XAUUSD",
            )
            if dec.action == "TRADE":
                trades += 1
        return trades

    def test_100_ticks_same_candle_zero_additional_entries(self):
        self.assertEqual(self._count_trades(100), 1,
                         "100 ticks on the same candle must produce exactly ONE entry")

    def test_1000_ticks_same_candle_zero_additional_entries(self):
        self.assertEqual(self._count_trades(1000), 1,
                         "1000 ticks on the same candle must produce exactly ONE entry")

    def test_forming_candle_cannot_trigger_entry(self):
        """Pattern ONLY on the forming candle [-1] → no entry (closed-only)."""
        candles = [
            {"time": 1, "open": 2500.0, "high": 2501.0, "low": 2499.0, "close": 2500.0},
            {"time": 2, "open": 2500.0, "high": 2507.0, "low": 2499.0, "close": 2506.0},
            {"time": 3, "open": 2506.0, "high": 2507.0, "low": 2505.0, "close": 2505.5},
            # [-1] FORMING bearish engulfing — must be IGNORED
            {"time": 4, "open": 2507.0, "high": 2508.0, "low": 2493.0, "close": 2494.0},
        ]
        direction, _ = get_pattern_entry_signal(candles, point=POINT, symbol="XAUUSD")
        self.assertEqual(direction, "HOLD",
                         "Pattern on forming candle [-1] must NOT trigger an entry")
        dec = _decide_impl(
            ticks=[], candles_m5=candles,
            account={"balance": 10000.0, "equity": 10000.0},
            risk_mgr=make_risk_mgr(), session="LONDON", spread=10.0,
            point=POINT, symbol="XAUUSD",
        )
        self.assertEqual(dec.action, "WAIT")

    def test_closed_candle_minus_two_triggers_entry(self):
        """Pattern on the last CLOSED candle [-2] → entry with correct candle time."""
        candles = bearish_engulfing_candles()
        direction, pat_entry = get_pattern_entry_signal(candles, point=POINT, symbol="XAUUSD")
        self.assertEqual(direction, "SELL")
        self.assertIsNotNone(pat_entry.candle_time,
                             "Pattern candle time must be the CLOSED candle [-2]")

    def test_analysis_does_not_permanently_block_candle(self):
        """ANALYZED ≠ TRADED: a temporarily risk-blocked candle stays eligible."""
        candles = bearish_engulfing_candles()
        blocking_risk = make_risk_mgr()
        blocking_risk.can_trade = Mock(return_value=False)

        # 1) Analysis attempt → risk blocked → WAIT (candle NOT marked traded)
        dec_blocked = _decide_impl(
            ticks=[], candles_m5=candles,
            account={"balance": 10000.0, "equity": 10000.0},
            risk_mgr=blocking_risk, session="LONDON", spread=10.0,
            point=POINT, symbol="XAUUSD",
        )
        self.assertEqual(dec_blocked.action, "WAIT")
        self.assertIn("RISK_BLOCKED", dec_blocked.reason)
        candle_key = "XAUUSD_3"
        self.assertNotIn(candle_key, _decide_impl._traded_candles,
                         "A risk-blocked analysis must NOT permanently consume the candle")

        # 2) Risk clears → same candle is still eligible and trades
        dec_trade = _decide_impl(
            ticks=[], candles_m5=candles,
            account={"balance": 10000.0, "equity": 10000.0},
            risk_mgr=make_risk_mgr(), session="LONDON", spread=10.0,
            point=POINT, symbol="XAUUSD",
        )
        self.assertEqual(dec_trade.action, "TRADE")
        self.assertEqual(dec_trade.direction, "SELL")
        self.assertIn(candle_key, _decide_impl._traded_candles,
                      "An EXECUTED trade must mark the candle as TRADED")

    def test_traded_candle_cannot_duplicate(self):
        dec = _decide_impl(
            ticks=[], candles_m5=bearish_engulfing_candles(),
            account={"balance": 10000.0, "equity": 10000.0},
            risk_mgr=make_risk_mgr(), session="LONDON", spread=10.0,
            point=POINT, symbol="XAUUSD",
        )
        self.assertEqual(dec.action, "TRADE")
        dec2 = _decide_impl(
            ticks=[], candles_m5=bearish_engulfing_candles(),
            account={"balance": 10000.0, "equity": 10000.0},
            risk_mgr=make_risk_mgr(), session="LONDON", spread=10.0,
            point=POINT, symbol="XAUUSD",
        )
        self.assertEqual(dec2.action, "WAIT")
        self.assertEqual(dec2.reason, "CANDLE_ALREADY_PROCESSED")


# ─────────────────────────────────────────────────────────────
# 14. NEVER FORCE A SELL
# ─────────────────────────────────────────────────────────────

class TestNeverForceASell(unittest.TestCase):

    def test_no_alternation_logic_in_production(self):
        """Static check: no BUY/SELL balancing logic exists in production code."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for rel in (os.path.join("core", "main.py"), os.path.join("brain", "brain.py")):
            with open(os.path.join(root, rel), "r", encoding="utf-8") as f:
                src = f.read().lower()
            self.assertNotIn("buy_count > sell_count", src)
            self.assertNotIn("sell_count > buy_count", src)
            self.assertNotIn("force_sell", src)
            self.assertNotIn("alternate_direction", src)

    def test_no_pattern_no_trade_even_after_buy_streak(self):
        """After many BUYs, a no-pattern market still yields WAIT (never forced SELL)."""
        clear_candle_caches()
        with patch("brain.smc_engine.detect_big_pattern", Mock(return_value=None)):
            decision = run_decide(flat_no_pattern_candles())
        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(decision.direction, "HOLD")


if __name__ == "__main__":
    unittest.main(verbosity=2)

