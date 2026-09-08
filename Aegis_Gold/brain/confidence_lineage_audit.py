"""
AEGIS GOLD — Confidence Lineage Audit
=====================================

Traces confidence back to every input and ensures confidence is calculated
ONLY from information available at T.

For each confidence value, record:
    confidence
    confidence_source
    engine_votes
    feature timestamps
    pattern timestamps
    model version
    calibration model version
    training dataset range
    decision timestamp

Ensure confidence is calculated ONLY from information available at T.

IMPORTANT:
DO NOT CAP CONFIDENCE AT 65% YET.
First determine why:
    65-70% PF ≈ 121.27
and:
    75-100% → 100% WR / PF 1.0 / zero DD
occur.
"""

import numpy as np
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import copy

logger = logging.getLogger("aegis.confidence_lineage")


@dataclass
class ConfidenceEntry:
    """Record of a confidence value and its sources."""
    confidence: float  # 0-100
    confidence_source: str  # Which component generated this confidence
    engine_votes: Dict[str, float]  # Individual engine vote scores
    feature_timestamps: Dict[str, datetime]  # Timestamps of feature data used
    pattern_timestamps: Dict[str, datetime]  # Timestamps of pattern data used
    model_version: str  # ML model version
    calibration_model_version: str  # Calibration model version
    training_dataset_range: Tuple[datetime, datetime]  # (start, end) of training data
    decision_timestamp: datetime  # When the decision was made
    data_provenance: Dict[str, Any]  # Where each input came from
    within_temporal_contract: bool  # Whether all data was <= decision_time


@dataclass
class ConfidenceBucket:
    """Bucket for confidence-based statistical analysis."""
    min_confidence: float
    max_confidence: float
    trades: List[Dict] = field(default_factory=list)
    win_count: int = 0
    loss_count: int = 0
    total_pnl: float = 0.0
    total_r: float = 0.0  # Total realized R
    max_dd: float = 0.0  # Max drawdown
    trade_count: int = 0
    sample_size_note: str = ""  # e.g., "exploratory", "weak evidence", "usable"


