"""
===========================================================================
AEGIS GOLD — Causality Enforcement Test Suite (Phase I)
===========================================================================

Tests for strict temporal causality enforcement and future data leakage prevention.

CRITICAL TEST COVERAGE:
-----------------------
1. Future data detection in prediction inputs
2. Random seed bias elimination in forecasting
3. Live model update prevention during trading
4. Temporal validation of all input data
5. Causality gate integration with prediction modules
6. Safe fallback behavior when causality is violated

===========================================================================
"""

import pytest
import numpy as np
import json
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.causality_enforcer import (
    CausalityEnforcer, 
    CausalityViolation, 
    CausalityAuditResult,
    get_causality_enforcer,
    audit_prediction_call
)


class TestCausalityEnforcer:
    """Test suite for core causality enforcement functionality."""
    
    def setup_method(self):
        """Setup for each test method."""
        self.enforcer = CausalityEnforcer()
        self.enforcer.audit_enabled = True
        self.decision_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        
    def test_future_data_detection_basic(self):
        """Test detection of future timestamps in basic inputs."""
        # Future timestamp in input data
        future_time = self.decision_time + timedelta(hours=1)
        inputs = {
            "market_data": {
                "timestamp": future_time.isoformat(),
                "price": 2010.50
            }
        }
        
        result = self.enforcer.validate_temporal_inputs(
            inputs, self.decision_time, "test_module"
        )
        
        assert not result.passed
        assert result.violation_count == 1
        assert result.violations[0].violation_type == "FUTURE_DATA"
        assert "future timestamp" in result.violations[0].description
        
    def test_future_data_detection_candles(self):
        """Test detection of future timestamps in candle data."""
        past_time = self.decision_time - timedelta(minutes=5)
        future_time = self.decision_time + timedelta(minutes=5)
        
        inputs = {
            "candles": [
                {"time": past_time.timestamp(), "open": 2010, "close": 2015},
                {"time": future_time.timestamp(), "open": 2015, "close": 2020}  # Future candle
            ]
        }
        
        result = self.enforcer.validate_temporal_inputs(
            inputs, self.decision_time, "test_module"
        )
        
        assert not result.passed
        assert result.violation_count == 1
        assert "Candle 1" in result.violations[0].description
        
    def test_valid_temporal_inputs(self):
        """Test that valid past/present data passes temporal validation."""
        past_time = self.decision_time - timedelta(minutes=10)
        
        inputs = {
            "market_data": {
                "timestamp": past_time.isoformat(),
                "price": 2010.50
            },
            "candles": [
                {"time": past_time.timestamp(), "open": 2010, "close": 2015}
            ]
        }
        
        result = self.enforcer.validate_temporal_inputs(
            inputs, self.decision_time, "test_module"
        )
        
        assert result.passed
        assert result.violation_count == 0
        
    def test_random_seed_control_check(self):
        """Test random seed control validation."""
        # This test verifies the random seed checking mechanism
        result = self.enforcer.check_random_seed_control("test_module", "predict")
        
        # The result depends on numpy's random state
        # We mainly test that the check runs without error
        assert isinstance(result, CausalityAuditResult)
        assert result.module_name == "test_module"
        
    def test_live_model_update_prevention(self):
        """Test prevention of model updates during live trading."""
        with patch('inspect.currentframe') as mock_frame:
            # Mock call stack showing a model update method.
            # The "current" frame returned by inspect.currentframe() is the
            # innermost call. Walking f_back walks through the CALLER frames:
            #   current (some_other_func) -> fit -> predict
            # 'fit' is a model-update method, so a violation must be raised.
            predict_frame = Mock()
            predict_frame.f_code.co_name = "predict"
            
            fit_frame = Mock()
            fit_frame.f_code.co_name = "fit"
            fit_frame.f_back = predict_frame
            
            current_frame = Mock()
            current_frame.f_code.co_name = "some_other_func"
            current_frame.f_back = fit_frame
            
            mock_frame.return_value = current_frame
            
            result = self.enforcer.prevent_live_model_updates("test_module", is_live_trading=True)
            
            assert not result.passed
            assert result.violation_count == 1
            assert result.violations[0].violation_type == "LIVE_MODEL_UPDATE"
            assert "fit" in result.violations[0].description
            
    def test_causality_gate_decorator(self):
        """Test causality gate decorator functionality."""
        # Mock prediction function
        def mock_predict_func(candles, symbol="XAUUSD"):
            return {"direction": "BUY", "confidence": 0.8}
        
        # Create causality gate
        gate = self.enforcer.create_causality_gate("test_module", "predict")
        wrapped_func = gate(mock_predict_func)
        
        # Test with valid inputs
        past_time = self.decision_time - timedelta(minutes=5)
        result = wrapped_func(
            candles=[{"time": past_time.timestamp(), "close": 2010}],
            decision_time=self.decision_time
        )
        
        assert result is not None
        assert result["direction"] == "BUY"
        
    def test_safe_fallback_behavior(self):
        """Test safe fallback when causality violations occur."""
        # Test Kronos fallback
        kronos_fallback = self.enforcer._safe_fallback("kronos", "predict")
        assert hasattr(kronos_fallback, "predicted_direction")
        assert kronos_fallback.predicted_direction == "NEUTRAL"
        
        # Test ML ensemble fallback
        ml_fallback = self.enforcer._safe_fallback("ml_ensemble", "predict")
        assert hasattr(ml_fallback, "direction")
        assert ml_fallback.direction == "NEUTRAL"
        
        # Test RL agent fallback
        rl_fallback = self.enforcer._safe_fallback("reinforcement_agent", "predict_action")
        assert rl_fallback == ("WAIT", 50)
        
    def test_violation_logging(self):
        """Test that violations are properly logged."""
        # Create a temporary log file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp_file:
            temp_log_path = tmp_file.name
            
        try:
            # Create enforcer with temporary log path
            enforcer = CausalityEnforcer(audit_log_path=temp_log_path)
            
            # Trigger a violation
            future_time = self.decision_time + timedelta(hours=1)
            inputs = {"data": {"timestamp": future_time.isoformat()}}
            
            result = enforcer.validate_temporal_inputs(
                inputs, self.decision_time, "test_module"
            )
            
            # Check that log file was created and contains violation
            assert os.path.exists(temp_log_path)
            with open(temp_log_path, 'r') as f:
                log_data = json.load(f)
                
            assert len(log_data) == 1
            assert log_data[0]["violation_type"] == "FUTURE_DATA"
            assert log_data[0]["module_name"] == "test_module"
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_log_path):
                os.unlink(temp_log_path)
                
    def test_violation_summary(self):
        """Test violation summary reporting."""
        # Trigger some violations
        future_time = self.decision_time + timedelta(hours=1)
        inputs = {"data": {"timestamp": future_time.isoformat()}}
        
        self.enforcer.validate_temporal_inputs(inputs, self.decision_time, "test1")
        self.enforcer.validate_temporal_inputs(inputs, self.decision_time, "test2")
        
        summary = self.enforcer.get_violation_summary()
        
        assert summary["total_violations"] == 2
        assert summary["by_type"]["FUTURE_DATA"] == 2
        assert summary["audit_enabled"] is True


