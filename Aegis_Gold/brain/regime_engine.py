"""
===========================================================================
AEGIS GOLD — Causal Market Regime Engine (Phase 2)
===========================================================================

PURPOSE:
  Classifies market regimes (TREND, RANGE, EXPANSION, COMPRESSION, HIGH_VOLATILITY,
  LOW_VOLATILITY) strictly using point-in-time candles timestamped t <= T.
===========================================================================
"""

from __future__ import annotations

import math
import logging
from typing import List, Dict, Any

from brain.frozen_snapshot import FrozenDecisionSnapshot

logger = logging.getLogger("aegis.regime_engine")


class RegimeEngine:
    """
    Causal Point-in-Time Market Regime Classification Engine.
    """

    def detect_regime(self, snapshot: FrozenDecisionSnapshot) -> str:
        """
        Classifies current regime from snapshot.candles_m5 (t <= T).
        """
        candles = snapshot.candles_m5
        if len(candles) < 20:
            return "RANGE"

        closes = [float(c.get("close", 2000.0)) for c in candles[-20:]]
        highs = [float(c.get("high", 2000.0)) for c in candles[-20:]]
        lows = [float(c.get("low", 2000.0)) for c in candles[-20:]]

        # Calculate Price Range and Volatility
        price_range = max(highs) - min(lows)
        recent_range = max(highs[-5:]) - min(lows[-5:])

        # Directional Trend Check
        net_change = closes[-1] - closes[0]
        abs_change = abs(net_change)

        if abs_change > (price_range * 0.60):
            regime = "TREND"
        elif recent_range > (price_range * 0.40):
            regime = "HIGH_VOLATILITY"
        elif recent_range < (price_range * 0.15):
            regime = "COMPRESSION"
        else:
            regime = "RANGE"

        logger.info(f"📊 [REGIME ENGINE] Current Regime={regime} (Net Change={net_change:.2f}, Range={price_range:.2f})")
        return regime
