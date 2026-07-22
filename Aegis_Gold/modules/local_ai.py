"""
Aegis-Gold — Local AI Engine
Fully self-contained decision intelligence. Zero external API dependencies.
No external AI APIs. No remote services. Fully local decision engine.

Provides:
  - Trend detection (multi-timeframe EMA + ADX)
  - Market structure analysis (swing S/R levels)
  - Momentum analysis (tick velocity + M1 range breakout)
  - Volatility analysis (ATR ratio + spike detection)
  - Support/Resistance detection (swing high/low pivot scan)
  - Risk scoring (R:R, spread, session, equity curve)
  - Trade confidence scoring (composite weighted score 0-100)
  - Entry filtering (candle pattern + RSI confirmation)
  - Exit optimization (ATR-based dynamic TP/SL + RSI exhaustion)
"""

import logging
import statistics
from typing import Any

logger = logging.getLogger("aegis.local_ai")

# ═══════════════════════════════════════════════════════════════
# PURE-PYTHON INDICATORS (no TA-Lib, no numpy required)
# ═══════════════════════════════════════════════════════════════

def _ema(prices: list, period: int) -> list:
    if not prices or len(prices) < period:
        return prices[:]
    k = 2.0 / (period + 1)
    result = [prices[0]]
    for p in prices[1:]:
        result.append(p * k + result[-1] * (1 - k))
    return result


def _sma(prices: list, period: int) -> list:
    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(prices[i])
        else:
            result.append(sum(prices[i - period + 1 : i + 1]) / period)
    return result


def _true_range(highs: list, lows: list, closes: list) -> list:
    tr = [highs[0] - lows[0]]
    for i in range(1, len(highs)):
        tr.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    return tr


def _atr(highs: list, lows: list, closes: list, period: int = 14) -> list:
    return _ema(_true_range(highs, lows, closes), period)


def _adx(highs: list, lows: list, closes: list, period: int = 14) -> list:
    if len(highs) < period + 1:
        return [0.0] * len(highs)
    tr = _true_range(highs, lows, closes)
    plus_dm, minus_dm = [0.0], [0.0]
    for i in range(1, len(highs)):
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        plus_dm.append(up if up > dn and up > 0 else 0.0)
        minus_dm.append(dn if dn > up and dn > 0 else 0.0)
    atr_s = _ema(tr, period)
    pdi = [100 * p / a if a else 0.0 for p, a in zip(_ema(plus_dm, period), atr_s)]
    mdi = [100 * m / a if a else 0.0 for m, a in zip(_ema(minus_dm, period), atr_s)]
    dx = [100 * abs(p - m) / (p + m) if (p + m) else 0.0 for p, m in zip(pdi, mdi)]
    return _ema(dx, period)


def _rsi(closes: list, period: int = 14) -> list:
    if len(closes) < period:
        return [50.0] * len(closes)
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    rsi = [100 - 100 / (1 + avg_g / avg_l) if avg_l else 100.0] * period
    for i in range(period, len(closes) - 1):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        rsi.append(100 - 100 / (1 + avg_g / avg_l) if avg_l else 100.0)
    return rsi


# ═══════════════════════════════════════════════════════════════
# CANDLE NORMALISATION HELPER
# ═══════════════════════════════════════════════════════════════

def _parse_candles(candles: list) -> tuple:
    """Return (opens, highs, lows, closes) regardless of dict or tuple format."""
    try:
        opens  = [c["open"]  for c in candles]
        highs  = [c["high"]  for c in candles]
        lows   = [c["low"]   for c in candles]
        closes = [c["close"] for c in candles]
    except (TypeError, KeyError):
        opens  = [c[1] for c in candles]
        highs  = [c[2] for c in candles]
        lows   = [c[3] for c in candles]
        closes = [c[4] for c in candles]
    return opens, highs, lows, closes


