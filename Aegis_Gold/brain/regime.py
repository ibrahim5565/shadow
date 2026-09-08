"""
Layer A: Market Regime Detection

QUANT X Extension (non-destructive):
  When QX["extended_regime"] is enabled, RegimeState gains two extra fields:
    - ambiguous (bool)          : True when classifier confidence < threshold
    - regime_confidence (float) : probability of the assigned label (0-1)
  When the flag is off, both fields default to False / 0.0 and nothing changes.
"""
import math
import statistics
from datetime import datetime, timezone
from dataclasses import dataclass
from config import settings as cfg
from brain.indicators import EMA, ADX, ATR, TR

@dataclass
class RegimeState:
    type: str
    score: int
    confidence_score: int
    trend: str
    adx: float
    reason: str
    swing_high: float = 0.0
    swing_low: float = 0.0
    ema_slope: float = 0.0
    # ── QUANT X extensions (always present; ignored when flag off) ─────────
    ambiguous:         bool  = False   # True → TRANSITIONAL state; widen safety margins
    regime_confidence: float = 0.0    # Soft probability of the assigned label (0-1)


def is_active_session() -> bool:
    """Checks if current UTC time falls within active trading hours (24/5 continuous trading)."""
    # 24/5 trading supported for ASIAN, LONDON, NY, and OVERLAP sessions
    weekday = datetime.now(timezone.utc).weekday()
    return weekday < 5  # Monday (0) to Friday (4)


def calculate_ema_slope(ema, point, window=3) -> float:
    """Calculates EMA slope angle in degrees, normalized by point size."""
    if len(ema) < window + 1 or point <= 0:
        return 0.0
    change = ema[-1] - ema[-1 - window]
    change_pts = change / point
    slope = change_pts / window
    return math.atan(slope) * 180 / math.pi


def detect_swings(highs, lows, window=2) -> tuple[float, float]:
    """
    Finds the most recent confirmed swing high and swing low.
    A swing high at index i is higher than index i-1, i-2, i+1, i+2.
    """
    swing_high = None
    swing_low = None
    
    n = len(highs)
    if n < 2 * window + 1:
        return highs[-1], lows[-1]
        
    for i in range(n - 1 - window, window, -1):
        # Check swing high
        is_high = True
        for j in range(1, window + 1):
            if highs[i] < highs[i - j] or highs[i] < highs[i + j]:
                is_high = False
                break
        if is_high and swing_high is None:
            swing_high = highs[i]
            
        # Check swing low
        is_low = True
        for j in range(1, window + 1):
            if lows[i] > lows[i - j] or lows[i] > lows[i + j]:
                is_low = False
                break
        if is_low and swing_low is None:
            swing_low = lows[i]
            
        if swing_high is not None and swing_low is not None:
            break
            
    # Fallback to absolute max/min if none found in history
    if swing_high is None:
        swing_high = max(highs[-20:])
    if swing_low is None:
        swing_low = min(lows[-20:])
        
    return swing_high, swing_low


