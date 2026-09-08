"""
===========================================================================
AEGIS GOLD — Entry Chase & Staleness Detector (Phase 4)
===========================================================================

PURPOSE:
  Rejects late entries where price has already moved too far from the
  trigger level, or where latency/staleness has degraded the R:R ratio.

REJECTION CRITERIA:
  1. CHASED ENTRY      — Current price > trigger_price + max_chase_pts
  2. STALE TRIGGER     — trigger_age > max_trigger_age_sec (default 180s)
  3. DEGRADED R:R      — Remaining R:R from current price to TP vs SL < 1.8R
===========================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from brain.setup_candidate import SetupCandidate, EntryTrigger
from brain.frozen_snapshot import FrozenDecisionSnapshot

logger = logging.getLogger("aegis.chase_detector")

DEFAULT_MAX_CHASE_PTS = 50.0       # Gold: 50 pts = $0.50 move past trigger price
DEFAULT_MAX_TRIGGER_AGE_SEC = 180   # 3 minutes max trigger age


@dataclass
class ChaseCheckResult:
    is_chased: bool
    is_stale: bool
    is_approved: bool
    remaining_rr: float
    reason: str


class EntryChaseDetector:
    """
    Evaluates trigger freshness and remaining R:R prior to Master Brain decision.
    """

    def __init__(
        self,
        max_chase_pts: float = DEFAULT_MAX_CHASE_PTS,
        max_trigger_age_sec: int = DEFAULT_MAX_TRIGGER_AGE_SEC,
        min_remaining_rr: float = 1.8,
    ):
        self.max_chase_pts = max_chase_pts
        self.max_trigger_age_sec = max_trigger_age_sec
        self.min_remaining_rr = min_remaining_rr

    def evaluate(
        self,
        setup: SetupCandidate,
        trigger: EntryTrigger,
        snapshot: FrozenDecisionSnapshot,
        sl_price: float,
        tp_price: float,
    ) -> ChaseCheckResult:
        """
        Evaluates whether a trade is fresh, on-level, and carries sufficient remaining R:R.
        """
        now = snapshot.timestamp
        current_price = snapshot.current_price
        pt = snapshot.point

        # 1. Staleness check
        tt = trigger.trigger_time if trigger.trigger_time.tzinfo else trigger.trigger_time.replace(tzinfo=timezone.utc)
        nt = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        trigger_age_sec = (nt - tt).total_seconds()

        if trigger_age_sec > self.max_trigger_age_sec:
            reason = f"STALE TRIGGER | Trigger age {trigger_age_sec:.1f}s > {self.max_trigger_age_sec}s limit"
            logger.warning(f"[CHASE DETECTOR] {reason}")
            return ChaseCheckResult(
                is_chased=False, is_stale=True, is_approved=False, remaining_rr=0.0, reason=reason
            )

        # 2. Chase distance check
        chase_distance_pts = abs(current_price - trigger.trigger_price) / pt if pt > 0 else 0.0

        if trigger.direction == "BUY" and current_price > trigger.trigger_price:
            if chase_distance_pts > self.max_chase_pts:
                reason = f"CHASED ENTRY | BUY price moved {chase_distance_pts:.1f}pts past trigger price {trigger.trigger_price:.2f}"
                logger.warning(f"[CHASE DETECTOR] {reason}")
                return ChaseCheckResult(
                    is_chased=True, is_stale=False, is_approved=False, remaining_rr=0.0, reason=reason
                )
        elif trigger.direction == "SELL" and current_price < trigger.trigger_price:
            if chase_distance_pts > self.max_chase_pts:
                reason = f"CHASED ENTRY | SELL price moved {chase_distance_pts:.1f}pts past trigger price {trigger.trigger_price:.2f}"
                logger.warning(f"[CHASE DETECTOR] {reason}")
                return ChaseCheckResult(
                    is_chased=True, is_stale=False, is_approved=False, remaining_rr=0.0, reason=reason
                )

        # 3. Remaining R:R check from CURRENT entry price
        risk_pts = abs(current_price - sl_price) / pt if pt > 0 else 0.0
        reward_pts = abs(tp_price - current_price) / pt if pt > 0 else 0.0

        if risk_pts <= 0:
            return ChaseCheckResult(
                is_chased=False, is_stale=False, is_approved=False, remaining_rr=0.0, reason="Invalid zero SL risk"
            )

        remaining_rr = round(reward_pts / risk_pts, 2)

        # 4. Move Consumption Check (% of expected move already consumed)
        total_move_pts = abs(tp_price - trigger.trigger_price) / pt if pt > 0 else 0.0
        if total_move_pts > 0:
            consumed_pct = (chase_distance_pts / total_move_pts) * 100.0
            if consumed_pct > 50.0:
                reason = f"MOVE CONSUMED | {consumed_pct:.1f}% of expected move consumed (> 50.0% max)"
                logger.warning(f"[CHASE DETECTOR] {reason}")
                return ChaseCheckResult(
                    is_chased=True, is_stale=False, is_approved=False, remaining_rr=remaining_rr, reason=reason
                )

        if remaining_rr < self.min_remaining_rr:
            reason = f"DEGRADED R:R | Remaining R:R={remaining_rr:.2f}R < {self.min_remaining_rr:.2f}R minimum floor"
            logger.warning(f"[CHASE DETECTOR] {reason}")
            return ChaseCheckResult(
                is_chased=False, is_stale=False, is_approved=False, remaining_rr=remaining_rr, reason=reason
            )

        return ChaseCheckResult(
            is_chased=False,
            is_stale=False,
            is_approved=True,
            remaining_rr=remaining_rr,
            reason=f"ENTRY FRESH | Age={trigger_age_sec:.1f}s Chase={chase_distance_pts:.1f}pts R:R={remaining_rr:.2f}R",
        )