# ═══════════════════════════════════════════════════════════════
# 1. TREND DETECTION
# ═══════════════════════════════════════════════════════════════

def detect_trend(candles_m5: list, candles_m1: list = None) -> dict:
    """
    Multi-timeframe trend detection using EMA 9/21 crossover + ADX strength filter.

    Returns:
        trend          : "TRENDING_UP" | "TRENDING_DOWN" | "RANGING"
        trend_score    : 0-100
        m5_trend       : "BULLISH" | "BEARISH" | "NONE"
        m1_trend       : "BULLISH" | "BEARISH" | "NONE"
        adx_m5         : float  (ADX value on M5)
        reason         : str
    """
    if len(candles_m5) < 30:
        return {"trend": "RANGING", "trend_score": 0, "m5_trend": "NONE",
                "m1_trend": "NONE", "adx_m5": 0.0, "reason": "Insufficient M5 data"}

    _, highs_m5, lows_m5, closes_m5 = _parse_candles(candles_m5)

    ema9_m5  = _ema(closes_m5, 9)
    ema21_m5 = _ema(closes_m5, 21)
    adx_m5   = _adx(highs_m5, lows_m5, closes_m5, 14)

    curr_adx = adx_m5[-1] if adx_m5 else 0.0
    m5_trend = ("BULLISH"  if ema9_m5[-1] > ema21_m5[-1]
                else "BEARISH" if ema9_m5[-1] < ema21_m5[-1]
                else "NONE")

    # M1 alignment (optional)
    m1_trend = "NONE"
    if candles_m1 and len(candles_m1) >= 15:
        _, _, _, closes_m1 = _parse_candles(candles_m1)
        ema9_m1  = _ema(closes_m1, 9)
        ema21_m1 = _ema(closes_m1, 21)
        m1_trend = ("BULLISH"  if ema9_m1[-1] > ema21_m1[-1]
                    else "BEARISH" if ema9_m1[-1] < ema21_m1[-1]
                    else "NONE")

    trend = "RANGING"
    trend_score = 20
    reason = "No alignment"

    if m5_trend == "BULLISH" and m1_trend in ("BULLISH", "NONE"):
        trend = "TRENDING_UP"
        trend_score = 60
        if curr_adx > 25: trend_score += 20
        if m1_trend == "BULLISH": trend_score += 20
        reason = f"Bullish | M5 ADX={curr_adx:.1f}"
    elif m5_trend == "BEARISH" and m1_trend in ("BEARISH", "NONE"):
        trend = "TRENDING_DOWN"
        trend_score = 60
        if curr_adx > 25: trend_score += 20
        if m1_trend == "BEARISH": trend_score += 20
        reason = f"Bearish | M5 ADX={curr_adx:.1f}"

    if curr_adx < 15:
        trend_score = max(10, trend_score - 30)
        reason += " (weak ADX)"

    return {
        "trend": trend,
        "trend_score": min(100, int(trend_score)),
        "m5_trend": m5_trend,
        "m1_trend": m1_trend,
        "adx_m5": round(curr_adx, 2),
        "reason": reason,
    }


# ═══════════════════════════════════════════════════════════════
# 2. MARKET STRUCTURE ANALYSIS
# ═══════════════════════════════════════════════════════════════

