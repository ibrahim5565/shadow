"""
tests/test_ev_decision_engine.py
=================================
AEGIS GOLD — EV Engine & Pre-Order Assertions Tests (Phase 6)

Verifies:
1. Expected Value formula calculation after deducting spread, commission, and slippage
2. Rejection of trades with EV <= 0 or EV < required_edge
3. Pre-order hard assertions verification (temporal causality, chase, staleness, EV, pricing)
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.ev_decision_engine import EVDecisionEngine, EVResult
from brain.pre_order_assertions import PreOrderAssertionsEngine, AssertionResult
from brain.setup_candidate import SetupCandidate, EntryTrigger, SetupState
from brain.chase_detector import ChaseCheckResult


class TestEVEngineAndAssertions(unittest.TestCase):

    def setUp(self):
        self.ev_engine = EVDecisionEngine(required_edge=0.50, commission_per_lot=7.0)
        self.assertions_engine = PreOrderAssertionsEngine()
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_ev_positive_trade_approved(self):
        """A trade with positive EV > $0.50 after costs should be approved."""
        res = self.ev_engine.evaluate_ev(
            direction="BUY",
            entry_price=2015.0,
            sl_price=2010.0,  # 5 pts risk = $5.00 gross loss at 0.01 lot
            tp_price=2035.0,  # 20 pts reward = $20.00 gross profit (4.0R)
            win_prob=0.65,
            symbol="XAUUSD",
            lot_size=0.01,
            spread_pts=15.0,  # $0.15 spread cost
            point=0.01,
            slippage_pts=5.0, # $0.05 slippage cost
        )
        self.assertTrue(res.approved)
        self.assertGreater(res.ev, 0.50)
        self.assertGreater(res.expected_profit, res.expected_loss)

    def test_ev_negative_trade_rejected(self):
        """A trade with negative or insufficient EV should be rejected."""
        res = self.ev_engine.evaluate_ev(
            direction="BUY",
            entry_price=2015.0,
            sl_price=2010.0,
            tp_price=2018.0,  # Only 3 pts reward vs 5 pts risk (0.6R)
            win_prob=0.45,    # 45% win prob
            symbol="XAUUSD",
            lot_size=0.01,
            spread_pts=25.0,
            point=0.01,
        )
        self.assertFalse(res.approved)
        self.assertLess(res.ev, 0.50)

    def test_pre_order_assertions_pass_when_clean(self):
        """All pre-order assertions should pass for a clean, fresh, positive-EV trade."""
        setup = SetupCandidate(
            setup_id="s1", symbol="XAUUSD", direction_bias="BUY",
            formation_time=self.now - timedelta(minutes=10),
            information_available_time=self.now - timedelta(minutes=5),
            confirmation_time=self.now - timedelta(minutes=5),
            setup_level=2015.0, invalidation_level=2010.0,
            expiry_time=self.now + timedelta(minutes=30),
            state=SetupState.TRIGGER_DETECTED,
        )
        trigger = EntryTrigger(
            trigger_id="t1", trigger_time=self.now - timedelta(seconds=10),
            direction="BUY", trigger_price=2015.0, setup_id="s1",
            trigger_type="DISPLACEMENT",
        )
        chase_res = ChaseCheckResult(
            is_chased=False, is_stale=False, is_approved=True, remaining_rr=3.5, reason="Fresh"
        )
        ev_res = EVResult(
            approved=True, ev=2.50, win_probability=0.65, loss_probability=0.35,
            expected_profit=15.0, expected_loss=5.0, total_execution_cost=0.30,
            spread_cost=0.15, commission_cost=0.07, slippage_cost=0.08,
            net_rr_ratio=3.0, reason="Approved",
        )

        res = self.assertions_engine.verify_pre_order_invariants(
            setup=setup, trigger=trigger, chase_result=chase_res, ev_result=ev_res,
            decision_time=self.now, bid=2014.80, ask=2015.00,
            sl_price=2010.0, tp_price=2035.0,
        )
        self.assertTrue(res.passed)
        self.assertEqual(res.violations, [])

    def test_pre_order_assertions_fail_on_future_trigger(self):
        """Pre-order assertion should FAIL if trigger_time > decision_time (leakage)."""
        setup = SetupCandidate(
            setup_id="s1", symbol="XAUUSD", direction_bias="BUY",
            formation_time=self.now - timedelta(minutes=10),
            information_available_time=self.now - timedelta(minutes=5),
            confirmation_time=self.now - timedelta(minutes=5),
            setup_level=2015.0, invalidation_level=2010.0,
            expiry_time=self.now + timedelta(minutes=30),
            state=SetupState.TRIGGER_DETECTED,
        )
        # FUTURE trigger time — leakage!
        trigger = EntryTrigger(
            trigger_id="t1", trigger_time=self.now + timedelta(minutes=5),
            direction="BUY", trigger_price=2015.0, setup_id="s1",
            trigger_type="DISPLACEMENT",
        )
        chase_res = ChaseCheckResult(is_chased=False, is_stale=False, is_approved=True, remaining_rr=3.5, reason="Fresh")
        ev_res = EVResult(approved=True, ev=2.50, win_probability=0.65, loss_probability=0.35, expected_profit=15.0, expected_loss=5.0, total_execution_cost=0.30, spread_cost=0.15, commission_cost=0.07, slippage_cost=0.08, net_rr_ratio=3.0, reason="Approved")

        res = self.assertions_engine.verify_pre_order_invariants(
            setup=setup, trigger=trigger, chase_result=chase_res, ev_result=ev_res,
            decision_time=self.now, bid=2014.80, ask=2015.00,
            sl_price=2010.0, tp_price=2035.0,
        )
        self.assertFalse(res.passed)
        self.assertTrue(any("trigger_time" in v for v in res.violations))
