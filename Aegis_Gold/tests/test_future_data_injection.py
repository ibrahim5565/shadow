"""
tests/test_future_data_injection.py
====================================
AEGIS GOLD — Future-Data Injection Tests (Phase 3)

VERIFICATION CONTRACT:
  At decision time T:
    decision_original = run_pattern_consensus(snapshot_at_T)

  Mutate/inject arbitrary future data AFTER time T:
    - Random future price spike (+1000 pts)
    - Extreme future market crash (-2000 pts)
    - Reversed future price sequence

  Re-run decision at time T:
    decision_after_future_mutation = run_pattern_consensus(snapshot_at_T)

  ASSERT:
    decision_original.action == decision_after_future_mutation.action
    decision_original.direction == decision_after_future_mutation.direction

  If the decision at time T changes when future data is added or modified,
  the test FAILS with FUTURE LEAKAGE.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.frozen_snapshot import FrozenDecisionSnapshot, build_snapshot
from brain.unified_brain import run_pattern_consensus


def _make_candle(t_offset_s, o=2000.0, h=2010.0, l=1995.0, c=2005.0):
    base_t = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    return {
        "time": int(base_t + t_offset_s),
        "open": o, "high": h, "low": l, "close": c, "volume": 100
    }


class TestFutureDataInjection(unittest.TestCase):

    def setUp(self):
        self.decision_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Build 50 closed M5 bars up to decision_time
        self.past_m5_bars = [
            _make_candle(t_offset_s=i * 300 - 50 * 300, c=2000.0 + i * 0.5)
            for i in range(50)
        ]
        self.past_m1_bars = [
            _make_candle(t_offset_s=i * 60 - 30 * 60, c=2000.0 + i * 0.1)
            for i in range(30)
        ]

        self.snapshot = build_snapshot(
            symbol="XAUUSD",
            candles_m5=self.past_m5_bars,
            candles_m1=self.past_m1_bars,
            decision_time=self.decision_time,
            point=0.01,
        )

    def test_future_spike_does_not_alter_past_decision(self):
        """Injecting a +1000 pt spike AFTER decision_time must NOT change decision at T."""
        # 1. Decision at T with un-mutated past
        dec_original = run_pattern_consensus(self.snapshot)

        # 2. Add future bars AFTER decision_time
        future_time = self.decision_time + timedelta(minutes=5)
        future_bar = {
            "time": int(future_time.timestamp()),
            "open": 2025.0,
            "high": 3025.0,  # +1000 pt spike
            "low": 2025.0,
            "close": 3000.0,
            "volume": 9999,
        }

        raw_m5_with_future = list(self.past_m5_bars) + [future_bar]

        # 3. Build snapshot at time T using array containing future bar
        snapshot_filtered = build_snapshot(
            symbol="XAUUSD",
            candles_m5=raw_m5_with_future,
            candles_m1=self.past_m1_bars,
            decision_time=self.decision_time,  # Snapshot time is T!
            point=0.01,
        )

        dec_filtered = run_pattern_consensus(snapshot_filtered)

        # 4. Assert: build_snapshot must filter out the future bar, producing exact same decision
        self.assertEqual(
            dec_original.action, dec_filtered.action,
            "FAIL - FUTURE LEAKAGE: Action changed after future bar added!"
        )
        self.assertEqual(
            dec_original.direction, dec_filtered.direction,
            "FAIL - FUTURE LEAKAGE: Direction changed after future bar added!"
        )

    def test_future_crash_does_not_alter_past_decision(self):
        """Injecting a -2000 pt crash AFTER decision_time must NOT change decision at T."""
        dec_original = run_pattern_consensus(self.snapshot)

        future_time = self.decision_time + timedelta(minutes=15)
        crash_bar = {
            "time": int(future_time.timestamp()),
            "open": 2025.0,
            "high": 2025.0,
            "low": 25.0,   # -2000 pt crash
            "close": 50.0,
            "volume": 99999,
        }

        raw_m5_with_crash = list(self.past_m5_bars) + [crash_bar]

        snapshot_crash = build_snapshot(
            symbol="XAUUSD",
            candles_m5=raw_m5_with_crash,
            candles_m1=self.past_m1_bars,
            decision_time=self.decision_time,
            point=0.01,
        )

        dec_crash = run_pattern_consensus(snapshot_crash)

        self.assertEqual(dec_original.action, dec_crash.action)
        self.assertEqual(dec_original.direction, dec_crash.direction)
