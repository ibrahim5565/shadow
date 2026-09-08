"""
ANTIGRAVITY OMEGA — Local Trend Detector Engine
Computes multi-timeframe trend alignment using EMA 9/21 and ADX.
"""
import logging
from brain.indicators import EMA, ADX

logger = logging.getLogger("aegis.omega.trend")

class TrendDetector:
    def __init__(self):
        logger.info("Local OMEGA Trend Detector initialized.")

    def analyze(self, candles_m5, candles_m1) -> dict:
        """
        Analyzes trend using M5 (Confirmation) and M1 (Entry) timeframes.
        Returns a dict with trend metrics.
        """
        # Ensure we have enough candles
        if len(candles_m5) < 30 or len(candles_m1) < 30:
            return {
                "trend": "RANGING",
                "trend_score": 0,
                "m5_trend": "NONE",
                "m1_trend": "NONE",
                "adx_m5": 0.0,
                "reason": "Insufficent candles"
            }

        from brain.candle_utils import parse_hlc
        highs_m5, lows_m5, closes_m5 = parse_hlc(candles_m5)
        highs_m1, lows_m1, closes_m1 = parse_hlc(candles_m1)

        # Indicator Calibrations
        ema9_m5 = EMA(closes_m5, 9)
        ema21_m5 = EMA(closes_m5, 21)
        adx_m5 = ADX(highs_m5, lows_m5, closes_m5, 14)

        ema9_m1 = EMA(closes_m1, 9)
        ema21_m1 = EMA(closes_m1, 21)
        adx_m1 = ADX(highs_m1, lows_m1, closes_m1, 14)

        curr_adx_m5 = adx_m5[-1] if adx_m5 else 0.0
        curr_adx_m1 = adx_m1[-1] if adx_m1 else 0.0

        # M5 Trend
        if ema9_m5[-1] > ema21_m5[-1]:
            m5_trend = "BULLISH"
        elif ema9_m5[-1] < ema21_m5[-1]:
            m5_trend = "BEARISH"
        else:
            m5_trend = "NONE"

        # M1 Trend
        if ema9_m1[-1] > ema21_m1[-1]:
            m1_trend = "BULLISH"
        elif ema9_m1[-1] < ema21_m1[-1]:
            m1_trend = "BEARISH"
        else:
            m1_trend = "NONE"

        # Overall alignment check
        trend = "RANGING"
        trend_score = 0
        reason = "No strong alignment"

        if m5_trend == "BULLISH" and m1_trend == "BULLISH":
            trend = "TRENDING_UP"
            trend_score = 60
            if curr_adx_m5 > 25:
                trend_score += 20
            if curr_adx_m1 > 25:
                trend_score += 20
            reason = f"Bullish Trend aligned | M5 ADX: {curr_adx_m5:.1f}"
        elif m5_trend == "BEARISH" and m1_trend == "BEARISH":
            trend = "TRENDING_DOWN"
            trend_score = 60
            if curr_adx_m5 > 25:
                trend_score += 20
            if curr_adx_m1 > 25:
                trend_score += 20
            reason = f"Bearish Trend aligned | M5 ADX: {curr_adx_m5:.1f}"
        else:
            trend = "RANGING"
            trend_score = 30
            reason = "Timeframes divergent or crossover occurring"

        # ADX trend filter override
        if curr_adx_m5 < 15:
            trend_score = max(10, trend_score - 30)
            reason += " (Low trend intensity ADX < 15)"

        return {
            "trend": trend,
            "trend_score": int(trend_score),
            "m5_trend": m5_trend,
            "m1_trend": m1_trend,
            "adx_m5": round(curr_adx_m5, 2),
            "adx_m1": round(curr_adx_m1, 2),
            "reason": reason
        }
