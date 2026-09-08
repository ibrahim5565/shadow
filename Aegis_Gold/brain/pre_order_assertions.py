"""
===========================================================================
AEGIS GOLD — Pre-Order Hard Assertions Engine (Phase 6)
===========================================================================

PURPOSE:
  Executes mandatory pre-flight causality, freshness, economics, and pricing
  assertions immediately prior to MT5 order transmission.

MANDATORY INVARIANTS:
  1. information_available_time <= decision_time
  2. confirmation_time <= decision_time
  3. trigger_time <= decision_time
  4. not entry_chased
  5. not trigger_stale
  6. not setup_expired
  7. EV > required_edge ($0.50)
  8. sl_price > 0 and tp_price > 0
  9. Directional Bid/Ask pricing check (BUY at Ask, SELL at Bid)

FAILURE BEHAVIOR:
  If ANY assertion fails, the order is IMMEDIATELY ABORTED and logged.
===========================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from brain.setup_candidate import SetupCandidate, EntryTrigger
from brain.chase_detector import ChaseCheckResult
from brain.ev_decision_engine import EVResult

logger = logging.getLogger("aegis.pre_order_assertions")


@dataclass
class AssertionResult:
    passed: bool
    violations: List[str]


class PreOrderAssertionsEngine:
    """
    Hard pre-order gate enforcing causality and execution economic integrity.
    """

    def verify_pre_order_invariants(
        self,
        setup: SetupCandidate,
        trigger: EntryTrigger,
        chase_result: ChaseCheckResult,
        ev_result: EVResult,
        decision_time: datetime,
        bid: float,
        ask: float,
        sl_price: float,
        tp_price: float,
    ) -> AssertionResult:
        """
        Executes all pre-order assertions. Returns AssertionResult(passed=True/False, violations=[...]).
        """
        violations = []
        dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)

        # 1. Temporal causality assertions
        iat = setup.information_available_time if setup.information_available_time.tzinfo else setup.information_available_time.replace(tzinfo=timezone.utc)
        ct = setup.confirmation_time if setup.confirmation_time.tzinfo else setup.confirmation_time.replace(tzinfo=timezone.utc)
        tt = trigger.trigger_time if trigger.trigger_time.tzinfo else trigger.trigger_time.replace(tzinfo=timezone.utc)

        if iat > dt:
            violations.append(f"[PRE-ORDER ASSERTION FAIL] info_available_time {iat.isoformat()} > decision_time {dt.isoformat()}")

        if ct > dt:
            violations.append(f"[PRE-ORDER ASSERTION FAIL] confirmation_time {ct.isoformat()} > decision_time {dt.isoformat()}")

        if tt > dt:
            violations.append(f"[PRE-ORDER ASSERTION FAIL] trigger_time {tt.isoformat()} > decision_time {dt.isoformat()}")

        # 2. Freshness & Chase assertions
        if chase_result.is_chased:
            violations.append(f"[PRE-ORDER ASSERTION FAIL] Chased entry detected: {chase_result.reason}")

        if chase_result.is_stale:
            violations.append(f"[PRE-ORDER ASSERTION FAIL] Stale trigger detected: {chase_result.reason}")

        if setup.is_expired(dt):
            violations.append(f"[PRE-ORDER ASSERTION FAIL] Setup is expired at decision_time")

        # 3. Expected Value assertion
        if not ev_result.approved or ev_result.ev <= 0:
            violations.append(f"[PRE-ORDER ASSERTION FAIL] EV check failed: {ev_result.reason}")

        # 4. SL/TP Validity
        if sl_price <= 0 or tp_price <= 0:
            violations.append(f"[PRE-ORDER ASSERTION FAIL] Invalid SL/TP prices: SL={sl_price}, TP={tp_price}")

        # 5. Pricing & Direction checks
        if trigger.direction == "BUY":
            if sl_price >= ask:
                violations.append(f"[PRE-ORDER ASSERTION FAIL] BUY SL={sl_price:.2f} >= Ask={ask:.2f}")
            if tp_price <= ask:
                violations.append(f"[PRE-ORDER ASSERTION FAIL] BUY TP={tp_price:.2f} <= Ask={ask:.2f}")
        elif trigger.direction == "SELL":
            if sl_price <= bid:
                violations.append(f"[PRE-ORDER ASSERTION FAIL] SELL SL={sl_price:.2f} <= Bid={bid:.2f}")
            if tp_price >= bid:
                violations.append(f"[PRE-ORDER ASSERTION FAIL] SELL TP={tp_price:.2f} >= Bid={bid:.2f}")
        else:
            violations.append(f"[PRE-ORDER ASSERTION FAIL] Invalid direction '{trigger.direction}'")

        passed = len(violations) == 0

        if passed:
            logger.info("✅ [PRE-ORDER ASSERTIONS PASSED] All temporal, freshness, EV, and pricing invariants verified.")
        else:
            for v in violations:
                logger.error(f"❌ {v}")

        return AssertionResult(passed=passed, violations=violations)