def analyze_regime(candles, symbol: str = "EURUSD", point: float = 0.00001) -> RegimeState:
    """
    Analyzes the market regime based on M5 candles.
    candles: List of MT5 candle tuples/dicts.
    """
    if len(candles) < cfg.CANDLE_COUNT:
        return RegimeState(
            type="RANGING", score=0, confidence_score=0, trend="NONE", adx=0.0,
            reason="Not enough data", swing_high=0.0, swing_low=0.0, ema_slope=0.0
        )
        
    # Standardize data access depending on how candles are passed (DataFrame/dict/tuple)
    if hasattr(candles, 'iloc') and hasattr(candles, 'columns'):
        # Pandas DataFrame (from MT5 copy_rates_from_pos via shadow_run / brain.py)
        closes = candles['close'].values.astype(float).tolist()
        highs  = candles['high'].values.astype(float).tolist()
        lows   = candles['low'].values.astype(float).tolist()
    elif hasattr(candles, 'dtype') and hasattr(candles.dtype, 'names') and candles.dtype.names:
        # NumPy structured array (direct MT5 copy_rates output)
        closes = candles['close'].astype(float).tolist()
        highs  = candles['high'].astype(float).tolist()
        lows   = candles['low'].astype(float).tolist()
    else:
        try:
            closes = [float(c['close']) for c in candles]
            highs  = [float(c['high'])  for c in candles]
            lows   = [float(c['low'])   for c in candles]
        except (TypeError, KeyError):
            closes = [float(c[4]) for c in candles]
            highs  = [float(c[2]) for c in candles]
            lows   = [float(c[3]) for c in candles]

        
    # Calculate indicators
    ema_fast = EMA(closes, cfg.EMA_FAST_PERIOD)      # default 8
    ema_mid  = EMA(closes, 13)                         # 13 EMA mid
    ema_slow = EMA(closes, cfg.EMA_SLOW_PERIOD)      # default 21
    adx_series = ADX(highs, lows, closes, cfg.ADX_PERIOD)
    
    current_adx = adx_series[-1] if adx_series else 0.0
    
    # Calculate EMA Slope Angle and Swings
    ema_slope_val = calculate_ema_slope(ema_slow, point, window=3)
    swing_high, swing_low = detect_swings(highs, lows, window=2)
    
    # Check Active Session Hours (Skip trading outside active sessions)
    if not is_active_session():
        return RegimeState(
            type="RANGING", score=0, confidence_score=0, trend="NONE", adx=current_adx,
            reason="Outside active session (London/NY)", swing_high=swing_high, swing_low=swing_low, ema_slope=ema_slope_val
        )
        
    # Get symbol config thresholds
    sym_cfg = cfg.get_symbol_config(symbol)
    ema_range_threshold = sym_cfg.get("ema_range_threshold", 0.00010)
    max_volatility_ratio = sym_cfg.get("max_volatility_ratio", 2.0)
    
    # Trend alignment check (Fast > Mid > Slow)
    trend = "RANGING"
    ema_aligned = False
    
    if (ema_fast[-1] > ema_mid[-1] > ema_slow[-1] + ema_range_threshold) and ema_fast[-1] > ema_fast[-3]:
        trend = "TRENDING_UP"
        ema_aligned = True
    elif (ema_fast[-1] < ema_mid[-1] < ema_slow[-1] - ema_range_threshold) and ema_fast[-1] < ema_fast[-3]:
        trend = "TRENDING_DOWN"
        ema_aligned = True
        
    # Volatility Check
    atr = ATR(highs, lows, closes, cfg.ATR_PERIOD)
    current_atr = atr[-1] if atr else 0.0
    avg_atr = statistics.mean(atr[-50:]) if len(atr) >= 50 else (statistics.mean(atr) if atr else 1.0)
    volatility_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0
    
    regime_type = ""
    reason = ""
    
    # Regime Decision Logic (Multi-Factor - ADX is not a requirement)
    # No single indicator forces a regime classification
    if volatility_ratio > max_volatility_ratio:
        regime_type = "VOLATILE"
        reason = f"Abnormal volatility (ratio={volatility_ratio:.2f}) — likely news"
    # Multiple weak signals suggest ranging
    elif not ema_aligned and abs(ema_slope_val) < 10.0 and current_adx < 20.0:
        regime_type = "RANGING"
        reason = f"Multiple ranging signals: EMAs crossed, flat slope ({ema_slope_val:.1f}°), weak ADX ({current_adx:.1f})"
    # Strong trending signals (ADX is supporting evidence, not requirement)
    elif ema_aligned and (current_adx > 25 or abs(ema_slope_val) > 30):
        regime_type = trend
        reason = f"Trending: EMA aligned, ADX={current_adx:.1f}, slope={ema_slope_val:.1f}°"
    # Moderate signals - prefer structure-based classification
    else:
        regime_type = trend if ema_aligned else "RANGING"
        reason = f"Moderate regime: EMA={'aligned' if ema_aligned else 'mixed'}, ADX={current_adx:.1f}, slope={ema_slope_val:.1f}°"
        
    # Regime Confidence Score
    score = 0
    if current_adx > 25: score += 30
    if current_adx > 30: score += 10
    if ema_aligned: score += 30
    if volatility_ratio < 1.5: score += 20
    
    # Price vs EMA
    curr_price = closes[-1]
    if curr_price > ema_fast[-1] and curr_price > ema_slow[-1] and trend == "TRENDING_UP":
        score += 10
    if curr_price < ema_fast[-1] and curr_price < ema_slow[-1] and trend == "TRENDING_DOWN":
        score += 10
        
    # ── QUANT X: soft-boundary regime confidence (flag-gated) ─────────────
    ambiguous         = False
    regime_confidence = 0.0
    try:
        from config.quant_x_config import QX
        if QX.flag("extended_regime"):
            ambiguity_threshold = QX.get("regime_ambiguity_threshold") or 0.55
            regime_confidence   = _soft_regime_confidence(
                current_adx, ema_aligned, volatility_ratio, score)
            if regime_confidence < ambiguity_threshold:
                ambiguous   = True
                regime_type = "TRANSITIONAL"
                reason      = (f"Transitional/ambiguous regime (conf={regime_confidence:.2f} "
                               f"< {ambiguity_threshold}) — safety margins widened")
    except Exception:
        pass   # Flag import failure → fall back silently

    return RegimeState(
        type=regime_type,
        score=score,
        confidence_score=score,
        trend=trend,
        adx=current_adx,
        reason=reason,
        swing_high=swing_high,
        swing_low=swing_low,
        ema_slope=ema_slope_val,
        ambiguous=ambiguous,
        regime_confidence=regime_confidence,
    )