def analyze_structure(candles: list, current_price: float, point: float,
                       zone_threshold_pts: float = 50.0) -> dict:
    """
    Detects nearest swing S/R and evaluates structural position.

    Returns:
        position               : "NEAR_SUPPORT" | "NEAR_RESISTANCE" | "MID_RANGE" | "IN_SPACE"
        preferred_direction    : "BUY" | "SELL" | "NONE"
        structure_score        : 0-100
        distance_to_support    : float (points)
        distance_to_resistance : float (points)
        nearest_support        : float
        nearest_resistance     : float
        sl_distance            : float (points)
        reason                 : str
    """
    if len(candles) < 20 or point <= 0:
        return {
            "position": "IN_SPACE", "preferred_direction": "NONE",
            "structure_score": 0, "distance_to_support": 999.0,
            "distance_to_resistance": 999.0, "nearest_support": 0.0,
            "nearest_resistance": 0.0, "sl_distance": 999.0, "reason": "Insufficient data",
        }

    _, highs, lows, _ = _parse_candles(candles[-100:] if len(candles) >= 100 else candles)

    swing_highs, swing_lows = [], []
    for i in range(2, len(highs) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1] and highs[i] > highs[i-2] and highs[i] > highs[i+2]:
            swing_highs.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i+1] and lows[i] < lows[i-2] and lows[i] < lows[i+2]:
            swing_lows.append(lows[i])

    swing_highs = swing_highs[-7:]
    swing_lows  = swing_lows[-7:]

    if not swing_highs and not swing_lows:
        return {
            "position": "IN_SPACE", "preferred_direction": "NONE",
            "structure_score": 0, "distance_to_support": 999.0,
            "distance_to_resistance": 999.0, "nearest_support": 0.0,
            "nearest_resistance": 0.0, "sl_distance": 999.0, "reason": "No swings detected",
        }

    resistances = sorted([x for x in swing_highs if x > current_price])
    supports    = sorted([x for x in swing_lows  if x < current_price], reverse=True)

    nearest_resistance = resistances[0]  if resistances else current_price + 999.0 * point
    nearest_support    = supports[0]     if supports    else current_price - 999.0 * point

    dist_res = (nearest_resistance - current_price) / point
    dist_sup = (current_price - nearest_support)    / point

    position = "MID_RANGE"
    preferred = "NONE"

    if dist_sup <= zone_threshold_pts:
        position  = "NEAR_SUPPORT"
        preferred = "BUY"
    elif dist_res <= zone_threshold_pts:
        position  = "NEAR_RESISTANCE"
        preferred = "SELL"
    elif dist_sup > 200 and dist_res > 200:
        position = "IN_SPACE"

    score = 0
    if position in ("NEAR_SUPPORT", "NEAR_RESISTANCE"):
        score += 50
        if dist_sup < zone_threshold_pts * 0.5 or dist_res < zone_threshold_pts * 0.5:
            score += 20
        if len([h for h in swing_highs if abs(h - nearest_resistance) < 5 * point]) >= 2:
            score += 15
        if len([l for l in swing_lows   if abs(l - nearest_support)    < 5 * point]) >= 2:
            score += 15
    else:
        score = 20

    sl_dist = dist_sup if preferred == "BUY" else dist_res

    return {
        "position": position,
        "preferred_direction": preferred,
        "structure_score": min(100, score),
        "distance_to_support": round(dist_sup, 1),
        "distance_to_resistance": round(dist_res, 1),
        "nearest_support": round(nearest_support, 5),
        "nearest_resistance": round(nearest_resistance, 5),
        "sl_distance": round(sl_dist, 1),
        "reason": f"{position} | S={round(dist_sup,0)}pts R={round(dist_res,0)}pts",
    }


# ═══════════════════════════════════════════════════════════════
# 3. MOMENTUM ANALYSIS
# ═══════════════════════════════════════════════════════════════

