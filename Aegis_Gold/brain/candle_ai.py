"""
ANTIGRAVITY OMEGA — Local Candle AI Engine v2.0
Analyzes multi-candle structures, wicks, patterns, and body ratios locally.
Patterns: Doji, Pinbar, Hammer, Shooting Star, Engulfing, Inside Bar,
          Three White Soldiers, Three Black Crows, Tweezer Top/Bottom,
          Marubozu (Breakout candle).
"""
import logging

logger = logging.getLogger("aegis.omega.candle_ai")


class CandleAI:
    def __init__(self):
        logger.info("Local OMEGA Candle AI Engine v2.0 initialized.")

    def _parse(self, candles):
        """Parse candles to lists regardless of dict/tuple/DataFrame format."""
        # Pandas DataFrame branch
        if hasattr(candles, 'iloc') and hasattr(candles, 'columns'):
            opens  = candles['open'].values.astype(float).tolist()  if 'open'  in candles.columns else [0.0] * len(candles)
            highs  = candles['high'].values.astype(float).tolist()  if 'high'  in candles.columns else [0.0] * len(candles)
            lows   = candles['low'].values.astype(float).tolist()   if 'low'   in candles.columns else [0.0] * len(candles)
            closes = candles['close'].values.astype(float).tolist() if 'close' in candles.columns else [0.0] * len(candles)
            return opens, highs, lows, closes
        # NumPy structured array branch
        if hasattr(candles, 'dtype') and hasattr(candles.dtype, 'names') and candles.dtype.names:
            opens  = candles['open'].astype(float).tolist()
            highs  = candles['high'].astype(float).tolist()
            lows   = candles['low'].astype(float).tolist()
            closes = candles['close'].astype(float).tolist()
            return opens, highs, lows, closes
        # List-of-dicts or list-of-tuples
        try:
            opens  = [c['open']  for c in candles]
            highs  = [c['high']  for c in candles]
            lows   = [c['low']   for c in candles]
            closes = [c['close'] for c in candles]
        except (TypeError, KeyError):
            try:
                opens  = [c[1] for c in candles]
                highs  = [c[2] for c in candles]
                lows   = [c[3] for c in candles]
                closes = [c[4] for c in candles]
            except Exception:
                opens  = [float(getattr(c, 'open',  0)) for c in candles]
                highs  = [float(getattr(c, 'high',  0)) for c in candles]
                lows   = [float(getattr(c, 'low',   0)) for c in candles]
                closes = [float(getattr(c, 'close', 0)) for c in candles]
        return opens, highs, lows, closes


    def analyze(self, candles) -> dict:
        """
        Analyzes M5/M1 candles for multi-candle pattern context.
        Returns a dict with:
            bullish_strength : 0-100
            bearish_strength : 0-100
            pattern          : str  — primary detected pattern name
            rejection        : str  — "TOP", "BOTTOM", "NONE"
            body_ratio       : float
            reason           : str  — human-readable explanation
            pattern_score    : int  — 0-100 raw pattern score
            context_trend    : str  — "BULLISH", "BEARISH", "NEUTRAL"
        """
        if len(candles) < 5:
            return self._empty("Not enough data (need 5+)")

        opens, highs, lows, closes = self._parse(candles)

        # ── Focus candle (last COMPLETED candle) ──────────────────
        o  = opens[-2];  h  = highs[-2];  l  = lows[-2];  c  = closes[-2]
        # Prior candles for context
        po = opens[-3];  pc = closes[-3];  ph = highs[-3];  pl = lows[-3]
        ppo = opens[-4]; ppc = closes[-4]
        # 3-candle pattern window
        c1o, c1c = opens[-4], closes[-4]  # 3 bars ago
        c2o, c2c = opens[-3], closes[-3]  # 2 bars ago
        c3o, c3c = opens[-2], closes[-2]  # Latest completed

        body        = abs(c - o)
        full_range  = h - l if h - l > 0 else 0.00001
        body_ratio  = body / full_range

        wick_top = h - max(o, c)
        wick_bot = min(o, c) - l

        # ── Multi-candle context trend (last 5 candles) ───────────
        bull_closes = sum(1 for i in range(-6, -1) if closes[i] > opens[i])
        bear_closes = 5 - bull_closes
        if bull_closes >= 4:
            context_trend = "BULLISH"
        elif bear_closes >= 4:
            context_trend = "BEARISH"
        else:
            context_trend = "NEUTRAL"

        bullish_strength = 0
        bearish_strength = 0
        pattern = "NONE"
        rejection = "NONE"
        reason = "Normal candle"
        pattern_score = 20  # baseline

        # ── 1. DOJI — Indecision ──────────────────────────────────
        if body_ratio < 0.10:
            pattern = "DOJI"
            reason = "Indecision Doji — no clear direction"
            return {
                "bullish_strength": 10,
                "bearish_strength": 10,
                "pattern": pattern,
                "rejection": "NONE",
                "body_ratio": round(body_ratio, 2),
                "reason": reason,
                "pattern_score": 10,
                "context_trend": context_trend,
            }

        # ── 2. THREE WHITE SOLDIERS ───────────────────────────────
        if (c1c > c1o and c2c > c2o and c3c > c3o  # three consecutive bull
                and c2c > c1c and c3c > c2c          # each higher close
                and c2o > c1o and c3o > c2o):         # each higher open
            bullish_strength = 95
            pattern = "THREE_WHITE_SOLDIERS"
            rejection = "NONE"
            reason = "Three White Soldiers — strong bullish continuation"
            pattern_score = 95
            return self._result(bullish_strength, bearish_strength, pattern,
                                rejection, body_ratio, reason, pattern_score, context_trend)

        # ── 3. THREE BLACK CROWS ──────────────────────────────────
        if (c1c < c1o and c2c < c2o and c3c < c3o   # three consecutive bear
                and c2c < c1c and c3c < c2c           # each lower close
                and c2o < c1o and c3o < c2o):          # each lower open
            bearish_strength = 95
            pattern = "THREE_BLACK_CROWS"
            rejection = "NONE"
            reason = "Three Black Crows — strong bearish continuation"
            pattern_score = 95
            return self._result(bullish_strength, bearish_strength, pattern,
                                rejection, body_ratio, reason, pattern_score, context_trend)

        # ── 4. MARUBOZU (Breakout) ────────────────────────────────
        if body_ratio >= 0.80:
            if c > o:
                bullish_strength = 85
                pattern = "MARUBOZU_BULL"
                reason = "Bullish Marubozu — full-body breakout candle"
                pattern_score = 85
            else:
                bearish_strength = 85
                pattern = "MARUBOZU_BEAR"
                reason = "Bearish Marubozu — full-body breakdown candle"
                pattern_score = 85
            return self._result(bullish_strength, bearish_strength, pattern,
                                rejection, body_ratio, reason, pattern_score, context_trend)

        # ── 5. PINBAR (strong rejection wick) ─────────────────────
        # Pinbar: wick >= 2.5x body, body in top/bottom 1/3 of range
        if wick_bot >= body * 2.5 and (min(o, c) - l) > full_range * 0.5:
            bullish_strength = 92
            pattern = "PINBAR_BULL"
            rejection = "BOTTOM"
            reason = "Bullish Pinbar — deep lower wick rejection"
            pattern_score = 92
            return self._result(bullish_strength, bearish_strength, pattern,
                                rejection, body_ratio, reason, pattern_score, context_trend)

        if wick_top >= body * 2.5 and (h - max(o, c)) > full_range * 0.5:
            bearish_strength = 92
            pattern = "PINBAR_BEAR"
            rejection = "TOP"
            reason = "Bearish Pinbar — deep upper wick rejection"
            pattern_score = 92
            return self._result(bullish_strength, bearish_strength, pattern,
                                rejection, body_ratio, reason, pattern_score, context_trend)

        # ── 6. HAMMER ─────────────────────────────────────────────
        if wick_bot >= body * 1.8 and c >= o and wick_top < body:
            bullish_strength = 88
            pattern = "HAMMER"
            rejection = "BOTTOM"
            reason = "Bullish Hammer — bottom wick rejection"
            pattern_score = 88
            return self._result(bullish_strength, bearish_strength, pattern,
                                rejection, body_ratio, reason, pattern_score, context_trend)

        # ── 7. SHOOTING STAR ──────────────────────────────────────
        if wick_top >= body * 1.8 and c <= o and wick_bot < body:
            bearish_strength = 88
            pattern = "SHOOTING_STAR"
            rejection = "TOP"
            reason = "Bearish Shooting Star — top wick rejection"
            pattern_score = 88
            return self._result(bullish_strength, bearish_strength, pattern,
                                rejection, body_ratio, reason, pattern_score, context_trend)

        # ── 8. TWEEZER TOP ────────────────────────────────────────
        if (abs(h - ph) / full_range < 0.15  # matching highs
                and c < o                      # current is bearish
                and pc > po                    # prior was bullish
                and body_ratio > 0.30):
            bearish_strength = 82
            pattern = "TWEEZER_TOP"
            rejection = "TOP"
            reason = "Tweezer Top — double rejection at highs"
            pattern_score = 82
            return self._result(bullish_strength, bearish_strength, pattern,
                                rejection, body_ratio, reason, pattern_score, context_trend)

        # ── 9. TWEEZER BOTTOM ─────────────────────────────────────
        if (abs(l - pl) / full_range < 0.15  # matching lows
                and c > o                      # current is bullish
                and pc < po                    # prior was bearish
                and body_ratio > 0.30):
            bullish_strength = 82
            pattern = "TWEEZER_BOTTOM"
            rejection = "BOTTOM"
            reason = "Tweezer Bottom — double rejection at lows"
            pattern_score = 82
            return self._result(bullish_strength, bearish_strength, pattern,
                                rejection, body_ratio, reason, pattern_score, context_trend)

        # ── 10. BULLISH ENGULFING ─────────────────────────────────
        if c > po and o < pc and pc < po and body_ratio > 0.50:
            bullish_strength = 85
            pattern = "ENGULFING_BULL"
            reason = "Bullish Engulfing — bears consumed"
            pattern_score = 85
            return self._result(bullish_strength, bearish_strength, pattern,
                                rejection, body_ratio, reason, pattern_score, context_trend)

        # ── 11. BEARISH ENGULFING ─────────────────────────────────
        if c < po and o > pc and pc > po and body_ratio > 0.50:
            bearish_strength = 85
            pattern = "ENGULFING_BEAR"
            reason = "Bearish Engulfing — bulls consumed"
            pattern_score = 85
            return self._result(bullish_strength, bearish_strength, pattern,
                                rejection, body_ratio, reason, pattern_score, context_trend)

        # ── 12. INSIDE BAR (Consolidation) ───────────────────────
        if h <= ph and l >= pl:
            pattern = "INSIDE_BAR"
            reason = "Inside Bar — consolidation. Waiting for breakout."
            pattern_score = 30
            # Inside bars are neutral — slightly favor context direction
            if context_trend == "BULLISH":
                bullish_strength = 45
            elif context_trend == "BEARISH":
                bearish_strength = 45
            else:
                bullish_strength = 30
                bearish_strength = 30
            return self._result(bullish_strength, bearish_strength, pattern,
                                rejection, body_ratio, reason, pattern_score, context_trend)

        # ── 13. STANDARD DIRECTIONAL CANDLE ──────────────────────
        if c > o:
            bullish_strength = 55 + int(body_ratio * 20)
            reason = f"Standard bullish body (ratio={body_ratio:.2f})"
            pattern = "BULL_CANDLE"
        else:
            bearish_strength = 55 + int(body_ratio * 20)
            reason = f"Standard bearish body (ratio={body_ratio:.2f})"
            pattern = "BEAR_CANDLE"
        pattern_score = max(bullish_strength, bearish_strength)

        return self._result(bullish_strength, bearish_strength, pattern,
                            rejection, body_ratio, reason, pattern_score, context_trend)

    def _result(self, bull, bear, pattern, rejection, body_ratio,
                reason, pattern_score, context_trend) -> dict:
        return {
            "bullish_strength": int(min(100, bull)),
            "bearish_strength": int(min(100, bear)),
            "pattern": pattern,
            "rejection": rejection,
            "body_ratio": round(body_ratio, 2),
            "reason": reason,
            "pattern_score": int(min(100, pattern_score)),
            "context_trend": context_trend,
        }

    def _empty(self, reason: str) -> dict:
        return {
            "bullish_strength": 0,
            "bearish_strength": 0,
            "pattern": "NONE",
            "rejection": "NONE",
            "body_ratio": 1.0,
            "reason": reason,
            "pattern_score": 0,
            "context_trend": "NEUTRAL",
        }
