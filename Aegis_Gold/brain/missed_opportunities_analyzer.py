"""
===========================================================================
AEGIS GOLD — Missed Opportunities Analyzer (Phase P)
===========================================================================

PURPOSE:
--------
Analyzes patterns that generated valid signals but weren't entered to identify
optimization opportunities and understand why profitable trades were skipped.

CORE FEATURES:
--------------
1. Missed Signal Tracking - Record all signals not acted upon
2. Outcome Simulation - Estimate what would have happened if entered
3. Opportunity Classification - Categorize reasons for missing trades
4. Performance Attribution - Identify which filters caused misses
5. Optimization Recommendations - Suggest improvements to entry rules
6. Lost Profit Analysis - Calculate cumulative missed profits

INTEGRATION:
------------
- Uses Entry Logic Engine (Phase M) for entry signal tracking
- Leverages Trade Reconstructor (Phase O) for outcome comparison
- Integrates with Opportunity Engine (Phase L) for quality metrics
- Works with Pattern Outcome Tracker (Phase G) for pattern analysis

===========================================================================
"""

import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import json

logger = logging.getLogger("aegis.missed")


class MissReason(Enum):
    """Reasons why an opportunity was not traded."""
    CONFIDENCE_GATE = "CONFIDENCE_GATE"          # Signal confidence too low
    QUALITY_GATE = "QUALITY_GATE"               # Opportunity quality too low
    RISK_GATE = "RISK_GATE"                     # Risk/reward ratio insufficient
    POSITION_LIMIT = "POSITION_LIMIT"           # Position size limit hit
    CORRELATION_FILTER = "CORRELATION_FILTER"   # Correlation with existing positions
    DRAWDOWN_LIMIT = "DRAWDOWN_LIMIT"           # Current drawdown too high
    SIGNAL_EXPIRED = "SIGNAL_EXPIRED"           # Entry window closed
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"         # User rejected trade
    SYSTEM_ERROR = "SYSTEM_ERROR"               # Technical/system failure
    UNKNOWN = "UNKNOWN"                         # Unknown reason


class SimulatedOutcome(Enum):
    """Classification of simulated outcome if trade was taken."""
    WIN_AT_TARGET = "WIN_AT_TARGET"            # Would have hit target
    WIN_EARLY = "WIN_EARLY"                    # Would have exited early with profit
    BREAKEVEN = "BREAKEVEN"                    # Would have closed breakeven
    SMALL_LOSS = "SMALL_LOSS"                  # Would have lost small
    STOPPED_OUT = "STOPPED_OUT"                # Would have been stopped out
    UNKNOWN = "UNKNOWN"                        # Cannot determine outcome


@dataclass
class MissedSignal:
    """Record of an opportunity signal that wasn't traded."""
    
    miss_id: str
    pattern_id: str
    symbol: str
    
    # Signal Information
    signal_time: str
    signal_price: float
    entry_target: float
    signal_quality_score: float
    signal_confidence: float
    
    # Risk Parameters
    planned_stop_loss: float
    planned_take_profit: float
    planned_position_size: float
    
    # Why It Was Missed
    miss_reason: MissReason
    miss_reason_details: str
    miss_severity: float        # 0-1: how critical was this miss
    
    # Market Context
    market_conditions: Dict[str, Any]
    system_state: Dict[str, Any]
    
    # Timing
    detection_time: str
    miss_detection_time: str
    signal_age_minutes: float


@dataclass
class SimulatedExecution:
    """Simulated execution if the opportunity had been taken."""
    
    sim_id: str
    missed_signal_id: str
    
    # Entry Simulation
    simulated_entry_price: float
    simulated_entry_time: str
    
    # Exit Simulation
    simulated_exit_price: Optional[float]
    simulated_exit_time: Optional[str]
    simulated_exit_reason: str
    
    # Outcome
    simulated_outcome: SimulatedOutcome
    simulated_pnl: float
    simulated_pnl_pct: float
    simulated_rr_ratio: float
    
    # Comparison with Actual Trades
    comparison_score: float     # How representative vs actual trades
    confidence_level: float     # How confident in simulation


