"""
===========================================================================
AEGIS GOLD — Entry Logic Engine (Phase M)
===========================================================================

PURPOSE:
--------
Implements earliest valid entry logic with setup→trigger pipeline, entry zones,
and chase protection. Transforms pattern detection into actionable trade entries.

CORE FEATURES:
--------------
1. Setup→Trigger Pipeline - Clear separation of pattern setup vs entry trigger
2. Entry Zone Management - Define optimal entry areas with tolerance
3. Chase Protection - Prevent entering after excessive price movement
4. Entry Validation - Multi-layered validation before entry execution
5. Entry Timing Optimization - Precise entry timing within valid windows
6. Miss Prevention - Early warning system for expiring entries

INTEGRATION:
------------
- Uses Opportunity Engine (Phase L) for quality assessment
- Leverages Pattern Quality Gates (Phase C) for validation
- Integrates with MTF Analysis (Phase E) for confluence
- Applies Causality Enforcement (Phase I) for temporal integrity
- Works with 7 AI Engines (Phase K) for consensus signals

===========================================================================
"""

import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple, Union
from enum import Enum
import json

logger = logging.getLogger("aegis.entry")


class SetupStatus(Enum):
    """Pattern setup status levels."""
    NO_SETUP = "NO_SETUP"                   # No pattern detected
    WEAK_SETUP = "WEAK_SETUP"               # Pattern forming but incomplete
    VALID_SETUP = "VALID_SETUP"             # Complete pattern, awaiting trigger
    TRIGGERED = "TRIGGERED"                  # Entry trigger fired
    ENTRY_WINDOW = "ENTRY_WINDOW"           # Active entry window
    EXPIRED = "EXPIRED"                     # Setup expired without entry
    INVALIDATED = "INVALIDATED"             # Setup broken/invalidated


class EntryTriggerType(Enum):
    """Types of entry triggers."""
    BREAKOUT = "BREAKOUT"                   # Price breaks key level
    PULLBACK_COMPLETE = "PULLBACK_COMPLETE" # Retracement finished
    MOMENTUM_SHIFT = "MOMENTUM_SHIFT"       # Momentum confirms direction
    STRUCTURE_BREAK = "STRUCTURE_BREAK"     # Market structure break
    LIQUIDITY_GRAB = "LIQUIDITY_GRAB"      # Liquidity sweep complete
    TIME_TRIGGER = "TIME_TRIGGER"           # Time-based entry signal
    CONFLUENCE_ALIGN = "CONFLUENCE_ALIGN"   # Multiple factors align


class EntryQuality(Enum):
    """Entry execution quality grades."""
    PERFECT = "PERFECT"         # Optimal entry at exact level
    EXCELLENT = "EXCELLENT"     # Very good entry within tight range
    GOOD = "GOOD"              # Acceptable entry within normal range
    FAIR = "FAIR"              # Suboptimal but acceptable entry
    POOR = "POOR"              # Bad entry timing but within limits
    CHASE = "CHASE"            # Entry after excessive movement
    REJECTED = "REJECTED"      # Entry rejected due to poor conditions


@dataclass
class EntryZone:
    """Defines an entry zone for pattern execution."""
    
    # Zone boundaries
    optimal_price: float        # Best entry price
    zone_low: float            # Lower boundary of entry zone
    zone_high: float           # Upper boundary of entry zone
    max_chase_price: float     # Maximum price to chase (protection)
    
    # Zone characteristics
    zone_width: float          # Total zone width in points
    chase_allowance: float     # Additional chase distance
    direction: str             # "BUY" or "SELL"
    
    # Quality scoring
    current_quality: EntryQuality
    distance_penalty: float    # Penalty for distance from optimal
    
    def is_price_in_zone(self, price: float) -> bool:
        """Check if price is within entry zone."""
        return self.zone_low <= price <= self.zone_high
    
    def is_price_chaseable(self, price: float) -> bool:
        """Check if price is within chase limits."""
        if self.direction == "BUY":
            return price <= self.max_chase_price
        else:
            return price >= self.max_chase_price
    
    def calculate_entry_quality(self, entry_price: float) -> EntryQuality:
        """Calculate entry quality based on price distance from optimal."""
        if not self.is_price_chaseable(entry_price):
            return EntryQuality.REJECTED
        
        distance = abs(entry_price - self.optimal_price)
        zone_width = abs(self.zone_high - self.zone_low)
        
        if distance <= zone_width * 0.1:
            return EntryQuality.PERFECT
        elif distance <= zone_width * 0.25:
            return EntryQuality.EXCELLENT
        elif distance <= zone_width * 0.5:
            return EntryQuality.GOOD
        elif self.is_price_in_zone(entry_price):
            return EntryQuality.FAIR
        elif self.is_price_chaseable(entry_price):
            return EntryQuality.CHASE
        else:
            return EntryQuality.REJECTED


