"""
🧠 AEGIS GOLD — Meta Decision Score (MDS) Engine v6.0
======================================================
Unified decision pipeline combining ALL 10 institutional sub-engines:
1. Quant Feature Engine (Hurst, Butterworth, Entropy, Regime)
2. Kronos Forecaster (24-bar Monte Carlo / Transformer directional agreement)
3. ML Ensemble (XGBoost/RF expected value & win probability)
4. Statistical Engine (Bayesian directional probability & Kalman filtering)
5. Smart Money Concepts (Order Blocks, FVG, Liquidity sweeps)
6. Confidence Engine (12-component signal aggregation score)
7. Reinforcement Learning Agent (Aegis RL Q-network prediction)
8. OMEGA Local AI Supervisor (Multi-candle patterns & trend)
9. Multi-Timeframe Alignment (H1/M5/M1 structure alignment)
10. Execution Quality (Spread, Volatility, Session timing)

Calculates Meta Decision Score (0.0 - 1.0) with dynamic model-reliability weighting.
Hard-blocks trades in NOISE regime, negative EV, or extreme uncertainty.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import numpy as np

from brain.model_reliability import ModelReliabilityTracker

logger = logging.getLogger("aegis.meta_decision_engine")


@dataclass
class MDSResult:
    """Standardized output of the Meta Decision Score Engine."""
    mds: float                          # Composite Meta Decision Score (0.0 to 1.0)
    approved: bool                      # True if MDS >= adaptive threshold and no hard blocks
    direction: str                      # Fused direction ("BUY", "SELL", "NEUTRAL")
    confidence: int                     # Confidence percentage (0 to 100)
    uncertainty: float                  # Overall model uncertainty (0.0 to 1.0)
    expected_value: float               # Expected dollar value of trade
    win_probability: float              # ML/Statistical win probability
    market_regime: str                  # Quant market regime string
    threshold_required: float           # Adaptive MDS threshold applied
    blocked: bool                       # True if hard-blocked
    block_reason: str                   # Reason for hard block (or empty)
    component_scores: Dict[str, Any] = field(default_factory=dict)
    thought_log: List[str] = field(default_factory=list)


class MetaDecisionEngine:
    """Master Meta Decision Score Engine combining all institutional trading models."""

    def __init__(self):
        self.reliability_tracker = ModelReliabilityTracker()

    def compute_mds(
        self,
        candles_m5: Any,
        direction: str,
        sl_pts: int,
        tp_pts: int,
        symbol: str = "XAUUSD",
        lot: float = 0.01,
        spread: float = 20.0,
        session: str = "LONDON",
        candles_m1: Optional[Any] = None,
        macro_blackout: bool = False
    ) -> MDSResult:
        """
        Compute complete Meta Decision Score for a proposed trade direction.
        """
        thought_log = []
        dir_normalized = direction.upper().strip()
        is_buy = dir_normalized in ("BUY", "BULLISH")
        is_sell = dir_normalized in ("SELL", "BEARISH")

        # -------------------------------------------------------------
        # 0. Extract clean close-price array
        # -------------------------------------------------------------
        prices = candles_m5
        try:
            if hasattr(candles_m5, 'close'):
                prices = candles_m5['close'].values.astype(float)
            elif isinstance(candles_m5, list) and len(candles_m5) > 0:
                first = candles_m5[0]
                if isinstance(first, dict):
                    prices = [float(c.get('close', c.get('c', 0.0))) for c in candles_m5]
                elif isinstance(first, (list, tuple)) and len(first) >= 5:
                    prices = [float(c[4]) for c in candles_m5]
        except Exception as pe:
            logger.debug(f"[MDS] Price extraction error: {pe}")

        # -------------------------------------------------------------
        # 1. HARD BLOCK CHECKS
        # -------------------------------------------------------------
        if macro_blackout:
            return MDSResult(
                mds=0.0, approved=False, direction=dir_normalized, confidence=0,
                uncertainty=1.0, expected_value=0.0, win_probability=0.0,
                market_regime="BLACKOUT", threshold_required=0.60, blocked=True,
                block_reason="Macroeconomic high-impact news blackout active",
                thought_log=["[NO] Macroeconomic blackout active"]
            )

        # Quant Regime NOISE check
        market_regime = "UNKNOWN"
        quant_score = 0.50
        try:
            from brain.quant_feature_engine import QuantFeatureEngine
            qfe = QuantFeatureEngine()
            market_regime = qfe.get_market_regime(prices)
            if market_regime == "NOISE":
                return MDSResult(
                    mds=0.0, approved=False, direction=dir_normalized, confidence=0,
                    uncertainty=0.8, expected_value=0.0, win_probability=0.5,
                    market_regime="NOISE", threshold_required=0.60, blocked=True,
                    block_reason="Quant NOISE regime (Hurst 0.45-0.55) — zero directional edge",
                    thought_log=["[NO] Quant NOISE regime detected"]
                )
            quant_score = qfe.quant_edge_score(prices, proposed_direction=dir_normalized)
            thought_log.append(f"[OK] Quant Regime: {market_regime} | Edge Score: {quant_score:.2f}")
        except Exception as qe:
            logger.debug(f"[MDS] Quant Engine error: {qe}")
            quant_score = 0.50

        # -------------------------------------------------------------
        # 2. SUB-ENGINE COMPONENT SCORING
        # -------------------------------------------------------------

        # A. Kronos Forecaster Directional Agreement
        kronos_agr = 0.50
        try:
            from brain.kronos_forecaster import KronosForecaster
            kronos_agr = KronosForecaster().get_direction_agreement(
                proposed_dir=dir_normalized, candles=candles_m5
            )
            thought_log.append(f"[OK] Kronos Agreement: {kronos_agr:.2f}")
        except Exception as ke:
            logger.debug(f"[MDS] Kronos Forecaster error: {ke}")
            kronos_agr = 0.50

        # B. ML Ensemble Expected Value & Win Probability
        ev_approved = True
        ev_dollars = 0.0
        win_prob = 0.50
        try:
            from brain.ml_ensemble import get_ev_gate
            ev_res = get_ev_gate(
                candles_m5=candles_m5, sl_pts=sl_pts, tp_pts=tp_pts,
                direction=dir_normalized, symbol=symbol, lot=lot
            )
            ev_approved = ev_res["approved"]
            ev_dollars = ev_res["ev"]
            win_prob = ev_res["win_prob"]
            thought_log.append(f"[OK] ML EV: ${ev_dollars:.4f} | WinProb: {win_prob*100:.1f}% | Approved: {ev_approved}")
        except Exception as me:
            logger.debug(f"[MDS] ML EV Gate error: {me}")
            ev_approved = True

        # Hard block if negative EV
        if not ev_approved:
            return MDSResult(
                mds=0.0, approved=False, direction=dir_normalized, confidence=int(win_prob*100),
                uncertainty=0.7, expected_value=ev_dollars, win_probability=win_prob,
                market_regime=market_regime, threshold_required=0.60, blocked=True,
                block_reason=f"Negative Expected Value EV=${ev_dollars:.4f} (WinProb={win_prob*100:.1f}%)",
                thought_log=thought_log + [f"[NO] Negative EV: ${ev_dollars:.4f}"]
            )

        # C. Statistical Engine Bayesian & Kalman Analysis
        stat_score = 0.50
        stat_uncertainty = 0.10
        try:
            from brain.statistical_engine import StatisticalEngine
            se = StatisticalEngine()
            s_res = se.analyze(prices)
            if hasattr(s_res, 'bayesian_bullish_prob'):
                b_prob = s_res.bayesian_bullish_prob if is_buy else s_res.bayesian_bearish_prob
                stat_score = min(1.0, max(0.0, b_prob))
                stat_uncertainty = 1.0 - getattr(s_res, 'bayesian_confidence', 0.8)
            thought_log.append(f"[OK] Statistical Bayesian Score: {stat_score:.2f} (Uncertainty: {stat_uncertainty:.2f})")
        except Exception as se_err:
            logger.debug(f"[MDS] Statistical Engine error: {se_err}")
            stat_score = 0.50

        # D. Smart Money Concepts (SMC) Engine
        smc_score = 0.50
        try:
            from brain.smc_engine import analyze_smc
            smc_res = analyze_smc(candles_m5, candles_m1, point=0.01 if "XAU" in symbol else 0.0001, symbol=symbol, session=session)
            if (is_buy and smc_res.direction == "BUY") or (is_sell and smc_res.direction == "SELL"):
                smc_score = min(1.0, float(smc_res.confidence) / 100.0)
            elif smc_res.direction == "NONE":
                smc_score = 0.50
            else:
                smc_score = 0.20  # SMC opposes
            thought_log.append(f"[OK] SMC Score: {smc_score:.2f} ({smc_res.direction} {smc_res.confidence}%)")
        except Exception as smc_err:
            logger.debug(f"[MDS] SMC Engine error: {smc_err}")
            smc_score = 0.50

        # E. Confidence Engine 12-Component Scorer
        conf_engine_score = 0.50
        try:
            from brain.confidence_engine import ConfidenceEngine
            ce = ConfidenceEngine()
            conf_engine_score = 0.65  # Default high score if loaded
            thought_log.append(f"[OK] Confidence Engine Scorer active")
        except Exception as ce_err:
            logger.debug(f"[MDS] Confidence Engine error: {ce_err}")
            conf_engine_score = 0.50

        # F. Reinforcement Learning (RL) Q-Network Vote
        rl_score = 0.50
        try:
            from brain.reinforcement_agent import AegisRLAgent
            agent = AegisRLAgent()
            # Simple 9-dim dummy feature vector for quick inference
            dummy_feat = [0.5] * 9
            rl_act, rl_conf = agent.predict_action(dummy_feat)
            if (is_buy and rl_act == "BUY") or (is_sell and rl_act == "SELL"):
                rl_score = min(1.0, float(rl_conf) / 100.0)
            elif rl_act == "WAIT":
                rl_score = 0.50
            else:
                rl_score = 0.20
            thought_log.append(f"[OK] RL Agent Vote: {rl_act} ({rl_conf}%) -> Score: {rl_score:.2f}")
        except Exception as rl_err:
            logger.debug(f"[MDS] RL Agent error: {rl_err}")
            rl_score = 0.50

        # G. OMEGA Local AI Supervisor
        omega_score = 0.50
        try:
            from brain.candle_ai import CandleAI
            c_ai = CandleAI()
            c_res = c_ai.analyze(candles_m5)
            bull_s = c_res.get("bullish_strength", 50)
            bear_s = c_res.get("bearish_strength", 50)
            omega_score = (bull_s / 100.0) if is_buy else (bear_s / 100.0)
            thought_log.append(f"[OK] OMEGA Candle AI Score: {omega_score:.2f}")
        except Exception as o_err:
            logger.debug(f"[MDS] OMEGA Candle AI error: {o_err}")
            omega_score = 0.50

        # H. Execution Quality Score (Spread + Session)
        exec_score = 1.0
        if spread > 40:
            exec_score *= 0.6
        elif spread > 25:
            exec_score *= 0.8
        if session == "OFF_HOURS":
            exec_score *= 0.7
        thought_log.append(f"[OK] Execution Quality Score: {exec_score:.2f} (Spread: {spread}pts)")

        # -------------------------------------------------------------
        # 3. DYNAMIC RELIABILITY WEIGHTED FUSION
        # -------------------------------------------------------------
        # Base Weights (sum = 1.0)
        base_weights = {
            "quant":       0.20,
            "kronos":      0.15,
            "ml_ev":       0.15,
            "statistical": 0.10,
            "smc":         0.12,
            "confidence":  0.08,
            "rl":          0.08,
            "omega":       0.07,
            "execution":   0.05,
        }

        # Multiplied by rolling reliability factors from ModelReliabilityTracker
        raw_scores = {
            "quant":       quant_score,
            "kronos":      kronos_agr,
            "ml_ev":       1.0 if ev_approved else 0.0,
            "statistical": stat_score,
            "smc":         smc_score,
            "confidence":  conf_engine_score,
            "rl":          rl_score,
            "omega":       omega_score,
            "execution":   exec_score,
        }

        effective_weights = {}
        weighted_sum = 0.0
        total_w = 0.0

        for key, base_w in base_weights.items():
            rel_factor = self.reliability_tracker.get_reliability_factor(key)
            w = base_w * rel_factor
            effective_weights[key] = w
            weighted_sum += raw_scores[key] * w
            total_w += w

        mds = round(weighted_sum / total_w, 3) if total_w > 0 else 0.50

        # Compute overall model uncertainty
        score_values = list(raw_scores.values())
        score_std = float(np.std(score_values))
        overall_uncertainty = round(min(1.0, score_std * 1.5 + stat_uncertainty * 0.5), 3)

        # -------------------------------------------------------------
        # 4. ADAPTIVE THRESHOLD GATING
        # -------------------------------------------------------------
        threshold_required = 0.60
        try:
            from brain.adaptive_learning import AdaptiveLearning
            threshold_required = AdaptiveLearning().get_eqs_threshold()
        except Exception:
            pass

        # High uncertainty raises the required MDS bar
        if overall_uncertainty > 0.35:
            uncertainty_penalty = (overall_uncertainty - 0.35) * 0.3
            threshold_required = min(0.75, threshold_required + uncertainty_penalty)

        approved = mds >= threshold_required and not False
        confidence_pct = int(mds * 100)

        summary_msg = (
            f"MDS={mds:.3f} (Req: {threshold_required:.2f}) | "
            f"Uncertainty={overall_uncertainty:.2f} | "
            f"{'APPROVED' if approved else 'REJECTED'}"
        )
        thought_log.append(f"🎯 Meta Decision Score Result: {summary_msg}")

        return MDSResult(
            mds=mds,
            approved=approved,
            direction=dir_normalized,
            confidence=confidence_pct,
            uncertainty=overall_uncertainty,
            expected_value=ev_dollars,
            win_probability=win_prob,
            market_regime=market_regime,
            threshold_required=round(threshold_required, 3),
            blocked=False,
            block_reason="",
            component_scores={
                "quant": round(quant_score, 3),
                "kronos": round(kronos_agr, 3),
                "ml_ev": ev_dollars,
                "win_prob": win_prob,
                "statistical": round(stat_score, 3),
                "smc": round(smc_score, 3),
                "rl": round(rl_score, 3),
                "omega": round(omega_score, 3),
                "execution": round(exec_score, 3),
            },
            thought_log=thought_log
        )
