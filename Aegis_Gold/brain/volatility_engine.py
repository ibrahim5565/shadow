"""
ANTIGRAVITY OMEGA — Local Volatility Engine
Evaluates market ATR ratios to filter news spikes and dead markets locally.
"""
import logging
import numpy as np
from brain.indicators import ATR

logger = logging.getLogger("aegis.omega.volatility")

class VolatilityEngine:
    def __init__(self):
        logger.info("Local OMEGA Volatility Engine initialized.")

    def analyze(self, candles_m5, point, max_ratio_limit=3.0) -> dict:
        """
        Analyzes volatility ratio using ATR smoothing.
        Filters news spikes and tightly ranging markets.
        """
        if len(candles_m5) < 30:
            return {
                "volatility_score": 50,
                "volatility_state": "NORMAL",
                "news_spike_detected": False,
                "low_volatility": False,
                "reason": "Not enough candle history"
            }

        # Standardize rates format
        try:
            highs = [c['high'] for c in candles_m5]
            lows = [c['low'] for c in candles_m5]
            closes = [c['close'] for c in candles_m5]
        except TypeError:
            highs = [c[2] for c in candles_m5]
            lows = [c[3] for c in candles_m5]
            closes = [c[4] for c in candles_m5]

        atr_series = ATR(highs, lows, closes, 14)
        if not atr_series or len(atr_series) < 5:
            return {
                "volatility_score": 50,
                "volatility_state": "NORMAL",
                "news_spike_detected": False,
                "low_volatility": False,
                "reason": "ATR computation failed"
            }

        curr_atr = atr_series[-1]
        
        # Historical baseline: average ATR of the last 30 candles (excluding current)
        avg_atr = np.mean(atr_series[-30:-1]) if len(atr_series) >= 30 else atr_series[0]
        if avg_atr <= 0:
            avg_atr = 0.0001

        volatility_ratio = curr_atr / avg_atr

        news_spike_detected = volatility_ratio > max_ratio_limit
        low_volatility = volatility_ratio < 0.40

        volatility_state = "NORMAL"
        volatility_score = 50

        if news_spike_detected:
            volatility_state = "VOLATILE"
            volatility_score = 90
            reason = f"Abnormal volatility spike ({volatility_ratio:.2f}x average ATR)"
        elif low_volatility:
            volatility_state = "COMPRESSED"
            volatility_score = 15
            reason = f"Compressed low-volatility range ({volatility_ratio:.2f}x average ATR)"
        else:
            volatility_state = "NORMAL"
            volatility_score = int(volatility_ratio * 50)
            volatility_score = min(75, max(30, volatility_score))
            reason = f"Healthy volatility regime ({volatility_ratio:.2f}x average ATR)"

        return {
            "volatility_score": int(volatility_score),
            "volatility_state": volatility_state,
            "news_spike_detected": news_spike_detected,
            "low_volatility": low_volatility,
            "volatility_ratio": round(volatility_ratio, 2),
            "reason": reason
        }
