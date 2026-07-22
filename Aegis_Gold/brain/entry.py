"""
Layer C: Entry Timing 
"""
from dataclasses import dataclass
from brain.indicators import RSI
from config import settings as cfg

@dataclass
class EntryState:
    timing_score: int
    score: int
    signal: str
    reason: str

def analyze_entry(ticks, candles, direction: str) -> EntryState:
    """
    Analyzes exact entry timing based on candlestick confirmation and RSI momentum.
    """
    if len(candles) < 15:
        return EntryState(0, 0, "NO_SIGNAL", "Not enough data")
        
    try:
        opens = [float(c['open']) for c in candles]
        highs = [float(c['high']) for c in candles]
        lows = [float(c['low']) for c in candles]
        closes = [float(c['close']) for c in candles]
    except TypeError:
        opens = [float(c[1]) for c in candles]
        highs = [float(c[2]) for c in candles]
        lows = [float(c[3]) for c in candles]
        closes = [float(c[4]) for c in candles]

    # Candle Pattern Analysis (last completed M5 candle)
    c_open, c_high, c_low, c_close = float(opens[-2]), float(highs[-2]), float(lows[-2]), float(closes[-2])
    prev_open, prev_close = float(opens[-3]), float(closes[-3])
    
    candle_body = abs(c_close - c_open)
    candle_range = c_high - c_low
    candle_range = candle_range if candle_range > 0 else 0.0001
    
    candle_wick_top = c_high - max(c_open, c_close)
    candle_wick_bot = min(c_open, c_close) - c_low
    
    score = 0
    reason = ""
    
    # Neutral/Dangerous Check
    if candle_body < candle_range * 0.1:
        return EntryState(0, 0, "NO_SIGNAL", "Indecision Doji candle")
        
    # Optional Candle Pattern Analysis (Bonus Score)
    if direction == "BUY":
        # Type 1: Strong Bull
        if c_close > c_open and candle_body > candle_range * 0.5:
            score += 20
            reason = "Bull Candle"
        # Type 2: Hammer
        elif candle_wick_bot > candle_body * 1.5 and c_close > c_open:
            score += 25
            reason = "Hammer"
        # Type 3: Engulfing
        elif c_close > prev_open and c_open < prev_close and prev_close < prev_open:
            score += 30
            reason = "Engulfing"
        else:
            score += 10 # Baseline for trend alignment
            reason = "Trend follow"
            
    elif direction == "SELL":
        # Type 1: Strong Bear
        if c_close < c_open and candle_body > candle_range * 0.5:
            score += 20
            reason = "Bear Candle"
        # Type 2: Shooting Star
        elif candle_wick_top > candle_body * 1.5 and c_close < c_open:
            score += 25
            reason = "Shooting Star"
        # Type 3: Engulfing
        elif c_close < prev_open and c_open > prev_close and prev_close > prev_open:
            score += 30
            reason = "Engulfing"
        else:
            score += 10 # Baseline for trend alignment
            reason = "Trend follow"
        
    # RSI Momentum check
    rsi = RSI(closes, cfg.RSI_PERIOD)
    curr_rsi = rsi[-1]
    prev_rsi = rsi[-2]
    
    if direction == "BUY":
        if curr_rsi > 75:
            return EntryState(0, 0, "NO_SIGNAL", "Overbought, reversal risk")
        if 45 < curr_rsi < 65:
            score += 15
        if curr_rsi > 50 and prev_rsi <= 50:
            score += 20
        if 30 < curr_rsi < 45 and prev_rsi <= 30:
            score += 25  # Recovering from oversold
            
    elif direction == "SELL":
        if curr_rsi < 25:
            return EntryState(0, 0, "NO_SIGNAL", "Oversold, reversal risk")
        if 35 < curr_rsi < 55:
            score += 15
        if curr_rsi < 50 and prev_rsi >= 50:
            score += 20
        if 55 < curr_rsi < 70 and prev_rsi >= 70:
            score += 25  # Retreating from overbought
            
    # Velocity factor
    # Since ticks represents tick array over time, we assume ticks list of NamedTuples
    import time
    now = time.time()
    # Mocking ticking due to MT5 tick format complexity.
    ticks_last_10s = len(ticks[-200:]) if len(ticks) >= 200 else len(ticks) # Simplification
    # Ideally we'd map tick 'time_msc' but this is an approximation for structural purpose
    score += 10 # Base velocity assumed
    
    signal = 'ENTRY_SIGNAL' if score >= cfg.MIN_ENTRY_SCORE else 'NO_SIGNAL'
    
    return EntryState(
        timing_score=score,
        score=score,
        signal=signal,
        reason=reason + f" + RSI({curr_rsi:.1f})"
    )
