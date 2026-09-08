"""
Layer B: Structure Analysis
Identifies nearest support and resistance levels.
"""
from dataclasses import dataclass
from config import settings as cfg

@dataclass
class StructureState:
    position: str
    preferred_direction: str
    score: int
    confluence_score: int
    distance_to_resistance: float
    distance_to_support: float
    sl_distance: float

def analyze_structure(candles, current_price: float, trend: str, point: float) -> StructureState:
    """
    Analyzes price structure context based on past 100 candles.
    """
    if len(candles) < 100:
        return StructureState(
            position="IN_SPACE", preferred_direction="NONE",
            score=0, confluence_score=0,
            distance_to_resistance=999.0, distance_to_support=999.0,
            sl_distance=999.0
        )
        
    from brain.candle_utils import parse_hlc
    highs_all, lows_all, _ = parse_hlc(candles)
    highs = highs_all[-100:]
    lows  = lows_all[-100:]
        
    swing_highs = []
    swing_lows = []
    
    # Process from index 2 to 97 (inclusive length 100)
    for i in range(2, len(highs) - 2):
        h = highs[i]
        # Convert to float to avoid numpy array comparison issues
        if (h > highs[i-1] and h > highs[i+1] and
            h > highs[i-2] and h > highs[i+2]):
            swing_highs.append(h)
            
        l = lows[i]
        if (l < lows[i-1] and l < lows[i+1] and
            l < lows[i-2] and l < lows[i+2]):
            swing_lows.append(l)
            
    # Keep only last 5
    swing_highs = swing_highs[-5:]
    swing_lows = swing_lows[-5:]
    
    if not swing_highs or not swing_lows:
        return StructureState("IN_SPACE", "NONE", 0, 0, 999.0, 999.0, 999.0)
        
    nearest_resistance = min(
        [x for x in swing_highs if x > current_price] + [float('inf')]
    )
    nearest_support = max(
        [x for x in swing_lows if x < current_price] + [-float('inf')]
    )
    
    # Convert raw price distances to POINTS using broker point settings
    distance_to_resistance_raw = nearest_resistance - current_price if nearest_resistance != float('inf') else 999.0 * point
    distance_to_support_raw = current_price - nearest_support if nearest_support != -float('inf') else 999.0 * point
    
    distance_to_resistance_pts = distance_to_resistance_raw / point if point > 0 else distance_to_resistance_raw
    distance_to_support_pts = distance_to_support_raw / point if point > 0 else distance_to_support_raw
    
    # Structure Position (purely in points)
    ZONE_THRESHOLD = getattr(cfg, "ZONE_THRESHOLD_PTS", 30)
    
    position = ""
    preferred_direction = "NONE"
    
    if distance_to_support_pts <= ZONE_THRESHOLD:
        position = "NEAR_SUPPORT"
        preferred_direction = "BUY"
    elif distance_to_resistance_pts <= ZONE_THRESHOLD:
        position = "NEAR_RESISTANCE"
        preferred_direction = "SELL"
    elif distance_to_support_pts > 100 and distance_to_resistance_pts > 100:
        position = "IN_SPACE"
        # Resolve bias: lean toward whichever level price is closer to
        if distance_to_support_pts < distance_to_resistance_pts:
            preferred_direction = "BUY"
        else:
            preferred_direction = "SELL"
    else:
        position = "MID_RANGE"
        # Resolve MID_RANGE direction by proximity (not left as NONE)
        if distance_to_support_pts <= distance_to_resistance_pts:
            preferred_direction = "BUY"
        else:
            preferred_direction = "SELL"

    # Confluence Score
    confluence_score = 0
    if position == "NEAR_SUPPORT": confluence_score += 40
    if position == "NEAR_RESISTANCE": confluence_score += 40

    if swing_lows.count(nearest_support) >= 2:
        confluence_score += 20

    # Side-aware distance bonus: strong conviction when very close to the relevant level
    if preferred_direction == "BUY" and distance_to_support_pts < (ZONE_THRESHOLD * 0.5):
        confluence_score += 20
    elif preferred_direction == "SELL" and distance_to_resistance_pts < (ZONE_THRESHOLD * 0.5):
        confluence_score += 20

    if trend == "TRENDING_UP" and preferred_direction == "BUY":
        confluence_score += 20
    if trend == "TRENDING_DOWN" and preferred_direction == "SELL":
        confluence_score += 20
        
    sl_dist_pts = distance_to_support_pts if preferred_direction == "BUY" else distance_to_resistance_pts
        
    return StructureState(
        position=position,
        preferred_direction=preferred_direction,
        score=confluence_score,
        confluence_score=confluence_score,
        distance_to_resistance=distance_to_resistance_pts,
        distance_to_support=distance_to_support_pts,
        sl_distance=sl_dist_pts
    )
