"""
===========================================================================
AEGIS GOLD — Real-Time Entry Trigger Engine (Phase 4)
===========================================================================

PURPOSE:
  Scans for real-time micro-triggers AFTER a setup transitions to ENTRY_ARMED.

TRIGGER TYPES:
  1. DISPLACEMENT        — M1 strong closed candle in setup direction
  2. MOMENTUM_ACCEL      — M1 candle body > 1.5x rolling 10-bar average body
  3. LEVEL_REJECTION     — M1 wick touch at setup_level with closed rejection
  4. RETEST              — Price retested setup_level and resumed direction

CAUSALITY GUARANTEE:
  Every trigger satisfies:
    setup.information_available_time <= trigger.trigger_time <= snapshot.timestamp
===========================================================================
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

from brain.setup_candidate import SetupCandidate, EntryTrigger, SetupState
from brain.frozen_snapshot import FrozenDecisionSnapshot

logger = logging.getLogger("aegis.trigger_engine")


class RealTimeEntryTriggerEngine:
    """
    Evaluates real-time M1 micro-triggers for ARMED setup candidates.
    """

    def __init__(self, min_body_mult: float = 1.2):
        self.min_body_mult = min_body_mult

    def detect_trigger(
        self,
        setup: SetupCandidate,
        snapshot: FrozenDecisionSnapshot,
    ) -> Optional[EntryTrigger]:
        """
        Scans closed M1 bars in snapshot for a valid micro-trigger matching setup bias.

        Returns EntryTrigger if a valid trigger fired; None otherwise.
        """
        now = snapshot.timestamp

        # 1. Verification gates
        if setup.state not in (SetupState.ENTRY_ARMED, SetupState.SETUP_CONFIRMED):
            return None

        if setup.is_expired(now):
            setup.state = SetupState.EXPIRED
            return None

        candles = list(snapshot.candles_m1) if snapshot.candles_m1 else list(snapshot.candles_m5)
        if snapshot.current_price <= 0 or not candles:
            return None

        if setup.is_invalidated(snapshot.current_price):
            setup.state = SetupState.INVALIDATED
            return None

        # 2. Extract M1 / M5 candles
        m1 = candles
        if len(m1) < 5:
            return None

        # Parse M1 bars
        closes = [float(c.get("close", c.get("c", 0.0))) if isinstance(c, dict) else getattr(c, "close", 0.0) for c in m1]
        opens = [float(c.get("open", c.get("o", 0.0))) if isinstance(c, dict) else getattr(c, "open", 0.0) for c in m1]
        highs = [float(c.get("high", c.get("h", 0.0))) if isinstance(c, dict) else getattr(c, "high", 0.0) for c in m1]
        lows = [float(c.get("low", c.get("l", 0.0))) if isinstance(c, dict) else getattr(c, "low", 0.0) for c in m1]

        last_open = opens[-1]
        last_close = closes[-1]
        last_high = highs[-1]
        last_low = lows[-1]

        direction = setup.direction_bias
        point = snapshot.point
        trigger_type = None
        evidence = []

        # 3. Calculate rolling body size
        bodies = [abs(c - o) for c, o in zip(closes[-10:-1], opens[-10:-1])]
        avg_body = sum(bodies) / max(len(bodies), 1)
        curr_body = abs(last_close - last_open)

        # 4. Trigger rules
        if direction == "BUY":
            is_bullish = last_close > last_open
            # Displacement: M1 close > previous M1 high
            is_displacement = last_close > highs[-2]
            # Acceleration: body size > 1.2x average body
            is_accel = is_bullish and (curr_body >= avg_body * self.min_body_mult)
            # Rejection: touched near setup_level and closed above
            is_rejection = last_low <= setup.setup_level + (10 * point) and last_close > setup.setup_level

            if is_displacement and is_bullish:
                trigger_type = "DISPLACEMENT"
                evidence.append(f"M1 Bullish Displacement (close {last_close:.2f} > prev high {highs[-2]:.2f})")
            elif is_accel:
                trigger_type = "MOMENTUM_ACCEL"
                evidence.append(f"M1 Momentum Accel (body {curr_body:.2f} >= {avg_body*self.min_body_mult:.2f})")
            elif is_rejection:
                trigger_type = "LEVEL_REJECTION"
                evidence.append(f"M1 Level Rejection at setup_level {setup.setup_level:.2f}")

        elif direction == "SELL":
            is_bearish = last_close < last_open
            is_displacement = last_close < lows[-2]
            is_accel = is_bearish and (curr_body >= avg_body * self.min_body_mult)
            is_rejection = last_high >= setup.setup_level - (10 * point) and last_close < setup.setup_level

            if is_displacement and is_bearish:
                trigger_type = "DISPLACEMENT"
                evidence.append(f"M1 Bearish Displacement (close {last_close:.2f} < prev low {lows[-2]:.2f})")
            elif is_accel:
                trigger_type = "MOMENTUM_ACCEL"
                evidence.append(f"M1 Momentum Accel (body {curr_body:.2f} >= {avg_body*self.min_body_mult:.2f})")
            elif is_rejection:
                trigger_type = "LEVEL_REJECTION"
                evidence.append(f"M1 Level Rejection at setup_level {setup.setup_level:.2f}")

        if trigger_type is None:
            return None

        # 5. Build EntryTrigger object
        trigger_id = f"trig_{uuid.uuid4().hex[:8]}"
        trigger = EntryTrigger(
            trigger_id=trigger_id,
            trigger_time=now,  # Micro-trigger timestamp equals snapshot time
            direction=direction,
            trigger_price=snapshot.current_price,
            setup_id=setup.setup_id,
            trigger_type=trigger_type,
            evidence=evidence,
            expiry_time=now + timedelta(minutes=5),
        )

        if trigger.is_valid(now, setup.information_available_time):
            setup.state = SetupState.TRIGGER_DETECTED
            logger.info(f"⚡ [TRIGGER FIRED] {trigger_type} for setup '{setup.setup_id}' at {snapshot.current_price:.2f}")
            return trigger

        return None
