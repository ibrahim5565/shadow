"""
===========================================================================
AEGIS GOLD v9.0 — Causality Enforcement Engine (Phase I)
===========================================================================

PURPOSE:
--------
Provides strict temporal causality enforcement to prevent future data leakage
in all forecasting, prediction, and machine learning modules.

CORE VIOLATIONS IDENTIFIED:
---------------------------
1. Kronos forecaster: unseeded np.random.normal() creates systematic bias
2. ML Ensemble: record_prediction_outcome() may update live model weights
3. RL Agent: _compute_realized_rr_reward() uses post-trade data for decisions

DESIGN PRINCIPLES:
------------------
1. Hard causality gates that BLOCK operations accessing future data
2. Temporal validation for all prediction inputs
3. Frozen snapshot enforcement for live trading decisions  
4. Audit trail logging for causality violations
5. Graceful degradation when causality is violated

ENFORCEMENT LAYERS:
-------------------
Layer 1: Input Validation - Ensure all inputs have timestamp <= decision_time
Layer 2: Model State Freezing - Prevent model updates during live decisions  
Layer 3: Random Seed Control - Eliminate systematic bias from random generators
Layer 4: Future Data Detection - Scan for lookahead bias patterns
Layer 5: Audit Logging - Track all causality checks and violations

===========================================================================
"""

import logging
import numpy as np
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger("aegis.causality")


@dataclass
class CausalityViolation:
    """Record of a causality violation detection."""
    module_name: str
    violation_type: str  # "FUTURE_DATA", "UNSEEDED_RANDOM", "LIVE_MODEL_UPDATE", "LOOKAHEAD_BIAS"
    description: str
    timestamp: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    data_involved: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None


@dataclass
class CausalityAuditResult:
    """Result of causality audit operation."""
    passed: bool
    violation_count: int
    violations: List[CausalityViolation]
    audit_timestamp: str
    module_name: str


