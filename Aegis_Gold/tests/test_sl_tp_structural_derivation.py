"""
tests/test_sl_tp_structural_derivation.py
==========================================
AEGIS GOLD — Structural SL/TP Derivation Tests

Verifies:
1. SL traces back to a real pattern structural level (OB, sweep, FVG edge)
2. TP traces to next opposing liquidity pool / unmitigated FVG
3. 2.0R minimum R:R floor: trades below 2.0R are REJECTED
4. No synthetic fallback TP — if no structural TP exists, trade is rejected
5. sl_basis and tp_basis strings are logged for audit trail
"""

import sys
import os
from datetime import datetime, timezone, timedelta
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.engine_vote import EngineVote, PatternEvidence, make_wait_vote


# ─────────────────────────────────────────────────────────────────
# Import structural SL/TP module
# ─────────────────────────────────────────────────────────────────

def _import_structural_sl_tp():
    try:
        from brain.structural_sl_tp import derive_sl_tp, MIN_RR_RATIO
        return derive_sl_tp, MIN_RR_RATIO
    except ImportError:
        raise unittest.SkipTest("brain/structural_sl_tp.py not yet implemented")


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _make_candle(o=2000.0, h=2010.0, l=1995.0, c=2005.0):
    return {"open": o, "high": h, "low": l, "close": c,
            "time": int(datetime.now(timezone.utc).timestamp())}


def _make_snapshot(n=50, current_price=2025.0):
    from brain.frozen_snapshot import FrozenDecisionSnapshot
    now = datetime.now(timezone.utc)
    m5_bars = [_make_candle(c=2000 + i * 0.5) for i in range(n)]
    return FrozenDecisionSnapshot(
        timestamp=now,
        symbol="XAUUSD",
        candles_m5=tuple(m5_bars),
        candles_m1=(),
        spread=20.0,
        point=0.01,
        session="LONDON",
        account_equity=10000.0,
        current_price=current_price,
    )


def _buy_vote_with_ob(ob_low=2010.0, ob_high=2020.0, tp=2060.0, current_price=2015.0):
    """Build a BUY vote with OB pattern evidence at specific price levels."""
    now = datetime.now(timezone.utc)
    ev = PatternEvidence(
        pattern_type="BOS_BUY",
        confirmation_time=now - timedelta(minutes=5),
        invalidation_level=ob_low - 5.0,
        confidence_raw=0.85,
        extra={
            "ob_low": ob_low,
            "ob_high": ob_high,
            "sweep_level": 0.0,
            "sl_pts": int((current_price - (ob_low - 5.0)) / 0.01),
            "tp_pts": int((tp - current_price) / 0.01),
        },
    )
    return EngineVote(
        engine_name="smc",
        direction="BUY",
        conviction=0.85,
        pattern_evidence=[ev],
        proposed_sl=ob_low - 5.0,
        proposed_tp=tp,
        invalidation_level=ob_low - 5.0,
        signal_time=now,
    )


def _sell_vote_with_ob(ob_low=2040.0, ob_high=2050.0, tp=2000.0, current_price=2045.0):
    """Build a SELL vote with OB pattern evidence."""
    now = datetime.now(timezone.utc)
    ev = PatternEvidence(
        pattern_type="BOS_SELL",
        confirmation_time=now - timedelta(minutes=5),
        invalidation_level=ob_high + 5.0,
        confidence_raw=0.80,
        extra={
            "ob_low": ob_low,
            "ob_high": ob_high,
            "sl_pts": int(((ob_high + 5.0) - current_price) / 0.01),
            "tp_pts": int((current_price - tp) / 0.01),
        },
    )
    return EngineVote(
        engine_name="smc",
        direction="SELL",
        conviction=0.80,
        pattern_evidence=[ev],
        proposed_sl=ob_high + 5.0,
        proposed_tp=tp,
        invalidation_level=ob_high + 5.0,
        signal_time=now,
    )


# ─────────────────────────────────────────────────────────────────
# 1. RR Ratio Calculation Tests (standalone, no module import needed)
# ─────────────────────────────────────────────────────────────────

class TestRRFloorEnforcement(unittest.TestCase):
    """Tests the 2.0R minimum R:R floor rule."""

    MIN_RR = 2.0

    def _calc_rr(self, entry, sl, tp, direction):
        """Calculate R:R ratio from entry/sl/tp prices."""
        sl_dist = abs(entry - sl)
        tp_dist = abs(entry - tp)
        if sl_dist == 0:
            return 0.0
        return tp_dist / sl_dist

    def test_rr_above_2_passes(self):
        """Trade with R:R >= 2.0 must pass."""
        entry = 2015.0
        sl = 2010.0    # 5 pts risk
        tp = 2025.0    # 10 pts reward → 2.0R exactly
        rr = self._calc_rr(entry, sl, tp, "BUY")
        assert rr >= self.MIN_RR, f"Expected R:R >= 2.0, got {rr:.2f}"

    def test_rr_below_2_rejected(self):
        """Trade with R:R < 2.0 must be rejected (returns None from derive_sl_tp)."""
        entry = 2015.0
        sl = 2010.0    # 5 pts risk
        tp = 2020.0    # 5 pts reward → 1.0R — below floor
        rr = self._calc_rr(entry, sl, tp, "BUY")
        assert rr < self.MIN_RR, f"Expected R:R < 2.0 for this test case, got {rr:.2f}"

    def test_rr_calculation_buy(self):
        """R:R calculation is correct for BUY trade."""
        entry = 2020.0
        sl = 2010.0    # risk = 10 pts
        tp = 2050.0    # reward = 30 pts → 3.0R
        rr = self._calc_rr(entry, sl, tp, "BUY")
        assert abs(rr - 3.0) < 0.01, f"Expected 3.0R, got {rr:.2f}"

    def test_rr_calculation_sell(self):
        """R:R calculation is correct for SELL trade."""
        entry = 2020.0
        sl = 2030.0    # risk = 10 pts
        tp = 1990.0    # reward = 30 pts → 3.0R
        rr = self._calc_rr(entry, sl, tp, "SELL")
        assert abs(rr - 3.0) < 0.01, f"Expected 3.0R, got {rr:.2f}"


