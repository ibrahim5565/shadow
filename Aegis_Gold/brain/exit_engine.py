"""
ANTIGRAVITY OMEGA — Local Exit Engine
Computes dynamic SL/TP boundaries and scans M1 momentum exhaustion signals for exits.
"""
import logging
from brain.indicators import ATR, RSI

logger = logging.getLogger("aegis.omega.exit")

class ExitEngine:
    def __init__(self):
        logger.info("Local OMEGA Exit Engine initialized.")

    def calculate_targets(self, candles_m5, point, base_tp=20, max_tp=60, base_sl=20, max_sl=40) -> dict:
        """
        Calculates dynamic TP/SL targets using ATR.
        """
        if len(candles_m5) < 14:
            return {"tp": base_tp, "sl": base_sl}

        try:
            highs = [c['high'] for c in candles_m5]
            lows = [c['low'] for c in candles_m5]
            closes = [c['close'] for c in candles_m5]
        except TypeError:
            highs = [c[2] for c in candles_m5]
            lows = [c[3] for c in candles_m5]
            closes = [c[4] for c in candles_m5]

        atr = ATR(highs, lows, closes, 14)
        curr_atr_pts = atr[-1] / point if atr and point > 0 else base_tp

        # TP = ATR-based, capped to max_tp; SL = 0 (managed dynamically)
        tp = min(max_tp, max(base_tp, int(curr_atr_pts * 1.5)))
        sl = 0  # NO STOP LOSS - never close on loss

        return {"tp": tp, "sl": sl}

    def check_exhaustion(self, closes_m1, direction: str) -> dict:
        """
        Scans for momentum exhaustion on M1 candles.
        Triggers early exit on momentum weakness.
        """
        if len(closes_m1) < 14:
            return {"exhaustion_detected": False, "reason": "Not enough M1 data"}

        rsi = RSI(closes_m1, 14)
        curr_rsi = rsi[-1]
        prev_rsi = rsi[-2]

        exhaustion_detected = False
        reason = "Momentum strong"

        if direction == "BUY":
            # Overbought reversion
            if prev_rsi > 70.0 and curr_rsi < 68.0:
                exhaustion_detected = True
                reason = f"Bullish exhaustion | RSI fell from {prev_rsi:.1f} to {curr_rsi:.1f}"
        elif direction == "SELL":
            # Oversold reversion
            if prev_rsi < 30.0 and curr_rsi > 32.0:
                exhaustion_detected = True
                reason = f"Bearish exhaustion | RSI rose from {prev_rsi:.1f} to {curr_rsi:.1f}"

        return {
            "exhaustion_detected": exhaustion_detected,
            "reason": reason
        }
