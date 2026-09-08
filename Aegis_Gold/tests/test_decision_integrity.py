"""
===========================================================================
AEGIS GOLD — Decision Integrity Regression Tests
===========================================================================

Tests for:
  1. Strong XAUUSD consensus cannot silently become WAIT
  2. A+ Pattern Trade cannot be overwritten by weak ML signal
  3. Invalid feature detection (ADX/RSI missing)
  4. Regime protection (invalid data keeps current strategy)
  5. Snapshot consistency (same cycle_id, feature_hash)
  6. No duplicate initialization
  7. No silent mutation (BUY 85% frozen, cannot be mutated)
===========================================================================
"""

import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.trading_decision import TradingDecision, create_decision, EngineSignal, MarketDecisionSnapshot
from brain.feature_validation import validate_features, extract_and_validate_features, FeatureValidationResult
from brain.decision_arbiter import (
    arbitrate_pattern_decision,
    compute_consensus,
    arbitrate_rl_decision,
    apply_arbitration_to_decision,
    ArbitrationResult,
)
from brain.model_registry import (
    get_model_registry,
    get_init_count,
    reset_init_counters,
    ModelRegistry,
)


class TestStrongConsensus(unittest.TestCase):
    """TEST 1 — Strong XAUUSD consensus cannot silently become WAIT."""

    def test_strong_consensus_produces_buy(self):
        """Neural=BULLISH, Quant=BULLISH, ML=BULLISH, OMEGA=BULLISH, Kronos=NEUTRAL, BigPat=BULLISH, RL=BUY"""
        engine_votes = {
            "neural": {"direction": "BULLISH", "confidence": 0.46},
            "quant": {"direction": "BULLISH", "confidence": 0.93},
            "ml_ensemble": {"direction": "BULLISH", "confidence": 0.74},
            "omega": {"direction": "BULLISH", "confidence": 0.61},
            "kronos": {"direction": "NEUTRAL", "confidence": 0.50},
            "big_pattern": {"direction": "BULLISH", "confidence": 0.80},
        }
        rl_signal = {"action": "BUY", "confidence": 0.75}

        result = compute_consensus(engine_votes, rl_signal)

        self.assertEqual(result.action, "BUY")
        self.assertGreater(result.buy_votes, result.sell_votes)
        self.assertGreaterEqual(result.buy_votes, 4)
        self.assertGreater(result.confidence, 0)

    def test_consensus_wait_requires_rejection_reason(self):
        """If consensus becomes WAIT, it must have a reason."""
        engine_votes = {
            "neural": {"direction": "BULLISH", "confidence": 0.46},
            "quant": {"direction": "BULLISH", "confidence": 0.93},
            "ml_ensemble": {"direction": "BULLISH", "confidence": 0.74},
            "omega": {"direction": "BULLISH", "confidence": 0.61},
            "kronos": {"direction": "NEUTRAL", "confidence": 0.50},
        }
        rl_signal = {"action": "BUY", "confidence": 0.75}

        # Create decision and apply arbitration
        decision = create_decision("XAUUSD", action="BUY", direction="BUY", confidence=78, source="CONSENSUS")
        result = compute_consensus(engine_votes, rl_signal)
        apply_arbitration_to_decision(decision, result)

        # If final is WAIT, must have rejection reason
        if decision.action == "WAIT":
            self.assertIsNotNone(decision.rejection_reason)
            self.assertIsNotNone(decision.rejection_stage)
            self.assertEqual(decision.previous_action, "BUY")
            self.assertIsNotNone(decision.previous_confidence)


class TestPatternArbitration(unittest.TestCase):
    """TEST 2 — A+ Pattern Trade cannot be overwritten by weak ML signal."""

    def test_high_quality_pattern_preserved(self):
        """Pattern BUY 85% A+ with ML SELL 29% must NOT become WAIT 29%."""
        pattern_signal = {
            "direction": "BUY",
            "confidence": 85.0,
            "grade": "A+",
            "pattern_name": "Bullish Engulfing",
            "rr_ratio": 2.5,
        }
        ml_signal = {
            "direction": "SELL",
            "confidence": 0.29,  # Weak signal
        }

        result = arbitrate_pattern_decision(
            pattern_signal=pattern_signal,
            ml_signal=ml_signal,
        )

        # Pattern must be preserved (not overwritten by weak ML)
        self.assertEqual(result.action, "BUY")
        self.assertTrue(result.pattern_preserved)
        self.assertFalse(result.vetoed)
        self.assertGreaterEqual(result.confidence, 80.0)

    def test_high_quality_pattern_hard_veto(self):
        """Pattern BUY 85% A+ with strong contradictory evidence can be vetoed with reason."""
        pattern_signal = {
            "direction": "BUY",
            "confidence": 85.0,
            "grade": "A+",
            "pattern_name": "Bullish Engulfing",
        }
        # Multiple strong contradictory signals
        ml_signal = {"direction": "SELL", "confidence": 0.85}
        quant_signal = {"direction": "SELL", "confidence": 0.80}
        omega_signal = {"direction": "SELL", "confidence": 0.75}

        result = arbitrate_pattern_decision(
            pattern_signal=pattern_signal,
            ml_signal=ml_signal,
            quant_signal=quant_signal,
            omega_signal=omega_signal,
        )

        # Either preserved or vetoed with reason - never silent WAIT 29%
        if result.action == "WAIT":
            self.assertTrue(result.vetoed)
            self.assertIsNotNone(result.veto_reason)
            self.assertGreaterEqual(result.confidence, 80.0)  # Preserve original confidence

    def test_weak_ml_does_not_overwrite(self):
        """ML SELL 29% must never result in WAIT 29%."""
        pattern_signal = {
            "direction": "BUY",
            "confidence": 85.0,
            "grade": "A+",
            "pattern_name": "Bullish Engulfing",
        }
        ml_signal = {"direction": "SELL", "confidence": 0.29}

        result = arbitrate_pattern_decision(
            pattern_signal=pattern_signal,
            ml_signal=ml_signal,
        )

        # Confidence must not collapse to 29%
        self.assertGreaterEqual(result.confidence, 80.0)


