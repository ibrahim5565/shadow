#!/usr/bin/env python3
"""
AEGIS GOLD - SMC Pattern Engine
================================
Combines Smart Money Concepts with Pattern Recognition

SMC + Patterns = Elite Entry Points:
- Pattern at Order Block = High probability
- Pattern with Liquidity Sweep = Even better
- Pattern + BOS/CHoCH = Confirmation

This engine finds patterns that align with SMC structures.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any
from brain.pattern_recognition import get_pattern_engine, Pattern
from brain.smc_engine import (
    _parse_candles,
    detect_swing_points,
    detect_bos_choch,
    detect_order_blocks,
    detect_liquidity_levels,
    detect_sweep
)

logger = logging.getLogger("aegis.smc_pattern")


class SMCPatternEngine:
    """
    Combines SMC concepts with chart patterns for maximum edge.
    """
    
    def __init__(self, point: float = 0.01):
        self.pattern_engine = get_pattern_engine()
        self.point = point
        logger.info("SMC Pattern Engine initialized")
    
    def find_smc_enhanced_patterns(self, rates: Any, point: Optional[float] = None) -> List[Dict]:
        """
        Find patterns that align with SMC structures.
        
        rates can be a dict {'open': [...], 'high': [...], 'low': [...], 'close': [...]}
        or a list of candles / DataFrame.
        
        Returns patterns with SMC enhancement score.
        """
        pt = point if point is not None else self.point

        if isinstance(rates, dict) and 'high' in rates and 'low' in rates and 'close' in rates:
            opens = list(rates.get('open', rates['close']))
            highs = list(rates['high'])
            lows = list(rates['low'])
            closes = list(rates['close'])
        else:
            opens, highs, lows, closes = _parse_candles(rates)
        
        if len(closes) < 15:
            return []
        
        # 1. Get all patterns
        h_arr = np.asarray(highs, dtype=float)
        l_arr = np.asarray(lows, dtype=float)
        c_arr = np.asarray(closes, dtype=float)
        o_arr = np.asarray(opens, dtype=float)

        patterns = self.pattern_engine.scan_all_patterns(h_arr, l_arr, c_arr, o_arr)
        
        if not patterns:
            return []
        
        # 2. Get SMC structures
        sh, sl = detect_swing_points(highs, lows)
        bos_choch = detect_bos_choch(highs, lows, closes, sh, sl)
        order_blocks = detect_order_blocks(opens, highs, lows, closes, bos_choch, pt)
        liq_levels = detect_liquidity_levels(highs, lows, sh, sl, pt)
        sweep = detect_sweep(highs, lows, closes, liq_levels, pt)
        
        # 3. Enhance patterns with SMC data
        enhanced = []
        for pattern in patterns:
            smc_score = self._calculate_smc_enhancement(
                pattern, order_blocks, sweep, bos_choch
            )
            
            if smc_score >= 0:
                enhanced_pattern = {
                    'pattern': pattern,
                    'smc_score': smc_score,
                    'final_confidence': min(98.0, pattern.confidence + smc_score),
                    'smc_factors': self._get_smc_factors(pattern, order_blocks, sweep, bos_choch)
                }
                enhanced.append(enhanced_pattern)
        
        # Sort by final confidence
        enhanced.sort(key=lambda x: x['final_confidence'], reverse=True)
        
        logger.info(f"Found {len(enhanced)} SMC-enhanced patterns")
        return enhanced
    
    def _calculate_smc_enhancement(self, pattern: Pattern, obs, sweep, bos) -> float:
        """
        Calculate SMC enhancement score (0-25 points).
        
        Factors:
        +10: Pattern at Order Block
        +8: Pattern after Liquidity Sweep
        +6: Pattern with BOS/CHoCH confirmation
        +5: Multiple SMC factors aligned
        """
        score = 0.0
        entry = pattern.entry_price
        
        # Check if pattern entry is near Order Block
        for ob in obs:
            ob_mid = (ob.high + ob.low) / 2.0
            if abs(entry - ob_mid) / entry < 0.003:  # Within 0.3%
                score += 10.0
                logger.debug("Pattern at Order Block: +10")
                break
        
        # Check if recent Liquidity Sweep aligns
        if sweep and sweep.get("swept"):
            sw_dir = sweep.get("direction", "")
            if (pattern.direction == "BULLISH" and sw_dir == "BULLISH") or \
               (pattern.direction == "BEARISH" and sw_dir == "BEARISH"):
                score += 8.0
                logger.debug("Recent Liquidity Sweep: +8")
        
        # Check if BOS/CHoCH confirms pattern direction
        if bos:
            if pattern.direction == 'BULLISH' and (bos.get('bullish_bos') or bos.get('bullish_choch')):
                score += 6.0
                logger.debug("BOS/CHoCH bullish confirmation: +6")
            elif pattern.direction == 'BEARISH' and (bos.get('bearish_bos') or bos.get('bearish_choch')):
                score += 6.0
                logger.debug("BOS/CHoCH bearish confirmation: +6")
        
        # Bonus for multiple factors
        if score >= 14.0:
            score += 5.0
            logger.debug("Multiple SMC factors: +5")
        
        return score
    
    def _get_smc_factors(self, pattern: Pattern, obs, sweep, bos) -> List[str]:
        """Get list of SMC factors present"""
        factors = []
        entry = pattern.entry_price
        
        for ob in obs:
            ob_mid = (ob.high + ob.low) / 2.0
            if abs(entry - ob_mid) / entry < 0.003:
                factors.append(f"Order Block ({ob.direction}) at {ob_mid:.2f}")
        
        if sweep and sweep.get("swept"):
            sw_dir = sweep.get("direction", "")
            if (pattern.direction == "BULLISH" and sw_dir == "BULLISH") or \
               (pattern.direction == "BEARISH" and sw_dir == "BEARISH"):
                factors.append(f"Liquidity Sweep {sw_dir}")
        
        if bos:
            if pattern.direction == 'BULLISH' and (bos.get('bullish_bos') or bos.get('bullish_choch')):
                factors.append(f"BOS/CHoCH Bullish Confirmed")
            elif pattern.direction == 'BEARISH' and (bos.get('bearish_bos') or bos.get('bearish_choch')):
                factors.append(f"BOS/CHoCH Bearish Confirmed")
        
        return factors


# Global instance
_smc_pattern_engine = None

def get_smc_pattern_engine():
    global _smc_pattern_engine
    if _smc_pattern_engine is None:
        _smc_pattern_engine = SMCPatternEngine()
    return _smc_pattern_engine
