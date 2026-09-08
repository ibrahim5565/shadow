"""
===========================================================================
🧠 AEGIS GOLD — Segmented Accuracy-Weighted 7-Engine Consensus Brain
===========================================================================

Mathematical Foundation:
  w_i(t) = Accuracy_i(t-200, session, mode) / Σ Accuracy_j(t-200, session, mode)
  w_i(t) = 0.95 * w_i(t-1) + 0.05 * w_i,target

Segmentation:
  - Session buckets: ASIA, LONDON, NY, OVERLAP
  - Mode buckets: Scalp (M1), Small Pattern (M5), Big Pattern (H1/H4)
===========================================================================
"""

import json
import logging
import os
import math
from typing import Dict, List, Any, Optional

logger = logging.getLogger("aegis.brain.adaptive")

ENGINES = ["neural", "quant", "ml_ensemble", "omega", "kronos", "smc", "rl"]
DEFAULT_WEIGHT = 1.0 / len(ENGINES)  # 0.1428

class SegmentedAdaptiveConsensusBrain:
    """
    Segmented 7-Engine Adaptive Weighting Engine.
    Tracks engine prediction accuracy segmented by session and trade mode.
    """

    def __init__(self, persistence_file: Optional[str] = None):
        if persistence_file is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            persistence_file = os.path.join(base_dir, "data", "engine_weights_segmented.json")
        
        self.persistence_file = persistence_file
        self.weights_by_segment: Dict[str, Dict[str, float]] = {}
        self.accuracy_history: Dict[str, Dict[str, List[int]]] = {}
        self.load_weights()

    def _get_segment_key(self, session: str, mode: str) -> str:
        s = str(session).strip().upper() if session else "LONDON"
        m = str(mode).strip().lower() if mode else "scalp"
        if "big" in m or "pro_trend" in m:
            m_norm = "big_pattern"
        elif "small" in m or "smc" in m:
            m_norm = "small_pattern"
        else:
            m_norm = "scalp"
        return f"{s}_{m_norm}"

    def get_weights(self, session: str = "LONDON", mode: str = "scalp") -> Dict[str, float]:
        """Retrieve current normalized engine weights for a specific session/mode segment."""
        key = self._get_segment_key(session, mode)
        if key not in self.weights_by_segment:
            return {e: DEFAULT_WEIGHT for e in ENGINES}
        return self.weights_by_segment[key]

    def update_weights(
        self,
        trade_history: List[Dict[str, Any]],
        session: str = "LONDON",
        mode: str = "scalp",
        window_size: int = 200,
        smoothing_factor: float = 0.95
    ) -> Dict[str, float]:
        """
        Computes rolling accuracy per engine within the given session/mode segment
        and applies smoothed weight updating.
        """
        key = self._get_segment_key(session, mode)
        
        # Filter trades matching segment
        matching_trades = []
        for t in trade_history:
            t_sess = str(t.get("session", "")).strip().upper()
            t_mode = str(t.get("mode", t.get("pattern_tier", ""))).strip().lower()
            if self._get_segment_key(t_sess, t_mode) == key:
                matching_trades.append(t)

        recent_trades = matching_trades[-window_size:]
        if not recent_trades:
            return self.get_weights(session, mode)

        # Calculate accuracy per engine
        engine_hits = {e: 0 for e in ENGINES}
        engine_counts = {e: 0 for e in ENGINES}

        for trade in recent_trades:
            outcome = str(trade.get("outcome", "")).upper()
            is_win = (outcome == "WIN" or trade.get("pnl_usd", 0) > 0)
            votes = trade.get("engine_votes", {})
            
            for e in ENGINES:
                if e in votes:
                    vote_dir = str(votes[e].get("direction", "")).lower()
                    trade_dir = str(trade.get("direction", "")).lower()
                    if vote_dir != "neutral" and vote_dir != "none":
                        engine_counts[e] += 1
                        if (is_win and vote_dir in (trade_dir, "bullish" if trade_dir == "buy" else "bearish")) or \
                           (not is_win and vote_dir != trade_dir):
                            engine_hits[e] += 1

        # Accuracy ratio (default to 0.50 if no predictions)
        accuracy = {}
        for e in ENGINES:
            cnt = engine_counts[e]
            accuracy[e] = (engine_hits[e] / cnt) if cnt > 0 else 0.50

        # Sum accuracies for normalization
        sum_acc = sum(accuracy.values())
        if sum_acc <= 0:
            target_weights = {e: DEFAULT_WEIGHT for e in ENGINES}
        else:
            target_weights = {e: round(accuracy[e] / sum_acc, 4) for e in ENGINES}

        # Apply smooth learning rate cap (0.95 prev + 0.05 target)
        prev_weights = self.get_weights(session, mode)
        new_weights = {}
        for e in ENGINES:
            w_prev = prev_weights.get(e, DEFAULT_WEIGHT)
            w_targ = target_weights[e]
            w_smoothed = smoothing_factor * w_prev + (1.0 - smoothing_factor) * w_targ
            new_weights[e] = round(w_smoothed, 4)

        # Normalize final weights so sum equals 1.0
        tot_w = sum(new_weights.values())
        if tot_w > 0:
            new_weights = {e: round(w / tot_w, 4) for e, w in new_weights.items()}

        self.weights_by_segment[key] = new_weights
        self.save_weights()

        logger.info(
            f"[ADAPTIVE BRAIN] Updated weights for segment {key} | "
            f"Accuracies: {accuracy} | New Weights: {new_weights}"
        )
        return new_weights

    def save_weights(self):
        try:
            os.makedirs(os.path.dirname(self.persistence_file), exist_ok=True)
            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(self.weights_by_segment, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save engine weights: {e}")

    def load_weights(self):
        if os.path.exists(self.persistence_file):
            try:
                with open(self.persistence_file, "r", encoding="utf-8") as f:
                    self.weights_by_segment = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load engine weights: {e}")
                self.weights_by_segment = {}
