"""
===========================================================================
AEGIS GOLD — Opportunity Engine (Phase L)
===========================================================================

PURPOSE:
--------
Comprehensive opportunity evaluation system that calculates opportunity quality,
expected move, remaining move, and expected value (EV) for every pattern.

CORE FEATURES:
--------------
1. Opportunity Quality Assessment - Multi-dimensional scoring (0-100)
2. Expected Move Calculation - Statistical target estimation
3. Remaining Move Analysis - How much potential is left
4. EV Analysis - Risk-adjusted expected value calculation
5. Opportunity Ranking - Compare multiple opportunities
6. Real-time Opportunity Tracking - Live opportunity updates

INTEGRATION:
------------
- Uses Pattern Memory (Phase J) for historical edge calculations
- Integrates with 7 AI Engines (Phase K) for consensus signals  
- Leverages MTF Analysis (Phase E) for confluence scoring
- Applies Pattern Quality Gates (Phase C) for validation
- Incorporates Causality Enforcement (Phase I) for temporal integrity

===========================================================================
"""

import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger("aegis.opportunity")


class OpportunityGrade(Enum):
    """Opportunity quality grades."""
    EXCELLENT = "EXCELLENT"    # 85-100: Exceptional opportunity
    GOOD = "GOOD"             # 70-84: Strong opportunity  
    FAIR = "FAIR"             # 55-69: Acceptable opportunity
    POOR = "POOR"             # 40-54: Marginal opportunity
    REJECTED = "REJECTED"     # 0-39: Below threshold


@dataclass
class OpportunityMetrics:
    """Core opportunity measurement metrics."""
    
    # Quality Assessment (0-100)
    overall_quality_score: float
    structure_quality: float        # Pattern structural strength
    confluence_quality: float       # Multi-timeframe alignment
    timing_quality: float          # Entry timing precision
    risk_quality: float            # Risk/reward profile
    
    # Move Analysis
    total_expected_move: float      # Full pattern target (points)
    remaining_move: float          # Points left to target
    move_completion_pct: float      # How much has already moved
    
    # Expected Value Analysis  
    win_probability: float          # Historical win rate
    expected_r: float              # Expected R multiple
    kelly_fraction: float          # Kelly criterion position size
    expected_pnl_per_unit: float   # Expected PnL per unit risk
    
    # Risk Assessment
    max_risk_points: float         # Stop loss distance
    risk_reward_ratio: float       # Target/Stop ratio
    max_drawdown_risk: float       # Expected adverse excursion
    breakeven_probability: float   # Chance of avoiding loss
    
    # Market Context
    market_regime_edge: float      # Edge in current regime
    volatility_adjustment: float   # Vol-adjusted expectations
    session_edge: float           # Session-specific edge
    news_risk_factor: float       # News event proximity penalty


