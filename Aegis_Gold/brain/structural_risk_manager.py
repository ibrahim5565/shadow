"""
===========================================================================
AEGIS GOLD — Structural Risk Manager (Phase N)
===========================================================================

PURPOSE:
--------
Implements structural stop loss and take profit management with intelligent
adjustments based on market structure, pattern evolution, and risk optimization.

CORE FEATURES:
--------------
1. Structure-Based Stops - SL/TP based on market structure levels
2. Dynamic Adjustment - Real-time SL/TP updates as patterns evolve
3. Trailing Mechanisms - Advanced trailing stops with structure awareness
4. Multi-Level Targets - Partial profit taking at key levels
5. Breakeven Management - Moving to breakeven at optimal timing
6. Risk Optimization - Position sizing and risk adjustment

INTEGRATION:
------------
- Uses Pattern Outcome Tracker (Phase G) for pattern evolution
- Leverages MTF Analysis (Phase E) for structure levels
- Applies Causality Enforcement (Phase I) for temporal integrity
- Works with Entry Logic Engine (Phase M) for coordinated risk management

===========================================================================
"""

import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple, Union
from enum import Enum
import json

logger = logging.getLogger("aegis.risk")


class StopLossType(Enum):
    """Types of stop loss mechanisms."""
    STRUCTURAL = "STRUCTURAL"           # Based on market structure levels
    ATR_BASED = "ATR_BASED"            # Average True Range based
    PERCENTAGE = "PERCENTAGE"          # Fixed percentage from entry
    TRAILING = "TRAILING"              # Trailing stop mechanism
    BREAKEVEN = "BREAKEVEN"            # Moved to breakeven
    PATTERN_BASED = "PATTERN_BASED"    # Based on pattern invalidation
    LIQUIDITY = "LIQUIDITY"            # Below liquidity levels


class TakeProfitType(Enum):
    """Types of take profit mechanisms."""
    STRUCTURAL = "STRUCTURAL"          # Structure-based targets
    FIBONACCI = "FIBONACCI"            # Fibonacci extension levels
    ATR_MULTIPLE = "ATR_MULTIPLE"      # ATR multiple targets
    PATTERN_TARGET = "PATTERN_TARGET"  # Pattern-specific targets
    PARTIAL = "PARTIAL"                # Partial profit taking
    TRAIL_TO_TARGET = "TRAIL_TO_TARGET" # Trail to final target


class RiskAdjustmentReason(Enum):
    """Reasons for risk adjustment."""
    STRUCTURE_BREAK = "STRUCTURE_BREAK"
    PATTERN_EVOLUTION = "PATTERN_EVOLUTION"
    VOLATILITY_CHANGE = "VOLATILITY_CHANGE"
    TIME_DECAY = "TIME_DECAY"
    PROFIT_PROTECTION = "PROFIT_PROTECTION"
    CORRELATION_RISK = "CORRELATION_RISK"
    NEWS_EVENT = "NEWS_EVENT"
    DRAWDOWN_CONTROL = "DRAWDOWN_CONTROL"


@dataclass
class StructuralLevel:
    """Represents a structural market level for risk management."""
    
    level_price: float
    level_type: str              # "SUPPORT", "RESISTANCE", "PIVOT", "LIQUIDITY"
    strength: float              # Level strength 0-1
    timeframe: str              # Timeframe where level is significant
    age_bars: int               # How old the level is
    test_count: int             # How many times tested
    last_test_time: Optional[str]
    confluence_factors: List[str]  # What makes this level significant
    
    def is_valid_level(self, current_time: datetime) -> bool:
        """Check if structural level is still valid."""
        if self.strength < 0.3:
            return False
        
        # Check age limits based on timeframe
        max_age = {
            'M1': 240,    # 4 hours
            'M5': 1440,   # 5 days
            'M15': 2880,  # 20 days
            'H1': 5760,   # 40 days
            'H4': 17280,  # 120 days
            'D1': 43200   # 300 days
        }.get(self.timeframe, 1440)
        
        return self.age_bars <= max_age


@dataclass
class RiskParameters:
    """Complete risk management parameters for a position."""
    
    # Stop Loss Configuration
    stop_loss_price: float
    stop_loss_type: StopLossType
    initial_stop_distance: float
    current_stop_distance: float
    
    # Take Profit Configuration
    take_profit_levels: List[Tuple[float, float]]  # [(price, partial_size), ...]
    take_profit_type: TakeProfitType
    final_target: float
    
    # Trailing Configuration
    trailing_active: bool
    trailing_distance: float
    trailing_trigger: Optional[float]
    breakeven_trigger: Optional[float]
    
    # Risk Metrics
    risk_reward_ratio: float
    max_loss_amount: float
    position_risk_pct: float
    
    # Adjustment History
    adjustment_history: List[Dict[str, Any]]
    last_adjustment_time: Optional[str]
    
    def calculate_current_risk_reward(self, current_price: float, direction: str) -> float:
        """Calculate current risk-reward ratio."""
        if direction == "BUY":
            current_risk = abs(current_price - self.stop_loss_price)
            current_reward = abs(self.final_target - current_price)
        else:
            current_risk = abs(self.stop_loss_price - current_price)
            current_reward = abs(current_price - self.final_target)
        
        return current_reward / current_risk if current_risk > 0 else 0.0