def analyze_momentum(ticks: list, candles_m1: list, point: float) -> dict:
    """
    Analyzes tick acceleration and M1 breakout candle momentum.

    Returns:
        strong_momentum    : bool
        momentum_score     : 0-100
        breakout_detected  : bool
        tps                : float (ticks per second)
        reason             : str
    """
    if len(ticks) < 10:
        return {"strong_momentum": False, "momentum_score": 50,
                "breakout_detected": False, "tps": 0.0, "reason": "Not enough tick data"}

    # TPS in last second
    try:
        last_msc = ticks[-1]["time_msc"]
        tps = sum(1 for t in ticks if last_msc - t["time_msc"] <= 1000)
        intervals = []
        t_list = list(ticks[-10:])
        for i in range(1, len(t_list)):
            diff = t_list[i]["time_msc"] - t_list[i-1]["time_msc"]
            if diff >= 0:
                intervals.append(diff)
        avg_interval = statistics.mean(intervals) if intervals else 500.0
    except Exception:
        tps = 2
        avg_interval = 500.0

    acceleration = (1.5 if avg_interval < 200 else 0.5 if avg_interval > 1000 else 1.0)

    score = 50.0
    if tps > 5:
        score += 15
    if acceleration > 1.0:
        score += 10

    breakout = False
    if candles_m1 and len(candles_m1) >= 5:
        _, highs_m1, lows_m1, _ = _parse_candles(candles_m1)
        ranges = [highs_m1[i] - lows_m1[i] for i in range(len(highs_m1))]
        curr_range = ranges[-1]
        hist_avg   = statistics.mean(ranges[-10:-1]) if len(ranges) >= 10 else (ranges[-1] or 0.0001)
        if hist_avg > 0:
            ratio = curr_range / hist_avg
            if ratio > 1.2: score += 15
            if ratio >= 1.5 and tps >= 8:
                breakout = True
                score += 10

    score = min(100.0, score)

    reason = "Normal momentum"
    if breakout:
        reason = f"Breakout detected | TPS={tps} | accel={acceleration:.1f}"
    elif score >= 65:
        reason = f"Strong momentum | TPS={tps}"

    return {
        "strong_momentum": score >= 60,
        "momentum_score": int(score),
        "breakout_detected": breakout,
        "tps": float(tps),
        "reason": reason,
    }


# ═══════════════════════════════════════════════════════════════
# 4. VOLATILITY ANALYSIS
# ═══════════════════════════════════════════════════════════════

def analyze_volatility(candles_m5: list, point: float,
                        max_ratio: float = 3.0) -> dict:
    """
    ATR-ratio based volatility classification.

    Returns:
        volatility_state    : "NORMAL" | "VOLATILE" | "COMPRESSED"
        volatility_score    : 0-100
        news_spike_detected : bool
        low_volatility      : bool
        volatility_ratio    : float
        reason              : str
    """
    if len(candles_m5) < 30:
        return {"volatility_state": "NORMAL", "volatility_score": 50,
                "news_spike_detected": False, "low_volatility": False,
                "volatility_ratio": 1.0, "reason": "Insufficient data"}

    _, highs, lows, closes = _parse_candles(candles_m5)
    atr_s = _atr(highs, lows, closes, 14)

    if not atr_s:
        return {"volatility_state": "NORMAL", "volatility_score": 50,
                "news_spike_detected": False, "low_volatility": False,
                "volatility_ratio": 1.0, "reason": "ATR error"}

    curr_atr = atr_s[-1]
    hist = atr_s[-30:-1] if len(atr_s) >= 30 else atr_s[:-1] or atr_s
    avg_atr = statistics.mean(hist) if hist else curr_atr or 0.0001
    if avg_atr <= 0:
        avg_atr = 0.0001

    ratio = curr_atr / avg_atr
    spike = ratio > max_ratio
    low   = ratio < 0.40

    if spike:
        state = "VOLATILE";   score = 90
        reason = f"News spike ({ratio:.2f}x avg ATR)"
    elif low:
        state = "COMPRESSED"; score = 15
        reason = f"Dead market ({ratio:.2f}x avg ATR)"
    else:
        state = "NORMAL";
        score = min(75, max(30, int(ratio * 50)))
        reason = f"Normal volatility ({ratio:.2f}x avg ATR)"

    return {
        "volatility_state": state,
        "volatility_score": score,
        "news_spike_detected": spike,
        "low_volatility": low,
        "volatility_ratio": round(ratio, 2),
        "reason": reason,
    }


