"""
═══════════════════════════════════════════════════════════════════════════════
🔭 AEGIS MULTI-TIMEFRAME ANALYSIS ENGINE - Institutional Market Structure
═══════════════════════════════════════════════════════════════════════════════

PURPOSE:
--------
Analyze market simultaneously across 9 timeframes to detect:
- Trend alignment and divergence
- Regime shifts before they become obvious
- Multi-timeframe support/resistance
- Higher timeframe market structure
- Institutional positioning

PHILOSOPHY:
-----------
"The trend is your friend, but only when all your friends agree."

Single timeframe analysis is gambling. Institutional traders analyze structure
across multiple timeframes to understand the TRUE market direction.

TIMEFRAMES ANALYZED:
--------------------
M1  - Ultra-short scalping, noise detection
M2  - Short-term momentum confirmation
M3  - Micro-trend validation
M5  - Primary scalping timeframe
M10 - Intermediate momentum
M15 - Swing structure
M30 - Session trend
H1  - Major trend direction
H4  - Institutional bias

OUTPUTS:
--------
- Trend for each timeframe (BULLISH, BEARISH, RANGING, VOLATILE)
- Alignment score (0-9): How many timeframes agree
- Regime detection: STRONG_TREND, WEAK_TREND, RANGE, TRANSITION
- Market structure: Higher highs/lows, lower highs/lows
- Key levels from higher timeframes
- Divergence alerts
- Recommended trade direction based on alignment

═══════════════════════════════════════════════════════════════════════════════
"""

import MetaTrader5 as mt5
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum
import logging

logger = logging.getLogger("MTF_Analyzer")


class TrendState(Enum):
    """Trend classification for each timeframe."""
    STRONG_BULLISH = "STRONG_BULLISH"
    BULLISH = "BULLISH"
    WEAK_BULLISH = "WEAK_BULLISH"
    RANGING = "RANGING"
    WEAK_BEARISH = "WEAK_BEARISH"
    BEARISH = "BEARISH"
    STRONG_BEARISH = "STRONG_BEARISH"
    VOLATILE = "VOLATILE"
    UNKNOWN = "UNKNOWN"


class MarketRegime(Enum):
    """Overall market regime based on multi-timeframe analysis."""
    STRONG_UPTREND = "STRONG_UPTREND"
    UPTREND = "UPTREND"
    WEAK_UPTREND = "WEAK_UPTREND"
    RANGE_BOUND = "RANGE_BOUND"
    WEAK_DOWNTREND = "WEAK_DOWNTREND"
    DOWNTREND = "DOWNTREND"
    STRONG_DOWNTREND = "STRONG_DOWNTREND"
    TRANSITION = "TRANSITION"
    VOLATILE = "VOLATILE"


@dataclass
class TimeframeAnalysis:
    """Analysis result for a single timeframe."""
    timeframe: str
    trend: TrendState
    trend_strength: int  # 0-100
    
    # Price structure
    current_price: float
    ema_fast: float
    ema_slow: float
    ema_alignment: str  # "BULLISH", "BEARISH", "NEUTRAL"
    
    # Momentum
    rsi: float
    adx: float
    momentum_score: int  # 0-100
    
    # Structure
    recent_high: float
    recent_low: float
    structure: str  # "HH_HL", "LH_LL", "RANGE"
    
    # Volatility
    atr: float
    volatility_state: str  # "LOW", "NORMAL", "HIGH", "EXTREME"
    
    # Confidence
    reliability: int  # 0-100 (how clean is the signal)


@dataclass
class MultiTimeframeResult:
    """Complete multi-timeframe analysis result."""
    symbol: str
    timestamp: str
    
    # Individual timeframe results
    m1: TimeframeAnalysis
    m2: TimeframeAnalysis
    m3: TimeframeAnalysis
    m5: TimeframeAnalysis
    m10: TimeframeAnalysis
    m15: TimeframeAnalysis
    m30: TimeframeAnalysis
    h1: TimeframeAnalysis
    h4: TimeframeAnalysis
    
    # Aggregated insights
    overall_regime: MarketRegime
    alignment_score: int  # 0-9 (how many timeframes agree on direction)
    trend_direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    trend_confidence: int  # 0-100
    
    # Trading recommendation
    recommended_direction: str  # "BUY", "SELL", "WAIT"
    trade_quality: str  # "EXCELLENT", "GOOD", "FAIR", "POOR"
    
    # Key levels from higher timeframes
    htf_resistance: float
    htf_support: float
    
    # Warnings
    divergence_detected: bool
    regime_shift_imminent: bool
    notes: str


