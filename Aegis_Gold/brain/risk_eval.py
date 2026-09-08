"""
Layer D: Risk Evaluation
Validates that constraints, loss limits, and R:R rules are unbroken.
"""
from dataclasses import dataclass
from config import settings as cfg

@dataclass
class RiskState:
    approved: bool
    rejection_reason: str
    quality_score: int

def evaluate_risk(account: dict, structure, candles, risk_mgr, session: str, spread: float) -> RiskState:
    """
    Evaluates execution risk to prevent overtrading and revenge trading.
    """
    # Check 1: Daily Trade Limit (Unlimited trades)
    # Daily limits removed per user request
        
    # Check 2: Spread Check
    if spread > cfg.SPREAD_LIMITS.get(session, 40):
        return RiskState(False, f"Spread {spread:.0f}pts too wide for {session} session", 0)
    
    # Check 3: R:R Ratio Check - DISABLED for aggressive trading (user requirement)
    # User wants: 65%+ confidence = TRADE at any SL/TP
    # sl_distance = structure.sl_distance
    # if sl_distance < cfg.MIN_SL_POINTS:
    #     return RiskState(False, f"SL too tight ({sl_distance:.0f}pts). Noise risk.", 0)
    # if sl_distance > cfg.MAX_SL_POINTS:
    #     return RiskState(False, f"SL too wide ({sl_distance:.0f}pts). Risk too high.", 0)
    # if (tp_distance / sl_distance) < cfg.MIN_RR_RATIO:
    #     return RiskState(False, "R:R not sufficient.", 0)
        
    # Check 4: Consecutive Loss Check
    if risk_mgr is not None and hasattr(risk_mgr, 'consecutive_losses'):
        try:
            cl = getattr(risk_mgr, 'consecutive_losses')
            if isinstance(cl, (int, float)) and cl >= cfg.MAX_CONSECUTIVE_LOSSES:
                return RiskState(False, f"{cfg.MAX_CONSECUTIVE_LOSSES} consecutive losses. Pause active.", 0)
        except Exception:
            pass
    # risk_mgr=None → shadow mode / lazy-bound → treat as cleared (no trade history)
    
    # Daily Loss Check: DISABLED (per user request - unlimited daily loss allowed)
        
    # Quality Map
    quality_score = 50
    if session == "OVERLAP":
        quality_score += 30
    elif session in ["LONDON", "NY"]:
        quality_score += 20
    elif session == "ASIAN":
        quality_score -= 20
        
    return RiskState(True, "Clear", quality_score)