@dataclass
class RiskAdjustment:
    """Represents a risk management adjustment."""
    
    adjustment_id: str
    timestamp: str
    reason: RiskAdjustmentReason
    
    # Changes made
    old_stop_loss: float
    new_stop_loss: float
    old_take_profit: float
    new_take_profit: float
    
    # Context
    trigger_price: float
    market_conditions: Dict[str, Any]
    confidence: float
    
    # Impact
    risk_change_pct: float
    reward_change_pct: float
    expected_improvement: float


@dataclass
class TradeRisk:
    """Complete trade risk state and management."""
    
    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    position_size: float
    
    # Current risk parameters
    risk_params: RiskParameters
    structural_levels: List[StructuralLevel]
    
    # Status tracking
    is_active: bool
    in_profit: bool
    breakeven_hit: bool
    partial_fills: List[Dict[str, Any]]
    
    # Performance metrics
    unrealized_pnl: float
    max_favorable_excursion: float
    max_adverse_excursion: float
    
    # Updates
    last_update_time: str
    update_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        result = asdict(self)
        result['risk_params'] = asdict(self.risk_params)
        result['structural_levels'] = [asdict(level) for level in self.structural_levels]
        return result


class StructuralRiskManager:
    """
    Advanced risk management system with structural awareness.
    """
    
    def __init__(self):
        # Risk parameters
        self.default_risk_pct = 1.0  # 1% risk per trade
        self.max_risk_pct = 2.0     # Maximum 2% risk
        self.min_rr_ratio = 1.5     # Minimum 1.5:1 R/R
        
        # Trailing parameters
        self.trailing_start_rr = 1.0  # Start trailing at 1:1 R/R
        self.trailing_step = 0.5      # Trail by 50% of profit move
        self.breakeven_trigger_rr = 0.5  # Move to BE at 0.5:1 R/R
        
        # Structure parameters
        self.min_level_strength = 0.4
        self.level_buffer_pips = 2.0
        
        # Active trades tracking
        self.active_trades = {}      # trade_id -> TradeRisk
        self.adjustment_history = []
        self.performance_metrics = {
            'total_adjustments': 0,
            'profitable_adjustments': 0,
            'avg_risk_reduction': 0.0,
            'avg_reward_improvement': 0.0
        }
        
        logger.info("[RISK] Structural Risk Manager initialized")
    
    def calculate_structural_stops(
        self,
        entry_price: float,
        direction: str,
        pattern_context: Dict[str, Any],
        market_structure: Dict[str, Any]
    ) -> RiskParameters:
        """
        Calculate optimal stop loss and take profit based on market structure.
        
        Args:
            entry_price: Entry price of the position
            direction: "BUY" or "SELL"
            pattern_context: Pattern information
            market_structure: Current market structure data
            
        Returns:
            Complete risk parameters
        """
        
        # Get structural levels
        structural_levels = self._identify_structural_levels(
            entry_price, direction, market_structure
        )
        
        # Calculate stop loss
        stop_loss_price, stop_type = self._calculate_structural_stop_loss(
            entry_price, direction, structural_levels, pattern_context
        )
        
        # Calculate take profit levels
        tp_levels, tp_type, final_target = self._calculate_structural_take_profit(
            entry_price, direction, structural_levels, pattern_context
        )
        
        # Calculate distances
        if direction == "BUY":
            stop_distance = abs(entry_price - stop_loss_price)
        else:
            stop_distance = abs(stop_loss_price - entry_price)
        
        # Calculate risk-reward ratio
        risk_reward_ratio = abs(final_target - entry_price) / stop_distance
        
        # Calculate position sizing
        position_risk_pct = min(self.default_risk_pct, self.max_risk_pct)
        max_loss_amount = position_risk_pct / 100.0  # As fraction
        
        # Setup trailing parameters
        trailing_distance = stop_distance * 0.5  # Start with 50% of initial risk
        breakeven_trigger = entry_price + (stop_distance * self.breakeven_trigger_rr * (1 if direction == "BUY" else -1))
        
        return RiskParameters(
            stop_loss_price=stop_loss_price,
            stop_loss_type=stop_type,
            initial_stop_distance=stop_distance,
            current_stop_distance=stop_distance,
            take_profit_levels=tp_levels,
            take_profit_type=tp_type,
            final_target=final_target,
            trailing_active=False,
            trailing_distance=trailing_distance,
            trailing_trigger=None,
            breakeven_trigger=breakeven_trigger,
            risk_reward_ratio=risk_reward_ratio,
            max_loss_amount=max_loss_amount,
            position_risk_pct=position_risk_pct,
            adjustment_history=[],
            last_adjustment_time=None
        )
    
    def _identify_structural_levels(
        self,
        reference_price: float,
        direction: str,
        market_structure: Dict[str, Any]
    ) -> List[StructuralLevel]:
        """Identify relevant structural levels for risk management."""
        
        levels = []
        
        # Get structure data
        support_levels = market_structure.get('support_levels', [])
        resistance_levels = market_structure.get('resistance_levels', [])
        pivot_levels = market_structure.get('pivot_levels', [])
        liquidity_levels = market_structure.get('liquidity_levels', [])
        
        # Process support levels
        for level_data in support_levels:
            if isinstance(level_data, dict):
                price = level_data.get('price', 0)
                strength = level_data.get('strength', 0.5)
                timeframe = level_data.get('timeframe', 'H1')
            else:
                price = float(level_data)
                strength = 0.5
                timeframe = 'H1'
            
            if strength >= self.min_level_strength:
                levels.append(StructuralLevel(
                    level_price=price,
                    level_type="SUPPORT",
                    strength=strength,
                    timeframe=timeframe,
                    age_bars=level_data.get('age_bars', 100) if isinstance(level_data, dict) else 100,
                    test_count=level_data.get('test_count', 2) if isinstance(level_data, dict) else 2,
                    last_test_time=None,
                    confluence_factors=level_data.get('confluence_factors', []) if isinstance(level_data, dict) else []
                ))
        
        # Process resistance levels
        for level_data in resistance_levels:
            if isinstance(level_data, dict):
                price = level_data.get('price', 0)
                strength = level_data.get('strength', 0.5)
                timeframe = level_data.get('timeframe', 'H1')
            else:
                price = float(level_data)
                strength = 0.5
                timeframe = 'H1'
            
            if strength >= self.min_level_strength:
                levels.append(StructuralLevel(
                    level_price=price,
                    level_type="RESISTANCE",
                    strength=strength,
                    timeframe=timeframe,
                    age_bars=level_data.get('age_bars', 100) if isinstance(level_data, dict) else 100,
                    test_count=level_data.get('test_count', 2) if isinstance(level_data, dict) else 2,
                    last_test_time=None,
                    confluence_factors=level_data.get('confluence_factors', []) if isinstance(level_data, dict) else []
                ))
        
        # Add liquidity levels
        for level_data in liquidity_levels:
            if isinstance(level_data, dict):
                price = level_data.get('price', 0)
            else:
                price = float(level_data)
            
            levels.append(StructuralLevel(
                level_price=price,
                level_type="LIQUIDITY",
                strength=0.8,  # Liquidity levels are important
                timeframe='M15',
                age_bars=50,
                test_count=1,
                last_test_time=None,
                confluence_factors=['liquidity_sweep']
            ))
        
        # Filter and sort by relevance to direction and price
        relevant_levels = []
        for level in levels:
            if direction == "BUY":
                # For BUY positions, we care about support (for SL) and resistance (for TP)
                if level.level_type in ["SUPPORT", "LIQUIDITY"] and level.level_price < reference_price:
                    relevant_levels.append(level)
                elif level.level_type == "RESISTANCE" and level.level_price > reference_price:
                    relevant_levels.append(level)
            else:
                # For SELL positions, we care about resistance (for SL) and support (for TP)
                if level.level_type in ["RESISTANCE", "LIQUIDITY"] and level.level_price > reference_price:
                    relevant_levels.append(level)
                elif level.level_type == "SUPPORT" and level.level_price < reference_price:
                    relevant_levels.append(level)
        
        # Sort by strength and proximity
        def level_score(level):
            distance = abs(level.level_price - reference_price)
            return level.strength - (distance / reference_price)  # Closer and stronger = higher score
        
        relevant_levels.sort(key=level_score, reverse=True)
        return relevant_levels[:10]  # Keep top 10 most relevant levels
    
    def _calculate_structural_stop_loss(
        self,
        entry_price: float,
        direction: str,
        structural_levels: List[StructuralLevel],
        pattern_context: Dict[str, Any]
    ) -> Tuple[float, StopLossType]:
        """Calculate optimal stop loss based on structure."""
        
        # Get pattern-specific invalidation level
        pattern_invalidation = pattern_context.get('invalidation_level')
        
        # Find best structural stop level
        stop_candidates = []
        
        for level in structural_levels:
            if direction == "BUY" and level.level_type in ["SUPPORT", "LIQUIDITY"]:
                if level.level_price < entry_price:
                    # Place stop below support with buffer
                    stop_price = level.level_price - self.level_buffer_pips
                    distance = entry_price - stop_price
                    score = level.strength * (1 + level.test_count * 0.1)
                    stop_candidates.append((stop_price, distance, score, StopLossType.STRUCTURAL))
            
            elif direction == "SELL" and level.level_type in ["RESISTANCE", "LIQUIDITY"]:
                if level.level_price > entry_price:
                    # Place stop above resistance with buffer
                    stop_price = level.level_price + self.level_buffer_pips
                    distance = stop_price - entry_price
                    score = level.strength * (1 + level.test_count * 0.1)
                    stop_candidates.append((stop_price, distance, score, StopLossType.STRUCTURAL))
        
        # Add pattern invalidation as candidate
        if pattern_invalidation:
            if direction == "BUY" and pattern_invalidation < entry_price:
                distance = entry_price - pattern_invalidation
                stop_candidates.append((pattern_invalidation, distance, 0.8, StopLossType.PATTERN_BASED))
            elif direction == "SELL" and pattern_invalidation > entry_price:
                distance = pattern_invalidation - entry_price
                stop_candidates.append((pattern_invalidation, distance, 0.8, StopLossType.PATTERN_BASED))
        
        # Add ATR-based fallback
        atr_value = pattern_context.get('atr', 20.0)  # Default ATR
        if direction == "BUY":
            atr_stop = entry_price - (atr_value * 1.5)
            atr_distance = entry_price - atr_stop
        else:
            atr_stop = entry_price + (atr_value * 1.5)
            atr_distance = atr_stop - entry_price
        
        stop_candidates.append((atr_stop, atr_distance, 0.6, StopLossType.ATR_BASED))
        
        # Select best candidate (balance between score and reasonable distance)
        if stop_candidates:
            # Filter out stops that are too tight or too wide
            max_distance = entry_price * 0.03  # Max 3% risk
            min_distance = entry_price * 0.005  # Min 0.5% risk
            
            valid_candidates = [
                (price, dist, score, type_) for price, dist, score, type_ in stop_candidates
                if min_distance <= dist <= max_distance
            ]
            
            if valid_candidates:
                # Choose highest scoring valid candidate
                best_candidate = max(valid_candidates, key=lambda x: x[2])
                return best_candidate[0], best_candidate[3]
            else:
                # Use ATR-based if no valid structural levels
                return atr_stop, StopLossType.ATR_BASED
        
        # Fallback to percentage-based
        if direction == "BUY":
            fallback_stop = entry_price * 0.985  # 1.5% stop
        else:
            fallback_stop = entry_price * 1.015
        
        return fallback_stop, StopLossType.PERCENTAGE
    
    def _calculate_structural_take_profit(
        self,
        entry_price: float,
        direction: str,
        structural_levels: List[StructuralLevel],
        pattern_context: Dict[str, Any]
    ) -> Tuple[List[Tuple[float, float]], TakeProfitType, float]:
        """Calculate take profit levels based on structure."""
        
        tp_levels = []
        
        # Get pattern target
        pattern_target = pattern_context.get('take_profit', pattern_context.get('target'))
        
        # Find structural targets
        target_candidates = []
        
        for level in structural_levels:
            if direction == "BUY" and level.level_type == "RESISTANCE":
                if level.level_price > entry_price:
                    # Target resistance with buffer
                    target_price = level.level_price - self.level_buffer_pips
                    distance = target_price - entry_price
                    score = level.strength * (1 + level.test_count * 0.1)
                    target_candidates.append((target_price, distance, score))
            
            elif direction == "SELL" and level.level_type == "SUPPORT":
                if level.level_price < entry_price:
                    # Target support with buffer
                    target_price = level.level_price + self.level_buffer_pips
                    distance = entry_price - target_price
                    score = level.strength * (1 + level.test_count * 0.1)
                    target_candidates.append((target_price, distance, score))
        
        # Sort by distance (closer targets first)
        target_candidates.sort(key=lambda x: x[1])
        
        # Create partial targets
        if target_candidates:
            # First target: 50% at nearest resistance/support
            if len(target_candidates) >= 1:
                tp_levels.append((target_candidates[0][0], 0.5))
            
            # Second target: 30% at second level or pattern target
            if len(target_candidates) >= 2:
                tp_levels.append((target_candidates[1][0], 0.3))
                final_target = target_candidates[1][0]
            elif pattern_target:
                tp_levels.append((pattern_target, 0.3))
                final_target = pattern_target
            else:
                # Use 2:1 R/R as fallback
                if direction == "BUY":
                    fallback_target = entry_price + (abs(entry_price - target_candidates[0][0]) * 2)
                else:
                    fallback_target = entry_price - (abs(target_candidates[0][0] - entry_price) * 2)
                tp_levels.append((fallback_target, 0.3))
                final_target = fallback_target
            
            # Final target: remaining 20% at extended target
            if len(target_candidates) >= 3:
                tp_levels.append((target_candidates[2][0], 0.2))
                final_target = target_candidates[2][0]
            
            tp_type = TakeProfitType.STRUCTURAL
        
        elif pattern_target:
            # Use pattern target with partial fills
            tp_levels.append((pattern_target, 0.7))  # 70% at pattern target
            
            # Add extended target
            if direction == "BUY":
                extended_target = pattern_target + (abs(pattern_target - entry_price) * 0.5)
            else:
                extended_target = pattern_target - (abs(entry_price - pattern_target) * 0.5)
            
            tp_levels.append((extended_target, 0.3))
            final_target = extended_target
            tp_type = TakeProfitType.PATTERN_TARGET
        
        else:
            # Fallback to R/R based targets
            atr_value = pattern_context.get('atr', 20.0)
            
            if direction == "BUY":
                target_1 = entry_price + (atr_value * 2)   # 2 ATR
                target_2 = entry_price + (atr_value * 3.5) # 3.5 ATR
            else:
                target_1 = entry_price - (atr_value * 2)
                target_2 = entry_price - (atr_value * 3.5)
            
            tp_levels = [(target_1, 0.6), (target_2, 0.4)]
            final_target = target_2
            tp_type = TakeProfitType.ATR_MULTIPLE
        
        return tp_levels, tp_type, final_target
    
    def create_trade_risk(
        self,
        trade_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        position_size: float,
        pattern_context: Dict[str, Any],
        market_structure: Dict[str, Any]
    ) -> TradeRisk:
        """
        Create comprehensive risk management for a new trade.
        
        Args:
            trade_id: Unique trade identifier
            symbol: Trading symbol
            direction: "BUY" or "SELL"
            entry_price: Entry price
            position_size: Position size
            pattern_context: Pattern information
            market_structure: Market structure data
            
        Returns:
            Complete TradeRisk object
        """
        
        # Calculate risk parameters
        risk_params = self.calculate_structural_stops(
            entry_price, direction, pattern_context, market_structure
        )
        
        # Get structural levels
        structural_levels = self._identify_structural_levels(
            entry_price, direction, market_structure
        )
        
        # Create trade risk object
        trade_risk = TradeRisk(
            trade_id=trade_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            position_size=position_size,
            risk_params=risk_params,
            structural_levels=structural_levels,
            is_active=True,
            in_profit=False,
            breakeven_hit=False,
            partial_fills=[],
            unrealized_pnl=0.0,
            max_favorable_excursion=0.0,
            max_adverse_excursion=0.0,
            last_update_time=datetime.now(timezone.utc).isoformat(),
            update_count=0
        )
        
        # Store in active trades
        self.active_trades[trade_id] = trade_risk
        
        logger.info(
            f"[RISK] Created trade risk for {trade_id}: "
            f"SL={risk_params.stop_loss_price:.2f}, "
            f"TP={risk_params.final_target:.2f}, "
            f"R/R={risk_params.risk_reward_ratio:.2f}"
        )
        
        return trade_risk
    
    def update_trade_risk(
        self,
        trade_id: str,
        current_price: float,
        market_structure: Optional[Dict[str, Any]] = None
    ) -> Optional[TradeRisk]:
        """
        Update trade risk management based on current market conditions.
        
        Args:
            trade_id: Trade identifier
            current_price: Current market price
            market_structure: Updated market structure data
            
        Returns:
            Updated TradeRisk object or None if not found
        """
        
        if trade_id not in self.active_trades:
            return None
        
        trade_risk = self.active_trades[trade_id]
        
        # Update PnL and excursions
        self._update_pnl_metrics(trade_risk, current_price)
        
        # Check for breakeven trigger
        self._check_breakeven_trigger(trade_risk, current_price)
        
        # Update trailing stop
        self._update_trailing_stop(trade_risk, current_price)
        
        # Check for structural adjustments
        if market_structure:
            self._check_structural_adjustments(trade_risk, current_price, market_structure)
        
        # Update timestamps
        trade_risk.last_update_time = datetime.now(timezone.utc).isoformat()
        trade_risk.update_count += 1
        
        return trade_risk
    
    def _update_pnl_metrics(self, trade_risk: TradeRisk, current_price: float):
        """Update PnL and excursion metrics."""
        
        if trade_risk.direction == "BUY":
            unrealized_pnl = (current_price - trade_risk.entry_price) * trade_risk.position_size
            excursion = current_price - trade_risk.entry_price
        else:
            unrealized_pnl = (trade_risk.entry_price - current_price) * trade_risk.position_size
            excursion = trade_risk.entry_price - current_price
        
        trade_risk.unrealized_pnl = unrealized_pnl
        trade_risk.in_profit = unrealized_pnl > 0
        
        # Update excursions
        if excursion > 0:  # Favorable move
            trade_risk.max_favorable_excursion = max(
                trade_risk.max_favorable_excursion, excursion
            )
        else:  # Adverse move
            trade_risk.max_adverse_excursion = min(
                trade_risk.max_adverse_excursion, excursion
            )
    
    def _check_breakeven_trigger(self, trade_risk: TradeRisk, current_price: float):
        """Check if trade should move to breakeven."""
        
        if trade_risk.breakeven_hit or not trade_risk.risk_params.breakeven_trigger:
            return
        
        risk_params = trade_risk.risk_params
        
        if trade_risk.direction == "BUY":
            if current_price >= risk_params.breakeven_trigger:
                # Move stop to breakeven (entry + small buffer)
                new_stop = trade_risk.entry_price + 2.0  # 2 pips buffer
                if new_stop > risk_params.stop_loss_price:
                    self._adjust_stop_loss(
                        trade_risk, new_stop, RiskAdjustmentReason.PROFIT_PROTECTION
                    )
                    trade_risk.breakeven_hit = True
        else:
            if current_price <= risk_params.breakeven_trigger:
                new_stop = trade_risk.entry_price - 2.0  # 2 pips buffer
                if new_stop < risk_params.stop_loss_price:
                    self._adjust_stop_loss(
                        trade_risk, new_stop, RiskAdjustmentReason.PROFIT_PROTECTION
                    )
                    trade_risk.breakeven_hit = True
    
    def _update_trailing_stop(self, trade_risk: TradeRisk, current_price: float):
        """Update trailing stop mechanism."""
        
        risk_params = trade_risk.risk_params
        
        # Check if trailing should activate
        if not risk_params.trailing_active and trade_risk.in_profit:
            current_rr = risk_params.calculate_current_risk_reward(current_price, trade_risk.direction)
            
            if current_rr >= self.trailing_start_rr:
                risk_params.trailing_active = True
                risk_params.trailing_trigger = current_price
                logger.info(f"[RISK] Trailing activated for {trade_risk.trade_id} at {current_price}")
        
        # Update trailing stop if active
        if risk_params.trailing_active and risk_params.trailing_trigger:
            
            if trade_risk.direction == "BUY":
                # Price moved favorably from trailing trigger
                favorable_move = current_price - risk_params.trailing_trigger
                if favorable_move > 0:
                    # Trail stop up by percentage of favorable move
                    trail_amount = favorable_move * self.trailing_step
                    new_stop = risk_params.stop_loss_price + trail_amount
                    
                    # Only move stop up (never down)
                    if new_stop > risk_params.stop_loss_price:
                        self._adjust_stop_loss(
                            trade_risk, new_stop, RiskAdjustmentReason.PROFIT_PROTECTION
                        )
                        risk_params.trailing_trigger = current_price  # Update trailing reference
            
            else:  # SELL
                favorable_move = risk_params.trailing_trigger - current_price
                if favorable_move > 0:
                    trail_amount = favorable_move * self.trailing_step
                    new_stop = risk_params.stop_loss_price - trail_amount
                    
                    # Only move stop down (never up)
                    if new_stop < risk_params.stop_loss_price:
                        self._adjust_stop_loss(
                            trade_risk, new_stop, RiskAdjustmentReason.PROFIT_PROTECTION
                        )
                        risk_params.trailing_trigger = current_price
    
    def _check_structural_adjustments(
        self,
        trade_risk: TradeRisk,
        current_price: float,
        market_structure: Dict[str, Any]
    ):
        """Check for structural-based risk adjustments."""
        
        # Update structural levels
        new_levels = self._identify_structural_levels(
            current_price, trade_risk.direction, market_structure
        )
        
        # Check for new significant levels
        significant_new_levels = [
            level for level in new_levels
            if level.strength > 0.7 and not any(
                abs(level.level_price - existing.level_price) < 5.0
                for existing in trade_risk.structural_levels
            )
        ]
        
        if significant_new_levels:
            # Evaluate if adjustment is beneficial
            best_new_level = max(significant_new_levels, key=lambda x: x.strength)
            
            if trade_risk.direction == "BUY":
                # New support level below current price
                if (best_new_level.level_type in ["SUPPORT", "LIQUIDITY"] and
                    best_new_level.level_price < current_price and
                    best_new_level.level_price > trade_risk.risk_params.stop_loss_price):
                    
                    new_stop = best_new_level.level_price - self.level_buffer_pips
                    self._adjust_stop_loss(
                        trade_risk, new_stop, RiskAdjustmentReason.STRUCTURE_BREAK
                    )
            
            else:  # SELL
                # New resistance level above current price
                if (best_new_level.level_type in ["RESISTANCE", "LIQUIDITY"] and
                    best_new_level.level_price > current_price and
                    best_new_level.level_price < trade_risk.risk_params.stop_loss_price):
                    
                    new_stop = best_new_level.level_price + self.level_buffer_pips
                    self._adjust_stop_loss(
                        trade_risk, new_stop, RiskAdjustmentReason.STRUCTURE_BREAK
                    )
            
            # Add new levels to tracking
            trade_risk.structural_levels.extend(significant_new_levels)
    
    def _adjust_stop_loss(
        self,
        trade_risk: TradeRisk,
        new_stop_price: float,
        reason: RiskAdjustmentReason
    ):
        """Adjust stop loss with proper tracking."""
        
        old_stop = trade_risk.risk_params.stop_loss_price
        old_distance = trade_risk.risk_params.current_stop_distance
        
        # Update stop loss
        trade_risk.risk_params.stop_loss_price = new_stop_price
        
        if trade_risk.direction == "BUY":
            new_distance = trade_risk.entry_price - new_stop_price
        else:
            new_distance = new_stop_price - trade_risk.entry_price
        
        trade_risk.risk_params.current_stop_distance = new_distance
        
        # Calculate impact
        risk_change_pct = (new_distance - old_distance) / old_distance * 100
        
        # Create adjustment record
        adjustment = RiskAdjustment(
            adjustment_id=f"{trade_risk.trade_id}_{len(trade_risk.risk_params.adjustment_history)}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            old_stop_loss=old_stop,
            new_stop_loss=new_stop_price,
            old_take_profit=trade_risk.risk_params.final_target,
            new_take_profit=trade_risk.risk_params.final_target,  # TP unchanged
            trigger_price=0.0,  # Current price when adjusted
            market_conditions={},
            confidence=0.8,
            risk_change_pct=risk_change_pct,
            reward_change_pct=0.0,
            expected_improvement=max(0, -risk_change_pct * 0.1)  # Risk reduction is good
        )
        
        trade_risk.risk_params.adjustment_history.append(asdict(adjustment))
        trade_risk.risk_params.last_adjustment_time = adjustment.timestamp
        
        self.adjustment_history.append(adjustment)
        self.performance_metrics['total_adjustments'] += 1
        
        logger.info(
            f"[RISK] Adjusted SL for {trade_risk.trade_id}: "
            f"{old_stop:.2f} → {new_stop_price:.2f} "
            f"(Risk change: {risk_change_pct:+.1f}%)"
        )
    
    def check_partial_profit_triggers(
        self,
        trade_risk: TradeRisk,
        current_price: float
    ) -> List[Dict[str, Any]]:
        """Check if any partial profit levels should be triggered."""
        
        triggered_partials = []
        
        for i, (tp_price, partial_size) in enumerate(trade_risk.risk_params.take_profit_levels):
            
            # Skip if already filled
            partial_id = f"TP_{i+1}"
            if any(fill['partial_id'] == partial_id for fill in trade_risk.partial_fills):
                continue
            
            # Check if trigger hit
            triggered = False
            if trade_risk.direction == "BUY" and current_price >= tp_price:
                triggered = True
            elif trade_risk.direction == "SELL" and current_price <= tp_price:
                triggered = True
            
            if triggered:
                partial_fill = {
                    'partial_id': partial_id,
                    'target_price': tp_price,
                    'fill_price': current_price,
                    'size_fraction': partial_size,
                    'fill_time': datetime.now(timezone.utc).isoformat(),
                    'pnl': self._calculate_partial_pnl(
                        trade_risk.entry_price, current_price, 
                        partial_size, trade_risk.direction
                    )
                }
                
                trade_risk.partial_fills.append(partial_fill)
                triggered_partials.append(partial_fill)
                
                logger.info(
                    f"[RISK] Partial TP triggered for {trade_risk.trade_id}: "
                    f"{partial_size*100:.0f}% at {current_price:.2f}"
                )
        
        return triggered_partials
    
    def _calculate_partial_pnl(
        self,
        entry_price: float,
        exit_price: float,
        size_fraction: float,
        direction: str
    ) -> float:
        """Calculate PnL for partial fill."""
        
        if direction == "BUY":
            pnl_per_unit = exit_price - entry_price
        else:
            pnl_per_unit = entry_price - exit_price
        
        return pnl_per_unit * size_fraction
    
    def get_active_trade_summary(self) -> Dict[str, Any]:
        """Get summary of all active trade risks."""
        
        total_trades = len(self.active_trades)
        profitable_trades = sum(1 for trade in self.active_trades.values() if trade.in_profit)
        
        total_unrealized = sum(trade.unrealized_pnl for trade in self.active_trades.values())
        
        # Risk distribution
        risk_levels = []
        for trade in self.active_trades.values():
            risk_pct = trade.risk_params.position_risk_pct
            risk_levels.append(risk_pct)
        
        avg_risk = np.mean(risk_levels) if risk_levels else 0.0
        max_risk = max(risk_levels) if risk_levels else 0.0
        
        # Trailing status
        trailing_active = sum(1 for trade in self.active_trades.values() 
                            if trade.risk_params.trailing_active)
        
        breakeven_hit = sum(1 for trade in self.active_trades.values() 
                           if trade.breakeven_hit)
        
        return {
            "total_active_trades": total_trades,
            "profitable_trades": profitable_trades,
            "profit_ratio": profitable_trades / total_trades if total_trades > 0 else 0.0,
            "total_unrealized_pnl": total_unrealized,
            "average_risk_pct": avg_risk,
            "maximum_risk_pct": max_risk,
            "trailing_active_count": trailing_active,
            "breakeven_hit_count": breakeven_hit,
            "total_adjustments": self.performance_metrics['total_adjustments'],
            "adjustment_success_rate": self.performance_metrics.get('profitable_adjustments', 0) / max(1, self.performance_metrics['total_adjustments'])
        }
    
    def close_trade_risk(self, trade_id: str, exit_price: float, exit_reason: str) -> Optional[Dict[str, Any]]:
        """Close trade risk management and calculate final metrics."""
        
        if trade_id not in self.active_trades:
            return None
        
        trade_risk = self.active_trades.pop(trade_id)
        
        # Calculate final PnL
        if trade_risk.direction == "BUY":
            final_pnl = (exit_price - trade_risk.entry_price) * trade_risk.position_size
        else:
            final_pnl = (trade_risk.entry_price - exit_price) * trade_risk.position_size
        
        # Calculate metrics
        total_partials_pnl = sum(fill['pnl'] for fill in trade_risk.partial_fills)
        
        final_metrics = {
            "trade_id": trade_id,
            "final_pnl": final_pnl,
            "partial_profits": total_partials_pnl,
            "total_pnl": final_pnl + total_partials_pnl,
            "max_favorable_excursion": trade_risk.max_favorable_excursion,
            "max_adverse_excursion": trade_risk.max_adverse_excursion,
            "exit_reason": exit_reason,
            "exit_time": datetime.now(timezone.utc).isoformat(),
            "total_adjustments": len(trade_risk.risk_params.adjustment_history),
            "breakeven_achieved": trade_risk.breakeven_hit,
            "trailing_used": trade_risk.risk_params.trailing_active,
            "partial_fills": len(trade_risk.partial_fills),
            "initial_risk_reward": trade_risk.risk_params.risk_reward_ratio,
            "risk_reduction": (
                trade_risk.risk_params.initial_stop_distance - 
                trade_risk.risk_params.current_stop_distance
            ) / trade_risk.risk_params.initial_stop_distance * 100
        }
        
        logger.info(
            f"[RISK] Closed trade {trade_id}: "
            f"PnL={final_pnl:+.2f}, "
            f"Adjustments={final_metrics['total_adjustments']}, "
            f"Risk Reduction={final_metrics['risk_reduction']:+.1f}%"
        )
        
        return final_metrics
    
    def get_risk_manager_performance(self) -> Dict[str, Any]:
        """Get overall risk manager performance metrics."""
        
        return {
            "total_trades_managed": len(self.adjustment_history) // 2,  # Rough estimate
            "total_adjustments": self.performance_metrics['total_adjustments'],
            "average_risk_reduction": self.performance_metrics.get('avg_risk_reduction', 0.0),
            "average_reward_improvement": self.performance_metrics.get('avg_reward_improvement', 0.0),
            "adjustment_success_rate": self.performance_metrics.get('profitable_adjustments', 0) / max(1, self.performance_metrics['total_adjustments']),
            "current_active_trades": len(self.active_trades),
            "trailing_utilization": sum(1 for t in self.active_trades.values() if t.risk_params.trailing_active) / max(1, len(self.active_trades)),
            "breakeven_achievement": sum(1 for t in self.active_trades.values() if t.breakeven_hit) / max(1, len(self.active_trades))
        }


# Global singleton instance
_structural_risk_manager = None

def get_structural_risk_manager() -> StructuralRiskManager:
    """Get or create singleton structural risk manager instance."""
    global _structural_risk_manager
    if _structural_risk_manager is None:
        _structural_risk_manager = StructuralRiskManager()
    return _structural_risk_manager