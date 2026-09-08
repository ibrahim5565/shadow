"""
Aegis Gold — Opportunity Funnel Telemetry Tracker
Tracks candidate flow through the 8-stage decision pipeline to distinguish between
low-opportunity market environments and excessively strict filter conditions.
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger("aegis.opportunity_funnel")


@dataclass
class FunnelCycleRecord:
    cycle_id: str
    symbol: str
    session: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # 8 Pipeline Stages
    krnos_detected: int = 0
    smc_validated: int = 0
    entry_zone_valid: int = 0
    trigger_confirmed: int = 0
    news_eligible: int = 0
    quant_economically_valid: int = 0
    risk_approved: int = 0
    trade_authorized: int = 0
    mt5_executed: int = 0
    
    rejection_stage: str = "NONE"
    rejection_reason: str = ""


class OpportunityFunnel:
    """
    Collects and reports conversion telemetry across all pipeline stages.
    """

    def __init__(self):
        self._aggregate_counts: Dict[str, int] = defaultdict(int)
        self._rejection_reasons: Dict[str, int] = defaultdict(int)
        self._total_cycles: int = 0

    def record_scan_event(
        self,
        stage_reached: str,
        symbol: str,
        session: str,
        rejection_reason: str = ""
    ):
        self._total_cycles += 1
        self._aggregate_counts[stage_reached] += 1
        if rejection_reason:
            self._rejection_reasons[rejection_reason] += 1

    def get_funnel_summary(self) -> Dict[str, Any]:
        """Calculates stage conversion percentages and drop-off reasons."""
        stages = [
            "1_KRNOS_DETECTED",
            "2_SMC_VALIDATED",
            "3_ENTRY_ZONE_VALID",
            "4_TRIGGER_CONFIRMED",
            "5_NEWS_ELIGIBLE",
            "6_QUANT_VALID",
            "7_RISK_APPROVED",
            "8_AUTHORIZED"
        ]
        
        counts = {s: self._aggregate_counts[s] for s in stages}
        base_candidates = max(1, counts["1_KRNOS_DETECTED"])
        conversion_rates = {
            s: round((counts[s] / base_candidates) * 100.0, 2)
            for s in stages
        }

        return {
            "total_scan_cycles": self._total_cycles,
            "stage_counts": counts,
            "conversion_rates_pct": conversion_rates,
            "top_rejection_reasons": dict(sorted(self._rejection_reasons.items(), key=lambda x: x[1], reverse=True)[:5])
        }
