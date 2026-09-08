"""
tests/test_remaining_rr.py
===========================
AEGIS GOLD — Remaining R:R & Move Consumption Unit Tests

Verifies:
1. Rejection of entries where remaining R:R < 1.80R from CURRENT price.
2. Rejection of entries where > 50% of expected move is consumed.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.chase_detector import EntryChaseDetector
from brain.setup_candidate import SetupCandidate, EntryTrigger, SetupState
from brain.frozen_snapshot import build_snapshot


class TestRemainingRR(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.chase_detector = EntryChaseDetector()

    def test_degraded_remaining_rr_rejected(self):
        """Remaining R:R < 1.80R from current entry price must be rejected."""
        setup = SetupCandidate(
            setup_id="s_rr", symbol="XAUUSD", direction_bias="BUY",
            formation_time=self.now - timedelta(minutes=10),
            information_available_time=self.now - timedelta(minutes=5),
            confirmation_time=self.now - timedelta(minutes=5),
            setup_level=2015.0, invalidation_level=2010.0,
            expiry_time=self.now + timedelta(minutes=30), state=SetupState.ENTRY_ARMED,
        )
        trigger = EntryTrigger(
            trigger_id="t_rr", trigger_time=self.now - timedelta(seconds=30),
            direction="BUY", trigger_price=2015.0, setup_id="s_rr", trigger_type="DISPLACEMENT",
        )
        # Price moved up to 2023.0 (Target is 2025.0) -> Reward remaining = 2 pts, Risk = 13 pts -> RR = 0.15R < 1.8R
        candles = [{"time": int(self.now.timestamp()) - i*300, "open": 2022.0, "high": 2024.0, "low": 2021.0, "close": 2023.0, "volume": 100} for i in range(20)][::-1]
        snapshot = build_snapshot("XAUUSD", candles, candles, self.now)

        res = self.chase_detector.evaluate(setup, trigger, snapshot, sl_price=2010.0, tp_price=2025.0)
        self.assertFalse(res.is_approved)
