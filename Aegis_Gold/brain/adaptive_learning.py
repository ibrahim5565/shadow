"""
ANTIGRAVITY OMEGA — Local Adaptive Learning Engine
Tracks performance metrics and dynamically adapts trading thresholds to preserve capital.
"""
import os
import json
import logging

logger = logging.getLogger("aegis.omega.learning")

PERF_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "omega_performance.json")

class AdaptiveLearning:
    def __init__(self):
        self.performance_data = self._load_performance()
        logger.info("Local OMEGA Adaptive Learning Engine initialized.")

    def _load_performance(self) -> dict:
        if os.path.exists(PERF_FILE):
            try:
                with open(PERF_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"total_trades": 0, "wins": 0, "losses": 0, "recent_results": []}

    def _save_performance(self):
        try:
            os.makedirs(os.path.dirname(PERF_FILE), exist_ok=True)
            with open(PERF_FILE, "w") as f:
                json.dump(self.performance_data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save performance data: {e}")

    def record_trade(self, result: str):
        """
        result: "WIN" or "LOSS"
        """
        self.performance_data["total_trades"] += 1
        if result == "WIN":
            self.performance_data["wins"] += 1
            self.performance_data["recent_results"].append(1)
        else:
            self.performance_data["losses"] += 1
            self.performance_data["recent_results"].append(0)

        # Keep only the last 20 trade results
        if len(self.performance_data["recent_results"]) > 20:
            self.performance_data["recent_results"].pop(0)

        self._save_performance()
        logger.info(f"Performance tracked: {result} recorded. Stats: {self.performance_data['wins']}W - {self.performance_data['losses']}L")

    def get_adaptations(self) -> dict:
        """
        Adapts parameters based on win rate.
        Returns multiplier or threshold offsets:
        - selectivity_multiplier: increase minimum required score if performance drops
        - lot_multiplier: scale lot down during drawdowns
        """
        recent = self.performance_data["recent_results"]
        if len(recent) < 5:
            return {"selectivity_offset": 0, "lot_multiplier": 1.0}

        win_rate = sum(recent) / len(recent)

        selectivity_offset = 0
        lot_multiplier = 1.0

        if win_rate < 0.40:
            # High selectivity mode (underperforming)
            selectivity_offset = 15  # Require higher confidence scores
            lot_multiplier = 0.5     # Halve lot size to protect capital
            logger.warning(f"Win rate underperforming ({win_rate:.1%}). Tightening filters.")
        elif win_rate < 0.50:
            selectivity_offset = 5
            lot_multiplier = 0.8
        elif win_rate >= 0.70:
            # High performance mode
            selectivity_offset = -5  # Slightly more aggressive
            lot_multiplier = 1.1     # Minor scale up if doing exceptionally well

        return {
            "selectivity_offset": selectivity_offset,
            "lot_multiplier": round(lot_multiplier, 2),
            "win_rate": round(win_rate, 2)
        }
