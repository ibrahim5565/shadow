"""
===========================================================================
AEGIS GOLD — Single Source of Truth for Trading Decisions
===========================================================================

TradingDecision is the ONLY authoritative object representing the current
trade decision. It implements a controlled state machine where every
transition is recorded and traceable.

DECISION OWNERSHIP RULE:
  A valid decision must never silently change.
  Every BUY/SELL -> WAIT transition MUST record:
    - rejection_reason
    - rejection_stage
    - previous_action
    - previous_confidence

STATE MACHINE:
  RAW -> VALIDATED -> CANDIDATE -> SELECTED -> FROZEN -> RISK_APPROVED
       -> EXECUTION_APPROVED -> EXECUTED
  Any state can transition to REJECTED (with reason) or WAIT.
===========================================================================
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aegis.trading_decision")


class DecisionStage(str, Enum):
    RAW = "RAW"
    VALIDATED = "VALIDATED"
    CANDIDATE = "CANDIDATE"
    SELECTED = "SELECTED"
    FROZEN = "FROZEN"
    RISK_APPROVED = "RISK_APPROVED"
    EXECUTION_APPROVED = "EXECUTION_APPROVED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    WAIT = "WAIT"


@dataclass(frozen=True)
class DecisionTransition:
    """A recorded state transition."""
    from_stage: str
    to_stage: str
    action: str
    confidence: float
    reason: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineSignal:
    """Standardized output from any engine participating in the decision."""
    engine: str
    action: str                    # "BUY", "SELL", "WAIT", "NEUTRAL"
    confidence: float              # 0.0 to 1.0
    timestamp: datetime
    valid: bool = True
    reason: str = ""
    features_hash: str = ""
    candle_timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketDecisionSnapshot:
    """
    Canonical market snapshot shared by ALL engines in one decision cycle.
    Ensures every engine analyzes the same point-in-time data.
    """
    symbol: str
    timeframe: str
    decision_timestamp: datetime
    last_closed_candle_timestamp: Optional[datetime] = None
    price: float = 0.0
    spread: float = 0.0
    point: float = 0.01
    session: str = "LONDON"
    features: Dict[str, Any] = field(default_factory=dict)
    feature_version: str = ""
    feature_hash: str = ""
    candles_m5: tuple = ()
    candles_m1: tuple = ()
    candles_h1: tuple = ()
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradingDecision:
    """
    Single authoritative trading decision object.

    All state transitions go through transition() which records the
    reason and stage. No silent mutation is allowed.
    """
    symbol: str
    action: str = "WAIT"           # BUY / SELL / WAIT
    direction: str = "NA"          # BUY / SELL / NA
    confidence: float = 0.0        # 0-100
    source: str = "UNKNOWN"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    candle_timestamp: Optional[datetime] = None
    cycle_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # Signal containers
    pattern_signal: Optional[Dict[str, Any]] = None
    consensus_signal: Optional[Dict[str, Any]] = None
    rl_signal: Optional[Dict[str, Any]] = None
    offline_rl_signal: Optional[Dict[str, Any]] = None
    ml_signal: Optional[Dict[str, Any]] = None
    quant_signal: Optional[Dict[str, Any]] = None
    omega_signal: Optional[Dict[str, Any]] = None
    kronos_signal: Optional[Dict[str, Any]] = None
    neural_signal: Optional[Dict[str, Any]] = None

    # Rejection tracking
    rejection_reason: Optional[str] = None
    rejection_stage: Optional[str] = None
    previous_action: Optional[str] = None
    previous_confidence: Optional[float] = None

    # State machine
    current_stage: str = DecisionStage.RAW.value
    transitions: List[DecisionTransition] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Execution details
    lot: float = 0.0
    sl_points: int = 0
    tp_points: int = 0
    rr_ratio: float = 0.0
    grade: str = "F"
    pattern: str = "NONE"
    regime: str = "NA"
    adx_val: float = 0.0
    rsi_val: float = 0.0
    atr_val: float = 0.0
    spread: float = 0.0
    session: str = "LONDON"
    thought_log: List[str] = field(default_factory=list)

    # ── State Machine ──────────────────────────────────────────────

    def transition(
        self,
        new_action: str,
        stage: str,
        reason: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "TradingDecision":
        """
        Controlled state transition. Records the change and reason.

        If the action changes from BUY/SELL to WAIT, the rejection
        reason and stage are automatically recorded.
        """
        old_action = self.action
        old_conf = self.confidence

        # Record rejection if BUY/SELL -> WAIT
        if old_action in ("BUY", "SELL") and new_action == "WAIT":
            self.rejection_reason = reason or "UNSPECIFIED_REJECTION"
            self.rejection_stage = stage
            self.previous_action = old_action
            self.previous_confidence = old_conf
            logger.info(
                "[DECISION_TRACE] symbol=%s cycle_id=%s stage=%s action=%s "
                "confidence=%.2f source=%s reason=%s previous_action=%s previous_confidence=%.2f",
                self.symbol, self.cycle_id, stage, new_action,
                confidence if confidence is not None else self.confidence,
                self.source, reason, old_action, old_conf,
            )

        # Record transition
        self.transitions.append(DecisionTransition(
            from_stage=self.current_stage,
            to_stage=stage,
            action=new_action,
            confidence=confidence if confidence is not None else self.confidence,
            reason=reason,
            metadata=metadata or {},
        ))

        # Apply changes
        self.action = new_action
        self.current_stage = stage
        if confidence is not None:
            self.confidence = confidence
        if reason:
            self.metadata[f"reason_{stage}"] = reason

        logger.info(
            "[DECISION_TRACE] symbol=%s cycle_id=%s stage=%s action=%s "
            "confidence=%.2f source=%s reason=%s",
            self.symbol, self.cycle_id, stage, new_action,
            self.confidence, self.source, reason,
        )

        return self

    def set_signal(self, engine: str, signal: EngineSignal) -> "TradingDecision":
        """Attach a standardized engine signal to the decision."""
        signal_dict = {
            "engine": signal.engine,
            "action": signal.action,
            "confidence": signal.confidence,
            "valid": signal.valid,
            "reason": signal.reason,
            "features_hash": signal.features_hash,
            "candle_timestamp": signal.candle_timestamp.isoformat() if signal.candle_timestamp else None,
        }
        if engine == "pattern":
            self.pattern_signal = signal_dict
        elif engine == "consensus":
            self.consensus_signal = signal_dict
        elif engine == "rl":
            self.rl_signal = signal_dict
        elif engine == "offline_rl":
            self.offline_rl_signal = signal_dict
        elif engine == "ml":
            self.ml_signal = signal_dict
        elif engine == "quant":
            self.quant_signal = signal_dict
        elif engine == "omega":
            self.omega_signal = signal_dict
        elif engine == "kronos":
            self.kronos_signal = signal_dict
        elif engine == "neural":
            self.neural_signal = signal_dict
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Serializable representation for observability."""
        return {
            "symbol": self.symbol,
            "cycle_id": self.cycle_id,
            "action": self.action,
            "direction": self.direction,
            "confidence": self.confidence,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "candle_timestamp": self.candle_timestamp.isoformat() if self.candle_timestamp else None,
            "current_stage": self.current_stage,
            "rejection_reason": self.rejection_reason,
            "rejection_stage": self.rejection_stage,
            "previous_action": self.previous_action,
            "previous_confidence": self.previous_confidence,
            "pattern_signal": self.pattern_signal,
            "consensus_signal": self.consensus_signal,
            "rl_signal": self.rl_signal,
            "offline_rl_signal": self.offline_rl_signal,
            "ml_signal": self.ml_signal,
            "quant_signal": self.quant_signal,
            "omega_signal": self.omega_signal,
            "kronos_signal": self.kronos_signal,
            "neural_signal": self.neural_signal,
            "transitions": [
                {
                    "from": t.from_stage,
                    "to": t.to_stage,
                    "action": t.action,
                    "confidence": t.confidence,
                    "reason": t.reason,
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in self.transitions
            ],
            "metadata": self.metadata,
            "lot": self.lot,
            "sl_points": self.sl_points,
            "tp_points": self.tp_points,
            "rr_ratio": self.rr_ratio,
            "grade": self.grade,
            "pattern": self.pattern,
            "regime": self.regime,
            "adx_val": self.adx_val,
            "rsi_val": self.rsi_val,
            "atr_val": self.atr_val,
            "spread": self.spread,
            "session": self.session,
        }

    def to_legacy_decision(self):
        """Convert to legacy Decision object for backward compatibility."""
        from brain.brain import Decision
        return Decision(
            action="TRADE" if self.action in ("BUY", "SELL") else "WAIT",
            direction=self.direction,
            lot=self.lot,
            tp_points=self.tp_points,
            sl_points=self.sl_points,
            confidence=int(self.confidence),
            grade=self.grade,
            regime=self.regime,
            regime_score=int(self.confidence),
            structure=self.pattern,
            structure_score=int(self.confidence),
            entry_score=int(self.confidence),
            reason=self.metadata.get("reason_FINAL", ""),
            pattern=self.pattern,
            rr_ratio=self.rr_ratio,
            adx_val=self.adx_val,
            rsi_val=self.rsi_val,
            thought_log=self.thought_log,
            signal_source=self.source,
        )


def create_decision(
    symbol: str,
    action: str = "WAIT",
    direction: str = "NA",
    confidence: float = 0.0,
    source: str = "UNKNOWN",
    timestamp: Optional[datetime] = None,
    candle_timestamp: Optional[datetime] = None,
    cycle_id: Optional[str] = None,
) -> TradingDecision:
    """Factory function for creating a new TradingDecision."""
    return TradingDecision(
        symbol=symbol,
        action=action,
        direction=direction,
        confidence=confidence,
        source=source,
        timestamp=timestamp or datetime.now(timezone.utc),
        candle_timestamp=candle_timestamp,
        cycle_id=cycle_id or uuid.uuid4().hex[:12],
    )