def _soft_regime_confidence(adx: float, ema_aligned: bool,
                             volatility_ratio: float, score: int) -> float:
    """
    Compute a soft probability (0-1) for the assigned regime label using
    logistic-scaled inputs.  Higher ADX + aligned EMAs + normal volatility
    = higher confidence.  Used only when QX["extended_regime"] is True.
    """
    # Logistic mapping helpers
    def _logistic(x: float, centre: float, scale: float) -> float:
        import math
        try:
            return 1.0 / (1.0 + math.exp(-(x - centre) / scale))
        except OverflowError:
            return 0.0 if x < centre else 1.0

    adx_prob   = _logistic(adx, 25.0, 5.0)          # ADX 25 = 50% conf
    align_prob = 0.7 if ema_aligned else 0.3
    vol_prob   = _logistic(2.0 - volatility_ratio, 0.5, 0.5)  # lower vol ratio = higher conf
    score_prob = min(score / 100.0, 1.0)

    # Weighted geometric mean
    weights    = [0.35, 0.25, 0.20, 0.20]
    probs      = [adx_prob, align_prob, vol_prob, score_prob]
    try:
        import math
        log_sum = sum(w * math.log(max(p, 1e-9)) for w, p in zip(weights, probs))
        return round(math.exp(log_sum), 4)
    except Exception:
        return round(sum(w * p for w, p in zip(weights, probs)), 4)


def get_pattern_regime_bias(candles_m5, candles_h1=None, symbol: str = "XAUUSD", point: float = 0.01) -> dict:
    """
    Exposes current Big Pattern bias and market regime to the pattern engine.
    Uses detect_big_pattern under the hood and combines it with analyze_regime.
    """
    from brain.smc_engine import detect_big_pattern
    regime = analyze_regime(candles_m5, symbol=symbol, point=point)
    big_pat = detect_big_pattern(symbol=symbol, candles_m5=candles_m5, candles_h1=candles_h1, point=point)

    return {
        "regime_type": regime.type,
        "trend": regime.trend,
        "adx": regime.adx,
        "big_pattern_bias": big_pat.bias,
        "big_pattern_type": big_pat.pattern_type,
        "big_pattern_conf": big_pat.confidence,
        "invalidation_level": big_pat.invalidation_level,
        "details": big_pat.details,
    }