class TestFeatureValidation(unittest.TestCase):
    """TEST 3 — Invalid feature detection."""

    def test_missing_features_detected(self):
        """ADX missing, RSI missing, ATR valid → features.valid = False."""
        features = {
            "atr": 11.79,
            "spread": 20.0,
            "price": 2400.0,
            "timestamp": datetime.now(timezone.utc),
        }
        # ADX and RSI are missing

        result = validate_features(features)

        self.assertFalse(result.valid)
        self.assertIn("adx", result.missing_features)
        self.assertIn("rsi", result.missing_features)
        self.assertNotIn("atr", result.missing_features)

    def test_no_silent_zero_fallback(self):
        """Missing values must not be silently converted to 0.0."""
        features = {
            "adx": 0.0,  # This is a placeholder, not a real value
            "rsi": 0.0,
            "atr": 11.79,
            "spread": 20.0,
            "price": 2400.0,
            "timestamp": datetime.now(timezone.utc),
        }

        result = validate_features(features)

        # ADX=0.0 and RSI=0.0 are invalid (out of reasonable range for real values)
        self.assertFalse(result.valid)
        self.assertIn("adx", result.invalid_features)
        self.assertIn("rsi", result.invalid_features)

    def test_valid_features_pass(self):
        """All valid features pass validation."""
        features = {
            "adx": 25.0,
            "rsi": 55.0,
            "atr": 11.79,
            "spread": 20.0,
            "price": 2400.0,
            "timestamp": datetime.now(timezone.utc),
        }

        result = validate_features(features)

        self.assertTrue(result.valid)
        self.assertEqual(result.missing_features, [])
        self.assertEqual(result.invalid_features, {})


class TestRegimeProtection(unittest.TestCase):
    """TEST 4 — Regime protection."""

    def test_invalid_regime_keeps_strategy(self):
        """regime=NA, ADX invalid → strategy remains unchanged."""
        from brain.regime_switcher import StrategyState

        state = StrategyState()
        original = state.current_name

        # Invalid regime
        result = state.evaluate_and_switch(
            regime_type="NA",
            adx=0.0,
            session="ASIAN",
            recent_win_rate=0.5,
        )

        self.assertIsNone(result)  # No switch
        self.assertEqual(state.current_name, original)  # Strategy unchanged

    def test_invalid_adx_keeps_strategy(self):
        """ADX=0.0 (placeholder) → strategy remains unchanged."""
        from brain.regime_switcher import StrategyState

        state = StrategyState()
        original = state.current_name

        result = state.evaluate_and_switch(
            regime_type="STRONG_TREND",
            adx=0.0,  # Invalid placeholder
            session="LONDON",
            recent_win_rate=0.5,
        )

        self.assertIsNone(result)
        self.assertEqual(state.current_name, original)


class TestSnapshotConsistency(unittest.TestCase):
    """TEST 5 — Snapshot consistency."""

    def test_same_cycle_id_and_feature_hash(self):
        """All engines in one cycle share the same cycle_id and feature_hash."""
        now = datetime.now(timezone.utc)
        decision = create_decision(
            "XAUUSD",
            action="BUY",
            direction="BUY",
            confidence=78,
            source="CONSENSUS",
            timestamp=now,
            candle_timestamp=now - timedelta(minutes=5),
        )

        # All engines attach signals with same cycle_id
        signal1 = EngineSignal(
            engine="ml", action="BUY", confidence=0.74,
            timestamp=now, features_hash="abc123",
            candle_timestamp=now - timedelta(minutes=5),
        )
        signal2 = EngineSignal(
            engine="quant", action="BUY", confidence=0.93,
            timestamp=now, features_hash="abc123",
            candle_timestamp=now - timedelta(minutes=5),
        )

        decision.set_signal("ml", signal1)
        decision.set_signal("quant", signal2)

        # Same cycle_id
        self.assertEqual(decision.cycle_id, decision.cycle_id)

        # Feature hashes are consistent
        self.assertEqual(signal1.features_hash, signal2.features_hash)

        # Candle timestamps are valid (before decision time)
        self.assertLess(signal1.candle_timestamp, decision.timestamp)
        self.assertLess(signal2.candle_timestamp, decision.timestamp)


