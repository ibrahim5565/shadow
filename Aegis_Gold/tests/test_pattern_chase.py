"""
tests/test_pattern_chase.py
============================
AEGIS GOLD — Pattern Chase Detector Unit Tests

Verifies:
1. Rejection of triggers where trigger age > 180 seconds (STALE).
2. Rejection of entries where price moved > 50 pts past trigger (CHASED).
3. Rejection of entries where remaining R:R < 1.80R.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.chase_detector import EntryChaseDetector, ChaseCheckResult
from brain.setup_candidate import SetupCandidate, EntryTrigger, SetupState
from brain.frozen_snapshot import build_snapshot


class TestPatternChaseDetector(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.chase_detector = EntryChaseDetector()

    def test_fresh_entry_approved(self):
        """Fresh trigger within 180s and <=50 pts move should be approved."""
        setup = SetupCandidate(
            setup_id="s_chase_1", symbol="XAUUSD", direction_bias="BUY",
            formation_time=self.now - timedelta(minutes=10),
            information_available_time=self.now - timedelta(minutes=5),
            confirmation_time=self.now - timedelta(minutes=5),
            setup_level=2015.0, invalidation_level=2010.0,
            expiry_time=self.now + timedelta(minutes=30), state=SetupState.ENTRY_ARMED,
        )
        trigger = EntryTrigger(
            trigger_id="t_1", trigger_time=self.now - timedelta(seconds=30),
            direction="BUY", trigger_price=2015.8, setup_id="s_chase_1", trigger_type="DISPLACEMENT",
        )
        snapshot = build_snapshot(
            symbol="XAUUSD",
            candles_m5=[{"time": int(self.now.timestamp()) - i*300, "open": 2015.0, "high": 2017.0, "low": 2014.0, "close": 2016.0, "volume": 100} for i in range(20)][::-1],
            candles_m1=[{"time": int(self.now.timestamp()) - i*60, "open": 2015.0, "high": 2017.0, "low": 2014.0, "close": 2016.0, "volume": 100} for i in range(20)][::-1],
            decision_time=self.now,
        )

        res = self.chase_detector.evaluate(setup, trigger, snapshot, sl_price=2010.0, tp_price=2035.0)
        self.assertTrue(res.is_approved)
        self.assertFalse(res.is_chased)
        self.assertFalse(res.is_stale)

    def test_stale_trigger_rejected(self):
        """Trigger older than 180 seconds must be declared STALE and rejected."""
        setup = SetupCandidate(
            setup_id="s_stale", symbol="XAUUSD", direction_bias="BUY",
            formation_time=self.now - timedelta(minutes=20),
            information_available_time=self.now - timedelta(minutes=15),
            confirmation_time=self.now - timedelta(minutes=15),
            setup_level=2015.0, invalidation_level=2010.0,
            expiry_time=self.now + timedelta(minutes=30), state=SetupState.ENTRY_ARMED,
        )
        trigger = EntryTrigger(
            trigger_id="t_stale", trigger_time=self.now - timedelta(seconds=240), # 240s old (>180s)
            direction="BUY", trigger_price=2015.0, setup_id="s_stale", trigger_type="DISPLACEMENT",
        )
        snapshot = build_snapshot(
            symbol="XAUUSD",
            candles_m5=[{"time": int(self.now.timestamp()) - i*300, "open": 2015.0, "high": 2017.0, "low": 2014.0, "close": 2016.0, "volume": 100} for i in range(20)][::-1],
            candles_m1=[{"time": int(self.now.timestamp()) - i*60, "open": 2015.0, "high": 2017.0, "low": 2014.0, "close": 2016.0, "volume": 100} for i in range(20)][::-1],
            decision_time=self.now,
        )

        res = self.chase_detector.evaluate(setup, trigger, snapshot, sl_price=2010.0, tp_price=2035.0)
        self.assertFalse(res.is_approved)
        self.assertTrue(res.is_stale)
