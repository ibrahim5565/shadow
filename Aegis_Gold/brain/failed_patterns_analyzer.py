"""
===========================================================================
AEGIS GOLD — Failed Patterns Analyzer (Phase Q)
===========================================================================

PURPOSE:
--------
Identifies and analyzes patterns that generated trades but failed to deliver
expected returns. Diagnoses root causes and recommends pattern improvements.

CORE FEATURES:
--------------
1. Pattern Failure Detection - Identify underperforming patterns
2. Root Cause Analysis - Diagnose why patterns fail
3. Failure Classification - Categorize types of pattern failures
4. Performance Attribution - Identify failure factors
5. Pattern Weakness Tracking - Long-term pattern health monitoring
6. Improvement Recommendations - Suggest pattern enhancements

INTEGRATION:
------------
- Uses Trade Reconstructor (Phase O) for trade outcome data
- Leverages Pattern Outcome Tracker (Phase G) for pattern metrics
- Integrates with Opportunity Engine (Phase L) for quality assessment
- Works with Entry Logic Engine (Phase M) for entry analysis

===========================================================================
"""

import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import json

logger = logging.getLogger("aegis.failed")


class FailureType(Enum):
    """Classification of pattern failure types."""
    LOW_WIN_RATE = "LOW_WIN_RATE"              # Below 40% win rate
    POOR_RR_RATIO = "POOR_RR_RATIO"            # Risk/reward less than 1.2
    EARLY_INVALIDATION = "EARLY_INVALIDATION"  # Pattern breaks quickly after entry
    WHIPSAW = "WHIPSAW"                        # Frequent false reversals
    TREND_FAILURE = "TREND_FAILURE"            # Pattern works against trend
    TIMING_FAILURE = "TIMING_FAILURE"          # Entry timing consistently off
    VOLATILITY_SENSITIVE = "VOLATILITY_SENSITIVE"  # Fails in high volatility
    CORRELATION_FAILURE = "CORRELATION_FAILURE"    # Fails when correlated
    SIGNAL_QUALITY_DECAY = "SIGNAL_QUALITY_DECAY"  # Quality declining over time
    STRUCTURE_INVALIDATION = "STRUCTURE_INVALIDATION"  # Market structure breaks pattern


class FailurePhase(Enum):
    """Phase where pattern fails relative to entry."""
    IMMEDIATE = "IMMEDIATE"          # Fails within first bar/candle
    SHORT_TERM = "SHORT_TERM"        # Fails within 5-10 bars
    MEDIUM_TERM = "MEDIUM_TERM"      # Fails within 20-50 bars
    LONG_TERM = "LONG_TERM"          # Fails but takes time to realize
    REVERSAL = "REVERSAL"            # Reverses after initial move
    STALL = "STALL"                  # Stalls and goes sideways


@dataclass
class FailedPattern:
    """Record of a pattern that failed to deliver expected returns."""
    
    failure_id: str
    pattern_id: str
    pattern_type: str
    symbol: str
    
    # Trade Information
    trade_id: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    
    # Expected vs Actual
    expected_outcome: str           # What should have happened
    actual_outcome: str             # What actually happened
    expected_pnl: float
    actual_pnl: float
    pnl_variance: float             # Expected - Actual
    
    # Failure Classification
    failure_type: FailureType
    failure_phase: FailurePhase
    failure_severity: float         # 0-1 scale
    failure_reason: str             # Detailed explanation
    
    # Market Context
    market_conditions_entry: Dict[str, Any]
    market_conditions_exit: Dict[str, Any]
    
    # Root Cause Analysis
    contributing_factors: List[str]
    root_cause: str
    
    # Pattern-Specific Data
    pattern_age_bars: int           # How old was pattern
    pattern_confluence: int         # Number of confluence factors
    timeframe: str


