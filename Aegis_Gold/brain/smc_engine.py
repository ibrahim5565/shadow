"""
Aegis-Gold SMC Engine — Smart Money Concepts
PRIMARY signal source for XAUUSD and EURUSD.

Concepts implemented:
  1. Order Blocks (OB)       — last bearish candle before bullish BOS / last bullish before bearish BOS
  2. Liquidity Levels        — equal highs/lows, swing highs/lows, BSL/SSL zones
  3. Liquidity Sweep (Sweep Entry) — price raids liquidity then reverses → high-probability entry
  4. Break of Structure (BOS) & Change of Character (CHoCH)
  5. Power of 3 (PO3)        — Accumulation → Manipulation → Distribution phases

Each concept scores points. Combined SMC score ≥ threshold → TRADE signal.
"""

import logging
import statistics
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger("aegis.smc")


# ─────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────

@dataclass
class OrderBlock:
    index: int
    high: float
    low: float
    direction: str        # "BULL" or "BEAR"
    mitigated: bool = False
    strength: float = 0.0

@dataclass
class LiquidityLevel:
    price: float
    level_type: str       # "BSL" (buy-side) or "SSL" (sell-side)
    touches: int = 1
    swept: bool = False

@dataclass
class SMCSignal:
    direction: str        # "BUY" or "SELL"
    confidence: int       # 0–100
    reason: str
    ob_high: float = 0.0
    ob_low: float = 0.0
    sweep_level: float = 0.0
    bos_confirmed: bool = False
    choch_confirmed: bool = False
    po3_phase: str = "NONE"
    sl_pts: int = 0
    tp_pts: int = 0
    grade: str = "F"
    details: List[str] = field(default_factory=list)

@dataclass
class BigPatternResult:
    bias: str              # 'bullish' | 'bearish' | 'neutral'
    pattern_type: str      # e.g., "BOS_BULLISH", "CHoCH_BEARISH", "OB_REACTION_BULLISH", "RANGE_REJECTION_BEARISH", "NONE"
    confidence: float      # 0.0 to 1.0
    invalidation_level: float
    tf_m5_bias: str = "neutral"
    tf_h1_bias: str = "neutral"
    details: List[str] = field(default_factory=list)

@dataclass
class SmallPatternResult:
    pattern_type: str      # e.g., "LIQUIDITY_SWEEP_REVERSAL", "OB_ENGULFING", "OB_FVG_PINBAR", "MICRO_BOS"
    confidence: float      # 0.0 to 1.0
    invalidation_level: float
    entry_price: float
    direction: str         # "BUY" or "SELL"
    details: List[str] = field(default_factory=list)


# Helpers
# ─────────────────────────────────────────────────────────────

def _candle_body(o: float, c: float) -> float:
    return abs(c - o)

def _candle_range(h: float, l: float) -> float:
    return h - l if h > l else 0.0

def _is_bullish(o: float, c: float) -> bool:
    return c > o

def _is_bearish(o: float, c: float) -> bool:
    return c < o

def _parse_candles(candles) -> Tuple[List[float], List[float], List[float], List[float]]:
    """Returns (opens, highs, lows, closes) regardless of candle format."""
    if hasattr(candles, 'close') and hasattr(candles, 'open'):
        opens = candles['open'].values.astype(float).tolist()
        highs = candles['high'].values.astype(float).tolist()
        lows = candles['low'].values.astype(float).tolist()
        closes = candles['close'].values.astype(float).tolist()
        return opens, highs, lows, closes

    opens, highs, lows, closes = [], [], [], []
    for c in candles:
        if isinstance(c, dict):
            o = c.get('open', c.get('o', c.get('Open', 0.0)))
            h = c.get('high', c.get('h', c.get('High', 0.0)))
            l = c.get('low', c.get('l', c.get('Low', 0.0)))
            cls = c.get('close', c.get('c', c.get('Close', 0.0)))
            opens.append(float(o))
            highs.append(float(h))
            lows.append(float(l))
            closes.append(float(cls))
        elif isinstance(c, (list, tuple, np.ndarray)):
            opens.append(float(c[1]))
            highs.append(float(c[2]))
            lows.append(float(c[3]))
            closes.append(float(c[4]))
        else:
            o = getattr(c, 'open', getattr(c, 'o', 0.0))
            h = getattr(c, 'high', getattr(c, 'h', 0.0))
            l = getattr(c, 'low', getattr(c, 'l', 0.0))
            cls = getattr(c, 'close', getattr(c, 'c', 0.0))
            opens.append(float(o))
            highs.append(float(h))
            lows.append(float(l))
            closes.append(float(cls))
    return opens, highs, lows, closes


# ─────────────────────────────────────────────────────────────
# 1. SWING HIGH / LOW DETECTION
# ─────────────────────────────────────────────────────────────

def detect_swing_points(highs: List[float], lows: List[float],
                        window: int = 3) -> Tuple[List[Tuple[int,float]], List[Tuple[int,float]]]:
    """
    Returns (swing_highs, swing_lows) as [(index, price), ...].
    A swing high: highest point in a window of 'window' candles each side.

    TEMPORAL INTEGRITY FIX:
    The original range (window, n-window) allowed pivot i=(n-window-1) to use
    right_h = highs[n-window:n], which includes the last bar in the array.
    If called on a snapshot that still contains the forming candle, this is
    look-ahead. Fixed: upper bound changed to (n-window-1) so the rightmost
    pivot checked is at i=(n-window-2), guaranteeing 'window' fully-closed
    bars exist on BOTH sides of every detected pivot.

    The FrozenDecisionSnapshot already strips the forming candle, but this
    fix provides defense-in-depth so the function is safe even if called
    with raw MT5 arrays that include a live bar.
    
    ADAPTIVE WINDOW FIX (NEW):
    The loop `for i in range(window, n - window - 1)` can produce an empty
    range when n is small. For range(w, n - w - 1) to be non-empty:
      w < n - w - 1
      2w + 1 < n
      w <= (n - 2) / 2
    
    With small candle counts, we reduce the window adaptively so that swing
    detection still works. When n <= 3, we cannot guarantee valid swings
    and return empty lists (correct behavior — no false positives).
    """
    swing_highs: List[Tuple[int,float]] = []
    swing_lows:  List[Tuple[int,float]] = []
    n = len(highs)

    # Adaptive window: reduce if necessary to avoid empty iteration range
    # For range(w, n - w - 1) to be non-empty: w <= (n - 2) // 2
    if n <= 3:
        # Too few candles to reliably detect swing points
        # Cannot guarantee 'window' bars exist on both sides
        return swing_highs, swing_lows
    
    max_viable_window = (n - 2) // 2
    effective_window = min(window, max_viable_window)

    # FIXED: was `range(window, n - window)` — that upper bound let the pivot
    # at i=(n-window-1) verify right_h against highs[n-window:n], touching the
    # last (potentially forming) bar. Now we stop at n-window-1 (exclusive),
    # i.e., the last checked pivot index is (n-window-2).
    # Using effective_window instead of window ensures no empty range.
    for i in range(effective_window, n - effective_window - 1):
        left_h  = highs[i - effective_window : i]
        right_h = highs[i + 1 : i + effective_window + 1]
        left_l  = lows[i - effective_window : i]
        right_l = lows[i + 1 : i + effective_window + 1]

        # Use len() for numpy array safety (avoid ambiguous boolean)
        if len(left_h) > 0 and len(right_h) > 0 and highs[i] > max(left_h) and highs[i] >= max(right_h):
            swing_highs.append((i, float(highs[i])))

        if len(left_l) > 0 and len(right_l) > 0 and lows[i] < min(left_l) and lows[i] <= min(right_l):
            swing_lows.append((i, float(lows[i])))

    return swing_highs, swing_lows


