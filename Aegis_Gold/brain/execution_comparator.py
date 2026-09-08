"""
Aegis Gold — Demo vs Shadow vs Live Execution Comparator Framework
Tracks and audits execution degradation, slippage ratios, fill latency, and spread differences
across DEMO_MODE, SHADOW_LIVE_MODE, and LIVE_MODE.
"""

import os
import json
import time
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger("aegis.execution_comparator")


@dataclass
class ExecutionRecord:
    trade_id: int
    symbol: str
    direction: str
    lot: float
    mode: str                         # "DEMO", "SHADOW_LIVE", "LIVE"
    requested_price: float
    executed_price: float
    slippage_points: float
    spread_points: float
    execution_latency_ms: float
    tp_points: int
    sl_points: int
    profit_usd: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExecutionComparator:
    """
    Records and calculates comparative metrics between demo and live execution.
    Blocks capital scaling if live slippage or fill degradation exceeds thresholds.
    """

    MAX_ACCEPTABLE_SLIPPAGE_PTS = 25.0 # Max acceptable slippage for scalping
    MAX_SLIPPAGE_DEGRADATION_RATIO = 2.5 # Live slippage vs Demo slippage

    def __init__(self, data_file: Optional[str] = None):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
        self.data_file = data_file or os.path.join(base_dir, "execution_comparison.jsonl")
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)

    def record_execution(self, record: ExecutionRecord):
        """Persists a trade execution record for comparison audit."""
        try:
            with open(self.data_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(record)) + "\n")
        except Exception as e:
            logger.error(f"Failed to record execution comparison: {e}")

    def compute_degradation_metrics(self, last_n: int = 200) -> Dict[str, Any]:
        """
        Calculates execution statistics across demo and live modes.
        """
        if not os.path.exists(self.data_file):
            return {
                "status": "INSUFFICIENT_DATA",
                "demo_avg_slippage": 0.0,
                "live_avg_slippage": 0.0,
                "slippage_ratio": 1.0,
                "scaling_allowed": True
            }

        records = []
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line.strip()))
        except Exception as e:
            logger.error(f"Error reading execution comparison data: {e}")
            return {"status": "READ_ERROR", "scaling_allowed": False}

        if not records:
            return {"status": "NO_RECORDS", "scaling_allowed": True}

        recent = records[-last_n:]
        demo_recs = [r for r in recent if r.get("mode") == "DEMO"]
        live_recs = [r for r in recent if r.get("mode") in ("LIVE", "SHADOW_LIVE")]

        demo_slip = sum(abs(r.get("slippage_points", 0)) for r in demo_recs) / max(1, len(demo_recs))
        live_slip = sum(abs(r.get("slippage_points", 0)) for r in live_recs) / max(1, len(live_recs))

        demo_lat = sum(r.get("execution_latency_ms", 0) for r in demo_recs) / max(1, len(demo_recs))
        live_lat = sum(r.get("execution_latency_ms", 0) for r in live_recs) / max(1, len(live_recs))

        ratio = (live_slip / max(0.1, demo_slip)) if live_recs and demo_recs else 1.0
        scaling_allowed = (ratio <= self.MAX_SLIPPAGE_DEGRADATION_RATIO) and (live_slip <= self.MAX_ACCEPTABLE_SLIPPAGE_PTS)

        return {
            "demo_count": len(demo_recs),
            "live_count": len(live_recs),
            "demo_avg_slippage_pts": round(demo_slip, 2),
            "live_avg_slippage_pts": round(live_slip, 2),
            "demo_avg_latency_ms": round(demo_lat, 1),
            "live_avg_latency_ms": round(live_lat, 1),
            "slippage_ratio": round(ratio, 2),
            "scaling_allowed": scaling_allowed,
            "rejection_reason": "" if scaling_allowed else f"Live slippage ratio {ratio:.2f}x exceeds limit {self.MAX_SLIPPAGE_DEGRADATION_RATIO}x"
        }