# ═══════════════════════════════════════════════════════════════
# 5. SUPPORT / RESISTANCE DETECTION
# ═══════════════════════════════════════════════════════════════

def detect_support_resistance(candles: list, point: float,
                               lookback: int = 100) -> dict:
    """
    Identifies the top 3 support and resistance levels by swing pivot count.

    Returns:
        supports    : list of (price, strength) sorted nearest first
        resistances : list of (price, strength) sorted nearest first
        count       : int (total pivots found)
    """
    src = candles[-lookback:] if len(candles) >= lookback else candles
    if len(src) < 10:
        return {"supports": [], "resistances": [], "count": 0}

    _, highs, lows, closes = _parse_candles(src)
    current = closes[-1]

    cluster_dist = point * 15  # Points within which levels cluster

    raw_highs, raw_lows = [], []
    for i in range(2, len(highs) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1] and highs[i] > highs[i-2] and highs[i] > highs[i+2]:
            raw_highs.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i+1] and lows[i] < lows[i-2] and lows[i] < lows[i+2]:
            raw_lows.append(lows[i])

    def _cluster(levels: list) -> list:
        if not levels:
            return []
        levels = sorted(levels)
        clusters = []
        cur = [levels[0]]
        for lvl in levels[1:]:
            if lvl - cur[-1] <= cluster_dist:
                cur.append(lvl)
            else:
                clusters.append((sum(cur) / len(cur), len(cur)))
                cur = [lvl]
        clusters.append((sum(cur) / len(cur), len(cur)))
        return sorted(clusters, key=lambda x: x[1], reverse=True)[:5]

    support_clusters    = _cluster([l for l in raw_lows  if l < current])
    resistance_clusters = _cluster([h for h in raw_highs if h > current])

    supports    = [(round(p, 5), s) for p, s in sorted(support_clusters,    key=lambda x: current - x[0])]
    resistances = [(round(p, 5), s) for p, s in sorted(resistance_clusters, key=lambda x: x[0] - current)]

    return {
        "supports": supports,
        "resistances": resistances,
        "count": len(raw_highs) + len(raw_lows),
    }


# ═══════════════════════════════════════════════════════════════
# 6. RISK SCORING
# ═══════════════════════════════════════════════════════════════

def score_risk(account: dict, session: str, spread: float,
               sl_distance: float, tp_distance: float,
               consecutive_losses: int = 0,
               daily_pnl: float = 0.0,
               daily_dd_limit: float = 0.03) -> dict:
    """
    Composite risk evaluation. Returns a normalised risk score and pass/fail flags.

    Returns:
        approved         : bool
        risk_score       : 0-100  (higher = better quality setup)
        rr_ratio         : float
        rejection_reason : str
    """
    score = 50
    reasons = []

    # 1. R:R
    rr = tp_distance / sl_distance if sl_distance > 0 else 0.0
    if rr >= 2.0:  score += 25
    elif rr >= 1.5: score += 15
    elif rr >= 1.0: score += 5
    else:
        reasons.append(f"R:R too low ({rr:.1f})")

    # 2. Session bonus
    session_bonus = {"OVERLAP": 20, "LONDON": 15, "NY": 15, "ASIAN": -10}
    score += session_bonus.get(session, 0)

    # 3. Spread penalty
    spread_limits = {"ASIAN": 20, "LONDON": 25, "NY": 25, "OVERLAP": 30}
    limit = spread_limits.get(session, 30)
    if spread > limit:
        reasons.append(f"Spread {spread:.0f}pts > limit {limit}pts")
    elif spread < limit * 0.5:
        score += 10  # Very tight spread bonus

    # 4. Consecutive loss penalty
    if consecutive_losses >= 5:
        reasons.append(f"{consecutive_losses} consecutive losses")
    elif consecutive_losses >= 3:
        score -= 15

    # 5. Daily P&L guard - DISABLED (unlimited daily loss allowed per user request)
    # equity = account.get("equity", 10000.0)
    # if equity > 0 and abs(daily_pnl) / equity > daily_dd_limit:
    #     reasons.append("Daily drawdown limit hit")

    approved = len(reasons) == 0

    return {
        "approved": approved,
        "risk_score": max(0, min(100, score)),
        "rr_ratio": round(rr, 2),
        "rejection_reason": " | ".join(reasons) if reasons else "Risk clear",
    }


