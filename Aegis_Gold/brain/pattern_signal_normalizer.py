"""
AEGIS GOLD — Pattern Signal Normalizer

Canonical pattern signal normalization layer.

This module provides a single source of truth for converting raw pattern detection
results into the canonical pattern_signal format used throughout the decision pipeline.

RULES:
- One canonical structure for all pattern signals
- No duplication of pattern parsing logic
- Type-safe with sensible defaults
- Preserves all relevant pattern metadata
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger("pattern_normalizer")


@dataclass
class CanonicalPatternSignal:
    """
    Canonical representation of a pattern signal.
    
    This is the single source of truth for pattern information flowing through
    the decision pipeline.
    """
    direction: str                    # "BUY", "SELL", "NONE"
    confidence: float                 # 0.0 - 100.0 (percentage)
    pattern_name: Optional[str]       # e.g., "Bullish Engulfing", None if no pattern
    source: str                       # e.g., "smc_pattern_engine", "none"
    grade: Optional[str] = None       # "A+", "A", "B", None if no pattern
    sl_points: Optional[int] = None   # Stop loss in points
    tp_points: Optional[int] = None   # Take profit in points
    rr_ratio: Optional[float] = None  # Risk/reward ratio
    entry_price: Optional[float] = None  # Entry price for pattern
    stop_loss: Optional[float] = None    # Stop loss price
    take_profit: Optional[float] = None  # Take profit price
    risk_reward_ratio: Optional[float] = None  # RR at entry
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for passing to fusion layer."""
        return {
            "direction": self.direction,
            "confidence": self.confidence,
            "pattern_name": self.pattern_name,
            "source": self.source,
            "grade": self.grade,
            "sl_points": self.sl_points,
            "tp_points": self.tp_points,
            "rr_ratio": self.rr_ratio,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward_ratio": self.risk_reward_ratio,
        }
    
    def is_empty(self) -> bool:
        """Check if this is an empty/null pattern signal."""
        return self.direction == "NONE" and self.pattern_name is None


