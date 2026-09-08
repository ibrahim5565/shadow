"""
AEGIS GOLD — Pattern Outcome Tracker

Tracks what happens AFTER a pattern is detected:
- Did it hit TP?
- Did it hit SL?
- Did it go stale?
- Was structure invalidated?

This is Phase G critical infrastructure for calculating TRUE historical edge.
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from enum import Enum
import json
import os

logger = logging.getLogger("aegis.pattern_outcome")


class PatternOutcome(Enum):
    """Final outcome of a pattern after observation period."""
    TP_HIT = "TP_HIT"              # Target reached
    SL_HIT = "SL_HIT"              # Stop loss hit
    STALE = "STALE"                # No significant move within horizon
    INVALIDATED = "INVALIDATED"    # Structure broke, pattern invalid
    PENDING = "PENDING"            # Still being observed
    UNKNOWN = "UNKNOWN"            # Could not determine


@dataclass
class TrackedPattern:
    """
    Complete pattern record with detection, setup, and eventual outcome.
    """
    # Identification
    pattern_id: str
    symbol: str
    pattern_type: str              # "BOS_BULLISH", "CHOCH_BEARISH", etc.
    direction: str                 # "BUY" or "SELL"
    
    # Detection info
    detection_timestamp: str       # ISO format
    detection_timeframe: str       # M5, M15, H1, etc.
    detection_price: float
    
    # Scale & Horizon
    scale: str                     # "SMALL", "MEDIUM", "LARGE"
    estimated_horizon_minutes: int
    
    # Setup levels
    entry_price: float
    stop_loss: float
    take_profit: float
    rr_ratio: float
    
    # Context at detection
    regime: str                    # "TRENDING_UP", "RANGING", etc.
    mtf_alignment: float          # 0.0-1.0
    htf_bias: str                 # "BULLISH", "BEARISH", "NEUTRAL"
    structure_strength: float     # 0.0-1.0
    
    # Outcome (filled after observation)
    outcome: str                  # PatternOutcome enum value
    actual_r: float               # Actual R achieved
    time_to_completion_minutes: int  # How long it took
    max_favorable_r: float        # Best R reached
    max_adverse_r: float          # Worst drawdown
    completion_timestamp: str     # When outcome determined
    
    # Trading decision
    was_traded: bool              # Did bot enter this pattern?
    not_traded_reason: str        # If not traded, why?
    gate_failures: List[str]      # Which quality gates failed
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TrackedPattern':
        """Create from dictionary."""
        # Handle gate_failures as list
        if 'gate_failures' in data and isinstance(data['gate_failures'], str):
            data['gate_failures'] = json.loads(data['gate_failures']) if data['gate_failures'] else []
        return cls(**data)


class PatternOutcomeTracker:
    """
    Tracks patterns from detection → outcome and calculates historical edge.
    """
    
    def __init__(self, storage_path: str = "data/validation/pattern_outcomes.json"):
        self.storage_path = storage_path
        self.tracked_patterns: Dict[str, TrackedPattern] = {}
        self.load()
    
    def load(self):
        """Load tracked patterns from disk."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.tracked_patterns = {
                        k: TrackedPattern.from_dict(v) 
                        for k, v in data.items()
                    }
                logger.info(f"📊 Loaded {len(self.tracked_patterns)} tracked patterns from {self.storage_path}")
            except Exception as e:
                logger.error(f"Failed to load pattern outcomes: {e}")
                self.tracked_patterns = {}
        else:
            logger.info(f"No existing pattern outcomes file at {self.storage_path}")
    
    def save(self):
        """Save tracked patterns to disk."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        try:
            data = {k: v.to_dict() for k, v in self.tracked_patterns.items()}
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"💾 Saved {len(self.tracked_patterns)} pattern outcomes")
        except Exception as e:
            logger.error(f"Failed to save pattern outcomes: {e}")
    
    def track_pattern(
        self,
        pattern_id: str,
        symbol: str,
        pattern_type: str,
        direction: str,
        detection_timestamp: datetime,
        detection_timeframe: str,
        detection_price: float,
        scale: str,
        estimated_horizon_minutes: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        rr_ratio: float,
        regime: str,
        mtf_alignment: float,
        htf_bias: str,
        structure_strength: float,
        was_traded: bool = False,
        not_traded_reason: str = "",
        gate_failures: List[str] = None
    ) -> TrackedPattern:
        """
        Start tracking a newly detected pattern.
        """
        pattern = TrackedPattern(
            pattern_id=pattern_id,
            symbol=symbol,
            pattern_type=pattern_type,
            direction=direction,
            detection_timestamp=detection_timestamp.isoformat(),
            detection_timeframe=detection_timeframe,
            detection_price=detection_price,
            scale=scale,
            estimated_horizon_minutes=estimated_horizon_minutes,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            rr_ratio=rr_ratio,
            regime=regime,
            mtf_alignment=mtf_alignment,
            htf_bias=htf_bias,
            structure_strength=structure_strength,
            outcome=PatternOutcome.PENDING.value,
            actual_r=0.0,
            time_to_completion_minutes=0,
            max_favorable_r=0.0,
            max_adverse_r=0.0,
            completion_timestamp="",
            was_traded=was_traded,
            not_traded_reason=not_traded_reason or "",
            gate_failures=gate_failures or []
        )
        
        self.tracked_patterns[pattern_id] = pattern
        self.save()
        return pattern
    
    def update_pattern_outcome(
        self,
        pattern_id: str,
        current_price: float,
        current_timestamp: datetime
    ) -> Optional[PatternOutcome]:
        """
        Check if pattern outcome can be determined based on current price.
        
        Returns:
            PatternOutcome if determined, None if still PENDING
        """
        if pattern_id not in self.tracked_patterns:
            return None
        
        pattern = self.tracked_patterns[pattern_id]
        
        # Already has outcome
        if pattern.outcome != PatternOutcome.PENDING.value:
            return PatternOutcome(pattern.outcome)
        
        # Calculate current R
        if pattern.direction == "BUY":
            risk_pts = pattern.entry_price - pattern.stop_loss
            current_r = (current_price - pattern.entry_price) / risk_pts if risk_pts > 0 else 0.0
            tp_hit = current_price >= pattern.take_profit
            sl_hit = current_price <= pattern.stop_loss
        else:  # SELL
            risk_pts = pattern.stop_loss - pattern.entry_price
            current_r = (pattern.entry_price - current_price) / risk_pts if risk_pts > 0 else 0.0
            tp_hit = current_price <= pattern.take_profit
            sl_hit = current_price >= pattern.stop_loss
        
        # Update max favorable/adverse
        if current_r > pattern.max_favorable_r:
            pattern.max_favorable_r = current_r
        if current_r < pattern.max_adverse_r:
            pattern.max_adverse_r = current_r
        
        # Check for outcome
        detection_time = datetime.fromisoformat(pattern.detection_timestamp)
        time_elapsed = int((current_timestamp - detection_time).total_seconds() / 60)
        
        outcome = None
        
        if tp_hit:
            # Target hit!
            outcome = PatternOutcome.TP_HIT
            pattern.actual_r = pattern.rr_ratio  # Achieved expected R:R
            pattern.time_to_completion_minutes = time_elapsed
            
        elif sl_hit:
            # Stop loss hit
            outcome = PatternOutcome.SL_HIT
            pattern.actual_r = -1.0
            pattern.time_to_completion_minutes = time_elapsed
            
        elif time_elapsed > pattern.estimated_horizon_minutes * 2:
            # Pattern took too long (2x horizon) → STALE
            outcome = PatternOutcome.STALE
            pattern.actual_r = current_r  # Whatever R we have now
            pattern.time_to_completion_minutes = time_elapsed
        
        # If outcome determined, update pattern
        if outcome:
            pattern.outcome = outcome.value
            pattern.completion_timestamp = current_timestamp.isoformat()
            self.save()
            
            logger.info(
                f"✅ Pattern {pattern_id} outcome: {outcome.value} "
                f"(R={pattern.actual_r:.2f}, Time={time_elapsed}min)"
            )
        
        return outcome
    
    def calculate_historical_edge(
        self,
        pattern_type: Optional[str] = None,
        scale: Optional[str] = None,
        regime: Optional[str] = None,
        mtf_alignment_min: float = 0.0,
        min_sample_size: int = 10
    ) -> Dict[str, Any]:
        """
        Calculate historical edge for patterns matching filters.
        
        Returns:
            Dict with win_rate, avg_win_r, avg_loss_r, expected_r, sample_size, etc.
        """
        # Filter patterns
        filtered = [
            p for p in self.tracked_patterns.values()
            if (pattern_type is None or p.pattern_type == pattern_type) and
               (scale is None or p.scale == scale) and
               (regime is None or p.regime == regime) and
               p.mtf_alignment >= mtf_alignment_min and
               p.outcome != PatternOutcome.PENDING.value
        ]
        
        if len(filtered) < min_sample_size:
            return {
                "sample_size": len(filtered),
                "sufficient_data": False,
                "message": f"Insufficient data: {len(filtered)} < {min_sample_size}"
            }
        
        # Calculate statistics
        wins = [p for p in filtered if p.outcome == PatternOutcome.TP_HIT.value]
        losses = [p for p in filtered if p.outcome == PatternOutcome.SL_HIT.value]
        stale = [p for p in filtered if p.outcome == PatternOutcome.STALE.value]
        
        total = len(filtered)
        win_count = len(wins)
        loss_count = len(losses)
        
        win_rate = win_count / total if total > 0 else 0.0
        
        avg_win_r = sum(p.actual_r for p in wins) / len(wins) if wins else 0.0
        avg_loss_r = sum(p.actual_r for p in losses) / len(losses) if losses else 0.0
        
        expected_r = (win_rate * avg_win_r) + ((1 - win_rate) * avg_loss_r)
        
        avg_time_to_tp = sum(p.time_to_completion_minutes for p in wins) / len(wins) if wins else 0
        avg_max_drawdown = sum(abs(p.max_adverse_r) for p in filtered) / len(filtered) if filtered else 0.0
        
        return {
            "pattern_type": pattern_type or "ALL",
            "scale": scale or "ALL",
            "regime": regime or "ALL",
            "mtf_alignment_min": mtf_alignment_min,
            "sample_size": total,
            "sufficient_data": True,
            "win_count": win_count,
            "loss_count": loss_count,
            "stale_count": len(stale),
            "win_rate": round(win_rate * 100, 1),
            "avg_win_r": round(avg_win_r, 2),
            "avg_loss_r": round(avg_loss_r, 2),
            "expected_r": round(expected_r, 2),
            "avg_time_to_tp_minutes": int(avg_time_to_tp),
            "avg_max_drawdown_r": round(avg_max_drawdown, 2),
            "tradeable": expected_r > 0.5  # Positive edge threshold
        }
    
    def get_missed_opportunities(
        self,
        was_traded: bool = False,
        outcome: str = PatternOutcome.TP_HIT.value
    ) -> List[TrackedPattern]:
        """
        Get patterns that weren't traded but would have been profitable.
        """
        return [
            p for p in self.tracked_patterns.values()
            if p.was_traded == was_traded and p.outcome == outcome
        ]
    
    def calculate_missed_opportunity_cost(self) -> Dict[str, Any]:
        """
        Calculate total R left on the table from missed profitable patterns.
        """
        all_patterns = list(self.tracked_patterns.values())
        traded = [p for p in all_patterns if p.was_traded]
        missed = [p for p in all_patterns if not p.was_traded]
        
        # Profitable patterns that were missed
        profitable_missed = [
            p for p in missed 
            if p.outcome == PatternOutcome.TP_HIT.value and p.actual_r > 0
        ]
        
        total_r_missed = sum(p.actual_r for p in profitable_missed)
        
        # Analyze why missed
        reasons = {}
        for p in missed:
            reason = p.not_traded_reason or "UNKNOWN"
            reasons[reason] = reasons.get(reason, 0) + 1
        
        return {
            "total_patterns": len(all_patterns),
            "patterns_traded": len(traded),
            "patterns_missed": len(missed),
            "profitable_missed": len(profitable_missed),
            "total_r_missed": round(total_r_missed, 2),
            "avg_r_per_missed": round(total_r_missed / len(profitable_missed), 2) if profitable_missed else 0.0,
            "missed_reasons": reasons
        }
    
    def get_pending_patterns(self) -> List[TrackedPattern]:
        """Get all patterns still being observed (outcome not yet determined)."""
        return [
            p for p in self.tracked_patterns.values()
            if p.outcome == PatternOutcome.PENDING.value
        ]
    
    def integrate_with_memory_system(self):
        """
        Integrate with Pattern Memory System for advanced similarity matching.
        Migrates existing patterns and enables memory-based predictions.
        """
        try:
            from brain.pattern_memory_system import get_pattern_memory_system
            
            memory_system = get_pattern_memory_system()
            
            # Migrate existing completed patterns
            migrated_count = memory_system.migrate_from_outcome_tracker(self)
            
            logger.info(f"[MEMORY] Integrated with Pattern Memory System, migrated {migrated_count} patterns")
            return memory_system
            
        except ImportError as e:
            logger.warning(f"[MEMORY] Pattern Memory System not available: {e}")
            return None
    
    def get_memory_prediction(self, pattern_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get pattern outcome prediction from memory system based on similarity.
        
        Args:
            pattern_context: Dict with pattern characteristics for fingerprinting
            
        Returns:
            Dict with prediction or None if memory system unavailable
        """
        try:
            from brain.pattern_memory_system import get_pattern_memory_system
            
            memory_system = get_pattern_memory_system()
            
            # Create fingerprint from context
            fingerprint = memory_system.create_pattern_fingerprint(
                pattern_type=pattern_context.get('pattern_type', 'UNKNOWN'),
                scale=pattern_context.get('scale', 'MEDIUM'),
                direction=pattern_context.get('direction', 'BUY'),
                price_levels=pattern_context.get('price_levels', []),
                candle_data=pattern_context.get('candle_data', []),
                regime=pattern_context.get('regime', 'UNKNOWN'),
                mtf_alignment=pattern_context.get('mtf_alignment', 0.5),
                volatility=pattern_context.get('volatility', 0.5),
                formation_speed=pattern_context.get('formation_speed', 0.5),
                timeframe=pattern_context.get('timeframe', 'M15'),
                rr_ratio=pattern_context.get('rr_ratio', 2.0),
                structure_strength=pattern_context.get('structure_strength', 0.5)
            )
            
            # Get prediction
            prediction = memory_system.predict_pattern_outcome(fingerprint)
            
            if prediction.sample_size >= 3:  # Sufficient data
                return prediction.to_dict()
            else:
                return None
                
        except ImportError as e:
            logger.warning(f"[MEMORY] Pattern Memory System not available: {e}")
            return None
        except Exception as e:
            logger.error(f"[MEMORY] Error getting memory prediction: {e}")
            return None
    
    def generate_summary_report(self) -> str:
        """Generate human-readable summary of all tracked patterns."""
        total = len(self.tracked_patterns)
        pending = len([p for p in self.tracked_patterns.values() if p.outcome == PatternOutcome.PENDING.value])
        completed = total - pending
        
        report = [
            "="*70,
            "PATTERN OUTCOME TRACKER — SUMMARY REPORT",
            "="*70,
            f"Total Patterns Tracked: {total}",
            f"Completed: {completed}",
            f"Pending: {pending}",
            "",
            "OVERALL EDGE:",
            "-"*70
        ]
        
        overall_edge = self.calculate_historical_edge(min_sample_size=1)
        if overall_edge.get("sufficient_data"):
            report.extend([
                f"Sample Size: {overall_edge['sample_size']}",
                f"Win Rate: {overall_edge['win_rate']}%",
                f"Avg Win: +{overall_edge['avg_win_r']}R",
                f"Avg Loss: {overall_edge['avg_loss_r']}R",
                f"Expected R: {overall_edge['expected_r']}R",
                f"Tradeable: {'YES ✓' if overall_edge['tradeable'] else 'NO ✗'}",
                ""
            ])
        
        # Missed opportunities
        missed_cost = self.calculate_missed_opportunity_cost()
        report.extend([
            "MISSED OPPORTUNITIES:",
            "-"*70,
            f"Patterns Missed: {missed_cost['patterns_missed']}",
            f"Profitable Missed: {missed_cost['profitable_missed']}",
            f"Total R Missed: {missed_cost['total_r_missed']}R",
            f"Avg R/Missed: {missed_cost['avg_r_per_missed']}R",
            "",
            "Top Reasons:",
        ])
        
        for reason, count in sorted(missed_cost['missed_reasons'].items(), key=lambda x: x[1], reverse=True)[:5]:
            report.append(f"  - {reason}: {count} patterns")
        
        report.append("="*70)
        
        return "\n".join(report)