@dataclass
class PatternFailureAnalysis:
    """Comprehensive analysis of pattern failures."""
    
    pattern_id: str
    pattern_type: str
    
    # Failure Statistics
    total_trades: int
    failed_trades: int
    failure_rate: float
    
    # Failure Types Distribution
    failure_types: Dict[str, int]
    most_common_failure: Optional[str]
    
    # Failure Phases
    failure_phases: Dict[str, int]
    most_common_phase: Optional[str]
    
    # Performance Metrics
    avg_failure_pnl_loss: float    # Average loss on failed trades
    max_failure_loss: float        # Worst single failure
    failure_severity_avg: float    # Average severity
    
    # Patterns in Failures
    failure_correlation_with_volatility: float
    failure_correlation_with_trend: float
    failure_correlation_with_time: float
    
    # Timing Analysis
    avg_bars_to_failure: float
    median_bars_to_failure: int
    
    # Market Impact
    total_loss_from_failures: float
    failure_opportunity_cost: float
    
    # Health Assessment
    pattern_health_score: float     # 0-100, overall pattern viability
    trend_score: float              # How trending-friendly
    stability_score: float          # Consistency of performance
    


@dataclass
class PatternFailureReport:
    """Comprehensive report on pattern failures."""
    
    # Overview
    total_patterns_analyzed: int
    patterns_with_failures: int
    overall_failure_rate: float
    
    # Top Issues
    most_common_failure_type: Optional[str]
    most_common_failure_phase: Optional[str]
    
    # Impact Assessment
    total_loss_from_failures: float
    avg_loss_per_failed_trade: float
    
    # Pattern Rankings
    worst_patterns: List[Tuple[str, float]]  # [(pattern_id, failure_rate), ...]
    best_patterns: List[Tuple[str, float]]
    
    # Failure Correlations
    failure_volatility_correlation: float
    failure_time_correlation: float
    
    # Recommendations
    patterns_needing_review: List[str]
    recommended_improvements: Dict[str, List[str]]