def normalize_pattern_signal(
    pattern_result: Optional[Any] = None,
    raw_direction: Optional[str] = None,
    confidence: Optional[float] = None,
    pattern_name: Optional[str] = None,
    grade: Optional[str] = None,
    sl_points: Optional[int] = None,
    tp_points: Optional[int] = None,
    rr_ratio: Optional[float] = None,
    entry_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    risk_reward_ratio: Optional[float] = None,
) -> CanonicalPatternSignal:
    """
    Normalize pattern detection results into canonical pattern_signal format.
    
    Supports multiple input styles:
    1. Raw pattern object with attributes
    2. Keyword arguments with individual fields
    
    Args:
        pattern_result: Raw pattern object from pattern engine (if present)
        raw_direction: "BULLISH", "BEARISH", or None
        confidence: Confidence percentage (0-100)
        pattern_name: Name of detected pattern
        grade: Quality grade (A+, A, B, etc.)
        sl_points: Stop loss in points
        tp_points: Take profit in points
        rr_ratio: Risk/reward ratio
        entry_price: Entry price
        stop_loss: Stop loss price
        take_profit: Take profit price
        risk_reward_ratio: RR ratio at entry
    
    Returns:
        CanonicalPatternSignal with all fields properly initialized
    """
    
    # Default to empty pattern
    canonical = CanonicalPatternSignal(
        direction="NONE",
        confidence=0.0,
        pattern_name=None,
        source="none"
    )
    
    # If no input at all, return empty
    if pattern_result is None and raw_direction is None:
        return canonical
    
    # If pattern_result object provided, extract fields
    if pattern_result is not None:
        try:
            # Map various attribute names for direction
            raw_dir = getattr(pattern_result, "direction", None) or raw_direction
            
            # Normalize direction: convert BULLISH->BUY, BEARISH->SELL
            if raw_dir:
                if "BULL" in str(raw_dir).upper():
                    canonical.direction = "BUY"
                elif "BEAR" in str(raw_dir).upper():
                    canonical.direction = "SELL"
                elif str(raw_dir).upper() in ("BUY", "SELL"):
                    canonical.direction = str(raw_dir).upper()
            
            # Extract confidence
            conf = getattr(pattern_result, "confidence", None) or confidence
            if conf is not None:
                canonical.confidence = float(conf)
            
            # Extract pattern name
            pname = getattr(pattern_result, "name", None) or pattern_name
            if pname:
                canonical.pattern_name = str(pname)
            
            # Extract grade
            grade_val = getattr(pattern_result, "grade", None) or grade
            if grade_val:
                canonical.grade = str(grade_val)
            
            # Extract SL/TP/RR
            sl_pts = getattr(pattern_result, "sl_pts", None) or sl_points
            if sl_pts is not None:
                canonical.sl_points = int(sl_pts)
            
            tp_pts = getattr(pattern_result, "tp_pts", None) or tp_points
            if tp_pts is not None:
                canonical.tp_points = int(tp_pts)
            
            rr = getattr(pattern_result, "risk_reward", None) or rr_ratio
            if rr is not None:
                canonical.rr_ratio = float(rr)
            
            # Extract prices
            entry = getattr(pattern_result, "entry_price", None) or entry_price
            if entry is not None:
                canonical.entry_price = float(entry)
            
            sl = getattr(pattern_result, "stop_loss", None) or stop_loss
            if sl is not None:
                canonical.stop_loss = float(sl)
            
            tp = getattr(pattern_result, "take_profit", None) or take_profit
            if tp is not None:
                canonical.take_profit = float(tp)
            
            # Extract RR ratio
            rr_r = getattr(pattern_result, "risk_reward_ratio", None) or risk_reward_ratio
            if rr_r is not None:
                canonical.risk_reward_ratio = float(rr_r)
            
            # Set source
            canonical.source = "smc_pattern_engine"
            
        except Exception as e:
            logger.warning(f"Error extracting pattern fields: {e}")
            # Return default (safe fallback)
            return canonical
    
    # Use keyword arguments if object extraction didn't fully populate
    if not canonical.pattern_name and pattern_name:
        canonical.pattern_name = str(pattern_name)
    
    if canonical.confidence == 0.0 and confidence is not None:
        canonical.confidence = float(confidence)
    
    if canonical.direction == "NONE" and raw_direction:
        if "BULL" in str(raw_direction).upper():
            canonical.direction = "BUY"
        elif "BEAR" in str(raw_direction).upper():
            canonical.direction = "SELL"
    
    # Validate direction
    if canonical.direction not in ("BUY", "SELL", "NONE"):
        canonical.direction = "NONE"
    
    # Validate confidence (0-100)
    canonical.confidence = max(0.0, min(100.0, canonical.confidence))
    
    logger.debug(
        "[PATTERN_NORMALIZER] Normalized pattern: direction=%s confidence=%.1f%% pattern=%s grade=%s",
        canonical.direction, canonical.confidence, canonical.pattern_name, canonical.grade
    )
    
    return canonical


def pattern_signal_from_decision(decision: Any) -> CanonicalPatternSignal:
    """
    Extract pattern_signal from a Decision object.
    
    Used when a Decision has already been created but we need to extract
    its pattern information for routing to fusion layer.
    
    Args:
        decision: Decision object with potential pattern data
    
    Returns:
        CanonicalPatternSignal
    """
    if not decision:
        return CanonicalPatternSignal(
            direction="NONE",
            confidence=0.0,
            pattern_name=None,
            source="none"
        )
    
    # If decision came from pattern engine, extract all fields
    if getattr(decision, "signal_source", None) == "PATTERN_ENGINE":
        return normalize_pattern_signal(
            raw_direction="BUY" if decision.direction == "BUY" else "SELL" if decision.direction == "SELL" else None,
            confidence=decision.confidence,
            pattern_name=getattr(decision, "pattern", None),
            grade=getattr(decision, "grade", None),
            sl_points=getattr(decision, "sl_points", None),
            tp_points=getattr(decision, "tp_points", None),
            rr_ratio=getattr(decision, "rr_ratio", None),
            entry_price=getattr(decision, "entry_price", None),
            stop_loss=getattr(decision, "stop_loss", None),
            take_profit=getattr(decision, "take_profit", None),
        )
    
    # Otherwise, empty pattern (pattern didn't generate this decision)
    return CanonicalPatternSignal(
        direction="NONE",
        confidence=0.0,
        pattern_name=None,
        source="none"
    )


# Convenience function: create empty pattern signal
def empty_pattern_signal() -> CanonicalPatternSignal:
    """Create an empty/null pattern signal."""
    return CanonicalPatternSignal(
        direction="NONE",
        confidence=0.0,
        pattern_name=None,
        source="none"
    )
