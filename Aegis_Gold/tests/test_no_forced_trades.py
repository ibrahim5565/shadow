"""
tests/test_no_forced_trades.py
===============================
AEGIS GOLD — No Forced Trades Unit Tests (Phase 5)

Verifies:
1. System returns action="WAIT" when no valid pattern exists.
2. System does NOT force synthetic trades or rely on tick scalping quotas.
3. System remains idle when market structure is noisy or unconfirmed.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.setup_candidate import SetupCandidate, SetupState
from brain.trigger_engine import RealTimeEntryTriggerEngine
from brain.frozen_snapshot import build_snapshot


class TestNoForcedTrades(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.trigger_engine = RealTimeEntryTriggerEngine()

    def test_returns_none_when_no_setup_exists(self):
        """When setup state is NO_SETUP, trigger engine returns None (WAIT)."""
        candles = [{"time": int(self.now.timestamp()) - i*300, "open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2000.0, "volume": 100} for i in range(20)][::-1]
        setup = SetupCandidate(
            setup_id="s_none", symbol="XAUUSD", direction_bias="WAIT",
            formation_time=self.now, information_available_time=self.now,
            confirmation_time=self.now, setup_level=2000.0, invalidation_level=1990.0,
            expiry_time=self.now + timedelta(minutes=30),
            state=SetupState.NO_SETUP,
        )
        snapshot = build_snapshot(
            symbol="XAUUSD",
            candles_m5=candles,
            candles_m1=candles,
            decision_time=self.now,
        )
        trigger = self.trigger_engine.detect_trigger(setup, snapshot)
        self.assertIsNone(trigger)

    def test_expired_setup_resets_to_expired_without_trade(self):
        """When setup is expired, trigger engine marks setup EXPIRED and returns None."""
        candles = [{"time": int(self.now.timestamp()) - i*300, "open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2000.0, "volume": 100} for i in range(20)][::-1]
        setup = SetupCandidate(
            setup_id="s_exp", symbol="XAUUSD", direction_bias="BUY",
            formation_time=self.now - timedelta(hours=2),
            information_available_time=self.now - timedelta(hours=2),
            confirmation_time=self.now - timedelta(hours=2),
            setup_level=2000.0, invalidation_level=1990.0,
            expiry_time=self.now - timedelta(minutes=30), # Already expired
            state=SetupState.ENTRY_ARMED,
        )
        snapshot = build_snapshot(
            symbol="XAUUSD",
            candles_m5=candles,
            candles_m1=candles,
            decision_time=self.now,
        )
        trigger = self.trigger_engine.detect_trigger(setup, snapshot)
        self.assertIsNone(trigger)
        self.assertEqual(setup.state, SetupState.EXPIRED)
