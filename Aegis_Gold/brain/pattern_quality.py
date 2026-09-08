"""
AEGIS GOLD — Pattern Quality Evaluation System

Replaces arbitrary confidence thresholds with multi-factor pattern quality assessment.

Philosophy:
-----------
A pattern should be traded based on:
1. Structural strength (clear BOS/CHoCH/OB/liquidity)
2. Historical edge (pattern memory shows positive expectancy)
3. Multi-timeframe alignment (HTF supports the pattern)
4. Engine consensus (7 AI engines agree on direction)
5. Entry quality (entry is early, not chasing)
6. Remaining move (sufficient movement left to capture)
7. Target validity (structural target exists)
8. Expected value (EV > 0 after all costs)

NOT based on:
- Arbitrary confidence >= X thresholds
- Single model probability
- Indicator crossovers

"""

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

logger = logging.getLogger("aegis.pattern_quality")


@dataclass
class PatternQuality:
    """
    Multi-factor pattern quality assessment.
    
    All scores are 0.0 to 1.0 unless otherwise noted.
    """
    
    # Core structural assessment
    structure_strength: float      # 0.0-1.0: BOS/CHoCH/OB clarity
    pattern_type: str             # e.g., "BULLISH_BOS_OB_SWEEP"
    
    # Historical evidence
    historical_edge: float        # Expected R from pattern memory (can be negative)
    pattern_sample_size: int      # Number of historical instances
    
    # Multi-timeframe
    mtf_alignment: float          # 0.0-1.0: HTF agreement
    htf_bias: str                 # "bullish" | "bearish" | "neutral"
    
    # AI consensus
    engine_consensus: float       # 0.0-1.0: % of engines agreeing
    engines_agreeing: int         # Count of engines supporting direction
    engines_total: int            # Total engines evaluated
    
    # Entry timing
    entry_quality: float          # 0.0-1.0: Early=1.0, Late=0.3, Chase=0.0
    distance_from_origin: float   # Points from structural origin
    
    # Opportunity assessment
    expected_move_pts: float      # Forecasted move in points
    consumed_move_pts: float      # Already consumed movement
    remaining_move_pct: float     # % of expected move remaining (0.0-1.0)
    
    # Target validity
    target_validity: float        # 0.0-1.0: Structural target exists & clear
    target_distance_pts: float    # Points to target
    invalidation_distance_pts: float  # Points to invalidation
    rr_ratio: float               # Reward:Risk ratio
    
    # Economic viability
    expected_value_usd: float     # EV after spread/commission/slippage
    win_probability: float        # 0.0-1.0: Estimated from pattern memory + ML
    avg_win_r: float              # Average R on wins
    avg_loss_r: float             # Average R on losses
    
    # Regime compatibility
    regime_compatible: bool       # Pattern works in current regime
    regime_type: str             # Current regime
    
    # Veto flags
    vetoes: List[str]            # List of veto reasons (empty = no veto)
    
    def is_tradeable(self) -> bool:
        """
        Multi-gate pattern quality check.
        
        Returns True if pattern passes ALL quality gates.
        """
        
        # Hard vetoes
        if len(self.vetoes) > 0:
            return False
        
        # Gate 1: Structural strength
        if self.structure_strength < 0.60:
            return False
        
        # Gate 2: Historical edge (positive expected R)
        if self.historical_edge <= 0:
            return False
        
        # Gate 3: Expected value (positive after costs)
        if self.expected_value_usd <= 0:
            return False
        
        # Gate 4: Remaining move (at least 50% left)
        if self.remaining_move_pct < 0.50:
            return False
        
        # Gate 5: Entry quality (not chasing)
        if self.entry_quality < 0.30:
            return False
        
        # Gate 6: Target validity (R:R >= 1.5)
        if self.rr_ratio < 1.5:
            return False
        
        # Gate 7: Engine consensus (at least 60%)
        if self.engine_consensus < 0.60:
            return False
        
        # Gate 8: Regime compatibility
        if not self.regime_compatible:
            return False
        
        # Gate 9: Multi-timeframe alignment (NEW - Phase E)
        # At least 50% of timeframes must agree on direction
        if self.mtf_alignment < 0.50:
            return False
        
        # All gates passed
        return True
    
    def quality_score(self) -> float:
        """
        Composite quality score for ranking opportunities.
        
        Returns 0.0 to 1.0 (higher = better pattern).
        This is for RANKING, not gating.
        """
        
        # Weighted combination
        score = (
            self.structure_strength * 0.20 +
            min(1.0, max(0.0, self.historical_edge / 3.0)) * 0.20 +  # Normalize historical edge
            self.mtf_alignment * 0.15 +
            self.engine_consensus * 0.15 +
            self.entry_quality * 0.10 +
            self.remaining_move_pct * 0.10 +
            self.target_validity * 0.05 +
            (1.0 if self.expected_value_usd > 0 else 0.0) * 0.05
        )
        
        return min(1.0, max(0.0, score))
    
    def get_summary(self) -> str:
        """Human-readable summary for logging."""
        
        tradeable = "✓ TRADEABLE" if self.is_tradeable() else "✗ NOT TRADEABLE"
        quality = self.quality_score()
        
        summary = (
            f"{tradeable} | Quality={quality:.2f} | "
            f"Structure={self.structure_strength:.2f} Edge={self.historical_edge:.2f}R "
            f"MTF={self.mtf_alignment:.2f} Engines={self.engines_agreeing}/{self.engines_total} "
            f"Entry={self.entry_quality:.2f} Remaining={self.remaining_move_pct:.0%} "
            f"RR={self.rr_ratio:.1f} EV=${self.expected_value_usd:.2f}"
        )
        
        if self.vetoes:
            summary += f" | VETOES: {', '.join(self.vetoes)}"
        
        return summary


