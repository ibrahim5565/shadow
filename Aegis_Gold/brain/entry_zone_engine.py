"""
===========================================================================
AEGIS GOLD — Entry Zone Engine (Phase 1)
===========================================================================

PURPOSE:
  Calculates ideal entry price, acceptable entry zone boundaries, structural
  invalidation, structural target, maximum chase price, and scale policy.
===========================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from brain.pattern_library import PatternScale

logger = logging.getLogger("aegis.entry_zone")


@dataclass
class EntryZoneSpecification:
    ideal_entry: float
    min_entry_zone: float
    max_entry_zone: float
    invalidation_price: float
    target_price: float
    max_chase_price: float
    scale_policy: PatternScale


class EntryZoneEngine:
    """
    Entry Zone Calculation Engine.
    """

    def calculate_entry_zone(
        self,
        direction: str,
        trigger_price: float,
        scale: PatternScale,
        sl_buffer_pts: float = 100.0,
        tp_buffer_pts: float = 300.0,
        point: float = 0.01,
    ) -> EntryZoneSpecification:
        """
        Calculates entry zone parameters causally.
        """
        pt = point if point > 0 else 0.01

        if direction == "BUY":
            ideal = trigger_price
            min_zone = trigger_price - (10.0 * pt)
            max_zone = trigger_price + (15.0 * pt)
            max_chase = trigger_price + (25.0 * pt)
            sl = trigger_price - (sl_buffer_pts * pt)
            tp = trigger_price + (tp_buffer_pts * pt)
        else:
            ideal = trigger_price
            min_zone = trigger_price - (15.0 * pt)
            max_zone = trigger_price + (10.0 * pt)
            max_chase = trigger_price - (25.0 * pt)
            sl = trigger_price + (sl_buffer_pts * pt)
            tp = trigger_price - (tp_buffer_pts * pt)

        return EntryZoneSpecification(
            ideal_entry=ideal,
            min_entry_zone=min_zone,
            max_entry_zone=max_zone,
            invalidation_price=sl,
            target_price=tp,
            max_chase_price=max_chase,
            scale_policy=scale,
        )
