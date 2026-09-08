"""
===========================================================================
AEGIS GOLD — Entry Timing Analysis Engine (Phase 2)
===========================================================================

PURPOSE:
  Objective classification of entry timing quality:
    - EARLIEST : Entry at initial trigger confirmation (chase <= 5 pts)
    - GOOD     : Entry within 5-20 pts of trigger price
    - LATE     : Entry within 20-50 pts of trigger price
    - CHASE    : Entry > 50 pts or trigger age > 180s
===========================================================================
"""

from __future__ import annotations

import logging
from typing import Dict, Any

logger = logging.getLogger("aegis.entry_timing")


class EntryTimingEngine:
    """
    Evaluates entry timing quality.
    """

    def classify_entry_timing(
        self,
        current_price: float,
        trigger_price: float,
        trigger_age_sec: float,
        point: float = 0.01,
    ) -> str:
        """
        Classifies entry timing quality into EARLIEST, GOOD, LATE, or CHASE.
        """
        pt = point if point > 0 else 0.01
        chase_pts = abs(current_price - trigger_price) / pt

        if trigger_age_sec > 180 or chase_pts > 50.0:
            return "CHASE"
        elif chase_pts <= 5.0:
            return "EARLIEST"
        elif chase_pts <= 20.0:
            return "GOOD"
        else:
            return "LATE"
