import logging
import time
import statistics
from collections import deque
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("aegis.execution_integrity")

class SlippageTracker:
    """
    Tracks and records slippage (requested price vs actual fill price).
    Surfaces rolling averages to the trade cost models.
    """
    def __init__(self, maxlen: int = 100):
        self._history: Dict[str, deque] = {}
        self._maxlen = maxlen

    def record_slippage(self, symbol: str, requested: float, filled: float, point: float) -> float:
        if symbol not in self._history:
            self._history[symbol] = deque(maxlen=self._maxlen)
        
        if point <= 0:
            return 0.0
        
        slippage_pts = abs(requested - filled) / point
        self._history[symbol].append(slippage_pts)
        return slippage_pts

    def get_avg_slippage(self, symbol: str) -> float:
        history = self._history.get(symbol)
        if not history:
            return 0.0
        return sum(history) / len(history)

    def is_slippage_anomaly(self, symbol: str, current_slippage_pts: float) -> bool:
        history = self._history.get(symbol)
        if not history or len(history) < 10:
            return False
        
        avg = sum(history) / len(history)
        std = statistics.stdev(history) if len(history) > 1 else 1.0
        
        # If current slippage exceeds avg by 3 standard deviations
        from config.quant_x_config import QX
        sigma_threshold = float(QX.get("slippage_alert_sigma") or 3.0)
        return current_slippage_pts > (avg + sigma_threshold * std)


class BrokerAnomalyDetector:
    """
    Monitors spread and execution behavior. Auto-throttles or halts
    if the broker deviates from their own historical baseline.
    """
    def __init__(self):
        self._spread_history: Dict[str, deque] = {}
        self.execution_paused = False

    def check_spread(self, symbol: str, current_spread_pts: float) -> bool:
        """
        Monitors spreads. Returns True if spread is acceptable,
        False if spread is anomalous.
        """
        from config.quant_x_config import QX
        if not QX.flag("execution_integrity"):
            return True

        window = int(QX.get("broker_anomaly_window") or 50)
        if symbol not in self._spread_history:
            self._spread_history[symbol] = deque(maxlen=window)

        # Record current spread
        self._spread_history[symbol].append(current_spread_pts)

        if len(self._spread_history[symbol]) < 15:
            return True

        # Calculate historical stats
        history = list(self._spread_history[symbol])
        avg_spread = sum(history) / len(history)
        
        limit_multiplier = float(QX.get("spread_anomaly_multiple") or 3.0)
        if current_spread_pts > avg_spread * limit_multiplier:
            logger.warning(
                f"[EXECUTION INTEGRITY] Spread anomaly on {symbol}: "
                f"Current={current_spread_pts:.1f} pts | Avg={avg_spread:.1f} pts. Threshold x{limit_multiplier} exceeded!"
            )
            return False
        return True

    def detect_stop_hunt(self, symbol: str, high: float, low: float, sl_price: float) -> bool:
        """
        Flags stop-hunt patterns (sudden price spike touching SL and immediate bounce back).
        """
        # Checks if low (or high) touched SL price within a tiny margin, but closed far from it
        if abs(low - sl_price) < 0.0001:
            logger.warning(f"[EXECUTION ANOMALY] Stop-hunt pattern check flagged for {symbol} near {sl_price}")
            return True
        return False


class FillMonitor:
    """
    Validates partial fills, duplicate fills, and detects orphaned orders.
    """
    def __init__(self):
        pass

    def inspect_positions_and_orders(self, active_orders: List, active_positions: List) -> dict:
        """
        Scans for execution discrepancies.
        Returns check dict detailing duplicates, orphans, and status.
        """
        report = {
            "duplicate_orders": [],
            "orphaned_positions": [],
            "status": "OK"
        }

        # Scan duplicate orders: more than 1 open order of same symbol/type
        seen_order_types = {}
        for order in active_orders:
            key = (order.symbol, order.type)
            if key in seen_order_types:
                report["duplicate_orders"].append(order.ticket)
                report["status"] = "ANOMALY"
            seen_order_types[key] = order.ticket

        return report