class MultiTimeframeAnalyzer:
    """
    Institutional-grade multi-timeframe market analysis engine.
    """
    
    # MT5 Timeframe constants
    TIMEFRAMES = {
        "M1": mt5.TIMEFRAME_M1,
        "M2": mt5.TIMEFRAME_M2,
        "M3": mt5.TIMEFRAME_M3,
        "M5": mt5.TIMEFRAME_M5,
        "M10": mt5.TIMEFRAME_M10,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4
    }
    
    def __init__(self):
        logger.info("🔭 Multi-Timeframe Analyzer initialized")
    
    def analyze(self, symbol: str) -> Optional[MultiTimeframeResult]:
        """
        Perform comprehensive multi-timeframe analysis.
        Returns complete analysis or None if data unavailable.
        """
        try:
            from datetime import datetime
            
            # Fetch data for all timeframes
            tf_data = {}
            for tf_name, tf_const in self.TIMEFRAMES.items():
                candles = self._fetch_candles(symbol, tf_const, count=100)
                if candles is None or len(candles) < 50:
                    logger.warning(f"Insufficient data for {tf_name}")
                    return None
                tf_data[tf_name] = candles
            
            # Analyze each timeframe
            m1_analysis = self._analyze_timeframe("M1", tf_data["M1"])
            m2_analysis = self._analyze_timeframe("M2", tf_data["M2"])
            m3_analysis = self._analyze_timeframe("M3", tf_data["M3"])
            m5_analysis = self._analyze_timeframe("M5", tf_data["M5"])
            m10_analysis = self._analyze_timeframe("M10", tf_data["M10"])
            m15_analysis = self._analyze_timeframe("M15", tf_data["M15"])
            m30_analysis = self._analyze_timeframe("M30", tf_data["M30"])
            h1_analysis = self._analyze_timeframe("H1", tf_data["H1"])
            h4_analysis = self._analyze_timeframe("H4", tf_data["H4"])
            
            # Aggregate analysis
            all_tf = [m1_analysis, m2_analysis, m3_analysis, m5_analysis, m10_analysis,
                     m15_analysis, m30_analysis, h1_analysis, h4_analysis]
            
            alignment_score = self._calculate_alignment(all_tf)
            overall_regime = self._determine_regime(all_tf)
            trend_direction = self._determine_trend_direction(all_tf)
            trend_confidence = self._calculate_trend_confidence(all_tf, alignment_score)
            
            # Trading recommendation
            recommended_direction, trade_quality = self._generate_recommendation(
                all_tf, alignment_score, overall_regime
            )
            
            # Key levels from higher timeframes (H4, H1, M30)
            htf_resistance = max(h4_analysis.recent_high, h1_analysis.recent_high, m30_analysis.recent_high)
            htf_support = min(h4_analysis.recent_low, h1_analysis.recent_low, m30_analysis.recent_low)
            
            # Divergence and regime shift detection
            divergence_detected = self._detect_divergence(all_tf)
            regime_shift_imminent = self._detect_regime_shift(all_tf)
            
            # Notes
            notes = self._generate_notes(all_tf, alignment_score, divergence_detected, regime_shift_imminent)
            
            result = MultiTimeframeResult(
                symbol=symbol,
                timestamp=datetime.utcnow().isoformat(),
                m1=m1_analysis,
                m2=m2_analysis,
                m3=m3_analysis,
                m5=m5_analysis,
                m10=m10_analysis,
                m15=m15_analysis,
                m30=m30_analysis,
                h1=h1_analysis,
                h4=h4_analysis,
                overall_regime=overall_regime,
                alignment_score=alignment_score,
                trend_direction=trend_direction,
                trend_confidence=trend_confidence,
                recommended_direction=recommended_direction,
                trade_quality=trade_quality,
                htf_resistance=htf_resistance,
                htf_support=htf_support,
                divergence_detected=divergence_detected,
                regime_shift_imminent=regime_shift_imminent,
                notes=notes
            )
            
            logger.info(f"✅ MTF Analysis complete: {symbol} | Alignment: {alignment_score}/9 | Regime: {overall_regime.value}")
            return result
            
        except Exception as e:
            logger.error(f"❌ MTF Analysis failed for {symbol}: {e}")
            return None
    
    def _fetch_candles(self, symbol: str, timeframe: int, count: int = 100):
        """Fetch candles for specific timeframe."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            return rates if (rates is not None and len(rates) > 0) else None
        except Exception as e:
            logger.error(f"Failed to fetch candles: {e}")
            return None
    
    def _analyze_timeframe(self, tf_name: str, candles) -> TimeframeAnalysis:
        """
        Analyze single timeframe for trend, momentum, structure.
        """
        closes = np.array([c['close'] for c in candles])
        highs = np.array([c['high'] for c in candles])
        lows = np.array([c['low'] for c in candles])
        
        current_price = closes[-1]
        
        # EMAs
        ema_fast = self._ema(closes, 9)
        ema_slow = self._ema(closes, 21)
        
        if ema_fast > ema_slow * 1.0005:
            ema_alignment = "BULLISH"
        elif ema_fast < ema_slow * 0.9995:
            ema_alignment = "BEARISH"
        else:
            ema_alignment = "NEUTRAL"
        
        # RSI
        rsi = self._rsi(closes, 14)
        
        # ADX
        adx = self._adx(highs, lows, closes, 14)
        
        # ATR
        atr = self._atr(highs, lows, closes, 14)
        
        # Volatility state
        atr_pct = (atr / current_price) * 100
        if atr_pct < 0.5:
            volatility_state = "LOW"
        elif atr_pct < 1.5:
            volatility_state = "NORMAL"
        elif atr_pct < 3.0:
            volatility_state = "HIGH"
        else:
            volatility_state = "EXTREME"
        
        # Structure (HH/HL, LH/LL, or RANGE)
        recent_high = np.max(highs[-20:])
        recent_low = np.min(lows[-20:])
        prev_high = np.max(highs[-40:-20])
        prev_low = np.min(lows[-40:-20])
        
        if recent_high > prev_high and recent_low > prev_low:
            structure = "HH_HL"  # Higher highs, higher lows (uptrend)
        elif recent_high < prev_high and recent_low < prev_low:
            structure = "LH_LL"  # Lower highs, lower lows (downtrend)
        else:
            structure = "RANGE"
        
        # Momentum score
        momentum_score = self._calculate_momentum_score(rsi, adx, ema_alignment)
        
        # Trend state
        trend = self._determine_trend_state(ema_alignment, structure, adx, rsi, momentum_score)
        
        # Trend strength
        trend_strength = self._calculate_trend_strength(adx, ema_fast, ema_slow, structure)
        
        # Reliability (how clean is the signal)
        reliability = self._calculate_reliability(adx, volatility_state, structure)
        
        return TimeframeAnalysis(
            timeframe=tf_name,
            trend=trend,
            trend_strength=trend_strength,
            current_price=current_price,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            ema_alignment=ema_alignment,
            rsi=rsi,
            adx=adx,
            momentum_score=momentum_score,
            recent_high=recent_high,
            recent_low=recent_low,
            structure=structure,
            atr=atr,
            volatility_state=volatility_state,
            reliability=reliability
        )
    
    def _determine_trend_state(self, ema_alignment: str, structure: str, adx: float, rsi: float, momentum: int) -> TrendState:
        """Classify trend state based on multiple factors."""
        if ema_alignment == "BULLISH" and structure == "HH_HL":
            if adx > 35 and rsi > 60:
                return TrendState.STRONG_BULLISH
            elif adx > 25 or rsi > 55:
                return TrendState.BULLISH
            else:
                return TrendState.WEAK_BULLISH
        
        elif ema_alignment == "BEARISH" and structure == "LH_LL":
            if adx > 35 and rsi < 40:
                return TrendState.STRONG_BEARISH
            elif adx > 25 or rsi < 45:
                return TrendState.BEARISH
            else:
                return TrendState.WEAK_BEARISH
        
        elif structure == "RANGE":
            if adx < 20:
                return TrendState.RANGING
            else:
                return TrendState.VOLATILE
        
        else:
            return TrendState.RANGING
    
    def _calculate_alignment(self, all_tf: List[TimeframeAnalysis]) -> int:
        """
        Calculate how many timeframes agree on trend direction.
        Returns 0-9.
        """
        bullish_count = 0
        bearish_count = 0
        
        for tf in all_tf:
            if "BULLISH" in tf.trend.value:
                bullish_count += 1
            elif "BEARISH" in tf.trend.value:
                bearish_count += 1
        
        # Return the maximum agreement
        return max(bullish_count, bearish_count)
    
    def _determine_regime(self, all_tf: List[TimeframeAnalysis]) -> MarketRegime:
        """Determine overall market regime based on all timeframes."""
        # Weight higher timeframes more heavily
        h4 = all_tf[8]
        h1 = all_tf[7]
        m30 = all_tf[6]
        m15 = all_tf[5]
        
        # Check higher timeframe consensus
        htf_trends = [h4.trend, h1.trend, m30.trend, m15.trend]
        
        bullish = sum(1 for t in htf_trends if "BULLISH" in t.value)
        bearish = sum(1 for t in htf_trends if "BEARISH" in t.value)
        ranging = sum(1 for t in htf_trends if t == TrendState.RANGING)
        
        if bullish >= 3:
            if h4.trend == TrendState.STRONG_BULLISH:
                return MarketRegime.STRONG_UPTREND
            elif h4.adx > 30:
                return MarketRegime.UPTREND
            else:
                return MarketRegime.WEAK_UPTREND
        
        elif bearish >= 3:
            if h4.trend == TrendState.STRONG_BEARISH:
                return MarketRegime.STRONG_DOWNTREND
            elif h4.adx > 30:
                return MarketRegime.DOWNTREND
            else:
                return MarketRegime.WEAK_DOWNTREND
        
        elif ranging >= 3:
            return MarketRegime.RANGE_BOUND
        
        else:
            # Mixed signals
            if h4.volatility_state in ["HIGH", "EXTREME"]:
                return MarketRegime.VOLATILE
            else:
                return MarketRegime.TRANSITION
    
    def _determine_trend_direction(self, all_tf: List[TimeframeAnalysis]) -> str:
        """Determine primary trend direction."""
        alignment = self._calculate_alignment(all_tf)
        
        bullish = sum(1 for tf in all_tf if "BULLISH" in tf.trend.value)
        bearish = sum(1 for tf in all_tf if "BEARISH" in tf.trend.value)
        
        if bullish > bearish and alignment >= 5:
            return "BULLISH"
        elif bearish > bullish and alignment >= 5:
            return "BEARISH"
        else:
            return "NEUTRAL"
    
    def _calculate_trend_confidence(self, all_tf: List[TimeframeAnalysis], alignment: int) -> int:
        """Calculate confidence in trend direction (0-100)."""
        # Base confidence from alignment
        base = (alignment / 9) * 60
        
        # Bonus from higher timeframe reliability
        h4_bonus = (all_tf[8].reliability / 100) * 20
        h1_bonus = (all_tf[7].reliability / 100) * 10
        m30_bonus = (all_tf[6].reliability / 100) * 10
        
        total = int(base + h4_bonus + h1_bonus + m30_bonus)
        return min(100, total)
    
    def _generate_recommendation(self, all_tf: List[TimeframeAnalysis], alignment: int, regime: MarketRegime) -> Tuple[str, str]:
        """
        Generate trading recommendation based on MTF analysis.
        Returns (direction, quality).
        """
        h4 = all_tf[8]
        h1 = all_tf[7]
        m15 = all_tf[5]
        m5 = all_tf[3]
        
        # Quality assessment
        if alignment >= 8 and h4.reliability > 70 and h1.reliability > 70:
            quality = "EXCELLENT"
        elif alignment >= 6 and h4.reliability > 60:
            quality = "GOOD"
        elif alignment >= 4:
            quality = "FAIR"
        else:
            quality = "POOR"
        
        # Direction recommendation
        if regime in [MarketRegime.STRONG_UPTREND, MarketRegime.UPTREND]:
            if m5.trend in [TrendState.BULLISH, TrendState.STRONG_BULLISH]:
                return ("BUY", quality)
            elif m5.trend in [TrendState.BEARISH, TrendState.STRONG_BEARISH]:
                return ("WAIT", "POOR")  # Divergence
            else:
                return ("WAIT", quality)
        
        elif regime in [MarketRegime.STRONG_DOWNTREND, MarketRegime.DOWNTREND]:
            if m5.trend in [TrendState.BEARISH, TrendState.STRONG_BEARISH]:
                return ("SELL", quality)
            elif m5.trend in [TrendState.BULLISH, TrendState.STRONG_BULLISH]:
                return ("WAIT", "POOR")  # Divergence
            else:
                return ("WAIT", quality)
        
        else:
            # Range or transition - wait for clarity
            return ("WAIT", quality)
    
    def _detect_divergence(self, all_tf: List[TimeframeAnalysis]) -> bool:
        """Detect trend divergence between timeframes."""
        h4 = all_tf[8]
        m5 = all_tf[3]
        
        h4_bullish = "BULLISH" in h4.trend.value
        h4_bearish = "BEARISH" in h4.trend.value
        m5_bullish = "BULLISH" in m5.trend.value
        m5_bearish = "BEARISH" in m5.trend.value
        
        # Divergence = H4 bullish but M5 bearish (or vice versa)
        return (h4_bullish and m5_bearish) or (h4_bearish and m5_bullish)
    
    def _detect_regime_shift(self, all_tf: List[TimeframeAnalysis]) -> bool:
        """Detect imminent regime shift."""
        h4 = all_tf[8]
        h1 = all_tf[7]
        m30 = all_tf[6]
        m15 = all_tf[5]
        
        # Regime shift signals:
        # 1. Lower TFs changing direction before higher TFs
        # 2. Structure breakdown
        # 3. Extreme volatility
        
        ltf_bullish = sum(1 for tf in all_tf[:4] if "BULLISH" in tf.trend.value)
        ltf_bearish = sum(1 for tf in all_tf[:4] if "BEARISH" in tf.trend.value)
        
        htf_bullish = "BULLISH" in h4.trend.value or "BULLISH" in h1.trend.value
        htf_bearish = "BEARISH" in h4.trend.value or "BEARISH" in h1.trend.value
        
        # Lower TFs reversing vs higher TFs
        if htf_bullish and ltf_bearish >= 3:
            return True
        if htf_bearish and ltf_bullish >= 3:
            return True
        
        # Extreme volatility
        if h4.volatility_state == "EXTREME" or h1.volatility_state == "EXTREME":
            return True
        
        return False
    
    def _generate_notes(self, all_tf: List[TimeframeAnalysis], alignment: int, divergence: bool, regime_shift: bool) -> str:
        """Generate human-readable analysis notes."""
        notes = []
        
        if alignment >= 8:
            notes.append("EXCEPTIONAL alignment across all timeframes")
        elif alignment >= 6:
            notes.append("Strong multi-timeframe alignment")
        elif alignment >= 4:
            notes.append("Moderate timeframe agreement")
        else:
            notes.append("Poor timeframe alignment - WAIT for clarity")
        
        if divergence:
            notes.append("⚠️ DIVERGENCE detected between H4 and M5")
        
        if regime_shift:
            notes.append("⚠️ REGIME SHIFT imminent - reduce position size")
        
        h4 = all_tf[8]
        if h4.volatility_state == "EXTREME":
            notes.append("⚠️ EXTREME volatility on H4 - avoid trading")
        
        return " | ".join(notes)
    
    # ═══════════════════════════════════════════════════════════════════════
    # TECHNICAL INDICATOR CALCULATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def _ema(self, data: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(data) < period:
            return data[-1]
        alpha = 2 / (period + 1)
        ema = data[0]
        for price in data[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return ema
    
    def _rsi(self, data: np.ndarray, period: int = 14) -> float:
        """Calculate RSI."""
        if len(data) < period + 1:
            return 50.0
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _adx(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """Calculate ADX (Average Directional Index)."""
        if len(highs) < period + 1:
            return 0.0
        
        # True Range
        tr = np.maximum(highs[1:] - lows[1:], 
                       np.abs(highs[1:] - closes[:-1]),
                       np.abs(lows[1:] - closes[:-1]))
        
        # Directional Movement
        plus_dm = np.maximum(highs[1:] - highs[:-1], 0)
        minus_dm = np.maximum(lows[:-1] - lows[1:], 0)
        
        # Smooth
        atr = np.mean(tr[-period:])
        plus_di = 100 * np.mean(plus_dm[-period:]) / atr if atr > 0 else 0
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr if atr > 0 else 0
        
        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
        return dx
    
    def _atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """Calculate ATR (Average True Range)."""
        if len(highs) < period + 1:
            return 0.0
        tr = np.maximum(highs[1:] - lows[1:],
                       np.abs(highs[1:] - closes[:-1]),
                       np.abs(lows[1:] - closes[:-1]))
        return np.mean(tr[-period:])
    
    def _calculate_momentum_score(self, rsi: float, adx: float, ema_alignment: str) -> int:
        """Calculate momentum score (0-100)."""
        score = 0
        
        # RSI contribution (0-40 points)
        if rsi > 70:
            score += 40
        elif rsi > 60:
            score += 30
        elif rsi > 50:
            score += 20
        elif rsi < 30:
            score += 40  # Oversold = momentum shift
        elif rsi < 40:
            score += 30
        elif rsi < 50:
            score += 20
        
        # ADX contribution (0-40 points)
        if adx > 40:
            score += 40
        elif adx > 30:
            score += 30
        elif adx > 20:
            score += 20
        else:
            score += 10
        
        # EMA alignment (0-20 points)
        if ema_alignment in ["BULLISH", "BEARISH"]:
            score += 20
        elif ema_alignment == "NEUTRAL":
            score += 10
        
        return min(100, score)
    
    def _calculate_trend_strength(self, adx: float, ema_fast: float, ema_slow: float, structure: str) -> int:
        """Calculate trend strength (0-100)."""
        score = 0
        
        # ADX (0-50 points)
        if adx > 40:
            score += 50
        elif adx > 30:
            score += 40
        elif adx > 20:
            score += 25
        else:
            score += 10
        
        # EMA separation (0-30 points)
        separation = abs(ema_fast - ema_slow) / ema_slow * 100
        if separation > 2:
            score += 30
        elif separation > 1:
            score += 20
        elif separation > 0.5:
            score += 10
        
        # Structure (0-20 points)
        if structure in ["HH_HL", "LH_LL"]:
            score += 20
        elif structure == "RANGE":
            score += 0
        
        return min(100, score)
    
    def _calculate_reliability(self, adx: float, volatility_state: str, structure: str) -> int:
        """Calculate signal reliability (0-100)."""
        score = 50  # Base
        
        # Strong ADX = reliable trend
        if adx > 30:
            score += 30
        elif adx > 20:
            score += 15
        elif adx < 15:
            score -= 20
        
        # Low volatility = more reliable
        if volatility_state == "LOW":
            score += 20
        elif volatility_state == "EXTREME":
            score -= 30
        
        # Clear structure = reliable
        if structure in ["HH_HL", "LH_LL"]:
            score += 0
        elif structure == "RANGE":
            score -= 20
        
        return max(0, min(100, score))


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

_mtf_analyzer = None

def get_mtf_analyzer() -> MultiTimeframeAnalyzer:
    """Get or create singleton MTF analyzer instance."""
    global _mtf_analyzer
    if _mtf_analyzer is None:
        _mtf_analyzer = MultiTimeframeAnalyzer()
    return _mtf_analyzer