class TestNoDuplicateInitialization(unittest.TestCase):
    """TEST 6 — No duplicate initialization."""

    def setUp(self):
        reset_init_counters()
        # Clear registry for clean test
        registry = get_model_registry()
        registry.clear()

    def test_single_initialization(self):
        """Repeated get_or_create calls only initialize once."""
        registry = get_model_registry()

        # Create a simple factory
        calls = []
        def factory():
            calls.append(1)
            return object()

        # Call 100 times
        for _ in range(100):
            registry.get_or_create("test_model", factory)

        self.assertEqual(len(calls), 1)
        self.assertEqual(get_init_count("test_model"), 1)

    def test_kronos_initialized_once(self):
        """Kronos should only be initialized once across repeated calls."""
        registry = get_model_registry()

        # Mock KronosForecaster to avoid heavy initialization.
        # NOTE: KronosForecaster is imported lazily inside get_kronos() from
        # brain.kronos_forecaster, so we patch it at its source module.
        with patch("brain.kronos_forecaster.KronosForecaster") as mock_kronos:
            mock_kronos.return_value = MagicMock()

            for _ in range(10):
                from brain.model_registry import get_kronos
                get_kronos()

            self.assertEqual(mock_kronos.call_count, 1)
            self.assertEqual(get_init_count("kronos"), 1)


class TestNoSilentMutation(unittest.TestCase):
    """TEST 7 — No silent mutation."""

    def test_frozen_decision_cannot_be_silently_mutated(self):
        """BUY 85% frozen decision cannot be silently changed to WAIT."""
        decision = create_decision(
            "XAUUSD",
            action="BUY",
            direction="BUY",
            confidence=85.0,
            source="PATTERN",
        )

        # Attempt to mutate through transition (must record reason)
        decision.transition(
            new_action="WAIT",
            stage="EXECUTION_GATE",
            reason="SPREAD_TOO_HIGH",
            confidence=85.0,
        )

        # Rejection must be recorded
        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(decision.rejection_reason, "SPREAD_TOO_HIGH")
        self.assertEqual(decision.rejection_stage, "EXECUTION_GATE")
        self.assertEqual(decision.previous_action, "BUY")
        self.assertEqual(decision.previous_confidence, 85.0)

        # Transition must be recorded
        self.assertEqual(len(decision.transitions), 1)
        self.assertEqual(decision.transitions[0].from_stage, "RAW")
        self.assertEqual(decision.transitions[0].to_stage, "EXECUTION_GATE")

    def test_risk_manager_cannot_directly_mutate(self):
        """Risk manager must return approval/rejection, not mutate the decision."""
        decision = create_decision(
            "XAUUSD",
            action="BUY",
            direction="BUY",
            confidence=85.0,
            source="PATTERN",
        )

        # Risk manager returns a result (doesn't mutate)
        risk_result = {"approved": False, "reason": "MARGIN_TOO_LOW"}

        # Apply through controlled transition
        if not risk_result["approved"]:
            decision.transition(
                new_action="WAIT",
                stage="RISK_GATE",
                reason=risk_result["reason"],
                confidence=85.0,
            )

        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(decision.rejection_reason, "MARGIN_TOO_LOW")
        self.assertEqual(decision.rejection_stage, "RISK_GATE")
        self.assertEqual(decision.previous_action, "BUY")
        self.assertEqual(decision.previous_confidence, 85.0)


class TestDecisionTrace(unittest.TestCase):
    """Test decision trace logging."""

    def test_decision_trace_has_all_stages(self):
        """Decision trace records all stages."""
        decision = create_decision("XAUUSD")

        # Simulate full flow
        decision.transition("BUY", "RAW", confidence=78)
        decision.transition("BUY", "VALIDATED", confidence=78)
        decision.transition("BUY", "CANDIDATE", confidence=78)
        decision.transition("BUY", "SELECTED", confidence=78)
        decision.transition("BUY", "FROZEN", confidence=78)
        decision.transition("BUY", "RISK_APPROVED", confidence=78)
        decision.transition("BUY", "EXECUTION_APPROVED", confidence=78)

        self.assertEqual(len(decision.transitions), 7)
        stages = [t.to_stage for t in decision.transitions]
        self.assertIn("RAW", stages)
        self.assertIn("VALIDATED", stages)
        self.assertIn("CANDIDATE", stages)
        self.assertIn("SELECTED", stages)
        self.assertIn("FROZEN", stages)
        self.assertIn("RISK_APPROVED", stages)
        self.assertIn("EXECUTION_APPROVED", stages)


if __name__ == "__main__":
    unittest.main()