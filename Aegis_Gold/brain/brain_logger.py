"""
Brain Logger
Records all decisions to csv, including skips for analysis.
"""
import os
import csv
from datetime import datetime, timezone
import logging

from config import settings as cfg

logger = logging.getLogger("aegis.brain")

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "brain_log.csv")

def ensure_brain_journal():
    if not os.path.exists(LOG_PATH):
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "action", "reason", "regime_type", "regime_score",
                "structure_pos", "structure_score", "entry_score", "total_score",
                "direction", "sl_points", "tp_points", "lot", "outcome", "thought_log"
            ])

def log_decision(decision):
    try:
        ensure_brain_journal()
        thought_log_str = "; ".join(decision.thought_log) if getattr(decision, 'thought_log', None) else ""
        with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now(timezone.utc).isoformat(),
                decision.action,
                decision.reason,
                decision.regime,
                decision.regime_score,
                decision.structure,
                decision.structure_score,
                decision.entry_score,
                decision.confidence,
                decision.direction,
                decision.sl_points,
                decision.tp_points,
                decision.lot,
                "NA", # Wait outcome filled NA
                thought_log_str
            ])
    except Exception as exc:
        logger.error(f"Brain log write error: {exc}")