# ═══════════════════════════════════════════════════════════════
# 7. TRADE CONFIDENCE SCORING
# ═══════════════════════════════════════════════════════════════

def score_confidence(trend: dict, structure: dict, momentum: dict,
                     volatility: dict, risk: dict,
                     entry_score: int = 0) -> dict:
    """
    Composite weighted confidence score for a trade setup.

    Weights:
      Trend       30%
      Structure   25%
      Entry       20%
      Momentum    15%
      Risk        10%

    Returns:
        confidence      : 0-100
        breakdown       : dict of component scores
        grade           : "A" | "B" | "C" | "D" | "F"
        tradeable       : bool (confidence >= 55)
    """
    trend_w     = trend.get("trend_score", 0)     * 0.30
    struct_w    = structure.get("structure_score", 0) * 0.25
    entry_w     = entry_score                      * 0.20
    momentum_w  = momentum.get("momentum_score", 0) * 0.15
    risk_w      = risk.get("risk_score", 0)        * 0.10

    # Penalise volatile/bad conditions
    if volatility.get("news_spike_detected", False):
        penalty = 40
    elif volatility.get("low_volatility", False):
        penalty = 20
    else:
        penalty = 0

    raw = trend_w + struct_w + entry_w + momentum_w + risk_w - penalty
    confidence = max(0, min(100, int(raw)))

    grade = ("A" if confidence >= 80 else "B" if confidence >= 65
             else "C" if confidence >= 55 else "D" if confidence >= 40 else "F")

    return {
        "confidence": confidence,
        "breakdown": {
            "trend":     int(trend_w),
            "structure": int(struct_w),
            "entry":     int(entry_w),
            "momentum":  int(momentum_w),
            "risk":      int(risk_w),
            "penalty":   penalty,
        },
        "grade": grade,
        "tradeable": confidence >= 55,
    }


# ═══════════════════════════════════════════════════════════════
# 8. ENTRY FILTERING
# ═══════════════════════════════════════════════════════════════

