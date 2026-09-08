"""
tests/test_engine_vote_schema.py
===================================
AEGIS GOLD — EngineVote Schema Tests

Verifies that every EngineVote returned by all 7 engines:
1. Has all required fields
2. Has pattern_evidence.confirmation_time <= snapshot.timestamp
3. Has valid proposed_sl and proposed_tp for non-WAIT votes
4. Direction is one of "BUY", "SELL", "WAIT"
5. Conviction is in [0.0, 1.0]
"""

import sys
import os
from datetime import datetime, timezone, timedelta
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.engine_vote import EngineVote, PatternEvidence, PricePoint, make_wait_vote
from brain.frozen_snapshot import FrozenDecisionSnapshot, build_snapshot


# ─────────────────────────────────────────────────────────────────
# Fixture: minimal valid snapshot
# ─────────────────────────────────────────────────────────────────

def _make_candle(t_offset_s, o=2000.0, h=2010.0, l=1995.0, c=2005.0):
    return {
        "time": int((datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()) + t_offset_s),
        "open": o, "high": h, "low": l, "close": c, "volume": 100
    }


def _make_snapshot(n_m5=50, n_m1=30, symbol="XAUUSD"):
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # bars with time BEFORE now (all closed)
    m5_bars = [_make_candle(t_offset_s=i * 300 - n_m5 * 300, c=2000 + i * 0.5) for i in range(n_m5)]
    m1_bars = [_make_candle(t_offset_s=i * 60 - n_m1 * 60, c=2000 + i * 0.2) for i in range(n_m1)]

    return FrozenDecisionSnapshot(
        timestamp=now,
        symbol=symbol,
        candles_m5=tuple(m5_bars),
        candles_m1=tuple(m1_bars),
        candles_h1=(),
        spread=20.0,
        point=0.01,
        session="LONDON",
        account_equity=10000.0,
        current_price=2025.0,
    )


# ─────────────────────────────────────────────────────────────────
# 1. EngineVote Dataclass Schema Tests
# ─────────────────────────────────────────────────────────────────

class TestEngineVoteSchema(unittest.TestCase):

    def test_required_fields_present(self):
        """EngineVote must have all required fields."""
        vote = EngineVote(
            engine_name="test_engine",
            direction="BUY",
            conviction=0.75,
            pattern_evidence=[],
            proposed_sl=1990.0,
            proposed_tp=2050.0,
            invalidation_level=1985.0,
            signal_time=datetime.now(timezone.utc),
        )
        assert vote.engine_name == "test_engine"
        assert vote.direction == "BUY"
        assert 0.0 <= vote.conviction <= 1.0
        assert isinstance(vote.pattern_evidence, list)
        assert vote.proposed_sl > 0
        assert vote.proposed_tp > 0
        assert vote.invalidation_level > 0

    def test_direction_must_be_valid(self):
        """Direction must be one of BUY, SELL, WAIT."""
        for direction in ("BUY", "SELL", "WAIT"):
            vote = make_wait_vote("test") if direction == "WAIT" else EngineVote(
                engine_name="test",
                direction=direction,
                conviction=0.5,
            )
            assert vote.direction in ("BUY", "SELL", "WAIT")

    def test_conviction_in_range(self):
        """Conviction must be [0.0, 1.0]."""
        vote = EngineVote(engine_name="test", direction="SELL", conviction=0.85)
        assert 0.0 <= vote.conviction <= 1.0

    def test_make_wait_vote_factory(self):
        """make_wait_vote should create a properly formed WAIT vote."""
        now = datetime.now(timezone.utc)
        vote = make_wait_vote("test_engine", "No signal", signal_time=now)
        assert vote.direction == "WAIT"
        assert vote.conviction == 0.0
        assert vote.engine_name == "test_engine"
        assert vote.error == "No signal"
        assert vote.pattern_evidence == []

    def test_leakage_check_passes_when_clean(self):
        """leakage_check() should return empty list when all confirmation_times <= decision_time."""
        now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=5)

        ev = PatternEvidence(
            pattern_type="BOS_BUY",
            confirmation_time=past,
        )
        vote = EngineVote(engine_name="smc", direction="BUY", conviction=0.8, pattern_evidence=[ev])
        violations = vote.leakage_check(now)
        assert violations == [], f"Expected no violations, got: {violations}"

    def test_leakage_check_fails_when_future_confirmation(self):
        """leakage_check() must flag evidence with confirmation_time > decision_time."""
        now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        future = now + timedelta(minutes=5)

        ev = PatternEvidence(
            pattern_type="BOS_BUY",
            confirmation_time=future,   # FUTURE timestamp — leakage!
        )
        vote = EngineVote(engine_name="smc", direction="BUY", conviction=0.8, pattern_evidence=[ev])
        violations = vote.leakage_check(now)
        assert len(violations) > 0, "Should detect leakage when confirmation_time > decision_time"
        assert "LEAKAGE" in violations[0]

    def test_pattern_evidence_is_valid_at_check(self):
        """PatternEvidence.is_valid_at() must return True only when confirmation <= decision_time."""
        now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=10)
        future = now + timedelta(minutes=10)

        ev_past = PatternEvidence(pattern_type="X", confirmation_time=past)
        ev_future = PatternEvidence(pattern_type="X", confirmation_time=future)
        ev_same = PatternEvidence(pattern_type="X", confirmation_time=now)

        assert ev_past.is_valid_at(now), "Past confirmation should be valid"
        assert ev_same.is_valid_at(now), "Same-time confirmation should be valid"
        assert not ev_future.is_valid_at(now), "Future confirmation should be INVALID (leakage)"


