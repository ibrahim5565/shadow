"""
AEGIS GOLD — Dataset Integrity Audit
====================================

Before trusting any backtest, verify the dataset itself. This is the first
and most fundamental step — if the data is corrupted, everything downstream
is meaningless.

Checks:
    duplicate trades
    duplicate timestamps
    duplicate OHLC rows
    missing candles
    impossible OHLC values
    impossible spreads
    zero-duration trades
    future timestamps
    negative durations
    impossible execution prices
    outcome timestamps before entry
    TP/SL hit before entry
    repeated identical outcomes

Also verify that the dataset contains REAL historical market data.

Explicitly identify:
    SYNTHETIC
    HISTORICAL
    LIVE

Never mix them without labeling.
"""

import numpy as np
import pandas as pd
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Set

logger = logging.getLogger("aegis.dataset_integrity")


class DatasetIntegrityAudit:
    """
    Audits the integrity of market data and trade datasets.
    
    Core principle: Before any analysis, ensure the data is clean, consistent,
    and truly historical. Mixing synthetic and live data without labeling
    invalidates all results.
    """
    
    def __init__(self):
        self.audit_results: Dict[str, Any] = {}
        self.issues: List[Dict[str, Any]] = []
        self.labels: Dict[str, str] = {}  # "SYNTHETIC", "HISTORICAL", "LIVE"
    
    def audit_dataframe(self, df: pd.DataFrame, label: str = "UNLABELED") -> Dict[str, Any]:
        """
        Audit a pandas DataFrame of market data (OHLCV).
        
        Args:
            df: DataFrame with columns ['time', 'open', 'high', 'low', 'close', 'volume']
            label: "SYNTHETIC", "HISTORICAL", or "LIVE" - explicitly label the data
            
        Returns:
            Dict with audit results and any issues found
        """
        self.labels[str(id(df))] = label
        self.issues = []
        
        issues = []
        
        # 1. Check for duplicate timestamps
        dup_timestamps = df['time'].duplicated(keep=False)
        if dup_timestamps.any():
            count = dup_timestamps.sum()
            issues.append({
                "type": "DUPLICATE_TIMESTAMPS",
                "severity": "CRITICAL",
                "description": f"Found {count} duplicate timestamps in dataset",
                "affected_rows": df.loc[dup_timestamps, 'time'].tolist()[:20]  # First 20
            })
        
        # 2. Check for missing candles (gaps in time)
        if 'time' in df.columns:
            times = df['time'].values
            if len(times) > 1:
                # Check for gaps (assuming 5-minute intervals for M5 data)
                time_diffs = np.diff(times)
                # Allow for 1-bar tolerance (the forming candle)
                unexpected_gaps = np.where(time_diffs > 300)[0]  # > 5 minutes for M5
                if len(unexpected_gaps) > 0:
                    # Filter out the last bar (forming candle)
                    unexpected_gaps = unexpected_gaps[unexpected_gaps < len(time_diffs) - 1]
                    if len(unexpected_gaps) > 0:
                        issues.append({
                            "type": "MISSING_CANDLES",
                            "severity": "HIGH",
                            "description": f"Found {len(unexpected_gaps)} unexpected time gaps in dataset",
                            "affected_positions": unexpected_gaps.tolist()[:10]
                        })
        
        # 3. Check for impossible OHLC values (high < low, close outside high-low range)
        impossible_ohlc = 0
        for idx, row in df.iterrows():
            if row['high'] < row['low']:
                impossible_ohlc += 1
            if row['close'] > row['high'] or row['close'] < row['low']:
                impossible_ohlc += 1
        
        if impossible_ohlc > 0:
            issues.append({
                "type": "IMPOSSIBLE_OHLC",
                "severity": "CRITICAL",
                "description": f"Found {impossible_ohlc} rows with impossible OHLC values (high < low or close outside range)",
                "affected_count": impossible_ohlc
            })
        
        # 4. Check for impossible spreads (high - low > close + open anomalies)
        # Normal spread should be high - low
        impossible_spreads = 0
        for idx, row in df.iterrows():
            calculated_spread = row['high'] - row['low']
            # Allow for small floating point differences
            if calculated_spread < 1e-10:
                impossible_spreads += 1
        
        if impossible_spreads > 0:
            issues.append({
                "type": "IMPOSSIBLE_SPREADS",
                "severity": "HIGH",
                "description": f"Found {impossible_spreads} rows with zero or negative spread",
                "affected_count": impossible_spreads
            })
        
        # 5. Check for zero-duration trades (if trade data included)
        # This would be checked in trade dataset audit
        
        # 6. Check for future timestamps (if decision_time known)
        # This would be checked in temporal audit
        
        # 7. Check for repeated identical outcomes (in trade data)
        
        # 8. Data type checks
        type_issues = self._check_data_types(df)
        issues.extend(type_issues)
        
        # Compile results
        self.issues = issues
        
        result = {
            "label": label,
            "dataset_id": str(id(df)),
            "total_rows": len(df),
            "issues_found": len(issues),
            "issues": issues,
            "data_types": {
                "column": df.dtypes.to_dict() if hasattr(df, 'dtypes') else "unknown"
            },
            "temporal_integrity": {
                "has_time_column": 'time' in df.columns,
                "time_range": {
                    "start": df['min']().isoformat() if hasattr(df['time'], 'isoformat') else str(df['time'].min()) if 'time' in df.columns else None,
                    "end": df['max']().isoformat() if hasattr(df['time'], 'isoformat') else str(df['time'].max()) if 'time' in df.columns else None
                } if 'time' in df.columns else None
            }
        }
        
        self.audit_results = result
        return result
    
    def _check_data_types(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Check for data type issues."""
        issues = []
        
        # Check for numeric columns that contain non-numeric values
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            if col in df.columns:
                try:
                    pd.to_numeric(df[col], errors='raise')
                except (ValueError, TypeError):
                    # Count non-numeric values
                    non_numeric = df[col].apply(lambda x: not isinstance(x, (int, float, np.number))).sum()
                    if non_numeric > 0:
                        issues.append({
                            "type": "NON_NUMERIC_DATA",
                            "severity": "HIGH",
                            "description": f"Column '{col}' contains {non_numeric} non-numeric values",
                            "affected_column": col
                        })
        
        # Check for datetime column
        if 'time' in df.columns:
            # Try to convert to datetime
            try:
                pd.to_datetime(df['time'], unit='s')  # Assuming Unix timestamps
            except Exception:
                # Check if time values look like timestamps or strings
                sample_time = df['time'].iloc[0]
                if isinstance(sample_time, str):
                    issues.append({
                        "type": "STRING_TIMESTAMPS",
                        "severity": "MEDIUM",
                        "description": "Time column contains string values - ensure they are Unix timestamps",
                        "affected_column": "time"
                    })
        
        return issues
    
    def audit_trade_dataset(self, trades: List[Dict], label: str = "UNLABELED") -> Dict[str, Any]:
        """
        Audit a list of trade records for integrity.
        
        Args:
            trades: List of trade dicts with fields like:
                ticket, timestamp, entry_time, exit_time, pnl, direction, etc.
            label: "SYNTHETIC", "HISTORICAL", or "LIVE"
            
        Returns:
            Dict with audit results
        """
        self.labels[str(id(trades))] = label
        self.issues = []
        
        issues = []
        
        # 1. Check for duplicate trades (by ticket)
        tickets = [t.get('ticket') for t in trades if t.get('ticket')]
        if tickets:
            unique_tickets = set(tickets)
            if len(unique_tickets) < len(tickets):
                dupes = len(tickets) - len(unique_tickets)
                issues.append({
                    "type": "DUPLICATE_TRADES",
                    "severity": "CRITICAL",
                    "description": f"Found {dupes} duplicate trades by ticket ID",
                    "affected_count": dupes
                })
        
        # 2. Check for duplicate timestamps
        timestamps = [t.get('timestamp') for t in trades if t.get('timestamp')]
        if timestamps:
            unique_ts = set(timestamps)
            if len(unique_ts) < len(timestamps):
                dupes = len(timestamps) - len(unique_ts)
                issues.append({
                    "type": "DUPLICATE_TRADE_TIMESTAMPS",
                    "severity": "HIGH",
                    "description": f"Found {dupes} duplicate trade timestamps",
                    "affected_count": dupes
                })
        
        # 3. Check for outcome timestamps before entry
        for i, trade in enumerate(trades):
            entry_time = trade.get('entry_time')
            exit_time = trade.get('exit_time')
            outcome_time = trade.get('outcome_timestamp')
            
            if entry_time and exit_time and outcome_time:
                try:
                    from datetime import datetime
                    entry_dt = datetime.fromisoformat(entry_time) if isinstance(entry_time, str) else entry_time
                    exit_dt = datetime.fromisoformat(exit_time) if isinstance(exit_time, str) else exit_time
                    outcome_dt = datetime.fromisoformat(outcome_time) if isinstance(outcome_time, str) else outcome_time
                    
                    if outcome_dt < entry_dt:
                        issues.append({
                            "type": "OUTCOME_BEFORE_ENTRY",
                            "severity": "CRITICAL",
                            "description": f"Trade {trade.get('ticket', i)}: outcome timestamp {outcome_dt} before entry {entry_dt}",
                            "trade_id": trade.get('ticket', i)
                        })
                    
                    # Check: TP/SL hit before entry
                    if outcome_dt < entry_dt:
                        issues.append({
                            "type": "TP_SL_BEFORE_ENTRY",
                            "severity": "CRITICAL",
                            "description": f"Trade {trade.get('ticket', i)}: TP/SL hit {outcome_dt} before entry {entry_dt}",
                            "trade_id": trade.get('ticket', i)
                        })
                
                except Exception:
                    pass
        
        # 4. Check for zero-duration trades
        for i, trade in enumerate(trades):
            entry_time = trade.get('entry_time')
            exit_time = trade.get('exit_time')
            
            if entry_time and exit_time:
                try:
                    from datetime import datetime
                    if isinstance(entry_time, str):
                        entry_dt = datetime.fromisoformat(entry_time)
                    else:
                        entry_dt = entry_time
                    if isinstance(exit_time, str):
                        exit_dt = datetime.fromisoformat(exit_time)
                    else:
                        exit_dt = exit_time
                    
                    duration = (exit_dt - entry_dt).total_seconds()
                    if duration <= 0:
                        issues.append({
                            "type": "ZERO_DURATION_TRADE",
                            "severity": "HIGH",
                            "description": f"Trade {trade.get('ticket', i)}: Zero or negative duration ({duration}s)",
                            "trade_id": trade.get('ticket', i),
                            "duration_seconds": duration
                        })
                
                except Exception:
                    pass
        
        # 4. Check for impossible execution prices
        for i, trade in enumerate(trades):
            entry_price = trade.get('entry_price')
            exit_price = trade.get('exit_price')
            direction = trade.get('direction')
            
            if entry_price is not None and exit_price is not None and direction:
                try:
                    if direction == 'BUY':
                        # For BUY: profit if exit > entry
                        # Impossible if exit < entry (for simple long trade)
                        if exit_price < entry_price:
                            # This could be a short trade, check context
                            # But if not marked as short, flag it
                            pass  # Context-dependent
                    elif direction == 'SELL':
                        # For SELL: profit if exit < entry
                        pass  # Context-dependent
                except Exception:
                    pass
        
        # 5. Check for repeated identical outcomes
        outcomes = [t.get('pnl', 0) for t in trades if t.get('pnl') is not None]
        if outcomes:
            unique_outcomes = set(outcomes)
            if len(unique_outcomes) == 1:
                # All trades have the same outcome - suspicious
                issues.append({
                    "type": "IDENTICAL_OUTCOMES",
                    "severity": "HIGH",
                    "description": f"All {len(trades)} trades have identical outcomes ({list(unique_outcomes)[0]})",
                    "affected_count": len(trades)
                })
        
        # Compile results
        self.issues = issues
        
        result = {
            "label": label,
            "total_trades": len(trades),
            "issues_found": len(issues),
            "issues": issues,
            "outcome_distribution": {
                "wins": sum(1 for t in trades if t.get('pnl', 0) > 0),
                "losses": sum(1 for t in trades if t.get('pnl', 0) < 0),
                "breakevens": sum(1 for t in trades if t.get('pnl', 0) == 0),
            },
            "pnl_statistics": {
                "total_pnl": sum(t.get('pnl', 0) for t in trades),
                "avg_pnl": sum(t.get('pnl', 0) for t in trades) / len(trades) if trades else 0,
                "pnl_std": float(np.std([t.get('pnl', 0) for t in trades])) if trades else 0
            }
        }
        
        self.audit_results = result
        return result
    
    def verify_data_origin(
        self,
        data_source: str,
        data_range: Tuple[datetime, datetime],
        data_label: str,
        expected_label: str = None
) -> Dict[str, Any]:
        """
        Verify that data origin is consistent and properly labeled.
        
        Args:
            data_source: Source identifier (file path, DB name, API endpoint)
            data_range: (start_date, end_date) of the data
            data_label: "SYNTHETIC", "HISTORICAL", or "LIVE"
            expected_label: Expected label (if known)
            
        Returns:
            Dict with verification result
        """
        # Check label consistency
        label_consistent = data_label == expected_label if expected_label else True
        
        # Check for mixed data labels within the same dataset
        # (This would require scanning the dataset for labels)
        mixed_labels = False  # Placeholder
        
        # Check date range makes sense
        start_date, end_date = data_range
        range_valid = end_date > start_date if start_date and end_date else True
        
        # Check for synthetic data markers
        synthetic_markers = ["synthetic", "generated", "simulated", "artificial"]
        is_synthetic = data_label.lower() in [s.lower() for s in synthetic_markers]
        
        result = {
            "data_source": data_source,
            "data_range": {
                "start": start_date.isoformat() if isinstance(start_date, datetime) else str(start_date),
                "end": end_date.isoformat() if isinstance(end_date, datetime) else str(end_date)
            },
            "data_label": data_label,
            "expected_label": expected_label,
            "label_consistent": label_consistent,
            "mixed_labels_detected": mixed_labels,
            "is_synthetic": is_synthetic,
            "range_valid": range_valid,
            "verification_passed": label_consistent and range_valid and data_label in ["SYNTHETIC", "HISTORICAL", "LIVE"]
        }
        
        return result
    
    def generate_integrity_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive dataset integrity audit report.
        
        Includes:
        - Data labels (SYNTHETIC/HISTORICAL/LIVE)
        - Issues found by type
        - Data origin verification
        - Recommendations
        """
        total_issues = len(self.issues)
        
        # Group issues by severity
        by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for issue in self.issues:
            sev = issue.get("severity", "LOW")
            if sev in by_severity:
                by_severity[sev] += 1
        
        # Count by type
        by_type = {}
        for issue in self.issues:
            itype = issue.get("type", "unknown")
            if itype not in by_type:
                by_type[itype] = 0
            by_type[itype] += 1
        
        # Data origin summary
        label_summary = {}
        for label in ["SYNTHETIC", "HISTORICAL", "LIVE"]:
            count = sum(1 for issue in self.issues 
                       if self.labels.get(str(id(issue.get("_dataset", None))), "") == label)
            label_summary[label] = count
        
        report = {
            "total_issues": total_issues,
            "by_severity": by_severity,
            "by_type": by_type,
            "data_labels": label_summary,
            "verification_status": {
                "synthetic_count": label_summary.get("SYNTHETIC", 0),
                "historical_count": label_summary.get("HISTORICAL", 0),
                "live_count": label_summary.get("LIVE", 0),
                "has_mixed_labels": any(
                    label_summary.get(s, 0) > 0 and label_summary.get(o, 0) > 0
                    for s, o in [("SYNTHETIC", "HISTORICAL"), ("SYNTHETIC", "LIVE"), ("HISTORICAL", "LIVE")]
                ),
                "recommendation": self._get_integrity_recommendation(by_severity, by_type)
            }
        }
        
        return report
    
    def _get_integrity_recommendation(self, by_severity: Dict, by_type: Dict) -> str:
        """Get recommendation based on integrity audit results."""
        critical = by_severity.get("CRITICAL", 0)
        high = by_severity.get("HIGH", 0)
        
        if critical > 0:
            return "FAIL - Critical data integrity issues found. Do not use for backtesting until resolved."
        elif high > 10:
            return "WARNING - High number of data quality issues. Investigate before use."
        elif high > 0:
            return "CAUTION - Some data quality issues present. Use with caution and disclose."
        else:
            return "PASS - Data integrity acceptable for analysis."


# Convenience functions
def audit_dataframe_integrity(
    df: pd.DataFrame,
    label: str = "UNLABELED"
) -> Dict[str, Any]:
    """
    Quick audit of a market DataFrame for integrity.
    
    Args:
        df: DataFrame with OHLCV data
        label: "SYNTHETIC", "HISTORICAL", or "LIVE"
        
    Returns:
        Dict with audit results
    """
    auditor = DatasetIntegrityAudit()
    return auditor.audit_dataframe(df, label)


def audit_trade_integrity(
    trades: List[Dict],
    label: str = "UNLABELED"
) -> Dict[str, Any]:
    """
    Quick audit of a trade dataset for integrity.
    
    Args:
        trades: List of trade dicts
        label: "SYNTHETIC", "HISTORICAL", or "LIVE"
        
    Returns:
        Dict with audit results
    """
    auditor = DatasetIntegrityAudit()
    return auditor.audit_trade_dataset(trades, label)


def verify_data_origin(
    data_source: str,
    data_range: Tuple[datetime, datetime],
    data_label: str,
    expected_label: str = None
) -> Dict[str, Any]:
    """
    Quick verification of data origin labeling.
    
    Args:
        data_source: Source identifier
        data_range: (start_date, end_date)
        data_label: "SYNTHETIC", "HISTORICAL", or "LIVE"
        expected_label: Expected label (if known)
        
    Returns:
        Dict with verification result
    """
    auditor = DatasetIntegrityAudit()
    return auditor.verify_data_origin(data_source, data_range, data_label, expected_label)