@dataclass
class MissedOpportunitySummary:
    """Summary analysis of a single missed opportunity."""
    
    miss_id: str
    pattern_id: str
    symbol: str
    
    # Event Information
    signal_date: str
    signal_quality: float
    signal_confidence: float
    
    # Impact Analysis
    miss_reason: MissReason
    severity: float
    
    # Simulated Outcome
    simulated_outcome: SimulatedOutcome
    estimated_pnl: float
    estimated_pnl_pct: float
    
    # Comparables
    similar_trades_count: int           # How many similar trades occurred
    similar_avg_pnl: float              # Average PnL of similar trades
    similar_win_rate: float             # Win rate of similar trades
    
    # Opportunity Cost
    opportunity_cost: float             # Estimated lost profit
    risk_adjusted_cost: float           # Risk-adjusted opportunity cost


@dataclass
class MissOpportunitiesReport:
    """Comprehensive report on missed opportunities."""
    
    # Statistics
    total_signals: int
    total_missed: int
    miss_rate: float
    
    # By Reason
    misses_by_reason: Dict[str, int]
    
    # Impact
    total_opportunity_cost: float       # Total estimated lost profit
    avg_opportunity_cost: float
    max_opportunity_cost: float
    
    # Quality Metrics
    avg_missed_signal_quality: float
    avg_missed_signal_confidence: float
    
    # Patterns
    most_missed_pattern: Optional[str]
    most_missed_reason: Optional[str]
    
    # Recommendations
    top_improvements: List[str]


