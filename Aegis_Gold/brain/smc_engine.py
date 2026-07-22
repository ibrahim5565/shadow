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


# ─────────────────────────────────────────────────────────────
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

def _parse_candles(candles) -> Tuple[List, List, List, List]:
    """Returns (opens, highs, lows, closes) regardless of candle format."""
    try:
        opens  = [float(c['open'])  for c in candles]
        highs  = [float(c['high'])  for c in candles]
        lows   = [float(c['low'])   for c in candles]
        closes = [float(c['close']) for c in candles]
    except (TypeError, KeyError):
        opens  = [float(c[1]) for c in candles]
        highs  = [float(c[2]) for c in candles]
        lows   = [float(c[3]) for c in candles]
        closes = [float(c[4]) for c in candles]
    return opens, highs, lows, closes


# ─────────────────────────────────────────────────────────────
# 1. SWING HIGH / LOW DETECTION
# ─────────────────────────────────────────────────────────────

def detect_swing_points(highs: List[float], lows: List[float],
                        window: int = 3) -> Tuple[List[Tuple[int,float]], List[Tuple[int,float]]]:
    """
    Returns (swing_highs, swing_lows) as [(index, price), ...].
    A swing high: highest point in a window of 'window' candles each side.
    """
    swing_highs: List[Tuple[int,float]] = []
    swing_lows:  List[Tuple[int,float]] = []
    n = len(highs)

    for i in range(window, n - window):
        left_h  = highs[i - window : i]
        right_h = highs[i + 1 : i + window + 1]
        left_l  = lows[i - window : i]
        right_l = lows[i + 1 : i + window + 1]

        if highs[i] >= max(left_h) and highs[i] >= max(right_h):
            swing_highs.append((i, highs[i]))

        if lows[i] <= min(left_l) and lows[i] <= min(right_l):
            swing_lows.append((i, lows[i]))

    return swing_highs, swing_lows


# ─────────────────────────────────────────────────────────────
# 2. BREAK OF STRUCTURE (BOS) & CHANGE OF CHARACTER (CHoCH)
# ─────────────────────────────────────────────────────────────

def detect_bos_choch(highs: List[float], lows: List[float], closes: List[float],
                     swing_highs: List[Tuple[int,float]],
                     swing_lows:  List[Tuple[int,float]]) -> dict:
    """
    BOS (Break of Structure):
      Bullish BOS  — price closes above a previous swing high → continuation up
      Bearish BOS  — price closes below a previous swing low  → continuation down

    CHoCH (Change of Character):
      In an uptrend, a CHoCH occurs when price breaks below the most recent swing low
      In a downtrend, a CHoCH occurs when price breaks above the most recent swing high
      CHoCH = trend reversal signal (stronger than BOS for entry)
    """
    result = {
        "bullish_bos":  False,
        "bearish_bos":  False,
        "bullish_choch": False,
        "bearish_choch": False,
        "last_broken_high": 0.0,
        "last_broken_low":  0.0,
    }

    if not swing_highs or not swing_lows or len(closes) < 5:
        return result

    current_close = closes[-1]
    prev_close    = closes[-2]

    # Use the last 3 swing highs/lows for recency
    recent_sh = swing_highs[-3:]
    recent_sl = swing_lows[-3:]

    # BOS — continuation
    for idx, price in recent_sh:
        if prev_close <= price < current_close:
            result["bullish_bos"]   = True
            result["last_broken_high"] = price
            break

    for idx, price in recent_sl:
        if prev_close >= price > current_close:
            result["bearish_bos"]  = True
            result["last_broken_low"] = price
            break

    # CHoCH — reversal signal (requires at least 2 swings each)
    if len(recent_sh) >= 2 and len(recent_sl) >= 2:
        # Downtrend CHoCH: in falling structure, price breaks last swing HIGH → bullish reversal
        last_sh_price = recent_sh[-1][1]
        if current_close > last_sh_price and recent_sh[-1][0] > recent_sl[-1][0]:
            result["bullish_choch"] = True
            result["last_broken_high"] = last_sh_price

        # Uptrend CHoCH: in rising structure, price breaks last swing LOW → bearish reversal
        last_sl_price = recent_sl[-1][1]
        if current_close < last_sl_price and recent_sl[-1][0] > recent_sh[-1][0]:
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
        default_sl = 40
        min_rr     = 2.0
        sl_buffer  = 10   # extra pts beyond OB for SL
    else:
        default_sl = 15
        min_rr     = 2.0
        sl_buffer  = 3

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
                symbol: str = "XAUUSD", session: str = "LONDON") -> SMCSignal:
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

