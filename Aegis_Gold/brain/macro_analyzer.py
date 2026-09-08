"""
Macro Bias Engine for Aegis-Gold v6.0.

Analyzes H4 + H1 + M15 candles to produce a hierarchical macro bias:
    STRONG_BULLISH | BULLISH | NEUTRAL | BEARISH | STRONG_BEARISH

Weights:
    H4  = 0.45
    H1  = 0.35
    M15 = 0.20

No perfect agreement required.  Uses EMA alignment + BOS/CHoCH structure
detection.  Accepts candle lists as input (avoids direct MT5 imports,
per Q5 — the gateway fetches candles and passes them in).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any
import logging

logger = logging.getLogger("aegis.macro_analyzer")

# Macro bias labels
STRONG_BULLISH = "STRONG_BULLISH"
BULLISH = "BULLISH"
NEUTRAL = "NEUTRAL"
BEARISH = "BEARISH"
STRONG_BEARISH = "STRONG_BEARISH"

MACRO_BIAS_LABELS = [STRONG_BULLISH, BULLISH, NEUTRAL, BEARISH, STRONG_BEARISH]

# Timeframe weights
H4_WEIGHT = 0.45
H1_WEIGHT = 0.35
M15_WEIGHT = 0.20


@dataclass
class MacroContext:
    """Result of macro bias analysis."""
    bias: str = NEUTRAL
    score: float = 0.0                 # -2.0 to +2.0 weighted sum
    h4_bias: float = 0.0               # -2 to +2
    h1_bias: float = 0.0               # -2 to +2
    m15_bias: float = 0.0              # -2 to +2
    h4_trend: str = "NEUTRAL"
    h1_trend: str = "NEUTRAL"
    m15_trend: str = "NEUTRAL"
    setup_zone: str = "NONE"           # "PULLBACK", "BREAKOUT", "RANGE", "NONE"
    invalidation_level: float = 0.0
    data_timestamp: str = ""
    valid: bool = True
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


def _ema(values: List[float], period: int) -> List[float]:
    """Simple EMA calculation."""
    if not values:
        return []
    k = 2.0 / (period + 1.0)
    ema = [values[0]]
    for v in values[1:]:
        ema.append(v * k + ema[-1] * (1 - k))
    return ema


def _detect_bos_choch(closes: List[float], highs: List[float], lows: List[float]) -> str:
    """
    Detect recent BOS (Break of Structure) or CHoCH (Change of Character).
    Returns "BOS_BULL", "BOS_BEAR", "CHoCH_BULL", "CHoCH_BEAR", or "NONE".
    """
    if len(closes) < 20:
        return "NONE"
    try:
        # Swing highs/lows over last 20 bars
        swing_highs = []
        swing_lows = []
        for i in range(2, len(closes) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                swing_highs.append((i, highs[i]))
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                swing_lows.append((i, lows[i]))

        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            # Recent structure
            last_high_idx, last_high = swing_highs[-1]
            prev_high_idx, prev_high = swing_highs[-2]
            last_low_idx, last_low = swing_lows[-1]
            prev_low_idx, prev_low = swing_lows[-2]

            # BOS bull: price breaks above last swing high
            if closes[-1] > last_high and last_high > prev_high:
                return "BOS_BULL"
            # BOS bear: price breaks below last swing low
            if closes[-1] < last_low and last_low < prev_low:
                return "BOS_BEAR"
            # CHoCH bull: higher low after lower low (structure shift up)
            if last_low > prev_low and last_high > prev_high and closes[-1] > last_high:
                return "CHoCH_BULL"
            # CHoCH bear: lower high after higher high (structure shift down)
            if last_high < prev_high and last_low < prev_low and closes[-1] < last_low:
                return "CHoCH_BEAR"
    except Exception as exc:
        logger.debug(f"[MACRO] BOS/CHoCH detection error: {exc}")
    return "NONE"


def _timeframe_bias(candles, weight: float) -> tuple:
    """
    Compute bias (-2 to +2) for a single timeframe.
    Returns (bias, trend_label, structure_label).
    """
    if not candles or len(candles) < 20:
        return 0.0, "NEUTRAL", "NONE"

    closes = _extract_series(candles, "close", 4)
    highs = _extract_series(candles, "high", 2)
    lows = _extract_series(candles, "low", 3)

    if len(closes) < 20:
        return 0.0, "NEUTRAL", "NONE"

    ema_fast = _ema(closes, 20)
    ema_slow = _ema(closes, 50)

    if len(ema_fast) < 2 or len(ema_slow) < 2:
        return 0.0, "NEUTRAL", "NONE"

    # EMA alignment
    ema_bias = 0.0
    if ema_fast[-1] > ema_slow[-1]:
        ema_bias = 1.0
    elif ema_fast[-1] < ema_slow[-1]:
        ema_bias = -1.0

    # Structure (BOS/CHoCH)
    structure = _detect_bos_choch(closes, highs, lows)
    struct_bias = 0.0
    if structure in ("BOS_BULL", "CHoCH_BULL"):
        struct_bias = 1.0
    elif structure in ("BOS_BEAR", "CHoCH_BEAR"):
        struct_bias = -1.0

    # Price vs EMA (momentum)
    momentum_bias = 0.0
    if closes[-1] > ema_fast[-1]:
        momentum_bias = 0.5
    elif closes[-1] < ema_fast[-1]:
        momentum_bias = -0.5

    bias = ema_bias + struct_bias + momentum_bias  # range -2.5 to +2.5

    # Normalize to -2 to +2
    bias = max(-2.0, min(2.0, bias))

    # Trend label
    if bias > 1.0:
        trend = "STRONG_BULLISH"
    elif bias > 0.3:
        trend = "BULLISH"
    elif bias < -1.0:
        trend = "STRONG_BEARISH"
    elif bias < -0.3:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    return bias, trend, structure


class MacroAnalyzer:
    """
    Hierarchical macro bias engine.
    Accepts H4, H1, M15 candle lists (fetched by the gateway, not MT5 directly).
    """

    def __init__(self):
        self._last_context: Optional[MacroContext] = None

    def analyze(self,
                symbol: str,
                candles_h4,
                candles_h1,
                candles_m15,
                point: float = 0.01) -> MacroContext:
        """
        Compute macro bias from H4/H1/M15 candles.

        Args:
            symbol: e.g. "XAUUSD"
            candles_h4: H4 candle list
            candles_h1: H1 candle list
            candles_m15: M15 candle list
            point: price point size (for invalidation calc)

        Returns:
            MacroContext with bias, score, and setup zone.
        """
        try:
            h4_bias, h4_trend, h4_struct = _timeframe_bias(candles_h4, H4_WEIGHT)
            h1_bias, h1_trend, h1_struct = _timeframe_bias(candles_h1, H1_WEIGHT)
            m15_bias, m15_trend, m15_struct = _timeframe_bias(candles_m15, M15_WEIGHT)

            # Weighted composite score (-2 to +2)
            score = (h4_bias * H4_WEIGHT + h1_bias * H1_WEIGHT + m15_bias * M15_WEIGHT) / (H4_WEIGHT + H1_WEIGHT + M15_WEIGHT)

            # Classify bias
            if score > 1.5:
                bias = STRONG_BULLISH
            elif score > 0.5:
                bias = BULLISH
            elif score < -1.5:
                bias = STRONG_BEARISH
            elif score < -0.5:
                bias = BEARISH
            else:
                bias = NEUTRAL

            # Setup zone detection
            setup_zone = "NONE"
            if h4_struct in ("BOS_BULL", "CHoCH_BULL") and m15_struct in ("BOS_BULL", "CHoCH_BULL"):
                setup_zone = "BREAKOUT"
            elif h4_struct in ("BOS_BEAR", "CHoCH_BEAR") and m15_struct in ("BOS_BEAR", "CHoCH_BEAR"):
                setup_zone = "BREAKOUT"
            elif m15_struct == "NONE" and h1_bias != 0:
                setup_zone = "PULLBACK"
            elif abs(score) < 0.5:
                setup_zone = "RANGE"

            # Invalidation level (from H4 structure)
            invalidation_level = 0.0
            try:
                if candles_h4 and len(candles_h4) >= 5:
                    if bias in (BULLISH, STRONG_BULLISH):
                        invalidation_level = min(_extract_series(candles_h4, "low", 3)[-5:])
                    elif bias in (BEARISH, STRONG_BEARISH):
                        invalidation_level = max(_extract_series(candles_h4, "high", 2)[-5:])
            except Exception:
                pass

            # Data timestamp (last candle close time)
            data_timestamp = ""
            try:
                last_candle = candles_h4[-1]
                if isinstance(last_candle, dict):
                    data_timestamp = str(last_candle.get("time", ""))
                elif hasattr(last_candle, "time"):
                    data_timestamp = str(last_candle.time)
            except Exception:
                pass

            ctx = MacroContext(
                bias=bias,
                score=round(score, 3),
                h4_bias=round(h4_bias, 3),
                h1_bias=round(h1_bias, 3),
                m15_bias=round(m15_bias, 3),
                h4_trend=h4_trend,
                h1_trend=h1_trend,
                m15_trend=m15_trend,
                setup_zone=setup_zone,
                invalidation_level=invalidation_level,
                data_timestamp=data_timestamp,
                valid=True,
                reason=f"H4={h4_trend} H1={h1_trend} M15={m15_trend} score={score:.2f}"
            )
            self._last_context = ctx
            return ctx

        except Exception as exc:
            logger.warning(f"[MACRO] analyze error for {symbol}: {exc}")
            ctx = MacroContext(valid=False, reason=f"ERROR: {exc}")
            self._last_context = ctx
            return ctx

    def get_last_context(self) -> Optional[MacroContext]:
        """Return the last computed macro context (for caching)."""
        return self._last_context


def macro_bias_matches_direction(macro_bias: str, direction: str) -> bool:
    """
    Check if macro bias supports a given trade direction.
    BUY requires BULLISH/STRONG_BULLISH.
    SELL requires BEARISH/STRONG_BEARISH.
    NEUTRAL is acceptable for small patterns but not macro continuation.
    """
    d = direction.upper()
    if d == "BUY":
        return macro_bias in (BULLISH, STRONG_BULLISH)
    elif d == "SELL":
        return macro_bias in (BEARISH, STRONG_BEARISH)
    return False


def macro_bias_contradicts(macro_bias: str, direction: str) -> bool:
    """
    Check if macro bias directly contradicts a trade direction.
    Used to reject small patterns that fight the macro trend.
    """
    d = direction.upper()
    if d == "BUY":
        return macro_bias in (BEARISH, STRONG_BEARISH)
    elif d == "SELL":
        return macro_bias in (BULLISH, STRONG_BULLISH)
    return False