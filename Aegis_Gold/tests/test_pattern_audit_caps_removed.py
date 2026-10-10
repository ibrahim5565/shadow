"""
Test: Caps-Removed Equivalence (Task 3)

With SIM caps removed (daily/open/loss caps = 10**9, cooldowns = 0,
time stop disabled), the SIMULATED_POSITION_LIMITS gate must reject
NOTHING, so:

    TRADED  ==  patterns passing all OTHER gates

Positions are still opened after each TRADED pattern (next-bar fill,
runner-style) so open-position/daily pressure exists and would reject
if caps were active - proving the equivalence holds under load.
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


def _caps_removed_limits() -> dict:
    """Real config limits with every cap removed (audit equivalence run)."""
    limits = read_audit_limits()
    huge = 10 ** 9
    for name in ("MAX_DAILY_TRADES", "MAX_OPEN_TRADES",
                 "MAX_CONSECUTIVE_LOSSES", "TIME_STOP_BASE_SEC"):
        limits[name] = LimitValue(name, huge, "test: caps removed")
    for name in ("COOLDOWN_AFTER_LOSS_SEC", "COOLDOWN_AFTER_CONSEC_LOSSES"):
        limits[name] = LimitValue(name, 0, "test: caps removed")
    return limits


def test_caps_removed_equivalence():
    np.random.seed(42)
    base_time = 1700000000.0
    bar_duration = 300

    data = []
    price = 2500.0
    for i in range(500):
        price += np.random.uniform(-1, 1)
        data.append({
            "time": base_time + (i * bar_duration),
            "open": price - 0.5,
            "high": price + 1.0,
            "low": price - 1.5,
            "close": price,
            "spread": 20,
        })
    df = pd.DataFrame(data)
    n = len(df)

    reset_pattern_state()
    patterns = detect_patterns_closed_candles_only(
        candles=df, symbol="XAUUSD", point=0.01, timeframe="M5"
    )
    if len(patterns) == 0:
        print("[SKIP] No patterns detected - cannot test caps equivalence")
        return

    pos_sim = PositionSimulator("XAUUSD", 0.01, limits=_caps_removed_limits())
    funnel = FunnelLogger()

    traded = 0
    other_gates_pass = 0
    sim_rejected = 0
    opened = 0

    for pattern in sorted(patterns, key=lambda p: p.candle_index):
        bi = int(pattern.candle_index)
        row = df.iloc[bi]
        ts = float(row["time"])

        # Runner-style: settle open positions on this bar first.
        pos_sim.check_daily_reset(ts)
        if pos_sim.open_positions:
            pos_sim.update_positions(row, ts, bar_index=bi)

        state = simulate_state_at_bar(
            bar_timestamp=pattern.timestamp,
            symbol="XAUUSD",
            candles=df,
            bar_index=bi,
            estimated_spread=25.0,
            daily_trades_so_far=pos_sim.daily_trades,
            consecutive_losses_so_far=pos_sim.consecutive_losses,
            broker_offset_hours=None,
        )
        record = funnel.log_pattern_through_gates(
            pattern=pattern,
            simulated_state=state,
            symbol="XAUUSD",
            point=0.01,
            risk_mgr=pos_sim,
            simulated_clock=SimulatedClock(state.candle_time_utc),
        )

        other_pass = all(
            g.passed for g in record.gates if g.gate_name != SIM_GATE
        )
        if other_pass:
            other_gates_pass += 1
        if record.rejection_gate == SIM_GATE:
            sim_rejected += 1
            print(f"  [FAIL] SIM gate rejected: {record.final_outcome} "
                  f"({record.rejection_reason})")
        if record.final_outcome == "TRADED":
            traded += 1
            # Next-bar-open fill (same as runner).
            fi = min(bi + 1, n - 1)
            fill = df.iloc[fi]
            pos_sim.open_position(
                direction=pattern.direction,
                entry_price=float(fill["open"]),
                stop_loss=float(pattern.stop_loss),
                take_profit=float(pattern.take_profit),
                lot_size=0.01,
                open_time=float(fill["time"]),
                open_bar=fi,
                pattern_type=pattern.pattern_type,
                pattern_name=pattern.pattern_name,
            )
            opened += 1

        assert (record.final_outcome == "TRADED") == other_pass, (
            f"Equivalence broken at bar {bi}: TRADED="
            f"{record.final_outcome == 'TRADED'} other_gates_pass="
            f"{other_pass} rejection={record.rejection_gate}"
        )

    assert sim_rejected == 0, (
        f"SIM gate rejected {sim_rejected} patterns with caps removed"
    )
    assert traded == other_gates_pass, (
        f"TRADED ({traded}) != other-gate-pass ({other_gates_pass})"
    )
    # The test must exercise real load on the simulator, not be vacuous.
    assert opened > 0, "No positions opened - equivalence test is vacuous"
    assert pos_sim.daily_trades > 0 or pos_sim.closed_positions, \
        "No daily trade pressure was exercised"

    print(f"[PASS] Caps-removed equivalence: TRADED ({traded}) == "
          f"patterns passing other gates ({other_gates_pass})")
    print(f"       Patterns={len(patterns)} SIM-gate rejections={sim_rejected} "
          f"positions opened={opened} open at end="
          f"{len(pos_sim.open_positions)} closed={len(pos_sim.closed_positions)}")


if __name__ == "__main__":
    test_caps_removed_equivalence()