class FailedPatternsAnalyzer:
    """
    Analyzes patterns that failed to deliver expected returns.
    """
    
    def __init__(self):
        # Failure tracking
        self.failed_patterns = {}           # failure_id -> FailedPattern
        self.pattern_analyses = {}          # pattern_id -> PatternFailureAnalysis
        
        # Statistics
        self.failure_statistics = {
            'total_trades': 0,
            'failed_trades': 0,
            'failure_types': {},
            'failure_phases': {},
            'by_pattern': {}
        }
        
        # Performance tracking
        self.pattern_performance = {}       # pattern_id -> performance metrics
        
        logger.info("[FAILED] Failed Patterns Analyzer initialized")
    
    def record_failed_pattern(
        self,
        pattern_id: str,
        pattern_type: str,
        symbol: str,
        trade_id: str,
        entry_price: float,
        exit_price: float,
        entry_time: str,
        exit_time: str,
        expected_outcome: str,
        actual_outcome: str,
        expected_pnl: float,
        actual_pnl: float,
        market_conditions_entry: Dict[str, Any],
        market_conditions_exit: Dict[str, Any],
        failure_type: FailureType,
        pattern_context: Dict[str, Any]
    ) -> FailedPattern:
        """
        Record a pattern that failed to deliver expected returns.
        
        Args:
            pattern_id: Pattern identifier
            pattern_type: Type of pattern
            symbol: Trading symbol
            trade_id: Associated trade ID
            entry_price: Entry price of trade
            exit_price: Exit price of trade
            entry_time: Entry timestamp
            exit_time: Exit timestamp
            expected_outcome: What should have happened
            actual_outcome: What actually happened
            expected_pnl: Expected P&L
            actual_pnl: Actual P&L achieved
            market_conditions_entry: Market state at entry
            market_conditions_exit: Market state at exit
            failure_type: Type of failure
            pattern_context: Pattern-specific context
            
        Returns:
            FailedPattern record
        """
        
        failure_id = f"{pattern_id}_FAIL_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Calculate variance
        pnl_variance = expected_pnl - actual_pnl
        
        # Determine failure phase
        holding_time = self._calculate_holding_time(entry_time, exit_time)
        failure_phase = self._determine_failure_phase(holding_time, pattern_context.get('timeframe', 'H1'))
        
        # Calculate severity
        severity = self._calculate_failure_severity(
            pnl_variance, expected_pnl, actual_pnl, failure_type
        )
        
        # Analyze root cause
        contributing_factors = self._identify_contributing_factors(
            pattern_context,
            market_conditions_entry,
            market_conditions_exit,
            failure_type
        )
        
        root_cause = self._determine_root_cause(
            failure_type, contributing_factors, pattern_context
        )
        
        # Create failure record
        failed_pattern = FailedPattern(
            failure_id=failure_id,
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            symbol=symbol,
            trade_id=trade_id,
            entry_time=entry_time,
            exit_time=exit_time,
            entry_price=entry_price,
            exit_price=exit_price,
            expected_outcome=expected_outcome,
            actual_outcome=actual_outcome,
            expected_pnl=expected_pnl,
            actual_pnl=actual_pnl,
            pnl_variance=pnl_variance,
            failure_type=failure_type,
            failure_phase=failure_phase,
            failure_severity=severity,
            failure_reason=f"{failure_type.value} - {root_cause}",
            market_conditions_entry=market_conditions_entry,
            market_conditions_exit=market_conditions_exit,
            contributing_factors=contributing_factors,
            root_cause=root_cause,
            pattern_age_bars=pattern_context.get('age_bars', 0),
            pattern_confluence=pattern_context.get('confluence_count', 0),
            timeframe=pattern_context.get('timeframe', 'H1')
        )
        
        # Store
        self.failed_patterns[failure_id] = failed_pattern
        
        # Update statistics
        self._update_failure_statistics(failed_pattern)
        
        logger.info(
            f"[FAILED] Recorded failure {failure_id}: "
            f"Type={failure_type.value}, Severity={severity:.2f}, "
            f"PnL Variance={pnl_variance:+.2f}"
        )
        
        return failed_pattern
    
    def _calculate_holding_time(self, entry_time: str, exit_time: str) -> timedelta:
        """Calculate holding time from entry to exit."""
        try:
            entry_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
            exit_dt = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
            return exit_dt - entry_dt
        except:
            return timedelta(hours=1)  # Default
    
    def _determine_failure_phase(self, holding_time: timedelta, timeframe: str) -> FailurePhase:
        """Determine when failure occurred relative to entry."""
        
        total_seconds = holding_time.total_seconds()
        
        # Map timeframe to bar duration
        timeframe_minutes = {
            'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
            'H1': 60, 'H4': 240, 'D1': 1440
        }.get(timeframe, 60)
        
        bars_held = total_seconds / (timeframe_minutes * 60)
        
        if bars_held <= 1.0:
            return FailurePhase.IMMEDIATE
        elif bars_held <= 10:
            return FailurePhase.SHORT_TERM
        elif bars_held <= 50:
            return FailurePhase.MEDIUM_TERM
        else:
            return FailurePhase.LONG_TERM
    
    def _calculate_failure_severity(
        self,
        pnl_variance: float,
        expected_pnl: float,
        actual_pnl: float,
        failure_type: FailureType
    ) -> float:
        """Calculate severity of pattern failure (0-1 scale)."""
        
        if expected_pnl == 0:
            return 0.5
        
        # Base severity on variance percentage
        variance_pct = abs(pnl_variance / expected_pnl) if expected_pnl != 0 else 0
        severity = min(1.0, variance_pct / 2.0)  # Normalize
        
        # Adjust by failure type
        type_weights = {
            FailureType.LOW_WIN_RATE: 0.8,
            FailureType.EARLY_INVALIDATION: 0.9,
            FailureType.WHIPSAW: 0.85,
            FailureType.TREND_FAILURE: 0.7,
            FailureType.TIMING_FAILURE: 0.6,
            FailureType.VOLATILITY_SENSITIVE: 0.65,
            FailureType.SIGNAL_QUALITY_DECAY: 0.75
        }.get(failure_type, 0.7)
        
        return severity * type_weights
    
    def _identify_contributing_factors(
        self,
        pattern_context: Dict[str, Any],
        market_entry: Dict[str, Any],
        market_exit: Dict[str, Any],
        failure_type: FailureType
    ) -> List[str]:
        """Identify factors contributing to pattern failure."""
        
        factors = []
        
        # Volatility analysis
        entry_vol = market_entry.get('volatility_level', 'NORMAL')
        exit_vol = market_exit.get('volatility_level', 'NORMAL')
        
        if entry_vol in ['HIGH', 'VERY_HIGH']:
            factors.append("High volatility at entry")
        
        if exit_vol != entry_vol:
            factors.append(f"Volatility change from {entry_vol} to {exit_vol}")
        
        # Pattern age analysis
        pattern_age = pattern_context.get('age_bars', 0)
        if pattern_age > 100:
            factors.append("Old pattern with potential decay")
        elif pattern_age < 5:
            factors.append("Very young pattern with low confirmation")
        
        # Confluence analysis
        confluence = pattern_context.get('confluence_count', 0)
        if confluence < 2:
            factors.append("Low confluence factors")
        
        # Trend analysis
        market_trend = market_entry.get('trend', 'UNKNOWN')
        pattern_direction = pattern_context.get('direction', 'UNKNOWN')
        
        if market_trend and pattern_direction and market_trend.upper().startswith('DOWN') and pattern_direction == 'BUY':
            factors.append("Pattern against downtrend")
        elif market_trend and pattern_direction and market_trend.upper().startswith('UP') and pattern_direction == 'SELL':
            factors.append("Pattern against uptrend")
        
        # Failure type specific
        if failure_type == FailureType.WHIPSAW:
            factors.append("Price quickly reversed after entry")
        elif failure_type == FailureType.EARLY_INVALIDATION:
            factors.append("Pattern structure invalidated early")
        elif failure_type == FailureType.TIMING_FAILURE:
            factors.append("Entry timing appears to be off")
        
        # Market conditions
        entry_momentum = market_entry.get('momentum_score', 0.5)
        if entry_momentum < 0.3:
            factors.append("Weak momentum at entry")
        
        entry_volume = market_entry.get('volume', 0)
        if entry_volume < 500:  # Arbitrary threshold
            factors.append("Low volume at entry")
        
        return factors
    
    def _determine_root_cause(
        self,
        failure_type: FailureType,
        contributing_factors: List[str],
        pattern_context: Dict[str, Any]
    ) -> str:
        """Determine root cause of pattern failure."""
        
        if not contributing_factors:
            return f"Pattern characteristic of {failure_type.value}"
        
        # Primary factor is typically the most relevant
        if contributing_factors:
            primary_factor = contributing_factors[0]
            
            if "volatility" in primary_factor.lower():
                return "High volatility invalidated pattern structure"
            elif "trend" in primary_factor.lower():
                return "Market trend conflicted with pattern direction"
            elif "momentum" in primary_factor.lower():
                return "Insufficient momentum to drive expected move"
            elif "old" in primary_factor.lower():
                return "Pattern structure had decayed or become invalidated"
            elif "young" in primary_factor.lower():
                return "Pattern needed more confirmation bars"
            elif "reversed" in primary_factor.lower():
                return "Price reversed quickly after setup completion"
            elif "volume" in primary_factor.lower():
                return "Insufficient volume to sustain move"
            else:
                return primary_factor
        
        return f"Pattern failure of type {failure_type.value}"
    
    def _update_failure_statistics(self, failed_pattern: FailedPattern):
        """Update failure statistics."""
        
        self.failure_statistics['total_trades'] += 1
        self.failure_statistics['failed_trades'] += 1
        
        # By type
        failure_type = failed_pattern.failure_type.value
        self.failure_statistics['failure_types'][failure_type] = \
            self.failure_statistics['failure_types'].get(failure_type, 0) + 1
        
        # By phase
        failure_phase = failed_pattern.failure_phase.value
        self.failure_statistics['failure_phases'][failure_phase] = \
            self.failure_statistics['failure_phases'].get(failure_phase, 0) + 1
        
        # By pattern
        pattern_id = failed_pattern.pattern_id
        if pattern_id not in self.failure_statistics['by_pattern']:
            self.failure_statistics['by_pattern'][pattern_id] = {
                'count': 0,
                'total_loss': 0.0,
                'failures': []
            }
        
        self.failure_statistics['by_pattern'][pattern_id]['count'] += 1
        self.failure_statistics['by_pattern'][pattern_id]['total_loss'] += failed_pattern.pnl_variance
        self.failure_statistics['by_pattern'][pattern_id]['failures'].append(failed_pattern.failure_id)
    
    def analyze_pattern_failures(
        self,
        pattern_id: str,
        pattern_type: str,
        all_trades: Dict[str, Any]
    ) -> PatternFailureAnalysis:
        """
        Analyze all failures for a given pattern.
        
        Args:
            pattern_id: Pattern to analyze
            pattern_type: Type of pattern
            all_trades: All trades for comparison
            
        Returns:
            PatternFailureAnalysis
        """
        
        # Get failures for this pattern
        pattern_failures = [
            fp for fp in self.failed_patterns.values()
            if fp.pattern_id == pattern_id
        ]
        
        if not pattern_failures:
            logger.warning(f"[FAILED] No failures found for pattern {pattern_id}")
            return None
        
        # Basic statistics
        total_trades = len([t for t in all_trades.values() if t.get('pattern_id') == pattern_id])
        failed_trades = len(pattern_failures)
        failure_rate = failed_trades / total_trades if total_trades > 0 else 0.0
        
        # Failure type distribution
        failure_types = {}
        for failure in pattern_failures:
            ftype = failure.failure_type.value
            failure_types[ftype] = failure_types.get(ftype, 0) + 1
        
        most_common_failure = max(failure_types.items(), key=lambda x: x[1])[0] if failure_types else None
        
        # Failure phases
        failure_phases = {}
        for failure in pattern_failures:
            fphase = failure.failure_phase.value
            failure_phases[fphase] = failure_phases.get(fphase, 0) + 1
        
        most_common_phase = max(failure_phases.items(), key=lambda x: x[1])[0] if failure_phases else None
        
        # Performance metrics
        failure_pnls = [f.pnl_variance for f in pattern_failures]
        avg_failure_loss = np.mean(failure_pnls) if failure_pnls else 0.0
        max_failure_loss = max(failure_pnls) if failure_pnls else 0.0
        failure_severity_avg = np.mean([f.failure_severity for f in pattern_failures])
        
        # Timing analysis
        holding_times = []
        for failure in pattern_failures:
            try:
                entry_dt = datetime.fromisoformat(failure.entry_time.replace('Z', '+00:00'))
                exit_dt = datetime.fromisoformat(failure.exit_time.replace('Z', '+00:00'))
                bars = ((exit_dt - entry_dt).total_seconds() / 60) / 60  # Simple conversion
                holding_times.append(bars)
            except:
                holding_times.append(1)
        
        avg_bars = np.mean(holding_times) if holding_times else 0.0
        median_bars = int(np.median(holding_times)) if holding_times else 0
        
        # Correlation analysis
        volatility_correlation = self._calculate_correlation_metric(
            pattern_failures, 'volatility_level'
        )
        trend_correlation = self._calculate_correlation_metric(
            pattern_failures, 'trend'
        )
        time_correlation = self._calculate_time_correlation(pattern_failures)
        
        # Loss calculation
        total_loss = sum(failure_pnls)
        opportunity_cost = sum([f.expected_pnl for f in pattern_failures])
        
        # Health score calculation
        pattern_health_score = self._calculate_pattern_health_score(
            failure_rate, avg_failure_loss, failure_severity_avg
        )
        
        trend_score = max(0, 100 - abs(trend_correlation) * 100)
        stability_score = max(0, 100 - (failure_severity_avg * 100))
        
        analysis = PatternFailureAnalysis(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            total_trades=total_trades,
            failed_trades=failed_trades,
            failure_rate=failure_rate,
            failure_types=failure_types,
            most_common_failure=most_common_failure,
            failure_phases=failure_phases,
            most_common_phase=most_common_phase,
            avg_failure_pnl_loss=avg_failure_loss,
            max_failure_loss=max_failure_loss,
            failure_severity_avg=failure_severity_avg,
            failure_correlation_with_volatility=volatility_correlation,
            failure_correlation_with_trend=trend_correlation,
            failure_correlation_with_time=time_correlation,
            avg_bars_to_failure=avg_bars,
            median_bars_to_failure=median_bars,
            total_loss_from_failures=total_loss,
            failure_opportunity_cost=opportunity_cost,
            pattern_health_score=pattern_health_score,
            trend_score=trend_score,
            stability_score=stability_score
        )
        
        self.pattern_analyses[pattern_id] = analysis
        
        logger.info(
            f"[FAILED] Pattern {pattern_id} analysis: "
            f"FailureRate={failure_rate:.1%}, HealthScore={pattern_health_score:.1f}, "
            f"CommonFailure={most_common_failure}"
        )
        
        return analysis
    
    def _calculate_correlation_metric(
        self,
        failures: List[FailedPattern],
        metric_name: str
    ) -> float:
        """Calculate correlation between failure and market metric."""
        
        if not failures:
            return 0.0
        
        # Simple binary correlation
        metric_during_failure = sum(
            1 for f in failures
            if f.market_conditions_entry.get(metric_name) and
            str(f.market_conditions_entry.get(metric_name)).upper() in ['HIGH', 'VERY_HIGH']
        )
        
        return metric_during_failure / len(failures) if failures else 0.0
    
    def _calculate_time_correlation(self, failures: List[FailedPattern]) -> float:
        """Calculate if failures cluster at certain times."""
        
        if not failures:
            return 0.0
        
        # Extract hour of failure
        failure_hours = []
        for failure in failures:
            try:
                exit_dt = datetime.fromisoformat(failure.exit_time.replace('Z', '+00:00'))
                failure_hours.append(exit_dt.hour)
            except:
                pass
        
        if not failure_hours:
            return 0.0
        
        # Check if there's clustering (e.g., many failures in certain hours)
        hour_counts = {}
        for hour in failure_hours:
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        max_count = max(hour_counts.values())
        clustering_score = (max_count / len(failure_hours)) - (1/24)  # Account for random distribution
        
        return max(0, min(1.0, clustering_score))
    
    def _calculate_pattern_health_score(
        self,
        failure_rate: float,
        avg_failure_loss: float,
        severity_avg: float
    ) -> float:
        """Calculate overall pattern health score (0-100)."""
        
        # Lower failure rate is better
        failure_rate_score = max(0, 100 - (failure_rate * 250))  # Convert to 0-100
        
        # Better if losses are smaller
        loss_score = max(0, 100 - (abs(avg_failure_loss) * 20))
        
        # Better if severity is lower
        severity_score = max(0, 100 - (severity_avg * 100))
        
        # Weighted combination
        health_score = (failure_rate_score * 0.4 + loss_score * 0.3 + severity_score * 0.3)
        
        return max(0, min(100, health_score))
    
    def generate_failure_report(self) -> PatternFailureReport:
        """Generate comprehensive report on pattern failures."""
        
        if not self.failed_patterns:
            logger.warning("[FAILED] No failed patterns recorded")
            return None
        
        # Calculate overall statistics
        pattern_ids = set(fp.pattern_id for fp in self.failed_patterns.values())
        total_patterns = len(pattern_ids)
        patterns_with_failures = len(self.pattern_analyses)
        
        total_trades = self.failure_statistics['total_trades']
        failed_trades = self.failure_statistics['failed_trades']
        overall_failure_rate = failed_trades / total_trades if total_trades > 0 else 0.0
        
        # Failure types
        failure_types = self.failure_statistics['failure_types']
        most_common_failure_type = max(failure_types.items(), key=lambda x: x[1])[0] if failure_types else None
        
        # Failure phases
        failure_phases = self.failure_statistics['failure_phases']
        most_common_failure_phase = max(failure_phases.items(), key=lambda x: x[1])[0] if failure_phases else None
        
        # Impact
        total_loss = sum(fp.pnl_variance for fp in self.failed_patterns.values())
        avg_loss_per_failed = total_loss / failed_trades if failed_trades > 0 else 0.0
        
        # Pattern rankings
        pattern_failures_count = {}
        for pattern_id, data in self.failure_statistics['by_pattern'].items():
            pattern_failures_count[pattern_id] = {
                'count': data['count'],
                'loss': data['total_loss'],
                'analysis': self.pattern_analyses.get(pattern_id)
            }
        
        # Worst patterns
        worst_patterns = sorted(
            [(pid, data['analysis'].failure_rate) 
             for pid, data in pattern_failures_count.items()
             if data['analysis']],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Best patterns (lowest failure rate among those with failures)
        best_patterns = sorted(
            [(pid, data['analysis'].failure_rate)
             for pid, data in pattern_failures_count.items()
             if data['analysis'] and data['analysis'].failure_rate > 0],
            key=lambda x: x[1]
        )[:5]
        
        # Correlations
        vol_correlations = [
            analysis.failure_correlation_with_volatility
            for analysis in self.pattern_analyses.values()
        ]
        failure_vol_correlation = np.mean(vol_correlations) if vol_correlations else 0.0
        
        time_correlations = [
            analysis.failure_correlation_with_time
            for analysis in self.pattern_analyses.values()
        ]
        failure_time_correlation = np.mean(time_correlations) if time_correlations else 0.0
        
        # Patterns needing review
        patterns_needing_review = [
            pid for pid, data in pattern_failures_count.items()
            if data['analysis'] and data['analysis'].failure_rate > 0.5
        ]
        
        # Recommendations
        recommended_improvements = {}
        for pattern_id, data in pattern_failures_count.items():
            if data['analysis']:
                analysis = data['analysis']
                improvements = []
                
                if analysis.failure_rate > 0.5:
                    improvements.append(f"Reduce entry false signals (failure rate {analysis.failure_rate:.1%})")
                
                if analysis.failure_correlation_with_volatility > 0.6:
                    improvements.append("Add volatility filter to reduce failures")
                
                if analysis.most_common_failure:
                    improvements.append(f"Address {analysis.most_common_failure}")
                
                if improvements:
                    recommended_improvements[pattern_id] = improvements
        
        report = PatternFailureReport(
            total_patterns_analyzed=total_patterns,
            patterns_with_failures=patterns_with_failures,
            overall_failure_rate=overall_failure_rate,
            most_common_failure_type=most_common_failure_type,
            most_common_failure_phase=most_common_failure_phase,
            total_loss_from_failures=total_loss,
            avg_loss_per_failed_trade=avg_loss_per_failed,
            worst_patterns=worst_patterns,
            best_patterns=best_patterns,
            failure_volatility_correlation=failure_vol_correlation,
            failure_time_correlation=failure_time_correlation,
            patterns_needing_review=patterns_needing_review,
            recommended_improvements=recommended_improvements
        )
        
        logger.info(
            f"[FAILED] Generated report: "
            f"FailureRate={overall_failure_rate:.1%}, "
            f"TopIssue={most_common_failure_type}, "
            f"TotalLoss={total_loss:+.2f}"
        )
        
        return report
    
    def get_failure_statistics(self) -> Dict[str, Any]:
        """Get summary of failure statistics."""
        
        return {
            "total_failed_patterns": len(self.failed_patterns),
            "failure_type_distribution": self.failure_statistics['failure_types'],
            "failure_phase_distribution": self.failure_statistics['failure_phases'],
            "patterns_analyzed": len(self.pattern_analyses),
            "overall_failure_rate": (
                self.failure_statistics['failed_trades'] / self.failure_statistics['total_trades']
                if self.failure_statistics['total_trades'] > 0 else 0.0
            )
        }


# Global singleton instance
_failed_analyzer = None

def get_failed_patterns_analyzer() -> FailedPatternsAnalyzer:
    """Get or create singleton analyzer."""
    global _failed_analyzer
    if _failed_analyzer is None:
        _failed_analyzer = FailedPatternsAnalyzer()
    return _failed_analyzer