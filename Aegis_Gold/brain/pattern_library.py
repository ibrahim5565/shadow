"""
===========================================================================
AEGIS GOLD — Structural Pattern Library (Phase 1)
===========================================================================

PURPOSE:
  Defines the formal Pattern Library and dataclasses for market structure
  patterns (BOS, CHoCH, Order Block, Breaker, Liquidity Sweep, FVG, Retest, Displacement).

PHILOSOPHY:
  AEGIS GOLD operates as a PATTERN-FIRST system. High-quality market structure
  patterns drive trade opportunities. Standalone confidence scores (% thresholds)
  are completely eliminated as trade authorization gates.
===========================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import List, Optional, Dict, Any

logger = logging.getLogger("aegis.pattern_library")


class PatternCategory(Enum):
    SMC_STRUCTURE = auto()
    LIQUIDITY = auto()
    PRICE_ACTION = auto()


class PatternType(Enum):
    # SMC Structural Patterns
    BOS_BULLISH = "BOS_BULLISH"
    BOS_BEARISH = "BOS_BEARISH"
    CHOCH_BULLISH = "CHOCH_BULLISH"
    CHOCH_BEARISH = "CHOCH_BEARISH"
    ORDER_BLOCK_BULLISH = "ORDER_BLOCK_BULLISH"
    ORDER_BLOCK_BEARISH = "ORDER_BLOCK_BEARISH"
    BREAKER_BULLISH = "BREAKER_BULLISH"
    BREAKER_BEARISH = "BREAKER_BEARISH"
    
    # Liquidity Patterns
    LIQUIDITY_SWEEP_BULLISH = "LIQUIDITY_SWEEP_BULLISH"
    LIQUIDITY_SWEEP_BEARISH = "LIQUIDITY_SWEEP_BEARISH"
    FVG_CONTINUATION_BULLISH = "FVG_CONTINUATION_BULLISH"
    FVG_CONTINUATION_BEARISH = "FVG_CONTINUATION_BEARISH"
    
    # Trigger / Price Action Patterns
    RETEST_BULLISH = "RETEST_BULLISH"
    RETEST_BEARISH = "RETEST_BEARISH"
    DISPLACEMENT_BULLISH = "DISPLACEMENT_BULLISH"
    DISPLACEMENT_BEARISH = "DISPLACEMENT_BEARISH"
    ENGULFING_BULLISH = "ENGULFING_BULLISH"
    ENGULFING_BEARISH = "ENGULFING_BEARISH"


class PatternScale(Enum):
    SMALL = "SMALL"      # Intraday micro-structure (5-15 min horizon)
    MEDIUM = "MEDIUM"    # Intraday swing structure (15-60 min horizon)
    LARGE = "LARGE"      # Higher-timeframe structure (1-4+ hour horizon)


@dataclass
class FutureMoveForecast:
    """
    Causal Point-in-Time Prediction of Expected Future Price Movement (t <= T).
    """
    direction: str                     # "BUY", "SELL", or "NEUTRAL"
    expected_move_points: float        # Expected favorable move in points
    expected_move_R: float             # Expected reward in R-multiples
    probability_up: float              # Estimated probability of upward move
    probability_down: float            # Estimated probability of downward move
    probability_neutral: float         # Estimated probability of noise/flat
    expected_mfe: float                # Expected Maximum Favorable Excursion (pts)
    expected_mae: float                # Expected Maximum Adverse Excursion (pts)
    expected_time_to_target_sec: int   # Estimated duration to target (seconds)
    forecast_horizon: str              # "SHORT", "MEDIUM", "LONG"
    forecast_quality: float            # Informational quality score (0.0 to 10.0)


@dataclass
class StructuralPattern:
    """
    Immutable representation of an identified, closed-bar market structure pattern.
    """
    pattern_id: str
    pattern_type: PatternType
    category: PatternCategory
    direction: str                     # "BUY" or "SELL"
    symbol: str
    formation_time: datetime
    confirmation_time: datetime
    information_available_time: datetime
    price_level: float
    invalidation_level: float
    target_level: float
    strength_score: float              # 0.0 to 10.0 scale based on structural evidence
    pattern_scale: PatternScale = PatternScale.MEDIUM
    future_move_estimate: Optional[FutureMoveForecast] = None
    evidence_notes: List[str] = field(default_factory=list)
    expiry_time: Optional[datetime] = None

    def is_causal(self, decision_time: datetime) -> bool:
        """Verifies zero future leakage: information_available_time <= decision_time."""
        dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        iat = self.information_available_time if self.information_available_time.tzinfo else self.information_available_time.replace(tzinfo=timezone.utc)
        ct = self.confirmation_time if self.confirmation_time.tzinfo else self.confirmation_time.replace(tzinfo=timezone.utc)
        return iat <= dt and ct <= dt

    def is_expired(self, current_time: datetime) -> bool:
        if not self.expiry_time:
            return False
        ct = current_time if current_time.tzinfo else current_time.replace(tzinfo=timezone.utc)
        et = self.expiry_time if self.expiry_time.tzinfo else self.expiry_time.replace(tzinfo=timezone.utc)
        return ct > et

    def is_invalidated(self, current_price: float) -> bool:
        if self.direction == "BUY":
            return current_price <= self.invalidation_level
        elif self.direction == "SELL":
            return current_price >= self.invalidation_level
        return False


def get_pattern_strength_hierarchy(pattern_type: PatternType) -> int:
    """Returns integer rank (higher = stronger structural pattern)."""
    ranks = {
        PatternType.CHOCH_BULLISH: 10,
        PatternType.CHOCH_BEARISH: 10,
        PatternType.BOS_BULLISH: 8,
        PatternType.BOS_BEARISH: 8,
        PatternType.LIQUIDITY_SWEEP_BULLISH: 7,
        PatternType.LIQUIDITY_SWEEP_BEARISH: 7,
        PatternType.ORDER_BLOCK_BULLISH: 6,
        PatternType.ORDER_BLOCK_BEARISH: 6,
        PatternType.BREAKER_BULLISH: 6,
        PatternType.BREAKER_BEARISH: 6,
        PatternType.FVG_CONTINUATION_BULLISH: 5,
        PatternType.FVG_CONTINUATION_BEARISH: 5,
        PatternType.DISPLACEMENT_BULLISH: 4,
        PatternType.DISPLACEMENT_BEARISH: 4,
        PatternType.RETEST_BULLISH: 4,
        PatternType.RETEST_BEARISH: 4,
    }
    return ranks.get(pattern_type, 3)
