"""
AEGIS GOLD — Multi-Timeframe Context Aggregator

Aggregates analysis from all timeframes and provides unified MTF context for trading decisions.

Philosophy:
-----------
Trading decisions must respect the hierarchical nature of timeframes:
- H4 sets the institutional bias (primary trend)
- H1 defines the session trend (HTF structure)
- M30 shows swing structure
- M15 provides pattern context
- M5 confirms entry signals
- M1 times execution

Lower timeframes CANNOT override higher timeframe bias.
Alignment across timeframes increases trade quality.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger("aegis.mtf_context")


class TimeframeBias(Enum):
    """Directional bias for a timeframe."""
    STRONG_BULLISH = "STRONG_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    STRONG_BEARISH = "STRONG_BEARISH"
    UNKNOWN = "UNKNOWN"


@dataclass
class TimeframeState:
    """State analysis for a single timeframe."""
    timeframe: str
    bias: TimeframeBias
    trend_strength: float  # 0.0-1.0
    structure: str  # "HH_HL" | "LH_LL" | "RANGE" | "UNKNOWN"
    ema_aligned: bool
    adx: float
    rsi: float
    recent_high: float
    recent_low: float
    reliability: float  # 0.0-1.0 (signal clarity)


@dataclass
class MTFContext:
    """
    Unified multi-timeframe context for trading decisions.
    
    Provides:
    - HTF bias (what direction institutions are trading)
    - MTF alignment (how many timeframes agree)
    - Divergence warnings (conflicts between timeframes)
    - Trade recommendations based on complete picture
    """
    
    # Individual timeframe states
    h4: TimeframeState
    h1: TimeframeState
    m30: TimeframeState
    m15: TimeframeState
    m5: TimeframeState
    m1: TimeframeState
    
    # Aggregated insights
    htf_bias: str  # "BULLISH" | "BEARISH" | "NEUTRAL" (from H4/H1)
    htf_bias_strength: float  # 0.0-1.0
    
    mtf_alignment_score: float  # 0.0-1.0 (how many timeframes agree)
    bullish_timeframes: int  # Count of bullish timeframes
    bearish_timeframes: int  # Count of bearish timeframes
    neutral_timeframes: int  # Count of ranging timeframes
    
    # Compatibility checks
    buy_compatible: bool  # Safe to take BUY trades
    sell_compatible: bool  # Safe to take SELL trades
    
    # Warnings
    divergence_detected: bool  # HTF and LTF conflict
    divergence_details: str
    
    # Quality assessment
    trade_quality: str  # "EXCELLENT" | "GOOD" | "FAIR" | "POOR"
    recommended_direction: str  # "BUY" | "SELL" | "WAIT"
    
    def __str__(self) -> str:
        """Human-readable summary."""
        return (
            f"MTF Context: HTF Bias={self.htf_bias} ({self.htf_bias_strength:.2f}), "
            f"Alignment={self.mtf_alignment_score:.2f}, "
            f"Bull={self.bullish_timeframes} Bear={self.bearish_timeframes} Neutral={self.neutral_timeframes}, "
            f"Quality={self.trade_quality}"
        )


class MTFContextAggregator:
    """
    Analyzes all timeframes and produces unified MTF context.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("aegis.mtf_context")
    
    def analyze(
        self,
        candles_h4: Optional[Any],
        candles_h1: Optional[Any],
        candles_m30: Optional[Any],
        candles_m15: Optional[Any],
        candles_m5: Optional[Any],
        candles_m1: Optional[Any],
    ) -> MTFContext:
        """
        Analyze all timeframes and produce unified MTF context.
        
        Returns:
            MTFContext with complete multi-timeframe analysis
        """
        
        # Analyze each timeframe
        h4_state = self._analyze_timeframe("H4", candles_h4)
        h1_state = self._analyze_timeframe("H1", candles_h1)
        m30_state = self._analyze_timeframe("M30", candles_m30)
        m15_state = self._analyze_timeframe("M15", candles_m15)
        m5_state = self._analyze_timeframe("M5", candles_m5)
        m1_state = self._analyze_timeframe("M1", candles_m1)
        
        # Determine HTF bias (H4 and H1 combined)
        htf_bias, htf_strength = self._determine_htf_bias(h4_state, h1_state)
        
        # Calculate alignment
        states = [h4_state, h1_state, m30_state, m15_state, m5_state, m1_state]
        alignment_score, bull_count, bear_count, neutral_count = self._calculate_alignment(states)
        
        # Check compatibility
        buy_compat, sell_compat = self._check_compatibility(htf_bias, htf_strength, states)
        
        # Detect divergences
        divergence, div_details = self._detect_divergence(h4_state, h1_state, m5_state, m1_state)
        
        # Assess quality
        quality = self._assess_quality(alignment_score, htf_strength, divergence)
        
        # Recommendation
        recommendation = self._make_recommendation(htf_bias, alignment_score, divergence, buy_compat, sell_compat)
        
        return MTFContext(
            h4=h4_state,
            h1=h1_state,
            m30=m30_state,
            m15=m15_state,
            m5=m5_state,
            m1=m1_state,
            htf_bias=htf_bias,
            htf_bias_strength=htf_strength,
            mtf_alignment_score=alignment_score,
            bullish_timeframes=bull_count,
            bearish_timeframes=bear_count,
            neutral_timeframes=neutral_count,
            buy_compatible=buy_compat,
            sell_compatible=sell_compat,
            divergence_detected=divergence,
            divergence_details=div_details,
            trade_quality=quality,
            recommended_direction=recommendation
        )
    
    def _analyze_timeframe(self, timeframe: str, candles: Optional[Any]) -> TimeframeState:
        """
        Analyze a single timeframe.
        
        Returns TimeframeState with bias, trend strength, structure.
        """
        if candles is None or len(candles) < 20:
            return TimeframeState(
                timeframe=timeframe,
                bias=TimeframeBias.UNKNOWN,
                trend_strength=0.0,
                structure="UNKNOWN",
                ema_aligned=False,
                adx=0.0,
                rsi=50.0,
                recent_high=0.0,
                recent_low=0.0,
                reliability=0.0
            )
        
        # Import indicators
        from modules.talib_indicators import EMA, ADX, RSI
        
        # Extract OHLC
        try:
            if hasattr(candles, 'close'):
                closes = candles['close'].values.astype(float)
                highs = candles['high'].values.astype(float)
                lows = candles['low'].values.astype(float)
            elif isinstance(candles, list) and len(candles) > 0:
                closes = [c['close'] for c in candles]
                highs = [c['high'] for c in candles]
                lows = [c['low'] for c in candles]
            else:
                closes = list(candles)
                highs = closes
                lows = closes
        except Exception as e:
            self.logger.warning(f"Failed to extract OHLC from {timeframe}: {e}")
            closes = []
            highs = []
            lows = []
        
        if len(closes) < 20:
            return TimeframeState(
                timeframe=timeframe,
                bias=TimeframeBias.UNKNOWN,
                trend_strength=0.0,
                structure="UNKNOWN",
                ema_aligned=False,
                adx=0.0,
                rsi=50.0,
                recent_high=0.0,
                recent_low=0.0,
                reliability=0.0
            )
        
        # Calculate indicators
        ema9 = EMA(closes, 9)
        ema21 = EMA(closes, 21)
        adx_vals = ADX(highs, lows, closes, 14)
        rsi_vals = RSI(closes, 14)
        
        curr_price = closes[-1]
        curr_ema9 = ema9[-1] if len(ema9) > 0 else curr_price
        curr_ema21 = ema21[-1] if len(ema21) > 0 else curr_price
        curr_adx = adx_vals[-1] if len(adx_vals) > 0 else 0.0
        curr_rsi = rsi_vals[-1] if len(rsi_vals) > 0 else 50.0
        
        # EMA alignment
        ema_aligned_bull = curr_price > curr_ema9 and curr_ema9 > curr_ema21
        ema_aligned_bear = curr_price < curr_ema9 and curr_ema9 < curr_ema21
        ema_aligned = ema_aligned_bull or ema_aligned_bear
        
        # Structure (simple swing high/low analysis)
        recent_high = max(highs[-10:]) if len(highs) >= 10 else curr_price
        recent_low = min(lows[-10:]) if len(lows) >= 10 else curr_price
        
        # Determine structure type
        if len(highs) >= 20:
            prev_high = max(highs[-20:-10])
            prev_low = min(lows[-20:-10])
            
            if recent_high > prev_high and recent_low > prev_low:
                structure = "HH_HL"  # Higher highs, higher lows
            elif recent_high < prev_high and recent_low < prev_low:
                structure = "LH_LL"  # Lower highs, lower lows
            else:
                structure = "RANGE"
        else:
            structure = "UNKNOWN"
        
        # Determine bias
        bias = TimeframeBias.NEUTRAL
        trend_strength = 0.0
        
        if structure == "HH_HL" and ema_aligned_bull:
            if curr_adx > 30:
                bias = TimeframeBias.STRONG_BULLISH
                trend_strength = min(1.0, curr_adx / 40.0)
            elif curr_adx > 20:
                bias = TimeframeBias.BULLISH
                trend_strength = min(0.8, curr_adx / 30.0)
            else:
                bias = TimeframeBias.BULLISH
                trend_strength = 0.5
        
        elif structure == "LH_LL" and ema_aligned_bear:
            if curr_adx > 30:
                bias = TimeframeBias.STRONG_BEARISH
                trend_strength = min(1.0, curr_adx / 40.0)
            elif curr_adx > 20:
                bias = TimeframeBias.BEARISH
                trend_strength = min(0.8, curr_adx / 30.0)
            else:
                bias = TimeframeBias.BEARISH
                trend_strength = 0.5
        
        elif structure == "HH_HL":
            bias = TimeframeBias.BULLISH
            trend_strength = 0.4
        
        elif structure == "LH_LL":
            bias = TimeframeBias.BEARISH
            trend_strength = 0.4
        
        else:
            bias = TimeframeBias.NEUTRAL
            trend_strength = 0.2
        
        # Reliability (based on ADX and structure clarity)
        reliability = min(1.0, (curr_adx / 30.0) * 0.7 + (0.3 if structure != "RANGE" else 0.0))
        
        return TimeframeState(
            timeframe=timeframe,
            bias=bias,
            trend_strength=trend_strength,
            structure=structure,
            ema_aligned=ema_aligned,
            adx=curr_adx,
            rsi=curr_rsi,
            recent_high=recent_high,
            recent_low=recent_low,
            reliability=reliability
        )
    
    def _determine_htf_bias(self, h4: TimeframeState, h1: TimeframeState) -> tuple[str, float]:
        """
        Determine higher timeframe bias from H4 and H1.
        H4 is primary, H1 is confirmation.
        
        Returns: (bias_str, strength)
        """
        # H4 carries more weight
        h4_weight = 0.6
        h1_weight = 0.4
        
        h4_score = 0.0
        if h4.bias in [TimeframeBias.STRONG_BULLISH, TimeframeBias.BULLISH]:
            h4_score = h4.trend_strength
        elif h4.bias in [TimeframeBias.STRONG_BEARISH, TimeframeBias.BEARISH]:
            h4_score = -h4.trend_strength
        
        h1_score = 0.0
        if h1.bias in [TimeframeBias.STRONG_BULLISH, TimeframeBias.BULLISH]:
            h1_score = h1.trend_strength
        elif h1.bias in [TimeframeBias.STRONG_BEARISH, TimeframeBias.BEARISH]:
            h1_score = -h1.trend_strength
        
        combined_score = h4_score * h4_weight + h1_score * h1_weight
        strength = abs(combined_score)
        
        if combined_score > 0.3:
            bias = "BULLISH"
        elif combined_score < -0.3:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
        
        return bias, strength
    
    def _calculate_alignment(self, states: List[TimeframeState]) -> tuple[float, int, int, int]:
        """
        Calculate how many timeframes agree on direction.
        
        Returns: (alignment_score, bull_count, bear_count, neutral_count)
        """
        bull_count = 0
        bear_count = 0
        neutral_count = 0
        
        for state in states:
            if state.bias in [TimeframeBias.STRONG_BULLISH, TimeframeBias.BULLISH]:
                bull_count += 1
            elif state.bias in [TimeframeBias.STRONG_BEARISH, TimeframeBias.BEARISH]:
                bear_count += 1
            else:
                neutral_count += 1
        
        # Alignment = % of timeframes agreeing on same direction
        total = len(states)
        max_agree = max(bull_count, bear_count, neutral_count)
        alignment_score = max_agree / total if total > 0 else 0.0
        
        return alignment_score, bull_count, bear_count, neutral_count
    
    def _check_compatibility(
        self,
        htf_bias: str,
        htf_strength: float,
        states: List[TimeframeState]
    ) -> tuple[bool, bool]:
        """
        Check if BUY/SELL trades are compatible with HTF bias.
        
        Returns: (buy_compatible, sell_compatible)
        """
        # Strong HTF bias blocks opposite direction
        if htf_bias == "BULLISH" and htf_strength > 0.6:
            return True, False  # Only BUY allowed
        
        elif htf_bias == "BEARISH" and htf_strength > 0.6:
            return False, True  # Only SELL allowed
        
        elif htf_bias == "BULLISH" and htf_strength > 0.4:
            # Moderate bullish bias - allow BUY, be cautious on SELL
            # SELL allowed only if M5/M1 show strong counter-structure
            m5 = next((s for s in states if s.timeframe == "M5"), None)
            m1 = next((s for s in states if s.timeframe == "M1"), None)
            
            sell_allowed = False
            if m5 and m1:
                if m5.bias in [TimeframeBias.STRONG_BEARISH, TimeframeBias.BEARISH] and \
                   m1.bias in [TimeframeBias.STRONG_BEARISH, TimeframeBias.BEARISH]:
                    sell_allowed = True
            
            return True, sell_allowed
        
        elif htf_bias == "BEARISH" and htf_strength > 0.4:
            # Moderate bearish bias - allow SELL, be cautious on BUY
            m5 = next((s for s in states if s.timeframe == "M5"), None)
            m1 = next((s for s in states if s.timeframe == "M1"), None)
            
            buy_allowed = False
            if m5 and m1:
                if m5.bias in [TimeframeBias.STRONG_BULLISH, TimeframeBias.BULLISH] and \
                   m1.bias in [TimeframeBias.STRONG_BULLISH, TimeframeBias.BULLISH]:
                    buy_allowed = True
            
            return buy_allowed, True
        
        else:
            # Weak/neutral HTF bias - both directions allowed
            return True, True
    
    def _detect_divergence(
        self,
        h4: TimeframeState,
        h1: TimeframeState,
        m5: TimeframeState,
        m1: TimeframeState
    ) -> tuple[bool, str]:
        """
        Detect dangerous divergences between HTF and LTF.
        
        Returns: (divergence_detected, details)
        """
        divergences = []
        
        # H4 vs M5 divergence
        if h4.bias in [TimeframeBias.STRONG_BULLISH, TimeframeBias.BULLISH] and \
           m5.bias in [TimeframeBias.STRONG_BEARISH, TimeframeBias.BEARISH]:
            divergences.append("H4 bullish but M5 bearish")
        
        elif h4.bias in [TimeframeBias.STRONG_BEARISH, TimeframeBias.BEARISH] and \
             m5.bias in [TimeframeBias.STRONG_BULLISH, TimeframeBias.BULLISH]:
            divergences.append("H4 bearish but M5 bullish")
        
        # H1 vs M5 divergence
        if h1.bias in [TimeframeBias.STRONG_BULLISH, TimeframeBias.BULLISH] and \
           m5.bias in [TimeframeBias.STRONG_BEARISH, TimeframeBias.BEARISH]:
            divergences.append("H1 bullish but M5 bearish")
        
        elif h1.bias in [TimeframeBias.STRONG_BEARISH, TimeframeBias.BEARISH] and \
             m5.bias in [TimeframeBias.STRONG_BULLISH, TimeframeBias.BULLISH]:
            divergences.append("H1 bearish but M5 bullish")
        
        detected = len(divergences) > 0
        details = "; ".join(divergences) if detected else "No divergence"
        
        return detected, details
    
    def _assess_quality(self, alignment: float, htf_strength: float, divergence: bool) -> str:
        """
        Assess overall trade quality based on MTF analysis.
        """
        if divergence:
            return "POOR"
        
        if alignment >= 0.8 and htf_strength >= 0.6:
            return "EXCELLENT"
        
        elif alignment >= 0.6 and htf_strength >= 0.4:
            return "GOOD"
        
        elif alignment >= 0.5:
            return "FAIR"
        
        else:
            return "POOR"
    
    def _make_recommendation(
        self,
        htf_bias: str,
        alignment: float,
        divergence: bool,
        buy_compat: bool,
        sell_compat: bool
    ) -> str:
        """
        Make trading recommendation based on MTF analysis.
        """
        if divergence:
            return "WAIT"
        
        if alignment < 0.5:
            return "WAIT"
        
        if htf_bias == "BULLISH" and buy_compat:
            return "BUY"
        
        elif htf_bias == "BEARISH" and sell_compat:
            return "SELL"
        
        else:
            return "WAIT"
