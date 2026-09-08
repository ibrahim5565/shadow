"""
===========================================================================
AEGIS GOLD — Engine Vote Contract (Pattern Consensus Architecture)
===========================================================================

TEMPORAL INTEGRITY RULE (non-negotiable):
  At decision time T:
    Allowed:   data.timestamp <= T
    Forbidden: data.timestamp > T

Every engine must expose:
    engine.predict_vote(snapshot: FrozenDecisionSnapshot) -> EngineVote

The EngineVote.pattern_evidence MUST include a confirmation_time for every
confirmed pattern. Any vote with confirmation_time > snapshot.timestamp is
silently discarded by the Unified Brain fusion layer — this is the primary
leakage detection mechanism.

Pattern confirmation rules:
  Swing high/low      — candles AFTER pivot have closed (no look-ahead)
  Order Block         — displacement candle(s) after OB have closed
  Fair Value Gap      — 3rd candle of 3-candle pattern has closed
  Liquidity Sweep     — wick closed AND price has reacted (not mid-wick)
  BOS / CHoCH         — breaking candle has closed beyond prior structure
  Kronos forecast     — generated from data <= T; scored ex-ante, not confirmed by future
===========================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional, Any


# ---------------------------------------------------------------------------
# PricePoint — a single forecasted price at a future bar
# ---------------------------------------------------------------------------

@dataclass
class PricePoint:
    """One step in a forecasted price path (Kronos-style)."""
    bar_offset: int          # Bars ahead from decision time (1 = next bar)
    price_mean: float        # Expected price at this step
    price_std: float         # Standard deviation (uncertainty band)
    timestamp: Optional[datetime] = None  # Estimated wall-clock time if known


# ---------------------------------------------------------------------------
# PatternEvidence — what pattern triggered a vote and WHEN it was confirmed
# ---------------------------------------------------------------------------

@dataclass
class PatternEvidence:
    """
    Records the confirmed pattern(s) that produced an EngineVote.

    MANDATORY fields for leakage audit:
      - pattern_type:       human-readable name of the pattern
      - confirmation_time:  the timestamp of the CLOSING candle that
                            makes this pattern unambiguously real.
                            Must be <= snapshot.timestamp.
      - formation_time:     when the pattern started forming (informational)
      - invalidation_level: price that proves this prediction wrong
    """
    pattern_type: str                     # e.g. "CHoCH_BULLISH", "FVG_BULLISH", "KRONOS_FORECAST"
    confirmation_time: datetime           # SIGNAL_TIME = CONFIRMATION_TIME, never earlier
    formation_time: Optional[datetime] = None  # When pattern started forming
    invalidation_level: float = 0.0       # Price that invalidates this pattern
    confidence_raw: float = 0.0           # Engine's internal raw confidence (0-1)
    details: List[str] = field(default_factory=list)  # Human-readable evidence trail
    extra: Dict[str, Any] = field(default_factory=dict)  # Engine-specific metadata

    def is_valid_at(self, decision_time: datetime) -> bool:
        """
        Returns True if this pattern evidence was available at decision_time.
        Leakage check: confirmation_time must be <= decision_time.
        """
        # Handle both tz-aware and tz-naive datetimes safely
        ct = self.confirmation_time
        dt = decision_time
        if ct.tzinfo is None and dt.tzinfo is not None:
            ct = ct.replace(tzinfo=timezone.utc)
        elif ct.tzinfo is not None and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return ct <= dt


# ---------------------------------------------------------------------------
# EngineVote — what every engine must return
# ---------------------------------------------------------------------------

@dataclass
class EngineVote:
    """
    Standardized output contract for each of the 7 engines.

    Fields
    ------
    engine_name:        Identifying string (e.g. "smc", "kronos", "ml_ensemble")
    direction:          "BUY", "SELL", or "WAIT"
    conviction:         Engine's own certainty [0, 1]. NOT a generic confidence %.
                        Each engine defines conviction in terms of its own pattern
                        strength (e.g. SMC uses score/100, Kronos uses |prob_up - 0.5|*2).
    predicted_path:     Kronos-style forecasted price path; None for most engines.
    pattern_evidence:   List of confirmed patterns that triggered this vote.
                        Every PatternEvidence item must have confirmation_time <= T.
    proposed_sl:        Pattern-derived stop-loss price (absolute price, not points).
                        0.0 means engine has no SL opinion (e.g. QFE regime engine).
    proposed_tp:        Pattern-derived take-profit price.
                        0.0 means engine has no TP opinion.
    invalidation_level: The price level that proves this prediction wrong.
    signal_time:        When this vote was generated (should equal snapshot.timestamp).
    error:              Non-empty if engine failed; vote direction is forced to "WAIT".
    """
    engine_name: str
    direction: Literal["BUY", "SELL", "WAIT"]
    conviction: float                              # 0.0 to 1.0
    pattern_evidence: List[PatternEvidence] = field(default_factory=list)
    proposed_sl: float = 0.0                       # Absolute price level
    proposed_tp: float = 0.0                       # Absolute price level
    invalidation_level: float = 0.0
    predicted_path: Optional[List[PricePoint]] = None
    signal_time: Optional[datetime] = None
    error: str = ""

    # ── Convenience helpers ─────────────────────────────────────────────────

    def is_directional(self) -> bool:
        """True if this engine is casting a directional vote (not WAIT)."""
        return self.direction in ("BUY", "SELL") and not self.error

    def leakage_check(self, decision_time: datetime) -> List[str]:
        """
        Returns a list of leakage violations found in pattern_evidence.
        An empty list means this vote passes the temporal integrity check.
        """
        violations = []
        for ev in self.pattern_evidence:
            if not ev.is_valid_at(decision_time):
                violations.append(
                    f"[LEAKAGE] {self.engine_name}: pattern '{ev.pattern_type}' "
                    f"confirmation_time={ev.confirmation_time} > decision_time={decision_time}"
                )
        return violations

    def strongest_evidence(self) -> Optional[PatternEvidence]:
        """Returns the highest-confidence PatternEvidence item."""
        if not self.pattern_evidence:
            return None
        return max(self.pattern_evidence, key=lambda e: e.confidence_raw)

    def to_dict(self) -> Dict[str, Any]:
        """Serializable summary for logging."""
        return {
            "engine": self.engine_name,
            "direction": self.direction,
            "conviction": round(self.conviction, 4),
            "proposed_sl": self.proposed_sl,
            "proposed_tp": self.proposed_tp,
            "invalidation_level": self.invalidation_level,
            "signal_time": self.signal_time.isoformat() if self.signal_time else None,
            "patterns": [
                {
                    "type": ev.pattern_type,
                    "confirmation_time": ev.confirmation_time.isoformat(),
                    "confidence": ev.confidence_raw,
                    "invalidation": ev.invalidation_level,
                }
                for ev in self.pattern_evidence
            ],
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# WAIT vote factory — used by engines that cannot form a confident signal
# ---------------------------------------------------------------------------

def make_wait_vote(engine_name: str, reason: str = "", signal_time: Optional[datetime] = None) -> EngineVote:
    """Returns a correctly-formed WAIT vote with an empty pattern_evidence list."""
    return EngineVote(
        engine_name=engine_name,
        direction="WAIT",
        conviction=0.0,
        pattern_evidence=[],
        proposed_sl=0.0,
        proposed_tp=0.0,
        invalidation_level=0.0,
        signal_time=signal_time or datetime.now(timezone.utc),
        error=reason,
    )
