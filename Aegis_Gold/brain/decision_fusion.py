import logging
import math
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("aegis.decision_fusion")

@dataclass
class FusionResult:
    long_prob: float
    short_prob: float
    no_trade_prob: float
    confidence: int
    uncertainty: float
    estimated_rr: float
    fused_direction: str
    action: str  # "TRADE" or "WAIT"
    block_reason: str

class DecisionFusionV2:
    """
    QUANT X Decision Fusion Layer v2:
    Ensembles multiple indicators, ML models, and RL recommendations.
    Weights each source dynamically by recent calibration and drift metrics.
    Enforces safe consensus rules and uncertainty-based gating.
    """

    def __init__(self):
        pass

    def fuse(
        self,
        smc_signal: Optional[dict],
        scalp_signal: Optional[dict],
        ml_prediction: Optional[dict],
        rl_action: str,
        rl_confidence: int,
        stat_analysis: Optional[dict],
        macro_blackout: bool,
        regime_type: str,
        regime_confidence: float,
        regime_ambiguous: bool,
        calibration_penalty: int,
        drift_defensive: bool,
        pattern_signal: Optional[dict] = None,
        unified_decision: Optional[Any] = None,
    ) -> FusionResult:
        from config.quant_x_config import QX

        # Default fallback results
        long_prob = 0.0
        short_prob = 0.0
        no_trade_prob = 1.0
        confidence = 0
        uncertainty = 0.0
        estimated_rr = 0.0
        fused_direction = "NA"
        action = "WAIT"
        block_reason = ""

        # Initialize pattern_signal safely - never undefined
        if not isinstance(pattern_signal, dict):
            pattern_signal = {
                "direction": "NONE",
                "confidence": 0.0,
                "pattern_name": None,
                "source": "none"
            }

        # Gather weights based on drift & calibration
        w_ml = 0.40
        w_smc = 0.35
        w_pattern = 0.25
        w_rl = 0.15
        w_unified = 0.50

        if drift_defensive:
            w_ml = 0.10  # demote drifted ML prediction
            w_smc = 0.50
            w_pattern = 0.40
            logger.info("[FUSION] Feature drift detected: demoting ML Ensemble weight.")

        # Aggregate probabilities for BUY, SELL, WAIT
        buy_votes = []
        sell_votes = []
        
        # 0. Unified Institutional Quant AI Neural Brain Input (Top Priority)
        if unified_decision is not None and getattr(unified_decision, "action", "WAIT") == "TRADE":
            u_dir = getattr(unified_decision, "direction", "NA")
            u_conf = float(getattr(unified_decision, "confidence", 0)) / 100.0
            if u_dir == "BUY":
                buy_votes.append(u_conf * w_unified)
            elif u_dir == "SELL":
                sell_votes.append(u_conf * w_unified)

        # 1. SMC Signal Input
        if smc_signal and smc_signal.get("direction") != "NONE":
            smc_dir = smc_signal.get("direction")
            smc_conf = float(smc_signal.get("confidence", 0.0)) / 100.0
            if smc_dir == "BUY":
                buy_votes.append(smc_conf * w_smc)
            elif smc_dir == "SELL":
                sell_votes.append(smc_conf * w_smc)

        # 2. Pattern Signal Input
        if pattern_signal and pattern_signal.get("direction") != "NONE":
            pattern_dir = pattern_signal.get("direction")
            pattern_conf = float(pattern_signal.get("confidence", 0.0)) / 100.0
            if pattern_dir == "BUY":
                buy_votes.append(pattern_conf * w_pattern)
            elif pattern_dir == "SELL":
                sell_votes.append(pattern_conf * w_pattern)
            
            logger.debug(
                "[PATTERN_FLOW] DecisionFusion processing pattern_signal: "
                "direction=%s confidence=%.1f%% pattern_name=%s contribution=%.3f",
                pattern_dir, pattern_signal.get("confidence", 0.0),
                pattern_signal.get("pattern_name", "unknown"),
                (pattern_conf * w_pattern)
            )

        # 3. ML Prediction Input
        if ml_prediction and ml_prediction.get("direction") != "NEUTRAL":
            ml_dir = ml_prediction.get("direction")
            ml_conf = float(ml_prediction.get("win_probability", 0.5))
            if ml_dir == "BUY":
                buy_votes.append(ml_conf * w_ml)
            elif ml_dir == "SELL":
                sell_votes.append(ml_conf * w_ml)
            
            # Incorporate ensemble disagreement into uncertainty
            ml_uncertainty = float(ml_prediction.get("uncertainty", 0.0))
            uncertainty = max(uncertainty, ml_uncertainty)

        # 4. RL Recommendation Input
        if rl_action != "WAIT":
            rl_conf = float(rl_confidence) / 100.0
            if rl_action == "BUY":
                buy_votes.append(rl_conf * w_rl)
            elif rl_action == "SELL":
                sell_votes.append(rl_conf * w_rl)

        # Calculate final buy/sell/wait probabilities normalized by active signal weights
        active_weights = 0.0
        if unified_decision is not None and getattr(unified_decision, "action", "WAIT") == "TRADE":
            active_weights += w_unified
        if smc_signal and smc_signal.get("direction") != "NONE":
            active_weights += w_smc
        if pattern_signal and pattern_signal.get("direction") != "NONE":
            active_weights += w_pattern
        if ml_prediction and ml_prediction.get("direction") != "NEUTRAL":
            active_weights += w_ml
        if rl_action != "WAIT":
            active_weights += w_rl

        if active_weights > 0:
            buy_prob = sum(buy_votes) / active_weights
            sell_prob = sum(sell_votes) / active_weights
            no_trade_prob = max(0.0, 1.0 - max(buy_prob, sell_prob))
        else:
            buy_prob = 0.0
            sell_prob = 0.0
            no_trade_prob = 1.0

        # Determine fused direction
        if buy_prob > sell_prob and buy_prob >= 0.40:
            fused_direction = "BUY"
            confidence = int(buy_prob * 100)
        elif sell_prob > buy_prob and sell_prob >= 0.40:
            fused_direction = "SELL"
            confidence = int(sell_prob * 100)
        else:
            fused_direction = "NA"
            confidence = int(max(buy_prob, sell_prob) * 100)

        # Conformal interval width & regime ambiguity contributes to uncertainty
        if regime_ambiguous:
            uncertainty += 0.25
        if stat_analysis and "conformal_interval_width" in stat_analysis:
            c_width = float(stat_analysis["conformal_interval_width"] or 0.5)
            uncertainty += c_width * 0.20

        # Apply calibration penalty to final confidence score
        confidence = max(0, confidence - calibration_penalty)

        # Gating rules:
        # 1. Macro Blackout Window Check
        if macro_blackout:
            action = "WAIT"
            block_reason = "VETO | Macro economic news blackout active"
        # 2. Uncertainty threshold breach check
        elif uncertainty > float(QX.get("fusion_uncertainty_block") or 0.60):
            action = "WAIT"
            block_reason = f"VETO | Combined uncertainty threshold breach ({uncertainty:.2f})"
        # 3. Disagreement block
        elif ml_prediction and float(ml_prediction.get("uncertainty", 0.0)) > float(QX.get("ensemble_disagreement_block_threshold") or 0.35):
            action = "WAIT"
            block_reason = f"VETO | ML ensemble disagreement too high"
        # 4. Adaptive threshold gating (EQS-driven, replaces hardcoded 50%)
        # Get adaptive threshold from AdaptiveLearning — rises during drawdown
        _fusion_min = 60  # default 60%
        try:
            from brain.adaptive_learning import AdaptiveLearning
            _fusion_min = int(AdaptiveLearning().get_eqs_threshold() * 100)
        except Exception:
            pass

        # Uncertainty penalty: high model disagreement raises the required bar
        _uncertainty_penalty = int(max(0.0, uncertainty - 0.3) * 20)  # up to +10 pts
        _effective_threshold = min(75, _fusion_min + _uncertainty_penalty)

        if confidence >= _effective_threshold:
            action = "TRADE"
        else:
            action = "WAIT"
            block_reason = (
                f"Confidence {confidence}% < adaptive threshold {_effective_threshold}% "
                f"(base={_fusion_min}%, uncertainty_penalty={_uncertainty_penalty}pts)"
            )


        return FusionResult(
            long_prob=round(buy_prob, 4),
            short_prob=round(sell_prob, 4),
            no_trade_prob=round(no_trade_prob, 4),
            confidence=confidence,
            uncertainty=round(uncertainty, 4),
            estimated_rr=estimated_rr,
            fused_direction=fused_direction,
            action=action,
            block_reason=block_reason
        )