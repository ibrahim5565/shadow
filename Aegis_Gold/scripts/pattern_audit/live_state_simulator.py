"""
Live State Simulator for Historical Replay

Simulates time-dependent gate inputs using candle timestamps.
Patches module-level datetime/time references in decision-chain modules only.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class SimulatedState:
    """State snapshot for a single historical bar."""
    spread_points: float
    spread_source: str  # "ACTUAL_HISTORY" | "ESTIMATED"
    session: str  # "LONDON", "NY", "ASIAN", "OVERLAP", "CLOSED"
    daily_trades_count: int
    consecutive_losses: int
    candle_time_utc: float  # Unix timestamp for simulated clock
    simulation_method: str
    confirmed: bool  # False = mark UNCONFIRMED in report


class SimulatedClock:
    """
    Simulated clock for historical replay.
    
    Patches module-level datetime/time references in decision-chain modules ONLY.
    NO global time.time patch - only modules that make trading decisions.
    
    Modules patched:
    - modules.risk_manager (datetime, time)
    - brain.brain (time for _decide_impl candle tracking)
    
    Restored in finally block.
    """
    
    def __init__(self, candle_time_utc: float):
        self.candle_time_utc = candle_time_utc
        self._original_refs = {}
    
    def __enter__(self):
        """Patch module-level references."""
        import modules.risk_manager
        import brain.brain
        from datetime import datetime, timezone
        import time as time_module
        
        # Save original references
        self._original_refs['risk_manager_datetime'] = modules.risk_manager.datetime
        self._original_refs['risk_manager_time'] = modules.risk_manager.time
        self._original_refs['brain_time'] = brain.brain.time
        
        # Create mock datetime module
        class MockDatetime:
            @staticmethod
            def now(tz=None):
                dt = datetime.fromtimestamp(self.candle_time_utc, tz=timezone.utc)
                if tz and tz != timezone.utc:
                    dt = dt.astimezone(tz)
                return dt
            
            # Pass through other datetime methods
            def __getattr__(self, name):
                return getattr(datetime, name)
            
            # Support datetime() constructor
            def __call__(self, *args, **kwargs):
                return datetime(*args, **kwargs)
        
        # Create mock time module
        class MockTime:
            @staticmethod
            def time():
                return self.candle_time_utc
            
            # Pass through other time methods
            def __getattr__(self, name):
                return getattr(time_module, name)
        
        mock_dt = MockDatetime()
        mock_time = MockTime()
        
        # Patch module-level references
        modules.risk_manager.datetime = mock_dt
        modules.risk_manager.time = mock_time
        brain.brain.time = mock_time
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore original references in finally block."""
        import modules.risk_manager
        import brain.brain
        
        try:
            modules.risk_manager.datetime = self._original_refs['risk_manager_datetime']
            modules.risk_manager.time = self._original_refs['risk_manager_time']
            brain.brain.time = self._original_refs['brain_time']
        except Exception as e:
            print(f"[WARN] Failed to restore original time references: {e}")


def estimate_spread_percentile(candles: pd.DataFrame, percentile: float = 95.0) -> float:
    """
    Calculate percentile of spread values from historical data.
    
    Args:
        candles: DataFrame with 'spread' column (points)
        percentile: Percentile to calculate (default 95th)
    
    Returns:
        Spread value at given percentile
    """
    if 'spread' not in candles.columns:
        return 25.0  # Default fallback for XAUUSD
    
    spreads = candles['spread'].values
    spreads = spreads[spreads > 0]  # Filter out zeros
    
    if len(spreads) == 0:
        return 25.0
    
    return float(np.percentile(spreads, percentile))


def assign_session(utc_hour: int) -> str:
    """
    Assign trading session based on UTC hour.
    
    Sessions (UTC):
    - ASIAN: 00:00-08:00
    - LONDON: 08:00-16:00
    - NY: 13:00-21:00
    - OVERLAP: 13:00-16:00 (London + NY)
    - CLOSED: 21:00-00:00 (weekends handled separately)
    
    NOTE: This function uses UTC time AFTER broker offset conversion.
    Session labels marked UNCONFIRMED until user provides broker offset.
    """
    if 13 <= utc_hour < 16:
        return "OVERLAP"
    elif 8 <= utc_hour < 13:
        return "LONDON"
    elif 16 <= utc_hour < 21:
        return "NY"
    elif 0 <= utc_hour < 8:
        return "ASIAN"
    else:
        return "CLOSED"


def simulate_state_at_bar(
    bar_timestamp: float,  # Unix timestamp (broker time, to be converted)
    symbol: str,
    candles: pd.DataFrame,
    bar_index: int,
    estimated_spread: Optional[float] = None,
    daily_trades_so_far: int = 0,
    consecutive_losses_so_far: int = 0,
    broker_offset_hours: Optional[float] = None,
    uses_dst: bool = False
) -> SimulatedState:
    """
    Simulate live state at historical bar.
    
    Args:
        bar_timestamp: Candle timestamp (Unix epoch, broker server time)
        symbol: Trading symbol
        candles: Historical data with 'spread' column if available
        bar_index: Index of current bar
        estimated_spread: Pre-calculated percentile spread (if spread column missing)
        daily_trades_so_far: Simulated daily trade count
        consecutive_losses_so_far: Simulated consecutive losses
        broker_offset_hours: UTC offset of broker (e.g., 2.0 for UTC+2)
        uses_dst: Whether broker uses DST
    
    Returns:
        SimulatedState with all gate inputs
    """
    # Convert broker time to UTC
    if broker_offset_hours is not None:
        # Apply offset (broker time → UTC)
        candle_time_utc = bar_timestamp - (broker_offset_hours * 3600)
        confirmed = True
    else:
        # No offset provided - assume timestamps are already UTC, mark UNCONFIRMED
        candle_time_utc = bar_timestamp
        confirmed = False
    
    # Get spread from history or use estimate
    spread_source = "ACTUAL_HISTORY"
    if 'spread' in candles.columns and bar_index < len(candles):
        spread_pts = float(candles.iloc[bar_index]['spread'])
        if spread_pts <= 0 and estimated_spread is not None:
            spread_pts = estimated_spread
            spread_source = "ESTIMATED"
    elif estimated_spread is not None:
        spread_pts = estimated_spread
        spread_source = "ESTIMATED"
    else:
        spread_pts = 25.0  # Default XAUUSD spread
        spread_source = "ESTIMATED"
    
    # Assign session based on UTC hour
    dt_utc = datetime.fromtimestamp(candle_time_utc, tz=timezone.utc)
    session = assign_session(dt_utc.hour)
    
    return SimulatedState(
        spread_points=spread_pts,
        spread_source=spread_source,
        session=session,
        daily_trades_count=daily_trades_so_far,
        consecutive_losses=consecutive_losses_so_far,
        candle_time_utc=candle_time_utc,
        simulation_method="SIMULATED",
        confirmed=confirmed  # False if no broker offset provided
    )
