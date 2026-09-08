"""
tests/test_consensus_threshold.py
====================================
AEGIS GOLD — Consensus Threshold Tests

Verifies the 5/7 (effectively 5/6 directional) consensus logic:
  - 5 BUY votes → TRADE BUY
  - 4 BUY + 2 SELL → WAIT
  - 5 SELL votes → TRADE SELL
  - Vote discard when confirmation_time > T
  - WAIT output when < 5 engines agree
  - RL Agent (meta-weighter) does NOT count in directional vote
"""

import sys
import os
from datetime import datetime, timezone, timedelta
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.engine_vote import EngineVote, PatternEvidence, make_wait_vote


# ─────────────────────────────────────────────────────────────────
# Import the consensus function from unified_brain
# ─────────────────────────────────────────────────────────────────

def _import_consensus():
    """Import the consensus function, skipping if unified_brain not yet refactored."""
    try:
        from brain.unified_brain import run_pattern_consensus
        return run_pattern_consensus
    except ImportError:
        raise unittest.SkipTest("run_pattern_consensus not yet implemented in unified_brain")


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _past(minutes=5):
    return _now() - timedelta(minutes=minutes)


def _future(minutes=5):
    return _now() + timedelta(minutes=minutes)


def _make_vote(engine_name, direction, conviction=0.8, confirmation_time=None, now=None):
    """Build a minimal EngineVote with one PatternEvidence."""
    t = now or _now()
    ct = confirmation_time or _past()
    ev = PatternEvidence(
        pattern_type=f"TEST_{direction}",
        confirmation_time=ct,
        confidence_raw=conviction,
    )
    if direction == "WAIT":
        return make_wait_vote(engine_name, signal_time=t)
    return EngineVote(
        engine_name=engine_name,
        direction=direction,
        conviction=conviction,
        pattern_evidence=[ev],
        proposed_sl=1990.0,
        proposed_tp=2050.0,
        invalidation_level=1985.0,
        signal_time=t,
    )


# ─────────────────────────────────────────────────────────────────
# Direct consensus logic tests (unit-testing the logic without
# importing unified_brain, in case it's not refactored yet)
# ─────────────────────────────────────────────────────────────────

