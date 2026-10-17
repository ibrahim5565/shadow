"""
Step 5b (auditor): supervisor trend-reversal exit replay, closed M5 only.

- supervisor_exit=False (default) is byte-identical in behaviour to the
  earlier audit: SL -> TP -> TIME only.
- supervisor_exit=True evaluates supervisor_exit_on_closed_m5() FIRST on
  closed-bar series (M5 leg of TrendDetector only; no M1, no ticks) and
  flags those exits SUPERVISOR_EXIT_TREND_REVERSAL (UNCONFIRMED).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pattern_audit.position_simulator import (
    PositionSimulator,
    supervisor_exit_on_closed_m5,
    _m5_closed_only_trend,
)


def _bars(n=60, drift=0.0):
    closes, highs, lows = [], [], []
    px = 2500.0
    for _ in range(n):
        px += drift
        closes.append(px)
        highs.append(px + 0.3)
        lows.append(px - 0.3)
    return closes, highs, lows


def _open_long(sim, entry=2500.0):
    return sim.open_position(
        direction="BUY", entry_price=entry,
        stop_loss=entry - 11.30, take_profit=entry + 28.25,
        lot_size=0.01, open_time=0.0, open_bar=0)


def _candle(high=None, low=None, close=2500.0):
    import pandas as pd
    return pd.Series({"high": close + 0.3 if high is None else high,
                      "low": close - 0.3 if low is None else low,
                      "close": close})
def test_disabled_flag_matches_legacy_sl_tp_time_behaviour():
    # Same bars, same position: disabled simulator must behave exactly as
    # the earlier audit (SL -> TP -> TIME, no supervisor exits).
    closes, highs, lows = _bars(60, drift=0.0)
    for enabled in (False, True):
        sim = PositionSimulator("XAUUSD", 0.01, supervisor_exit=enabled)
        _open_long(sim)
        sim.update_positions(_candle(), 300.0, bar_index=5,
                             closes=closes, highs=highs, lows=lows)
        # Flat M5: no supervisor exit either way; whatever TIME/SL/TP the
        # legacy logic produces must be identical with the flag on or off.
        assert all(p.exit_reason != "SUPERVISOR_EXIT_TREND_REVERSAL"
                   for p in sim.closed_positions)
    # Legacy parity: same scenario with the flag off vs a pristine legacy
    # simulator with default args must close identically.
    legacy = PositionSimulator("XAUUSD", 0.01)
    flagged_off = PositionSimulator("XAUUSD", 0.01, supervisor_exit=False)
    for sim in (legacy, flagged_off):
        _open_long(sim)
        sim.update_positions(_candle(), 300.0, bar_index=5,
                             closes=closes, highs=highs, lows=lows)
    assert [(p.exit_reason, round(p.pnl, 6)) for p in legacy.closed_positions] == \
           [(p.exit_reason, round(p.pnl, 6)) for p in flagged_off.closed_positions]
    assert len(legacy.open_positions) == len(flagged_off.open_positions)
    # Down-drifted M5 closes -> TRENDING_DOWN: only enabled exits early.
    d_closes, d_highs, d_lows = _bars(60, drift=-0.5)
    off = PositionSimulator("XAUUSD", 0.01, supervisor_exit=False)
    _open_long(off, entry=d_closes[-1])
    off.update_positions(_candle(close=d_closes[-1]), 300.0, bar_index=5,
                         closes=d_closes, highs=d_highs, lows=d_lows)
    assert all(p.exit_reason != "SUPERVISOR_EXIT_TREND_REVERSAL"
               for p in off.closed_positions)
    on = PositionSimulator("XAUUSD", 0.01, supervisor_exit=True)
    _open_long(on, entry=d_closes[-1])
    on.update_positions(_candle(close=d_closes[-1]), 300.0, bar_index=5,
                        closes=d_closes, highs=d_highs, lows=d_lows)
    assert len(on.open_positions) == 0
    assert on.closed_positions[-1].exit_reason == \
        "SUPERVISOR_EXIT_TREND_REVERSAL"


def test_m5_trend_leg_matches_live_shape_and_floor():
    # Strong down-drift: TRENDING_DOWN with score >= live floor (50).
    d_closes, d_highs, d_lows = _bars(60, drift=-0.5)
    trend, score = _m5_closed_only_trend(d_closes, d_highs, d_lows)
    assert trend == "TRENDING_DOWN"
    assert score >= 50
    # Flat market: no reversal exit for a BUY.
    f_closes, f_highs, f_lows = _bars(60, drift=0.0)
    should, trend, score = supervisor_exit_on_closed_m5(
        "BUY", f_closes, f_highs, f_lows)
    assert should is False
    # Mirror rule: SELL exits on TRENDING_UP.
    u_closes, u_highs, u_lows = _bars(60, drift=+0.5)
    should, trend, score = supervisor_exit_on_closed_m5(
        "SELL", u_closes, u_highs, u_lows)
    assert (should, trend) == (True, "TRENDING_UP")