class ConfidenceLineageAudit:
    """
    Audits confidence calculations to ensure temporal integrity.
    
    Core principle: Confidence must be calculated ONLY from information
    available at the decision timestamp T. Any confidence that depends
    on future data is a temporal integrity violation.
    """
    
    def __init__(self):
        self.audit_trail: List[ConfidenceEntry] = []
        self.buckets: Dict[str, ConfidenceBucket] = {}
        self.violations: List[Dict] = []
    
    def audit_confidence(
        self,
        confidence_value: float,
        confidence_source: str,
        engine_votes: Dict[str, float],
        feature_data: Dict[str, Any],
        pattern_data: Optional[List[Dict[str, Any]]],
        model_version: str,
        calibration_version: str,
        training_range: Tuple[datetime, datetime],
        decision_time: datetime,
        snapshot: Optional[Any] = None,
    ) -> ConfidenceEntry:
        """
        Audit a confidence calculation for temporal integrity.
        
        Records the confidence entry with full lineage and checks that
        all data used is within the temporal contract (<= decision_time).
        
        Returns ConfidenceEntry with provenance information.
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        
        # Check feature data timestamps
        feature_timestamps = {}
        feature_provenance = {}
        
        if isinstance(feature_data, dict):
            timestamp_fields = ['timestamp', 'time', 'datetime', 'formation_time',
                               'information_available_time', 'confirmation_time',
                               'trigger_time', 'signal_time', 'execution_time']
            
            for key, value in feature_data.items():
                if isinstance(value, (int, float)):
                    # Numeric value - could be a timestamp epoch
                    try:
                        ts = datetime.fromtimestamp(value, tz=timezone.utc) if value > 1000000 else None
                        if ts:
                            feature_timestamps[key] = ts
                            if ts > decision_dt:
                                self.violations.append({
                                    "type": "FUTURE_FEATURE_TIMESTAMP",
                                    "component": f"confidence.{key}",
                                    "timestamp_used": ts,
                                    "decision_timestamp": decision_dt,
                                    "severity": "CRITICAL",
                                    "details": f"Feature '{key}' has future timestamp {ts} > decision_time {decision_dt}"
                                })
                    except Exception:
                        pass
                elif isinstance(value, dict):
                    # Nested dict - check for timestamps
                    for ts_field in timestamp_fields:
                        if ts_field in value:
                            try:
                                ts_val = value[ts_field]
                                if isinstance(ts_val, (int, float)):
                                    ts = datetime.fromtimestamp(ts_val, tz=timezone.utc) if ts_val > 1000000 else None
                                    if ts:
                                        feature_timestamps[f"{key}.{ts_field}"] = ts
                                        if ts > decision_dt:
                                            self.violations.append({
                                                "type": "FUTURE_FEATURE_TIMESTAMP",
                                                "component": f"confidence.{key}.{ts_field}",
                                                "timestamp_used": ts,
                                                "decision_timestamp": decision_dt,
                                                "severity": "CRITICAL",
                                                "details": f"Feature '{key}.{ts_field}' has future timestamp {ts} > decision_time {decision_dt}"
                                            })
                            except Exception:
                                pass
        
        # Check pattern data timestamps
        pattern_timestamps = {}
        if pattern_data:
            for i, pattern in enumerate(pattern_data):
                if isinstance(pattern, dict):
                    if 'confirmation_time' in pattern:
                        try:
                            ts_val = pattern['confirmation_time']
                            if isinstance(ts_val, (int, float)):
                                ts = datetime.fromtimestamp(ts_val, tz=timezone.utc) if ts_val > 1000000 else None
                                if ts:
                                    pattern_timestamps[f"pattern[{i}].confirmation_time"] = ts
                                    if ts > decision_dt:
                                        self.violations.append({
                                            "type": "FUTURE_PATTERN_CONFIRMATION",
                                            "component": f"confidence.patterns[{i}].confirmation_time",
                                            "timestamp_used": ts,
                                            "decision_timestamp": decision_dt,
                                            "severity": "CRITICAL",
                                            "details": f"Pattern {i} has confirmation_time {ts} > decision_time {decision_dt}"
                                        })
                        except Exception:
                            pass
                    
                    if 'evidence_timestamp' in pattern:
                        try:
                            ts_val = pattern['evidence_timestamp']
                            if isinstance(ts_val, (int, float)):
                                ts = datetime.fromtimestamp(ts_val, tz=timezone.utc) if ts_val > 1000000 else None
                                if ts:
                                    pattern_timestamps[f"pattern[{i}].evidence_timestamp"] = ts
                                    if ts > decision_dt:
                                        self.violations.append({
                                            "type": "FUTURE_ENGINE_EVIDENCE",
                                            "component": f"confidence.patterns[{i}].evidence_timestamp",
                                            "timestamp_used": ts,
                                            "decision_timestamp": decision_dt,
                                            "severity": "CRITICAL",
                                            "details": f"Pattern {i} has evidence_timestamp {ts} > decision_time {decision_dt}"
                                        })
                        except Exception:
                            pass
        
        # Record the confidence entry
        entry = ConfidenceEntry(
            confidence=confidence_value,
            confidence_source=confidence_source,
            engine_votes=copy.deepcopy(engine_votes),
            feature_timestamps=feature_timestamps,
            pattern_timestamps=pattern_timestamps,
            model_version=model_version,
            calibration_model_version=calibration_version,
            training_dataset_range=training_range,
            decision_timestamp=decision_dt,
            data_provenance={
                "feature_data": feature_provenance,
                "pattern_data": copy.deepcopy(pattern_data) if pattern_data else None,
            },
            within_temporal_contract=len([v for v in self.violations 
                                          if "confidence" in str(v.get("component", ""))]) == 0
        )
        
        # Add to audit trail
        self.audit_trail.append(entry)
        
        # Clear violations for next audit (or keep accumulating)
        # self.violations = [v for v in self.violations if "confidence" not in str(v.get("component", ""))]
        
        return entry
    
    def audit_confidence_bucket(
        self,
        confidence: float,
        trade_outcome: float,  # pnl in USD or R multiples
        feature_data: Dict[str, Any],
        pattern_data: Optional[List[Dict[str, Any]]],
        model_version: str,
        calibration_version: str,
        training_range: Tuple[datetime, datetime],
        decision_time: datetime,
        snapshot: Optional[Any] = None,
    ) -> ConfidenceEntry:
        """
        Audit a confidence value within a bucket analysis context.
        
        Also tracks bucket statistics (win/loss, PF, etc.)
        """
        # First, do the standard audit
        entry = self.audit_confidence(
            confidence_value=confidence_value,
            confidence_source="bucket_analysis",
            engine_votes={},
            feature_data=feature_data,
            pattern_data=pattern_data,
            model_version=model_version,
            calibration_version=calibration_version,
            training_range=training_range,
            decision_time=decision_time,
            snapshot=snapshot,
        )
        
        # Track bucket statistics
        bucket_key = f"{int(confidence_value//5)*5}-{int(confidence_value//5+1)*5}"
        if bucket_key not in self.buckets:
            self.buckets[bucket_key] = ConfidenceBucket(
                min_confidence=int(confidence_value//5)*5,
                max_confidence=int(confidence_value//5+1)*5,
            )
        
        bucket = self.buckets[bucket_key]
        bucket.trades.append({
            "confidence": confidence_value,
            "outcome": trade_outcome,
            "model_version": model_version,
            "decision_time": decision_time.isoformat(),
        })
        bucket.trade_count += 1
        
        if trade_outcome > 0:
            bucket.win_count += 1
        else:
            bucket.loss_count += 1
        
        bucket.total_pnl += trade_outcome
        
        return entry
    
    def check_confidence_anomaly(
        self,
        bucket_results: Dict[str, Dict],
    ) -> Dict[str, Any]:
        """
        Check for confidence anomalies as identified in the diagnostic findings.
        
        Checks the pathological patterns:
        1. 65-70% bucket: PF ≈ 121.27 (anomalous spike)
        2. 75-100% bucket: 100% WR, PF=1.0, zero DD (too perfect)
        
        Returns analysis of any anomalies found.
        """
        anomalies = {
            "anomalous_65_70_pf": False,
            "anomalous_75_100_pf": False,
            "analysis": {}
        }
        
        # Check 65-70% bucket
        if "65-70" in bucket_results:
            bucket = bucket_results["65-70"]
            pf = bucket.get("profit_factor", 0)
            wr = bucket.get("win_rate", 0)
            n_trades = bucket.get("trade_count", 0)
            
            # PF > 50 with reasonable trade count is suspicious
            if pf > 50 and n_trades < 100:
                anomalies["anomalous_65_70_pf"] = True
                anomalies["analysis"]["65-70"] = {
                    "profit_factor": pf,
                    "win_rate": wr,
                    "trade_count": n_trades,
                    "flag": "SUSPICIOUS_PF_SPIKE - likely overfitting or forward-looking bias"
                }
            
            # Also check if PF is unreasonably high for the sample size
            if n_trades > 0 and pf > 20:
                anomalies["analysis"]["65-70_pf_too_high"] = True
        
        # Check 75-100% bucket
        for bucket_name in ["75-80", "80-85", "85-90", "90-95", "95-100"]:
            if bucket_name in bucket_results:
                bucket = bucket_results[bucket_name]
                wr = bucket.get("win_rate", 0)
                pf = bucket.get("profit_factor", 0)
                n_trades = bucket.get("trade_count", 0)
                max_dd = bucket.get("max_drawdown", 0)
                
                # 100% win rate with PF=1.0 and zero DD is suspicious
                if wr >= 100 and pf <= 1.001 and max_dd == 0:
                    anomalies["anomalous_75_100_pf"] = True
                    if "analysis" not in anomalies:
                        anomalies["analysis"] = {}
                    anomalies["analysis"][bucket_name] = {
                        "win_rate": wr,
                        "profit_factor": pf,
                        "trade_count": n_trades,
                        "max_drawdown": max_dd,
                        "flag": "IMPOSSIBLE_STATISTICS - 100% WR with zero risk indicates synthetic data"
                    }
                # Check for PF >> 1 with small sample
                elif n_trades < 30 and pf > 10:
                    anomalies["analysis"][f"{bucket_name}_small_sample_pf"] = True
        
        return anomalies
    
    def generate_lineage_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive confidence lineage audit report.
        
        Includes:
        - Total entries audited
        - Violations by type
        - Confidence distribution by bucket
        - Temporal contract compliance
        - Bucket statistics
        - Anomaly detection results
        """
        total_entries = len(self.audit_trail)
        total_violations = len(self.violations)
        
        # Group violations by type
        violations_by_type = {}
        for v in self.violations:
            vtype = v.get("type", "unknown")
            if vtype not in violations_by_type:
                violations_by_type[vtype] = 0
            violations_by_type[vtype] += 1
        
        # Check temporal contract compliance
        critical_violations = len([v for v in self.violations if v.get("severity") == "CRITICAL"])
        
        # Bucket statistics
        bucket_stats = {}
        for bucket_name, bucket in self.buckets.items():
            if bucket.trade_count > 0:
                wr = bucket.win_count / bucket.trade_count * 100 if bucket.trade_count > 0 else 0
                pf = bucket.total_pnl / abs(bucket.total_pnl - bucket.win_count * 1e-10) if bucket.total_pnl != 0 else 1.0
                bucket_stats[bucket_name] = {
                    "trade_count": bucket.trade_count,
                    "win_rate": round(wr, 2),
                    "total_pnl": round(bucket.total_pnl, 4),
                    "max_drawdown": round(bucket.max_dd, 4),
                    "win_loss_ratio": round(bucket.win_count / max(bucket.loss_count, 1), 2),
                }
        
        # Check for confidence anomalies
        anomaly_analysis = {}
        if self.buckets:
            # Get the 65-70 and 75-100 buckets for anomaly check
            for name in ["65-70", "75-80", "80-85", "85-90", "90-95", "95-100"]:
                if name in self.buckets:
                    bucket = self.buckets[name]
                    if bucket.trade_count > 0:
                        anomalies = self.check_confidence_anomaly({
                            name: {
                                "profit_factor": self._calc_pf_from_bucket(bucket),
                                "win_rate": bucket.win_count / bucket.trade_count * 100,
                                "trade_count": bucket.trade_count,
                            }
                        })
                        if anomalies.get("anomalous_65_70_pf") or anomalies.get("anomalous_75_100_pf"):
                            anomaly_analysis[name] = anomalies
        
        report = {
            "total_entries_audited": total_entries,
            "total_violations": total_violations,
            "critical_violations": critical_violations,
            "violations_by_type": violations_by_type,
            "temporal_contract_compliance": {
                "passed": critical_violations == 0,
                "description": "All confidence calculations use only data <= decision_time"
            },
            "confidence_buckets": bucket_stats,
            "anomaly_detection": anomaly_analysis,
            "model_versions": self._extract_model_versions(),
            "training_ranges": {
                "start": min(e.training_dataset_range[0] for e in self.audit_trail).isoformat() 
                if self.audit_trail else None,
                "end": max(e.training_dataset_range[1] for e in self.audit_trail).isoformat() 
                if self.audit_trail else None,
            },
        }
        
        return report
    
    def _calc_pf_from_bucket(self, bucket: ConfidenceBucket) -> float:
        """Calculate profit factor from bucket data."""
        if bucket.win_count + bucket.loss_count == 0:
            return 1.0
        gross_profit = max(bucket.win_count, 1)  # At least 1 winning trade
        gross_loss = max(bucket.loss_count, 1)  # At least 1 losing trade
        return gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    def _extract_model_versions(self) -> Dict[str, str]:
        """Extract unique model versions from audit trail."""
        versions = set()
        for entry in self.audit_trail:
            if entry.model_version:
                versions.add(entry.model_version)
            if entry.calibration_model_version:
                versions.add(entry.calibration_model_version)
        return {v: v for v in versions}


