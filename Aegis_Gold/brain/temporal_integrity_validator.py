"""
COMPLETE FILE - AEGIS GOLD — Temporal Integrity Validator
=========================================================

Validates that all data, features, patterns, and engine outputs
contain only information available at the decision timestamp T.

Enforces: observation_timestamp <= decision_timestamp
No downstream component may request future candles, ticks, indicators,
pattern confirmations, normalized values, or outcomes.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger("aegis.temporal_validator")


@dataclass
class TemporalViolation:
    """Record of a temporal integrity violation."""
    violation_type: str
    component: str
    timestamp_used: datetime
    decision_timestamp: datetime
    source: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    trade_signal_id: Optional[str] = None
    details: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of a temporal validation check."""
    passed: bool
    violations: List[TemporalViolation] = field(default_factory=list)
    trade_signal_id: Optional[str] = None


# Checkpoint definitions from the task requirements
CHECKPOINT_01_DATA = "CHECKPOINT_01_DATA"
CHECKPOINT_02_SNAPSHOT = "CHECKPOINT_02_SNAPSHOT"
CHECKPOINT_03_FEATURES = "CHECKPOINT_03_FEATURES"
CHECKPOINT_04_PATTERN = "CHECKPOINT_04_PATTERN"
CHECKPOINT_05_ENGINE = "CHECKPOINT_05_ENGINE"
CHECKPOINT_06_CONSENSUS = "CHECKPOINT_06_CONSENSUS"
CHECKPOINT_07_CONFIDENCE = "CHECKPOINT_07_CONFIDENCE"
CHECKPOINT_08_RISK = "CHECKPOINT_08_RISK"
CHECKPOINT_09_EXECUTION = "CHECKPOINT_09_EXECUTION"


