#!/usr/bin/env python3
"""
AEGIS GOLD - Advanced Pattern Recognition Engine
=================================================
Detects chart patterns with proper TP/SL based on pattern structure.
Replaces scalping with high-probability pattern trades.

PATTERNS DETECTED:
✓ Head & Shoulders / Inverse H&S
✓ Double Top / Double Bottom  
✓ Triple Top / Triple Bottom
✓ Bull/Bear Flags
✓ Ascending/Descending Triangles
✓ Wedges (Rising/Falling)
✓ Candlestick Patterns (Engulfing, Hammer, etc.)

All patterns include:
- Proper entry point
- Pattern-based SL
- Pattern-based TP (2:1 to 3:1 R:R)
- Invalidation level
- Confidence score
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger("aegis.pattern")

@dataclass
class Pattern:
    """Pattern detection result"""
    name: str                   
    type: str                   # 'REVERSAL' or 'CONTINUATION'
    direction: str              # 'BULLISH' or 'BEARISH'
    confidence: float           # 0-100%
    entry_price: float          
    stop_loss: float            
    take_profit: float          
    risk_reward: float          
    formation_bars: int         
    key_levels: Dict            
    invalidation_level: float   
    metadata: Dict              


class PatternRecognitionEngine:
    """Advanced pattern scanner for XAUUSD/EURUSD"""
    
    def __init__(self, min_bars=10, max_bars=100):
        self.min_bars = min_bars
        self.max_bars = max_bars
        self.tolerance = 0.005  # 0.5% price tolerance
        logger.info("Pattern Recognition Engine v2.0 initialized")
    
    def scan_all_patterns(self, highs: np.ndarray, lows: np.ndarray, 
                         closes: np.ndarray, opens: np.ndarray = None) -> List[Pattern]:
        """
        Main entry point - scan for ALL pattern types
        Returns list sorted by confidence
        """
        patterns = []
        
        # Ensure array types
        highs = np.asarray(highs, dtype=float)
        lows = np.asarray(lows, dtype=float)
        closes = np.asarray(closes, dtype=float)
        if opens is not None:
            opens = np.asarray(opens, dtype=float)
        
        # 1. REVERSAL PATTERNS
        patterns.extend(self._detect_head_shoulders(highs, lows, closes))
        patterns.extend(self._detect_double_patterns(highs, lows, closes))
        patterns.extend(self._detect_triple_patterns(highs, lows, closes))
        
        # 2. CONTINUATION PATTERNS  
        patterns.extend(self._detect_flags(highs, lows, closes))
        patterns.extend(self._detect_triangles(highs, lows, closes))
        patterns.extend(self._detect_wedges(highs, lows, closes))
        
        # 3. CANDLESTICK PATTERNS
        if opens is not None:
            patterns.extend(self._detect_candlestick(opens, highs, lows, closes))
        
        # Sort by confidence
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        
        logger.info(f"Found {len(patterns)} patterns")
        return patterns
    
    def _detect_head_shoulders(self, highs, lows, closes) -> List[Pattern]:
        """Detect H&S and Inverse H&S patterns"""
        patterns = []
        n = len(highs)
        if n < 30:
            return patterns
        
        # Use last 50 bars
        window = min(50, n)
        h = highs[-window:]
        l = lows[-window:]
        c = closes[-window:]
        
        # Find swing highs (for H&S)
        swings_h = self._find_swings(h, 'high')
        
        if len(swings_h) >= 3:
            ls, head, rs = swings_h[-3:]
            ls_val, head_val, rs_val = h[ls], h[head], h[rs]
            
            # H&S criteria: head is highest, shoulders similar
            if head_val > ls_val and head_val > rs_val and ls < head < rs:
                shoulder_diff = abs(ls_val - rs_val) / ls_val
                
                if shoulder_diff < 0.015:  # Shoulders within 1.5%
                    neckline = (l[ls] + l[rs]) / 2
                    current = c[-1]
                    
                    if current <= neckline * 1.005:
                        height = head_val - neckline
                        entry = neckline * 0.998
                        sl = head_val * 1.003
                        tp = entry - height  # Project down
                        rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                        
                        if rr >= 1.8:
                            conf = self._calc_confidence('H&S', shoulder_diff, rr)
                            patterns.append(Pattern(
                                name="Head and Shoulders",
                                type="REVERSAL",
                                direction="BEARISH",
                                confidence=conf,
                                entry_price=entry,
                                stop_loss=sl,
                                take_profit=tp,
                                risk_reward=rr,
                                formation_bars=rs - ls,
                                key_levels={'neckline': neckline, 'head': head_val},
                                invalidation_level=head_val,
                                metadata={'symmetry': 1-shoulder_diff}
                            ))
        
        # Inverse H&S (same logic on lows)
        swings_l = self._find_swings(l, 'low')
        if len(swings_l) >= 3:
            ls, head, rs = swings_l[-3:]
            ls_val, head_val, rs_val = l[ls], l[head], l[rs]
            
            if head_val < ls_val and head_val < rs_val and ls < head < rs:
                shoulder_diff = abs(ls_val - rs_val) / ls_val
                
                if shoulder_diff < 0.015:
                    neckline = (h[ls] + h[rs]) / 2
                    current = c[-1]
                    
                    if current >= neckline * 0.995:
                        height = neckline - head_val
                        entry = neckline * 1.002
                        sl = head_val * 0.997
                        tp = entry + height
                        rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                        
                        if rr >= 1.8:
                            conf = self._calc_confidence('INV_H&S', shoulder_diff, rr)
                            patterns.append(Pattern(
                                name="Inverse Head and Shoulders",
                                type="REVERSAL",
                                direction="BULLISH",
                                confidence=conf,
                                entry_price=entry,
                                stop_loss=sl,
                                take_profit=tp,
                                risk_reward=rr,
                                formation_bars=rs - ls,
                                key_levels={'neckline': neckline, 'head': head_val},
                                invalidation_level=head_val,
                                metadata={'symmetry': 1-shoulder_diff}
                            ))
        
        return patterns
    
    def _detect_double_patterns(self, highs, lows, closes) -> List[Pattern]:
        """Detect Double Top and Double Bottom"""
        patterns = []
        n = len(highs)
        if n < 20:
            return patterns
        
        window = min(40, n)
        h = highs[-window:]
        l = lows[-window:]
        c = closes[-window:]
        
        # DOUBLE TOP
        swings_h = self._find_swings(h, 'high')
        if len(swings_h) >= 2:
            p1, p2 = swings_h[-2:]
            peak1, peak2 = h[p1], h[p2]
            
            # Peaks similar within 0.5%
            if abs(peak1 - peak2) / peak1 < 0.005:
                trough = np.min(l[p1:p2+1])
                current = c[-1]
                
                if current <= trough * 1.003:
                    height = (peak1 + peak2) / 2 - trough
                    entry = trough * 0.997
                    sl = max(peak1, peak2) * 1.003
                    tp = entry - height
                    rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                    
                    if rr >= 2.0:
                        conf = self._calc_confidence('DOUBLE_TOP', 0, rr)
                        patterns.append(Pattern(
                            name="Double Top",
                            type="REVERSAL",
                            direction="BEARISH",
                            confidence=conf,
                            entry_price=entry,
                            stop_loss=sl,
                            take_profit=tp,
                            risk_reward=rr,
                            formation_bars=p2-p1,
                            key_levels={'peak1': peak1, 'peak2': peak2, 'trough': trough},
                            invalidation_level=max(peak1, peak2),
                            metadata={}
                        ))
        
        # DOUBLE BOTTOM
        swings_l = self._find_swings(l, 'low')
        if len(swings_l) >= 2:
            t1, t2 = swings_l[-2:]
            trough1, trough2 = l[t1], l[t2]
            
            if abs(trough1 - trough2) / trough1 < 0.005:
                peak = np.max(h[t1:t2+1])
                current = c[-1]
                
                if current >= peak * 0.997:
                    height = peak - (trough1 + trough2) / 2
                    entry = peak * 1.003
                    sl = min(trough1, trough2) * 0.997
                    tp = entry + height
                    rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                    
                    if rr >= 2.0:
                        conf = self._calc_confidence('DOUBLE_BOTTOM', 0, rr)
                        patterns.append(Pattern(
                            name="Double Bottom",
                            type="REVERSAL",
                            direction="BULLISH",
                            confidence=conf,
                            entry_price=entry,
                            stop_loss=sl,
                            take_profit=tp,
                            risk_reward=rr,
                            formation_bars=t2-t1,
                            key_levels={'trough1': trough1, 'trough2': trough2, 'peak': peak},
                            invalidation_level=min(trough1, trough2),
                            metadata={}
                        ))
        
        return patterns
    
    def _detect_triple_patterns(self, highs, lows, closes) -> List[Pattern]:
        """Detect Triple Top and Triple Bottom"""
        patterns = []
        n = len(highs)
        if n < 30:
            return patterns
        
        window = min(50, n)
        h = highs[-window:]
        l = lows[-window:]
        c = closes[-window:]
        
        swings_h = self._find_swings(h, 'high')
        if len(swings_h) >= 3:
            p1, p2, p3 = swings_h[-3:]
            pk1, pk2, pk3 = h[p1], h[p2], h[p3]
            avg_peak = (pk1 + pk2 + pk3) / 3.0
            if max(abs(pk1-avg_peak), abs(pk2-avg_peak), abs(pk3-avg_peak)) / avg_peak < 0.006:
                trough = np.min(l[p1:p3+1])
                height = avg_peak - trough
                entry = trough * 0.997
                sl = avg_peak * 1.003
                tp = entry - height
                rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                if rr >= 2.0:
                    conf = self._calc_confidence('TRIPLE_TOP', 0, rr)
                    patterns.append(Pattern(
                        name="Triple Top",
                        type="REVERSAL",
                        direction="BEARISH",
                        confidence=conf,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        risk_reward=rr,
                        formation_bars=p3-p1,
                        key_levels={'peak1': pk1, 'peak2': pk2, 'peak3': pk3, 'trough': trough},
                        invalidation_level=avg_peak,
                        metadata={}
                    ))

        swings_l = self._find_swings(l, 'low')
        if len(swings_l) >= 3:
            t1, t2, t3 = swings_l[-3:]
            tr1, tr2, tr3 = l[t1], l[t2], l[t3]
            avg_trough = (tr1 + tr2 + tr3) / 3.0
            if max(abs(tr1-avg_trough), abs(tr2-avg_trough), abs(tr3-avg_trough)) / avg_trough < 0.006:
                peak = np.max(h[t1:t3+1])
                height = peak - avg_trough
                entry = peak * 1.003
                sl = avg_trough * 0.997
                tp = entry + height
                rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                if rr >= 2.0:
                    conf = self._calc_confidence('TRIPLE_BOTTOM', 0, rr)
                    patterns.append(Pattern(
                        name="Triple Bottom",
                        type="REVERSAL",
                        direction="BULLISH",
                        confidence=conf,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        risk_reward=rr,
                        formation_bars=t3-t1,
                        key_levels={'trough1': tr1, 'trough2': tr2, 'trough3': tr3, 'peak': peak},
                        invalidation_level=avg_trough,
                        metadata={}
                    ))

        return patterns
    
    def _detect_flags(self, highs, lows, closes) -> List[Pattern]:
        """Detect Bull Flag and Bear Flag"""
        patterns = []
        n = len(closes)
        if n < 20:
            return patterns
        
        window = min(30, n)
        c = closes[-window:]
        h = highs[-window:]
        l = lows[-window:]
        
        half = window // 2
        
        # BULL FLAG: strong up move + tight consolidation
        move = (c[half] - c[0]) / c[0]
        if move > 0.02:  # 2% flagpole
            flag_range = (np.max(h[half:]) - np.min(l[half:])) / np.min(l[half:])
            if flag_range < 0.01:  # Tight flag
                flag_high = np.max(h[half:])
                flag_low = np.min(l[half:])
                pole_height = c[half] - c[0]
                
                entry = flag_high * 1.002
                sl = flag_low * 0.997
                tp = entry + pole_height
                rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                
                if rr >= 2.5:
                    conf = self._calc_confidence('BULL_FLAG', flag_range, rr)
                    patterns.append(Pattern(
                        name="Bull Flag",
                        type="CONTINUATION",
                        direction="BULLISH",
                        confidence=conf,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        risk_reward=rr,
                        formation_bars=window,
                        key_levels={'flag_high': flag_high, 'flag_low': flag_low},
                        invalidation_level=flag_low,
                        metadata={'pole_strength': move*100}
                    ))
        
        # BEAR FLAG
        if move < -0.02:
            flag_range = (np.max(h[half:]) - np.min(l[half:])) / np.min(l[half:])
            if flag_range < 0.01:
                flag_high = np.max(h[half:])
                flag_low = np.min(l[half:])
                pole_height = c[0] - c[half]
                
                entry = flag_low * 0.998
                sl = flag_high * 1.003
                tp = entry - pole_height
                rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                
                if rr >= 2.5:
                    conf = self._calc_confidence('BEAR_FLAG', flag_range, rr)
                    patterns.append(Pattern(
                        name="Bear Flag",
                        type="CONTINUATION",
                        direction="BEARISH",
                        confidence=conf,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        risk_reward=rr,
                        formation_bars=window,
                        key_levels={'flag_high': flag_high, 'flag_low': flag_low},
                        invalidation_level=flag_high,
                        metadata={'pole_strength': abs(move)*100}
                    ))
        
        return patterns
    
    def _detect_triangles(self, highs, lows, closes) -> List[Pattern]:
        """Detect Ascending, Descending, Symmetrical Triangles"""
        patterns = []
        n = len(highs)
        if n < 25:
            return patterns

        window = min(35, n)
        h = highs[-window:]
        l = lows[-window:]
        c = closes[-window:]

        swings_h = self._find_swings(h, 'high')
        swings_l = self._find_swings(l, 'low')

        if len(swings_h) >= 2 and len(swings_l) >= 2:
            h_vals = [h[i] for i in swings_h[-2:]]
            l_vals = [l[i] for i in swings_l[-2:]]

            # Ascending Triangle: flat tops, higher lows
            if abs(h_vals[0] - h_vals[1]) / h_vals[0] < 0.004 and l_vals[1] > l_vals[0]:
                resistance = (h_vals[0] + h_vals[1]) / 2.0
                height = resistance - l_vals[0]
                entry = resistance * 1.002
                sl = l_vals[-1] * 0.998
                tp = entry + height
                rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                if rr >= 2.0:
                    conf = self._calc_confidence('ASCENDING_TRIANGLE', 0, rr)
                    patterns.append(Pattern(
                        name="Ascending Triangle",
                        type="CONTINUATION",
                        direction="BULLISH",
                        confidence=conf,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        risk_reward=rr,
                        formation_bars=window,
                        key_levels={'resistance': resistance},
                        invalidation_level=l_vals[-1],
                        metadata={}
                    ))

            # Descending Triangle: flat bottoms, lower highs
            elif abs(l_vals[0] - l_vals[1]) / l_vals[0] < 0.004 and h_vals[1] < h_vals[0]:
                support = (l_vals[0] + l_vals[1]) / 2.0
                height = h_vals[0] - support
                entry = support * 0.998
                sl = h_vals[-1] * 1.002
                tp = entry - height
                rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                if rr >= 2.0:
                    conf = self._calc_confidence('DESCENDING_TRIANGLE', 0, rr)
                    patterns.append(Pattern(
                        name="Descending Triangle",
                        type="CONTINUATION",
                        direction="BEARISH",
                        confidence=conf,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        risk_reward=rr,
                        formation_bars=window,
                        key_levels={'support': support},
                        invalidation_level=h_vals[-1],
                        metadata={}
                    ))

        return patterns
    
    def _detect_wedges(self, highs, lows, closes) -> List[Pattern]:
        """Detect Rising and Falling Wedges"""
        patterns = []
        n = len(highs)
        if n < 25:
            return patterns

        window = min(35, n)
        h = highs[-window:]
        l = lows[-window:]
        c = closes[-window:]

        swings_h = self._find_swings(h, 'high')
        swings_l = self._find_swings(l, 'low')

        if len(swings_h) >= 2 and len(swings_l) >= 2:
            h_vals = [h[i] for i in swings_h[-2:]]
            l_vals = [l[i] for i in swings_l[-2:]]

            # Falling Wedge (Bullish Reversal): lower highs & lower lows, but range contracting
            if h_vals[1] < h_vals[0] and l_vals[1] < l_vals[0]:
                range1 = h_vals[0] - l_vals[0]
                range2 = h_vals[1] - l_vals[1]
                if range2 < range1 * 0.8:
                    entry = h_vals[-1] * 1.002
                    sl = l_vals[-1] * 0.997
                    height = range1
                    tp = entry + height * 1.5
                    rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                    if rr >= 2.0:
                        conf = self._calc_confidence('FALLING_WEDGE', 0, rr)
                        patterns.append(Pattern(
                            name="Falling Wedge",
                            type="REVERSAL",
                            direction="BULLISH",
                            confidence=conf,
                            entry_price=entry,
                            stop_loss=sl,
                            take_profit=tp,
                            risk_reward=rr,
                            formation_bars=window,
                            key_levels={'apex_high': h_vals[-1]},
                            invalidation_level=l_vals[-1],
                            metadata={}
                        ))

            # Rising Wedge (Bearish Reversal): higher highs & higher lows, range contracting
            elif h_vals[1] > h_vals[0] and l_vals[1] > l_vals[0]:
                range1 = h_vals[0] - l_vals[0]
                range2 = h_vals[1] - l_vals[1]
                if range2 < range1 * 0.8:
                    entry = l_vals[-1] * 0.998
                    sl = h_vals[-1] * 1.003
                    height = range1
                    tp = entry - height * 1.5
                    rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                    if rr >= 2.0:
                        conf = self._calc_confidence('RISING_WEDGE', 0, rr)
                        patterns.append(Pattern(
                            name="Rising Wedge",
                            type="REVERSAL",
                            direction="BEARISH",
                            confidence=conf,
                            entry_price=entry,
                            stop_loss=sl,
                            take_profit=tp,
                            risk_reward=rr,
                            formation_bars=window,
                            key_levels={'apex_low': l_vals[-1]},
                            invalidation_level=h_vals[-1],
                            metadata={}
                        ))

        return patterns
    
    def _detect_candlestick(self, opens, highs, lows, closes) -> List[Pattern]:
        """Detect candlestick patterns"""
        patterns = []
        if len(closes) < 2:
            return patterns
        
        o2, o3 = opens[-2], opens[-1]
        h2, h3 = highs[-2], highs[-1]
        l2, l3 = lows[-2], lows[-1]
        c2, c3 = closes[-2], closes[-1]
        
        o1 = opens[-3] if len(closes) >= 3 else o2
        h1 = highs[-3] if len(closes) >= 3 else h2
        l1 = lows[-3] if len(closes) >= 3 else l2
        c1 = closes[-3] if len(closes) >= 3 else c2
        
        # BULLISH ENGULFING
        if c2 < o2 and c3 > o3:  # Red then green
            if o3 <= c2 and c3 >= o2 and (o2 - c2) > 0:  # Engulfs
                ratio = (c3 - o3) / (o2 - c2)
                if ratio > 1.2:
                    entry = c3
                    sl = l3 * 0.998
                    tp = entry + 2.5 * (entry - sl)
                    rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                    conf = min(85, 65 + ratio*10)
                    
                    patterns.append(Pattern(
                        name="Bullish Engulfing",
                        type="REVERSAL",
                        direction="BULLISH",
                        confidence=conf,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        risk_reward=rr,
                        formation_bars=2,
                        key_levels={},
                        invalidation_level=l3,
                        metadata={'body_ratio': ratio}
                    ))
        
        # BEARISH ENGULFING
        if c2 > o2 and c3 < o3:
            if o3 >= c2 and c3 <= o2 and (c2 - o2) > 0:
                ratio = (o3 - c3) / (c2 - o2)
                if ratio > 1.2:
                    entry = c3
                    sl = h3 * 1.002
                    tp = entry - 2.5 * (sl - entry)
                    rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                    conf = min(85, 65 + ratio*10)
                    
                    patterns.append(Pattern(
                        name="Bearish Engulfing",
                        type="REVERSAL",
                        direction="BEARISH",
                        confidence=conf,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        risk_reward=rr,
                        formation_bars=2,
                        key_levels={},
                        invalidation_level=h3,
                        metadata={'body_ratio': ratio}
                    ))
        
        # HAMMER (bullish at support)
        body = abs(c3 - o3)
        lower_wick = min(o3, c3) - l3
        upper_wick = h3 - max(o3, c3)
        
        if body > 0 and lower_wick > 2 * body and upper_wick < body * 0.5:
            entry = h3 * 1.001
            sl = l3 * 0.997
            tp = entry + 3 * (entry - sl)
            rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
            
            patterns.append(Pattern(
                name="Hammer",
                type="REVERSAL",
                direction="BULLISH",
                confidence=75,
                entry_price=entry,
                stop_loss=sl,
                take_profit=tp,
                risk_reward=rr,
                formation_bars=1,
                key_levels={},
                invalidation_level=l3,
                metadata={'wick_ratio': lower_wick/body if body > 0 else 0}
            ))
        
        # SHOOTING STAR (bearish at resistance)
        if body > 0 and upper_wick > 2 * body and lower_wick < body * 0.5:
            entry = l3 * 0.999
            sl = h3 * 1.003
            tp = entry - 3 * (sl - entry)
            rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
            
            patterns.append(Pattern(
                name="Shooting Star",
                type="REVERSAL",
                direction="BEARISH",
                confidence=75,
                entry_price=entry,
                stop_loss=sl,
                take_profit=tp,
                risk_reward=rr,
                formation_bars=1,
                key_levels={},
                invalidation_level=h3,
                metadata={'wick_ratio': upper_wick/body if body > 0 else 0}
            ))

        # MORNING STAR (bullish 3-candle reversal)
        body1 = abs(c1 - o1)
        body2 = abs(c2 - o2)
        body3 = abs(c3 - o3)
        if body1 > 0 and c1 < o1:  # Candle 1: substantial bearish
            if body2 <= body1 * 0.5 and min(o2, c2) <= c1:  # Candle 2: small body at bottom
                if c3 > o3 and c3 >= (o1 + c1) / 2:  # Candle 3: strong bullish closing past midpoint
                    entry = c3
                    lowest_low = min(l1, l2, l3)
                    sl = lowest_low * 0.998
                    tp = entry + 2.5 * (entry - sl)
                    rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                    conf = min(90, 75 + int((c3 - (o1 + c1) / 2) / body1 * 15))
                    patterns.append(Pattern(
                        name="Morning Star",
                        type="REVERSAL",
                        direction="BULLISH",
                        confidence=conf,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        risk_reward=rr,
                        formation_bars=3,
                        key_levels={},
                        invalidation_level=lowest_low,
                        metadata={'body_ratio': body3 / body1 if body1 > 0 else 1.0}
                    ))

        # EVENING STAR (bearish 3-candle reversal)
        if body1 > 0 and c1 > o1:  # Candle 1: substantial bullish
            if body2 <= body1 * 0.5 and max(o2, c2) >= c1:  # Candle 2: small body at top
                if c3 < o3 and c3 <= (o1 + c1) / 2:  # Candle 3: strong bearish closing past midpoint
                    entry = c3
                    highest_high = max(h1, h2, h3)
                    sl = highest_high * 1.002
                    tp = entry - 2.5 * (sl - entry)
                    rr = abs(tp - entry) / abs(sl - entry) if abs(sl - entry) > 1e-6 else 0.0
                    conf = min(90, 75 + int(((o1 + c1) / 2 - c3) / body1 * 15))
                    patterns.append(Pattern(
                        name="Evening Star",
                        type="REVERSAL",
                        direction="BEARISH",
                        confidence=conf,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        risk_reward=rr,
                        formation_bars=3,
                        key_levels={},
                        invalidation_level=highest_high,
                        metadata={'body_ratio': body3 / body1 if body1 > 0 else 1.0}
                    ))
        
        return patterns
    
    def _find_swings(self, prices, swing_type):
        """Find swing highs or lows"""
        swings = []
        for i in range(2, len(prices)-2):
            if swing_type == 'high':
                if prices[i] > prices[i-1] and prices[i] > prices[i-2] and \
                   prices[i] > prices[i+1] and prices[i] > prices[i+2]:
                    swings.append(i)
            else:
                if prices[i] < prices[i-1] and prices[i] < prices[i-2] and \
                   prices[i] < prices[i+1] and prices[i] < prices[i+2]:
                    swings.append(i)
        return swings
    
    def _calc_confidence(self, pattern_name, symmetry, rr):
        """Calculate pattern confidence score"""
        base = 65
        symmetry_bonus = (1.0 - symmetry) * 15
        rr_bonus = min(15, (rr - 1.5) * 8)
        return min(95, base + symmetry_bonus + rr_bonus)


# Global instance
_pattern_engine = None

def get_pattern_engine():
    global _pattern_engine
    if _pattern_engine is None:
        _pattern_engine = PatternRecognitionEngine()
    return _pattern_engine
