"""
ANTIGRAVITY OMEGA — Local Adaptive Learning Engine
Tracks performance metrics and dynamically adapts the Edge-Quality Score (EQS) threshold
and lot sizing based on rolling Profit Factor. Replaces the old static selectivity_offset table.
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
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "recent_results": [],
            "recent_pnl": []
        }

    def _save_performance(self):
        try:
            os.makedirs(os.path.dirname(PERF_FILE), exist_ok=True)
            with open(PERF_FILE, "w") as f:
                json.dump(self.performance_data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save performance data: {e}")

    def record_trade(self, result: str, pnl: float = 0.0):
        """
        result: "WIN" or "LOSS"
        pnl:    profit/loss in USD for this trade
        """
        self.performance_data["total_trades"] += 1
        if result == "WIN":
            self.performance_data["wins"] += 1
            self.performance_data["recent_results"].append(1)
            self.performance_data["gross_profit"] = self.performance_data.get("gross_profit", 0.0) + abs(pnl)
        else:
            self.performance_data["losses"] += 1
            self.performance_data["recent_results"].append(0)
            self.performance_data["gross_loss"] = self.performance_data.get("gross_loss", 0.0) + abs(pnl)

        self.performance_data.setdefault("recent_pnl", []).append(round(pnl, 2))

        # Keep only last 30 results (wider window for PF stability)
        if len(self.performance_data["recent_results"]) > 30:
            self.performance_data["recent_results"].pop(0)
        if len(self.performance_data.get("recent_pnl", [])) > 30:
            self.performance_data["recent_pnl"].pop(0)

        self._save_performance()
        logger.info(
            f"Performance tracked: {result} pnl={pnl:+.2f}. "
            f"Stats: {self.performance_data['wins']}W - {self.performance_data['losses']}L | "
            f"Rolling PF: {self._rolling_profit_factor():.2f}"
        )

    def _rolling_profit_factor(self) -> float:
        """Calculate rolling Profit Factor from recent PnL records."""
        recent_pnl = self.performance_data.get("recent_pnl", [])
        if len(recent_pnl) < 5:
            return 1.0  # Assume neutral before enough data
        gross_win = sum(p for p in recent_pnl if p > 0)
        gross_loss = sum(abs(p) for p in recent_pnl if p < 0)
        if gross_loss == 0:
            return 2.0 if gross_win > 0 else 1.0
        return round(gross_win / gross_loss, 3)

    def get_eqs_threshold(self) -> float:
        """
        Returns the dynamic Edge-Quality Score (EQS) threshold based on rolling Profit Factor.

        PF > 1.5  → EQS >= 0.55  (system profitable — take slightly more trades)
        PF 1.0-1.5→ EQS >= 0.60  (steady state — standard gate)
        PF 0.7-1.0→ EQS >= 0.65  (underperforming — tighten edge requirement)
        PF < 0.7  → EQS >= 0.70  (capital protection mode)
        """
        recent = self.performance_data.get("recent_results", [])
        if len(recent) < 5:
            return 0.60  # Default before enough data

        pf = self._rolling_profit_factor()

        if pf > 1.5:
            threshold = 0.55
        elif pf >= 1.0:
            threshold = 0.60
        elif pf >= 0.7:
            threshold = 0.65
        else:
            threshold = 0.70

        logger.debug(f"[AdaptiveLearning] Rolling PF={pf:.2f} -> EQS threshold={threshold:.2f}")
        return threshold

    def get_adaptations(self) -> dict:
        """
        Returns adaptation parameters for current market performance.
        Drives lot scaling and EQS threshold adjustment.
        """
        recent = self.performance_data.get("recent_results", [])
        pf = self._rolling_profit_factor()

        lot_multiplier = 1.0
        if pf < 0.7:
            lot_multiplier = 0.5  # Halve lot in drawdown protection mode
            logger.warning(f"[AdaptiveLearning] PF={pf:.2f} < 0.7 ? Lot halved (capital protection).")
        elif pf < 1.0:
            lot_multiplier = 0.8
        elif pf > 1.5:
            lot_multiplier = 1.1  # Minor scale-up in high-performance mode

        win_rate = sum(recent) / len(recent) if recent else 0.5

        return {
            "eqs_threshold": self.get_eqs_threshold(),
            "lot_multiplier": round(lot_multiplier, 2),
            "win_rate": round(win_rate, 3),
            "rolling_pf": pf,
        }