# ─────────────────────────────────────────────────────────────
# 2. BREAK OF STRUCTURE (BOS) & CHANGE OF CHARACTER (CHoCH)
# ─────────────────────────────────────────────────────────────

def detect_bos_choch(highs: List[float], lows: List[float], closes: List[float],
                     swing_highs: List[Tuple[int,float]],
                     swing_lows:  List[Tuple[int,float]],
                     bos_lookback: int = 10,
                     point: float = 0.01,
                     buffer_pts: float = 2.0) -> dict:
    result = {
        "bullish_bos":  False,
        "bearish_bos":  False,
        "bullish_choch": False,
        "bearish_choch": False,
        "last_broken_high": 0.0,
        "last_broken_low":  0.0,
    }

    if (not swing_highs and not swing_lows) or len(closes) < 5:
        # DIAGNOSTIC: Log swing detection failure for forensics
        try:
            from brain.pattern_diagnostic import log_pattern_diagnostic
            log_pattern_diagnostic({
                "candle_count": len(closes),
                "swing_highs": len(swing_highs),
                "swing_lows": len(swing_lows),
                "reason": "Insufficient swings or candles (<5)"
            })
        except Exception:
            pass
        return result

    current_close = closes[-1]
    n = len(closes)
    buffer = buffer_pts * point

    recent_sh = swing_highs[-3:]
    recent_sl = swing_lows[-3:]

    # ── BOS: current close has broken through a recent swing level ────────────
    for idx, price in recent_sh:
        if current_close > price + buffer and idx < n - 1:
            result["bullish_bos"]      = True
            result["last_broken_high"] = price
            break

    for idx, price in recent_sl:
        if current_close < price - buffer and idx < n - 1:
            result["bearish_bos"]     = True
            result["last_broken_low"] = price
            break

    # CHoCH — reversal signal (requires at least 2 swings each)
    if len(recent_sh) >= 2 and len(recent_sl) >= 2:
        last_sh_price = recent_sh[-1][1]
        if current_close > last_sh_price + buffer and recent_sh[-1][0] > recent_sl[-1][0]:
            result["bullish_choch"] = True
            result["last_broken_high"] = last_sh_price

        last_sl_price = recent_sl[-1][1]
        if current_close < last_sl_price - buffer and recent_sl[-1][0] > recent_sh[-1][0]:
            result["bearish_choch"] = True
            result["last_broken_low"] = last_sl_price

    return result



# ─────────────────────────────────────────────────────────────
# 3. ORDER BLOCK DETECTION
# ─────────────────────────────────────────────────────────────

def detect_order_blocks(opens: List[float], highs: List[float],
                        lows: List[float], closes: List[float],
                        bos: dict, point: float,
                        lookback: int = 30) -> List[OrderBlock]:
    """
    Order Block = the last opposing candle before a BOS impulse.

    Bullish OB:  last BEARISH candle before a strong bullish BOS move
    Bearish OB:  last BULLISH candle before a strong bearish BOS move

    The OB zone (high–low of that candle) is a premium/discount zone
    where price is expected to react when it returns.
    """
    obs: List[OrderBlock] = []
    n   = len(closes)
    start = max(0, n - lookback)

    # Look for bullish OBs (if bullish BOS or CHoCH detected)
    if bos.get("bullish_bos") or bos.get("bullish_choch"):
        # Walk back from current candle to find last bearish candle in the impulse range
        for i in range(n - 2, start, -1):
            if _is_bearish(opens[i], closes[i]):
                body = _candle_body(opens[i], closes[i])
                rng  = _candle_range(highs[i], lows[i])
                strength = (body / rng * 100) if rng > 0 else 0
                obs.append(OrderBlock(
                    index=i, high=highs[i], low=lows[i],
                    direction="BULL", strength=strength
                ))
                break   # Only the most recent one matters

    # Look for bearish OBs (if bearish BOS or CHoCH detected)
    if bos.get("bearish_bos") or bos.get("bearish_choch"):
        for i in range(n - 2, start, -1):
            if _is_bullish(opens[i], closes[i]):
                body = _candle_body(opens[i], closes[i])
                rng  = _candle_range(highs[i], lows[i])
                strength = (body / rng * 100) if rng > 0 else 0
                obs.append(OrderBlock(
                    index=i, high=highs[i], low=lows[i],
                    direction="BEAR", strength=strength
                ))
                break

    # Check mitigation: OB is mitigated if current price has already traded through it
    current_price = closes[-1]
    for ob in obs:
        if ob.direction == "BULL" and current_price < ob.low:
            ob.mitigated = True
        if ob.direction == "BEAR" and current_price > ob.high:
            ob.mitigated = True

    return [ob for ob in obs if not ob.mitigated]


# ─────────────────────────────────────────────────────────────
# 4. LIQUIDITY LEVEL DETECTION
# ─────────────────────────────────────────────────────────────

def detect_liquidity_levels(highs: List[float], lows: List[float],
                             swing_highs: List[Tuple[int,float]],
                             swing_lows:  List[Tuple[int,float]],
                             point: float, equal_threshold_pts: float = 5.0) -> List[LiquidityLevel]:
    """
    Liquidity levels = pools of stop-losses sitting above/below price.

    Buy-Side Liquidity (BSL):  sitting ABOVE swing highs (buy-stops / long breakout stops)
    Sell-Side Liquidity (SSL): sitting BELOW swing lows  (sell-stops / long SLs)

    Equal highs/lows = strongest liquidity (many traders placed SLs at the same level).
    """
    levels: List[LiquidityLevel] = []
    equal_threshold = equal_threshold_pts * point

    # BSL from swing highs
    sh_prices = [p for _, p in swing_highs[-8:]]
    for price in sh_prices:
        touches = sum(1 for p in sh_prices if abs(p - price) <= equal_threshold)
        levels.append(LiquidityLevel(price=price, level_type="BSL", touches=touches))

    # SSL from swing lows
    sl_prices = [p for _, p in swing_lows[-8:]]
    for price in sl_prices:
        touches = sum(1 for p in sl_prices if abs(p - price) <= equal_threshold)
        levels.append(LiquidityLevel(price=price, level_type="SSL", touches=touches))

    # De-duplicate close levels
    merged: List[LiquidityLevel] = []
    used = set()
    for i, lv in enumerate(levels):
        if i in used:
            continue
        for j, lv2 in enumerate(levels):
            if j != i and j not in used and abs(lv.price - lv2.price) <= equal_threshold:
                lv.touches = max(lv.touches, lv2.touches)
                used.add(j)
        merged.append(lv)

    return merged