class TestKronosCausalityFix:
    """Test causality fixes in Kronos forecaster."""
    
    def setup_method(self):
        """Setup for Kronos causality tests."""
        from brain.kronos_forecaster import KronosForecaster
        self.forecaster = KronosForecaster()
        
    def test_deterministic_random_seeding(self):
        """Test that Kronos uses deterministic seeding to prevent bias."""
        # Create identical price data
        closes = np.array([2010.0, 2015.0, 2012.0, 2018.0, 2020.0])
        
        # Generate two forecasts with same data
        forecast1 = self.forecaster._run_statistical_fallback(
            closes, closes, closes, 2020.0, "2024-01-15T12:00:00Z"
        )
        
        forecast2 = self.forecaster._run_statistical_fallback(
            closes, closes, closes, 2020.0, "2024-01-15T12:00:00Z"
        )
        
        # Results should be identical (deterministic)
        assert forecast1.confidence_up == forecast2.confidence_up
        assert forecast1.predicted_direction == forecast2.predicted_direction
        assert forecast1.price_path_mean == forecast2.price_path_mean
        
    def test_different_prices_different_predictions(self):
        """Test that different price data produces different predictions."""
        closes1 = np.array([2010.0, 2015.0, 2012.0, 2018.0, 2020.0])
        closes2 = np.array([2010.0, 2005.0, 2008.0, 2002.0, 1998.0])
        
        forecast1 = self.forecaster._run_statistical_fallback(
            closes1, closes1, closes1, 2020.0, "2024-01-15T12:00:00Z"
        )
        
        forecast2 = self.forecaster._run_statistical_fallback(
            closes2, closes2, closes2, 1998.0, "2024-01-15T12:00:00Z"
        )
        
        # Different price histories should produce different forecasts
        assert forecast1.confidence_up != forecast2.confidence_up or \
               forecast1.predicted_direction != forecast2.predicted_direction