class TestConsensusLogicDirect(unittest.TestCase):
    """
    Tests the consensus algorithm directly — pure logic unit tests.
    These tests replicate what run_pattern_consensus() must implement.
    """

    DIRECTIONAL_ENGINES = ["smc", "kronos", "quant_feature_engine", "ml_ensemble", "omega", "unified_brain"]
    MIN_AGREEMENT = 5  # 5 of 6 directional engines

    def _run_consensus(self, votes, decision_time=None):
        """
        Minimal consensus implementation for testing.
        Mirrors what unified_brain.run_pattern_consensus() must do.
        """
        dt = decision_time or _now()

        # Step 1: Discard votes with future confirmation_time (leakage gate)
        valid_votes = []
        discarded = []
        for vote in votes:
            # RL agent never counts as directional
            if vote.engine_name == "rl_agent":
                continue
            leaked = [ev for ev in vote.pattern_evidence if not ev.is_valid_at(dt)]
            if leaked:
                discarded.append(vote)
            else:
                valid_votes.append(vote)

        # Step 2: Count directional votes
        buy_count = sum(1 for v in valid_votes if v.direction == "BUY")
        sell_count = sum(1 for v in valid_votes if v.direction == "SELL")

        # Step 3: Check threshold
        if buy_count >= self.MIN_AGREEMENT:
            return "BUY", buy_count, sell_count, discarded
        elif sell_count >= self.MIN_AGREEMENT:
            return "SELL", buy_count, sell_count, discarded
        else:
            return "WAIT", buy_count, sell_count, discarded

    def test_5_buy_votes_yields_trade_buy(self):
        """5 out of 6 directional engines agreeing BUY → TRADE BUY."""
        votes = [
            _make_vote("smc", "BUY"),
            _make_vote("kronos", "BUY"),
            _make_vote("quant_feature_engine", "BUY"),
            _make_vote("ml_ensemble", "BUY"),
            _make_vote("omega", "BUY"),
            _make_vote("unified_brain", "SELL"),  # 1 disagree
        ]
        direction, buy_c, sell_c, discarded = self._run_consensus(votes)
        assert direction == "BUY", f"Expected BUY with 5/6, got {direction} (buy={buy_c}, sell={sell_c})"
        assert discarded == []

    def test_5_sell_votes_yields_trade_sell(self):
        """5 out of 6 directional engines agreeing SELL → TRADE SELL."""
        votes = [
            _make_vote("smc", "SELL"),
            _make_vote("kronos", "SELL"),
            _make_vote("quant_feature_engine", "SELL"),
            _make_vote("ml_ensemble", "SELL"),
            _make_vote("omega", "SELL"),
            _make_vote("unified_brain", "BUY"),  # 1 disagree
        ]
        direction, buy_c, sell_c, discarded = self._run_consensus(votes)
        assert direction == "SELL", f"Expected SELL with 5/6, got {direction}"

    def test_4_buy_2_sell_yields_wait(self):
        """4 BUY + 2 SELL = only 4/6 agreement → WAIT (below 5/6 threshold)."""
        votes = [
            _make_vote("smc", "BUY"),
            _make_vote("kronos", "BUY"),
            _make_vote("quant_feature_engine", "BUY"),
            _make_vote("ml_ensemble", "BUY"),
            _make_vote("omega", "SELL"),
            _make_vote("unified_brain", "SELL"),
        ]
        direction, buy_c, sell_c, discarded = self._run_consensus(votes)
        assert direction == "WAIT", f"Expected WAIT with only 4/6, got {direction}"

    def test_all_wait_votes_yields_wait(self):
        """All WAIT votes → WAIT."""
        votes = [
            _make_vote("smc", "WAIT"),
            _make_vote("kronos", "WAIT"),
            _make_vote("quant_feature_engine", "WAIT"),
            _make_vote("ml_ensemble", "WAIT"),
            _make_vote("omega", "WAIT"),
            _make_vote("unified_brain", "WAIT"),
        ]
        direction, buy_c, sell_c, discarded = self._run_consensus(votes)
        assert direction == "WAIT"

    def test_rl_agent_vote_excluded_from_count(self):
        """RL Agent's predict_vote() must NOT count in the directional consensus."""
        votes = [
            _make_vote("smc", "BUY"),
            _make_vote("kronos", "BUY"),
            _make_vote("quant_feature_engine", "BUY"),
            _make_vote("ml_ensemble", "BUY"),
            _make_vote("omega", "WAIT"),
            _make_vote("unified_brain", "WAIT"),
            _make_vote("rl_agent", "BUY"),  # Should NOT count
        ]
        direction, buy_c, sell_c, discarded = self._run_consensus(votes)
        # Only 4 directional BUY votes (rl_agent excluded), 2 WAIT
        assert direction == "WAIT", (
            f"RL Agent vote should be excluded from count, got {direction} with buy_c={buy_c}"
        )

    def test_future_confirmation_vote_discarded(self):
        """Votes with confirmation_time > decision_time must be discarded."""
        now = _now()
        future_ct = now + timedelta(minutes=10)  # FUTURE — leakage

        votes = [
            _make_vote("smc", "BUY", confirmation_time=future_ct),  # LEAKED
            _make_vote("kronos", "BUY"),
            _make_vote("quant_feature_engine", "BUY"),
            _make_vote("ml_ensemble", "BUY"),
            _make_vote("omega", "BUY"),
            _make_vote("unified_brain", "BUY"),
        ]
        direction, buy_c, sell_c, discarded = self._run_consensus(votes, decision_time=now)
        # smc vote discarded → only 5 BUY (still meets 5/6)
        # The 5 remaining are all BUY
        assert len(discarded) == 1, f"Expected 1 discarded vote, got {len(discarded)}"
        assert discarded[0].engine_name == "smc"

    def test_leakage_discard_drops_below_threshold(self):
        """If discarding leaked votes drops below threshold → WAIT."""
        now = _now()
        future_ct = now + timedelta(minutes=10)

        votes = [
            _make_vote("smc", "BUY", confirmation_time=future_ct),      # LEAKED
            _make_vote("kronos", "BUY", confirmation_time=future_ct),   # LEAKED
            _make_vote("quant_feature_engine", "BUY"),
            _make_vote("ml_ensemble", "BUY"),
            _make_vote("omega", "BUY"),
            _make_vote("unified_brain", "SELL"),
        ]
        direction, buy_c, sell_c, discarded = self._run_consensus(votes, decision_time=now)
        # 2 leaked (SMC, Kronos) → only 3 valid BUY < threshold 5 → WAIT
        assert len(discarded) == 2
        assert direction == "WAIT", (
            f"After discarding 2 leaked votes, only 3 BUY remain — should be WAIT, got {direction}"
        )

    def test_6_of_6_agreement_yields_trade(self):
        """All 6 directional engines agreeing → TRADE."""
        votes = [
            _make_vote("smc", "BUY"),
            _make_vote("kronos", "BUY"),
            _make_vote("quant_feature_engine", "BUY"),
            _make_vote("ml_ensemble", "BUY"),
            _make_vote("omega", "BUY"),
            _make_vote("unified_brain", "BUY"),
        ]
        direction, buy_c, sell_c, discarded = self._run_consensus(votes)
        assert direction == "BUY"
        assert buy_c == 6