# ─────────────────────────────────────────────────────────────
# 5. LIQUIDITY SWEEP DETECTION
# ─────────────────────────────────────────────────────────────

def detect_sweep(highs: List[float], lows: List[float], closes: List[float],
                 liq_levels: List[LiquidityLevel],
                 point: float, sweep_buffer_pts: float = 3.0) -> dict:
    """
    Sweep = price wicks beyond a liquidity level then closes back inside it.

    Bullish sweep (setup for BUY):
      Price wicks BELOW an SSL level (triggers sell-stops), then closes back above it.
      → Smart money grabbed liquidity below. Likely to reverse UP.

    Bearish sweep (setup for SELL):
      Price wicks ABOVE a BSL level (triggers buy-stops), then closes back below it.
      → Smart money grabbed liquidity above. Likely to reverse DOWN.
    """
    sweep_buffer = sweep_buffer_pts * point
    result = {
        "bullish_sweep": False,
        "bearish_sweep": False,
        "swept_level":   0.0,
        "sweep_type":    "NONE",
    }

    if len(highs) < 3 or not liq_levels:
        return result

    last_high  = highs[-1]
    last_low   = lows[-1]
    last_close = closes[-1]
    prev_close = closes[-2]

    for lv in liq_levels:
        price = lv.price

        # Bullish sweep: wick below SSL, close back above
        if lv.level_type == "SSL":
            if last_low <= price - sweep_buffer and last_close > price:
                result["bullish_sweep"] = True
                result["swept_level"]   = price
                result["sweep_type"]    = "SSL_SWEPT_BULLISH"
                lv.swept = True
                break

        # Bearish sweep: wick above BSL, close back below
        if lv.level_type == "BSL":
            if last_high >= price + sweep_buffer and last_close < price:
                result["bearish_sweep"] = True
                result["swept_level"]   = price
                result["sweep_type"]    = "BSL_SWEPT_BEARISH"
                lv.swept = True
                break

    return result


# ─────────────────────────────────────────────────────────────
# 6. POWER OF 3 (PO3) PHASE DETECTION
# ─────────────────────────────────────────────────────────────

def detect_power_of_3(opens: List[float], highs: List[float],
                      lows: List[float], closes: List[float],
                      session: str) -> dict:
    """
    Power of 3 (ICT concept):
      Phase 1 — ACCUMULATION:   price ranging, building orders (Asian session / pre-London)
      Phase 2 — MANIPULATION:   liquidity sweep / stop hunt (false break at session open)
      Phase 3 — DISTRIBUTION:   true directional move, strong BOS, trend continuation

    We approximate PO3 by:
      - Looking at candle body ratios and range contraction/expansion
      - Checking if the last 5 candles show expanding range (distribution)
      - Checking for a preceding sweep (manipulation)

    Returns the detected phase and directional bias.
    """
    result = {
        "phase":     "NONE",
        "direction": "NONE",
        "score":     0,
    }

    if len(closes) < 20:
        return result

    # Range analysis over last 20 candles
    ranges_20 = [_candle_range(highs[i], lows[i]) for i in range(-20, 0)]
    avg_range  = statistics.mean(ranges_20) if ranges_20 else 0.0
    if avg_range == 0:
        return result

    # Last 5 candle ranges — expansion indicates distribution
    ranges_5   = [_candle_range(highs[i], lows[i]) for i in range(-5, 0)]
    avg_5      = statistics.mean(ranges_5) if ranges_5 else 0.0

    # First 10 candle ranges — contraction indicates accumulation
    ranges_10  = [_candle_range(highs[i], lows[i]) for i in range(-15, -5)]
    avg_10     = statistics.mean(ranges_10) if ranges_10 else 0.0

    expansion_ratio    = avg_5 / avg_range   if avg_range > 0 else 1.0
    contraction_ratio  = avg_10 / avg_range  if avg_range > 0 else 1.0

    # Detect net direction of last 5 candles
    net_move = closes[-1] - closes[-6]
    direction = "BUY" if net_move > 0 else "SELL"

    if contraction_ratio < 0.8 and expansion_ratio > 1.2:
        # Classic PO3: accumulation → distribution
        phase = "DISTRIBUTION"
        score = 30
    elif contraction_ratio < 0.8:
        phase = "ACCUMULATION"
        score = 10
    elif expansion_ratio > 1.3:
        phase = "DISTRIBUTION"
        score = 25
    else:
        phase = "MANIPULATION"
        score = 15

    result["phase"]     = phase
    result["direction"] = direction
    result["score"]     = score
    return result


# ─────────────────────────────────────────────────────────────
# 7. FAIR VALUE GAP (FVG / IMBALANCE)
# ─────────────────────────────────────────────────────────────

def detect_fvg(opens: List[float], highs: List[float],
               lows: List[float], closes: List[float],
               point: float, min_gap_pts: float = 5.0) -> dict:
    """
    Fair Value Gap = 3-candle imbalance where the wick of candle 1
    and the wick of candle 3 don't overlap — price left an unfilled gap.

    Bullish FVG: low[3] > high[1]  — gap to the upside (support)
    Bearish FVG: high[3] < low[1]  — gap to the downside (resistance)

    Price often returns to fill the FVG before continuing.
    """
    result = {
        "bullish_fvg": False,
        "bearish_fvg": False,
        "fvg_high":    0.0,
        "fvg_low":     0.0,
        "in_fvg":      False,
    }

    if len(highs) < 5:
        return result

    min_gap = min_gap_pts * point
    current_price = closes[-1]

    # Check last 10 candles for recent FVGs
    for i in range(len(closes) - 4, max(0, len(closes) - 15), -1):
        h1, l1 = highs[i],   lows[i]
        h3, l3 = highs[i+2], lows[i+2]

        # Bullish FVG: gap between high of candle i and low of candle i+2
        if l3 > h1 + min_gap:
            result["bullish_fvg"] = True
            result["fvg_high"]    = l3
            result["fvg_low"]     = h1
            # Are we currently trading inside this FVG (potential support)?
            if h1 <= current_price <= l3:
                result["in_fvg"] = True
            break

        # Bearish FVG: gap between low of candle i and high of candle i+2
        if h3 < l1 - min_gap:
            result["bearish_fvg"] = True
            result["fvg_high"]    = l1
            result["fvg_low"]     = h3
            if h3 <= current_price <= l1:
                result["in_fvg"] = True
            break

    return result


