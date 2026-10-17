"""
Audit Runner

Main orchestrator for pattern detection audit.
Runs with MT5 BLOCKED and simulated clock.
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# BLOCK MT5 IMMEDIATELY
sys.modules["MetaTrader5"] = None
print("[AUDIT] MT5 access BLOCKED. Any MT5 import will fail.")

from scripts.pattern_audit.pattern_detector import (
    detect_patterns_closed_candles_only,
    reset_pattern_state
)
from scripts.pattern_audit.live_state_simulator import (
    SimulatedClock,
    simulate_state_at_bar,
    estimate_spread_percentile
)
from scripts.pattern_audit.funnel_logger import FunnelLogger
from scripts.pattern_audit.position_simulator import PositionSimulator
from scripts.pattern_audit.risk_limits import read_audit_limits
from scripts.pattern_audit.report_generator import (
    generate_funnel_table,
    generate_daily_table,
    generate_detection_report,
    print_detection_report
)


def load_historical_data(symbol: str, timeframe: str, data_dir: str = "d:/Trading/Aegis_Gold/data", months: int = 12) -> pd.DataFrame:
    """
    Load historical data from CSV or generate sample data.
    
    For now, generates sample data. In production, would load from:
    - Pre-saved MT5 data export (CSV)
    - Database
    - Pickle file
    
    Args:
        symbol: Trading symbol
        timeframe: "M5", "M15", or "H1"
        data_dir: Directory containing historical data
    
    Returns:
        DataFrame with columns: time, open, high, low, close, spread
    """
    # Try to load from CSV first
    csv_path = Path(data_dir) / f"{symbol}_{timeframe}_history.csv"
    
    if csv_path.exists():
        print(f"[AUDIT] Loading historical data from {csv_path}")
        df = pd.read_csv(csv_path)
        
        # Ensure required columns
        required = ['time', 'open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required):
            raise ValueError(f"CSV missing required columns: {required}")
        
        # Convert time to Unix timestamp if needed
        if df['time'].dtype == 'object':
            df['time'] = pd.to_datetime(df['time']).astype(int) / 10**9
        
        return df
    
    # If no CSV, generate sample data (DEMO MODE)
    print(f"[WARN] No historical data found at {csv_path}")
    print(f"[WARN] Generating sample data for DEMO (not for production use)")
    
    return generate_sample_data(symbol, timeframe, months=months)


def generate_sample_data(symbol: str, timeframe: str, months: int = 12) -> pd.DataFrame:
    """
    Generate sample OHLC data for testing.
    
    WARNING: This is for testing infrastructure only.
    Production audit MUST use real historical data.
    """
    # Calculate number of bars
    bars_per_hour = {"M5": 12, "M15": 4, "H1": 1}
    hours_per_month = 30 * 24
    total_bars = months * hours_per_month * bars_per_hour.get(timeframe, 12)
    
    # Generate timestamps (going backwards from now)
    end_time = datetime.now(timezone.utc).timestamp()
    minutes_per_bar = {"M5": 5, "M15": 15, "H1": 60}
    bar_duration = minutes_per_bar.get(timeframe, 5) * 60
    
    timestamps = [end_time - (i * bar_duration) for i in range(total_bars, 0, -1)]
    
    # Generate price data (random walk around 2500 for XAUUSD)
    base_price = 2500.0
    prices = [base_price]
    
    for _ in range(total_bars - 1):
        change = np.random.normal(0, 2.0)  # 2 point std dev
        prices.append(prices[-1] + change)
    
    # Generate OHLC
    data = []
    for i, timestamp in enumerate(timestamps):
        close = prices[i]
        volatility = 5.0
        
        high = close + abs(np.random.normal(0, volatility))
        low = close - abs(np.random.normal(0, volatility))
        open_price = low + np.random.uniform(0, high - low)
        
        # Ensure OHLC relationships
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        
        # Generate spread (15-35 points for XAUUSD)
        spread = int(np.random.uniform(15, 35))
        
        data.append({
            'time': timestamp,
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'spread': spread
        })
    
    df = pd.DataFrame(data)
    print(f"[AUDIT] Generated {len(df)} bars of sample data ({months} months, {timeframe})")
    
    return df


def run_audit(
    symbol: str = "XAUUSD",
    months: int = 12,
    broker_offset_hours: float = None,
    uses_dst: bool = False
):
    """
    Main audit orchestrator.
    
    Args:
        symbol: Trading symbol
        months: Target months of history (actual may differ based on data available)
        broker_offset_hours: UTC offset of broker (e.g., 2.0 for UTC+2), None = UNCONFIRMED
        uses_dst: Whether broker uses DST
    """
    print("\n" + "="*60)
    print("PATTERN AUDIT - STARTING")
    print("="*60)
    print(f"Symbol: {symbol}")
    print(f"Target History: {months} months")
    print(f"Broker Offset: {broker_offset_hours if broker_offset_hours else 'UNCONFIRMED'}")
    print("="*60 + "\n")
    
    # Step 1: Reset global state
    print("[1/6] Resetting global state...")
    reset_pattern_state()
    
    # Step 2: Load historical data
    print(f"[2/6] Loading historical data...")
    data_m5 = load_historical_data(symbol, "M5", months=months)
    
    # Calculate actual history length
    if len(data_m5) > 0:
        time_range = data_m5['time'].max() - data_m5['time'].min()
        actual_months = time_range / (30 * 24 * 3600)
        print(f"       Loaded {len(data_m5)} M5 bars ({actual_months:.1f} months actual)")
    else:
        print("[ERROR] No data loaded!")
        return
    
    # Step 3: Estimate spread percentile if spread column exists
    print(f"[3/6] Analyzing spread data...")
    if 'spread' in data_m5.columns:
        estimated_spread = estimate_spread_percentile(data_m5, percentile=95.0)
        print(f"       95th percentile spread: {estimated_spread:.1f} points")
    else:
        estimated_spread = 25.0
        print(f"       No spread column - using default: {estimated_spread} points")
    
    # Step 4: Detect patterns
    print(f"[4/6] Detecting patterns on closed candles...")
    point = 0.01 if symbol == "XAUUSD" else 0.00001
    
    patterns_m5 = detect_patterns_closed_candles_only(
        candles=data_m5,
        symbol=symbol,
        point=point,
        timeframe="M5"
    )
    
    print(f"       Detected {len(patterns_m5)} M5 patterns")
    
    # Step 5: Run through funnel
    print(f"[5/6] Running patterns through decision gates...")
    
    funnel_logger = FunnelLogger()
    
    # SIMULATED position state (NOT real RiskManager.can_trade).
    # Limits READ from real live config (file:line shown in report).
    limits = read_audit_limits()
    print('    SIMULATED limits (read-only from live files):')
    for _k in ('MAX_DAILY_TRADES', 'MAX_OPEN_TRADES',
               'MAX_CONSECUTIVE_LOSSES', 'COOLDOWN_AFTER_LOSS_SEC',
               'COOLDOWN_AFTER_CONSEC_LOSSES'):
        _lv = limits.get(_k)
        print(f'      {_k}={_lv.value} <- {_lv.source}')
    pos_sim = PositionSimulator(symbol, point, limits=limits)
    pos_sim.max_hold_bars = 30

    # Bar-driven replay: settle open positions on each bar, then gate
    # patterns at that bar; fills at NEXT-BAR OPEN (no look-ahead).
    daily_rows = []
    cur_day = None
    day_detected = 0
    day_opened = 0
    n = len(data_m5)
    by_idx = {}
    for _p in patterns_m5:
        by_idx.setdefault(int(_p.candle_index), []).append(_p)
    eod_open = {}
    for bi in range(n):
        _row = data_m5.iloc[bi]
        _t = _row["time"]
        _ts = float(_t.timestamp()) if hasattr(_t, "timestamp") else float(_t)
        pos_sim.check_daily_reset(_ts)
        _day = datetime.fromtimestamp(_ts, tz=timezone.utc).strftime("%Y-%m-%d")
        if cur_day is None:
            cur_day = _day
        if _day != cur_day:
            daily_rows.append({"day": cur_day, "patterns_detected": day_detected,
                               "trades_opened": day_opened,
                               "open_positions_eod": eod_open.get(cur_day, 0)})
            cur_day, day_detected, day_opened = _day, 0, 0
        if pos_sim.open_positions:
            pos_sim.update_positions(_row, _ts, bar_index=bi)
        for pattern in by_idx.get(bi, []):
            day_detected += 1
            simulated_state = simulate_state_at_bar(
                bar_timestamp=pattern.timestamp,
                symbol=symbol,
                candles=data_m5,
                bar_index=pattern.candle_index,
                estimated_spread=estimated_spread,
                daily_trades_so_far=pos_sim.daily_trades,
                consecutive_losses_so_far=pos_sim.consecutive_losses,
                broker_offset_hours=broker_offset_hours,
                uses_dst=uses_dst,
            )
            simulated_clock = SimulatedClock(simulated_state.candle_time_utc)
            record = funnel_logger.log_pattern_through_gates(
                pattern=pattern,
                simulated_state=simulated_state,
                symbol=symbol,
                point=point,
                risk_mgr=pos_sim,
                simulated_clock=simulated_clock,
            )
            if record.final_outcome == "TRADED":
                _fi = min(int(pattern.candle_index) + 1, n - 1)
                _fill = data_m5.iloc[_fi]
                _ft = _fill["time"]
                _fts = float(_ft.timestamp()) if hasattr(_ft, "timestamp") else float(_ft)
                pos_sim.open_position(
                    direction=pattern.direction,
                    entry_price=float(_fill["open"]),
                    stop_loss=float(pattern.stop_loss),
                    take_profit=float(pattern.take_profit),
                    lot_size=0.01,
                    open_time=_fts,
                    open_bar=_fi,
                    pattern_type=pattern.pattern_type,
                    pattern_name=pattern.pattern_name,
                )
                day_opened += 1
        eod_open[cur_day] = len(pos_sim.open_positions)
    if cur_day is not None:
        daily_rows.append({"day": cur_day, "patterns_detected": day_detected,
                           "trades_opened": day_opened,
                           "open_positions_eod": len(pos_sim.open_positions)})
    if pos_sim.open_positions and n:
        _last = data_m5.iloc[-1]
        _lt = _last["time"]
        _lts = float(_lt.timestamp()) if hasattr(_lt, "timestamp") else float(_lt)
        for _t in list(pos_sim.open_positions):
            pos_sim.close_position(_t, float(_last["close"]), _lts, "TIME")
        if daily_rows:
            daily_rows[-1]["open_positions_eod"] = 0
    print(f"       Logged {len(funnel_logger.records)} patterns through gates")
    
    # Step 6: Generate reports
    print(f"[6/6] Generating reports...")
    
    # Generate funnel table
    funnel_df = generate_funnel_table(
        funnel_logger.records,
        output_path="d:/Trading/Aegis_Gold/data/pattern_audit_funnel_table.csv"
    )
    
    # Generate detection report
    report = generate_detection_report(
        funnel_logger.records,
        history_months=actual_months
    )
    
    # Print report
    print_detection_report(report)
    
    daily_df = generate_daily_table(
        daily_rows,
        output_path="d:/Trading/Aegis_Gold/data/pattern_audit_daily.csv",
    )
    print("\nPER-DAY TABLE (patterns detected / trades opened / open EOD):")
    print(daily_df.to_string(index=False) if len(daily_df) else "(empty)")

    # Print funnel table
    print("\nFUNNEL TABLE (SIM gate = simulated limits; counts per reason):")
    print(funnel_df.to_string(index=False))

    print("\nSIM gate limits (value <- source file:line):")
    for _k, _lv in sorted(limits.items()):
        print(f"  {_k}={_lv.value} <- {_lv.source}")
    from scripts.pattern_audit.position_simulator import UNCONFIRMED_REAL_GATES
    print("\nReal RiskManager.can_trade() conditions NOT evaluated here "
          "(UNCONFIRMED - need MT5/account state):")
    for _g in UNCONFIRMED_REAL_GATES:
        print(f"  - UNCONFIRMED: {_g}")
    
    print("\n" + "="*60)
    print("AUDIT COMPLETE - STOPPING HERE")
    print("="*60)
    print("\nNext steps:")
    print("1. Review funnel table above")
    print("2. Provide broker offset if sessions are UNCONFIRMED")
    print("3. Approve funnel before proceeding to fixes")
    print("\n" + "="*60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run pattern detection audit")
    parser.add_argument("--symbol", default="XAUUSD", help="Trading symbol")
    parser.add_argument("--months", type=int, default=12, help="Target months of history")
    parser.add_argument("--broker-offset", type=float, default=None, help="Broker UTC offset (e.g., 2.0)")
    parser.add_argument("--dst", action="store_true", help="Broker uses DST")
    
    args = parser.parse_args()
    
    run_audit(
        symbol=args.symbol,
        months=args.months,
        broker_offset_hours=args.broker_offset,
        uses_dst=args.dst
    )
