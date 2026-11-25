"""Regression tests for the final WAIT confidence invariant."""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.brain import Decision, verify_direction_integrity


class TestWaitConfidenceInvariant(unittest.TestCase):
    def test_direction_integrity_failure_zeros_confidence(self):
        decision = Decision(
            action="TRADE",
            direction="SELL",
            pattern_direction="BUY",
            confidence=87,
        )
        self.assertFalse(verify_direction_integrity(decision))
        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(decision.confidence, 0)

    def test_missing_authoritative_direction_zeros_confidence(self):
        decision = Decision(action="TRADE", direction="BUY", confidence=75)
        self.assertFalse(verify_direction_integrity(decision))
        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(decision.confidence, 0)

    def test_wait_decision_default_confidence_is_zero(self):
        decision = Decision(action="WAIT", direction="HOLD")
        self.assertEqual(decision.confidence, 0)


if __name__ == "__main__":
    unittest.main()