# ─────────────────────────────────────────────────────────────
# 8. PRICE IN ORDER BLOCK CHECK
# ─────────────────────────────────────────────────────────────

def price_in_ob(current_price: float, order_blocks: List[OrderBlock],
                direction: str, point: float,
                buffer_pts: float = 5.0) -> Tuple[bool, Optional[OrderBlock]]:
    """
    Returns True if current price is inside (or very near) a valid OB
    that aligns with the trade direction.
    """
    buffer = buffer_pts * point
    for ob in order_blocks:
        if ob.mitigated:
            continue
        in_zone = (ob.low - buffer) <= current_price <= (ob.high + buffer)
        if in_zone:
            if direction == "BUY"  and ob.direction == "BULL":
                return True, ob
            if direction == "SELL" and ob.direction == "BEAR":
                return True, ob
    return False, None


# ─────────────────────────────────────────────────────────────
# 9. SL / TP CALCULATION — SMC-BASED
# ─────────────────────────────────────────────────────────────

def calculate_smc_sl_tp(direction: str, current_price: float,
                        order_block: Optional[OrderBlock],
                        swing_highs: List[Tuple[int,float]],
                        swing_lows:  List[Tuple[int,float]],
                        point: float, symbol: str = "XAUUSD") -> Tuple[int, int]:
    """
    SMC-based SL/TP:
      SL: just beyond the Order Block or last swing high/low
      TP: next liquidity pool (swing high for BUY, swing low for SELL)
          minimum 1:2 RR enforced

    Gold: wider SL (30–80 pts), bigger TP (60–200 pts)
    EURUSD: tighter SL (10–20 pts), TP (20–60 pts)
    """
    is_gold = "XAU" in symbol

    # Default SL/TP if no OB
    if is_gold:
        default_sl = 150  # Mandatory Gold Floor ($1.50 move)
        min_rr     = 2.0
        sl_buffer  = 15   # extra pts beyond OB for SL
    else:
        default_sl = 40   # Mandatory EURUSD Floor (4 pips)
        min_rr     = 2.0
        sl_buffer  = 5

    sl_pts = default_sl
    tp_pts = int(default_sl * min_rr)

    # SL: place just beyond the OB boundary
    if order_block is not None:
        if direction == "BUY":
            # SL below the OB low
            sl_price = order_block.low - sl_buffer * point
            sl_pts   = max(default_sl, int((current_price - sl_price) / point))
        else:
            # SL above the OB high
            sl_price = order_block.high + sl_buffer * point
            sl_pts   = max(default_sl, int((sl_price - current_price) / point))

    # TP: next opposing liquidity level
    if direction == "BUY" and swing_highs:
        # Target the nearest swing high above current price
        above = [(i, p) for i, p in swing_highs if p > current_price]
        if above:
            target_price = above[0][1]
            tp_pts = max(int(sl_pts * min_rr), int((target_price - current_price) / point))

    elif direction == "SELL" and swing_lows:
        # Target the nearest swing low below current price
        below = [(i, p) for i, p in swing_lows if p < current_price]
        if below:
            target_price = below[-1][1]
            tp_pts = max(int(sl_pts * min_rr), int((current_price - target_price) / point))

    # Caps
    if is_gold:
        sl_pts = min(sl_pts, 100)
        tp_pts = min(tp_pts, 300)
    else:
        sl_pts = min(sl_pts, 30)
        tp_pts = min(tp_pts, 100)

    sl_pts = max(sl_pts, 5)
    tp_pts = max(tp_pts, int(sl_pts * min_rr))

    return sl_pts, tp_pts


# ─────────────────────────────────────────────────────────────
# 10. MAIN SMC ANALYSIS FUNCTION
# ─────────────────────────────────────────────────────────────