def filter_entry(candles: list, ticks: list, direction: str, point: float,
                 rsi_period: int = 14) -> dict:
    """
    Candle pattern + RSI entry confirmation.

    Returns:
        entry_approved : bool
        entry_score    : 0-100
        pattern        : str
        rsi            : float
        reason         : str
    """
    if len(candles) < 5:
        return {"entry_approved": False, "entry_score": 0,
                "pattern": "NONE", "rsi": 50.0, "reason": "Not enough candles"}

    opens, highs, lows, closes = _parse_candles(candles)

    o, h, l, c = opens[-2], highs[-2], lows[-2], closes[-2]
    po, pc = opens[-3], closes[-3]

    body   = abs(c - o)
    rng    = h - l if h > l else 0.00001
    b_ratio = body / rng
    wick_t = h - max(o, c)
    wick_b = min(o, c) - l

    pattern = "NONE"
    score   = 0

    if b_ratio < 0.10:
        return {"entry_approved": False, "entry_score": 0,
                "pattern": "DOJI", "rsi": 50.0, "reason": "Doji — indecision"}

    # Pattern scoring
    if direction == "BUY":
        if wick_b >= body * 1.5 and c > o:
            pattern = "HAMMER";        score += 35
        elif c > po and o < pc and pc < po:
            pattern = "ENGULFING_BULL"; score += 40
        elif b_ratio >= 0.65 and c > o:
            pattern = "STRONG_BULL";    score += 30
        else:
            pattern = "WEAK_BULL";      score += 10
    else:  # SELL
        if wick_t >= body * 1.5 and c < o:
            pattern = "SHOOTING_STAR";  score += 35
        elif c < po and o > pc and pc > po:
            pattern = "ENGULFING_BEAR"; score += 40
        elif b_ratio >= 0.65 and c < o:
            pattern = "STRONG_BEAR";    score += 30
        else:
            pattern = "WEAK_BEAR";      score += 10

    # RSI filter
    rsi_vals = _rsi(closes, rsi_period)
    curr_rsi = rsi_vals[-1] if rsi_vals else 50.0
    prev_rsi = rsi_vals[-2] if len(rsi_vals) >= 2 else curr_rsi

    if direction == "BUY":
        if curr_rsi > 75:
            return {"entry_approved": False, "entry_score": 0,
                    "pattern": pattern, "rsi": curr_rsi, "reason": "Overbought RSI"}
        if 45 < curr_rsi < 65:         score += 20
        if curr_rsi > 50 > prev_rsi:   score += 25
    else:
        if curr_rsi < 25:
            return {"entry_approved": False, "entry_score": 0,
                    "pattern": pattern, "rsi": curr_rsi, "reason": "Oversold RSI"}
        if 35 < curr_rsi < 55:         score += 20
        if curr_rsi < 50 < prev_rsi:   score += 25

    # Tick velocity bonus
    if ticks and len(ticks) >= 5:
        try:
            last_msc = ticks[-1]["time_msc"]
            tps = sum(1 for t in ticks if last_msc - t["time_msc"] <= 1000)
            if tps >= 5: score += 10
        except Exception:
            pass

    score = min(100, score)
    approved = score >= 45

    return {
        "entry_approved": approved,
        "entry_score": score,
        "pattern": pattern,
        "rsi": round(curr_rsi, 1),
        "reason": f"{pattern} | RSI={curr_rsi:.1f}" + (" — ENTRY OK" if approved else " — weak setup"),
    }


# ═══════════════════════════════════════════════════════════════
# 9. EXIT OPTIMISATION
# ═══════════════════════════════════════════════════════════════

def optimize_exit(candles_m5: list, candles_m1: list, point: float,
                  direction: str,
                  base_tp: int = 20, max_tp: int = 60,
                  base_sl: int = 20, max_sl: int = 40) -> dict:
    """
    ATR-based dynamic TP/SL targets + RSI exhaustion exit signal.

    Returns:
        tp              : int (points)
        sl              : int (points)
        exhaustion      : bool
        exhaustion_reason : str
    """
    tp, sl = base_tp, base_sl

    if len(candles_m5) >= 14:
        _, highs, lows, closes = _parse_candles(candles_m5)
        atr_s = _atr(highs, lows, closes, 14)
        if atr_s and point > 0:
            atr_pts = atr_s[-1] / point
            tp = int(min(max_tp, max(base_tp, atr_pts * 1.5)))
            sl = int(min(max_sl, max(base_sl, atr_pts * 1.0)))

    exhaustion = False
    exhaustion_reason = "Momentum intact"

    if candles_m1 and len(candles_m1) >= 14:
        _, _, _, closes_m1 = _parse_candles(candles_m1)
        rsi_s = _rsi(closes_m1, 14)
        if len(rsi_s) >= 2:
            curr_r, prev_r = rsi_s[-1], rsi_s[-2]
            if direction == "BUY" and prev_r > 70 and curr_r < 68:
                exhaustion = True
                exhaustion_reason = f"Bullish exhaustion: RSI {prev_r:.1f}→{curr_r:.1f}"
            elif direction == "SELL" and prev_r < 30 and curr_r > 32:
                exhaustion = True
                exhaustion_reason = f"Bearish exhaustion: RSI {prev_r:.1f}→{curr_r:.1f}"

    return {
        "tp": tp,
        "sl": sl,
        "exhaustion": exhaustion,
        "exhaustion_reason": exhaustion_reason,
    }


