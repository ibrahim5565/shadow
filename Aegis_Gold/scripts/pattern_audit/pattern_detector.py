"""
Pattern Detector Wrapper

Wraps existing pattern detection functions for audit use.
Calls real get_pattern_entry_signal() - NO copied logic.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List
import pandas as pd
import numpy as np


@dataclass
class PatternDetectionResult:
    """Result of pattern detection on a single closed candle."""
    timestamp: float  # Unix timestamp of candle
    timeframe: str  # "M5", "M15", "H1"
    pattern_type: str  # "CANDLESTICK", "SMC_BOS", "SMC_CHOCH", etc.
    pattern_name: str  # "Bullish Engulfing", "BOS_Bullish", etc.
    direction: str  # "BUY", "SELL", "HOLD"
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    risk_reward: float
    candle_index: int  # Bar index in data for no-look-ahead verification


def detect_patterns_closed_candles_only(
    candles: pd.DataFrame,
    symbol: str,
    point: float,
    timeframe: str = "M5"
) -> List[PatternDetectionResult]:
    """
    Detect patterns on CLOSED candles only.
    
    Calls brain.brain.get_pattern_entry_signal() directly - NO copied logic.
    
    Args:
        candles: Historical OHLC data with 'time', 'open', 'high', 'low', 'close'
        symbol: Trading symbol
        point: Point size for symbol (0.01 for XAUUSD)
        timeframe: Timeframe label for reporting
    
    Returns:
        List of detected patterns (one per closed candle with pattern found)
    """
    from brain.brain import get_pattern_entry_signal
    
    results = []
    
    # Ensure we have enough data
    if len(candles) < 10:
        return results
    
    # Gateway inputs are already closed-candle-only (MT5 start_pos=1).
    # Do not drop the newest supplied bar a second time.
    closed_candles = candles
    
    for i in range(len(closed_candles)):
        # Get window up to and including current bar
        # Pattern detection needs context (e.g., previous bars for patterns)
        window_start = max(0, i - 50)  # 50-bar lookback window
        window = closed_candles.iloc[window_start:i+1]
        
        if len(window) < 2:
            continue
        
        try:
            # Call real pattern detection function
            direction, pattern_entry = get_pattern_entry_signal(
                candles=window,
                point=point,
                symbol=symbol,
                is_closed_only=True  # Tell function data is already closed-only
            )
            
            # Skip if no pattern detected
            if direction == "HOLD" or pattern_entry.pattern_name in ["NONE", "INSUFFICIENT_DATA"]:
                continue
            
            # Get candle timestamp
            candle_time = closed_candles.iloc[i]['time']
            if isinstance(candle_time, pd.Timestamp):
                candle_time = candle_time.timestamp()
            elif not isinstance(candle_time, (int, float)):
                candle_time = float(candle_time)
            
            # Determine pattern type category
            pattern_name_upper = pattern_entry.pattern_name.upper()
            if "BOS" in pattern_name_upper or "BREAK" in pattern_name_upper:
                pattern_type = "SMC_BOS"
            elif "CHOCH" in pattern_name_upper or "CHANGE" in pattern_name_upper:
                pattern_type = "SMC_CHOCH"
            else:
                pattern_type = "CANDLESTICK"
            
            result = PatternDetectionResult(
                timestamp=candle_time,
                timeframe=timeframe,
                pattern_type=pattern_type,
                pattern_name=pattern_entry.pattern_name,
                direction=direction,
                entry_price=pattern_entry.entry_price,
                stop_loss=pattern_entry.stop_loss,
                take_profit=pattern_entry.take_profit,
                confidence=pattern_entry.confidence,
                risk_reward=pattern_entry.risk_reward,
                candle_index=i
            )
            
            results.append(result)
            
        except Exception as e:
            # Log but continue (don't let one bad bar stop entire audit)
            print(f"[WARN] Pattern detection failed at bar {i}: {e}")
            continue
    
    return results


def reset_pattern_state():
    """
    Reset global pattern detection state.
    
    Clears:
    - brain.pattern_recognition._pattern_engine singleton
    - brain.brain._decide_impl function attributes
    """
    import brain.pattern_recognition
    from brain.brain import _decide_impl
    
    # Reset pattern engine singleton
    brain.pattern_recognition._pattern_engine = None
    
    # Clear _decide_impl function attributes (guard each)
    if hasattr(_decide_impl, "_analyzed_candles"):
        delattr(_decide_impl, "_analyzed_candles")
    if hasattr(_decide_impl, "_traded_candles"):
        delattr(_decide_impl, "_traded_candles")
    if hasattr(_decide_impl, "_processed_candles"):
        delattr(_decide_impl, "_processed_candles")
    
    print("[AUDIT] Pattern detection state reset.")
