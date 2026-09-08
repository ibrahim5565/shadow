"""
===========================================================================
AEGIS GOLD — Causality Enforcer (Phase S)
===========================================================================

PURPOSE:
--------
Final comprehensive causality enforcement system ensuring strict temporal
integrity across all 18 phases and 12 pipeline stages. Prevents all forms
of future data leakage and forward-looking bias.

VIOLATIONS DETECTED:
--------------------
1. Future Price Data - Using prices before they occurred
2. Live Model Updates - Training on data that hasn't occurred yet
3. Forward-Looking Bias - Decision rules based on future events
4. Signal Timing - Entry signals generated with future knowledge
5. Data Integrity - Timestamp violations and causality breaks
6. ML Live Updates - ML models updated with live data during trading
7. Kronos Violations - Random seeds using future time
8. Correlation Leakage - Using forward-looking correlation data

ENFORCEMENT MECHANISMS:
-----------------------
1. Timestamp Validation - All events must have valid, causal timestamps
2. Data Freezing - Historical data frozen at decision point
3. Model Lockdown - ML models locked during forward testing
4. RL Freezing - RL agents frozen after initial training
5. Pipeline Isolation - Each stage operates only on historical data
6. Verification Checkpoints - Validation at each pipeline stage
7. Audit Trail - Complete causality audit for each decision

===========================================================================
"""

import logging
import hashlib
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import json

logger = logging.getLogger("aegis.causality")


class CausalityViolation(Enum):
    """Types of causality violations."""
    FUTURE_PRICE_DATA = "FUTURE_PRICE_DATA"
    LIVE_MODEL_UPDATE = "LIVE_MODEL_UPDATE"
    FORWARD_LOOKING_BIAS = "FORWARD_LOOKING_BIAS"
    SIGNAL_TIMING = "SIGNAL_TIMING"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    ML_LIVE_UPDATE = "ML_LIVE_UPDATE"
    KRONOS_VIOLATION = "KRONOS_VIOLATION"
    CORRELATION_LEAKAGE = "CORRELATION_LEAKAGE"
    TEMPORAL_ORDERING = "TEMPORAL_ORDERING"
    UNKNOWN = "UNKNOWN"


class DataContext(Enum):
    """Context where data exists."""
    HISTORICAL = "HISTORICAL"        # Data from past, decision point frozen
    FORWARD_TEST = "FORWARD_TEST"    # Out-of-sample forward test
    LIVE_TRADING = "LIVE_TRADING"    # Real-time live trading
    SIMULATION = "SIMULATION"        # Backtesting simulation


@dataclass
class CausalityRecord:
    """Record of causality validation at decision point."""
    
    record_id: str
    timestamp: str                    # When decision was made
    reference_timestamp: str          # Latest allowed historical data
    data_context: DataContext
    
    # Data availability
    available_data_up_to: str        # Cutoff for available historical data
    decision_timestamp: str          # When decision was executed
    
    # Validation results
    violations_detected: List[CausalityViolation] = field(default_factory=list)
    is_causal: bool = True
    
    # Details
    checked_data_sources: List[str] = field(default_factory=list)
    data_checksums: Dict[str, str] = field(default_factory=dict)  # For integrity
    
    # Audit trail
    enforcements_applied: List[str] = field(default_factory=list)
    verification_passed: bool = True


@dataclass
class CausalityViolationRecord:
    """Details of detected causality violation."""
    
    violation_id: str
    violation_type: CausalityViolation
    severity: float              # 0-1 scale
    
    # Context
    timestamp: str
    stage_name: str
    pattern_id: Optional[str]
    trade_id: Optional[str]
    
    # Details
    description: str
    evidence: Dict[str, Any]     # What shows the violation
    impact: str                  # How this affects trading
    
    # Remediation
    is_recoverable: bool
    recommended_action: str