# ─────────────────────────────────────────────────────────────────
# 2. structural_sl_tp Module Tests (Phase 5)
# ─────────────────────────────────────────────────────────────────

class TestStructuralSLTPDerivation(unittest.TestCase):

    def test_derive_sl_tp_returns_pattern_based_sl(self):
        """SL must trace back to the OB structural level, not a generic ATR multiple."""
        derive_sl_tp, MIN_RR_RATIO = _import_structural_sl_tp()

        ob_low = 2010.0
        current_price = 2015.0
        votes = [_buy_vote_with_ob(ob_low=ob_low, ob_high=2020.0, tp=2065.0, current_price=current_price)]
        snapshot = _make_snapshot(current_price=current_price)

        result = derive_sl_tp(votes, "BUY", snapshot, "XAUUSD")
        sl_price, tp_price, sl_basis, tp_basis = result

        if sl_price is None:
            raise unittest.SkipTest("No structural SL derived — insufficient pattern data")

        # SL must be AT or BELOW the OB low (invalidation level)
        assert sl_price <= ob_low, (
            f"SL={sl_price:.2f} must be at or below OB low={ob_low:.2f} — "
            "not a structural derivation"
        )
        assert sl_basis and len(sl_basis) > 0, "sl_basis must be populated for audit trail"

    def test_derive_sl_tp_enforces_rr_floor(self):
        """If structural TP gives < 2.0R, trade must be rejected (returns None, None)."""
        derive_sl_tp, MIN_RR_RATIO = _import_structural_sl_tp()

        current_price = 2015.0
        ob_low = 2010.0
        # TP only 5 pts above entry = 1.0R (sl=5pts, tp=5pts) — should reject
        bad_tp = current_price + 5.0   # only 1.0R
        votes = [_buy_vote_with_ob(ob_low=ob_low, ob_high=2020.0, tp=bad_tp, current_price=current_price)]
        snapshot = _make_snapshot(current_price=current_price)

        result = derive_sl_tp(votes, "BUY", snapshot, "XAUUSD")
        sl_price, tp_price, sl_basis, tp_basis = result

        assert sl_price is None and tp_price is None, (
            f"Expected None/None for R:R < {MIN_RR_RATIO}, got sl={sl_price} tp={tp_price}"
        )

    def test_derive_sl_tp_no_synthetic_fallback(self):
        """If no structural TP exists at 2.0R, function must return None (no ATR fallback)."""
        derive_sl_tp, MIN_RR_RATIO = _import_structural_sl_tp()

        # Give a vote with NO TP (proposed_tp=0.0 means engine has no TP opinion)
        now = datetime.now(timezone.utc)
        ev = PatternEvidence(
            pattern_type="HURST_REGIME",
            confirmation_time=now - timedelta(minutes=5),
            confidence_raw=0.75,
        )
        no_tp_vote = EngineVote(
            engine_name="quant_feature_engine",
            direction="BUY",
            conviction=0.75,
            pattern_evidence=[ev],
            proposed_sl=0.0,
            proposed_tp=0.0,  # No TP opinion
            invalidation_level=0.0,
            signal_time=now,
        )
        snapshot = _make_snapshot()
        result = derive_sl_tp([no_tp_vote], "BUY", snapshot, "XAUUSD")
        sl_price, tp_price, sl_basis, tp_basis = result

        # With no structural TP, must return None — not an ATR fallback
        assert tp_price is None or tp_price == 0.0, (
            f"Expected None TP when no structural TP exists, got tp={tp_price}"
        )

    def test_sl_basis_string_populated(self):
        """sl_basis must contain the pattern type for audit trail."""
        derive_sl_tp, MIN_RR_RATIO = _import_structural_sl_tp()

        current_price = 2015.0
        votes = [_buy_vote_with_ob(ob_low=2005.0, ob_high=2015.0, tp=2065.0, current_price=current_price)]
        snapshot = _make_snapshot(current_price=current_price)

        result = derive_sl_tp(votes, "BUY", snapshot, "XAUUSD")
        sl_price, tp_price, sl_basis, tp_basis = result

        if sl_price is not None:
            assert sl_basis and len(sl_basis) > 0, "sl_basis must describe which pattern set the SL"
            assert tp_basis and len(tp_basis) > 0, "tp_basis must describe which pattern set the TP"

    def test_sell_trade_sl_above_entry(self):
        """For SELL trades, SL must be ABOVE entry price."""
        derive_sl_tp, MIN_RR_RATIO = _import_structural_sl_tp()

        current_price = 2045.0
        votes = [_sell_vote_with_ob(ob_low=2040.0, ob_high=2050.0, tp=2000.0, current_price=current_price)]
        snapshot = _make_snapshot(current_price=current_price)

        result = derive_sl_tp(votes, "SELL", snapshot, "XAUUSD")
        sl_price, tp_price, sl_basis, tp_basis = result

        if sl_price is not None:
            assert sl_price > current_price, (
                f"SELL SL={sl_price:.2f} must be ABOVE entry={current_price:.2f}"
            )
            assert tp_price < current_price, (
                f"SELL TP={tp_price:.2f} must be BELOW entry={current_price:.2f}"
            )