def analyze_smc(candles_m5, candles_m1=None, point: float = 0.01,
                symbol: str = "XAUUSD", session: str = "LONDON", current_price: Optional[float] = None) -> SMCSignal:
    """
    Master SMC analysis. Runs all 5 concepts and produces a combined signal.

    Scoring system (max 100):
      BOS/CHoCH confirmation  : +20 (BOS) / +30 (CHoCH — stronger)
      Order Block alignment   : +25
      Liquidity sweep         : +25
      Power of 3 phase        : up to +15
      FVG confluence          : +10
      Multiple touch liquidity: +5 per extra touch (max +10)

    Threshold: 55+ = TRADE signal
    """
    try:
        opens, highs, lows, closes = _parse_candles(candles_m5)
    except Exception as e:
        logger.warning(f"SMC: candle parse error: {e}")
        return SMCSignal(direction="NONE", confidence=0, reason=f"Candle parse error: {e}")

    if len(closes) < 30:
        return SMCSignal(direction="NONE", confidence=0, reason="Not enough candles for SMC analysis")

    current_price = closes[-1]
    details: List[str] = []
    score = 0
    direction = "NONE"

    # ── Step 1: Swing points ──────────────────────────────────
    swing_highs, swing_lows = detect_swing_points(highs, lows, window=3)

    if not swing_highs or not swing_lows:
        return SMCSignal(direction="NONE", confidence=0, reason="No swing points detected")

    # ── Step 2: BOS / CHoCH ───────────────────────────────────
    bos = detect_bos_choch(highs, lows, closes, swing_highs, swing_lows)

    bos_confirmed  = bos["bullish_bos"]  or bos["bearish_bos"]
    choch_confirmed = bos["bullish_choch"] or bos["bearish_choch"]

    if bos["bullish_choch"]:
        direction = "BUY"
        score    += 30
        details.append(f"✅ CHoCH BULLISH — trend reversal confirmed (broken high @ {bos['last_broken_high']:.2f})")
    elif bos["bearish_choch"]:
        direction = "SELL"
        score    += 30
        details.append(f"✅ CHoCH BEARISH — trend reversal confirmed (broken low @ {bos['last_broken_low']:.2f})")
    elif bos["bullish_bos"]:
        direction = "BUY"
        score    += 20
        details.append(f"✅ BOS BULLISH — structure break up @ {bos['last_broken_high']:.2f}")
    elif bos["bearish_bos"]:
        direction = "SELL"
        score    += 20
        details.append(f"✅ BOS BEARISH — structure break down @ {bos['last_broken_low']:.2f}")
    else:
        details.append("❌ No BOS/CHoCH — no structural confirmation")

    if direction == "NONE":
        return SMCSignal(direction="NONE", confidence=min(score, 30),
                         reason="No BOS/CHoCH — waiting for structure break",
                         details=details)

    # ── Step 3: Order Blocks ──────────────────────────────────
    obs = detect_order_blocks(opens, highs, lows, closes, bos, point)
    in_ob, matched_ob = price_in_ob(current_price, obs, direction, point)

    if in_ob and matched_ob:
        score += 25
        details.append(f"✅ OB {matched_ob.direction} @ {matched_ob.low:.2f}–{matched_ob.high:.2f} "
                        f"(strength {matched_ob.strength:.0f}%) — price inside OB zone")
    else:
        # Partial credit if OB exists but price not inside yet
        if obs:
            score += 10
            details.append(f"🟡 OB found ({obs[0].direction}) but price not yet in zone — partial credit")
        else:
            details.append("❌ No valid Order Block found")

    # ── Step 4: Liquidity Levels + Sweep ─────────────────────
    liq_levels = detect_liquidity_levels(highs, lows, swing_highs, swing_lows, point)
    sweep = detect_sweep(highs, lows, closes, liq_levels, point)

    sweep_detected = sweep["bullish_sweep"] or sweep["bearish_sweep"]
    sweep_aligns   = (direction == "BUY"  and sweep["bullish_sweep"]) or \
                     (direction == "SELL" and sweep["bearish_sweep"])

    if sweep_aligns:
        score += 25
        details.append(f"✅ SWEEP {sweep['sweep_type']} @ {sweep['swept_level']:.2f} — "
                        f"liquidity grabbed, reversal expected")
        # Bonus for high-touch liquidity levels
        for lv in liq_levels:
            if lv.swept and lv.touches >= 2:
                bonus = min(lv.touches - 1, 2) * 5
                score += bonus
                details.append(f"✅ Equal {lv.level_type} ({lv.touches} touches) +{bonus}pts bonus")
    elif sweep_detected:
        details.append(f"🟡 Sweep detected ({sweep['sweep_type']}) but against direction — caution")
    else:
        details.append("❌ No liquidity sweep — entry not at swept level")

    # ── Step 5: Power of 3 ───────────────────────────────────
    po3 = detect_power_of_3(opens, highs, lows, closes, session)
    po3_score = po3.get("score", 0)
    po3_phase = po3.get("phase", "NONE")
    po3_dir   = po3.get("direction", "NONE")

    if po3_phase == "DISTRIBUTION" and po3_dir == direction:
        score += po3_score
        details.append(f"✅ PO3 DISTRIBUTION phase → {po3_dir} bias confirmed (+{po3_score}pts)")
    elif po3_phase == "MANIPULATION":
        score += 10
        details.append(f"🟡 PO3 MANIPULATION phase — sweep likely in progress (+10pts)")
    elif po3_phase == "ACCUMULATION":
        score += 5
        details.append(f"🟡 PO3 ACCUMULATION — building orders, wait for breakout (+5pts)")
    else:
        details.append(f"❌ PO3 phase {po3_phase} neutral or against direction")

    # ── Step 6: FVG Confluence ───────────────────────────────
    fvg = detect_fvg(opens, highs, lows, closes, point)
    if fvg["in_fvg"]:
        score += 10
        details.append(f"✅ FVG — price inside imbalance zone {fvg['fvg_low']:.2f}–{fvg['fvg_high']:.2f} (+10pts)")
    elif fvg["bullish_fvg"] and direction == "BUY":
        score += 5
        details.append(f"🟡 Bullish FVG nearby — approaching imbalance (+5pts)")
    elif fvg["bearish_fvg"] and direction == "SELL":
        score += 5
        details.append(f"🟡 Bearish FVG nearby — approaching imbalance (+5pts)")

    # ── M1 Confirmation (if available) ───────────────────────
    if candles_m1 is not None and len(candles_m1) >= 10:
        try:
            _, h1, l1, c1 = _parse_candles(candles_m1)
            m1_highs, m1_lows = h1[-20:], l1[-20:]
            m1_bos = detect_bos_choch(h1, l1, c1,
                                      *detect_swing_points(h1, l1, window=2))
            m1_confirms = (
                (direction == "BUY"  and (m1_bos["bullish_bos"] or m1_bos["bullish_choch"])) or
                (direction == "SELL" and (m1_bos["bearish_bos"] or m1_bos["bearish_choch"]))
            )
            if m1_confirms:
                score += 10
                details.append("✅ M1 BOS/CHoCH confirms M5 direction (+10pts)")
            else:
                details.append("🟡 M1 structure not yet confirming M5 direction")
        except Exception as e:
            logger.debug(f"SMC M1 confirmation error: {e}")

    # ── Final scoring ─────────────────────────────────────────
    score = min(score, 100)

    if   score >= 80: grade = "A"
    elif score >= 65: grade = "B"
    elif score >= 50: grade = "C"
    elif score >= 35: grade = "D"
    else:             grade = "F"

    # SL/TP calculation
    sl_pts, tp_pts = calculate_smc_sl_tp(
        direction, current_price, matched_ob if in_ob else None,
        swing_highs, swing_lows, point, symbol
    )

    reason_summary = (
        f"SMC {direction} {symbol} | conf={score}% {grade} | "
        f"BOS={'✅' if bos_confirmed else '❌'} CHoCH={'✅' if choch_confirmed else '❌'} "
        f"OB={'✅' if in_ob else '❌'} Sweep={'✅' if sweep_aligns else '❌'} "
        f"PO3={po3_phase} | SL:{sl_pts}pts TP:{tp_pts}pts"
    )

    logger.info(f"[SMC] {reason_summary}")
    for d in details:
        logger.info(f"[SMC]   {d}")

    return SMCSignal(
        direction=direction,
        confidence=score,
        reason=reason_summary,
        ob_high=matched_ob.high if matched_ob else 0.0,
        ob_low=matched_ob.low  if matched_ob else 0.0,
        sweep_level=sweep["swept_level"],
        bos_confirmed=bos_confirmed,
        choch_confirmed=choch_confirmed,
        po3_phase=po3_phase,
        sl_pts=sl_pts,
        tp_pts=tp_pts,
        grade=grade,
        details=details,
    )


# ─────────────────────────────────────────────────────────────
# 11. DUAL-TIER PATTERN ENGINE (SECTION 1 & SECTION 2)
# ─────────────────────────────────────────────────────────────