class MissedOpportunitiesAnalyzer:
    """
    Analyzes missed trading opportunities and identifies optimization areas.
    """
    
    def __init__(self):
        # Missed signal tracking
        self.missed_signals = {}            # miss_id -> MissedSignal
        self.simulated_executions = {}      # sim_id -> SimulatedExecution
        self.missed_summaries = {}          # miss_id -> MissedOpportunitySummary
        
        # Analytics
        self.miss_statistics = {
            'total_signals': 0,
            'total_missed': 0,
            'by_reason': {},
            'by_pattern': {},
            'by_date': {}
        }
        
        # Comparison with actual trades
        self.actual_trades_cache = []       # For comparison
        
        logger.info("[MISS] Missed Opportunities Analyzer initialized")
    
    def record_missed_signal(
        self,
        pattern_id: str,
        symbol: str,
        entry_signal,
        miss_reason: MissReason,
        reason_details: str,
        market_snapshot,
        system_state: Dict[str, Any]
    ) -> MissedSignal:
        """
        Record an opportunity signal that wasn't traded.
        
        Args:
            pattern_id: Pattern that generated signal
            symbol: Trading symbol
            entry_signal: Entry signal object
            miss_reason: Why the trade wasn't taken
            reason_details: Detailed explanation
            market_snapshot: Market conditions at signal time
            system_state: System state (positions, limits, etc.)
            
        Returns:
            MissedSignal record
        """
        
        miss_id = f"{pattern_id}_MISS_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Extract signal information
        signal_price = market_snapshot.current_price
        signal_quality = entry_signal.setup_quality_score
        signal_confidence = entry_signal.entry_trigger.confidence if entry_signal.entry_trigger else 0.5
        
        # Extract risk parameters
        stop_loss = entry_signal.entry_zone.optimal_price - (entry_signal.entry_zone.zone_width * 0.5) \
                    if entry_signal.entry_zone.direction == "BUY" else \
                    entry_signal.entry_zone.optimal_price + (entry_signal.entry_zone.zone_width * 0.5)
        
        take_profit = entry_signal.entry_zone.optimal_price + (entry_signal.entry_zone.zone_width * 1.5) \
                      if entry_signal.entry_zone.direction == "BUY" else \
                      entry_signal.entry_zone.optimal_price - (entry_signal.entry_zone.zone_width * 1.5)
        
        # Calculate severity (0-1 scale)
        severity = self._calculate_miss_severity(
            signal_quality, signal_confidence, miss_reason
        )
        
        # Capture market conditions
        market_conditions = {
            'price': signal_price,
            'volatility': getattr(market_snapshot, 'volatility_level', 'NORMAL'),
            'volume': getattr(market_snapshot, 'volume', 0),
            'momentum': getattr(market_snapshot, 'momentum_score', 0.5),
            'time': datetime.now(timezone.utc).isoformat()
        }
        
        # Calculate signal age
        signal_time = entry_signal.setup_completion_time
        try:
            signal_dt = datetime.fromisoformat(signal_time.replace('Z', '+00:00'))
            signal_age = (datetime.now(timezone.utc) - signal_dt).total_seconds() / 60.0
        except:
            signal_age = 0.0
        
        # Create missed signal record
        missed_signal = MissedSignal(
            miss_id=miss_id,
            pattern_id=pattern_id,
            symbol=symbol,
            signal_time=signal_time,
            signal_price=signal_price,
            entry_target=entry_signal.entry_zone.optimal_price,
            signal_quality_score=signal_quality,
            signal_confidence=signal_confidence,
            planned_stop_loss=stop_loss,
            planned_take_profit=take_profit,
            planned_position_size=entry_signal.position_size_fraction,
            miss_reason=miss_reason,
            miss_reason_details=reason_details,
            miss_severity=severity,
            market_conditions=market_conditions,
            system_state=system_state,
            detection_time=datetime.now(timezone.utc).isoformat(),
            miss_detection_time=datetime.now(timezone.utc).isoformat(),
            signal_age_minutes=signal_age
        )
        
        # Store
        self.missed_signals[miss_id] = missed_signal
        
        # Update statistics
        self.miss_statistics['total_signals'] += 1
        self.miss_statistics['total_missed'] += 1
        
        reason_key = miss_reason.value
        self.miss_statistics['by_reason'][reason_key] = \
            self.miss_statistics['by_reason'].get(reason_key, 0) + 1
        
        logger.info(
            f"[MISS] Recorded missed signal {miss_id}: "
            f"Reason={miss_reason.value}, Quality={signal_quality:.1f}, "
            f"Severity={severity:.2f}"
        )
        
        return missed_signal
    
    def _calculate_miss_severity(
        self,
        signal_quality: float,
        signal_confidence: float,
        miss_reason: MissReason
    ) -> float:
        """Calculate severity of missing an opportunity (0-1)."""
        
        # Higher severity for high-quality missed signals
        quality_component = signal_quality / 100.0
        confidence_component = signal_confidence
        
        # Adjust by reason
        reason_weight = {
            MissReason.CONFIDENCE_GATE: 0.3,    # Low impact - shouldn't have been confident anyway
            MissReason.QUALITY_GATE: 0.4,       # Low-medium impact
            MissReason.RISK_GATE: 0.5,          # Medium impact - risk was real concern
            MissReason.POSITION_LIMIT: 0.8,     # High impact - system constraint
            MissReason.CORRELATION_FILTER: 0.7, # High impact - correlation concern
            MissReason.DRAWDOWN_LIMIT: 0.9,     # Very high impact - protective measure
            MissReason.SIGNAL_EXPIRED: 0.2,     # Low impact - trade window closed
            MissReason.MANUAL_OVERRIDE: 0.6,    # Medium-high impact - user decision
            MissReason.SYSTEM_ERROR: 0.5,       # Medium impact - avoidable
            MissReason.UNKNOWN: 0.3
        }.get(miss_reason, 0.5)
        
        # Combine components
        severity = (quality_component * 0.4 + confidence_component * 0.3) * reason_weight
        return min(1.0, severity)
    
    def simulate_execution(
        self,
        missed_signal: MissedSignal,
        actual_price_history: List[Tuple[datetime, float]],
        actual_trades_for_comparison: List[Dict[str, Any]] = None
    ) -> SimulatedExecution:
        """
        Simulate what would have happened if the opportunity was taken.
        
        Args:
            missed_signal: The missed signal to simulate
            actual_price_history: Price history after signal
            actual_trades_for_comparison: Recent actual trades for comparison
            
        Returns:
            SimulatedExecution with hypothetical outcomes
        """
        
        sim_id = f"{missed_signal.miss_id}_SIM"
        
        # Simulate entry at signal price
        simulated_entry_price = missed_signal.signal_price
        simulated_entry_time = missed_signal.signal_time
        
        # Simulate exit based on price history
        simulated_exit_price = None
        simulated_exit_time = None
        simulated_exit_reason = "UNKNOWN"
        simulated_outcome = SimulatedOutcome.UNKNOWN
        simulated_pnl = 0.0
        simulated_pnl_pct = 0.0
        simulated_rr_ratio = 0.0
        
        if actual_price_history:
            # Check for SL hit
            sl_hit = False
            for price_time, price in actual_price_history:
                if missed_signal.planned_stop_loss is not None:
                    # Check if price crossed stop loss
                    if (missed_signal.planned_stop_loss < simulated_entry_price and price <= missed_signal.planned_stop_loss) or \
                       (missed_signal.planned_stop_loss > simulated_entry_price and price >= missed_signal.planned_stop_loss):
                        simulated_exit_price = missed_signal.planned_stop_loss
                        simulated_exit_time = price_time.isoformat() if isinstance(price_time, datetime) else str(price_time)
                        simulated_exit_reason = "STOP_LOSS"
                        sl_hit = True
                        break
            
            if not sl_hit:
                # Check for TP hit
                tp_hit = False
                for price_time, price in actual_price_history:
                    if missed_signal.planned_take_profit is not None:
                        if (missed_signal.planned_take_profit > simulated_entry_price and price >= missed_signal.planned_take_profit) or \
                           (missed_signal.planned_take_profit < simulated_entry_price and price <= missed_signal.planned_take_profit):
                            simulated_exit_price = missed_signal.planned_take_profit
                            simulated_exit_time = price_time.isoformat() if isinstance(price_time, datetime) else str(price_time)
                            simulated_exit_reason = "TARGET_HIT"
                            tp_hit = True
                            break
                
                if not tp_hit and actual_price_history:
                    # Use last price as exit
                    simulated_exit_price = actual_price_history[-1][1]
                    simulated_exit_time = actual_price_history[-1][0].isoformat() if isinstance(actual_price_history[-1][0], datetime) else str(actual_price_history[-1][0])
                    simulated_exit_reason = "TIME_EXIT"
        
        # Calculate P&L
        if simulated_exit_price:
            if missed_signal.symbol.endswith('USD'):  # Simplified direction detection
                pnl_per_unit = simulated_exit_price - simulated_entry_price
            else:
                pnl_per_unit = simulated_exit_price - simulated_entry_price
            
            simulated_pnl = pnl_per_unit * missed_signal.planned_position_size
            simulated_pnl_pct = (pnl_per_unit / simulated_entry_price) if simulated_entry_price > 0 else 0
            
            # Calculate R/R
            risk_distance = abs(simulated_entry_price - missed_signal.planned_stop_loss)
            reward_distance = abs(simulated_exit_price - simulated_entry_price)
            simulated_rr_ratio = reward_distance / risk_distance if risk_distance > 0 else 0.0
            
            # Classify outcome
            if simulated_exit_reason == "TARGET_HIT":
                simulated_outcome = SimulatedOutcome.WIN_AT_TARGET
            elif simulated_exit_reason == "STOP_LOSS":
                simulated_outcome = SimulatedOutcome.STOPPED_OUT
            elif simulated_pnl > 0:
                if simulated_pnl > reward_distance * 0.5:
                    simulated_outcome = SimulatedOutcome.WIN_EARLY
                else:
                    simulated_outcome = SimulatedOutcome.WIN_EARLY
            elif abs(simulated_pnl) < 5.0:
                simulated_outcome = SimulatedOutcome.BREAKEVEN
            elif simulated_pnl > -risk_distance * 0.5:
                simulated_outcome = SimulatedOutcome.SMALL_LOSS
            else:
                simulated_outcome = SimulatedOutcome.STOPPED_OUT
        
        # Calculate comparison score with actual trades
        comparison_score = 0.5  # Default confidence
        if actual_trades_for_comparison:
            similar_trades = [t for t in actual_trades_for_comparison 
                            if abs(t.get('entry_quality', 0.5) - missed_signal.signal_quality_score / 100.0) < 0.2]
            if similar_trades:
                comparison_score = len(similar_trades) / len(actual_trades_for_comparison)
        
        # Create execution record
        simulation = SimulatedExecution(
            sim_id=sim_id,
            missed_signal_id=missed_signal.miss_id,
            simulated_entry_price=simulated_entry_price,
            simulated_entry_time=simulated_entry_time,
            simulated_exit_price=simulated_exit_price,
            simulated_exit_time=simulated_exit_time,
            simulated_exit_reason=simulated_exit_reason,
            simulated_outcome=simulated_outcome,
            simulated_pnl=simulated_pnl,
            simulated_pnl_pct=simulated_pnl_pct,
            simulated_rr_ratio=simulated_rr_ratio,
            comparison_score=comparison_score,
            confidence_level=min(1.0, comparison_score + 0.3)  # Boost confidence slightly
        )
        
        # Store
        self.simulated_executions[sim_id] = simulation
        
        logger.info(
            f"[MISS] Simulated execution for {missed_signal.miss_id}: "
            f"Outcome={simulated_outcome.value}, PnL={simulated_pnl:+.2f}, "
            f"Confidence={simulation.confidence_level:.2f}"
        )
        
        return simulation
    
    def create_miss_summary(
        self,
        missed_signal: MissedSignal,
        simulated_execution: SimulatedExecution,
        similar_actual_trades: List[Dict[str, Any]] = None
    ) -> MissedOpportunitySummary:
        """
        Create comprehensive summary of a missed opportunity.
        
        Args:
            missed_signal: The missed signal
            simulated_execution: Simulated outcome
            similar_actual_trades: Comparable actual trades
            
        Returns:
            MissedOpportunitySummary
        """
        
        # Calculate comparables
        similar_trades_count = len(similar_actual_trades) if similar_actual_trades else 0
        similar_avg_pnl = 0.0
        similar_win_rate = 0.0
        
        if similar_actual_trades:
            valid_trades = [t for t in similar_actual_trades if t.get('final_pnl') is not None]
            if valid_trades:
                similar_avg_pnl = np.mean([t.get('final_pnl', 0) for t in valid_trades])
                wins = [t for t in valid_trades if t.get('final_pnl', 0) > 0]
                similar_win_rate = len(wins) / len(valid_trades) if valid_trades else 0.0
        
        # Calculate opportunity cost
        opportunity_cost = simulated_execution.simulated_pnl
        risk_adjusted_cost = opportunity_cost * simulated_execution.confidence_level
        
        # Extract date
        try:
            signal_date = datetime.fromisoformat(
                missed_signal.signal_time.replace('Z', '+00:00')
            ).strftime('%Y-%m-%d')
        except:
            signal_date = "unknown"
        
        # Create summary
        summary = MissedOpportunitySummary(
            miss_id=missed_signal.miss_id,
            pattern_id=missed_signal.pattern_id,
            symbol=missed_signal.symbol,
            signal_date=signal_date,
            signal_quality=missed_signal.signal_quality_score,
            signal_confidence=missed_signal.signal_confidence,
            miss_reason=missed_signal.miss_reason,
            severity=missed_signal.miss_severity,
            simulated_outcome=simulated_execution.simulated_outcome,
            estimated_pnl=simulated_execution.simulated_pnl,
            estimated_pnl_pct=simulated_execution.simulated_pnl_pct,
            similar_trades_count=similar_trades_count,
            similar_avg_pnl=similar_avg_pnl,
            similar_win_rate=similar_win_rate,
            opportunity_cost=opportunity_cost,
            risk_adjusted_cost=risk_adjusted_cost
        )
        
        self.missed_summaries[missed_signal.miss_id] = summary
        
        return summary
    
    def analyze_missed_opportunities(self) -> MissOpportunitiesReport:
        """Generate comprehensive report on all missed opportunities."""
        
        if not self.missed_signals:
            logger.warning("[MISS] No missed signals recorded for analysis")
            return None
        
        # Calculate statistics
        total_signals = self.miss_statistics['total_signals']
        total_missed = self.miss_statistics['total_missed']
        miss_rate = total_missed / total_signals if total_signals > 0 else 0.0
        
        # By reason
        misses_by_reason = self.miss_statistics['by_reason']
        
        # Impact analysis
        opportunity_costs = []
        signal_qualities = []
        signal_confidences = []
        
        for miss_id, summary in self.missed_summaries.items():
            opportunity_costs.append(summary.opportunity_cost)
            signal_qualities.append(summary.signal_quality)
            signal_confidences.append(summary.signal_confidence)
        
        total_opportunity_cost = sum(opportunity_costs) if opportunity_costs else 0.0
        avg_opportunity_cost = np.mean(opportunity_costs) if opportunity_costs else 0.0
        max_opportunity_cost = max(opportunity_costs) if opportunity_costs else 0.0
        
        avg_missed_quality = np.mean(signal_qualities) if signal_qualities else 0.0
        avg_missed_confidence = np.mean(signal_confidences) if signal_confidences else 0.0
        
        # Most missed pattern/reason
        most_missed_pattern = None
        most_missed_reason = None
        
        if self.miss_statistics['by_pattern']:
            most_missed_pattern = max(
                self.miss_statistics['by_pattern'].items(),
                key=lambda x: x[1]
            )[0]
        
        if misses_by_reason:
            most_missed_reason = max(
                misses_by_reason.items(),
                key=lambda x: x[1]
            )[0]
        
        # Recommendations
        top_improvements = self._generate_recommendations(misses_by_reason, opportunity_costs)
        
        report = MissOpportunitiesReport(
            total_signals=total_signals,
            total_missed=total_missed,
            miss_rate=miss_rate,
            misses_by_reason=misses_by_reason,
            total_opportunity_cost=total_opportunity_cost,
            avg_opportunity_cost=avg_opportunity_cost,
            max_opportunity_cost=max_opportunity_cost,
            avg_missed_signal_quality=avg_missed_quality,
            avg_missed_signal_confidence=avg_missed_confidence,
            most_missed_pattern=most_missed_pattern,
            most_missed_reason=most_missed_reason,
            top_improvements=top_improvements
        )
        
        logger.info(
            f"[MISS] Generated report: "
            f"MissRate={miss_rate:.1%}, "
            f"OpportunityCost={total_opportunity_cost:+.2f}, "
            f"TopReason={most_missed_reason}"
        )
        
        return report
    
    def _generate_recommendations(
        self,
        misses_by_reason: Dict[str, int],
        opportunity_costs: List[float]
    ) -> List[str]:
        """Generate recommendations based on missed opportunities."""
        
        recommendations = []
        
        # Analyze reason distribution
        if misses_by_reason:
            total_misses = sum(misses_by_reason.values())
            
            # High-frequency reasons
            for reason, count in sorted(misses_by_reason.items(), key=lambda x: x[1], reverse=True)[:3]:
                pct = (count / total_misses) * 100
                
                if reason == "CONFIDENCE_GATE":
                    recommendations.append(
                        f"Confidence gate causes {pct:.1f}% of misses - consider lowering threshold from {0.6}"
                    )
                elif reason == "QUALITY_GATE":
                    recommendations.append(
                        f"Quality gate causes {pct:.1f}% of misses - evaluate if {55.0} min quality is too high"
                    )
                elif reason == "RISK_GATE":
                    recommendations.append(
                        f"Risk/reward gate causes {pct:.1f}% of misses - may be too restrictive at {1.5}:1"
                    )
                elif reason == "POSITION_LIMIT":
                    recommendations.append(
                        f"Position limits cause {pct:.1f}% of misses - consider increasing max position size"
                    )
                elif reason == "DRAWDOWN_LIMIT":
                    recommendations.append(
                        f"Drawdown limits cause {pct:.1f}% of misses - may be too conservative"
                    )
        
        # Profit potential analysis
        profitable_misses = len([c for c in opportunity_costs if c > 0])
        if opportunity_costs:
            profit_pct = (profitable_misses / len(opportunity_costs)) * 100
            if profit_pct > 50:
                recommendations.append(
                    f"{profit_pct:.1f}% of missed opportunities would have been profitable - review filters"
                )
        
        return recommendations[:5]  # Return top 5 recommendations
    
    def get_miss_statistics(self) -> Dict[str, Any]:
        """Get summary statistics on missed opportunities."""
        
        total_missed = len(self.missed_signals)
        
        # By reason
        reason_counts = {}
        reason_severity = {}
        for miss in self.missed_signals.values():
            reason = miss.miss_reason.value
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            severity_list = reason_severity.setdefault(reason, [])
            severity_list.append(miss.miss_severity)
        
        # Calculate average severity by reason
        avg_severity_by_reason = {
            reason: np.mean(severities)
            for reason, severities in reason_severity.items()
        }
        
        # Opportunity costs
        total_opportunity_cost = sum(
            s.opportunity_cost for s in self.missed_summaries.values()
        )
        
        return {
            "total_missed_signals": total_missed,
            "misses_by_reason": reason_counts,
            "avg_severity_by_reason": avg_severity_by_reason,
            "total_opportunity_cost": total_opportunity_cost,
            "avg_severity": np.mean([m.miss_severity for m in self.missed_signals.values()]) if self.missed_signals else 0.0
        }


# Global singleton instance
_missed_analyzer = None

def get_missed_opportunities_analyzer() -> MissedOpportunitiesAnalyzer:
    """Get or create singleton analyzer."""
    global _missed_analyzer
    if _missed_analyzer is None:
        _missed_analyzer = MissedOpportunitiesAnalyzer()
    return _missed_analyzer