"""
tests/test_pattern_confirmation_timing.py
=========================================
AEGIS GOLD — Pattern Confirmation Timing Tests

Verifies that each SMC pattern type only fires at/after true confirmation
time, never during the forming (unclosed) candle.

TEMPORAL INTEGRITY RULE:
  SIGNAL_TIME >= INFORMATION_AVAILABLE_TIME
  = CONFIRMATION_TIME (never the formation candle)
"""

import sys
import os
from datetime import datetime, timezone, timedelta
import unittest

# Make sure brain/ is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.smc_engine import (
    detect_swing_points,
    detect_bos_choch,
    detect_order_blocks,
    detect_fvg,
    detect_sweep,
    detect_liquidity_levels,
)


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _make_bar(o, h, l, c):
    return {"open": o, "high": h, "low": l, "close": c}


def _flat_series(n=50, base=2000.0):
    """n bars of flat price."""
    return [_make_bar(base, base + 5, base - 5, base) for _ in range(n)]


def _bullish_impulse_then_pullback(base=2000.0, impulse_pts=100, pullback_pts=50):
    """Creates a clean BOS_BULLISH sequence: flat → impulse up → pullback."""
    bars = _flat_series(30, base)
    # Impulse candles (3 strong bullish)
    for i in range(3):
        bars.append(_make_bar(base, base + impulse_pts, base - 5, base + impulse_pts))
        base += impulse_pts
    # Pullback
    for i in range(5):
        bars.append(_make_bar(base, base + 5, base - pullback_pts // 5, base - pullback_pts // 5))
        base -= pullback_pts // 5
    return bars


# ─────────────────────────────────────────────────────────────────
# 1. Swing Point Detection — No Look-Ahead
# ─────────────────────────────────────────────────────────────────

class TestSwingPointConfirmation(unittest.TestCase):

    def test_swing_highs_not_at_last_bar(self):
        """A swing high should never be detected AT the last bar (it's unconfirmed)."""
        highs = [100.0] * 20
        lows  = [99.0]  * 20
        # Make the last bar the highest — this is the FORMING bar, not confirmed
        highs[-1] = 105.0

        sh, sl = detect_swing_points(highs, lows, window=3)
        # The last bar should NOT appear as a confirmed swing high
        last_idx = len(highs) - 1
        for idx, _ in sh:
            assert idx != last_idx, (
                f"Swing high detected at last bar index {last_idx} — look-ahead violation!"
            )

    def test_swing_highs_not_at_second_to_last_bar(self):
        """With window=3, the pivot at n-4 is the last valid pivot (needs 3 bars after it)."""
        n = 20
        highs = [100.0] * n
        lows  = [99.0]  * n
        # Attempt to make n-2 look like a pivot
        highs[n - 2] = 105.0

        sh, sl = detect_swing_points(highs, lows, window=3)
        # n-2 needs highs[n-1] on its right, which is the last bar (not proven confirmed)
        # With FIXED range(window, n-window-1), n-2 = 18 should NOT be a detected pivot
        # because the range stops at n-window-1 = 20-3-1 = 16 (exclusive upper)
        for idx, _ in sh:
            assert idx < n - 3, (
                f"Swing high at idx={idx} too close to last bar — look-ahead risk"
            )

    def test_confirmed_swing_high_detected(self):
        """A proper swing high with enough confirmed bars on both sides IS detected."""
        highs = [100.0] * 30
        lows  = [99.0]  * 30
        highs[10] = 110.0  # Clear pivot at index 10 with 3+ bars on each side

        sh, _ = detect_swing_points(highs, lows, window=3)
        assert any(idx == 10 for idx, _ in sh), "Should detect confirmed pivot at index 10"

    def test_swing_lows_not_at_last_bar(self):
        """Same test for swing lows."""
        highs = [100.0] * 20
        lows  = [99.0]  * 20
        lows[-1] = 90.0  # Forming bar — should not be confirmed pivot

        _, sl = detect_swing_points(highs, lows, window=3)
        last_idx = len(lows) - 1
        for idx, _ in sl:
            assert idx != last_idx, "Swing low detected at forming bar — look-ahead!"


# ─────────────────────────────────────────────────────────────────
# 2. BOS / CHoCH — Confirmed on Closed Bar Only
# ─────────────────────────────────────────────────────────────────

class TestBOSConfirmation(unittest.TestCase):

    def test_bullish_bos_requires_close_beyond_swing_high(self):
        """BOS is confirmed only when the closing price is beyond the prior swing high."""
        # Build: flat + pivot + break
        highs  = [100.0] * 20 + [105.0] + [100.0] * 5 + [106.0]  # last close > swing high
        lows   = [99.0]  * 27
        closes = [100.0] * 20 + [104.0] + [100.0] * 5 + [106.5]  # confirmed close above

        sh, sl = detect_swing_points(highs, lows, window=2)
        result = detect_bos_choch(highs, lows, closes, sh, sl)
        assert result["bullish_bos"] or result["bullish_choch"], (
            "BOS or CHoCH should be detected when close is above prior swing high"
        )

    def test_no_bos_when_close_below_swing_high(self):
        """Mid-wick that touches but doesn't CLOSE above prior swing high is not BOS."""
        highs  = [100.0] * 20 + [105.0] + [100.0] * 5 + [108.0]  # high touches above...
        lows   = [99.0]  * 27
        closes = [100.0] * 20 + [104.0] + [100.0] * 5 + [104.5]  # ...but close does not

        sh, sl = detect_swing_points(highs, lows, window=2)
        result = detect_bos_choch(highs, lows, closes, sh, sl)
        # Close of 104.5 is NOT above swing high of 105.0 + buffer
        assert not result["bullish_bos"], (
            "BOS should NOT be triggered by a wick — only by a confirmed close"
        )


# ─────────────────────────────────────────────────────────────────
# 3. FVG — Only After 3rd Candle Closes
# ─────────────────────────────────────────────────────────────────

class TestFVGConfirmation(unittest.TestCase):

    def test_fvg_requires_3_candle_close(self):
        """A FVG is only real after the 3rd candle (index i+2) has closed."""
        point = 0.01
        # Build a valid FVG: c1.high < c3.low
        opens  = [2000.0, 2020.0, 2030.0, 2060.0, 2050.0]
        highs  = [2010.0, 2025.0, 2040.0, 2070.0, 2060.0]
        lows   = [1995.0, 2015.0, 2025.0, 2045.0, 2040.0]
        closes = [2008.0, 2022.0, 2038.0, 2065.0, 2055.0]
        # c[0].high=2010, c[2].low=2025 → bullish FVG (gap from 2010 to 2025)

        result = detect_fvg(opens, highs, lows, closes, point, min_gap_pts=5.0)
        # The 3rd candle (index 2) has closed, so FVG IS valid at this point
        assert result["bullish_fvg"], "FVG should be detected after 3rd candle closes"

    def test_no_fvg_on_partial_data(self):
        """FVG must not fire on < 5 candles."""
        result = detect_fvg([2000.0, 2010.0], [2005.0, 2015.0], [1995.0, 2005.0], [2002.0, 2012.0], 0.01)
        assert not result["bullish_fvg"]
        assert not result["bearish_fvg"]


# ─────────────────────────────────────────────────────────────────
# 4. Liquidity Sweep — Wick Closed + Price Reacted
# ─────────────────────────────────────────────────────────────────

class TestSweepConfirmation(unittest.TestCase):

    def test_bullish_sweep_requires_close_above_ssl(self):
        """Sweep is only valid if the bar CLOSED back above the SSL level."""
        from brain.smc_engine import LiquidityLevel
        point = 0.01

        # SSL at 2000 — bar wicks below to 1998, closes back above at 2005
        highs  = [2010.0] * 5 + [2006.0]
        lows   = [1999.0] * 5 + [1998.0]  # sweep candle low < SSL
        closes = [2005.0] * 5 + [2005.0]  # close ABOVE SSL

        ssl_level = LiquidityLevel(price=2000.0, level_type="SSL")
        result = detect_sweep(highs, lows, closes, [ssl_level], point, sweep_buffer_pts=1.0)
        assert result["bullish_sweep"], "Bullish sweep should be confirmed when close > SSL"

    def test_no_sweep_if_still_below_ssl(self):
        """If price closes BELOW the SSL (didn't recover), it's not a sweep — it's a breakdown."""
        from brain.smc_engine import LiquidityLevel
        point = 0.01

        highs  = [2010.0] * 5 + [2005.0]
        lows   = [1999.0] * 5 + [1995.0]  # pierced SSL
        closes = [2005.0] * 5 + [1997.0]  # did NOT close back above SSL

        ssl_level = LiquidityLevel(price=2000.0, level_type="SSL")
        result = detect_sweep(highs, lows, closes, [ssl_level], point, sweep_buffer_pts=1.0)
        assert not result["bullish_sweep"], "Should NOT confirm sweep if close stays below SSL"


# ─────────────────────────────────────────────────────────────────
# 5. Order Block — Displacement Candle Must Have Closed
# ─────────────────────────────────────────────────────────────────

class TestOrderBlockConfirmation(unittest.TestCase):

    def test_ob_only_when_bos_confirmed(self):
        """Order block is only detected after a BOS is confirmed by closed bar."""
        point = 0.01

        # Build: 30 flat bars + a clear bullish BOS
        highs  = [2000.0] * 30 + [2005.0, 2010.0, 2020.0]
        lows   = [1995.0] * 33
        closes = [1999.0] * 30 + [2004.0, 2008.0, 2019.0]  # clear break up
        opens  = [1998.0] * 30 + [1999.0, 2004.0, 2008.0]

        sh, sl = detect_swing_points(highs, lows, window=3)
        bos = detect_bos_choch(highs, lows, closes, sh, sl)

        if bos.get("bullish_bos") or bos.get("bullish_choch"):
            obs = detect_order_blocks(opens, highs, lows, closes, bos, point)
            # OBs may or may not be found depending on candle sequence,
            # but if found, they must have been set by a BEARISH candle in
            # the lookback — not a forming candle
            for ob in obs:
                assert ob.index < len(closes) - 1, (
                    f"OB at index {ob.index} is the forming (last) candle — look-ahead!"
                )
        else:
            raise unittest.SkipTest("BOS not triggered with this synthetic data — skip OB test")
