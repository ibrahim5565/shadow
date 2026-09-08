"""
===========================================================================
AEGIS GOLD — Exhaustive Pattern Scanner (Phase 1)
===========================================================================

PURPOSE:
  Scans every historical decision point timestamp T (t <= T) across M1, M5, M15,
  M30, H1, H4 timeframes and discovers all observable structural patterns
  (BOS, CHoCH, OB, FVG, Sweeps, Displacement, Rejections, Retests).
===========================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from brain.pattern_event import PatternEvent
from brain.pattern_library import PatternType, PatternCategory, PatternScale
from brain.pattern_discovery_engine import PatternDiscoveryEngine

logger = logging.getLogger("aegis.exhaustive_scanner")


class ExhaustivePatternScanner:
    """
    Historical Exhaustive Multi-Timeframe Pattern Scanner.
    """

    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol
        self.base_engine = PatternDiscoveryEngine(symbol=symbol)

    def scan_historical_opportunities(
        self,
        candles_m5: List[Dict[str, Any]],
        decision_time: datetime,
    ) -> List[PatternEvent]:
        """
        Exhaustively scans all patterns available <= decision_time.
        """
        events = self.base_engine.discover_patterns(candles_m5, decision_time)
        logger.info(f"🔎 [EXHAUSTIVE SCANNER] Discovered {len(events)} pattern events at T={decision_time.isoformat()}")
        return events