def detect_big_pattern(
    symbol: str = "XAUUSD",
    candles_m5=None,
    candles_h1=None,
    point: float = 0.01,
    require_htf_sweep: bool = False,
) -> BigPatternResult:
    """
    SECTION 1 — BIG PATTERN (M5 primary, H1 confirmation layer)
    Determines directional bias ('bullish', 'bearish', or 'neutral') and structural regime.

    Args:
        require_htf_sweep: When True (Sniper Mode), confidence is capped at 0.55 unless
                           a confirmed HTF liquidity sweep (BSL/SSL) is present in the
                           last 20 M5 candles. This enforces PO3 Manipulation phase.

    Returns neutral whenever no clean structural pattern is present. Neutral = hard gate stop.
    """
    if candles_m5 is None:
        return BigPatternResult(bias="neutral", pattern_type="NONE", confidence=0.0, invalidation_level=0.0, details=["No M5 candle data"])

    try:
        opens, highs, lows, closes = _parse_candles(candles_m5)
    except Exception as e:
        return BigPatternResult(bias="neutral", pattern_type="NONE", confidence=0.0, invalidation_level=0.0, details=[f"Parse error: {e}"])

    if len(closes) < 20:
        return BigPatternResult(bias="neutral", pattern_type="NONE", confidence=0.0, invalidation_level=0.0, details=["Insufficient M5 candles (<20)"])

    current_price = closes[-1]
    details: List[str] = []
    
    # 1. M5 Swing points & BOS/CHoCH
    sh_m5, sl_m5 = detect_swing_points(highs, lows, window=3)
    bos_m5 = detect_bos_choch(highs, lows, closes, sh_m5, sl_m5) if (sh_m5 and sl_m5) else {}
    
    m5_bias = "neutral"
    m5_pattern = "NONE"
    m5_conf = 0.0
    invalidation = 0.0

    if bos_m5.get("bullish_choch"):
        m5_bias = "bullish"
        m5_pattern = "CHoCH_BULLISH"
        m5_conf = 0.85
        invalidation = sl_m5[-1][1] if sl_m5 else (min(lows[-10:]) - 10 * point)
        details.append(f"M5 CHoCH Bullish at {bos_m5.get('last_broken_high'):.2f}")
    elif bos_m5.get("bearish_choch"):
        m5_bias = "bearish"
        m5_pattern = "CHoCH_BEARISH"
        m5_conf = 0.85
        invalidation = sh_m5[-1][1] if sh_m5 else (max(highs[-10:]) + 10 * point)
        details.append(f"M5 CHoCH Bearish at {bos_m5.get('last_broken_low'):.2f}")
    elif bos_m5.get("bullish_bos"):
        m5_bias = "bullish"
        m5_pattern = "BOS_BULLISH"
        m5_conf = 0.70
        invalidation = sl_m5[-1][1] if sl_m5 else (min(lows[-10:]) - 10 * point)
        details.append(f"M5 BOS Bullish at {bos_m5.get('last_broken_high'):.2f}")
    elif bos_m5.get("bearish_bos"):
        m5_bias = "bearish"
        m5_pattern = "BOS_BEARISH"
        m5_conf = 0.70
        invalidation = sh_m5[-1][1] if sh_m5 else (max(highs[-10:]) + 10 * point)
        details.append(f"M5 BOS Bearish at {bos_m5.get('last_broken_low'):.2f}")
    else:
        # Check Order Block reaction or Range rejection on M5
        obs_m5 = detect_order_blocks(opens, highs, lows, closes, bos_m5, point)
        in_bull_ob, bull_ob = price_in_ob(current_price, obs_m5, "BUY", point)
        in_bear_ob, bear_ob = price_in_ob(current_price, obs_m5, "SELL", point)


        if in_bull_ob and bull_ob:
            m5_bias = "bullish"
            m5_pattern = "OB_REACTION_BULLISH"
            m5_conf = 0.65
            invalidation = bull_ob.low - 5 * point
            details.append(f"M5 OB Reaction Bullish zone [{bull_ob.low:.2f}-{bull_ob.high:.2f}]")
        elif in_bear_ob and bear_ob:
            m5_bias = "bearish"
            m5_pattern = "OB_REACTION_BEARISH"
            m5_conf = 0.65
            invalidation = bear_ob.high + 5 * point
            details.append(f"M5 OB Reaction Bearish zone [{bear_ob.low:.2f}-{bear_ob.high:.2f}]")
        else:
            # Range boundary rejection: requires price to be at the extreme boundary (<= 5% of range)
            range_high = max(highs[-30:])
            range_low = min(lows[-30:])
            range_span = range_high - range_low
            if range_span > 20 * point:
                if (current_price - range_low) / range_span <= 0.05:
                    m5_bias = "bullish"
                    m5_pattern = "RANGE_REJECTION_BULLISH"
                    m5_conf = 0.60
                    invalidation = range_low - 10 * point
                    details.append(f"M5 Range Low Rejection at {range_low:.2f}")
                elif (range_high - current_price) / range_span <= 0.05:
                    m5_bias = "bearish"
                    m5_pattern = "RANGE_REJECTION_BEARISH"
                    m5_conf = 0.60
                    invalidation = range_high + 10 * point
                    details.append(f"M5 Range High Rejection at {range_high:.2f}")

    # 2. H1 Confirmation (if provided)
    h1_bias = "neutral"
    if candles_h1 is not None:
        try:
            ho, hh, hl, hc = _parse_candles(candles_h1)
            if len(hc) >= 10:
                sh_h1, sl_h1 = detect_swing_points(hh, hl, window=2)
                bos_h1 = detect_bos_choch(hh, hl, hc, sh_h1, sl_h1) if (sh_h1 and sl_h1) else {}
                if bos_h1.get("bearish_choch") or bos_h1.get("bearish_bos"):
                    h1_bias = "bearish"
                elif bos_h1.get("bullish_choch") or bos_h1.get("bullish_bos"):
                    h1_bias = "bullish"
                elif hc[-1] < min(hc[-5:-1]):
                    h1_bias = "bearish"
                elif hc[-1] > max(hc[-5:-1]):
                    h1_bias = "bullish"
        except Exception as _e:
            details.append(f"H1 evaluation skipped: {_e}")


    # Combine M5 & H1: H1 confirms/vetoes M5
    final_bias = m5_bias
    if m5_bias != "neutral" and h1_bias != "neutral":
        if m5_bias != h1_bias:
            # Veto! Conflict between M5 and H1 -> Neutral bias (hard gate stop)
            final_bias = "neutral"
            details.append(f"H1 vetoed M5 bias: M5={m5_bias} vs H1={h1_bias}")
        else:
            m5_conf = min(1.0, m5_conf + 0.15)
            details.append(f"H1 confirms M5 {m5_bias} bias (+15% conf)")

    if final_bias == "neutral":
        m5_conf = 0.0
        m5_pattern = "NONE"

    # ── FVG Detection (Sniper: marks OB+FVG in details) ───────────────────
    # A Fair Value Gap exists when candle[n-2].high < candle[n].low (bull)
    # or candle[n-2].low > candle[n].high (bear) — 3-candle imbalance.
    if final_bias != "neutral" and len(closes) >= 3:
        try:
            fvg_bull = highs[-3] < lows[-1]   # gap: prior high < current low
            fvg_bear = lows[-3]  > highs[-1]  # gap: prior low  > current high
            if (final_bias == "bullish" and fvg_bull) or (final_bias == "bearish" and fvg_bear):
                details.append("FVG_CONFIRMED: 3-candle imbalance gap present")
                m5_conf = min(1.0, m5_conf + 0.05)  # FVG boost
            else:
                # OB present but no FVG — note for Sniper Filter
                if "OB" in m5_pattern or bos_m5:
                    details.append("OB_PRESENT_NO_FVG")
        except Exception:
            pass

    # ── HTF Sweep Check (Sniper Mode: require PO3 manipulation phase) ─────
    if require_htf_sweep and final_bias != "neutral":
        try:
            sh_m5_sw, sl_m5_sw = detect_swing_points(highs, lows, window=2)
            liq_levels_sw = detect_liquidity_levels(highs, lows, sh_m5_sw, sl_m5_sw, point)
            sweep_res = detect_sweep(highs, lows, closes, liq_levels_sw, point)
            sweep_found = (
                (final_bias == "bullish" and sweep_res.get("bullish_sweep")) or
                (final_bias == "bearish" and sweep_res.get("bearish_sweep"))
            )
            if sweep_found:
                details.append(f"HTF_SWEEP_CONFIRMED: {sweep_res.get('sweep_type', 'SWEPT')} @ {sweep_res.get('swept_level', 0.0):.2f}")
            else:
                # No sweep found — cap confidence so Sniper Filter SMC lock fails
                m5_conf = min(m5_conf, 0.55)
                details.append("HTF_SWEEP_ABSENT: confidence capped at 0.55 for Sniper Mode")
        except Exception as _sw_err:
            details.append(f"HTF_SWEEP_CHECK_ERROR: {_sw_err}")

    return BigPatternResult(
        bias=final_bias,
        pattern_type=m5_pattern,
        confidence=m5_conf,
        invalidation_level=invalidation,
        tf_m5_bias=m5_bias,
        tf_h1_bias=h1_bias,
        details=details
    )


