"""
Aegis-Gold v5.0 — Pure Python Indicators
No TA-Lib dependency needed.
"""

def EMA(prices: list[float], period: int) -> list[float]:
    """Calculates Exponential Moving Average"""
    if not prices or len(prices) < period:
        return []
        
    k = 2 / (period + 1)
    result = [prices[0]]
    for p in prices[1:]:
        result.append(p * k + result[-1] * (1 - k))
        
    # To align with array lengths, we often pad the beginning or just return the list.
    # For simplicity, returning the EMA array. Note that early values are inaccurate until period.
    return result

def SMA(prices: list[float], period: int) -> list[float]:
    """Simple Moving Average"""
    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(prices[i]) # Fallback
        else:
            result.append(sum(prices[i-period+1:i+1]) / period)
    return result

def TR(high: list[float], low: list[float], close: list[float]) -> list[float]:
    """Calculates True Range"""
    tr = [high[0] - low[0]]
    for i in range(1, len(high)):
        tr.append(max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1])
        ))
    return tr

def ATR(high: list[float], low: list[float], close: list[float], period: int = 14) -> list[float]:
    """Average True Range (using EMA smoothing)"""
    tr = TR(high, low, close)
    return EMA(tr, period)

def ADX(high: list[float], low: list[float], close: list[float], period: int = 14) -> list[float]:
    """Calculates Average Directional Index"""
    if len(high) < period + 1:
        return [0.0] * len(high)
        
    tr = TR(high, low, close)
    
    plus_dm = [0.0]
    minus_dm = [0.0]
    
    for i in range(1, len(high)):
        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]
        
        if up_move > down_move and up_move > 0:
            plus_dm.append(up_move)
        else:
            plus_dm.append(0.0)
            
        if down_move > up_move and down_move > 0:
            minus_dm.append(down_move)
        else:
            minus_dm.append(0.0)
            
    # Smooth them using EMA as requested by the prompt algorithm approximation
    atr = EMA(tr, period)
    smooth_plus_dm = EMA(plus_dm, period)
    smooth_minus_dm = EMA(minus_dm, period)
    
    plus_di = []
    minus_di = []
    dx = []
    
    for i in range(len(high)):
        if atr[i] == 0:
            plus_di.append(0.0)
            minus_di.append(0.0)
        else:
            plus_di.append(100 * smooth_plus_dm[i] / atr[i])
            minus_di.append(100 * smooth_minus_dm[i] / atr[i])
            
        if plus_di[i] + minus_di[i] == 0:
            dx.append(0.0)
        else:
            dx.append(100 * abs(plus_di[i] - minus_di[i]) / (plus_di[i] + minus_di[i]))
            
    adx = EMA(dx, period)
    return adx

def RSI(close: list[float], period: int = 14) -> list[float]:
    """Relative Strength Index"""
    if len(close) < period:
        return [50.0] * len(close)
        
    gains = []
    losses = []
    
    for i in range(1, len(close)):
        diff = close[i] - close[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))
            
    # Calculate initial averages
    avg_gain = sum(gains[:period]) / period if gains else 0
    avg_loss = sum(losses[:period]) / period if losses else 0
    
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    initial_rsi = 100 - (100 / (1 + rs))
    rsi = [initial_rsi] * period # Pad early values
    rsi.append(initial_rsi)
    
    for i in range(period, len(close) - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi.append(100 - (100 / (1 + rs)))
        
    return rsi
