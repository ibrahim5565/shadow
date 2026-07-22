"""
ANTIGRAVITY OMEGA — Local Momentum Engine
Analyzes tick speed, tick intervals, acceleration, and M1 breakout momentum.
"""
import logging
import numpy as np

logger = logging.getLogger("aegis.omega.momentum")

class MomentumEngine:
    def __init__(self):
        logger.info("Local OMEGA Momentum Engine initialized.")

    def analyze(self, ticks, candles_m1, point) -> dict:
        """
        Analyzes tick acceleration, ticks-per-second, and M1 candle momentum.
        """
        if len(ticks) < 10 or len(candles_m1) < 10:
            return {
                "strong_momentum": False,
                "momentum_score": 50,
                "breakout_detected": False,
                "tps": 0.0,
                "reason": "Not enough tick/candle data"
            }

        # 1. Tick speed & acceleration
        # Inspect the last 10 ticks for milliseconds interval
        try:
            msc_times = [t['time_msc'] for t in ticks[-10:]]
            intervals = [msc_times[i] - msc_times[i-1] for i in range(1, len(msc_times))]
            avg_interval = np.mean(intervals) if intervals else 500.0
            
            # TPS (Ticks Per Second) calculation in the last 2 seconds
            last_msc = ticks[-1]["time_msc"]
            tps = sum(1 for t in ticks if last_msc - t["time_msc"] <= 1000)
        except Exception:
            avg_interval = 500.0
            tps = 2.0

        # Acceleration factor
        acceleration = 1.0
        if avg_interval < 200.0:  # Fast ticks under 200ms apart
            acceleration = 1.5
        elif avg_interval > 1000.0:  # Slow ticks
            acceleration = 0.5

        # 2. M1 Breakout candle momentum
        try:
            closes = [c['close'] for c in candles_m1]
            highs = [c['high'] for c in candles_m1]
            lows = [c['low'] for c in candles_m1]
        except TypeError:
            closes = [c[4] for c in candles_m1]
            highs = [c[2] for c in candles_m1]
            lows = [c[3] for c in candles_m1]

        # Calculate current M1 range vs average M1 range of past 10 candles
        ranges = [abs(highs[i] - lows[i]) for i in range(len(highs))]
        current_range = ranges[-1]
        avg_range = np.mean(ranges[-10:-1]) if len(ranges) >= 10 else (ranges[-1] if ranges else 0.0001)
        if avg_range <= 0:
            avg_range = 0.00001
        
        range_ratio = current_range / avg_range

        # Compute combined momentum score (0 to 100)
        momentum_score = 50.0
        if range_ratio > 1.2:
            momentum_score += 15.0
        if tps > 5:
            momentum_score += 15.0
        if acceleration > 1.0:
            momentum_score += 10.0
        
        # Upper limits
        momentum_score = min(100.0, momentum_score)

        strong_momentum = momentum_score >= 60.0
        breakout_detected = range_ratio >= 1.5 and tps >= 8

        reason = f"Normal momentum | TPS: {tps} | range_ratio: {range_ratio:.2f}"
        if breakout_detected:
            reason = f"⚡ BREAKOUT BREAKOUT DETECTED | High TPS ({tps}) | Range Ratio: {range_ratio:.2f}"
        elif strong_momentum:
            reason = f"Strong momentum | TPS: {tps} | Accel: {acceleration:.1f}"

        return {
            "strong_momentum": strong_momentum,
            "momentum_score": int(momentum_score),
            "breakout_detected": breakout_detected,
            "tps": float(tps),
            "reason": reason
        }