@dataclass
class EntryTrigger:
    """Represents an entry trigger event."""
    
    trigger_type: EntryTriggerType
    trigger_price: float
    trigger_time: str
    confidence: float          # Trigger signal strength (0-1)
    
    # Trigger details
    supporting_factors: List[str]
    invalidation_price: float  # Price that invalidates trigger
    urgency_level: str        # "IMMEDIATE", "NORMAL", "PATIENT"
    
    # Market context at trigger
    market_structure: Dict[str, Any]
    volume_confirmation: bool
    momentum_alignment: bool


@dataclass
class EntrySignal:
    """Complete entry signal with all components."""
    
    # Signal identification
    signal_id: str
    pattern_id: str
    symbol: str
    
    # Setup information
    setup_status: SetupStatus
    setup_completion_time: Optional[str]
    setup_quality_score: float  # From opportunity engine
    
    # Trigger information
    entry_trigger: Optional[EntryTrigger]
    trigger_confirmation: bool
    
    # Entry zone
    entry_zone: EntryZone
    current_price: float
    
    # Execution parameters
    recommended_action: str     # "ENTER", "WAIT", "CHASE", "ABORT"
    entry_urgency: str         # Time pressure level
    max_slippage: float        # Acceptable slippage
    
    # Risk management
    stop_loss: float
    take_profit: float
    position_size_fraction: float  # Fraction of max position
    
    # Validation flags
    is_valid: bool
    validation_errors: List[str]
    
    # Timing
    signal_time: str
    expiration_time: str
    window_remaining_seconds: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/transmission."""
        result = asdict(self)
        result['setup_status'] = self.setup_status.value
        result['entry_zone'] = asdict(self.entry_zone)
        if self.entry_trigger:
            result['entry_trigger'] = asdict(self.entry_trigger)
            result['entry_trigger']['trigger_type'] = self.entry_trigger.trigger_type.value
        return result


class EntryLogicEngine:
    """
    Core engine for earliest valid entry logic and execution timing.
    """
    
    def __init__(self):
        # Entry zone parameters
        self.default_zone_width = {
            'SMALL': 8.0,    # Points for small patterns
            'MEDIUM': 15.0,  # Points for medium patterns  
            'LARGE': 25.0    # Points for large patterns
        }
        
        self.chase_multiplier = 1.5  # Max chase = zone_width * multiplier
        self.max_slippage_points = 3.0
        
        # Quality thresholds
        self.min_setup_quality = 55.0
        self.min_trigger_confidence = 0.6
        
        # Timing parameters
        self.setup_timeout_minutes = {
            'SMALL': 30,
            'MEDIUM': 60, 
            'LARGE': 120
        }
        
        # Active tracking
        self.active_setups = {}      # pattern_id -> EntrySignal
        self.triggered_signals = {}  # signal_id -> EntrySignal
        self.entry_history = []
        
        logger.info("[ENTRY] Engine initialized")
    
    def evaluate_setup_status(
        self,
        pattern_context: Dict[str, Any],
        market_snapshot,
        opportunity_assessment=None
    ) -> SetupStatus:
        """
        Evaluate the current setup status of a detected pattern.
        
        Args:
            pattern_context: Pattern details and context
            market_snapshot: Current market conditions  
            opportunity_assessment: Result from opportunity engine
            
        Returns:
            Current setup status
        """
        
        # Check if pattern exists and is valid
        if not pattern_context.get('pattern_type') or pattern_context.get('pattern_type') == 'UNKNOWN':
            return SetupStatus.NO_SETUP
        
        # Check pattern completion
        completion_pct = pattern_context.get('completion_percentage', 0.0)
        if completion_pct < 70.0:
            return SetupStatus.WEAK_SETUP
        
        # Check quality requirements
        if opportunity_assessment:
            quality_score = opportunity_assessment.metrics.overall_quality_score
            if quality_score < self.min_setup_quality:
                return SetupStatus.WEAK_SETUP
        
        # Check if setup is expired
        detection_time = pattern_context.get('detection_time')
        if detection_time:
            try:
                detected_at = datetime.fromisoformat(detection_time.replace('Z', '+00:00'))
                age_minutes = (datetime.now(timezone.utc) - detected_at).total_seconds() / 60
                
                scale = pattern_context.get('scale', 'MEDIUM')
                timeout = self.setup_timeout_minutes.get(scale, 60)
                
                if age_minutes > timeout:
                    return SetupStatus.EXPIRED
            except:
                pass
        
        # Check for invalidation conditions
        if self._is_setup_invalidated(pattern_context, market_snapshot):
            return SetupStatus.INVALIDATED
        
        # Check if already triggered
        if self._is_setup_triggered(pattern_context, market_snapshot):
            return SetupStatus.TRIGGERED
        
        # Default to valid setup
        return SetupStatus.VALID_SETUP
    
    def create_entry_zone(
        self,
        pattern_context: Dict[str, Any],
        market_snapshot
    ) -> EntryZone:
        """
        Create entry zone for pattern with optimal price and boundaries.
        
        Args:
            pattern_context: Pattern details
            market_snapshot: Current market state
            
        Returns:
            EntryZone with calculated boundaries
        """
        
        # Get basic pattern info
        direction = pattern_context.get('direction', 'BUY')
        scale = pattern_context.get('scale', 'MEDIUM')
        entry_price = pattern_context.get('entry_price', market_snapshot.current_price)
        current_price = market_snapshot.current_price
        
        # Calculate zone width based on scale
        base_width = self.default_zone_width.get(scale, 15.0)
        
        # Adjust for volatility
        volatility = getattr(market_snapshot, 'volatility_level', 'NORMAL')
        vol_multiplier = {
            'VERY_LOW': 0.6,
            'LOW': 0.8, 
            'NORMAL': 1.0,
            'HIGH': 1.3,
            'VERY_HIGH': 1.6
        }.get(volatility, 1.0)
        
        zone_width = base_width * vol_multiplier
        chase_distance = zone_width * self.chase_multiplier
        
        # Calculate zone boundaries
        if direction == "BUY":
            zone_low = entry_price - zone_width * 0.3   # Allow some better entry
            zone_high = entry_price + zone_width * 0.7  # Limit chase up
            max_chase_price = entry_price + chase_distance
        else:  # SELL
            zone_high = entry_price + zone_width * 0.3  # Allow some better entry
            zone_low = entry_price - zone_width * 0.7   # Limit chase down 
            max_chase_price = entry_price - chase_distance
        
        # Calculate current quality
        current_quality = EntryQuality.GOOD  # Default
        if current_price != entry_price:
            distance = abs(current_price - entry_price)
            if distance <= zone_width * 0.1:
                current_quality = EntryQuality.PERFECT
            elif distance <= zone_width * 0.25:
                current_quality = EntryQuality.EXCELLENT
            elif distance > zone_width:
                current_quality = EntryQuality.CHASE if abs(current_price - entry_price) <= chase_distance else EntryQuality.REJECTED
        
        distance_penalty = min(1.0, abs(current_price - entry_price) / zone_width) * 0.5
        
        return EntryZone(
            optimal_price=entry_price,
            zone_low=zone_low,
            zone_high=zone_high,
            max_chase_price=max_chase_price,
            zone_width=zone_width,
            chase_allowance=chase_distance - zone_width,
            direction=direction,
            current_quality=current_quality,
            distance_penalty=distance_penalty
        )
    
    def detect_entry_trigger(
        self,
        pattern_context: Dict[str, Any],
        market_snapshot,
        previous_snapshot=None
    ) -> Optional[EntryTrigger]:
        """
        Detect entry trigger events for valid setups.
        
        Args:
            pattern_context: Pattern information
            market_snapshot: Current market state
            previous_snapshot: Previous market state for comparison
            
        Returns:
            EntryTrigger if trigger detected, None otherwise
        """
        
        current_price = market_snapshot.current_price
        direction = pattern_context.get('direction', 'BUY')
        pattern_type = pattern_context.get('pattern_type', '')
        
        # Check for different trigger types
        triggers = []
        
        # 1. Breakout trigger
        breakout_trigger = self._detect_breakout_trigger(
            pattern_context, market_snapshot, previous_snapshot
        )
        if breakout_trigger:
            triggers.append(breakout_trigger)
        
        # 2. Pullback completion trigger
        pullback_trigger = self._detect_pullback_trigger(
            pattern_context, market_snapshot
        )
        if pullback_trigger:
            triggers.append(pullback_trigger)
        
        # 3. Momentum shift trigger
        momentum_trigger = self._detect_momentum_trigger(
            pattern_context, market_snapshot, previous_snapshot
        )
        if momentum_trigger:
            triggers.append(momentum_trigger)
        
        # 4. Structure break trigger
        structure_trigger = self._detect_structure_trigger(
            pattern_context, market_snapshot
        )
        if structure_trigger:
            triggers.append(structure_trigger)
        
        # Return highest confidence trigger
        if triggers:
            best_trigger = max(triggers, key=lambda t: t.confidence)
            if best_trigger.confidence >= self.min_trigger_confidence:
                return best_trigger
        
        return None
    
    def _detect_breakout_trigger(
        self,
        pattern_context: Dict[str, Any],
        market_snapshot,
        previous_snapshot
    ) -> Optional[EntryTrigger]:
        """Detect breakout-based entry trigger."""
        
        current_price = market_snapshot.current_price
        direction = pattern_context.get('direction', 'BUY')
        
        # Get breakout level
        breakout_level = pattern_context.get('entry_price', current_price)
        
        # Check for clean break
        if direction == "BUY" and current_price > breakout_level:
            # Confirm it's a new break (not already broken)
            if previous_snapshot and previous_snapshot.current_price <= breakout_level:
                
                # Calculate confidence based on break strength
                break_strength = (current_price - breakout_level) / breakout_level * 10000  # In pips
                confidence = min(1.0, 0.6 + break_strength * 0.02)  # Base 60% + strength bonus
                
                # Check volume confirmation if available
                volume_confirmed = getattr(market_snapshot, 'volume_spike', False)
                if volume_confirmed:
                    confidence += 0.1
                
                return EntryTrigger(
                    trigger_type=EntryTriggerType.BREAKOUT,
                    trigger_price=current_price,
                    trigger_time=datetime.now(timezone.utc).isoformat(),
                    confidence=confidence,
                    supporting_factors=["Clean level break", "Price momentum"],
                    invalidation_price=breakout_level * 0.999,  # 1 pip below break
                    urgency_level="IMMEDIATE",
                    market_structure={'breakout_level': breakout_level},
                    volume_confirmation=volume_confirmed,
                    momentum_alignment=True
                )
        
        elif direction == "SELL" and current_price < breakout_level:
            if previous_snapshot and previous_snapshot.current_price >= breakout_level:
                
                break_strength = (breakout_level - current_price) / breakout_level * 10000
                confidence = min(1.0, 0.6 + break_strength * 0.02)
                
                volume_confirmed = getattr(market_snapshot, 'volume_spike', False)
                if volume_confirmed:
                    confidence += 0.1
                
                return EntryTrigger(
                    trigger_type=EntryTriggerType.BREAKOUT,
                    trigger_price=current_price,
                    trigger_time=datetime.now(timezone.utc).isoformat(),
                    confidence=confidence,
                    supporting_factors=["Clean level break", "Price momentum"],
                    invalidation_price=breakout_level * 1.001,
                    urgency_level="IMMEDIATE", 
                    market_structure={'breakout_level': breakout_level},
                    volume_confirmation=volume_confirmed,
                    momentum_alignment=True
                )
        
        return None
    
    def _detect_pullback_trigger(
        self,
        pattern_context: Dict[str, Any],
        market_snapshot
    ) -> Optional[EntryTrigger]:
        """Detect pullback completion trigger."""
        
        # Check for pullback patterns
        if 'PULLBACK' not in pattern_context.get('pattern_type', ''):
            return None
        
        current_price = market_snapshot.current_price
        direction = pattern_context.get('direction', 'BUY')
        
        # Get retracement levels
        pullback_start = pattern_context.get('pullback_start', current_price)
        pullback_target = pattern_context.get('pullback_target', current_price)
        
        # Check if pullback is complete (price reached target area)
        if direction == "BUY":
            target_reached = current_price <= pullback_target * 1.002  # Small tolerance
            bounce_strength = (current_price - pullback_target) / pullback_target * 10000
        else:
            target_reached = current_price >= pullback_target * 0.998
            bounce_strength = (pullback_target - current_price) / pullback_target * 10000
        
        if target_reached and bounce_strength > 5:  # At least 5 pip bounce
            confidence = min(1.0, 0.65 + bounce_strength * 0.015)
            
            return EntryTrigger(
                trigger_type=EntryTriggerType.PULLBACK_COMPLETE,
                trigger_price=current_price,
                trigger_time=datetime.now(timezone.utc).isoformat(),
                confidence=confidence,
                supporting_factors=["Pullback target reached", "Reversal signs"],
                invalidation_price=pullback_target,
                urgency_level="NORMAL",
                market_structure={'pullback_target': pullback_target},
                volume_confirmation=False,
                momentum_alignment=bounce_strength > 10
            )
        
        return None
    
    def _detect_momentum_trigger(
        self,
        pattern_context: Dict[str, Any],
        market_snapshot,
        previous_snapshot
    ) -> Optional[EntryTrigger]:
        """Detect momentum shift trigger."""
        
        if not previous_snapshot:
            return None
        
        current_price = market_snapshot.current_price
        previous_price = previous_snapshot.current_price
        direction = pattern_context.get('direction', 'BUY')
        
        # Calculate price momentum
        price_change = current_price - previous_price
        momentum_strength = abs(price_change) / previous_price * 10000  # In pips
        
        # Check momentum alignment with direction
        momentum_aligned = (direction == "BUY" and price_change > 0) or \
                          (direction == "SELL" and price_change < 0)
        
        if momentum_aligned and momentum_strength > 8:  # Minimum 8 pip move
            
            # Get momentum indicators if available
            momentum_score = getattr(market_snapshot, 'momentum_score', 0.5)
            confidence = min(1.0, 0.55 + momentum_strength * 0.01 + momentum_score * 0.2)
            
            return EntryTrigger(
                trigger_type=EntryTriggerType.MOMENTUM_SHIFT,
                trigger_price=current_price,
                trigger_time=datetime.now(timezone.utc).isoformat(),
                confidence=confidence,
                supporting_factors=["Strong momentum", f"{momentum_strength:.1f} pip move"],
                invalidation_price=previous_price,
                urgency_level="NORMAL",
                market_structure={'momentum_strength': momentum_strength},
                volume_confirmation=getattr(market_snapshot, 'volume_spike', False),
                momentum_alignment=True
            )
        
        return None
    
    def _detect_structure_trigger(
        self,
        pattern_context: Dict[str, Any],
        market_snapshot
    ) -> Optional[EntryTrigger]:
        """Detect market structure break trigger."""
        
        pattern_type = pattern_context.get('pattern_type', '')
        
        # Only for structure-based patterns
        if not any(x in pattern_type for x in ['BOS', 'CHOCH', 'STRUCTURE']):
            return None
        
        current_price = market_snapshot.current_price
        direction = pattern_context.get('direction', 'BUY')
        
        # Check for structure break confirmation
        structure_broken = pattern_context.get('structure_broken', False)
        structure_level = pattern_context.get('structure_level', current_price)
        
        if structure_broken:
            # Calculate break strength
            break_distance = abs(current_price - structure_level)
            break_strength = break_distance / structure_level * 10000
            
            confidence = min(1.0, 0.7 + break_strength * 0.01)
            
            return EntryTrigger(
                trigger_type=EntryTriggerType.STRUCTURE_BREAK,
                trigger_price=current_price,
                trigger_time=datetime.now(timezone.utc).isoformat(),
                confidence=confidence,
                supporting_factors=["Market structure break", "Directional bias confirmed"],
                invalidation_price=structure_level,
                urgency_level="IMMEDIATE",
                market_structure={'structure_level': structure_level},
                volume_confirmation=getattr(market_snapshot, 'volume_spike', False),
                momentum_alignment=break_strength > 5
            )
        
        return None
    
    def _is_setup_invalidated(
        self,
        pattern_context: Dict[str, Any],
        market_snapshot
    ) -> bool:
        """Check if setup has been invalidated."""
        
        current_price = market_snapshot.current_price
        direction = pattern_context.get('direction', 'BUY')
        
        # Check invalidation level
        invalidation_level = pattern_context.get('invalidation_level')
        if invalidation_level:
            if direction == "BUY" and current_price < invalidation_level:
                return True
            elif direction == "SELL" and current_price > invalidation_level:
                return True
        
        # Check stop loss breach
        stop_loss = pattern_context.get('stop_loss')
        if stop_loss:
            if direction == "BUY" and current_price <= stop_loss:
                return True
            elif direction == "SELL" and current_price >= stop_loss:
                return True
        
        return False
    
    def _is_setup_triggered(
        self,
        pattern_context: Dict[str, Any],
        market_snapshot
    ) -> bool:
        """Check if setup has already been triggered."""
        
        # Simple implementation - check if price has moved significantly toward target
        current_price = market_snapshot.current_price
        entry_price = pattern_context.get('entry_price', current_price)
        take_profit = pattern_context.get('take_profit', current_price)
        direction = pattern_context.get('direction', 'BUY')
        
        # Calculate how much price has moved toward target
        if direction == "BUY":
            move_toward_target = current_price - entry_price
            total_target_distance = take_profit - entry_price
        else:
            move_toward_target = entry_price - current_price  
            total_target_distance = entry_price - take_profit
        
        # Consider triggered if moved >20% toward target
        if total_target_distance > 0:
            progress_pct = move_toward_target / total_target_distance
            return progress_pct > 0.20
        
        return False
    
    def generate_entry_signal(
        self,
        pattern_context: Dict[str, Any],
        market_snapshot,
        opportunity_assessment=None,
        ai_consensus=None
    ) -> EntrySignal:
        """
        Generate complete entry signal with all components.
        
        Args:
            pattern_context: Pattern information
            market_snapshot: Current market conditions
            opportunity_assessment: Opportunity quality assessment
            ai_consensus: AI consensus result
            
        Returns:
            Complete EntrySignal object
        """
        
        signal_id = f"{pattern_context.get('pattern_id', 'unknown')}_{int(datetime.now().timestamp())}"
        
        # Evaluate setup status
        setup_status = self.evaluate_setup_status(
            pattern_context, market_snapshot, opportunity_assessment
        )
        
        # Create entry zone
        entry_zone = self.create_entry_zone(pattern_context, market_snapshot)
        
        # Detect entry trigger
        entry_trigger = None
        trigger_confirmation = False
        
        if setup_status == SetupStatus.VALID_SETUP:
            entry_trigger = self.detect_entry_trigger(pattern_context, market_snapshot)
            trigger_confirmation = entry_trigger is not None
        
        # Determine recommended action
        recommended_action = self._determine_recommended_action(
            setup_status, entry_trigger, entry_zone, market_snapshot.current_price
        )
        
        # Calculate urgency and timing
        urgency_level = self._calculate_entry_urgency(
            setup_status, entry_trigger, pattern_context
        )
        
        # Validate signal
        is_valid, validation_errors = self._validate_entry_signal(
            pattern_context, setup_status, entry_zone, opportunity_assessment
        )
        
        # Override recommended action if signal is invalid
        if not is_valid:
            recommended_action = "ABORT"
        
        # Get quality score
        quality_score = 0.0
        if opportunity_assessment:
            quality_score = opportunity_assessment.metrics.overall_quality_score
        
        # Calculate position sizing
        position_fraction = self._calculate_position_size(
            opportunity_assessment, entry_zone, ai_consensus
        )
        
        # Create entry signal
        signal = EntrySignal(
            signal_id=signal_id,
            pattern_id=pattern_context.get('pattern_id', 'unknown'),
            symbol=pattern_context.get('symbol', 'XAUUSD'),
            setup_status=setup_status,
            setup_completion_time=pattern_context.get('detection_time'),
            setup_quality_score=quality_score,
            entry_trigger=entry_trigger,
            trigger_confirmation=trigger_confirmation,
            entry_zone=entry_zone,
            current_price=market_snapshot.current_price,
            recommended_action=recommended_action,
            entry_urgency=urgency_level,
            max_slippage=self.max_slippage_points,
            stop_loss=pattern_context.get('stop_loss', 0.0),
            take_profit=pattern_context.get('take_profit', 0.0),
            position_size_fraction=position_fraction,
            is_valid=is_valid,
            validation_errors=validation_errors,
            signal_time=datetime.now(timezone.utc).isoformat(),
            expiration_time=self._calculate_signal_expiration(pattern_context).isoformat(),
            window_remaining_seconds=self._calculate_window_remaining(pattern_context)
        )
        
        # Store for tracking
        if setup_status in [SetupStatus.VALID_SETUP, SetupStatus.TRIGGERED]:
            self.active_setups[signal.pattern_id] = signal
        
        if trigger_confirmation:
            self.triggered_signals[signal_id] = signal
        
        logger.info(
            f"[ENTRY] {signal_id}: {setup_status.value} | "
            f"Action={recommended_action} | Quality={quality_score:.1f}"
        )
        
        return signal
    def _determine_recommended_action(
        self,
        setup_status: SetupStatus,
        entry_trigger: Optional[EntryTrigger],
        entry_zone: EntryZone,
        current_price: float
    ) -> str:
        """Determine recommended action based on setup status and conditions."""
        
        # No action for invalid setups
        if setup_status in [SetupStatus.NO_SETUP, SetupStatus.WEAK_SETUP, 
                           SetupStatus.EXPIRED, SetupStatus.INVALIDATED]:
            return "ABORT"
        
        # Wait for trigger if setup is valid but not triggered
        if setup_status == SetupStatus.VALID_SETUP and not entry_trigger:
            return "WAIT"
        
        # Entry logic when triggered
        if entry_trigger and entry_trigger.confidence >= self.min_trigger_confidence:
            
            # Check if price is in optimal entry zone
            if entry_zone.is_price_in_zone(current_price):
                return "ENTER"
            
            # Check if price is chaseable
            elif entry_zone.is_price_chaseable(current_price):
                # Allow chase only for high confidence triggers
                if entry_trigger.confidence > 0.8 and entry_trigger.urgency_level == "IMMEDIATE":
                    return "CHASE"
                else:
                    return "WAIT"  # Wait for better price
            
            else:
                return "ABORT"  # Price too far, abort
        
        # Default to wait
        return "WAIT"
    
    def _calculate_entry_urgency(
        self,
        setup_status: SetupStatus,
        entry_trigger: Optional[EntryTrigger],
        pattern_context: Dict[str, Any]
    ) -> str:
        """Calculate entry urgency level."""
        
        # High urgency for immediate triggers
        if entry_trigger and entry_trigger.urgency_level == "IMMEDIATE":
            return "IMMEDIATE"
        
        # Check pattern age
        detection_time = pattern_context.get('detection_time')
        if detection_time:
            try:
                detected_at = datetime.fromisoformat(detection_time.replace('Z', '+00:00'))
                age_minutes = (datetime.now(timezone.utc) - detected_at).total_seconds() / 60
                
                scale = pattern_context.get('scale', 'MEDIUM')
                timeout = self.setup_timeout_minutes.get(scale, 60)
                
                # Increasing urgency as expiration approaches
                time_remaining_pct = max(0, (timeout - age_minutes) / timeout)
                
                if time_remaining_pct < 0.2:
                    return "CRITICAL"  # Less than 20% time left
                elif time_remaining_pct < 0.5:
                    return "HIGH"     # Less than 50% time left
                else:
                    return "NORMAL"   # Plenty of time
                    
            except:
                return "NORMAL"
        
        return "NORMAL"
    
    def _validate_entry_signal(
        self,
        pattern_context: Dict[str, Any],
        setup_status: SetupStatus,
        entry_zone: EntryZone,
        opportunity_assessment=None
    ) -> Tuple[bool, List[str]]:
        """Validate entry signal for execution readiness."""
        
        errors = []
        
        # Check setup status
        if setup_status in [SetupStatus.NO_SETUP, SetupStatus.WEAK_SETUP]:
            errors.append(f"Invalid setup status: {setup_status.value}")
        
        # Check entry zone validity
        if entry_zone.zone_width <= 0:
            errors.append("Invalid entry zone width")
        
        if entry_zone.optimal_price <= 0:
            errors.append("Invalid optimal entry price")
        
        # Check risk management
        stop_loss = pattern_context.get('stop_loss', 0.0)
        take_profit = pattern_context.get('take_profit', 0.0)
        
        if stop_loss <= 0:
            errors.append("Missing stop loss")
        
        if take_profit <= 0:
            errors.append("Missing take profit")
        
        # Check risk/reward
        entry_price = entry_zone.optimal_price
        if stop_loss > 0 and take_profit > 0:
            direction = entry_zone.direction
            
            if direction == "BUY":
                risk = abs(entry_price - stop_loss)
                reward = abs(take_profit - entry_price)
            else:
                risk = abs(stop_loss - entry_price)
                reward = abs(entry_price - take_profit)
            
            if risk > 0:
                rr_ratio = reward / risk
                if rr_ratio < 1.0:
                    errors.append(f"Poor risk/reward ratio: {rr_ratio:.2f}")
            else:
                errors.append("Zero risk calculation")
        
        # Check opportunity quality if available
        if opportunity_assessment and not opportunity_assessment.is_tradeable:
            errors.append("Opportunity marked as non-tradeable")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def _calculate_position_size(
        self,
        opportunity_assessment=None,
        entry_zone: EntryZone = None,
        ai_consensus=None
    ) -> float:
        """Calculate position size fraction based on opportunity quality."""
        
        base_fraction = 0.02  # 2% base position
        
        # Adjust based on opportunity quality
        if opportunity_assessment:
            quality_score = opportunity_assessment.metrics.overall_quality_score
            
            if quality_score >= 85:
                multiplier = 1.5    # Excellent opportunities
            elif quality_score >= 70:
                multiplier = 1.2    # Good opportunities  
            elif quality_score >= 55:
                multiplier = 1.0    # Fair opportunities
            else:
                multiplier = 0.5    # Poor opportunities
            
            # Kelly fraction consideration
            kelly_fraction = opportunity_assessment.metrics.kelly_fraction
            if kelly_fraction > 0:
                multiplier = min(multiplier, kelly_fraction / base_fraction)
        
        else:
            multiplier = 1.0
        
        # Adjust for AI confidence
        if ai_consensus:
            confidence = ai_consensus.get('final_confidence', 0.5)
            confidence_multiplier = max(0.5, confidence)
            multiplier *= confidence_multiplier
        
        # Adjust for entry quality
        if entry_zone:
            if entry_zone.current_quality == EntryQuality.PERFECT:
                multiplier *= 1.1
            elif entry_zone.current_quality in [EntryQuality.CHASE, EntryQuality.POOR]:
                multiplier *= 0.7
        
        return min(0.05, base_fraction * multiplier)  # Cap at 5%
    
    def _calculate_signal_expiration(self, pattern_context: Dict[str, Any]) -> datetime:
        """Calculate when entry signal expires."""
        
        base_time = datetime.now(timezone.utc)
        scale = pattern_context.get('scale', 'MEDIUM')
        
        # Shorter expiration for entry signals vs setups
        expiration_minutes = {
            'SMALL': 15,
            'MEDIUM': 30,
            'LARGE': 60
        }
        
        minutes = expiration_minutes.get(scale, 30)
        return base_time + timedelta(minutes=minutes)
    
    def _calculate_window_remaining(self, pattern_context: Dict[str, Any]) -> int:
        """Calculate remaining window in seconds."""
        
        detection_time = pattern_context.get('detection_time')
        if not detection_time:
            return 3600  # Default 1 hour
        
        try:
            detected_at = datetime.fromisoformat(detection_time.replace('Z', '+00:00'))
            scale = pattern_context.get('scale', 'MEDIUM')
            timeout_minutes = self.setup_timeout_minutes.get(scale, 60)
            
            expiration_time = detected_at + timedelta(minutes=timeout_minutes)
            remaining = (expiration_time - datetime.now(timezone.utc)).total_seconds()
            
            return max(0, int(remaining))
            
        except:
            return 3600
    
    def update_active_signals(self, market_snapshot) -> List[EntrySignal]:
        """Update all active entry signals with current market conditions."""
        
        updated_signals = []
        expired_signals = []
        
        for pattern_id, signal in self.active_setups.items():
            
            # Check expiration
            expiration = datetime.fromisoformat(signal.expiration_time.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > expiration:
                expired_signals.append(pattern_id)
                continue
            
            # Update entry zone quality
            signal.entry_zone.current_quality = signal.entry_zone.calculate_entry_quality(
                market_snapshot.current_price
            )
            
            # Update current price
            signal.current_price = market_snapshot.current_price
            
            # Update window remaining
            signal.window_remaining_seconds = self._calculate_window_remaining({
                'detection_time': signal.setup_completion_time,
                'scale': 'MEDIUM'  # Default, could be improved
            })
            
            updated_signals.append(signal)
        
        # Clean up expired signals
        for pattern_id in expired_signals:
            expired_signal = self.active_setups.pop(pattern_id)
            expired_signal.setup_status = SetupStatus.EXPIRED
            expired_signal.recommended_action = "ABORT"
            logger.info(f"[ENTRY] Signal {expired_signal.signal_id} expired")
        
        return updated_signals
    
    def get_best_entry_opportunity(self) -> Optional[EntrySignal]:
        """Get the best current entry opportunity."""
        
        # Get all valid triggered signals
        valid_signals = [
            signal for signal in self.triggered_signals.values()
            if signal.is_valid and signal.recommended_action in ["ENTER", "CHASE"]
        ]
        
        if not valid_signals:
            return None
        
        # Rank by quality score and entry conditions
        def signal_score(signal: EntrySignal) -> float:
            base_score = signal.setup_quality_score / 100.0
            
            # Bonus for immediate entry
            if signal.recommended_action == "ENTER":
                base_score += 0.2
            
            # Bonus for high trigger confidence
            if signal.entry_trigger:
                base_score += signal.entry_trigger.confidence * 0.1
            
            # Penalty for chase
            if signal.recommended_action == "CHASE":
                base_score -= 0.1
            
            # Urgency bonus
            if signal.entry_urgency == "IMMEDIATE":
                base_score += 0.05
            
            return base_score
        
        best_signal = max(valid_signals, key=signal_score)
        return best_signal
    
    def get_entry_summary(self) -> Dict[str, Any]:
        """Get summary of current entry situation."""
        
        active_count = len(self.active_setups)
        triggered_count = len(self.triggered_signals)
        
        # Count by status
        status_counts = {}
        for signal in self.active_setups.values():
            status = signal.setup_status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count by recommended action
        action_counts = {}
        for signal in self.active_setups.values():
            action = signal.recommended_action
            action_counts[action] = action_counts.get(action, 0) + 1
        
        best_opportunity = self.get_best_entry_opportunity()
        
        return {
            "active_setups": active_count,
            "triggered_signals": triggered_count,
            "status_distribution": status_counts,
            "action_distribution": action_counts,
            "best_opportunity": best_opportunity.signal_id if best_opportunity else None,
            "immediate_entries": action_counts.get("ENTER", 0),
            "chase_opportunities": action_counts.get("CHASE", 0),
            "waiting_for_trigger": action_counts.get("WAIT", 0)
        }


# Global singleton instance  
_entry_logic_engine = None

def get_entry_logic_engine() -> EntryLogicEngine:
    """Get or create singleton entry logic engine instance."""
    global _entry_logic_engine
    if _entry_logic_engine is None:
        _entry_logic_engine = EntryLogicEngine()
    return _entry_logic_engine