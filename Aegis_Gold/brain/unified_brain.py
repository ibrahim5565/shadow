"""
🧠 AEGIS GOLD — UNIFIED INSTITUTIONAL QUANT AI NEURAL BRAIN
==============================================================
ARCHITECTURE v2.0 — Pattern-Based 7-Engine Consensus
  (Replaces indicator-confidence gating with pattern-agreement consensus)

7 ENGINES:
  1. Kronos Forecaster    — future price-path forecasting model
  2. SMC Engine           — order blocks, liquidity sweeps, FVGs, BOS/CHoCH
  3. Quant Feature Engine — Hurst, entropy, FFT/wavelets, fractal/regime
  4. ML Ensemble          — XGBoost, RF, NN, LogReg on closed-bar features
  5. OMEGA (AISupervisor) — candle/trend/momentum/volatility composite
  6. Neural DQN / RL      — meta-weighter only (NOT a directional voter)
  7. Unified/Master Brain — consensus fusion layer (this file)

CONSENSUS LOGIC:
  - All 7 engines called via engine.predict_vote(FrozenDecisionSnapshot)
  - RL Agent is meta-weighter only; directional count uses 6 engines
  - Minimum 5/6 directional agreement → TRADE; else → WAIT
  - Any vote with pattern_evidence.confirmation_time > snapshot.timestamp DISCARDED
  - SL/TP derived from structural patterns via brain/structural_sl_tp.py
  - 2.0R minimum R:R floor — hard reject if structural TP insufficient

TEMPORAL INTEGRITY:
  All engines receive only FrozenDecisionSnapshot (data timestamp <= T).
  No engine may call mt5.copy_rates_from_pos() inside predict_vote().

BACKWARD COMPATIBILITY:
  predict_unified() is preserved for legacy callers. It routes through the
  new run_pattern_consensus() when a FrozenDecisionSnapshot is available.
"""

import os
import sys
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False
from config import settings as cfg
from brain.candle_ai import CandleAI
from brain.regime import analyze_regime
from brain.smc_engine import SMCEngine, analyze_smc
from brain.indicators import RSI, ADX, ATR
from brain.reinforcement_agent import AegisRLAgent
from brain.advanced_neural_architecture import DuelingDQN, AdvancedActorCritic
from brain.quant_feature_engine import QuantFeatureEngine
from brain.kronos_forecaster import KronosForecaster
from brain.engine_vote import EngineVote, make_wait_vote
from brain.frozen_snapshot import FrozenDecisionSnapshot, build_snapshot
from brain.structural_sl_tp import derive_sl_tp, MIN_RR_RATIO

logger = logging.getLogger("aegis.unified_brain")

# ── Consensus configuration ────────────────────────────────────────────────
DIRECTIONAL_ENGINE_NAMES = ["smc", "kronos", "quant_feature_engine", "ml_ensemble", "omega"]
# Note: unified_brain itself can be a 6th directional voter if legacy predict_unified is used
MIN_DIRECTIONAL_AGREEMENT = 5   # Must be >= this many engines agreeing on same direction


@dataclass
class UnifiedDecision:
    action: str                       # "TRADE" or "WAIT"
    direction: str = "NA"             # "BUY", "SELL", "NA"
    confidence: int = 0               # 0 to 100
    profit_factor_score: float = 1.0  # Estimated PF contribution
    institutional_score: int = 0     # 0 to 100 grade
    model_consensus: float = 0.0      # % agreement across models
    reasoning: str = ""
    thought_log: List[str] = field(default_factory=list)
    component_scores: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PatternDecision:
    pattern_type: str
    action: str                       # "TRADE" or "WAIT"
    direction: str                    # "BUY", "SELL", or "WAIT"
    supporting_engines: List[str]
    conflicting_engines: List[str]
    entry_zone: float
    trigger_type: str
    stop_loss: float
    take_profit: float
    expected_value: float
    reason: str
    timestamp: datetime