def detect_small_pattern(symbol: str, candles_m1, required_bias: str, point: float = 0.01) -> Optional[SmallPatternResult]:
    """
    SECTION 2 — SMALL PATTERN (M1 trigger layer)
    Detects M1 entries ONLY in the direction of required_bias ('bullish'/'BUY' or 'bearish'/'SELL').
    
    Hard filter: if required_bias is neutral or pattern_direction != required_bias, return None immediately.
    """
    # ── Hard Gate Filter ──────────────────────────────────────
    if not required_bias or required_bias.lower() == "neutral":
        return None

    target_dir = "BUY" if required_bias.lower() in ("bullish", "buy") else "SELL"

    if candles_m1 is None:
        return None

    try:
        opens, highs, lows, closes = _parse_candles(candles_m1)
    except Exception:
        return None

    if len(closes) < 10:
        return None

    current_price = closes[-1]
    
    # 1. Check Liquidity Sweep + Reversal on M1
    sh_m1, sl_m1 = detect_swing_points(highs, lows, window=2)
    liq_m1 = detect_liquidity_levels(highs, lows, sh_m1, sl_m1, point)
    sweep_m1 = detect_sweep(highs, lows, closes, liq_m1, point)
    
    if target_dir == "BUY" and sweep_m1.get("bullish_sweep"):
        inval = sweep_m1.get("swept_level", lows[-1]) - 5 * point
        return SmallPatternResult(
            pattern_type="LIQUIDITY_SWEEP_REVERSAL",
            confidence=0.85,
            invalidation_level=inval,
            entry_price=current_price,
            direction="BUY",
            details=["M1 Bullish SSL Sweep + Reversal"]
        )
    elif target_dir == "SELL" and sweep_m1.get("bearish_sweep"):
        inval = sweep_m1.get("swept_level", highs[-1]) + 5 * point
        return SmallPatternResult(
            pattern_type="LIQUIDITY_SWEEP_REVERSAL",
            confidence=0.85,
            invalidation_level=inval,
            entry_price=current_price,
            direction="SELL",
            details=["M1 Bearish BSL Sweep + Reversal"]
        )

    # 2. Check Engulfing candle on M1
    if len(closes) >= 3:
        prev_o, prev_c = opens[-2], closes[-2]
        curr_o, curr_c = opens[-1], closes[-1]
        
        # Bullish Engulfing for BUY
        if target_dir == "BUY" and _is_bearish(prev_o, prev_c) and _is_bullish(curr_o, curr_c):
            if curr_c > prev_o and curr_o <= prev_c:
                inval = min(lows[-2:]) - 3 * point
                return SmallPatternResult(
                    pattern_type="OB_ENGULFING",
                    confidence=0.75,
                    invalidation_level=inval,
                    entry_price=current_price,
                    direction="BUY",
                    details=["M1 Bullish Engulfing Pattern"]
                )
        # Bearish Engulfing for SELL
        elif target_dir == "SELL" and _is_bullish(prev_o, prev_c) and _is_bearish(curr_o, curr_c):
            if curr_c < prev_o and curr_o >= prev_c:
                inval = max(highs[-2:]) + 3 * point
                return SmallPatternResult(
                    pattern_type="OB_ENGULFING",
                    confidence=0.75,
                    invalidation_level=inval,
                    entry_price=current_price,
                    direction="SELL",
                    details=["M1 Bearish Engulfing Pattern"]
                )

    # 3. Check Pin Bar Rejection at OB / FVG
    fvg_m1 = detect_fvg(opens, highs, lows, closes, point)
    curr_body = _candle_body(opens[-1], closes[-1])
    curr_range = _candle_range(highs[-1], lows[-1])
    
    if curr_range > 0:
        lower_wick = min(opens[-1], closes[-1]) - lows[-1]
        upper_wick = highs[-1] - max(opens[-1], closes[-1])
        
        if target_dir == "BUY" and (lower_wick / curr_range) >= 0.55 and (fvg_m1.get("in_fvg") or fvg_m1.get("bullish_fvg")):
            inval = lows[-1] - 3 * point
            return SmallPatternResult(
                pattern_type="OB_FVG_PINBAR",
                confidence=0.70,
                invalidation_level=inval,
                entry_price=current_price,
                direction="BUY",
                details=["M1 Pin Bar Rejection at FVG/OB Zone"]
            )
        elif target_dir == "SELL" and (upper_wick / curr_range) >= 0.55 and (fvg_m1.get("in_fvg") or fvg_m1.get("bearish_fvg")):
            inval = highs[-1] + 3 * point
            return SmallPatternResult(
                pattern_type="OB_FVG_PINBAR",
                confidence=0.70,
                invalidation_level=inval,
                entry_price=current_price,
                direction="SELL",
                details=["M1 Pin Bar Rejection at FVG/OB Zone"]
            )

    # 4. Check Micro-BOS on M1
    bos_m1 = detect_bos_choch(highs, lows, closes, sh_m1, sl_m1) if (sh_m1 and sl_m1) else {}
    if target_dir == "BUY" and (bos_m1.get("bullish_bos") or bos_m1.get("bullish_choch")):
        inval = sl_m1[-1][1] if sl_m1 else (lows[-1] - 5 * point)
        return SmallPatternResult(
            pattern_type="MICRO_BOS",
            confidence=0.65,
            invalidation_level=inval,
            entry_price=current_price,
            direction="BUY",
            details=["M1 Micro-BOS Bullish"]
        )
    elif target_dir == "SELL" and (bos_m1.get("bearish_bos") or bos_m1.get("bearish_choch")):
        inval = sh_m1[-1][1] if sh_m1 else (highs[-1] + 5 * point)
        return SmallPatternResult(
            pattern_type="MICRO_BOS",
            confidence=0.65,
            invalidation_level=inval,
            entry_price=current_price,
            direction="SELL",
            details=["M1 Micro-BOS Bearish"]
        )

    return None


