# ============================================================
# INDICATORS ENGINE — EMA, RSI, ATR, VWAP, Bollinger Bands
# ============================================================

import numpy as np
import pandas as pd
from config import EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    high = df["high"]
    low  = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def calculate_bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    sma   = series.rolling(period).mean()
    std   = series.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, sma, lower


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3
    return (typical * df["volume"]).cumsum() / df["volume"].cumsum()


def calculate_all(df: pd.DataFrame) -> dict:
    """Calculate all indicators and return latest values as dict."""
    close = df["close"]

    ema_fast = calculate_ema(close, EMA_FAST)
    ema_slow = calculate_ema(close, EMA_SLOW)
    rsi      = calculate_rsi(close, RSI_PERIOD)
    atr      = calculate_atr(df, ATR_PERIOD)
    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(close)

    # EMA crossover: 1 = bullish cross, -1 = bearish cross, 0 = no cross
    prev_diff = ema_fast.iloc[-2] - ema_slow.iloc[-2]
    curr_diff = ema_fast.iloc[-1] - ema_slow.iloc[-1]
    if prev_diff < 0 and curr_diff > 0:
        ema_cross = 1
    elif prev_diff > 0 and curr_diff < 0:
        ema_cross = -1
    else:
        ema_cross = 0

    # Trend direction
    trend = "BULLISH" if ema_fast.iloc[-1] > ema_slow.iloc[-1] else "BEARISH"

    # RSI zone
    rsi_val = round(float(rsi.iloc[-1]), 2)
    if rsi_val > 70:
        rsi_zone = "OVERBOUGHT"
    elif rsi_val < 30:
        rsi_zone = "OVERSOLD"
    else:
        rsi_zone = "NEUTRAL"

    # Price vs Bollinger
    price = close.iloc[-1]
    if price > bb_upper.iloc[-1]:
        bb_signal = "ABOVE_UPPER"
    elif price < bb_lower.iloc[-1]:
        bb_signal = "BELOW_LOWER"
    else:
        bb_signal = "INSIDE"

    return {
        "ema_fast"   : round(float(ema_fast.iloc[-1]), 4),
        "ema_slow"   : round(float(ema_slow.iloc[-1]), 4),
        "ema_cross"  : ema_cross,
        "trend"      : trend,
        "rsi"        : rsi_val,
        "rsi_zone"   : rsi_zone,
        "atr"        : round(float(atr.iloc[-1]), 4),
        "bb_upper"   : round(float(bb_upper.iloc[-1]), 4),
        "bb_mid"     : round(float(bb_mid.iloc[-1]), 4),
        "bb_lower"   : round(float(bb_lower.iloc[-1]), 4),
        "bb_signal"  : bb_signal,
        "price"      : round(float(price), 4),
        "spread_ok"  : True,  # Updated dynamically in connector
    }