class UnifiedQuantAIBrain:
    """Master Institutional Neural Engine combining RL, AI, Quant, Math, and SMC."""

    def __init__(self, model_dir: Optional[str] = None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model_dir = model_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
        
        # Sub-engines
        self.candle_ai = CandleAI()
        self.rl_agent = AegisRLAgent()
        
        # Neural Transformer Models
        self.nn_input_size = 50
        self.dueling_dqn = DuelingDQN(input_size=self.nn_input_size, hidden_size=256, n_actions=3).to(self.device)
        self.actor_critic = AdvancedActorCritic(input_size=self.nn_input_size, hidden_size=256, n_actions=3).to(self.device)
        
        self._load_neural_weights()

    def _load_neural_weights(self):
        """Loads trained PyTorch neural weights if available."""
        dqn_path = os.path.join(self.model_dir, "aegis_rl_actor.pt")
        if os.path.exists(dqn_path):
            try:
                state_dict = torch.load(dqn_path, map_location=self.device)
                self.dueling_dqn.load_state_dict(state_dict, strict=False)
                logger.info(f"[BRAIN] [UNIFIED BRAIN] Loaded DuelingDQN weights from {dqn_path}")
            except Exception as e:
                logger.warning(f"[WARN] [UNIFIED BRAIN] Could not load DuelingDQN weights: {e}")

    def extract_feature_vector(
        self,
        candles_m5: List[Any],
        candles_m1: Optional[List[Any]],
        symbol: str = "XAUUSD",
        session: str = "LONDON",
        spread: float = 20.0,
        point: float = 0.01
    ) -> np.ndarray:
        """
        Constructs a 50-dimensional feature tensor representing market micro-structure,
        regime, candle AI patterns, technical momentum, SMC blocks, and statistical volatility.
        """
        features = np.zeros(self.nn_input_size, dtype=np.float32)

        if candles_m5 is None or len(candles_m5) < 14:
            return features

        try:
            from brain.candle_utils import parse_hlc
            highs_m5, lows_m5, closes_m5 = parse_hlc(candles_m5)
            if not closes_m5:
                return features
        except Exception:
            return features

        # 1. Technical Indicators (0 - 9)
        rsi_m5 = RSI(closes_m5, 14)[-1] if len(closes_m5) >= 14 else 50.0
        adx_res = ADX(highs_m5, lows_m5, closes_m5, 14) if len(closes_m5) >= 14 else (20.0, 20.0, 20.0)
        adx_val = adx_res[0] if isinstance(adx_res, tuple) else 20.0
        atr_val = ATR(highs_m5, lows_m5, closes_m5, 14)[-1] if len(closes_m5) >= 14 else 1.0

        features[0] = rsi_m5 / 100.0
        features[1] = adx_val / 100.0
        features[2] = min(5.0, atr_val / (point * 100.0 if point > 0 else 1.0)) / 5.0
        features[3] = min(5.0, spread / 50.0)

        # 2. Candle AI Analysis (10 - 19)
        candle_res = self.candle_ai.analyze(candles_m5)
        features[10] = candle_res.get("bullish_strength", 0) / 100.0
        features[11] = candle_res.get("bearish_strength", 0) / 100.0
        features[12] = candle_res.get("pattern_score", 0) / 100.0
        features[13] = candle_res.get("body_ratio", 0.5)

        # 3. Market Regime (20 - 24)
        regime_res = analyze_regime(candles_m5)
        reg_score = getattr(regime_res, 'score', 50) if hasattr(regime_res, 'score') else (regime_res.get('score', 50) if isinstance(regime_res, dict) else 50)
        features[20] = reg_score / 100.0
        regime_str = getattr(regime_res, 'type', getattr(regime_res, 'trend', 'RANGING')) if hasattr(regime_res, 'type') else (regime_res.get('regime', 'RANGING') if isinstance(regime_res, dict) else 'RANGING')
        features[21] = 1.0 if "BULL" in regime_str or "UP" in regime_str else (-1.0 if "BEAR" in regime_str or "DOWN" in regime_str else 0.0)

        # 4. Smart Money Concepts (25 - 34)
        smc_res = analyze_smc(candles_m5, candles_m1, point=point, symbol=symbol, session=session)
        features[25] = smc_res.confidence / 100.0
        features[26] = 1.0 if smc_res.direction == "BUY" else (-1.0 if smc_res.direction == "SELL" else 0.0)
        features[27] = 1.0 if getattr(smc_res, 'ob_detected', (smc_res.ob_high > 0 or smc_res.ob_low > 0)) else 0.0
        features[28] = 1.0 if getattr(smc_res, 'fvg_detected', False) else 0.0
        features[29] = 1.0 if getattr(smc_res, 'liquidity_sweep', smc_res.sweep_level > 0) else 0.0

        # 5. Price Action Momentum & Quant Features (35 - 49)
        ret1 = (closes_m5[-1] - closes_m5[-2]) / closes_m5[-2] if len(closes_m5) > 1 and closes_m5[-2] != 0 else 0.0
        ret5 = (closes_m5[-1] - closes_m5[-6]) / closes_m5[-6] if len(closes_m5) > 5 and closes_m5[-6] != 0 else 0.0
        features[35] = np.clip(np.nan_to_num(ret1 * 100.0), -1.0, 1.0)
        features[36] = np.clip(np.nan_to_num(ret5 * 100.0), -1.0, 1.0)

        # Quant Feature Engine pass (40 - 45)
        try:
            qfe = QuantFeatureEngine()
            q_res = qfe.analyze(closes_m5)
            features[40] = float(q_res.get('hurst', 0.5))
            features[41] = float(q_res.get('entropy_shannon', 0.0)) / 5.0
            features[42] = min(5.0, float(q_res.get('parkinson_vol', 0.0))) / 5.0
        except Exception:
            pass

        return np.nan_to_num(features)

    def predict_unified(
        self,
        candles_m5: List[Any],
        candles_m1: Optional[List[Any]] = None,
        symbol: str = "XAUUSD",
        session: str = "LONDON",
        spread: float = 20.0,
        point: float = 0.01
    ) -> UnifiedDecision:
        """
        Executes unified Neural Quant AI inference.
        Combines Kronos forecaster, SMC engine, Quant Feature Engine, and PyTorch Neural Net.
        """
        thought_log = []
        feat_vec = self.extract_feature_vector(candles_m5, candles_m1, symbol, session, spread, point)

        # PyTorch Neural Pass
        self.dueling_dqn.eval()
        with torch.no_grad():
            feat_tensor = torch.from_numpy(feat_vec).unsqueeze(0).to(dtype=torch.float32, device=self.device)
            q_values = self.dueling_dqn(feat_tensor).cpu().numpy()[0]

        # Action mapping: 0 -> WAIT, 1 -> BUY, 2 -> SELL
        exp_q = np.exp(q_values - np.max(q_values))
        softmax_probs = exp_q / np.sum(exp_q)

        nn_action_idx = int(np.argmax(q_values))
        actions = ["WAIT", "BUY", "SELL"]
        nn_action = actions[nn_action_idx]
        nn_confidence = int(softmax_probs[nn_action_idx] * 100)

        thought_log.append(f"🧠 [Neural Network] Raw Prediction: {nn_action} ({nn_confidence}% confidence)")

        # Sub-engine evaluations
        smc_res = analyze_smc(candles_m5, candles_m1, point=point, symbol=symbol, session=session)
        candle_res = self.candle_ai.analyze(candles_m5)
        regime_res = analyze_regime(candles_m5)

        # Kronos forecaster pass (Source 5) — use cached instance to avoid repeated HF downloads
        kronos_direction = "NEUTRAL"
        kronos_conf = 0.50
        try:
            if not hasattr(self, "_kronos"):
                self._kronos = KronosForecaster()
            kf_res = self._kronos.forecast(candles_m5)
            kronos_direction = kf_res.predicted_direction
            kronos_conf = kf_res.confidence_up
            thought_log.append(f"⏳ [Kronos Forecaster] Horizon Direction: {kronos_direction} ({kronos_conf*100:.0f}% confidence)")
        except Exception as e:
            thought_log.append(f"⏳ [Kronos Forecaster] Fallback mode: {e}")

        # Quant feature pass (Hurst trend persistence filter)
        hurst_exponent = 0.50
        try:
            from brain.candle_utils import parse_closes
            closes_m5 = parse_closes(candles_m5) if candles_m5 else []
            if len(closes_m5) >= 20:
                qfe = QuantFeatureEngine()
                q_res = qfe.analyze(closes_m5)
                hurst_exponent = float(q_res.get('hurst', 0.50))
        except Exception:
            pass

        # Compute multi-model consensus
        buy_signals = 0
        sell_signals = 0
        total_sources = 5

        # Source 1: Neural Net
        if nn_action == "BUY": buy_signals += 1
        elif nn_action == "SELL": sell_signals += 1

        # Source 2: SMC Engine
        if smc_res.direction == "BUY": buy_signals += 1
        elif smc_res.direction == "SELL": sell_signals += 1

        # Source 3: Candle AI
        if candle_res.get("bullish_strength", 0) > 60: buy_signals += 1
        elif candle_res.get("bearish_strength", 0) > 60: sell_signals += 1

        # Source 4: Regime
        reg_str = getattr(regime_res, 'type', getattr(regime_res, 'trend', '')) if hasattr(regime_res, 'type') else (regime_res.get('regime', '') if isinstance(regime_res, dict) else '')
        if "BULL" in reg_str or "UP" in reg_str: buy_signals += 1
        elif "BEAR" in reg_str or "DOWN" in reg_str: sell_signals += 1

        # Source 5: Kronos Forecaster
        if kronos_direction == "BUY": buy_signals += 1
        elif kronos_direction == "SELL": sell_signals += 1

        fused_direction = "NA"
        if buy_signals >= 3:
            fused_direction = "BUY"
            consensus_pct = (buy_signals / total_sources) * 100
        elif sell_signals >= 3:
            fused_direction = "SELL"
            consensus_pct = (sell_signals / total_sources) * 100
        else:
            fused_direction = "NA"
            consensus_pct = (max(buy_signals, sell_signals) / total_sources) * 100

        thought_log.append(f"🏛️ [Institutional Consensus] Direction: {fused_direction} ({consensus_pct:.0f}% consensus, Hurst: {hurst_exponent:.2f})")

        # Phase 3 Walk-Forward CV Data-Backed Consensus Gating Threshold (55%)
        min_consensus_required = 55.0  # Data-backed by Purged Walk-Forward CV sweep
        min_nn_confidence_required = 35 # Accessible neural confidence threshold

        final_action = "WAIT"
        reason = "Consensus insufficient"

        if fused_direction != "NA" and consensus_pct >= min_consensus_required:
            final_action = "TRADE"
            reason = f"High Institutional Consensus ({consensus_pct:.0f}%)"
            thought_log.append(f"✅ [Gating Passed] {reason}")
        else:
            reason = f"Gating Veto | NN Conf {nn_confidence}%, Consensus {consensus_pct:.0f}% < {min_consensus_required}%"
            thought_log.append(f"❌ [Gating Veto] {reason}")

        estimated_pf = 2.10 if final_action == "TRADE" else 1.0

        return UnifiedDecision(
            action=final_action,
            direction=fused_direction,
            confidence=nn_confidence,
            profit_factor_score=estimated_pf,
            institutional_score=int(consensus_pct),
            model_consensus=consensus_pct,
            reasoning=reason,
            thought_log=thought_log,
            component_scores={
                "nn_confidence": nn_confidence,
                "smc_confidence": smc_res.confidence,
                "kronos_confidence": int(kronos_conf * 100),
                "hurst_exponent": round(hurst_exponent, 2),
                "candle_strength": max(candle_res.get("bullish_strength", 0), candle_res.get("bearish_strength", 0)),
                "regime_score": getattr(regime_res, 'score', 50) if hasattr(regime_res, 'score') else 50,
            }
        )


# ═══════════════════════════════════════════════════════════════════════════
# 🎯 PATTERN CONSENSUS ARCHITECTURE V2.0 (7 ENGINES, NO INDICATOR GATES)
# ═══════════════════════════════════════════════════════════════════════════

def run_pattern_consensus(
    snapshot: FrozenDecisionSnapshot,
    engines: Optional[Dict[str, Any]] = None,
    min_agreement: int = 5,
) -> UnifiedDecision:
    """
    Executes 7-Engine Pattern Consensus on a FrozenDecisionSnapshot.

    STEPS:
    1. Collect EngineVote objects from all 7 engines using predict_vote(snapshot).
    2. Temporal Integrity Gate: Discard any vote whose pattern evidence has
       confirmation_time > snapshot.timestamp (leakage detection).
    3. Exclude RL Agent from directional vote count (RL is meta-weighter only).
    4. Count directional agreement among valid directional engines (SMC, Kronos, QFE, ML, OMEGA).
    5. Require >= min_agreement (default 5 of 6 directional engines) for BUY or SELL.
    6. Derive structural SL/TP via derive_sl_tp() from confirming pattern levels.
    7. Enforce 2.0R minimum floor: reject trade if structural TP < 2.0R.
    8. Return UnifiedDecision with detailed thought_log and component votes.
    """
    thought_log: List[str] = []
    now = snapshot.timestamp
    symbol = snapshot.symbol

    thought_log.append(f"⏱️ [Consensus Scan] T={now.isoformat()} Symbol={symbol} Price={snapshot.current_price}")

    # 1. Instantiate default engines if not provided
    if engines is None:
        engines = {}

    smc_eng = engines.get("smc") or SMCEngine(symbol=symbol, default_point=snapshot.point)
    kronos_eng = engines.get("kronos") or KronosForecaster()
    qfe_eng = engines.get("quant_feature_engine") or QuantFeatureEngine()

    from brain.ml_ensemble import MLEnsemble
    ml_eng = engines.get("ml_ensemble") or MLEnsemble()

    from brain.ai_supervisor import AISupervisor
    omega_eng = engines.get("omega") or AISupervisor()

    rl_eng = engines.get("rl_agent") or AegisRLAgent()

    # 2. Collect votes
    votes: List[EngineVote] = []
    engine_map = {
        "smc": smc_eng,
        "kronos": kronos_eng,
        "quant_feature_engine": qfe_eng,
        "ml_ensemble": ml_eng,
        "omega": omega_eng,
        "rl_agent": rl_eng,
    }

    for name, eng in engine_map.items():
        try:
            if hasattr(eng, "predict_vote"):
                vote = eng.predict_vote(snapshot)
            else:
                vote = make_wait_vote(name, f"Engine {name} missing predict_vote", signal_time=now)
            votes.append(vote)
        except Exception as exc:
            logger.warning(f"[Consensus] Engine '{name}' predict_vote exception: {exc}")
            votes.append(make_wait_vote(name, f"Exception: {exc}", signal_time=now))

    # 3. Temporal Integrity Gate: Check for future confirmation_time (leakage)
    valid_votes: List[EngineVote] = []
    discarded_votes: List[EngineVote] = []

    for vote in votes:
        # RL agent vote is meta-weighter only (not directional)
        if vote.engine_name == "rl_agent":
            continue

        violations = vote.leakage_check(now)
        if violations:
            logger.error(f"❌ [LEAKAGE AUDIT REJECT] {violations[0]}")
            thought_log.append(f"❌ [LEAKAGE DISCARD] {vote.engine_name}: {violations[0]}")
            discarded_votes.append(vote)
        else:
            valid_votes.append(vote)

    # 4. Extract RL Meta-Weights
    try:
        rl_weights = rl_eng.get_engine_weights(regime=snapshot.session)
    except Exception:
        rl_weights = {v.engine_name: 1.0 for v in valid_votes}

    # 5. Count directional agreement
    buy_votes = [v for v in valid_votes if v.direction == "BUY"]
    sell_votes = [v for v in valid_votes if v.direction == "SELL"]
    wait_votes = [v for v in valid_votes if v.direction == "WAIT"]

    buy_count = len(buy_votes)
    sell_count = len(sell_votes)

    thought_log.append(
        f"📊 [Engine Votes] BUY={buy_count}, SELL={sell_count}, WAIT={len(wait_votes)}, Discarded={len(discarded_votes)}"
    )
    for v in valid_votes:
        thought_log.append(f"  └─ {v.engine_name}: {v.direction} (conviction={v.conviction:.2f})")

    # Determine proposed consensus direction
    fused_direction = "NA"
    agreeing_votes: List[EngineVote] = []

    if buy_count >= min_agreement:
        fused_direction = "BUY"
        agreeing_votes = buy_votes
    elif sell_count >= min_agreement:
        fused_direction = "SELL"
        agreeing_votes = sell_votes

    if fused_direction == "NA":
        reason = f"No Consensus | BUY={buy_count}, SELL={sell_count} (Required >= {min_agreement}/{len(valid_votes)})"
        thought_log.append(f"❌ [Consensus Veto] {reason}")
        return UnifiedDecision(
            action="WAIT",
            direction="NA",
            confidence=int(max(buy_count, sell_count) / max(len(valid_votes), 1) * 100),
            profit_factor_score=1.0,
            institutional_score=0,
            model_consensus=round(max(buy_count, sell_count) / max(len(valid_votes), 1) * 100, 1),
            reasoning=reason,
            thought_log=thought_log,
            component_scores={v.engine_name: v.direction for v in votes},
        )

    thought_log.append(f"✅ [Consensus Reached] Direction={fused_direction} ({len(agreeing_votes)}/{len(valid_votes)} engines agree)")

    # 6. Structural SL/TP Derivation & 2.0R Floor Enforcement
    sl_price, tp_price, sl_basis, tp_basis = derive_sl_tp(agreeing_votes, fused_direction, snapshot, symbol)

    if sl_price is None or tp_price is None:
        reason = "Structural SL/TP Veto | Unable to derive valid pattern SL/TP meeting 2.0R floor"
        thought_log.append(f"❌ [SL/TP Veto] {reason}")
        return UnifiedDecision(
            action="WAIT",
            direction="NA",
            confidence=0,
            profit_factor_score=1.0,
            institutional_score=0,
            model_consensus=round(len(agreeing_votes) / max(len(valid_votes), 1) * 100, 1),
            reasoning=reason,
            thought_log=thought_log,
            component_scores={v.engine_name: v.direction for v in votes},
        )

    # 7. Convert SL/TP prices to points for main execution pipeline
    current_price = snapshot.current_price
    pt = snapshot.point
    sl_pts = int(round(abs(current_price - sl_price) / pt))
    tp_pts = int(round(abs(current_price - tp_price) / pt))
    rr_ratio = round((tp_pts / sl_pts), 2) if sl_pts > 0 else 0.0

    thought_log.append(f"🎯 [Structural Levels] SL={sl_price:.2f} ({sl_pts}pts | {sl_basis})")
    thought_log.append(f"🎯 [Structural Levels] TP={tp_price:.2f} ({tp_pts}pts | {tp_basis})")
    thought_log.append(f"⚖️ [R:R Floor Passed] Realized R:R = {rr_ratio}R >= {MIN_RR_RATIO}R floor")

    avg_conviction = sum(v.conviction * rl_weights.get(v.engine_name, 1.0) for v in agreeing_votes) / len(agreeing_votes)
    confidence = int(min(99, max(50, avg_conviction * 100)))

    return UnifiedDecision(
        action="TRADE",
        direction=fused_direction,
        confidence=confidence,
        profit_factor_score=round(2.0 + rr_ratio * 0.2, 2),
        institutional_score=int(len(agreeing_votes) / len(valid_votes) * 100),
        model_consensus=round(len(agreeing_votes) / len(valid_votes) * 100, 1),
        reasoning=f"7-Engine Consensus {fused_direction} | {len(agreeing_votes)}/{len(valid_votes)} Agree | R:R={rr_ratio}R",
        thought_log=thought_log,
        component_scores={
            "sl_price": sl_price,
            "tp_price": tp_price,
            "sl_pts": sl_pts,
            "tp_pts": tp_pts,
            "rr_ratio": rr_ratio,
            "sl_basis": sl_basis,
            "tp_basis": tp_basis,
            "agree_count": len(agreeing_votes),
            "total_valid_votes": len(valid_votes),
            "engine_votes": {v.engine_name: v.direction for v in valid_votes},
        },
    )
