"""
Test: Non-Trivial Caps Equivalence (daily=5, max open=2)

Part A - hand-checkable can_trade() sequence with exact expected reason
strings (daily cap 5, open cap 2, all other caps live-read):

    state            daily  open   expected
    fresh            0      0      (True, "")
    open A,B         2      2      (False, "MAX_OPEN (2/2)")
    close A          2      1      (True, "")
    open C           3      2      (False, "MAX_OPEN (2/2)")
    close B,C        3      0      (True, "")
    open D,E         5      2      (False, "DAILY_LIMIT (5/5)")  <- daily first
    close D,E        5      0      (False, "DAILY_LIMIT (5/5)")
    next UTC day     0      0      (True, "")

Part B - funnel replay equivalence on the seed-42 SYNTHETIC TEST FIXTURE
(500 random M5 bars, NOT real market data): PATTERN_DETECTION +
RISK_EVALUATION are state-independent, so both runs must reach the SIM
gate for the same patterns; each run then partitions those exactly:

    reached_sim == sim_rejected + traded + failed_later   (per run)
    reached_sim(baseline) == reached_sim(capped)          (cross-run)

with per-day trades <= 5 and peak open positions <= 2 asserted.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Block MT5
sys.modules["MetaTrader5"] = None

from scripts.pattern_audit.pattern_detector import (
    detect_patterns_closed_candles_only,
    reset_pattern_state,
)
from scripts.pattern_audit.live_state_simulator import (
    SimulatedClock,
    simulate_state_at_bar,
)
from scripts.pattern_audit.funnel_logger import FunnelLogger
from scripts.pattern_audit.position_simulator import PositionSimulator
from scripts.pattern_audit.risk_limits import LimitValue, read_audit_limits

SIM_GATE = "SIMULATED_POSITION_LIMITS"


def _mk_limits(**overrides) -> dict:
    limits = read_audit_limits()
    for name, (value, src) in overrides.items():
        limits[name] = LimitValue(name, value, src)
    return limits


def _caps_removed_limits() -> dict:
    huge = 10 ** 9
    return _mk_limits(
        MAX_DAILY_TRADES=(huge, "test: caps removed"),
        MAX_OPEN_TRADES=(huge, "test: caps removed"),
        MAX_CONSECUTIVE_LOSSES=(huge, "test: caps removed"),
        TIME_STOP_BASE_SEC=(huge, "test: caps removed"),
        COOLDOWN_AFTER_LOSS_SEC=(0, "test: caps removed"),
        COOLDOWN_AFTER_CONSEC_LOSSES=(0, "test: caps removed"),
    )


def _nontrivial_limits() -> dict:
    """The requested caps: daily 5, max open 2; everything else live-read."""
    return _mk_limits(
        MAX_DAILY_TRADES=(5, "test: daily cap 5"),
        MAX_OPEN_TRADES=(2, "test: open cap 2"),
    )


def _open(sim, t):
    return sim.open_position(
        direction="BUY", entry_price=2500.0, stop_loss=2490.0,
        take_profit=2510.0, lot_size=0.01, open_time=t,
        pattern_type="TEST", pattern_name="TEST",
    )


def test_nontrivial_caps_can_trade_sequence():
    """Part A: exact hand-checkable sequence (daily=5, open=2)."""
    sim = PositionSimulator("XAUUSD", 0.01, limits=_nontrivial_limits())
    t0 = 1700000000.0
    # The runner calls check_daily_reset() at every bar before trading;
    # first call establishes the current UTC day.
    sim.check_daily_reset(t0)

    assert sim.can_trade(t0) == (True, ""), "fresh sim must allow"

    a = _open(sim, t0)          # daily=1, open=1
    b = _open(sim, t0)          # daily=2, open=2
    assert sim.can_trade(t0) == (False, "MAX_OPEN (2/2)")

    sim.close_position(a, 2505.0, t0, "TP")   # daily=2, open=1, win
    assert sim.can_trade(t0) == (True, "")

    c = _open(sim, t0)          # daily=3, open=2
    assert sim.can_trade(t0) == (False, "MAX_OPEN (2/2)")

    sim.close_position(b, 2505.0, t0, "TP")   # daily=3, open=1
    sim.close_position(c, 2505.0, t0, "TP")   # daily=3, open=0
    assert sim.can_trade(t0) == (True, "")

    d = _open(sim, t0)          # daily=4, open=1
    e = _open(sim, t0)          # daily=5, open=2
    # DAILY_LIMIT is checked BEFORE MAX_OPEN in can_trade()
    assert sim.can_trade(t0) == (False, "DAILY_LIMIT (5/5)")

    sim.close_position(d, 2505.0, t0, "TP")   # daily=5, open=1
    sim.close_position(e, 2505.0, t0, "TP")   # daily=5, open=0
    assert sim.can_trade(t0) == (False, "DAILY_LIMIT (5/5)")

    sim.check_daily_reset(t0 + 86400)         # next UTC day
    assert sim.can_trade(t0 + 86400) == (True, "")

    print("[PASS] Non-trivial caps: can_trade sequence matches hand table "
          "(daily=5, open=2)")


def _replay(limits, df, patterns):
    """Runner-style replay. Returns counters for equivalence checks."""
    n = len(df)
    pos_sim = PositionSimulator("XAUUSD", 0.01, limits=limits)
    funnel = FunnelLogger()
    counts = {
        "reached_sim": 0, "traded": 0, "sim_rejected": 0, "failed_later": 0,
        "peak_open": 0, "per_day_traded": {}, "sim_reasons": {},
    }
    LATER_GATES = {"SPREAD_CHECK", "SESSION_CHECK", "DIRECTION_INTEGRITY"}
    for pattern in sorted(patterns, key=lambda p: p.candle_index):
        bi = int(pattern.candle_index)
        row = df.iloc[bi]
        ts = float(row["time"])
        pos_sim.check_daily_reset(ts)
        if pos_sim.open_positions:
            pos_sim.update_positions(row, ts, bar_index=bi)

        state = simulate_state_at_bar(
            bar_timestamp=pattern.timestamp, symbol="XAUUSD", candles=df,
            bar_index=bi, estimated_spread=25.0,
            daily_trades_so_far=pos_sim.daily_trades,
            consecutive_losses_so_far=pos_sim.consecutive_losses,
            broker_offset_hours=None,
        )
        record = funnel.log_pattern_through_gates(
            pattern=pattern, simulated_state=state, symbol="XAUUSD",
            point=0.01, risk_mgr=pos_sim,
            simulated_clock=SimulatedClock(state.candle_time_utc),
        )
        gate_names = [g.gate_name for g in record.gates]
        if SIM_GATE in gate_names:
            counts["reached_sim"] += 1
        if record.rejection_gate in LATER_GATES:
            counts["failed_later"] += 1
        if record.rejection_gate == SIM_GATE:
            counts["sim_rejected"] += 1
            sim_gate = next(g for g in record.gates
                            if g.gate_name == SIM_GATE)
            code = (sim_gate.metadata.get("reason_code")
                    or (sim_gate.reason.split()[0] if sim_gate.reason else "?"))
            counts["sim_reasons"][code] = counts["sim_reasons"].get(code, 0) + 1
        if record.final_outcome == "TRADED":
            counts["traded"] += 1
            fi = min(bi + 1, n - 1)
            fill = df.iloc[fi]
            pos_sim.open_position(
                direction=pattern.direction, entry_price=float(fill["open"]),
                stop_loss=float(pattern.stop_loss),
                take_profit=float(pattern.take_profit), lot_size=0.01,
                open_time=float(fill["time"]), open_bar=fi,
                pattern_type=pattern.pattern_type,
                pattern_name=pattern.pattern_name,
            )
            day = pd.to_datetime(ts, unit="s", utc=True).strftime("%Y-%m-%d")
            counts["per_day_traded"][day] = \
                counts["per_day_traded"].get(day, 0) + 1
        counts["peak_open"] = max(counts["peak_open"],
                                  len(pos_sim.open_positions))
    return counts


def test_nontrivial_caps_funnel_equivalence():
    """Part B: capped replay partitions the baseline exactly."""
    np.random.seed(42)
    base_time = 1700000000.0
    data = []
    price = 2500.0
    for i in range(500):
        price += np.random.uniform(-1, 1)
        data.append({
            "time": base_time + (i * 300),
            "open": price - 0.5, "high": price + 1.0,
            "low": price - 1.5, "close": price, "spread": 20,
        })
    df = pd.DataFrame(data)

    reset_pattern_state()
    patterns = detect_patterns_closed_candles_only(
        candles=df, symbol="XAUUSD", point=0.01, timeframe="M5"
    )
    assert len(patterns) == 274, \
        f"fixture drift: expected 274 patterns, got {len(patterns)}"

    base = _replay(_caps_removed_limits(), df, patterns)
    cap = _replay(_nontrivial_limits(), df, patterns)

    # Upstream gates (PATTERN_DETECTION + RISK_EVALUATION) are
    # state-independent (evaluate_risk's daily check is disabled;
    # MAX_CONSECUTIVE_LOSSES=999999999 is never reached), so both runs
    # must REACH the SIM gate for the same patterns: 274/274 (0 RISK fails).
    assert base["reached_sim"] == cap["reached_sim"] == 274, \
        f"upstream gates diverged: base={base} cap={cap}"

    # Baseline (caps removed): SIM never rejects; hand arithmetic
    # 274 = 247 TRADED + 27 SPREAD/SESSION/DIR rejects; 247 = 129+118.
    assert base["sim_rejected"] == 0, base
    assert base["traded"] == 247 and base["failed_later"] == 27, base
    assert base["traded"] + base["failed_later"] == base["reached_sim"], base
    assert base["per_day_traded"] == {"2023-11-15": 129,
                                      "2023-11-16": 118}, base

    # Capped run partition: 274 = 263 SIM rejections + 10 TRADED + 1.
    assert cap["sim_rejected"] == 263 and cap["traded"] == 10, cap
    assert cap["failed_later"] == 1, cap
    assert (cap["sim_rejected"] + cap["traded"] + cap["failed_later"]
            == cap["reached_sim"]), cap

    # Caps bind (non-vacuous); only the two configured caps may reject
    # (live cooldown/loss-pause limits are 0 / 999999999 and never fire).
    assert cap["sim_rejected"] > 0, "caps never bound - test is vacuous"
    assert 0 < cap["traded"] < base["traded"], cap
    allowed = {"DAILY_LIMIT", "MAX_OPEN"}
    assert set(cap["sim_reasons"]) <= allowed, cap["sim_reasons"]

    # Daily cap: exactly 5 trades on each fixture trading day; open cap <=2.
    assert cap["per_day_traded"] == {"2023-11-15": 5,
                                     "2023-11-16": 5}, cap["per_day_traded"]
    assert cap["peak_open"] <= 2, cap["peak_open"]

    print(f"[PASS] Non-trivial caps funnel equivalence: reached_sim="
          f"{cap['reached_sim']} == baseline {base['reached_sim']}; "
          f"capped {cap['sim_rejected']} rejected + {cap['traded']} traded "
          f"+ {cap['failed_later']} later-fail == {cap['reached_sim']}")
    print(f"       rejections by reason={cap['sim_reasons']} "
          f"per-day traded={dict(sorted(cap['per_day_traded'].items()))} "
          f"peak_open={cap['peak_open']}")


if __name__ == "__main__":
    test_nontrivial_caps_can_trade_sequence()
    test_nontrivial_caps_funnel_equivalence()