# Convenience function
def audit_confidence_lineage(
    confidence_value: float,
    confidence_source: str,
    engine_votes: Dict[str, float],
    feature_data: Dict[str, Any],
    pattern_data: Optional[List[Dict[str, Any]]],
    model_version: str,
    calibration_version: str,
    training_range: Tuple[datetime, datetime],
    decision_time: datetime,
    snapshot: Optional[Any] = None,
) -> ConfidenceEntry:
    """
    Quick audit of a confidence value for temporal integrity.
    
    Args:
        confidence_value: The confidence score (0-100)
        confidence_source: Which component generated this confidence
        engine_votes: Individual engine vote scores
        feature_data: Feature data used in confidence calculation
        pattern_data: Pattern data used (optional)
        model_version: ML model version
        calibration_version: Calibration model version
        training_range: (start, end) of training dataset
        decision_time: When the decision was made
        snapshot: Optional FrozenDecisionSnapshot for additional validation
        
    Returns:
        ConfidenceEntry with full lineage and temporal compliance status
    """
    auditor = ConfidenceLineageAudit()
    return auditor.audit_confidence(
        confidence_value=confidence_value,
        confidence_source=confidence_source,
        engine_votes=engine_votes,
        feature_data=feature_data,
        pattern_data=pattern_data,
        model_version=model_version,
        calibration_version=calibration_version,
        training_range=training_range,
        decision_time=decision_time,
        snapshot=snapshot,
    )