# ═══════════════════════════════════════════════════════════════
# MASTER DECISION FUNCTION
# ═══════════════════════════════════════════════════════════════

def full_analysis(candles_m5: list, candles_m1: list, ticks: list,
                  current_price: float, point: float,
                  account: dict, session: str, spread: float,
                  consecutive_losses: int = 0,
                  daily_pnl: float = 0.0) -> dict:
    """
    Single entry-point: runs all 9 analysis modules and returns a unified decision.

    Returns:
        action         : "TRADE" | "WAIT"
        direction      : "BUY" | "SELL" | "NA"
        confidence     : 0-100
        tp_points      : int
        sl_points      : int
        grade          : str
        reason         : str
        detail         : dict  (all sub-analysis results)
    """
    zone_pts = {"XAUUSD": 50, "EURUSD": 15}.get(
        next((k for k in ("XAUUSD", "EURUSD") if k.upper() in str(account.get("server", ""))), ""),
        30
    )

    # Run all engines
    trend      = detect_trend(candles_m5, candles_m1)
    structure  = analyze_structure(candles_m5, current_price, point, zone_pts)
    momentum   = analyze_momentum(ticks, candles_m1, point)
    volatility = analyze_volatility(candles_m5, point)
    sr         = detect_support_resistance(candles_m5, point)

    # Determine direction from structure or trend
    direction = structure.get("preferred_direction", "NONE")
    if direction == "NONE":
        direction = "BUY" if trend.get("trend") == "TRENDING_UP" else \
                    "SELL" if trend.get("trend") == "TRENDING_DOWN" else "NONE"

    if direction == "NONE":
        return {
            "action": "WAIT", "direction": "NA", "confidence": 0,
            "tp_points": 20, "sl_points": 20, "grade": "F",
            "reason": "No directional bias", "detail": {},
        }

    entry = filter_entry(candles_m5, ticks, direction, point)
    exit_params = optimize_exit(candles_m5, candles_m1, point, direction)

    sl_dist = max(10.0, structure.get("sl_distance", 20.0))
    tp_dist = exit_params["tp"]

    risk = score_risk(
        account, session, spread, sl_dist, tp_dist,
        consecutive_losses, daily_pnl,
    )

    conf_result = score_confidence(trend, structure, momentum, volatility, risk,
                                   entry.get("entry_score", 0))

    # Block on hard veto conditions
    veto = None
    if volatility.get("news_spike_detected"):
        veto = "News spike detected — no trade"
    elif not risk.get("approved"):
        veto = risk.get("rejection_reason", "Risk rejected")
    elif not entry.get("entry_approved") and conf_result["confidence"] < 45:
        veto = entry.get("reason", "Entry not confirmed")

    if veto:
        return {
            "action": "WAIT",
            "direction": direction,
            "confidence": conf_result["confidence"],
            "tp_points": exit_params["tp"],
            "sl_points": exit_params["sl"],
            "grade": conf_result["grade"],
            "reason": veto,
            "detail": {
                "trend": trend, "structure": structure,
                "momentum": momentum, "volatility": volatility,
                "entry": entry, "risk": risk, "sr": sr,
            },
        }

    return {
        "action": "TRADE",
        "direction": direction,
        "confidence": conf_result["confidence"],
        "tp_points": exit_params["tp"],
        "sl_points": exit_params["sl"],
        "grade": conf_result["grade"],
        "reason": (
            f"CONFIRMED | dir={direction} | conf={conf_result['confidence']} "
            f"| grade={conf_result['grade']} | {entry.get('pattern','?')}"
        ),
        "detail": {
            "trend": trend, "structure": structure,
            "momentum": momentum, "volatility": volatility,
            "entry": entry, "risk": risk, "sr": sr,
            "exit": exit_params,
        },
    }
