"""
===========================================================================
AEGIS GOLD — Pattern Memory Engine (Phase 1)
===========================================================================

PURPOSE:
  Maintains persistent historical pattern memory storing pattern signatures,
  conditional setup outcomes, and regime interaction statistics.
===========================================================================
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import Dict, List, Any, Optional

logger = logging.getLogger("aegis.pattern_memory")


@dataclass
class PatternMemoryEntry:
    pattern_signature: str
    pattern_type: str
    scale: str
    symbol: str
    regime: str
    occurrence_count: int
    win_count: int
    loss_count: int
    profit_factor: float
    win_rate: float
    avg_mfe: float
    avg_mae: float


class PatternMemoryEngine:
    """
    Persistent Pattern Memory & Historical Outcome Lookup Engine.
    """

    def __init__(self, storage_path: str = "data/validation/pattern_memory.json"):
        self.storage_path = storage_path
        self.memory: Dict[str, PatternMemoryEntry] = {}
        self.load_memory()

    def load_memory(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self.memory[k] = PatternMemoryEntry(**v)
                logger.info(f"🧠 [PATTERN MEMORY] Loaded {len(self.memory)} pattern memory entries.")
            except Exception as e:
                logger.warning(f"[PATTERN MEMORY] Could not load memory: {e}")

    def save_memory(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        dict_data = {k: asdict(v) for k, v in self.memory.items()}
        with open(self.storage_path, "w") as f:
            json.dump(dict_data, f, indent=2)

    def record_outcome(
        self,
        pattern_type: str,
        scale: str,
        symbol: str,
        regime: str,
        outcome: str,
        mfe_pts: float,
        mae_pts: float,
    ):
        sig = f"{symbol}_{pattern_type}_{scale}_{regime}"
        entry = self.memory.get(sig)
        if not entry:
            entry = PatternMemoryEntry(
                pattern_signature=sig, pattern_type=pattern_type, scale=scale,
                symbol=symbol, regime=regime, occurrence_count=0, win_count=0,
                loss_count=0, profit_factor=1.0, win_rate=0.0, avg_mfe=0.0, avg_mae=0.0,
            )

        entry.occurrence_count += 1
        if outcome == "WIN":
            entry.win_count += 1
        elif outcome == "LOSS":
            entry.loss_count += 1

        entry.win_rate = round((entry.win_count / max(entry.occurrence_count, 1)) * 100.0, 1)
        self.memory[sig] = entry
        self.save_memory()