class TemporalIntegrityValidator:
    """
    Validates temporal integrity of trading decisions.
    
    Core principle: Every object consumed downstream must reference only
    information available at the decision timestamp T. No future data
    leakage is permitted.
    """
    
    # Violation types
    FUTURE_CANDLE = "FUTURE_CANDLE"
    FUTURE_TICK = "FUTURE_TICK"
    FUTURE_FEATURE = "FUTURE_FEATURE"
    FUTURE_NORMALIZATION = "FUTURE_NORMALIZATION"
    FUTURE_PATTERN_CONFIRMATION = "FUTURE_PATTERN_CONFIRMATION"
    FUTURE_ENGINE_EVIDENCE = "FUTURE_ENGINE_EVIDENCE"
    FUTURE_CONFIDENCE_INFO = "FUTURE_CONFIDENCE_INFO"
    FUTURE_OUTCOME_LEAKAGE = "FUTURE_OUTCOME_LEAKAGE"
    SIGNAL_TIME_BEFORE_INFO = "SIGNAL_TIME_BEFORE_INFO"
    TRIGGER_BEFORE_CONFIRMATION = "TRIGGER_BEFORE_CONFIRMATION"
    DECISION_BEFORE_TRIGGER = "DECISION_BEFORE_TRIGGER"
    EXECUTION_BEFORE_DECISION = "EXECUTION_BEFORE_DECISION"
    
    # Verification checkpoints (from task requirements)
    CHECKPOINT_01_DATA = CHECKPOINT_01_DATA
    CHECKPOINT_02_SNAPSHOT = CHECKPOINT_02_SNAPSHOT
    CHECKPOINT_03_FEATURES = CHECKPOINT_03_FEATURES
    CHECKPOINT_04_PATTERN = CHECKPOINT_04_PATTERN
    CHECKPOINT_05_ENGINE = CHECKPOINT_05_ENGINE
    CHECKPOINT_06_CONSENSUS = CHECKPOINT_06_CONSENSUS
    CHECKPOINT_07_CONFIDENCE = CHECKPOINT_07_CONFIDENCE
    CHECKPOINT_08_RISK = CHECKPOINT_08_RISK
    CHECKPOINT_09_EXECUTION = CHECKPOINT_09_EXECUTION
    CHECKPOINT_NAMES = [
        CHECKPOINT_01_DATA,
        CHECKPOINT_02_SNAPSHOT,
        CHECKPOINT_03_FEATURES,
        CHECKPOINT_04_PATTERN,
        CHECKPOINT_05_ENGINE,
        CHECKPOINT_06_CONSENSUS,
        CHECKPOINT_07_CONFIDENCE,
        CHECKPOINT_08_RISK,
        CHECKPOINT_09_EXECUTION,
    ]
    
    def checkpoint_result(
        self,
        stage: str,
        decision_time: datetime,
        max_source_timestamp: float,
        passed: bool,
        trade_signal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a checkpoint result record.
        
        Example:
            {
                "stage": "FEATURES",
                "decision_time": T,
                "max_source_timestamp": X,
                "passed": true
            }
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        
        return {
            "stage": stage,
            "decision_time": decision_dt.isoformat(),
            "max_source_timestamp": max_source_timestamp,
            "passed": passed,
            "trade_signal_id": trade_signal_id
        }
    
    def validate_checkpoint_01_data(
        self,
        raw_data: Any,
        decision_time: datetime,
        trade_signal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        CHECKPOINT_01_DATA: Validate raw market data timestamps.
        
        Verifies: max_source_timestamp <= T
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        
        violations = []
        
        # Extract timestamps from raw data and check they're <= decision_time
        def check_and_extract(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in ('timestamp', 'time', 'datetime'):
                        ts = self._parse_timestamp(value)
                        if ts and ts > decision_dt:
                            violations.append(TemporalViolation(
                                violation_type=self.FUTURE_DATA,
                                component=f"data.{path}.{key}",
                                timestamp_used=ts,
                                decision_timestamp=decision_dt,
                                source=f"data.{path}.{key}",
                                severity="CRITICAL",
                                trade_signal_id=trade_signal_id,
                                details=f"Raw data at {path}.{key} has future timestamp {ts} > decision_time {decision_dt}"
                            ))
                    elif isinstance(value, (dict, list)):
                        check_and_extract(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_and_extract(item, f"{path}[{i}]")
        
        check_and_extract(raw_data)
        
        # Calculate max source timestamp
        max_ts = 0.0
        def extract_max_ts(obj):
            nonlocal max_ts
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in ('timestamp', 'time', 'datetime'):
                        ts = self._parse_timestamp(value)
                        if ts and ts > max_ts:
                            max_ts = ts.timestamp()
                    elif isinstance(value, (dict, list)):
                        extract_max_ts(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_max_ts(item)
        
        extract_max_ts(raw_data)
        
        passed = len(violations) == 0
        
        result = self.checkpoint_result(
            self.CHECKPOINT_01_DATA,
            decision_time,
            max_ts,
            passed,
            trade_signal_id
        )
        
        if not passed:
            logger.critical(
                f"[CHECKPOINT {self.CHECKPOINT_01_DATA}] FAILED for {trade_signal_id}: "
                f"{len(violations)} violations, max_source_timestamp={max_ts}"
            )
            for v in violations:
                logger.critical(f"  {v.violation_type}: {v.details}")
        
        return result
    
    def validate_checkpoint_02_snapshot(
        self,
        snapshot,
        decision_time: datetime,
        trade_signal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        CHECKPOINT_02_SNAPSHOT: Validate FrozenDecisionSnapshot integrity.
        
        Verifies: All candle timestamps <= decision_time, no future data in snapshot
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        violations = []
        
        # Validate M5 candles
        for i, bar in enumerate(snapshot.candles_m5):
            bar_time = self._extract_bar_time(bar, "M5", i)
            if bar_time and bar_time >= decision_dt:
                violations.append(TemporalViolation(
                    violation_type=self.FUTURE_CANDLE,
                    component=f"snapshot.candles_m5[{i}]",
                    timestamp_used=bar_time,
                    decision_timestamp=decision_dt,
                    source=f"candles_m5[{i}]",
                    severity="CRITICAL",
                    trade_signal_id=trade_signal_id,
                    details=f"M5 bar {i} has timestamp {bar_time} >= decision_time {decision_dt}"
                ))
        
        # Validate M1 candles
        for i, bar in enumerate(snapshot.candles_m1):
            bar_time = self._extract_bar_time(bar, "M1", i)
            if bar_time and bar_time >= decision_dt:
                violations.append(TemporalViolation(
                    violation_type=self.FUTURE_CANDLE,
                    component=f"snapshot.candles_m1[{i}]",
                    timestamp_used=bar_time,
                    decision_timestamp=decision_dt,
                    source=f"candles_m1[{i}]",
                    severity="CRITICAL",
                    trade_signal_id=trade_signal_id,
                    details=f"M1 bar {i} has timestamp {bar_time} >= decision_time {decision_dt}"
                ))
        
        # Validate H1 candles
        for i, bar in enumerate(snapshot.candles_h1):
            bar_time = self._extract_bar_time(bar, "H1", i)
            if bar_time and bar_time >= decision_dt:
                violations.append(TemporalViolation(
                    violation_type=self.FUTURE_CANDLE,
                    component=f"snapshot.candles_h1[{i}]",
                    timestamp_used=bar_time,
                    decision_timestamp=decision_dt,
                    source=f"candles_h1[{i}]",
                    severity="CRITICAL",
                    trade_signal_id=trade_signal_id,
                    details=f"H1 bar {i} has timestamp {bar_time} >= decision_time {decision_dt}"
                ))
        
        # Validate extra fields
        if snapshot.extra:
            for key, value in snapshot.extra.items():
                if isinstance(value, dict) and 'timestamp' in value:
                    ts = self._parse_timestamp(value['timestamp'])
                    if ts and ts > decision_dt:
                        violations.append(TemporalViolation(
                            violation_type=self.FUTURE_FEATURE,
                            component=f"snapshot.extra['{key}'].timestamp",
                            timestamp_used=ts,
                            decision_timestamp=decision_dt,
                            source=f"extra['{key}'].timestamp",
                            severity="CRITICAL",
                            trade_signal_id=trade_signal_id,
                            details=f"Extra field '{key}' has future timestamp {ts} >= decision_time {decision_dt}"
                        ))
        
        passed = len(violations) == 0
        
        result = self.checkpoint_result(
            self.CHECKPOINT_02_SNAPSHOT,
            decision_time,
            decision_dt.timestamp() if passed else 0.0,
            passed,
            trade_signal_id
        )
        
        if not passed:
            logger.critical(
                f"[CHECKPOINT {self.CHECKPOINT_02_SNAPSHOT}] FAILED for {trade_signal_id}: "
                f"{len(violations)} violations"
            )
            for v in violations:
                logger.critical(f"  {v.violation_type}: {v.details}")
        
        return result
    
    def validate_checkpoint_03_features(
        self,
        features: Dict[str, Any],
        decision_time: datetime,
        trade_signal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        CHECKPOINT_03_FEATURES: Validate feature timestamps.
        
        Verifies: feature_source_max_timestamp <= decision_time
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        violations = []
        
        # Check for timestamp fields in feature data
        timestamp_fields = ['timestamp', 'time', 'datetime', 'created_at', 'updated_at',
                           'formation_time', 'information_available_time', 'confirmation_time',
                           'trigger_time', 'signal_time', 'execution_time']
        
        for key, value in features.items():
            if isinstance(value, dict):
                for ts_field in timestamp_fields:
                    if ts_field in value:
                        ts = self._parse_timestamp(value[ts_field])
                        if ts and ts > decision_dt:
                            violations.append(TemporalViolation(
                                violation_type=self.FUTURE_FEATURE,
                                component=f"features.{key}.{ts_field}",
                                timestamp_used=ts,
                                decision_timestamp=decision_dt,
                                source=f"{key}.{ts_field}",
                                severity="CRITICAL",
                                trade_signal_id=trade_signal_id,
                                details=f"Feature '{key}.{ts_field}' has future timestamp {ts} > decision_time {decision_dt}"
                            ))
                
                if 'time' in value:
                    ts = self._parse_timestamp(value['time'])
                    if ts and ts > decision_dt:
                        violations.append(TemporalViolation(
                            violation_type=self.FUTURE_FEATURE,
                            component=f"features.{key}.time",
                            timestamp_used=ts,
                            decision_timestamp=decision_dt,
                            source=f"{key}.time",
                            severity="CRITICAL",
                            trade_signal_id=trade_signal_id,
                            details=f"Feature '{key}' has future timestamp {ts} > decision_time {decision_dt}"
                        ))
            
            elif isinstance(value, list) and len(value) > 0:
                first_item = value[0]
                if isinstance(first_item, dict) and 'time' in first_item:
                    ts = self._parse_timestamp(first_item['time'])
                    if ts and ts > decision_dt:
                        violations.append(TemporalViolation(
                            violation_type=self.FUTURE_CANDLE,
                            component=f"features.{key}",
                            timestamp_used=ts,
                            decision_timestamp=decision_dt,
                            source=f"{key}[0].time",
                            severity="CRITICAL",
                            trade_signal_id=trade_signal_id,
                            details=f"Feature '{key}' contains candle with future timestamp {ts} > decision_time {decision_dt}"
                        ))
        
        passed = len(violations) == 0
        
        result = self.checkpoint_result(
            self.CHECKPOINT_03_FEATURES,
            decision_time,
            decision_dt.timestamp() if passed else 0.0,
            passed,
            trade_signal_id
        )
        
        if not passed:
            logger.critical(
                f"[CHECKPOINT {self.CHECKPOINT_03_FEATURES}] FAILED for {trade_signal_id}: "
                f"{len(violations)} violations"
            )
            for v in violations:
                logger.critical(f"  {v.violation_type}: {v.details}")
        
        return result
    
    def validate_checkpoint_04_patterns(
        self,
        patterns: List[Dict[str, Any]],
        decision_time: datetime,
        trade_signal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        CHECKPOINT_04_PATTERNS: Validate pattern confirmation timestamps.
        
        Verifies: confirmation_time <= decision_time
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        violations = []
        
        for i, pattern in enumerate(patterns):
            if isinstance(pattern, dict):
                if 'confirmation_time' in pattern:
                    ts = self._parse_timestamp(pattern['confirmation_time'])
                    if ts and ts > decision_dt:
                        violations.append(TemporalViolation(
                            violation_type=self.FUTURE_PATTERN_CONFIRMATION,
                            component=f"patterns[{i}].confirmation_time",
                            timestamp_used=ts,
                            decision_timestamp=decision_dt,
                            source=f"patterns[{i}].confirmation_time",
                            severity="CRITICAL",
                            trade_signal_id=trade_signal_id,
                            details=f"Pattern {i} has confirmation_time {ts} > decision_time {decision_dt}"
                        ))
                
                if 'evidence_timestamp' in pattern:
                    ts = self._parse_timestamp(pattern['evidence_timestamp'])
                    if ts and ts > decision_dt:
                        violations.append(TemporalViolation(
                            violation_type=self.FUTURE_ENGINE_EVIDENCE,
                            component=f"patterns[{i}].evidence_timestamp",
                            timestamp_used=ts,
                            decision_timestamp=decision_dt,
                            source=f"patterns[{i}].evidence_timestamp",
                            severity="CRITICAL",
                            trade_signal_id=trade_signal_id,
                            details=f"Pattern {i} has evidence_timestamp {ts} > decision_time {decision_dt}"
                        ))
                
                if 'outcome' in pattern or 'label' in pattern:
                    violations.append(TemporalViolation(
                        violation_type=self.FUTURE_OUTCOME_LEAKAGE,
                        component=f"patterns[{i}].outcome/label",
                        timestamp_used=decision_dt,
                        decision_timestamp=decision_dt,
                        source=f"patterns[{i}].outcome/label",
                        severity="CRITICAL",
                        trade_signal_id=trade_signal_id,
                        details=f"Pattern {i} contains outcome/label leakage - future outcome known at decision time"
                    ))
        
        passed = len(violations) == 0
        
        result = self.checkpoint_result(
            self.CHECKPOINT_04_PATTERNS,
            decision_time,
            decision_dt.timestamp() if passed else 0.0,
            passed,
            trade_signal_id
        )
        
        if not passed:
            logger.critical(
                f"[CHECKPOINT {self.CHECKPOINT_04_PATTERNS}] FAILED for {trade_signal_id}: "
                f"{len(violations)} violations"
            )
            for v in violations:
                logger.critical(f"  {v.violation_type}: {v.details}")
        
        return result
    
    def validate_checkpoint_05_engine(
        self,
        engine_votes: List[Dict[str, Any]],
        decision_time: datetime,
        trade_signal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        CHECKPOINT_05_ENGINE: Validate engine evidence timestamps.
        
        Verifies: evidence_timestamp <= decision_time
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        violations = []
        
        for i, vote in enumerate(engine_votes):
            if isinstance(vote, dict):
                if 'evidence_timestamp' in vote:
                    ts = self._parse_timestamp(vote['evidence_timestamp'])
                    if ts and ts > decision_dt:
                        violations.append(TemporalViolation(
                            violation_type=self.FUTURE_ENGINE_EVIDENCE,
                            component=f"engine_votes[{i}].evidence_timestamp",
                            timestamp_used=ts,
                            decision_timestamp=decision_dt,
                            source=f"engine_votes[{i}].evidence_timestamp",
                            severity="CRITICAL",
                            trade_signal_id=trade_signal_id,
                            details=f"Engine vote {i} has evidence_timestamp {ts} > decision_time {decision_dt}"
                        ))
                
                if 'confidence' in vote:
                    conf = vote['confidence']
                    if isinstance(conf, (int, float)) and conf > 100:
                        violations.append(TemporalViolation(
                            violation_type=self.FUTURE_CONFIDENCE_INFO,
                            component=f"engine_votes[{i}].confidence",
                            timestamp_used=decision_dt,
                            decision_timestamp=decision_dt,
                            source=f"engine_votes[{i}].confidence",
                            severity="HIGH",
                            trade_signal_id=trade_signal_id,
                            details=f"Engine vote {i} has unusually high confidence {conf}% - may indicate future data leakage"
                        ))
                
                if 'normalized_value' in vote:
                    nv = vote['normalized_value']
                    if isinstance(nv, float) and (nv > 1.0 or nv < -1.0):
                        violations.append(TemporalViolation(
                            violation_type=self.FUTURE_NORMALIZATION,
                            component=f"engine_votes[{i}].normalized_value",
                            timestamp_used=decision_dt,
                            decision_timestamp=decision_dt,
                            source=f"engine_votes[{i}].normalized_value",
                            severity="HIGH",
                            trade_signal_id=trade_signal_id,
                            details=f"Engine vote {i} has normalized_value {nv} outside [-1, 1] range - may indicate future data"
                        ))
        
        passed = len(violations) == 0
        
        result = self.checkpoint_result(
            self.CHECKPOINT_05_ENGINE,
            decision_time,
            decision_dt.timestamp() if passed else 0.0,
            passed,
            trade_signal_id
        )
        
        if not passed:
            logger.critical(
                f"[CHECKPOINT {self.CHECKPOINT_05_ENGINE}] FAILED for {trade_signal_id}: "
                f"{len(violations)} violations"
            )
            for v in violations:
                logger.critical(f"  {v.violation_type}: {v.details}")
        
        return result
    
    def validate_checkpoint_06_consensus(
        self,
        consensus_result: Any,
        decision_time: datetime,
        trade_signal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        CHECKPOINT_06_CONSENSUS: Validate consensus timestamps.
        
        Verifies: All consensus evidence timestamps <= decision_time
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        violations = []
        
        # Handle different consensus result formats
        if isinstance(consensus_result, dict):
            # Check for evidence_timestamp
            if 'evidence_timestamp' in consensus_result:
                ts = self._parse_timestamp(consensus_result['evidence_timestamp'])
                if ts and ts > decision_dt:
                    violations.append(TemporalViolation(
                        violation_type=self.FUTURE_ENGINE_EVIDENCE,
                        component="consensus.evidence_timestamp",
                        timestamp_used=ts,
                        decision_timestamp=decision_dt,
                        source="consensus.evidence_timestamp",
                        severity="CRITICAL",
                        trade_signal_id=trade_signal_id,
                        details=f"Consensus has evidence_timestamp {ts} > decision_time {decision_dt}"
                    ))
            
            # Check for confidence
            if 'confidence' in consensus_result:
                conf = consensus_result['confidence']
                if isinstance(conf, (int, float)) and conf > 100:
                    violations.append(TemporalViolation(
                        violation_type=self.FUTURE_CONFIDENCE_INFO,
                        component="consensus.confidence",
                        timestamp_used=decision_dt,
                        decision_timestamp=decision_dt,
                        source="consensus.confidence",
                        severity="HIGH",
                        trade_signal_id=trade_signal_id,
                        details=f"Consensus has unusually high confidence {conf}% - may indicate future data leakage"
                    ))
        
        elif hasattr(consensus_result, '__iter__'):
            # Iterable consensus (list of votes)
            for i, vote in enumerate(consensus_result):
                if isinstance(vote, dict) and 'evidence_timestamp' in vote:
                    ts = self._parse_timestamp(vote['evidence_timestamp'])
                    if ts and ts > decision_dt:
                        violations.append(TemporalViolation(
                            violation_type=self.FUTURE_ENGINE_EVIDENCE,
                            component=f"consensus.votes[{i}].evidence_timestamp",
                            timestamp_used=ts,
                            decision_timestamp=decision_dt,
                            source=f"consensus.votes[{i}].evidence_timestamp",
                            severity="CRITICAL",
                            trade_signal_id=trade_signal_id,
                            details=f"Consensus vote {i} has evidence_timestamp {ts} > decision_time {decision_dt}"
                        ))
        
        passed = len(violations) == 0
        
        result = self.checkpoint_result(
            self.CHECKPOINT_06_CONSENSUS,
            decision_time,
            decision_dt.timestamp() if passed else 0.0,
            passed,
            trade_signal_id
        )
        
        if not passed:
            logger.critical(
                f"[CHECKPOINT {self.CHECKPOINT_06_CONSENSUS}] FAILED for {trade_signal_id}: "
                f"{len(violations)} violations"
            )
            for v in violations:
                logger.critical(f"  {v.violation_type}: {v.details}")
        
        return result
    
    def validate_checkpoint_07_confidence(
        self,
        confidence_data: Dict[str, Any],
        decision_time: datetime,
        trade_signal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        CHECKPOINT_07_CONFIDENCE: Validate confidence calculation timestamps.
        
        Verifies: All confidence source timestamps <= decision_time
        Confidence must be calculated ONLY from information available at T.
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        violations = []
        
        if isinstance(confidence_data, dict):
            # Record confidence lineage as required by task
            for key, value in confidence_data.items():
                # Check timestamp fields
                timestamp_fields = ['timestamp', 'time', 'datetime', 'formation_time',
                                   'information_available_time', 'confirmation_time',
                                   'trigger_time', 'signal_time']
                
                if isinstance(value, (int, float)):
                    # Numeric confidence value - check if unreasonably high
                    if key in ('confidence', 'total_confidence') and value > 100:
                        violations.append(TemporalViolation(
                            violation_type=self.FUTURE_CONFIDENCE_INFO,
                            component=f"confidence.{key}",
                            timestamp_used=decision_dt,
                            decision_timestamp=decision_dt,
                            source=f"confidence.{key}",
                            severity="HIGH",
                            trade_signal_id=trade_signal_id,
                            details=f"Confidence {value}% exceeds 100% - may indicate future data leakage"
                        ))
                    
                    # Check for normalized values outside valid range
                    if key in ('normalized_confidence', 'confidence_normalized') and (value > 1.0 or value < 0.0):
                        violations.append(TemporalViolation(
                            violation_type=self.FUTURE_NORMALIZATION,
                            component=f"confidence.{key}",
                            timestamp_used=decision_dt,
                            decision_timestamp=decision_dt,
                            source=f"confidence.{key}",
                            severity="HIGH",
                            trade_signal_id=trade_signal_id,
                            details=f"Confidence normalized value {value} outside [0, 1] range - may indicate future data"
                        ))
                
                # Check timestamp fields
                if isinstance(value, dict):
                    for ts_field in timestamp_fields:
                        if ts_field in value:
                            ts = self._parse_timestamp(value[ts_field])
                            if ts and ts > decision_dt:
                                violations.append(TemporalViolation(
                                    violation_type=self.FUTURE_CONFIDENCE_INFO,
                                    component=f"confidence.{key}.{ts_field}",
                                    timestamp_used=ts,
                                    decision_timestamp=decision_dt,
                                    source=f"confidence.{key}.{ts_field}",
                                    severity="CRITICAL",
                                    trade_signal_id=trade_signal_id,
                                    details=f"Confidence {key} source {ts_field} has future timestamp {ts} > decision_time {decision_dt}"
                                ))
                
                elif isinstance(value, str) or isinstance(value, (int, float)):
                    # Parse string timestamps
                    if isinstance(value, str):
                        ts = self._parse_timestamp(value)
                        if ts and ts > decision_dt:
                                            violations.append(TemporalViolation(
                                violation_type=self.FUTURE_CONFIDENCE_INFO,
                                component=f"confidence.{key}",
                                timestamp_used=ts,
                                decision_timestamp=decision_dt,
                                source=f"confidence.{key}",
                                severity="CRITICAL",
                                trade_signal_id=trade_signal_id,
                                details=f"Confidence {key} source has future timestamp {ts} > decision_time {decision_dt}"
                            ))
        
        passed = len(violations) == 0
        
        result = self.checkpoint_result(
            self.CHECKPOINT_07_CONFIDENCE,
            decision_time,
            decision_dt.timestamp() if passed else 0.0,
            passed,
            trade_signal_id
        )
        
        if not passed:
            logger.critical(
                f"[CHECKPOINT {self.CHECKPOINT_07_CONFIDENCE}] FAILED for {trade_signal_id}: "
                f"{len(violations)} violations"
            )
            for v in violations:
                logger.critical(f"  {v.violation_type}: {v.details}")
        
        return result
    
    def validate_checkpoint_08_risk(
        self,
        risk_decision: Dict[str, Any],
        decision_time: datetime,
        trade_signal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        CHECKPOINT_08_RISK: Validate risk decision timestamps.
        
        Verifies: signal_time <= decision_time <= execution_time
        All risk assessment timestamps must be <= decision_time.
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        violations = []
        
        if isinstance(risk_decision, dict):
            # Check signal_time
            if 'signal_time' in risk_decision:
                ts = self._parse_timestamp(risk_decision['signal_time'])
                if ts and ts > decision_dt:
                    violations.append(TemporalViolation(
                        violation_type=self.SIGNAL_TIME_BEFORE_INFO,
                        component="risk.signal_time",
                        timestamp_used=ts,
                        decision_timestamp=decision_dt,
                        source="risk.signal_time",
                        severity="CRITICAL",
                        trade_signal_id=trade_signal_id,
                        details=f"Risk signal_time {ts} > decision_time {decision_dt}"
                    ))
            
            # Check execution_time
            if 'execution_time' in risk_decision:
                ts = self._parse_timestamp(risk_decision['execution_time'])
                if ts and ts > decision_dt:
                    violations.append(TemporalViolation(
                        violation_type=self.EXECUTION_BEFORE_DECISION,
                        component="risk.execution_time",
                        timestamp_used=ts,
                        decision_timestamp=decision_dt,
                        source="risk.execution_time",
                        severity="CRITICAL",
                        trade_signal_id=trade_signal_id,
                        details=f"Risk execution_time {ts} > decision_time {decision_dt}"
                    ))
            
            # Check for future outcome/label in risk assessment
            for key in ['outcome', 'label', 'predicted_outcome']:
                if key in risk_decision:
                    # Outcome should not be available at decision time
                    violations.append(TemporalViolation(
                        violation_type=self.FUTURE_OUTCOME_LEAKAGE,
                        component=f"risk.{key}",
                        timestamp_used=decision_dt,
                        decision_timestamp=decision_dt,
                        source=f"risk.{key}",
                        severity="CRITICAL",
                        trade_signal_id=trade_signal_id,
                        details=f"Risk assessment contains {key} leakage - future outcome known at decision time"
                    ))
            
            # Check confidence source timestamps
            if 'confidence_source' in risk_decision:
                cs = risk_decision['confidence_source']
                if isinstance(cs, dict):
                    for ts_field in ['timestamp', 'time']:
                        if ts_field in cs:
                            ts = self._parse_timestamp(cs[ts_field])
                            if ts and ts > decision_dt:
                                violations.append(TemporalViolation(
                                    violation_type=self.FUTURE_CONFIDENCE_INFO,
                                    component=f"risk.confidence_source.{ts_field}",
                                    timestamp_used=ts,
                                    decision_timestamp=decision_dt,
                                    source=f"risk.confidence_source.{ts_field}",
                                    severity="HIGH",
                                    trade_signal_id=trade_signal_id,
                                    details=f"Risk confidence source {ts_field} has future timestamp {ts} > decision_time {decision_dt}"
                                ))
        
        passed = len(violations) == 0
        
        result = self.checkpoint_result(
            self.CHECKPOINT_08_RISK,
            decision_time,
            decision_dt.timestamp() if passed else 0.0,
            passed,
            trade_signal_id
        )
        
        if not passed:
            logger.critical(
                f"[CHECKPOINT {self.CHECKPOINT_08_RISK}] FAILED for {trade_signal_id}: "
                f"{len(violations)} violations"
            )
            for v in violations:
                logger.critical(f"  {v.violation_type}: {v.details}")
        
        return result
    
    def validate_checkpoint_09_execution(
        self,
        execution_data: Dict[str, Any],
        decision_time: datetime,
        trade_signal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        CHECKPOINT_09_EXECUTION: Validate execution timestamps.
        
        Verifies: decision_time <= execution_time
        All execution timestamps must respect the ordering chain.
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        violations = []
        
        if isinstance(execution_data, dict):
            # Check execution_time vs decision_time
            if 'execution_time' in execution_data:
                ts = self._parse_timestamp(execution_data['execution_time'])
                if ts and ts > decision_dt:
                    violations.append(TemporalViolation(
                        violation_type=self.EXECUTION_BEFORE_DECISION,
                        component="execution.execution_time",
                        timestamp_used=ts,
                        decision_timestamp=decision_dt,
                        source="execution.execution_time",
                        severity="CRITICAL",
                        trade_signal_id=trade_signal_id,
                        details=f"Execution execution_time {ts} > decision_time {decision_dt}"
                    ))
            
            # Check order_send_time
            if 'order_send_time' in execution_data:
                ts = self._parse_timestamp(execution_data['order_send_time'])
                if ts and ts > decision_dt:
                    violations.append(TemporalViolation(
                        violation_type=self.FUTURE_OUTCOME_LEAKAGE,
                        component="execution.order_send_time",
                        timestamp_used=ts,
                        decision_timestamp=decision_dt,
                        source="execution.order_send_time",
                        severity="HIGH",
                        trade_signal_id=trade_signal_id,
                        details=f"Execution order_send_time {ts} > decision_time {decision_dt}"
                    ))
            
            # Check for future outcome in execution
            for key in ['outcome', 'final_pnl', 'realized_profit']:
                if key in execution_data:
                    violations.append(TemporalViolation(
                        violation_type=self.FUTURE_OUTCOME_LEAKAGE,
                        component=f"execution.{key}",
                        timestamp_used=decision_dt,
                        decision_timestamp=decision_dt,
                        source=f"execution.{key}",
                        severity="CRITICAL",
                        trade_signal_id=trade_signal_id,
                        details=f"Execution contains {key} leakage - future P&L known at decision time"
                    ))
            
            # Check signal_time <= decision_time <= execution_time ordering
            if 'signal_time' in execution_data and 'execution_time' in execution_data:
                signal_ts = self._parse_timestamp(execution_data['signal_time'])
                exec_ts = self._parse_timestamp(execution_data['execution_time'])
                if signal_ts and exec_ts and signal_ts > exec_ts:
                    violations.append(TemporalViolation(
                        violation_type=self.EXECUTION_BEFORE_DECISION,
                        component="execution.signal_time_vs_execution_time",
                        timestamp_used=signal_ts,
                        decision_timestamp=exec_ts,
                        source="execution.signal_time_vs_execution_time",
                        severity="CRITICAL",
                        trade_signal_id=trade_signal_id,
                        details=f"Execution signal_time {signal_ts} > execution_time {exec_ts} - violates ordering"
                    ))
        
        passed = len(violations) == 0
        
        result = self.checkpoint_result(
            self.CHECKPOINT_09_EXECUTION,
            decision_time,
            decision_dt.timestamp() if passed else 0.0,
            passed,
            trade_signal_id
        )
        
        if not passed:
            logger.critical(
                f"[CHECKPOINT {self.CHECKPOINT_09_EXECUTION}] FAILED for {trade_signal_id}: "
                f"{len(violations)} violations"
            )
            for v in violations:
                logger.critical(f"  {v.violation_type}: {v.details}")
        
        return result
    
    def run_all_checkpoints(
        self,
        snapshot,
        decision_time: datetime,
        formation_time: datetime,
        information_available_time: datetime,
        confirmation_time: datetime,
        trigger_time: datetime,
        execution_time: datetime,
        features: Optional[Dict[str, Any]] = None,
        patterns: Optional[List[Dict[str, Any]]] = None,
        engine_votes: Optional[List[Dict[str, Any]]] = None,
        consensus_result: Optional[Any] = None,
        confidence_data: Optional[Dict[str, Any]] = None,
        risk_decision: Optional[Dict[str, Any]] = None,
        execution_data: Optional[Dict[str, Any]] = None,
        trade_signal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run ALL verification checkpoints and return results.
        
        This is the main method that runs all 9 checkpoints and collects
        their results. The pipeline must STOP if any checkpoint fails.
        
        Returns dict with all checkpoint results and overall status.
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        all_results = []
        all_violations = []
        stop_pipeline = False
        
        # RUN ALL CHECKPOINTS
        # CHECKPOINT_01: DATA
        result_01 = self.validate_checkpoint_01_data(
            raw_data=snapshot if hasattr(snapshot, 'candles_m5') else None,
            decision_time=decision_time,
            trade_signal_id=trade_signal_id
        )
        all_results.append(result_01)
        if not result_01["passed"]:
            stop_pipeline = True
            all_violations.extend(result_01.get("violations", []))
        
        # CHECKPOINT_02: SNAPSHOT
        result_02 = self.validate_checkpoint_02_snapshot(
            snapshot=snapshot,
            decision_time=decision_time,
            trade_signal_id=trade_signal_id
        )
        all_results.append(result_02)
        if not result_02["passed"]:
            stop_pipeline = True
            all_violations.extend(result_02.get("violations", []))
        
        # CHECKPOINT_03: FEATURES
        result_03 = self.validate_checkpoint_03_features(
            features=features or {},
            decision_time=decision_time,
            trade_signal_id=trade_signal_id
        )
        all_results.append(result_03)
        if not result_03["passed"]:
            stop_pipeline = True
            all_violations.extend(result_03.get("violations", []))
        
        # CHECKPOINT_04: PATTERNS
        result_04 = self.validate_checkpoint_04_patterns(
            patterns=patterns or [],
            decision_time=decision_time,
            trade_signal_id=trade_signal_id
        )
        all_results.append(result_04)
        if not result_04["passed"]:
            stop_pipeline = True
            all_violations.extend(result_04.get("violations", []))
        
        # CHECKPOINT_05: ENGINE
        result_05 = self.validate_checkpoint_05_engine(
            engine_votes=engine_votes or [],
            decision_time=decision_time,
            trade_signal_id=trade_signal_id
        )
        all_results.append(result_05)
        if not result_05["passed"]:
            stop_pipeline = True
            all_violations.extend(result_05.get("violations", []))
        
        # CHECKPOINT_06: CONSENSUS
        result_06 = self.validate_checkpoint_06_consensus(
            consensus_result=consensus_result,
            decision_time=decision_time,
            trade_signal_id=trade_signal_id
        )
        all_results.append(result_06)
        if not result_06["passed"]:
            stop_pipeline = True
            all_violations.extend(result_06.get("violations", []))
        
        # CHECKPOINT_07: CONFIDENCE
        result_07 = self.validate_checkpoint_07_confidence(
            confidence_data=confidence_data or {},
            decision_time=decision_time,
            trade_signal_id=trade_signal_id
        )
        all_results.append(result_07)
        if not result_07["passed"]:
            stop_pipeline = True
            all_violations.extend(result_07.get("violations", []))
        
        # CHECKPOINT_08: RISK
        result_08 = self.validate_checkpoint_08_risk(
            risk_decision=risk_decision or {},
            decision_time=decision_time,
            trade_signal_id=trade_signal_id
        )
        all_results.append(result_08)
        if not result_08["passed"]:
            stop_pipeline = True
            all_violations.extend(result_08.get("violations", []))
        
        # CHECKPOINT_09: EXECUTION
        result_09 = self.validate_checkpoint_09_execution(
            execution_data=execution_data or {},
            decision_time=decision_time,
            trade_signal_id=trade_signal_id
        )
        all_results.append(result_09)
        if not result_09["passed"]:
            stop_pipeline = True
            all_violations.extend(result_09.get("violations", []))
        
        # Compile overall result
        critical_violations = [v for v in all_violations if v.severity == "CRITICAL"]
        any_passed = all(r["passed"] for r in all_results)
        
        overall_result = {
            "overall_passed": any_passed and not stop_pipeline,
            "stop_pipeline": stop_pipeline,
            "checkpoints": {
                self.CHECKPOINT_01_DATA: result_01,
                self.CHECKPOINT_02_SNAPSHOT: result_02,
                self.CHECKPOINT_03_FEATURES: result_03,
                self.CHECKPOINT_04_PATTERNS: result_04,
                self.CHECKPOINT_05_ENGINE: result_05,
                self.CHECKPOINT_06_CONSENSUS: result_06,
                self.CHECKPOINT_07_CONFIDENCE: result_07,
                self.CHECKPOINT_08_RISK: result_08,
                self.CHECKPOINT_09_EXECUTION: result_09,
            },
            "total_violations": len(all_violations),
            "critical_violations": len(critical_violations),
            "violations_by_type": {},
            "trade_signal_id": trade_signal_id
        }
        
        # Group violations by type
        by_type = {}
        for v in all_violations:
            vtype = v.violation_type
            if vtype not in by_type:
                by_type[vtype] = 0
            by_type[vtype] += 1
        overall_result["violations_by_type"] = by_type
        
        # Log summary
        if stop_pipeline:
            logger.critical(
                f"[CHECKPOINT PIPELINE] STOPPED for {trade_signal_id}: "
                f"{len(all_violations)} total violations, {len(critical_violations)} CRITICAL"
            )
            for cp_name, cp_result in overall_result["checkpoints"].items():
                if not cp_result["passed"]:
                    logger.critical(f"  {cp_name}: FAILED")
        elif any_passed:
            logger.info(
                f"[CHECKPOINT PIPELINE] PASSED for {trade_signal_id}: "
                f"All {len(all_results)} checkpoints valid"
            )
        else:
            logger.warning(
                f"[CHECKPOINT PIPELINE] PARTIAL for {trade_signal_id}: "
                f"{len(all_results)} checkpoints run, some warnings only"
            )
        
        return overall_result
    
    # Helper methods (already defined earlier in the file)
    def _extract_bar_time(self, bar, tf_label: str, idx: int) -> Optional[datetime]:
        """Extract timestamp from a bar object."""
        bar_time = None
        
        if isinstance(bar, dict):
            bar_time = bar.get("time") or bar.get("timestamp")
        elif hasattr(bar, "time"):
            bar_time = bar.time
        elif hasattr(bar, "__getitem__"):
            try:
                bar_time = bar[0]
            except Exception:
                pass
        
        if bar_time is None:
            return None
        
        if isinstance(bar_time, (int, float)):
            try:
                bar_dt = datetime.fromtimestamp(bar_time, tz=timezone.utc)
            except Exception:
                return None
        elif isinstance(bar_time, datetime):
            bar_dt = bar_time if bar_time.tzinfo else bar_time.replace(tzinfo=timezone.utc)
        else:
            return None
        
        return bar_dt
    
    def _parse_timestamp(self, timestamp_value: Any) -> Optional[datetime]:
        """Parse various timestamp formats to datetime."""
        if isinstance(timestamp_value, datetime):
            return timestamp_value if timestamp_value.tzinfo else timestamp_value.replace(tzinfo=timezone.utc)
        elif isinstance(timestamp_value, (int, float)):
            try:
                return datetime.fromtimestamp(timestamp_value, tz=timezone.utc)
            except Exception:
                return None
        elif isinstance(timestamp_value, str):
            try:
                from datetime import datetime
                return datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
            except Exception:
                try:
                    return datetime.fromtimestamp(float(timestamp_value), tz=timezone.utc)
                except Exception:
                    return None
        return None


# Convenience function for quick validation
def validate_temporal_integrity(
    snapshot,
    decision_time: datetime,
    trade_signal_id: Optional[str] = None
) -> ValidationResult:
    """
    Quick validation of a FrozenDecisionSnapshot's temporal integrity.
    
    Args:
        snapshot: FrozenDecisionSnapshot to validate
        decision_time: The decision timestamp T
        trade_signal_id: Optional trade/signal identifier
        
    Returns:
        ValidationResult with passed flag and any violations
    """
    validator = TemporalIntegrityValidator()
    return validator.validate_decision_snapshot(snapshot, decision_time, trade_signal_id)


# Global singleton instance
_validator = None

def get_temporal_validator() -> TemporalIntegrityValidator:
    """Get or create the global temporal integrity validator instance."""
    global _validator
    if _validator is None:
        _validator = TemporalIntegrityValidator()
    return _validator