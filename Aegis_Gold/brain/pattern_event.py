"""
===========================================================================
AEGIS GOLD — Pattern Event Model (Phase 1)
===========================================================================

PURPOSE:
  Defines the structured PatternEvent representation for historical pattern
  discovery. Every discovered pattern records exact detection, confirmation,
  and earliest entry timestamps.
===========================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from brain.pattern_library import PatternType, PatternCategory, PatternScale

logger = logging.getLogger("aegis.pattern_event")


@dataclass
class PatternEvent:
    """
    Structured Causal Representation of a Discovered Market Pattern.
    """
    symbol: str
    pattern_id: str
    pattern_type: PatternType
    direction: str                     # "BUY" or "SELL"
    scale: PatternScale                # SMALL, MEDIUM, LARGE
    detection_time: datetime
    confirmation_time: datetime
    information_available_time: datetime
    timeframe: str                     # "M1", "M5", "M15", "M30", "H1"
    price_level: float
    invalidation_level: float
    target_level: float
    strength_score: float
    earliest_entry_time: datetime
    expiry_time: datetime
    causal: bool = True
    evidence_notes: List[str] = field(default_factory=list)

    def is_causal(self, decision_time: datetime) -> bool:
        """Verifies zero future leakage: information_available_time <= decision_time."""
        dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        iat = self.information_available_time if self.information_available_time.tzinfo else self.information_available_time.replace(tzinfo=timezone.utc)
        ct = self.confirmation_time if self.confirmation_time.tzinfo else self.confirmation_time.replace(tzinfo=timezone.utc)
        return iat <= dt and ct <= dt