def evaluate_pattern_quality(
    pattern: Dict,
    engines: Dict[str, Dict],
    pattern_memory_stats: Optional[Dict],
    entry_analysis: Dict,
    forecast: Dict,
    ev_result: Dict,
    regime: str
) -> PatternQuality:
    """
    Evaluate complete pattern quality from all components.
    
    Args:
        pattern: Pattern detection result (from SMC/pattern engine)
        engines: Dict of engine votes {"smc": {...}, "kronos": {...}, etc}
        pattern_memory_stats: Historical pattern performance
        entry_analysis: Entry zone analysis result
        forecast: Future move forecast
        ev_result: Expected value calculation
        regime: Current regime type
        
    Returns:
        PatternQuality assessment
    """
    
    # 1. Structure strength (from pattern detector)
    structure_strength = pattern.get("structure_strength", pattern.get("confidence", 0.5))
    if isinstance(structure_strength, int):
        structure_strength = structure_strength / 100.0
    
    pattern_type = pattern.get("pattern_type", "UNKNOWN")
    
    # 2. Historical edge (from pattern memory)
    if pattern_memory_stats:
        historical_edge = pattern_memory_stats.get("expected_r", 0.0)
        sample_size = pattern_memory_stats.get("sample_size", 0)
    else:
        historical_edge = 0.0
        sample_size = 0
    
    # 3. Multi-timeframe alignment
    mtf_alignment = entry_analysis.get("mtf_alignment", 0.5)
    htf_bias = entry_analysis.get("htf_bias", "neutral")
    
    # 4. Engine consensus
    agreeing = 0
    total = 0
    for engine_name, engine_result in engines.items():
        if engine_result and engine_result.get("direction") == pattern.get("direction"):
            agreeing += 1
        total += 1
    
    engine_consensus = agreeing / total if total > 0 else 0.0
    
    # 5. Entry quality
    entry_quality = entry_analysis.get("entry_quality", 0.5)
    distance_from_origin = entry_analysis.get("distance_from_origin_pts", 0)
    
    # 6. Opportunity assessment
    expected_move = forecast.get("expected_move_pts", 0)
    consumed_move = forecast.get("consumed_move_pts", 0)
    remaining_pct = forecast.get("remaining_move_pct", 1.0)
    
    # 7. Target validity
    target_validity = entry_analysis.get("target_validity", 0.5)
    target_distance = entry_analysis.get("target_distance_pts", 0)
    invalidation_distance = entry_analysis.get("invalidation_distance_pts", 0)
    rr_ratio = target_distance / invalidation_distance if invalidation_distance > 0 else 0.0
    
    # 8. Economic viability
    expected_value = ev_result.get("ev_usd", 0.0)
    win_prob = ev_result.get("win_probability", 0.5)
    avg_win_r = pattern_memory_stats.get("avg_win_r", 2.0) if pattern_memory_stats else 2.0
    avg_loss_r = pattern_memory_stats.get("avg_loss_r", -1.0) if pattern_memory_stats else -1.0
    
    # 9. Regime compatibility
    pattern_regimes = pattern_memory_stats.get("compatible_regimes", []) if pattern_memory_stats else []
    regime_compatible = (len(pattern_regimes) == 0 or regime in pattern_regimes)
    
    # 10. Collect vetoes
    vetoes = []
    if structure_strength < 0.40:
        vetoes.append("WEAK_STRUCTURE")
    if remaining_pct < 0.30:
        vetoes.append("MOVE_CONSUMED")
    if entry_quality < 0.20:
        vetoes.append("CHASE")
    if rr_ratio < 1.0:
        vetoes.append("POOR_RR")
    if expected_value <= 0:
        vetoes.append("NEGATIVE_EV")
    
    return PatternQuality(
        structure_strength=structure_strength,
        pattern_type=pattern_type,
        historical_edge=historical_edge,
        pattern_sample_size=sample_size,
        mtf_alignment=mtf_alignment,
        htf_bias=htf_bias,
        engine_consensus=engine_consensus,
        engines_agreeing=agreeing,
        engines_total=total,
        entry_quality=entry_quality,
        distance_from_origin=distance_from_origin,
        expected_move_pts=expected_move,
        consumed_move_pts=consumed_move,
        remaining_move_pct=remaining_pct,
        target_validity=target_validity,
        target_distance_pts=target_distance,
        invalidation_distance_pts=invalidation_distance,
        rr_ratio=rr_ratio,
        expected_value_usd=expected_value,
        win_probability=win_prob,
        avg_win_r=avg_win_r,
        avg_loss_r=avg_loss_r,
        regime_compatible=regime_compatible,
        regime_type=regime,
        vetoes=vetoes
    )