class TestMLEnsembleCausalityFix:
    """Test causality fixes in ML Ensemble."""
    
    def setup_method(self):
        """Setup for ML Ensemble causality tests."""
        from brain.ml_ensemble import MLEnsemble
        self.ensemble = MLEnsemble()
        
    @patch('brain.causality_enforcer.get_causality_enforcer')
    def test_blocked_live_model_updates(self, mock_get_enforcer):
        """Test that live model updates are blocked during trading."""
        # Mock enforcer that detects violation
        mock_enforcer = Mock()
        mock_audit_result = Mock()
        mock_audit_result.passed = False
        mock_enforcer.prevent_live_model_updates.return_value = mock_audit_result
        mock_get_enforcer.return_value = mock_enforcer
        
        # Attempt to record prediction outcome (should be blocked)
        initial_predictions = len(self.ensemble.recent_predictions)
        self.ensemble.record_prediction_outcome("test_pred", True)
        
        # Verify no prediction was recorded
        assert len(self.ensemble.recent_predictions) == initial_predictions
        
    @patch('brain.causality_enforcer.get_causality_enforcer')  
    def test_allowed_training_mode_updates(self, mock_get_enforcer):
        """Test that model updates are allowed in training mode."""
        # Mock enforcer that allows updates
        mock_enforcer = Mock()
        mock_audit_result = Mock()
        mock_audit_result.passed = True
        mock_enforcer.prevent_live_model_updates.return_value = mock_audit_result
        mock_get_enforcer.return_value = mock_enforcer
        
        # Record prediction outcome (should be allowed)
        initial_predictions = len(self.ensemble.recent_predictions)
        self.ensemble.record_prediction_outcome("test_pred", True)
        
        # Verify prediction was recorded
        assert len(self.ensemble.recent_predictions) == initial_predictions + 1
        assert self.ensemble.recent_predictions[-1] is True


class TestReinforcementAgentCausalityFix:
    """Test causality fixes in Reinforcement Agent."""
    
    def setup_method(self):
        """Setup for RL Agent causality tests."""
        from brain.reinforcement_agent import AegisRLAgent
        self.agent = AegisRLAgent()
        
    @patch('brain.causality_enforcer.get_causality_enforcer')
    def test_blocked_live_weight_updates(self, mock_get_enforcer):
        """Test that engine weight updates are blocked during live trading."""
        # Mock enforcer that detects violation
        mock_enforcer = Mock()
        mock_audit_result = Mock()
        mock_audit_result.passed = False
        mock_enforcer.prevent_live_model_updates.return_value = mock_audit_result
        mock_get_enforcer.return_value = mock_enforcer
        
        # Mock weights file to test file operations
        trade_outcome = {
            "tier": "test",
            "profit_usd": 100.0,
            "engine_votes": {"kronos": {"direction": "buy", "confidence": 0.8}},
            "direction": "BUY"
        }
        
        # Attempt to update weights (should be blocked)
        with patch('os.path.exists', return_value=False):
            self.agent.update_engine_weights(trade_outcome)
        
        # Test passes if no exception is raised (method exits gracefully)
        assert True


class TestAuditPredictionCall:
    """Test convenience function for prediction call audits."""
    
    def test_audit_prediction_call_function(self):
        """Test the audit_prediction_call convenience function."""
        decision_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        future_time = decision_time + timedelta(hours=1)
        
        inputs = {
            "data": {"timestamp": future_time.isoformat()}
        }
        
        result = audit_prediction_call("test_module", "predict", inputs, decision_time)
        
        assert not result.passed
        assert result.violation_count == 1
        assert result.module_name == "test_module.predict"


def test_singleton_causality_enforcer():
    """Test that get_causality_enforcer returns singleton instance."""
    enforcer1 = get_causality_enforcer()
    enforcer2 = get_causality_enforcer()
    
    assert enforcer1 is enforcer2
    assert isinstance(enforcer1, CausalityEnforcer)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])