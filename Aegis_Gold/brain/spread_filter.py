"""
ANTIGRAVITY OMEGA — Local Spread Filter Module
Tracks dynamic rolling spread and evaluates acceptable boundaries per session.
"""
import logging
import numpy as np

logger = logging.getLogger("aegis.omega.spread")

class SpreadFilter:
    def __init__(self, rolling_window=20, dynamic_mult=2.0):
        self.rolling_window = rolling_window
        self.dynamic_mult = dynamic_mult
        self.spread_history = []
        logger.info("Local OMEGA Spread Filter initialized.")

    def analyze(self, current_spread: float, session: str, session_spread_max: float) -> dict:
        """
        Main evaluation for spread health.
        Logs historical spreads and evaluates if the spread is tight enough.
        """
        # Save spread to history
        self.spread_history.append(current_spread)
        if len(self.spread_history) > self.rolling_window:
            self.spread_history.pop(0)

        # Dynamic limit based on rolling average
        if len(self.spread_history) >= 5:
            roll_avg = np.mean(self.spread_history)
            dynamic_limit = roll_avg * self.dynamic_mult
        else:
            dynamic_limit = 999.0

        hard_limit = session_spread_max
        effective_limit = min(dynamic_limit, hard_limit)

        spread_ok = current_spread < effective_limit
        reason = f"Spread {current_spread:.0f} pts OK | Cap: {effective_limit:.0f} pts"
        if not spread_ok:
            reason = f"Spread {current_spread:.0f} pts too wide | Cap: {effective_limit:.0f} pts"

        return {
            "spread_ok": spread_ok,
            "current_spread": current_spread,
            "dynamic_limit": round(dynamic_limit, 2),
            "effective_limit": round(effective_limit, 2),
            "reason": reason
        }

    def check(self, current_spread: float, session: str = "LONDON", session_spread_max: float = 30.0) -> bool:
        res = self.analyze(current_spread, session, session_spread_max)
        return res["spread_ok"]

    def is_valid(self, current_spread: float, session: str = "LONDON", session_spread_max: float = 30.0) -> bool:
        return self.check(current_spread, session, session_spread_max)