class SMCEngine:
    """
    Class wrapper for Smart Money Concepts (SMC) Engine.
    Provides object-oriented interface around analyze_smc and underlying detection routines.
    """
    def __init__(self, default_point: float = 0.01, symbol: str = "XAUUSD"):
        self.default_point = default_point
        self.symbol = symbol

    def analyze(self, candles_m5, current_price: Optional[float] = None, point: Optional[float] = None, symbol: Optional[str] = None, candles_m1: Optional[list] = None) -> SMCSignal:
        pt = point if point is not None else self.default_point
        sym = symbol if symbol is not None else self.symbol
        
        # If passed a dict of timeframes e.g. {"M5": df, "M1": df} or dataframe
        if isinstance(candles_m5, dict):
            m5 = candles_m5.get("M5", candles_m5.get("m5", []))
            m1 = candles_m5.get("M1", candles_m5.get("m1", candles_m1))
            candles_m5 = m5
            if candles_m1 is None:
                candles_m1 = m1

        if current_price is None:
            if hasattr(candles_m5, 'close'):
                current_price = float(candles_m5['close'].iloc[-1])
            elif isinstance(candles_m5, list) and len(candles_m5) > 0:
                c = candles_m5[-1]
                current_price = float(c.get('close', c.get('c', 0.0)) if isinstance(c, dict) else getattr(c, 'close', 0.0))
            else:
                current_price = 0.0

        return analyze_smc(candles_m5=candles_m5, current_price=current_price, point=pt, symbol=sym, candles_m1=candles_m1)

    def extract_smc_features(self, candles_m5, current_price: float = 0.0, point: float = 0.01) -> SMCSignal:
        return self.analyze(candles_m5, current_price=current_price, point=point)

    def detect_big_pattern(self, symbol: Optional[str] = None, candles_m5=None, candles_h1=None, point: Optional[float] = None) -> BigPatternResult:
        sym = symbol if symbol is not None else self.symbol
        pt = point if point is not None else self.default_point
        return detect_big_pattern(symbol=sym, candles_m5=candles_m5, candles_h1=candles_h1, point=pt)

    def detect_small_pattern(self, symbol: Optional[str] = None, candles_m1=None, required_bias: str = "neutral", point: Optional[float] = None) -> Optional[SmallPatternResult]:
        sym = symbol if symbol is not None else self.symbol
        pt = point if point is not None else self.default_point
        return detect_small_pattern(symbol=sym, candles_m1=candles_m1, required_bias=required_bias, point=pt)

    def predict_vote(self, snapshot) -> "EngineVote":
        """
        Pattern Consensus Architecture — per-engine point-in-time contract.

        Accepts a FrozenDecisionSnapshot and returns an EngineVote containing:
        - direction (BUY / SELL / WAIT)
        - conviction (SMC score / 100)
        - pattern_evidence with confirmation_time <= snapshot.timestamp
        - proposed_sl and proposed_tp derived from structural pattern levels
        - invalidation_level (price that proves this prediction wrong)

        Temporal integrity: this method reads ONLY snapshot.candles_m5 and
        snapshot.candles_m1. It does NOT call mt5 or any live data source.
        """
        from datetime import datetime, timezone
        from brain.engine_vote import EngineVote, PatternEvidence, make_wait_vote

        now = snapshot.timestamp
        pt = snapshot.point
        sym = snapshot.symbol

        try:
            m5 = list(snapshot.candles_m5)
            m1 = list(snapshot.candles_m1) if snapshot.candles_m1 else None

            if len(m5) < 30:
                return make_wait_vote("smc", "Insufficient M5 bars", signal_time=now)

            # ── Run full SMC analysis on snapshot data only ────────────────
            sig = analyze_smc(
                candles_m5=m5,
                candles_m1=m1,
                point=pt,
                symbol=sym,
                session=snapshot.session,
            )

            if sig.direction not in ("BUY", "SELL") or sig.confidence < 35:
                return make_wait_vote("smc", f"SMC no signal (conf={sig.confidence})", signal_time=now)

            # ── Build pattern evidence ─────────────────────────────────────
            # confirmation_time = snapshot.timestamp because all candles in the
            # snapshot are already closed. The SMC signal is derived purely from
            # those closed bars, so the signal is available at snapshot.timestamp.
            pattern_details = sig.details[:]
            if sig.bos_confirmed:
                pattern_type = "CHoCH_" + sig.direction if sig.choch_confirmed else "BOS_" + sig.direction
            elif sig.ob_high > 0 or sig.ob_low > 0:
                pattern_type = "OB_" + sig.direction
            elif sig.sweep_level > 0:
                pattern_type = "SWEEP_" + sig.direction
            else:
                pattern_type = "SMC_" + sig.direction

            evidence = PatternEvidence(
                pattern_type=pattern_type,
                confirmation_time=now,  # All patterns confirmed at snapshot time
                formation_time=now,
                invalidation_level=sig.ob_low if sig.direction == "BUY" else sig.ob_high,
                confidence_raw=sig.confidence / 100.0,
                details=pattern_details,
                extra={
                    "grade": sig.grade,
                    "bos_confirmed": sig.bos_confirmed,
                    "choch_confirmed": sig.choch_confirmed,
                    "ob_high": sig.ob_high,
                    "ob_low": sig.ob_low,
                    "sweep_level": sig.sweep_level,
                    "po3_phase": sig.po3_phase,
                    "sl_pts": sig.sl_pts,
                    "tp_pts": sig.tp_pts,
                },
            )

            # ── Derive absolute SL / TP prices ────────────────────────────
            current_price = snapshot.current_price or 0.0
            if current_price > 0 and sig.sl_pts > 0 and sig.tp_pts > 0:
                if sig.direction == "BUY":
                    proposed_sl = current_price - sig.sl_pts * pt
                    proposed_tp = current_price + sig.tp_pts * pt
                    invalidation = sig.ob_low if sig.ob_low > 0 else proposed_sl
                else:
                    proposed_sl = current_price + sig.sl_pts * pt
                    proposed_tp = current_price - sig.tp_pts * pt
                    invalidation = sig.ob_high if sig.ob_high > 0 else proposed_sl
            else:
                proposed_sl = 0.0
                proposed_tp = 0.0
                invalidation = evidence.invalidation_level

            return EngineVote(
                engine_name="smc",
                direction=sig.direction,
                conviction=sig.confidence / 100.0,
                pattern_evidence=[evidence],
                proposed_sl=proposed_sl,
                proposed_tp=proposed_tp,
                invalidation_level=invalidation,
                signal_time=now,
            )

        except Exception as exc:
            logger.warning(f"[SMC] predict_vote error: {exc}")
            return make_wait_vote("smc", f"predict_vote error: {exc}", signal_time=now)



