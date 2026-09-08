"""
===========================================================================
AEGIS GOLD — Setup Candidate & State Machine (Phase 4)
===========================================================================

PURPOSE:
  Separates MARKET STRUCTURE (Setup) from TIMING (Trigger).

SETUP STATE MACHINE:
  NO_SETUP
     ↓
  SETUP_DETECTED        (initial pattern forming)
     ↓
  SETUP_CONFIRMED       (pattern confirmed by closed bar; info_available <= T)
     ↓
  ENTRY_ARMED           (waiting for real-time micro-trigger)
     ↓
  TRIGGER_DETECTED      (micro-trigger fired via RealTimeEntryTriggerEngine)
     ↓
  ENGINE_EVALUATION     (7-Engine Consensus)
     ↓
  MASTER_DECISION       (EV Check + Cost Evaluation)
     ↓
  EXECUTED / REJECTED

TERMINAL / FAILURE STATES:
  EXPIRED               (setup_age > expiry_time)
  INVALIDATED           (price breached invalidation_level)
  STALE                 (trigger expired before fill)
  CHASED                (price moved too far from trigger level)
===========================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class SetupState(Enum):
    NO_SETUP = auto()
    SETUP_DETECTED = auto()
    SETUP_CONFIRMED = auto()
    ENTRY_ARMED = auto()
    TRIGGER_DETECTED = auto()
    ENGINE_EVALUATION = auto()
    MASTER_DECISION = auto()
    EXECUTED = auto()

    # Terminal failure states
    EXPIRED = auto()
    INVALIDATED = auto()
    STALE = auto()
    CHASED = auto()
    REJECTED = auto()


@dataclass
class SetupCandidate:
    """
    Represents an identified structural market setup prior to entry trigger.

    Fields
    ------
    setup_id:                   Unique setup identifier
    symbol:                     Trading symbol ("XAUUSD", "EURUSD")
    direction_bias:             "BUY" or "SELL"
    formation_time:             When setup started forming
    information_available_time: When setup became unambiguously observable (<= T)
    confirmation_time:          When closing bar confirmed setup (<= T)
    setup_level:                Structural entry reference price (e.g. OB edge)
    invalidation_level:         Price that invalidates setup (e.g. OB low)
    expiry_time:                Timestamp when setup expires if no trigger fires
    state:                      Current SetupState enum
    evidence:                   Pattern evidence details
    extra:                      Metadata dictionary
    """
    setup_id: str
    symbol: str
    direction_bias: str                           # "BUY" or "SELL"
    formation_time: datetime
    information_available_time: datetime
    confirmation_time: datetime
    setup_level: float
    invalidation_level: float
    expiry_time: datetime
    state: SetupState = SetupState.SETUP_DETECTED
    evidence: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self, current_time: datetime) -> bool:
        """Returns True if current_time >= expiry_time."""
        ct = current_time if current_time.tzinfo else current_time.replace(tzinfo=timezone.utc)
        et = self.expiry_time if self.expiry_time.tzinfo else self.expiry_time.replace(tzinfo=timezone.utc)
        return ct >= et

    def is_invalidated(self, current_price: float) -> bool:
        """Returns True if price has breached the invalidation level."""
        if self.direction_bias == "BUY":
            return current_price <= self.invalidation_level
        elif self.direction_bias == "SELL":
            return current_price >= self.invalidation_level
        return False

    def arm_entry(self, current_time: datetime) -> bool:
        """Transitions setup from SETUP_CONFIRMED to ENTRY_ARMED if valid."""
        if self.is_expired(current_time):
            self.state = SetupState.EXPIRED
            return False
        if self.state in (SetupState.SETUP_CONFIRMED, SetupState.SETUP_DETECTED):
            self.state = SetupState.ENTRY_ARMED
            return True
        return self.state == SetupState.ENTRY_ARMED


@dataclass
class EntryTrigger:
    """
    Real-time micro-trigger indicating WHEN to enter an armed setup.

    Fields
    ------
    trigger_id:     Unique trigger identifier
    trigger_time:   Timestamp when trigger fired (MUST be >= information_available_time)
    direction:      "BUY" or "SELL"
    trigger_price:  Price at trigger moment
    setup_id:       Associated SetupCandidate ID
    trigger_type:   "MICROSTRUCTURE_BREAK", "DISPLACEMENT", "MOMENTUM_ACCEL", "REJECTION", "RETEST"
    evidence:       Evidence list describing the micro-trigger
    expiry_time:    Trigger expiration time (usually 1-3 M1 bars)
    """
    trigger_id: str
    trigger_time: datetime
    direction: str
    trigger_price: float
    setup_id: str
    trigger_type: str
    evidence: List[str] = field(default_factory=list)
    expiry_time: Optional[datetime] = None

    def is_valid(self, decision_time: datetime, info_available_time: datetime) -> bool:
        """Verifies trigger causality: info_available <= trigger_time <= decision_time."""
        tt = self.trigger_time if self.trigger_time.tzinfo else self.trigger_time.replace(tzinfo=timezone.utc)
        dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        iat = info_available_time if info_available_time.tzinfo else info_available_time.replace(tzinfo=timezone.utc)

        return iat <= tt <= dt
