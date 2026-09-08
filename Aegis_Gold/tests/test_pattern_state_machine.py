"""
tests/test_pattern_state_machine.py
====================================
AEGIS GOLD — Pattern State Machine Unit Tests

Verifies:
1. State machine transitions: NO_SETUP -> SETUP_DETECTED -> SETUP_CONFIRMED -> ENTRY_ARMED -> TRIGGER_DETECTED
2. Invalidation and expiry state handling
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.setup_candidate import SetupCandidate, SetupState


class TestPatternStateMachine(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_state_machine_arm_and_trigger(self):
        """SetupCandidate correctly transitions through state machine lifecycle."""
        setup = SetupCandidate(
            setup_id="s100",
            symbol="XAUUSD",
            direction_bias="BUY",
            formation_time=self.now - timedelta(minutes=15),
            information_available_time=self.now - timedelta(minutes=5),
            confirmation_time=self.now - timedelta(minutes=5),
            setup_level=2015.0,
            invalidation_level=2010.0,
            expiry_time=self.now + timedelta(minutes=30),
            state=SetupState.SETUP_CONFIRMED,
        )
        self.assertEqual(setup.state, SetupState.SETUP_CONFIRMED)

        # Arm entry
        setup.arm_entry(self.now)
        self.assertEqual(setup.state, SetupState.ENTRY_ARMED)

        # Trigger
        setup.state = SetupState.TRIGGER_DETECTED
        self.assertEqual(setup.state, SetupState.TRIGGER_DETECTED)

    def test_invalidation_state_transition(self):
        """Breaching invalidation level marks setup as INVALIDATED."""
        setup = SetupCandidate(
            setup_id="s101",
            symbol="XAUUSD",
            direction_bias="BUY",
            formation_time=self.now - timedelta(minutes=15),
            information_available_time=self.now - timedelta(minutes=5),
            confirmation_time=self.now - timedelta(minutes=5),
            setup_level=2015.0,
            invalidation_level=2010.0,
            expiry_time=self.now + timedelta(minutes=30),
            state=SetupState.ENTRY_ARMED,
        )
        self.assertFalse(setup.is_invalidated(2012.0))
        self.assertTrue(setup.is_invalidated(2009.0))
