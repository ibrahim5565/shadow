"""
ANTIGRAVITY OMEGA — Local Risk Manager Module
Interfaces with modules/risk_manager.py to validate constraints.
"""
import logging
from modules.risk_manager import RiskManager as CoreRiskManager

logger = logging.getLogger("aegis.omega.risk")

class OMEGARiskManager:
    def __init__(self, gateway):
        self.core_risk = CoreRiskManager(gateway)
        logger.info("Local OMEGA Risk Manager wrapper initialized.")

    def evaluate(self, account_info: dict, session: str, current_spread: float, symbol_config: dict) -> dict:
        """
        Runs OMEGA risk validation checks.
        """
        reasons = []
        approved = True

        # Ensure core risk starts daily state
        if self.core_risk.start_equity <= 0 and account_info:
            self.core_risk.init_daily(account_info.get("equity", 10000.0))

        # Check consecutive losses
        consec_losses = self.core_risk.consecutive_losses
        if consec_losses >= 5:
            approved = False
            reasons.append(f"Pause active: {consec_losses} consecutive losses")

        # Check spread limits
        max_spread = symbol_config.get("spread_limits", {}).get(session, 30)
        if current_spread > max_spread:
            approved = False
            reasons.append(f"Spread {current_spread:.0f} pts too wide (Cap: {max_spread} pts)")

        reason_str = "Risk cleared" if approved else f"Risk restricted: {', '.join(reasons)}"

        return {
            "approved": approved,
            "consecutive_losses": consec_losses,
            "reason": reason_str
        }
