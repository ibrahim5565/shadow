"""
LTF Trigger Engine for Aegis-Gold v6.0.

Detects M5/M1 local triggers:
    - Liquidity sweep + reclaim
    - Local BOS
    - OB reaction
    - FVG fill
    - Breakout + retest
    - Engulfing

Produces a TriggerResult with signal_type, trigger_score, entry_price, stop_loss.
"""

from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger("aegis.ltf_trigger")


@dataclass
class TriggerResult:
    """Result of LTF trigger detection."""
    valid: bool = False
    signal_type: str = "NONE"
    trigger_score: float = 0.0        # 0.0–1.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    reason: str = ""


def _extract_series(candles, key_name: str, tuple_idx: int) -> List[float]:
    """Extract a numeric series from candles (dict, object, or tuple)."""
    res = []
    for c in candles:
        try:
            if isinstance(c, dict):
                res.append(float(c[key_name]))
            elif hasattr(c, key_name):
                res.append(float(getattr(c, key_name)))
            else:
                res.append(float(c[tuple_idx]))
        except Exception:
            continue
    return res


def _detect_liquidity_sweep(closes, highs, lows, direction: str) -> bool:
    """
    Detect liquidity sweep: price pokes beyond a recent swing high/low
    then closes back inside (reclaim).
    """
    if len(closes) < 10:
        return False
    try:
        if direction == "BUY":
            # Recent swing low (liquidity below)
            recent_lows = lows[-15:-3]
            if not recent_lows:
                return False
            swing_low = min(recent_lows)
            # Sweep: price dipped below swing_low then closed back above it
            if lows[-3] < swing_low and closes[-1] > swing_low:
                return True
        elif direction == "SELL":
            recent_highs = highs[-15:-3]
            if not recent_highs:
                return False
            swing_high = max(recent_highs)
            if highs[-3] > swing_high and closes[-1] < swing_high:
                return True
    except Exception:
        pass
    return False


def _detect_local_bos(closes, highs, lows, direction: str) -> bool:
    """Detect local break of structure on M5/M1."""
    if len(closes) < 10:
        return False
    try:
        if direction == "BUY":
            # Break above recent swing high
            recent_highs = highs[-10:-2]
            if not recent_highs:
                return False
            swing_high = max(recent_highs)
            return closes[-1] > swing_high
        elif direction == "SELL":
            recent_lows = lows[-10:-2]
            if not recent_lows:
                return False
            swing_low = min(recent_lows)
            return closes[-1] < swing_low
    except Exception:
        pass
    return False


def _detect_ob_reaction(closes, highs, lows, direction: str) -> bool:
    """
    Detect order block reaction: price returns to a recent consolidation
    zone (order block) and shows rejection.
    """
    if len(closes) < 12:
        return False
    try:
        if direction == "BUY":
            # Find recent bearish candle (the OB) and check price returned to its range
            for i in range(-8, -2):
                if closes[i] < closes[i-1]:  # bearish candle
                    ob_high = highs[i]
                    ob_low = lows[i]
                    # Price returned into OB zone and closed back above
                    if lows[-2] <= ob_high and closes[-1] > ob_high:
                        return True
        elif direction == "SELL":
            for i in range(-8, -2):
                if closes[i] > closes[i-1]:  # bullish candle
                    ob_high = highs[i]
                    ob_low = lows[i]
                    if highs[-2] >= ob_low and closes[-1] < ob_low:
                        return True
    except Exception:
        pass
    return False


def _detect_fvg_fill(closes, highs, lows, direction: str) -> bool:
    """
    Detect Fair Value Gap fill: price fills a gap between candle bodies
    then continues in the original direction.
    """
    if len(closes) < 8:
        return False
    try:
        if direction == "BUY":
            # FVG: gap between candle[i-2].high and candle[i].low
            for i in range(-6, -2):
                if lows[i] > highs[i-2]:  # gap up
                    fvg_low = highs[i-2]
                    fvg_high = lows[i]
                    # Price filled the gap and closed back above
                    if lows[-2] <= fvg_high and closes[-1] > fvg_high:
                        return True
        elif direction == "SELL":
            for i in range(-6, -2):
                if highs[i] < lows[i-2]:  # gap down
                    fvg_low = highs[i]
                    fvg_high = lows[i-2]
                    if highs[-2] >= fvg_low and closes[-1] < fvg_low:
                        return True
    except Exception:
        pass
    return False


