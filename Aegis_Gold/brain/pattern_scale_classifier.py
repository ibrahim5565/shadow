"""
AEGIS GOLD — Pattern Scale Classification System

Classifies patterns by their temporal scale (SMALL/MEDIUM/LARGE) and validates
entry timing appropriateness.

Philosophy:
-----------
A 5-minute M5 pattern is fundamentally different from a 4-hour H1 pattern.
They require different entry timing, position management, and expectations.

Pattern Scale:
- SMALL: 5-15 min horizon (M1/M5 patterns, quick execution)
- MEDIUM: 15-60 min horizon (M15/M30 patterns, setup→trigger)
- LARGE: 1-4 hour horizon (H1/H4 patterns, patient cascade entry)
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger("aegis.pattern_scale")


class PatternScale(Enum):
    """Pattern temporal scale classification."""
    SMALL = "SMALL"      # 5-15 minute horizon
    MEDIUM = "MEDIUM"    # 15-60 minute horizon
    LARGE = "LARGE"      # 1-4 hour horizon
    UNKNOWN = "UNKNOWN"


class PatternLifecycleState(Enum):
    """Pattern lifecycle progression."""
    FORMING = "FORMING"          # Pattern detected but not complete
    TRIGGERED = "TRIGGERED"      # Pattern complete, entry setup forming
    VALID_ENTRY = "VALID_ENTRY"  # Entry zone confirmed, can execute
    STALE = "STALE"              # Entry window expired
    INVALIDATED = "INVALIDATED"  # Stop loss hit or structure broken
    COMPLETED = "COMPLETED"      # Target reached


@dataclass
class PatternScaleInfo:
    """
    Complete pattern scale classification and timing information.
    """
    # Classification
    scale: PatternScale
    detection_timeframe: str
    confidence: float  # 0.0-1.0 (how confident in this classification)
    
    # Horizon estimation
    estimated_horizon_minutes: int  # Expected pattern duration
    min_horizon_minutes: int        # Minimum expected duration
    max_horizon_minutes: int        # Maximum expected duration
    
    # Entry timing
    entry_window_minutes: int       # How long entry window stays valid
    time_since_detection: int       # Minutes since pattern detected
    entry_window_remaining: int     # Minutes left in entry window
    entry_timing_valid: bool        # Is current timing appropriate?
    
    # Pattern characteristics
    candle_count: int
    price_range_atr: float          # Price range in ATR units
    target_points: float
    invalidation_points: float
    
    # Lifecycle
    lifecycle_state: PatternLifecycleState
    
    def __str__(self) -> str:
        return (
            f"Scale={self.scale.value} | Horizon={self.estimated_horizon_minutes}min | "
            f"EntryWindow={self.entry_window_remaining}/{self.entry_window_minutes}min | "
            f"State={self.lifecycle_state.value} | Valid={self.entry_timing_valid}"
        )


class PatternScaleClassifier:
    """
    Classifies patterns by temporal scale and validates entry timing.
    """
    
    # Timeframe to minutes mapping
    TIMEFRAME_MINUTES = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "H1": 60,
        "H4": 240,
    }
    
    # Entry window as % of horizon by scale
    ENTRY_WINDOW_PCT = {
        PatternScale.SMALL: 0.20,   # 20% of horizon (tight window)
        PatternScale.MEDIUM: 0.30,  # 30% of horizon
        PatternScale.LARGE: 0.40,   # 40% of horizon (patient entry)
    }
    
    def __init__(self):
        self.logger = logging.getLogger("aegis.pattern_scale")
    
    def classify(
        self,
        detection_timeframe: str,
        candle_count: int,
        price_range_atr: float,
        target_points: float,
        invalidation_points: float,
        htf_aligned: bool = False,
        time_since_detection: int = 0,
    ) -> PatternScaleInfo:
        """
        Classify pattern scale and calculate timing information.
        
        Args:
            detection_timeframe: Where pattern was detected (M1/M5/M15/M30/H1/H4)
            candle_count: Number of candles forming the pattern
            price_range_atr: Price range normalized by ATR
            target_points: Distance to target in points
            invalidation_points: Distance to stop loss
            htf_aligned: Is pattern confirmed by higher timeframes?
            time_since_detection: Minutes since pattern was first detected
            
        Returns:
            PatternScaleInfo with complete classification
        """
        
        # 1. Determine scale
        scale = self._classify_scale(
            detection_timeframe,
            candle_count,
            price_range_atr,
            target_points,
            htf_aligned
        )
        
        # 2. Estimate horizon
        horizon_min, horizon_est, horizon_max = self._estimate_horizon(
            scale,
            detection_timeframe,
            candle_count,
            target_points
        )
        
        # 3. Calculate entry window
        entry_window = self._calculate_entry_window(scale, horizon_est)
        entry_remaining = max(0, entry_window - time_since_detection)
        
        # 4. Validate entry timing
        timing_valid = self._validate_entry_timing(
            scale,
            detection_timeframe,
            time_since_detection,
            entry_window
        )
        
        # 5. Determine lifecycle state
        lifecycle_state = self._determine_lifecycle_state(
            time_since_detection,
            entry_window,
            timing_valid
        )
        
        # 6. Confidence in classification
        confidence = self._calculate_classification_confidence(
            scale,
            detection_timeframe,
            candle_count,
            htf_aligned
        )
        
        return PatternScaleInfo(
            scale=scale,
            detection_timeframe=detection_timeframe,
            confidence=confidence,
            estimated_horizon_minutes=horizon_est,
            min_horizon_minutes=horizon_min,
            max_horizon_minutes=horizon_max,
            entry_window_minutes=entry_window,
            time_since_detection=time_since_detection,
            entry_window_remaining=entry_remaining,
            entry_timing_valid=timing_valid,
            candle_count=candle_count,
            price_range_atr=price_range_atr,
            target_points=target_points,
            invalidation_points=invalidation_points,
            lifecycle_state=lifecycle_state
        )
    
    def _classify_scale(
        self,
        timeframe: str,
        candle_count: int,
        price_range_atr: float,
        target_points: float,
        htf_aligned: bool
    ) -> PatternScale:
        """
        Determine pattern scale based on multiple factors.
        """
        
        # Lower timeframes (M1/M5)
        if timeframe in ["M1", "M5"]:
            # Quick small patterns
            if candle_count <= 8 and price_range_atr < 2.0 and target_points < 30:
                return PatternScale.SMALL
            
            # Extended structure on small timeframe
            elif candle_count >= 12 or target_points >= 50:
                return PatternScale.MEDIUM
            
            else:
                return PatternScale.SMALL
        
        # Mid timeframes (M15/M30)
        elif timeframe in ["M15", "M30"]:
            # Quick move, no HTF confirmation = small
            if candle_count <= 6 and not htf_aligned and target_points < 40:
                return PatternScale.SMALL
            
            # Extended structure or HTF aligned = large
            elif candle_count >= 12 or (htf_aligned and target_points > 80):
                return PatternScale.LARGE
            
            # Most M15/M30 patterns are MEDIUM
            else:
                return PatternScale.MEDIUM
        
        # Higher timeframes (H1/H4)
        elif timeframe in ["H1", "H4"]:
            # Large institutional patterns
            if candle_count >= 10 and target_points > 80:
                return PatternScale.LARGE
            
            # Smaller H1 patterns
            elif candle_count < 8 and target_points < 60:
                return PatternScale.MEDIUM
            
            else:
                return PatternScale.LARGE
        
        else:
            return PatternScale.UNKNOWN
    
    def _estimate_horizon(
        self,
        scale: PatternScale,
        timeframe: str,
        candle_count: int,
        target_points: float
    ) -> tuple[int, int, int]:
        """
        Estimate pattern horizon (min, estimate, max) in minutes.
        
        Returns: (min_minutes, estimated_minutes, max_minutes)
        """
        
        tf_minutes = self.TIMEFRAME_MINUTES.get(timeframe, 5)
        base_horizon = candle_count * tf_minutes
        
        # Scale multipliers
        if scale == PatternScale.SMALL:
            multiplier = 1.2
            min_mult = 0.8
            max_mult = 1.5
        
        elif scale == PatternScale.MEDIUM:
            multiplier = 1.5
            min_mult = 1.0
            max_mult = 2.0
        
        elif scale == PatternScale.LARGE:
            multiplier = 2.0
            min_mult = 1.5
            max_mult = 3.0
        
        else:
            multiplier = 1.0
            min_mult = 0.5
            max_mult = 1.5
        
        # Calculate horizons
        estimated = int(base_horizon * multiplier)
        min_horizon = int(base_horizon * min_mult)
        max_horizon = int(base_horizon * max_mult)
        
        # Apply bounds by scale
        if scale == PatternScale.SMALL:
            estimated = max(5, min(15, estimated))
            min_horizon = max(3, min(10, min_horizon))
            max_horizon = max(10, min(20, max_horizon))
        
        elif scale == PatternScale.MEDIUM:
            estimated = max(15, min(60, estimated))
            min_horizon = max(10, min(40, min_horizon))
            max_horizon = max(30, min(90, max_horizon))
        
        elif scale == PatternScale.LARGE:
            estimated = max(60, min(240, estimated))
            min_horizon = max(40, min(120, min_horizon))
            max_horizon = max(120, min(360, max_horizon))
        
        return min_horizon, estimated, max_horizon
    
    def _calculate_entry_window(self, scale: PatternScale, horizon_minutes: int) -> int:
        """
        Calculate how long entry window stays valid.
        """
        pct = self.ENTRY_WINDOW_PCT.get(scale, 0.25)
        window = int(horizon_minutes * pct)
        
        # Apply minimums and maximums
        if scale == PatternScale.SMALL:
            window = max(2, min(10, window))
        
        elif scale == PatternScale.MEDIUM:
            window = max(5, min(30, window))
        
        elif scale == PatternScale.LARGE:
            window = max(15, min(90, window))
        
        return window
    
    def _validate_entry_timing(
        self,
        scale: PatternScale,
        detection_timeframe: str,
        time_since_detection: int,
        entry_window: int
    ) -> bool:
        """
        Validate if current timing is appropriate for pattern scale.
        """
        
        # Entry window expired?
        if time_since_detection > entry_window:
            return False
        
        # Too early? (pattern still forming)
        if time_since_detection < 1:
            return False
        
        # Scale-specific timing rules
        if scale == PatternScale.SMALL:
            # SMALL patterns need quick execution
            if detection_timeframe in ["M1", "M5"]:
                return time_since_detection <= 10
            else:
                return False  # Can't enter SMALL from higher timeframe
        
        elif scale == PatternScale.MEDIUM:
            # MEDIUM patterns need setup confirmation
            if detection_timeframe in ["M1", "M5"]:
                # Need at least 2-5 min for setup to form
                return 2 <= time_since_detection <= 30
            elif detection_timeframe in ["M15", "M30"]:
                return time_since_detection <= 20
            else:
                return False
        
        elif scale == PatternScale.LARGE:
            # LARGE patterns need patience
            if detection_timeframe in ["M1", "M5"]:
                # Too early - need HTF structure first
                return False
            elif detection_timeframe in ["M15", "M30"]:
                # Need time for entry zone to form
                return time_since_detection >= 5
            elif detection_timeframe in ["H1", "H4"]:
                # Need pullback/entry setup
                return time_since_detection >= 10
        
        return True
    
    def _determine_lifecycle_state(
        self,
        time_since_detection: int,
        entry_window: int,
        timing_valid: bool
    ) -> PatternLifecycleState:
        """
        Determine current lifecycle state of pattern.
        """
        
        # Just detected
        if time_since_detection == 0:
            return PatternLifecycleState.FORMING
        
        # Entry window expired
        elif time_since_detection > entry_window:
            return PatternLifecycleState.STALE
        
        # Valid entry timing
        elif timing_valid:
            return PatternLifecycleState.VALID_ENTRY
        
        # Pattern complete but entry not ready
        elif time_since_detection > 0:
            return PatternLifecycleState.TRIGGERED
        
        else:
            return PatternLifecycleState.FORMING
    
    def _calculate_classification_confidence(
        self,
        scale: PatternScale,
        timeframe: str,
        candle_count: int,
        htf_aligned: bool
    ) -> float:
        """
        Calculate confidence in scale classification (0.0-1.0).
        """
        
        confidence = 0.5  # Base confidence
        
        # Clear timeframe-scale match
        if timeframe in ["M1", "M5"] and scale == PatternScale.SMALL:
            confidence += 0.2
        elif timeframe in ["M15", "M30"] and scale == PatternScale.MEDIUM:
            confidence += 0.2
        elif timeframe in ["H1", "H4"] and scale == PatternScale.LARGE:
            confidence += 0.2
        
        # HTF alignment increases confidence
        if htf_aligned:
            confidence += 0.15
        
        # Extreme candle counts suggest uncertainty
        if candle_count < 3 or candle_count > 30:
            confidence -= 0.1
        
        # Normal candle range increases confidence
        elif 5 <= candle_count <= 20:
            confidence += 0.1
        
        return max(0.0, min(1.0, confidence))


def validate_entry_for_pattern_scale(
    pattern_scale_info: PatternScaleInfo,
    current_entry_timeframe: str
) -> tuple[bool, str]:
    """
    Validate if proposed entry timeframe is appropriate for pattern scale.
    
    Args:
        pattern_scale_info: Pattern scale classification
        current_entry_timeframe: Timeframe on which entry is being attempted
        
    Returns:
        (is_valid, reason)
    """
    
    scale = pattern_scale_info.scale
    detection_tf = pattern_scale_info.detection_timeframe
    
    # Check lifecycle state
    if pattern_scale_info.lifecycle_state == PatternLifecycleState.STALE:
        return False, f"Pattern STALE (entry window expired {pattern_scale_info.time_since_detection - pattern_scale_info.entry_window_minutes} min ago)"
    
    if pattern_scale_info.lifecycle_state == PatternLifecycleState.FORMING:
        return False, "Pattern still FORMING (not yet triggered)"
    
    if pattern_scale_info.lifecycle_state == PatternLifecycleState.INVALIDATED:
        return False, "Pattern INVALIDATED (structure broken)"
    
    # Check entry timing
    if not pattern_scale_info.entry_timing_valid:
        return False, f"Entry timing invalid for {scale.value} pattern"
    
    # Check timeframe appropriateness
    if scale == PatternScale.SMALL:
        if current_entry_timeframe not in ["M1", "M5"]:
            return False, f"SMALL pattern requires M1/M5 entry, not {current_entry_timeframe}"
    
    elif scale == PatternScale.MEDIUM:
        if current_entry_timeframe not in ["M1", "M5", "M15"]:
            return False, f"MEDIUM pattern requires M1/M5/M15 entry, not {current_entry_timeframe}"
    
    elif scale == PatternScale.LARGE:
        if current_entry_timeframe not in ["M1", "M5", "M15", "M30"]:
            return False, f"LARGE pattern requires M1/M5/M15/M30 entry, not {current_entry_timeframe}"
        
        # LARGE patterns shouldn't be entered immediately on M1
        if current_entry_timeframe == "M1" and pattern_scale_info.time_since_detection < 10:
            return False, "LARGE pattern too early for M1 entry (need M15 setup first)"
    
    return True, "Entry timing and timeframe valid for pattern scale"