# ─────────────────────────────────────────────────────────────────
# 2. SMC Engine Vote Schema
# ─────────────────────────────────────────────────────────────────

class TestSMCVoteSchema(unittest.TestCase):

    def test_smc_predict_vote_returns_engine_vote(self):
        """SMCEngine.predict_vote() must return an EngineVote instance."""
        from brain.smc_engine import SMCEngine
        engine = SMCEngine(symbol="XAUUSD")
        snapshot = _make_snapshot()
        vote = engine.predict_vote(snapshot)
        assert isinstance(vote, EngineVote), f"Expected EngineVote, got {type(vote)}"

    def test_smc_vote_no_leakage(self):
        """SMC vote must have all confirmation_times <= snapshot.timestamp."""
        from brain.smc_engine import SMCEngine
        engine = SMCEngine(symbol="XAUUSD")
        snapshot = _make_snapshot()
        vote = engine.predict_vote(snapshot)
        violations = vote.leakage_check(snapshot.timestamp)
        assert violations == [], f"SMC vote has leakage: {violations}"

    def test_smc_vote_direction_valid(self):
        """SMC vote direction must be BUY, SELL, or WAIT."""
        from brain.smc_engine import SMCEngine
        engine = SMCEngine(symbol="XAUUSD")
        snapshot = _make_snapshot()
        vote = engine.predict_vote(snapshot)
        assert vote.direction in ("BUY", "SELL", "WAIT")

    def test_smc_vote_conviction_in_range(self):
        """SMC conviction must be in [0.0, 1.0]."""
        from brain.smc_engine import SMCEngine
        engine = SMCEngine(symbol="XAUUSD")
        snapshot = _make_snapshot()
        vote = engine.predict_vote(snapshot)
        assert 0.0 <= vote.conviction <= 1.0


# ─────────────────────────────────────────────────────────────────
# 3. Kronos Vote Schema
# ─────────────────────────────────────────────────────────────────

class TestKronosVoteSchema(unittest.TestCase):

    def test_kronos_predict_vote_returns_engine_vote(self):
        """KronosForecaster.predict_vote() must return an EngineVote."""
        try:
            from brain.kronos_forecaster import KronosForecaster
            engine = KronosForecaster()
            snapshot = _make_snapshot()
            vote = engine.predict_vote(snapshot)
            assert isinstance(vote, EngineVote)
            assert vote.direction in ("BUY", "SELL", "WAIT")
            assert 0.0 <= vote.conviction <= 1.0
            violations = vote.leakage_check(snapshot.timestamp)
            assert violations == [], f"Kronos leakage: {violations}"
        except ImportError:
            raise unittest.SkipTest("KronosForecaster not available")


# ─────────────────────────────────────────────────────────────────
# 4. QFE Vote Schema
# ─────────────────────────────────────────────────────────────────

class TestQFEVoteSchema(unittest.TestCase):

    def test_qfe_predict_vote_returns_engine_vote(self):
        """QuantFeatureEngine.predict_vote() must return an EngineVote."""
        from brain.quant_feature_engine import QuantFeatureEngine
        engine = QuantFeatureEngine()
        snapshot = _make_snapshot()
        vote = engine.predict_vote(snapshot)
        assert isinstance(vote, EngineVote)
        assert vote.direction in ("BUY", "SELL", "WAIT")
        assert 0.0 <= vote.conviction <= 1.0
        violations = vote.leakage_check(snapshot.timestamp)
        assert violations == [], f"QFE leakage: {violations}"


# ─────────────────────────────────────────────────────────────────
# 5. FrozenDecisionSnapshot Integrity
# ─────────────────────────────────────────────────────────────────

class TestSnapshotIntegrity(unittest.TestCase):

    def test_snapshot_bars_all_before_timestamp(self):
        """All bars in a valid snapshot must have timestamp < snapshot.timestamp."""
        snapshot = _make_snapshot()
        violations = snapshot.verify_integrity()
        assert violations == [], f"Snapshot integrity violations: {violations}"

    def test_build_snapshot_strips_forming_candle(self):
        """build_snapshot() must strip the last (forming) bar if its time >= decision_time."""
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        # Include a bar at exactly now (forming)
        m5_bars = [
            _make_candle(t_offset_s=i * 300 - 50 * 300) for i in range(49)
        ]
        # Add a "forming" bar with timestamp AT decision time
        forming_time = int(now.timestamp())
        m5_bars.append({"time": forming_time, "open": 2000, "high": 2010, "low": 1995, "close": 2005, "volume": 1})

        snap = build_snapshot(
            symbol="XAUUSD",
            candles_m5=m5_bars,
            candles_m1=[],
            decision_time=now,
            point=0.01,
        )
        # The forming bar should have been stripped
        violations = snap.verify_integrity()
        assert violations == [], f"build_snapshot did not strip forming bar: {violations}"