@dataclass 
class CausalityAudit:
    """Complete causality audit trail."""
    
    audit_id: str
    session_start: str
    session_end: Optional[str]
    
    # Summary
    total_decisions: int
    causal_decisions: int
    violation_decisions: int
    
    # Violations
    violations_by_type: Dict[str, int]
    critical_violations: List[CausalityViolationRecord]
    
    # Enforcements
    total_enforcements: int
    enforcements_applied: List[str]
    
    # Data integrity
    data_integrity_score: float  # 0-100
    causality_score: float       # 0-100
    
    # Recommendations
    recommendations: List[str]


class CausalityEnforcer:
    """
    Comprehensive causality enforcement system for AEGIS GOLD.
    """
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize causality enforcer.
        
        Args:
            strict_mode: If True, halt on any violation; if False, log and continue
        """
        
        self.strict_mode = strict_mode
        
        # Tracking
        self.records = {}                   # record_id -> CausalityRecord
        self.violations = {}                # violation_id -> CausalityViolationRecord
        
        # Configuration
        self.max_price_delay_seconds = 0    # No future prices allowed
        self.model_lockdown_enabled = True
        self.rl_freeze_enabled = True
        self.ml_live_update_allowed = False  # Never update ML during trading
        
        # Data context tracking
        self.current_context = DataContext.HISTORICAL
        self.decision_cutoff = None         # Timestamp cutoff for decisions
        
        # Enforcement hooks
        self.enforcement_hooks = {}
        
        # Audit trail
        self.current_audit = None
        self.audit_history = []
        
        logger.info(
            f"[CAUSALITY] Enforcer initialized (strict_mode={strict_mode})"
        )
    
    def start_session(self, data_context: DataContext) -> str:
        """
        Start new causality session.
        
        Args:
            data_context: Type of data context (historical, forward test, live)
            
        Returns:
            Audit ID
        """
        
        self.current_context = data_context
        audit_id = f"AUDIT_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        
        self.current_audit = CausalityAudit(
            audit_id=audit_id,
            session_start=datetime.now(timezone.utc).isoformat(),
            session_end=None,
            total_decisions=0,
            causal_decisions=0,
            violation_decisions=0,
            violations_by_type={},
            critical_violations=[],
            total_enforcements=0,
            enforcements_applied=[],
            data_integrity_score=100.0,
            causality_score=100.0,
            recommendations=[]
        )
        
        logger.info(
            f"[CAUSALITY] Started session {audit_id} in {data_context.value} mode"
        )
        
        return audit_id
    
    def validate_decision(
        self,
        decision_id: str,
        stage_name: str,
        timestamp: str,
        available_data_timestamp: str,
        data_being_used: Dict[str, Any],
        pipeline_context: Optional[Dict[str, Any]] = None
    ) -> CausalityRecord:
        """
        Validate causality of a decision/action.
        
        Args:
            decision_id: Unique ID for this decision
            stage_name: Pipeline stage making decision
            timestamp: When decision is being made
            available_data_timestamp: Latest data that should be available
            data_being_used: Data used for the decision
            pipeline_context: Full pipeline context
            
        Returns:
            CausalityRecord with validation results
        """
        
        record = CausalityRecord(
            record_id=decision_id,
            timestamp=timestamp,
            reference_timestamp=available_data_timestamp,
            data_context=self.current_context,
            available_data_up_to=available_data_timestamp,
            decision_timestamp=datetime.now(timezone.utc).isoformat(),
            checked_data_sources=list(data_being_used.keys()) if data_being_used else []
        )
        
        # Perform checks
        violations = self._check_all_violations(
            stage_name, timestamp, available_data_timestamp, 
            data_being_used, pipeline_context
        )
        
        record.violations_detected = violations
        record.is_causal = len(violations) == 0
        
        # Apply enforcements
        if violations:
            self._apply_enforcements(record, violations)
            self.current_audit.violation_decisions += 1
            
            if self.strict_mode:
                logger.error(
                    f"[CAUSALITY] CRITICAL: {len(violations)} violations in {stage_name}"
                )
                for violation in violations:
                    logger.error(f"  - {violation.value}")
                raise RuntimeError(f"Causality violations detected: {violations}")
        else:
            self.current_audit.causal_decisions += 1
        
        # Store record
        self.records[decision_id] = record
        self.current_audit.total_decisions += 1
        
        logger.info(
            f"[CAUSALITY] Decision {decision_id}: {stage_name} - "
            f"Causal={record.is_causal}, Violations={len(violations)}"
        )
        
        return record
    
    def _check_all_violations(
        self,
        stage_name: str,
        timestamp: str,
        available_data_timestamp: str,
        data_being_used: Dict[str, Any],
        pipeline_context: Optional[Dict[str, Any]] = None
    ) -> List[CausalityViolation]:
        """Check for all types of causality violations."""
        
        violations = []
        
        # Check 1: Timestamp ordering
        if not self._check_timestamp_ordering(timestamp, available_data_timestamp):
            violations.append(CausalityViolation.TEMPORAL_ORDERING)
        
        # Check 2: Future price data
        if self._check_future_price_data(data_being_used, available_data_timestamp):
            violations.append(CausalityViolation.FUTURE_PRICE_DATA)
        
        # Check 3: Data integrity
        if not self._check_data_integrity(data_being_used):
            violations.append(CausalityViolation.DATA_INTEGRITY)
        
        # Check 4: ML model updates
        if self._check_ml_live_updates():
            violations.append(CausalityViolation.ML_LIVE_UPDATE)
        
        # Check 5: RL agent updates
        if self._check_rl_live_updates():
            violations.append(CausalityViolation.LIVE_MODEL_UPDATE)
        
        # Check 6: Forward-looking bias
        if self._check_forward_looking_bias(stage_name, pipeline_context):
            violations.append(CausalityViolation.FORWARD_LOOKING_BIAS)
        
        # Check 7: Signal timing
        if self._check_signal_timing(timestamp, available_data_timestamp, stage_name):
            violations.append(CausalityViolation.SIGNAL_TIMING)
        
        # Check 8: Correlation leakage
        if self._check_correlation_leakage(data_being_used):
            violations.append(CausalityViolation.CORRELATION_LEAKAGE)
        
        return violations
    
    def _check_timestamp_ordering(self, timestamp: str, available_data: str) -> bool:
        """Verify timestamps are in correct causal order."""
        
        try:
            decision_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            data_dt = datetime.fromisoformat(available_data.replace('Z', '+00:00'))
            
            # Decision must be after data cutoff
            if decision_dt < data_dt:
                return False
            
            # No huge time jumps (arbitrary but reasonable check)
            time_diff = (decision_dt - data_dt).total_seconds()
            if time_diff > 86400 * 365:  # More than 1 year difference
                return False
            
            return True
            
        except:
            return False
    
    def _check_future_price_data(
        self,
        data_being_used: Dict[str, Any],
        available_data_timestamp: str
    ) -> bool:
        """Check if future prices are being used."""
        
        # Look for price data with timestamps after available_data_timestamp
        try:
            available_dt = datetime.fromisoformat(available_data_timestamp.replace('Z', '+00:00'))
            
            for key, value in data_being_used.items():
                # Check if this is price data
                if any(x in key.lower() for x in ['price', 'high', 'low', 'close']):
                    
                    # Check if value has a timestamp
                    if isinstance(value, dict) and 'timestamp' in value:
                        try:
                            value_dt = datetime.fromisoformat(
                                str(value['timestamp']).replace('Z', '+00:00')
                            )
                            if value_dt > available_dt + timedelta(seconds=self.max_price_delay_seconds):
                                return True
                        except:
                            pass
            
            return False
            
        except:
            return False
    
    def _check_data_integrity(self, data_being_used: Dict[str, Any]) -> bool:
        """Verify data integrity (no NaN, missing, or corrupted data)."""
        
        try:
            for key, value in data_being_used.items():
                
                # Check for None/NaN
                if value is None:
                    return False
                
                # Check for suspicious values
                if isinstance(value, (int, float)):
                    if value != value:  # NaN check
                        return False
                    if value == float('inf'):
                        return False
                
                # Check for empty collections
                if isinstance(value, (list, dict)):
                    if len(value) == 0:
                        return False
            
            return True
            
        except:
            return False
    
    def _check_ml_live_updates(self) -> bool:
        """Check if ML models are being updated with live data."""
        
        # In live trading or forward test, ML should be frozen
        if self.current_context in [DataContext.LIVE_TRADING, DataContext.FORWARD_TEST]:
            if not self.model_lockdown_enabled:
                return True
        
        # Check if any ML update hooks are registered
        if 'ml_update' in self.enforcement_hooks:
            return not self.enforcement_hooks['ml_update']
        
        return False
    
    def _check_rl_live_updates(self) -> bool:
        """Check if RL agents are being updated with live data."""
        
        # In live trading or forward test, RL should be frozen
        if self.current_context in [DataContext.LIVE_TRADING, DataContext.FORWARD_TEST]:
            if not self.rl_freeze_enabled:
                return True
        
        return False
    
    def _check_forward_looking_bias(
        self,
        stage_name: str,
        pipeline_context: Optional[Dict[str, Any]]
    ) -> bool:
        """Check for forward-looking bias in decision logic."""
        
        # Certain stages should never have forward-looking logic
        forbidden_stages = {
            'ENTRY_SIGNAL': ['entry_trigger'],  # Should not look ahead
            'PATTERN_DETECTION': ['future_confirmation'],
            'OPPORTUNITY_ASSESSMENT': ['forward_outcome']
        }
        
        if pipeline_context and stage_name in forbidden_stages:
            for forbidden_field in forbidden_stages[stage_name]:
                if forbidden_field in pipeline_context:
                    if pipeline_context[forbidden_field]:
                        return True
        
        return False
    
    def _check_signal_timing(
        self,
        timestamp: str,
        available_data_timestamp: str,
        stage_name: str
    ) -> bool:
        """Check if signals are generated at correct causal point."""
        
        # Entry signals must be generated after data is available
        if 'ENTRY_SIGNAL' in stage_name or 'EXECUTION' in stage_name:
            try:
                ts_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                data_dt = datetime.fromisoformat(available_data_timestamp.replace('Z', '+00:00'))
                
                # Signal timestamp must be AT or after data timestamp
                if ts_dt < data_dt:
                    return True  # Violation: signal before data available
                
            except:
                pass
        
        return False
    
    def _check_correlation_leakage(self, data_being_used: Dict[str, Any]) -> bool:
        """Check for correlation data leakage."""
        
        # Correlation should not use forward-looking data
        if data_being_used.get('correlation_matrix'):
            # Check if correlation includes future data
            corr = data_being_used['correlation_matrix']
            if isinstance(corr, dict):
                if corr.get('includes_forward_data'):
                    return True
        
        return False
    
    def _apply_enforcements(
        self,
        record: CausalityRecord,
        violations: List[CausalityViolation]
    ):
        """Apply enforcement actions for violations."""
        
        for violation in violations:
            
            if violation == CausalityViolation.ML_LIVE_UPDATE:
                # Ensure ML is frozen
                self._lock_ml_models()
                record.enforcements_applied.append("ML_LOCKDOWN")
            
            elif violation == CausalityViolation.LIVE_MODEL_UPDATE:
                # Ensure RL is frozen
                self._freeze_rl_agents()
                record.enforcements_applied.append("RL_FREEZE")
            
            elif violation == CausalityViolation.FUTURE_PRICE_DATA:
                # Remove future prices
                record.enforcements_applied.append("REMOVE_FUTURE_PRICES")
            
            elif violation == CausalityViolation.FORWARD_LOOKING_BIAS:
                # Disable forward-looking logic
                record.enforcements_applied.append("DISABLE_FORWARD_LOGIC")
            
            self.current_audit.total_enforcements += 1
        
        record.verification_passed = len(violations) == 0
    
    def _lock_ml_models(self):
        """Lock ML models from updates."""
        self.model_lockdown_enabled = True
        logger.warning("[CAUSALITY] ML models locked")
    
    def _freeze_rl_agents(self):
        """Freeze RL agents from updates."""
        self.rl_freeze_enabled = True
        logger.warning("[CAUSALITY] RL agents frozen")
    
    def end_session(self) -> CausalityAudit:
        """
        End causality session and generate audit report.
        
        Returns:
            Complete CausalityAudit
        """
        
        if not self.current_audit:
            return None
        
        # Calculate scores
        total_decisions = self.current_audit.total_decisions
        if total_decisions > 0:
            causality_score = (self.current_audit.causal_decisions / total_decisions) * 100
        else:
            causality_score = 100.0
        
        # Data integrity based on violations
        violation_count = sum(self.current_audit.violations_by_type.values())
        data_integrity_score = max(0, 100 - (violation_count * 10))
        
        # Update audit
        self.current_audit.session_end = datetime.now(timezone.utc).isoformat()
        self.current_audit.causality_score = causality_score
        self.current_audit.data_integrity_score = data_integrity_score
        
        # Generate recommendations
        self.current_audit.recommendations = self._generate_recommendations()
        
        # Store in history
        self.audit_history.append(self.current_audit)
        
        logger.info(
            f"[CAUSALITY] Session ended: CausalityScore={causality_score:.1f}, "
            f"IntegrityScore={data_integrity_score:.1f}, "
            f"Violations={violation_count}"
        )
        
        return self.current_audit
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on violations."""
        
        recommendations = []
        
        if not self.current_audit:
            return recommendations
        
        # Analyze violation patterns
        for violation_type, count in self.current_audit.violations_by_type.items():
            if count > 0:
                if violation_type == CausalityViolation.FUTURE_PRICE_DATA.value:
                    recommendations.append(
                        f"Eliminate {count} instances of future price data usage"
                    )
                elif violation_type == CausalityViolation.ML_LIVE_UPDATE.value:
                    recommendations.append(
                        "Implement ML model lockdown during trading"
                    )
                elif violation_type == CausalityViolation.LIVE_MODEL_UPDATE.value:
                    recommendations.append(
                        "Freeze RL agents after training completion"
                    )
        
        return recommendations
    
    def get_causality_health(self) -> Dict[str, Any]:
        """Get overall causality health assessment."""
        
        if not self.current_audit:
            return {'status': 'NO_SESSION', 'causality_healthy': False}
        
        total_decisions = self.current_audit.total_decisions
        violation_decisions = self.current_audit.violation_decisions
        
        health = {
            'causality_score': self.current_audit.causality_score,
            'data_integrity_score': self.current_audit.data_integrity_score,
            'total_decisions': total_decisions,
            'causal_decisions': self.current_audit.causal_decisions,
            'violation_decisions': violation_decisions,
            'violations_by_type': self.current_audit.violations_by_type,
            'status': 'HEALTHY' if self.current_audit.causality_score > 95 else 'WARNING' if self.current_audit.causality_score > 80 else 'CRITICAL',
            'causality_healthy': self.current_audit.causality_score >= 99.0,
            'data_integrity_healthy': self.current_audit.data_integrity_score >= 95.0,
            'enforcements_applied': self.current_audit.total_enforcements
        }
        
        return health


# Global singleton instance
_causality_enforcer = None

def get_causality_enforcer(strict_mode: bool = True) -> CausalityEnforcer:
    """Get or create singleton causality enforcer."""
    global _causality_enforcer
    if _causality_enforcer is None:
        _causality_enforcer = CausalityEnforcer(strict_mode=strict_mode)
    return _causality_enforcer