@dataclass 
class OpportunityAssessment:
    """Complete opportunity evaluation result."""
    
    # Identification
    opportunity_id: str
    symbol: str
    pattern_type: str
    direction: str
    
    # Core Metrics
    metrics: OpportunityMetrics
    
    # Grading
    grade: OpportunityGrade
    is_tradeable: bool
    rejection_reasons: List[str]
    
    # Execution Details
    optimal_entry_price: float
    entry_window_start: float
    entry_window_end: float
    stop_loss_price: float
    take_profit_price: float
    
    # Timing
    detection_time: str
    expiration_time: str
    urgency_level: str             # "IMMEDIATE", "PATIENT", "EXPIRING"
    
    # Context
    supporting_factors: List[str]
    risk_factors: List[str]
    confidence_level: float        # AI consensus confidence
    
    # Performance Tracking
    historical_edge: Dict[str, float]  # Win rate, avg R, etc.
    similar_patterns: int              # Pattern memory sample size
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/transmission."""
        result = asdict(self)
        result['metrics'] = asdict(self.metrics)
        result['grade'] = self.grade.value
        return result


class OpportunityEngine:
    """
    Core opportunity evaluation and ranking engine.
    """
    
    def __init__(self):
        # Quality thresholds
        self.min_tradeable_score = 55.0
        self.excellent_threshold = 85.0
        self.good_threshold = 70.0
        self.fair_threshold = 55.0
        
        # Risk parameters
        self.max_risk_per_trade = 0.02  # 2% account risk
        self.min_rr_ratio = 1.5
        self.max_drawdown_tolerance = 0.15  # 15% max drawdown
        
        # Opportunity tracking
        self.active_opportunities = {}
        self.opportunity_history = []
        
        logger.info("[OPPORTUNITY] Engine initialized")
    
    def _generate_opportunity_id(
        self,
        pattern_context: Dict[str, Any],
        market_snapshot
    ) -> str:
        """
        Generate a unique opportunity ID from pattern context and market snapshot.
        """
        symbol = pattern_context.get('symbol', 'XAUUSD')
        pattern_type = pattern_context.get('pattern_type', 'UNKNOWN')
        direction = pattern_context.get('direction', 'UNKNOWN')
        ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S%f')
        
        return f"{symbol}_{pattern_type}_{direction}_{ts}"
    
    def evaluate_opportunity(
        self,
        pattern_context: Dict[str, Any],
        market_snapshot,
        ai_consensus_result: Optional[Dict] = None
    ) -> OpportunityAssessment:
        """
        Comprehensive opportunity evaluation for a detected pattern.
        
        Args:
            pattern_context: Pattern details (type, scale, levels, etc.)
            market_snapshot: Current market state and data
            ai_consensus_result: Result from 7-engine consensus
            
        Returns:
            OpportunityAssessment with complete evaluation
        """
        opportunity_id = self._generate_opportunity_id(pattern_context, market_snapshot)
        
        logger.info(f"[OPPORTUNITY] Evaluating {opportunity_id}")
        
        # Calculate core metrics
        metrics = self._calculate_opportunity_metrics(
            pattern_context, market_snapshot, ai_consensus_result
        )
        
        # Determine grade and tradeability
        grade = self._assign_opportunity_grade(metrics.overall_quality_score)
        is_tradeable, rejection_reasons = self._assess_tradeability(metrics, pattern_context)
        
        # Calculate execution parameters
        execution_params = self._calculate_execution_parameters(
            pattern_context, metrics, market_snapshot
        )
        
        # Get historical performance context
        historical_context = self._get_historical_context(pattern_context)
        
        # Determine urgency and timing
        urgency_level = self._assess_urgency(pattern_context, metrics)
        
        # Build supporting/risk factors
        supporting_factors = self._identify_supporting_factors(metrics, pattern_context)
        risk_factors = self._identify_risk_factors(metrics, pattern_context)
        
        # Create assessment
        assessment = OpportunityAssessment(
            opportunity_id=opportunity_id,
            symbol=pattern_context.get('symbol', 'XAUUSD'),
            pattern_type=pattern_context.get('pattern_type', 'UNKNOWN'),
            direction=pattern_context.get('direction', 'UNKNOWN'),
            metrics=metrics,
            grade=grade,
            is_tradeable=is_tradeable,
            rejection_reasons=rejection_reasons,
            optimal_entry_price=execution_params['optimal_entry'],
            entry_window_start=execution_params['window_start'],
            entry_window_end=execution_params['window_end'],
            stop_loss_price=execution_params['stop_loss'],
            take_profit_price=execution_params['take_profit'],
            detection_time=datetime.now(timezone.utc).isoformat(),
            expiration_time=self._calculate_expiration_time(pattern_context).isoformat(),
            urgency_level=urgency_level,
            supporting_factors=supporting_factors,
            risk_factors=risk_factors,
            confidence_level=ai_consensus_result.get('final_confidence', 0.5) if ai_consensus_result else 0.5,
            historical_edge=historical_context['edge_metrics'],
            similar_patterns=historical_context['sample_size']
        )
        
        # Store for tracking
        self.active_opportunities[opportunity_id] = assessment
        
        logger.info(
            f"[OPPORTUNITY] {opportunity_id}: {grade.value} "
            f"(Quality={metrics.overall_quality_score:.1f}, "
            f"E(R)={metrics.expected_r:.2f}, Tradeable={is_tradeable})"
        )
        
        return assessment
    
    def _calculate_opportunity_metrics(
        self,
        pattern_context: Dict[str, Any], 
        market_snapshot,
        ai_consensus: Optional[Dict] = None
    ) -> OpportunityMetrics:
        """Calculate comprehensive opportunity metrics."""
        
        # Extract key pattern data
        current_price = market_snapshot.current_price or pattern_context.get('current_price', 0.0)
        entry_price = pattern_context.get('entry_price', current_price)
        stop_loss = pattern_context.get('stop_loss', 0.0)
        take_profit = pattern_context.get('take_profit', 0.0)
        direction = pattern_context.get('direction', 'BUY')
        
        # Calculate distance metrics
        if direction == "BUY":
            risk_points = abs(entry_price - stop_loss)
            reward_points = abs(take_profit - entry_price)
            remaining_points = abs(take_profit - current_price) if current_price < take_profit else 0.0
        else:  # SELL
            risk_points = abs(stop_loss - entry_price)
            reward_points = abs(entry_price - take_profit)
            remaining_points = abs(current_price - take_profit) if current_price > take_profit else 0.0
        
        total_expected_move = reward_points
        move_completion_pct = max(0.0, (total_expected_move - remaining_points) / total_expected_move * 100) if total_expected_move > 0 else 0.0
        
        # Risk/Reward calculation
        rr_ratio = reward_points / risk_points if risk_points > 0 else 0.0
        
        # Get historical edge from pattern memory
        historical_edge = self._get_pattern_memory_edge(pattern_context)
        win_probability = historical_edge.get('win_rate', 0.6) / 100.0
        expected_r = historical_edge.get('expected_r', rr_ratio * win_probability - (1 - win_probability))
        
        # Kelly fraction calculation
        if win_probability > 0 and rr_ratio > 0:
            kelly_fraction = max(0.0, min(0.25, (win_probability * rr_ratio - (1 - win_probability)) / rr_ratio))
        else:
            kelly_fraction = 0.0
        
        # Expected PnL per unit risk
        expected_pnl_per_unit = expected_r  # In R multiples
        
        # Quality assessments (0-100)
        structure_quality = self._assess_structure_quality(pattern_context)
        confluence_quality = self._assess_confluence_quality(pattern_context, market_snapshot)  
        timing_quality = self._assess_timing_quality(pattern_context, market_snapshot)
        risk_quality = self._assess_risk_quality(rr_ratio, risk_points, expected_r)
        
        # Overall quality (weighted average)
        quality_weights = {
            'structure': 0.30,
            'confluence': 0.25, 
            'timing': 0.25,
            'risk': 0.20
        }
        overall_quality = (
            structure_quality * quality_weights['structure'] +
            confluence_quality * quality_weights['confluence'] +
            timing_quality * quality_weights['timing'] +
            risk_quality * quality_weights['risk']
        )
        
        # Market context adjustments
        regime_edge = self._calculate_regime_edge(pattern_context, market_snapshot)
        volatility_adj = self._calculate_volatility_adjustment(market_snapshot)
        session_edge = self._calculate_session_edge(pattern_context, market_snapshot)
        news_risk = self._calculate_news_risk_factor(market_snapshot)
        
        # Risk assessments
        max_drawdown_risk = historical_edge.get('avg_max_adverse_r', 0.5)
        breakeven_prob = win_probability * 0.8 + 0.1  # Approximation
        
        return OpportunityMetrics(
            overall_quality_score=overall_quality,
            structure_quality=structure_quality,
            confluence_quality=confluence_quality,
            timing_quality=timing_quality,
            risk_quality=risk_quality,
            total_expected_move=total_expected_move,
            remaining_move=remaining_points,
            move_completion_pct=move_completion_pct,
            win_probability=win_probability,
            expected_r=expected_r,
            kelly_fraction=kelly_fraction,
            expected_pnl_per_unit=expected_pnl_per_unit,
            max_risk_points=risk_points,
            risk_reward_ratio=rr_ratio,
            max_drawdown_risk=max_drawdown_risk,
            breakeven_probability=breakeven_prob,
            market_regime_edge=regime_edge,
            volatility_adjustment=volatility_adj,
            session_edge=session_edge,
            news_risk_factor=news_risk
        )
    
    def _get_pattern_memory_edge(self, pattern_context: Dict[str, Any]) -> Dict[str, float]:
        """Get historical edge metrics from pattern memory system."""
        try:
            from brain.pattern_memory_system import get_pattern_memory_system
            
            memory_system = get_pattern_memory_system()
            stats = memory_system.get_pattern_statistics(
                pattern_type=pattern_context.get('pattern_type'),
                scale=pattern_context.get('scale'),
                direction=pattern_context.get('direction'),
                regime=pattern_context.get('regime')
            )
            
            if stats.get('sample_size', 0) >= 5:
                return {
                    'win_rate': stats.get('win_rate', 60.0),
                    'expected_r': stats.get('expected_r', 0.5),
                    'avg_max_adverse_r': 0.3,  # Placeholder
                    'sample_size': stats.get('sample_size', 0)
                }
            else:
                # Fallback to pattern outcome tracker
                return self._get_outcome_tracker_edge(pattern_context)
                
        except ImportError:
            return self._get_outcome_tracker_edge(pattern_context)
        except Exception as e:
            logger.warning(f"[OPPORTUNITY] Pattern memory error: {e}")
            return self._get_default_edge_metrics()
    
    def _get_outcome_tracker_edge(self, pattern_context: Dict[str, Any]) -> Dict[str, float]:
        """Get edge metrics from pattern outcome tracker."""
        try:
            from brain.pattern_outcome_tracker import PatternOutcomeTracker
            
            tracker = PatternOutcomeTracker()
            edge_stats = tracker.calculate_historical_edge(
                pattern_type=pattern_context.get('pattern_type'),
                scale=pattern_context.get('scale'),
                regime=pattern_context.get('regime'),
                min_sample_size=3
            )
            
            if edge_stats.get('sufficient_data', False):
                return {
                    'win_rate': edge_stats.get('win_rate', 60.0),
                    'expected_r': edge_stats.get('expected_r', 0.5),
                    'avg_max_adverse_r': edge_stats.get('avg_max_drawdown_r', 0.3),
                    'sample_size': edge_stats.get('sample_size', 0)
                }
            else:
                return self._get_default_edge_metrics()
                
        except Exception as e:
            logger.warning(f"[OPPORTUNITY] Outcome tracker error: {e}")
            return self._get_default_edge_metrics()
    
    def _get_default_edge_metrics(self) -> Dict[str, float]:
        """Default edge metrics when no historical data available."""
        return {
            'win_rate': 60.0,
            'expected_r': 0.5,
            'avg_max_adverse_r': 0.4,
            'sample_size': 0
        }
    
    def _assess_structure_quality(self, pattern_context: Dict[str, Any]) -> float:
        """Assess the structural quality of the pattern (0-100)."""
        score = 50.0  # Base score
        
        # Pattern type quality
        pattern_type = pattern_context.get('pattern_type', '')
        high_quality_patterns = ['BOS_BULLISH', 'BOS_BEARISH', 'CHOCH_BULLISH', 'CHOCH_BEARISH']
        if any(hq in pattern_type for hq in high_quality_patterns):
            score += 15.0
        
        # Structure strength
        structure_strength = pattern_context.get('structure_strength', 0.5)
        score += structure_strength * 25.0  # 0-25 points
        
        # Order block presence
        if pattern_context.get('ob_present', False):
            score += 10.0
        
        # Liquidity sweep
        if pattern_context.get('liquidity_swept', False):
            score += 10.0
        
        # Fair value gap
        if pattern_context.get('fvg_present', False):
            score += 5.0
        
        return min(100.0, max(0.0, score))
    
    def _assess_confluence_quality(self, pattern_context: Dict[str, Any], market_snapshot) -> float:
        """Assess multi-timeframe and confluence quality (0-100).""" 
        score = 30.0  # Base score
        
        # MTF alignment
        mtf_alignment = pattern_context.get('mtf_alignment', 0.5)
        score += mtf_alignment * 40.0  # 0-40 points
        
        # HTF bias confirmation
        htf_bias = pattern_context.get('htf_bias', 'NEUTRAL')
        if htf_bias != 'NEUTRAL':
            score += 15.0
        
        # Regime compatibility
        regime = pattern_context.get('regime', 'UNKNOWN')
        direction = pattern_context.get('direction', 'BUY')
        if (regime == 'TRENDING_UP' and direction == 'BUY') or \
           (regime == 'TRENDING_DOWN' and direction == 'SELL'):
            score += 10.0
        
        # Session alignment
        session = getattr(market_snapshot, 'session', 'UNKNOWN')
        favorable_sessions = ['LONDON', 'NY', 'OVERLAP']
        if session in favorable_sessions:
            score += 5.0
        
        return min(100.0, max(0.0, score))
    
    def _assess_timing_quality(self, pattern_context: Dict[str, Any], market_snapshot) -> float:
        """Assess entry timing quality (0-100)."""
        score = 40.0  # Base score
        
        # Pattern freshness
        detection_time = pattern_context.get('detection_time')
        if detection_time:
            try:
                detected_at = datetime.fromisoformat(detection_time.replace('Z', '+00:00'))
                age_minutes = (datetime.now(timezone.utc) - detected_at).total_seconds() / 60
                if age_minutes < 5:
                    score += 20.0  # Fresh pattern
                elif age_minutes < 15:
                    score += 10.0  # Recent pattern  
                elif age_minutes > 60:
                    score -= 15.0  # Stale pattern
            except:
                pass
        
        # Entry window position
        move_completion = pattern_context.get('move_completion_pct', 0.0)
        if move_completion < 20.0:
            score += 20.0  # Early in move
        elif move_completion < 50.0:
            score += 10.0  # Mid move
        elif move_completion > 80.0:
            score -= 20.0  # Late in move
        
        # Formation speed (faster = better timing)
        formation_speed = pattern_context.get('formation_speed', 0.5)
        if formation_speed > 0.7:
            score += 10.0
        elif formation_speed < 0.3:
            score -= 5.0
        
        # News/volatility timing
        try:
            vol_level = getattr(market_snapshot, 'volatility_level', 'NORMAL')
            if vol_level == 'HIGH':
                score -= 10.0  # High vol = poor timing
            elif vol_level == 'LOW':
                score += 5.0   # Low vol = good timing
        except:
            pass
        
        return min(100.0, max(0.0, score))
    
    def _assess_risk_quality(self, rr_ratio: float, risk_points: float, expected_r: float) -> float:
        """Assess risk/reward profile quality (0-100)."""
        score = 20.0  # Base score
        
        # Risk/Reward ratio scoring
        if rr_ratio >= 3.0:
            score += 30.0
        elif rr_ratio >= 2.0:
            score += 20.0
        elif rr_ratio >= 1.5:
            score += 10.0
        elif rr_ratio < 1.0:
            score -= 30.0
        
        # Expected R scoring
        if expected_r >= 1.0:
            score += 25.0
        elif expected_r >= 0.5:
            score += 15.0
        elif expected_r >= 0.0:
            score += 5.0
        else:
            score -= 20.0
        
        # Risk size appropriateness
        if risk_points > 0:
            if 20 <= risk_points <= 100:  # Appropriate for XAUUSD
                score += 15.0
            elif risk_points < 10 or risk_points > 200:
                score -= 15.0
        
        # Bonus for excellent risk management
        if rr_ratio >= 2.5 and expected_r >= 0.8:
            score += 10.0
        
        return min(100.0, max(0.0, score))
    
    def _calculate_regime_edge(self, pattern_context: Dict[str, Any], market_snapshot) -> float:
        """Calculate edge based on current market regime."""
        try:
            regime = pattern_context.get('regime', 'UNKNOWN')
            direction = pattern_context.get('direction', 'BUY')
            
            # Regime-direction compatibility matrix
            regime_edges = {
                ('TRENDING_UP', 'BUY'): 0.15,
                ('TRENDING_DOWN', 'SELL'): 0.15,
                ('RANGING', 'BUY'): -0.05,
                ('RANGING', 'SELL'): -0.05,
                ('MEAN_REVERTING', 'BUY'): -0.10,
                ('MEAN_REVERTING', 'SELL'): -0.10
            }
            
            return regime_edges.get((regime, direction), 0.0)
            
        except Exception as e:
            logger.warning(f"[OPPORTUNITY] Regime edge calculation error: {e}")
            return 0.0
    
    def _calculate_volatility_adjustment(self, market_snapshot) -> float:
        """Calculate volatility-based adjustment factor."""
        try:
            volatility = getattr(market_snapshot, 'volatility_level', 'NORMAL')
            
            adjustments = {
                'VERY_LOW': -0.05,   # Poor for breakouts
                'LOW': 0.02,         # Good for precise entries
                'NORMAL': 0.05,      # Optimal conditions
                'HIGH': 0.00,        # Neutral - can go either way
                'VERY_HIGH': -0.10   # Dangerous conditions
            }
            
            return adjustments.get(volatility, 0.0)
            
        except Exception:
            return 0.0
    
    def _calculate_session_edge(self, pattern_context: Dict[str, Any], market_snapshot) -> float:
        """Calculate session-based edge adjustment."""
        try:
            session = getattr(market_snapshot, 'session', 'UNKNOWN')
            
            # Session edge based on XAUUSD behavior
            session_edges = {
                'LONDON': 0.08,      # High activity, good for breakouts
                'NY': 0.10,          # Highest volume, best execution
                'OVERLAP': 0.12,     # Peak liquidity
                'ASIA': -0.02,       # Lower volume, choppier
                'UNKNOWN': 0.00
            }
            
            return session_edges.get(session, 0.0)
            
        except Exception:
            return 0.0
    
    def _calculate_news_risk_factor(self, market_snapshot) -> float:
        """Calculate news event risk penalty."""
        try:
            # Check for upcoming high-impact news
            news_risk = getattr(market_snapshot, 'news_risk_level', 'LOW')
            
            risk_factors = {
                'NONE': 0.0,
                'LOW': -0.02,
                'MEDIUM': -0.08,
                'HIGH': -0.20,       # Major news event nearby
                'EXTREME': -0.50     # NFP, FOMC, etc.
            }
            
            return risk_factors.get(news_risk, 0.0)
            
        except Exception:
            return 0.0
    def _assign_opportunity_grade(self, quality_score: float) -> OpportunityGrade:
        """Assign letter grade based on quality score."""
        if quality_score >= self.excellent_threshold:
            return OpportunityGrade.EXCELLENT
        elif quality_score >= self.good_threshold:
            return OpportunityGrade.GOOD
        elif quality_score >= self.fair_threshold:
            return OpportunityGrade.FAIR
        elif quality_score >= 40.0:
            return OpportunityGrade.POOR
        else:
            return OpportunityGrade.REJECTED
    
    def _assess_tradeability(
        self, 
        metrics: OpportunityMetrics, 
        pattern_context: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Assess whether opportunity meets minimum trading criteria."""
        rejection_reasons = []
        
        # Quality threshold
        if metrics.overall_quality_score < self.min_tradeable_score:
            rejection_reasons.append(f"Quality too low ({metrics.overall_quality_score:.1f} < {self.min_tradeable_score})")
        
        # Risk/Reward ratio
        if metrics.risk_reward_ratio < self.min_rr_ratio:
            rejection_reasons.append(f"R:R too low ({metrics.risk_reward_ratio:.2f} < {self.min_rr_ratio})")
        
        # Expected value
        if metrics.expected_r <= 0:
            rejection_reasons.append(f"Negative expected R ({metrics.expected_r:.2f})")
        
        # Remaining move check
        if metrics.move_completion_pct > 90:
            rejection_reasons.append(f"Pattern too mature ({metrics.move_completion_pct:.1f}% complete)")
        
        # Risk size validation
        if metrics.max_risk_points <= 0:
            rejection_reasons.append("Invalid stop loss distance")
        
        # News risk check
        if metrics.news_risk_factor < -0.15:
            rejection_reasons.append("High news risk nearby")
        
        # Kelly fraction sanity check
        if metrics.kelly_fraction <= 0:
            rejection_reasons.append("Kelly criterion suggests no position")
        
        # Win probability minimum
        if metrics.win_probability < 0.45:
            rejection_reasons.append(f"Win probability too low ({metrics.win_probability:.1%})")
        
        is_tradeable = len(rejection_reasons) == 0
        return is_tradeable, rejection_reasons
    
    def _calculate_execution_parameters(
        self,
        pattern_context: Dict[str, Any],
        metrics: OpportunityMetrics, 
        market_snapshot
    ) -> Dict[str, float]:
        """Calculate optimal execution parameters."""
        current_price = market_snapshot.current_price or pattern_context.get('current_price', 0.0)
        direction = pattern_context.get('direction', 'BUY')
        
        # Base levels from pattern
        entry_price = pattern_context.get('entry_price', current_price)
        stop_loss = pattern_context.get('stop_loss', entry_price)
        take_profit = pattern_context.get('take_profit', entry_price)
        
        # Calculate entry window based on pattern scale
        scale = pattern_context.get('scale', 'MEDIUM')
        scale_multipliers = {'SMALL': 0.5, 'MEDIUM': 1.0, 'LARGE': 1.5}
        window_size = 10.0 * scale_multipliers.get(scale, 1.0)  # Points
        
        if direction == "BUY":
            optimal_entry = entry_price
            window_start = entry_price - window_size * 0.3  # Allow some chase
            window_end = entry_price + window_size * 0.7    # Limit chase
        else:  # SELL
            optimal_entry = entry_price
            window_start = entry_price + window_size * 0.3  # Allow some chase  
            window_end = entry_price - window_size * 0.7    # Limit chase
        
        return {
            'optimal_entry': optimal_entry,
            'window_start': window_start,
            'window_end': window_end,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
    
    def _calculate_expiration_time(self, pattern_context: Dict[str, Any]) -> datetime:
        """Calculate when opportunity expires."""
        base_time = datetime.now(timezone.utc)
        
        # Expiration based on pattern scale
        scale = pattern_context.get('scale', 'MEDIUM')
        expiration_minutes = {
            'SMALL': 15,    # Quick patterns expire fast
            'MEDIUM': 60,   # Standard expiration
            'LARGE': 240    # Large patterns have longer windows
        }
        
        minutes = expiration_minutes.get(scale, 60)
        return base_time + timedelta(minutes=minutes)
    
    def _assess_urgency(self, pattern_context: Dict[str, Any], metrics: OpportunityMetrics) -> str:
        """Assess entry urgency level."""
        # High urgency conditions
        if metrics.timing_quality > 85 and metrics.move_completion_pct < 10:
            return "IMMEDIATE"
        
        # Medium urgency
        if metrics.move_completion_pct < 30 and metrics.timing_quality > 60:
            return "PATIENT"
        
        # Low urgency (pattern aging)
        if metrics.move_completion_pct > 50 or metrics.timing_quality < 40:
            return "EXPIRING"
        
        return "PATIENT"
    
    def _identify_supporting_factors(
        self, 
        metrics: OpportunityMetrics, 
        pattern_context: Dict[str, Any]
    ) -> List[str]:
        """Identify positive factors supporting the opportunity."""
        factors = []
        
        if metrics.structure_quality > 80:
            factors.append("Strong structural pattern")
        
        if metrics.confluence_quality > 75:
            factors.append("High multi-timeframe confluence")
        
        if metrics.risk_reward_ratio >= 2.5:
            factors.append(f"Excellent R:R ({metrics.risk_reward_ratio:.1f}:1)")
        
        if metrics.expected_r > 1.0:
            factors.append(f"Positive expected R ({metrics.expected_r:.2f})")
        
        if metrics.win_probability > 0.7:
            factors.append(f"High win probability ({metrics.win_probability:.1%})")
        
        if metrics.session_edge > 0.05:
            factors.append("Favorable trading session")
        
        if metrics.market_regime_edge > 0.1:
            factors.append("Regime supports direction")
        
        if pattern_context.get('ob_present'):
            factors.append("Order block confirmation")
        
        if pattern_context.get('liquidity_swept'):
            factors.append("Liquidity sweep present")
        
        return factors
    
    def _identify_risk_factors(
        self, 
        metrics: OpportunityMetrics, 
        pattern_context: Dict[str, Any]
    ) -> List[str]:
        """Identify risk factors that could impact the opportunity."""
        factors = []
        
        if metrics.move_completion_pct > 70:
            factors.append(f"Pattern {metrics.move_completion_pct:.0f}% complete")
        
        if metrics.max_drawdown_risk > 0.4:
            factors.append("High drawdown risk")
        
        if metrics.news_risk_factor < -0.1:
            factors.append("High-impact news nearby")
        
        if metrics.volatility_adjustment < -0.05:
            factors.append("Unfavorable volatility conditions")
        
        if metrics.win_probability < 0.55:
            factors.append("Below-average historical performance")
        
        if metrics.timing_quality < 50:
            factors.append("Suboptimal entry timing")
        
        if metrics.remaining_move < metrics.max_risk_points:
            factors.append("Limited remaining upside")
        
        return factors
    
    def _get_historical_context(self, pattern_context: Dict[str, Any]) -> Dict[str, Any]:
        """Get historical performance context for similar patterns."""
        edge_metrics = self._get_pattern_memory_edge(pattern_context)
        
        return {
            'edge_metrics': edge_metrics,
            'sample_size': edge_metrics.get('sample_size', 0),
            'confidence_level': min(1.0, edge_metrics.get('sample_size', 0) / 20.0)
        }
    
    def update_opportunity(self, opportunity_id: str, current_price: float) -> Optional[OpportunityAssessment]:
        """Update an existing opportunity with current market conditions."""
        if opportunity_id not in self.active_opportunities:
            return None
        
        opportunity = self.active_opportunities[opportunity_id]
        
        # Work on a copy so callers retain the previously-stored assessment
        import copy
        updated = copy.deepcopy(opportunity)
        
        # Recalculate remaining move
        direction = updated.direction
        take_profit = updated.take_profit_price
        
        if direction == "BUY":
            remaining_points = max(0.0, take_profit - current_price)
        else:
            remaining_points = max(0.0, current_price - take_profit)
        
        # Update metrics
        updated.metrics.remaining_move = remaining_points
        updated.metrics.move_completion_pct = (
            (updated.metrics.total_expected_move - remaining_points) / 
            updated.metrics.total_expected_move * 100
        ) if updated.metrics.total_expected_move > 0 else 100.0
        
        # Check if expired
        expiration = datetime.fromisoformat(updated.expiration_time.replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > expiration:
            updated.urgency_level = "EXPIRED"
            updated.is_tradeable = False
            updated.rejection_reasons.append("Opportunity expired")
        
        # Replace stored assessment with the updated copy
        self.active_opportunities[opportunity_id] = updated
        
        return updated
    
    def rank_opportunities(self, opportunities: List[OpportunityAssessment]) -> List[OpportunityAssessment]:
        """Rank opportunities by quality and potential."""
        def opportunity_score(opp: OpportunityAssessment) -> float:
            if not opp.is_tradeable:
                return -1.0
            
            # Multi-factor scoring
            quality_score = opp.metrics.overall_quality_score / 100.0
            ev_score = max(0.0, opp.metrics.expected_r) / 2.0  # Normalize to ~0.5 max
            urgency_bonus = {"IMMEDIATE": 0.2, "PATIENT": 0.1, "EXPIRING": -0.1}.get(opp.urgency_level, 0.0)
            
            return quality_score + ev_score + urgency_bonus
        
        return sorted(opportunities, key=opportunity_score, reverse=True)
    
    def get_opportunity_summary(self) -> Dict[str, Any]:
        """Get summary of all active opportunities."""
        active_opps = [opp for opp in self.active_opportunities.values() if opp.is_tradeable]
        
        if not active_opps:
            return {
                "active_count": 0,
                "tradeable_count": 0,
                "best_opportunity": None,
                "avg_quality": 0.0,
                "total_expected_r": 0.0
            }
        
        tradeable_opps = [opp for opp in active_opps if opp.is_tradeable]
        best_opp = max(tradeable_opps, key=lambda x: x.metrics.overall_quality_score) if tradeable_opps else None
        
        return {
            "active_count": len(self.active_opportunities),
            "tradeable_count": len(tradeable_opps),
            "best_opportunity": best_opp.opportunity_id if best_opp else None,
            "avg_quality": sum(opp.metrics.overall_quality_score for opp in tradeable_opps) / len(tradeable_opps) if tradeable_opps else 0.0,
            "total_expected_r": sum(opp.metrics.expected_r for opp in tradeable_opps),
            "grading_distribution": {
                grade.value: len([opp for opp in active_opps if opp.grade == grade])
                for grade in OpportunityGrade
            }
        }


# Global singleton instance
_opportunity_engine = None

def get_opportunity_engine() -> OpportunityEngine:
    """Get or create singleton opportunity engine instance."""
    global _opportunity_engine
    if _opportunity_engine is None:
        _opportunity_engine = OpportunityEngine()
    return _opportunity_engine