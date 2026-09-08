"""
Aegis Gold — Canonical Domain Contracts & Opportunity Pipeline Types
Zero-confidence architecture: trades are defined and authorized by market patterns,
structural validation, and quantitative economic viability.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


@dataclass(frozen=True)
class PatternCandidate:
    """Canonical pattern representation from KRNOS, SMC, or multi-timeframe engines."""
    pattern_id: str                   # e.g., "KRNOS_EXPANSION_BULL_20260825_143000"
    engine_source: str                # "KRNOS", "SMC", "STRUCTURE"
    timeframe: str                    # "M1", "M5", "M15", "H1", "H4"
    direction: str                    # "BUY" or "SELL"
    pattern_type: str                 # "BOS", "CHoCH", "ORDER_BLOCK", "LIQUIDITY_SWEEP", "FVG", "EXPANSION", "BREAKOUT_RETEST"
    structure_context: str            # "TREND_CONTINUATION", "REVERSAL", "PULLBACK", "RANGE_BOUND"
    invalidation_level: float         # Structural invalidation price
    entry_zone_low: float             # Lower bound of entry zone
    entry_zone_high: float            # Upper bound of entry zone
    expected_path: List[float] = field(default_factory=list) # Projected price trajectory from Kronos
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expiry_bars: int = 12             # Lifetime of pattern before obsolescence
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EntryOpportunity:
    """Validated entry location and structural trigger."""
    opportunity_id: str
    pattern: PatternCandidate
    symbol: str
    direction: str
    entry_price: float
    structural_sl_price: float
    structural_sl_points: int
    trigger_type: str                 # "M1_CHoCH", "M1_SWEEP_REVERSAL", "M5_OB_REACTION", "M1_ENGULFING"
    trigger_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    entry_zone_valid: bool = True
    reason: str = ""


@dataclass(frozen=True)
class NewsRegimeState:
    """Fundamental news regime classification."""
    regime: str                       # "NORMAL", "PRE_NEWS", "NEWS_SHOCK", "POST_NEWS", "STABILIZATION"
    current_event: Optional[str] = None
    minutes_to_next_event: Optional[int] = None
    minutes_since_last_event: Optional[int] = None
    spread_multiplier_tolerance: float = 1.5
    trading_allowed: bool = True
    cooldown_active: bool = False
    reason: str = "Market normal"


@dataclass(frozen=True)
class QuantPlan:
    """Quantitative economic validation plan targeting $3.00–$4.00 profit per trade."""
    opportunity_id: str
    symbol: str
    direction: str
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    sl_points: int
    tp_points: int
    target_usd: float                 # Target dollar profit (default $3.50, range $3.00-$4.00)
    risk_usd: float                   # Dollar risk on trade
    risk_reward_ratio: float          # Realized R:R ratio
    lot_size: float                   # Calculated lot size
    atr_points: float                 # Current ATR in points
    spread_cost_usd: float            # Spread cost in dollars
    expected_move_points: float       # Expected move based on structural target & Kronos
    target_is_economically_realistic: bool
    expected_value_usd: float         # Mathematical expectancy
    rejection_reason: str = ""


@dataclass(frozen=True)
class TradeAuthorization:
    """
    Single canonical trade authorization contract.
    MT5 Gateway execution MUST reject any order request without a valid instance.
    """
    authorized: bool
    authorization_id: str
    opportunity_id: str
    pattern_id: str
    symbol: str
    direction: str                    # "BUY" or "SELL"
    lot: float
    entry_price: float
    stop_loss: float
    take_profit: float
    target_usd: float
    risk_usd: float
    sl_points: int
    tp_points: int
    news_regime: str
    local_ai_context: Dict[str, Any]  # Contextual metadata only (cannot veto or upgrade)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reason: str = ""
    rejection_code: str = ""
    source_path: str = "PATH_0"          # Which path generated this
    signal_type: str = "UNKNOWN"         # Signal type enum
    macro_bias: str = "NEUTRAL"          # Macro context
    authorization_version: str = "v2.0"  # Version tracking
    causal_validity: bool = True          # Timestamp assertion result
    data_timestamp: str = ""             # Last candle timestamp used
