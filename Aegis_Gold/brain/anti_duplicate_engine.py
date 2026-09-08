"""
Aegis Gold — Anti-Duplicate Opportunity & Frequency Protection Engine
Prevents execution spam by enforcing opportunity-level uniqueness (price zone + structure event),
while allowing unlimited legitimate independent opportunities across the trading session.
"""

import time
import logging
from typing import Dict, Any, Optional
from brain.canonical_types import EntryOpportunity

logger = logging.getLogger("aegis.anti_duplicate")


class AntiDuplicateEngine:
    """
    Tracks active price zones and trigger signatures to prevent duplicate order placement
    without placing artificial time limits on distinct new opportunities.
    """

    def __init__(self, zone_tolerance_points: float = 30.0, expiry_seconds: float = 180.0):
        self.zone_tolerance_points = zone_tolerance_points
        self.expiry_seconds = expiry_seconds
        # Key: (symbol, direction) -> list of recent {price, trigger_type, timestamp, pattern_id}
        self._history: Dict[str, list] = {}

    def is_duplicate(self, opportunity: EntryOpportunity, point: float) -> bool:
        """
        Determines whether this opportunity is a duplicate of a recently authorized setup.
        """
        now = time.time()
        key = f"{opportunity.symbol}_{opportunity.direction}"
        
        # Clean expired entries
        if key in self._history:
            self._history[key] = [
                rec for rec in self._history[key]
                if (now - rec["timestamp"]) < self.expiry_seconds
            ]
        else:
            self._history[key] = []

        entry_px = opportunity.entry_price
        trigger = opportunity.trigger_type
        pattern_id = opportunity.pattern.pattern_id

        # Check if an identical setup in the same price zone exists
        for rec in self._history[key]:
            price_dist_pts = abs(entry_px - rec["price"]) / max(0.00001, point)
            
            # Exact same pattern ID is always duplicate within expiry window
            if rec["pattern_id"] == pattern_id:
                logger.debug(f"[ANTI-DUPLICATE] Blocked: Identical pattern ID {pattern_id}")
                return True

            # Same price zone + same trigger type = duplicate
            if price_dist_pts < self.zone_tolerance_points and rec["trigger_type"] == trigger:
                logger.debug(
                    f"[ANTI-DUPLICATE] Blocked duplicate in {opportunity.symbol}: "
                    f"Zone dist {price_dist_pts:.1f}pts < {self.zone_tolerance_points}pts with trigger {trigger}"
                )
                return True

        return False

    def record_authorization(self, opportunity: EntryOpportunity):
        """Records an authorized entry to track future duplicate attempts."""
        key = f"{opportunity.symbol}_{opportunity.direction}"
        if key not in self._history:
            self._history[key] = []

        self._history[key].append({
            "price": opportunity.entry_price,
            "trigger_type": opportunity.trigger_type,
            "pattern_id": opportunity.pattern.pattern_id,
            "timestamp": time.time()
        })