def _detect_engulfing(closes, opens, direction: str) -> bool:
    """Detect bullish/bearish engulfing candle."""
    if len(closes) < 3:
        return False
    try:
        if direction == "BUY":
            # Previous bearish, current bullish engulfing
            prev_bear = closes[-2] < opens[-2]
            curr_bull = closes[-1] > opens[-1]
            engulfs = closes[-1] > opens[-2] and opens[-1] < closes[-2]
            return prev_bear and curr_bull and engulfs
        elif direction == "SELL":
            prev_bull = closes[-2] > opens[-2]
            curr_bear = closes[-1] < opens[-1]
            engulfs = closes[-1] < opens[-2] and opens[-1] > closes[-2]
            return prev_bull and curr_bear and engulfs
    except Exception:
        pass
    return False


class LTFTriggerEngine:
    """
    Detects M5/M1 local triggers for a given direction.
    """

    def find_trigger(self,
                     candles_m5,
                     candles_m1,
                     direction: str,
                     macro_context=None,
                     point: float = 0.01) -> TriggerResult:
        """
        Find a valid LTF trigger.

        Args:
            candles_m5: M5 candle list
            candles_m1: M1 candle list
            direction: "BUY" or "SELL"
            macro_context: optional MacroContext (for invalidation)
            point: price point size

        Returns:
            TriggerResult
        """
        if not candles_m5 or len(candles_m5) < 10:
            return TriggerResult(valid=False, reason="INSUFFICIENT_M5_DATA")

        closes = _extract_series(candles_m5, "close", 4)
        highs = _extract_series(candles_m5, "high", 2)
        lows = _extract_series(candles_m5, "low", 3)
        opens = _extract_series(candles_m5, "open", 1)

        if len(closes) < 10:
            return TriggerResult(valid=False, reason="INSUFFICIENT_M5_DATA")

        # Check each trigger type
        triggers = []

        # 1. Liquidity sweep
        if _detect_liquidity_sweep(closes, highs, lows, direction):
            triggers.append(("LIQUIDITY_SWEEP", 0.85))

        # 2. Local BOS
        if _detect_local_bos(closes, highs, lows, direction):
            triggers.append(("MICRO_BOS", 0.75))

        # 3. OB reaction
        if _detect_ob_reaction(closes, highs, lows, direction):
            triggers.append(("OB_REACTION", 0.80))

        # 4. FVG fill
        if _detect_fvg_fill(closes, highs, lows, direction):
            triggers.append(("FVG_REACTION", 0.70))

        # 5. Engulfing
        if _detect_engulfing(closes, opens, direction):
            triggers.append(("MICRO_CHOCH", 0.65))

        # 6. Breakout + retest (M1 check)
        if candles_m1 and len(candles_m1) >= 10:
            m1_closes = _extract_series(candles_m1, "close", 4)
            m1_highs = _extract_series(candles_m1, "high", 2)
            m1_lows = _extract_series(candles_m1, "low", 3)
            if _detect_local_bos(m1_closes, m1_highs, m1_lows, direction):
                triggers.append(("SMALL_BREAKOUT", 0.72))

        if not triggers:
            return TriggerResult(valid=False, reason="NO_TRIGGER")

        # Pick the best trigger
        best_type, best_score = max(triggers, key=lambda t: t[1])

        # Entry price = current close
        entry_price = closes[-1]

        # Stop loss: recent swing low/high
        stop_loss = 0.0
        if direction == "BUY":
            stop_loss = min(lows[-5:]) - point * 5
        elif direction == "SELL":
            stop_loss = max(highs[-5:]) + point * 5

        return TriggerResult(
            valid=True,
            signal_type=best_type,
            trigger_score=best_score,
            entry_price=entry_price,
            stop_loss=stop_loss,
            reason=f"TRIGGER={best_type} score={best_score:.2f}"
        )