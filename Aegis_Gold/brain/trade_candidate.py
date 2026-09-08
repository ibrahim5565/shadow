"""
TradeCandidate dataclass, TradeClass enum, and SIGNAL_TYPES for Aegis-Gold v6.0.

This module defines the canonical candidate structure produced by all 5 paths
(PATH_0 through PATH_4) and consumed by the CandidateRankingEngine and the
Canonical Authorization Builder.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class TradeClass(Enum):
    """Two trade classes defined by the v6.0 architecture."""
    MACRO_CONTINUATION = "MACRO_CONTINUATION"
    SMALL_PATTERN = "SMALL_PATTERN"


SIGNAL_TYPES: List[str] = [
    "MACRO_CONTINUATION",   # H4/H1 aligned, M5 pullback entry
    "MACRO_REVERSAL",       # Macro shift + structural trigger
    "SMALL_BREAKOUT",       # M5/M1 local breakout
    "SMALL_RETEST",         # Post-breakout retest entry
    "LIQUIDITY_SWEEP",      # Sweep + reclaim
    "OB_REACTION",          # Order block bounce
    "FVG_REACTION",         # Fair value gap fill
    "MICRO_BOS",            # M1 break of structure
    "MICRO_CHOCH",          # M1 change of character
    "PATTERN_CONTINUATION", # Classic pattern continuation
    "SMC_STRUCTURAL",       # BOS/CHoCH confirmed
]


@dataclass
class TradeCandidate:
    """A single trade candidate produced by any of the 5 paths."""
    symbol: str
    direction: str            # "BUY" | "SELL"
    signal_type: str          # e.g. "MACRO_CONTINUATION", "SMALL_BREAKOUT"
    source_path: str          # "PATH_0" through "PATH_4"
    macro_bias: str           # "STRONG_BULLISH" | "BULLISH" | "NEUTRAL" | "BEARISH" | "STRONG_BEARISH"
    macro_score: float        # 0.0–1.0
    setup_score: float        # 0.0–1.0
    trigger_score: float      # 0.0–1.0
    quant_score: float        # 0.0–1.0
    ml_score: float           # 0.0–1.0
    pattern_score: float      # 0.0–1.0
    expected_value: float     # USD
    risk_reward: float        # e.g. 2.1
    spread_cost: float        # USD
    entry_price: float
    stop_loss: float
    take_profit: float
    sl_points: int
    tp_points: int
    lot: float
    confidence: float         # 0.0–1.0
    timestamp: str            # ISO
    data_timestamp: str       # Timestamp of last candle used
    causal_valid: bool = True
    risk_valid: bool = True
    final_score: float = 0.0  # Computed composite
    wait_reason: str = ""     # Set if this candidate is rejected
    trade_class: str = ""     # TradeClass value, derived

    def __post_init__(self):
        """Derive trade_class from signal_type."""
        if not self.trade_class:
            if self.signal_type in ("MACRO_CONTINUATION", "MACRO_REVERSAL"):
                self.trade_class = TradeClass.MACRO_CONTINUATION.value
            else:
                self.trade_class = TradeClass.SMALL_PATTERN.value

    def signal_hash(self) -> str:
        """Deterministic hash for anti-duplicate detection."""
        import hashlib
        raw = f"{self.symbol}|{self.direction}|{self.signal_type}|{self.entry_price:.2f}|{self.stop_loss:.2f}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Serialize for logging / diagnostics."""
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "signal_type": self.signal_type,
            "source_path": self.source_path,
            "macro_bias": self.macro_bias,
            "macro_score": self.macro_score,
            "setup_score": self.setup_score,
            "trigger_score": self.trigger_score,
            "quant_score": self.quant_score,
            "ml_score": self.ml_score,
            "pattern_score": self.pattern_score,
            "expected_value": self.expected_value,
            "risk_reward": self.risk_reward,
            "spread_cost": self.spread_cost,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "sl_points": self.sl_points,
            "tp_points": self.tp_points,
            "lot": self.lot,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "data_timestamp": self.data_timestamp,
            "causal_valid": self.causal_valid,
            "risk_valid": self.risk_valid,
            "final_score": self.final_score,
            "wait_reason": self.wait_reason,
            "trade_class": self.trade_class,
        }