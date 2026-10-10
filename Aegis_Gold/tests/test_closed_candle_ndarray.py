"""
Step 5 (AC-3, bug fix): closed-candle slicing for the MT5 numpy structured
array, with real dedup timestamps.

(a) The same bars as a real-format MT5 ndarray must produce the same signal
    as the same bars as a closed-only DataFrame (i.e. the forming bar at
    [-1] is dropped for every input type), and mutating the forming bar
    must not change the signal.
(b) 20 loop iterations inside one candle: exactly 1 TRADE then 19 WAIT with
    reason CANDLE_ALREADY_PROCESSED.
(c) The next candle (advanced closed bar) can trade again.

No thresholds, gates, SL/TP, or risk limits are touched here.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.brain import _decide_impl, _extract_candle_time, get_pattern_entry_signal

MT5_DTYPE = np.dtype([
    ("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
    ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<i8"),
    ("spread", "<i4"), ("real_volume", "<i8"),
])


def _closed_bars():
    """60 closed bars: flat, then bearish + bullish-engulfing at the end."""
    rows = []
    for i in range(60):
        rows.append((1_000_000 + i * 300, 2500.0, 2500.3, 2499.7, 2500.0,
                     10, 30, 0))
    rows[-2] = (1_000_000 + 58 * 300, 2510.0, 2512.0, 2498.0, 2500.0,
                10, 30, 0)
    rows[-1] = (1_000_000 + 59 * 300, 2496.0, 2516.0, 2494.0, 2514.0,
                10, 30, 0)
    return rows


def _ndarray_with_forming(closed_rows, forming_close=2514.2,
                          forming_high=2515.0, forming_low=2513.0):
    rows = list(closed_rows) + [(
        closed_rows[-1][0] + 300, 2514.0, forming_high, forming_low,
        forming_close, 10, 30, 0)]
    return np.array(rows, dtype=MT5_DTYPE)


def _closed_only_frame(closed_rows):
    return pd.DataFrame(
        [{"time": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4]}
         for r in closed_rows])


def _permissive_risk():
    risk = MagicMock()
    risk.lot_override = 0.0
    risk.can_trade.return_value = True
    risk.is_daily_loss_limit_reached.return_value = False
    risk.volatility_scaled_lot.side_effect = lambda *a, **k: 0.01
    risk.correlation_exposure_check.return_value = True
    risk.margin_buffer_check.return_value = True
    return risk


def _reset_caches():
    for attr in ("_analyzed_candles", "_traded_candles", "_processed_candles"):
        if hasattr(_decide_impl, attr):
            try:
                getattr(_decide_impl, attr).clear()
            except Exception:
                pass


def test_ndarray_signal_equals_closed_only_dataframe():
    closed = _closed_bars()
    arr = _ndarray_with_forming(closed)
    frame = _closed_only_frame(closed)

    dir_arr, entry_arr = get_pattern_entry_signal(
        arr, point=0.01, symbol="XAUUSD")
    dir_df, entry_df = get_pattern_entry_signal(
        frame, point=0.01, symbol="XAUUSD", is_closed_only=True)

    assert dir_arr == dir_df == "BUY"
    assert "ENGULFING" in entry_arr.pattern_name.upper()
    assert entry_arr.pattern_name == entry_df.pattern_name
    assert entry_arr.candle_time is not None
    assert entry_arr.candle_time == closed[-1][0]
    # Real MT5 epoch timestamps flow through (dedup keys are never None).
    assert _extract_candle_time(arr[-2]) == closed[-1][0]
    assert _extract_candle_time(arr[-1]) == closed[-1][0] + 300


def test_forming_bar_mutation_does_not_change_signal():
    closed = _closed_bars()
    base = _ndarray_with_forming(closed, forming_close=2514.2)
    wild = _ndarray_with_forming(
        closed, forming_close=2600.0, forming_high=2610.0,
        forming_low=2590.0)

    dir_base, entry_base = get_pattern_entry_signal(
        base, point=0.01, symbol="XAUUSD")
    dir_wild, entry_wild = get_pattern_entry_signal(
        wild, point=0.01, symbol="XAUUSD")

    assert (dir_base, entry_base.pattern_name) == \
        (dir_wild, entry_wild.pattern_name) == ("BUY", entry_base.pattern_name)
    assert abs(entry_base.entry_price - entry_wild.entry_price) < 1e-9


def test_twenty_iterations_one_candle_gives_one_trade():
    _reset_caches()
    closed = _closed_bars()
    arr = _ndarray_with_forming(closed)
    risk = _permissive_risk()
    account = {"equity": 10000.0, "balance": 10000.0}

    actions, reasons = [], []
    for _ in range(20):
        dec = _decide_impl([], arr, account, risk, "LONDON", 15.0, 0.01,
                           "XAUUSD")
        actions.append(dec.action)
        reasons.append(dec.reason)

    assert actions[0] == "TRADE", reasons[0]
    assert actions.count("TRADE") == 1
    assert actions.count("WAIT") == 19
    for reason in reasons[1:]:
        assert reason == "CANDLE_ALREADY_PROCESSED", reason


def test_next_candle_can_trade_again():
    _reset_caches()
    closed = _closed_bars()
    risk = _permissive_risk()
    account = {"equity": 10000.0, "balance": 10000.0}

    first = _decide_impl([], _ndarray_with_forming(closed), account, risk,
                         "LONDON", 15.0, 0.01, "XAUUSD")
    assert first.action == "TRADE"

    # Advance one candle: old forming bar becomes closed, new forming bar.
    # Keep the engulfing shape on the new closed bar [-2] so the pattern
    # persists; the clock advances one full M5 step (+300s) so the dedup
    # key is a fresh timestamp.
    advanced = list(closed)[:-2] + [
        (closed[-1][0], 2510.0, 2512.0, 2498.0, 2500.0, 10, 30, 0),
        (closed[-1][0] + 300, 2496.0, 2516.0, 2494.0, 2514.0, 10, 30, 0),
        (closed[-1][0] + 600, 2514.0, 2515.0, 2513.0, 2514.2, 10, 30, 0),
    ]
    second = _decide_impl([], np.array(advanced, dtype=MT5_DTYPE), account,
                          risk, "LONDON", 15.0, 0.01, "XAUUSD")
    assert second.action == "TRADE", second.reason
    _reset_caches()