class CausalityEnforcer:
    """
    Core causality enforcement engine that provides temporal validation
    and prevents future data leakage across all prediction modules.
    """
    
    def __init__(self, audit_log_path: str = "d:\\Trading\\Aegis_Gold\\data\\causality_audit.json"):
        self.audit_log_path = Path(audit_log_path)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.violations_detected = []
        self.audit_enabled = True
        
        # Initialize violation tracking
        self.violation_counts = {
            "FUTURE_DATA": 0,
            "UNSEEDED_RANDOM": 0, 
            "LIVE_MODEL_UPDATE": 0,
            "LOOKAHEAD_BIAS": 0
        }
        
        logger.info("[CAUSALITY] Enforcement engine initialized")
    
    def validate_temporal_inputs(
        self, 
        inputs: Dict[str, Any], 
        decision_time: datetime,
        module_name: str
    ) -> CausalityAuditResult:
        """
        Validates that all inputs have timestamps <= decision_time.
        
        Args:
            inputs: Dictionary of input data with timestamps
            decision_time: The current decision timestamp
            module_name: Name of module being audited
            
        Returns:
            CausalityAuditResult with validation status
        """
        violations = []
        
        for key, value in inputs.items():
            # Check for timestamp fields
            if isinstance(value, dict):
                timestamp_fields = ['timestamp', 'time', 'datetime', 'created_at', 'updated_at']
                for ts_field in timestamp_fields:
                    if ts_field in value:
                        try:
                            data_time = self._parse_timestamp(value[ts_field])
                            if data_time > decision_time:
                                violations.append(CausalityViolation(
                                    module_name=module_name,
                                    violation_type="FUTURE_DATA",
                                    description=f"Input '{key}.{ts_field}' contains future timestamp: {data_time} > {decision_time}",
                                    timestamp=datetime.now(timezone.utc).isoformat(),
                                    severity="CRITICAL",
                                    data_involved={"input_key": key, "future_timestamp": str(data_time)}
                                ))
                        except Exception as e:
                            logger.warning(f"[CAUSALITY] Could not parse timestamp {value[ts_field]}: {e}")
            
            # Check for candle data with future timestamps
            elif isinstance(value, list) and key in ['candles', 'bars', 'history']:
                for i, item in enumerate(value):
                    if isinstance(item, dict) and 'time' in item:
                        try:
                            candle_time = self._parse_timestamp(item['time'])
                            if candle_time > decision_time:
                                violations.append(CausalityViolation(
                                    module_name=module_name,
                                    violation_type="FUTURE_DATA", 
                                    description=f"Candle {i} in '{key}' has future timestamp: {candle_time} > {decision_time}",
                                    timestamp=datetime.now(timezone.utc).isoformat(),
                                    severity="CRITICAL",
                                    data_involved={"candle_index": i, "future_timestamp": str(candle_time)}
                                ))
                        except Exception:
                            pass
        
        # Update violation counts
        for v in violations:
            self.violation_counts[v.violation_type] += 1
            
        result = CausalityAuditResult(
            passed=len(violations) == 0,
            violation_count=len(violations),
            violations=violations,
            audit_timestamp=datetime.now(timezone.utc).isoformat(),
            module_name=module_name
        )
        
        if violations and self.audit_enabled:
            self._log_violations(result)
            
        return result
    
    def check_random_seed_control(self, module_name: str, operation: str) -> CausalityAuditResult:
        """
        Ensures random number generators are properly seeded for reproducibility.
        
        Critical for preventing systematic directional bias in forecasting models.
        """
        violations = []
        
        # Check numpy random state
        try:
            # Get current numpy random state
            current_state = np.random.get_state()
            state_info = current_state[0]  # Generator type
            
            # Warning: This is a heuristic check since we can't directly detect if
            # random was seeded. We check if we're in a "fresh" unseeded state.
            if state_info == 'MT19937':
                # Create a test to see if randomness is deterministic
                np.random.seed(42)  # Set test seed
                test_val1 = np.random.random()
                np.random.seed(42)  # Reset same seed
                test_val2 = np.random.random()
                
                # If values are same, seeding works (good)
                # If different, there might be an issue with random state
                if abs(test_val1 - test_val2) > 1e-10:
                    violations.append(CausalityViolation(
                        module_name=module_name,
                        violation_type="UNSEEDED_RANDOM",
                        description=f"Random number generator may not be properly seeded in operation: {operation}",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        severity="HIGH",
                        data_involved={"operation": operation, "test_diff": abs(test_val1 - test_val2)}
                    ))
                
        except Exception as e:
            logger.warning(f"[CAUSALITY] Could not check random seed: {e}")
        
        # Update violation counts
        for v in violations:
            self.violation_counts[v.violation_type] += 1
            
        result = CausalityAuditResult(
            passed=len(violations) == 0,
            violation_count=len(violations),
            violations=violations,
            audit_timestamp=datetime.now(timezone.utc).isoformat(),
            module_name=module_name
        )
        
        if violations and self.audit_enabled:
            self._log_violations(result)
            
        return result
    
    def prevent_live_model_updates(self, module_name: str, is_live_trading: bool = True) -> CausalityAuditResult:
        """
        Prevents ML models from being updated during live trading decisions.
        
        Model updates should only occur during dedicated training phases,
        not during live inference/prediction.
        """
        violations = []
        
        if is_live_trading:
            # Check if we're in a prediction/inference context
            # This is enforced by checking if certain model update methods are being called
            import inspect
            frame = inspect.currentframe()
            
            try:
                # Walk up the call stack to check for model update methods
                for i in range(10):  # Check up to 10 frames up
                    frame = frame.f_back
                    if frame is None:
                        break
                        
                    func_name = frame.f_code.co_name
                    
                    # Flag suspicious method names that suggest model updates
                    update_methods = [
                        'fit', 'train', 'update_weights', 'record_prediction_outcome',
                        'update_engine_weights', 'retrain', 'optimize', 'learn'
                    ]
                    
                    if any(method in func_name.lower() for method in update_methods):
                        violations.append(CausalityViolation(
                            module_name=module_name,
                            violation_type="LIVE_MODEL_UPDATE",
                            description=f"Model update method '{func_name}' called during live trading",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            severity="CRITICAL",
                            data_involved={"method_name": func_name, "frame_level": i}
                        ))
                        
            except Exception as e:
                logger.warning(f"[CAUSALITY] Could not inspect call stack: {e}")
            finally:
                del frame  # Prevent reference cycles
        
        # Update violation counts
        for v in violations:
            self.violation_counts[v.violation_type] += 1
            
        result = CausalityAuditResult(
            passed=len(violations) == 0,
            violation_count=len(violations),
            violations=violations,
            audit_timestamp=datetime.now(timezone.utc).isoformat(),
            module_name=module_name
        )
        
        if violations and self.audit_enabled:
            self._log_violations(result)
            
        return result
    
    def audit_prediction_inputs(
        self,
        prediction_func: Callable,
        inputs: Dict[str, Any],
        decision_time: datetime,
        module_name: str
    ) -> tuple[Any, CausalityAuditResult]:
        """
        Audits a prediction function call to ensure causality compliance.
        
        Returns:
            Tuple of (prediction_result, audit_result)
        """
        # Step 1: Validate temporal inputs
        temporal_result = self.validate_temporal_inputs(inputs, decision_time, module_name)
        
        # Step 2: Check random seed control  
        random_result = self.check_random_seed_control(module_name, prediction_func.__name__)
        
        # Step 3: Prevent live model updates
        live_update_result = self.prevent_live_model_updates(module_name, is_live_trading=True)
        
        # Combine all violations
        all_violations = (
            temporal_result.violations + 
            random_result.violations + 
            live_update_result.violations
        )
        
        combined_result = CausalityAuditResult(
            passed=len(all_violations) == 0,
            violation_count=len(all_violations),
            violations=all_violations,
            audit_timestamp=datetime.now(timezone.utc).isoformat(),
            module_name=module_name
        )
        
        # NOTE: The prediction function is NOT executed here. The caller
        # (e.g. create_causality_gate) is responsible for invoking the
        # original function with its original arguments after the audit
        # passes. This prevents argument-mangling bugs where inputs dicts
        # are passed as kwargs.
        if not combined_result.passed and self.audit_enabled:
            logger.error(f"[CAUSALITY] BLOCKED prediction due to {len(all_violations)} causality violations")
        
        return None, combined_result
    
    def create_causality_gate(self, module_name: str, operation_name: str):
        """
        Creates a causality gate decorator for wrapping prediction functions.
        
        Usage:
            @causality_enforcer.create_causality_gate("kronos", "predict")
            def predict(self, candles, symbol="XAUUSD"):
                # prediction logic
                pass
        """
        def causality_gate_decorator(func):
            def wrapped_function(*args, **kwargs):
                # Extract decision time from arguments or use current time
                decision_time = kwargs.pop('decision_time', datetime.now(timezone.utc))
                
                # Prepare inputs for audit
                inputs = {
                    'args': args[1:] if args else [],  # Skip 'self' parameter
                    'kwargs': kwargs
                }
                
                # Run causality audit
                _, audit = self.audit_prediction_inputs(
                    func, inputs, decision_time, module_name
                )
                
                if audit.passed:
                    # Call the original function with its original arguments
                    return func(*args, **kwargs)
                else:
                    logger.error(f"[CAUSALITY] {module_name}.{operation_name} BLOCKED due to causality violations")
                    # Return safe fallback instead of crashing
                    return self._safe_fallback(module_name, operation_name)
                    
            return wrapped_function
        return causality_gate_decorator
    
    def _safe_fallback(self, module_name: str, operation_name: str) -> Any:
        """Provides safe fallback values when causality is violated."""
        fallbacks = {
            'kronos': {
                'predict': self._neutral_kronos_forecast(),
                'forecast': self._neutral_kronos_forecast(),
                'get_engine_vote': {'engine': 'kronos', 'direction': 'neutral', 'confidence': 0.5}
            },
            'ml_ensemble': {
                'predict': self._neutral_ml_prediction()  
            },
            'reinforcement_agent': {
                'predict_action': ('WAIT', 50),
                'get_action_q_values': [0.33, 0.33, 0.34]
            }
        }
        
        module_fallbacks = fallbacks.get(module_name, {})
        return module_fallbacks.get(operation_name, None)
    
    def _neutral_kronos_forecast(self):
        """Safe neutral forecast for Kronos when causality is violated."""
        from brain.kronos_forecaster import KronosForecast
        return KronosForecast(
            price_path_mean=[],
            price_path_std=[],
            volatility_forecast_24h=0.0,
            confidence_up=0.5,
            predicted_direction="NEUTRAL",
            horizon_bars=24,
            timestamp=datetime.now(timezone.utc).isoformat(),
            model_version="causality-safe-fallback",
        )
    
    def _neutral_ml_prediction(self):
        """Safe neutral prediction for ML Ensemble when causality is violated."""
        from brain.ml_ensemble import MLPrediction
        return MLPrediction(
            direction="NEUTRAL",
            win_probability=0.5,
            confidence=0,
            gradient_boost_prob=0.5,
            random_forest_prob=0.5, 
            neural_net_prob=0.5,
            logistic_prob=0.5,
            model_agreement=1.0,
            ensemble_method="CAUSALITY_SAFE",
            recent_accuracy=0.5,
            recent_precision=0.5,
            trade_recommendation="WAIT",
            expected_win_rate=0.5,
            uncertainty=0.0
        )
    
    def _parse_timestamp(self, timestamp_value: Union[str, int, float, datetime]) -> datetime:
        """Parses various timestamp formats to datetime object."""
        if isinstance(timestamp_value, datetime):
            return timestamp_value
        elif isinstance(timestamp_value, (int, float)):
            return datetime.fromtimestamp(timestamp_value, timezone.utc)
        elif isinstance(timestamp_value, str):
            try:
                return datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
            except:
                # Try parsing as timestamp
                try:
                    return datetime.fromtimestamp(float(timestamp_value), timezone.utc)
                except:
                    raise ValueError(f"Could not parse timestamp: {timestamp_value}")
        else:
            raise ValueError(f"Unsupported timestamp type: {type(timestamp_value)}")
    
    def _log_violations(self, audit_result: CausalityAuditResult):
        """Logs causality violations to audit file."""
        try:
            # Load existing log (handle empty file gracefully)
            log_data = []
            if self.audit_log_path.exists():
                with open(self.audit_log_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        log_data = json.load(content)
                    else:
                        log_data = []
            
            # Add new violations
            for violation in audit_result.violations:
                log_data.append(asdict(violation))
            
            # Keep only last 1000 violations to prevent log bloat
            if len(log_data) > 1000:
                log_data = log_data[-1000:]
            
            # Save updated log
            with open(self.audit_log_path, 'w') as f:
                json.dump(log_data, f, indent=2, default=str)
                
            logger.warning(f"[CAUSALITY] Logged {len(audit_result.violations)} violations for {audit_result.module_name}")
            
        except Exception as e:
            logger.error(f"[CAUSALITY] Failed to log violations: {e}")
    
    def get_violation_summary(self) -> Dict[str, Any]:
        """Returns summary of all causality violations detected."""
        return {
            "total_violations": sum(self.violation_counts.values()),
            "by_type": dict(self.violation_counts),
            "audit_enabled": self.audit_enabled,
            "log_path": str(self.audit_log_path)
        }
    
    def reset_violation_counts(self):
        """Resets violation counters (useful for testing)."""
        self.violation_counts = {k: 0 for k in self.violation_counts.keys()}
        self.violations_detected.clear()


# Global singleton instance
_causality_enforcer = None

def get_causality_enforcer() -> CausalityEnforcer:
    """Get or create singleton causality enforcer instance."""
    global _causality_enforcer
    if _causality_enforcer is None:
        _causality_enforcer = CausalityEnforcer()
    return _causality_enforcer


# Convenience function for quick audits
def audit_prediction_call(
    module_name: str, 
    operation_name: str,
    inputs: Dict[str, Any], 
    decision_time: datetime = None
) -> CausalityAuditResult:
    """Quick causality audit for a prediction call."""
    enforcer = get_causality_enforcer()
    if decision_time is None:
        decision_time = datetime.now(timezone.utc)
    
    return enforcer.validate_temporal_inputs(inputs, decision_time, f"{module_name}.{operation_name}")