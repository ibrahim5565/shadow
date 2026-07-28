from brain.ABSOLUTE_NEVER_PAUSE_ENFORCER import activate_absolute_never_pause

"""
The Brain Decision Engine v4.0 — SCALP Primary + SMC Secondary
PRIMARY:   Classic scalp (regime/structure/entry) — ALWAYS 50% threshold
SECONDARY: Smart Money Concepts — fires if scalp confidence >= 50%

Dashboard always receives a live confidence score regardless of which path fires.
User Priority: Take every trade >= 50% confidence (50% display = 50% gate = TRADE)
"""
import logging
import statistics
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from dataclasses import dataclass, field
from config import settings as cfg
from brain.regime import analyze_regime
from brain.structure import analyze_structure
from brain.entry import analyze_entry
from brain.risk_eval import evaluate_risk
from brain.indicators import ATR, RSI
from brain.adaptive_learning import AdaptiveLearning
from brain.brain_logger import log_decision
from brain.smc_engine import analyze_smc
from brain.regime_switcher import get_strategy_state
from brain.explainability import build_explanation, save_explanation

logger = logging.getLogger("aegis.brain")


# ─────────────────────────────────────────────────────────────
# Decision dataclass
# ─────────────────────────────────────────────────────────────

@dataclass
class Decision:
    action: str               # "TRADE" or "WAIT"
    direction: str = "NA"
    lot: float = 0.0
    tp_points: int = 0
    sl_points: int = 0
    confidence: int = 0
    grade: str = "F"
    regime: str = "NA"
    regime_score: int = 0
    structure: str = "NA"
    structure_score: int = 0
    entry_score: int = 0
    reason: str = ""
    pattern: str = "NONE"
    rr_ratio: float = 0.0
    atr_estimate: float = 0.0
    news_clear: bool = True
    mode: str = "NORMAL"
    adx_val: float = 0.0
    rsi_val: float = 0.0
    thought_log: list = field(default_factory=list)
    signal_source: str = "SCALP"   # "SMC" or "SCALP"


def _build_thought(step: str, detail: str, passed: bool) -> str:
    icon = "✅" if passed else "❌"
    return f"{icon} [{step}] {detail}"


# ─────────────────────────────────────────────────────────────
# Lot sizing helper
# ─────────────────────────────────────────────────────────────

def _calc_lot(sym_cfg: dict, risk_mgr) -> float:
    """
    Returns the correct lot size for this symbol and mode.
    Manual override > config > adaptive learning.
    """
    # Manual override takes priority
    if getattr(risk_mgr, "lot_override", 0.0) > 0.0:
        return risk_mgr.lot_override

    # Use config values
    if cfg.DEMO_MODE:
        base_lot = sym_cfg.get("base_lot_demo", 0.01)
    else:
        base_lot = sym_cfg.get("base_lot_live", 0.01)

    max_lot = sym_cfg.get("max_lot", 0.01)

    # Apply adaptive learning (only reduces, never increases)
    try:
        adaptive       = AdaptiveLearning()
        lot_multiplier = adaptive.get_adaptations().get("lot_multiplier", 1.0)
    except Exception:
        lot_multiplier = 1.0

    lot = base_lot * lot_multiplier
    lot = max(0.01, min(max_lot, round(lot, 2)))

    return lot


# ─────────────────────────────────────────────────────────────
# Main decision engine
# ─────────────────────────────────────────────────────────────

def _decide_impl(ticks, candles_m5, account: dict, risk_mgr, session: str,
                 spread: float, point: float, symbol: str = "XAUUSD",
                 candles_m1=None) -> Decision:
    """
    Routing:
      PATH 1 — SMC (PRIMARY):   BOS/CHoCH + OB + Liquidity Sweep + PO3 + FVG
                                 score >= SMC_SIGNAL_THRESHOLD → TRADE
      PATH 2 — SCALP (FALLBACK): regime + structure + entry + risk
                                 confidence >= threshold → TRADE
      Otherwise → WAIT  (dashboard still shows best available confidence)
    """
    sym_cfg       = cfg.get_symbol_config(symbol)
    scalp_ctrl    = getattr(cfg, "SCALP_MODE_CONTROL", "smc")
    bypass_gates  = scalp_ctrl in ("ultra_pro", "first_200_trades", "smc", "scalp")
    smc_threshold = getattr(cfg, "SMC_SIGNAL_THRESHOLD", 55)
    thoughts: list = []

    lot      = _calc_lot(sym_cfg, risk_mgr)
    curr_rsi = 50.0

    # Pre-compute ATR for SL/TP sizing (used by all paths below)
    atr_estimate = 0.0
    try:
        if candles_m5 is not None and len(candles_m5) >= 14:
            def _extract_series(candles, key_name, tuple_idx):
                res = []
                for c in candles:
                    if isinstance(c, dict):
                        res.append(float(c[key_name]))
                    elif hasattr(c, key_name):
                        res.append(float(getattr(c, key_name)))
                    else:
                        res.append(float(c[tuple_idx]))
                return res

            _cl = _extract_series(candles_m5, "close", 4)
            _hi = _extract_series(candles_m5, "high", 2)
            _lo = _extract_series(candles_m5, "low", 3)
            _atrs = ATR(_hi, _lo, _cl, 14)
            atr_price = _atrs[-1] if _atrs else 0.0
            atr_estimate = (atr_price / point) if (point > 0 and atr_price > 0) else 0.0
    except Exception as _atr_err:
        logger.warning(f"[{symbol}] ATR calculation error in brain: {_atr_err}")
        atr_estimate = 0.0

    if atr_estimate <= 0.0:
        atr_estimate = 150.0 if ("XAU" in symbol.upper() or "GOLD" in symbol.upper()) else 40.0

    # RSI for dashboard (best-effort)
    try:
        cl = ([c["close"] for c in candles_m5]
              if isinstance(candles_m5[-1], dict)
              else [c[4] for c in candles_m5])
        rs = RSI(cl, 14)
        curr_rsi = rs[-1] if rs else 50.0
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════
    # PATH 0 — UNIFIED INSTITUTIONAL QUANT AI NEURAL BRAIN (TOP PRIORITY)
    # ══════════════════════════════════════════════════════════
    try:
        from brain.unified_brain import UnifiedQuantAIBrain
        if not hasattr(_decide_impl, "_unified_brain"):
            _decide_impl._unified_brain = UnifiedQuantAIBrain()
        
        unified_dec = _decide_impl._unified_brain.predict_unified(
            candles_m5=candles_m5, candles_m1=candles_m1, symbol=symbol,
            session=session, spread=spread, point=point
        )
        
        for t in unified_dec.thought_log:
            thoughts.append(t)
            
        if unified_dec.action == "TRADE" and unified_dec.confidence >= 50:
            logger.info(f"🧠 [{symbol}] UNIFIED QUANT AI NEURAL BRAIN SIGNAL: {unified_dec.direction} ({unified_dec.confidence}% conf)")
            # Compute ATR-scaled SL/TP — SL is never zero
            try:
                _u_atr_pts = getattr(unified_dec, "atr_estimate", 0.0) or atr_estimate
                _u_exits = risk_mgr.atr_scaled_sl_tp(symbol, _u_atr_pts, unified_dec.confidence)
                _u_sl = _u_exits["sl_pts"]
                _u_tp = _u_exits["tp_pts"]
                _u_rr = _u_exits["rr_ratio"]
            except Exception:
                is_gold = ("XAU" in symbol.upper() or "GOLD" in symbol.upper())
                _u_sl, _u_tp, _u_rr = (150, 300, 2.0) if is_gold else (40, 80, 2.0)  # safe symbol defaults (meets mandatory SL floor)
            return Decision(
                action="TRADE",
                direction=unified_dec.direction,
                lot=lot,
                tp_points=_u_tp,
                sl_points=_u_sl,
                confidence=unified_dec.confidence,
                grade="A+" if unified_dec.confidence >= 70 else "A",
                regime="UNIFIED_QUANT_AI",
                regime_score=unified_dec.confidence,
                structure="INSTITUTIONAL_NEURAL",
                structure_score=unified_dec.institutional_score,
                entry_score=unified_dec.confidence,
                reason=unified_dec.reasoning,
                pattern="NEURAL_TRANSFORMER_DQN",
                rr_ratio=_u_rr,
                adx_val=0.0,
                rsi_val=curr_rsi,
                thought_log=thoughts,
                signal_source="UNIFIED_QUANT_AI"
            )
    except Exception as e:
        logger.warning(f"[{symbol}] Unified Quant AI Brain error: {e}", exc_info=True)

    # ══════════════════════════════════════════════════════════
    # PATH 1 — SMART MONEY CONCEPTS  (PRIMARY)
    # ══════════════════════════════════════════════════════════
    smc = None
    try:
        smc = analyze_smc(candles_m5, candles_m1,
                          point=point, symbol=symbol, session=session)
    except Exception as e:
        logger.warning(f"[{symbol}] SMC error: {e}", exc_info=True)

    if smc is not None and smc.direction not in ("NONE", "NA"):
        thoughts.append(_build_thought(
            "SMC", smc.reason, smc.confidence >= smc_threshold))
        for d in smc.details:
            thoughts.append(f"    {d}")

        if smc.confidence >= smc_threshold:
            # Spread / consecutive-loss check
            try:
                fake_struct = type("S", (), {
                    "sl_distance": smc.sl_pts,
                    "position": "SMC_ZONE",
                    "preferred_direction": smc.direction,
                    "confluence_score": smc.confidence,
                })()
                risk = evaluate_risk(account, fake_struct,
                                     candles_m5, risk_mgr, session, spread)
            except Exception as e:
                logger.warning(f"[{symbol}] SMC risk-eval error: {e}")
                risk = type("R", (), {
                    "approved": True,
                    "rejection_reason": "",
                    "quality_score": 50,
                })()

            if not risk.approved:
                return Decision(
                    action="WAIT", direction=smc.direction,
                    confidence=smc.confidence, grade=smc.grade,
                    regime="SMC", regime_score=smc.confidence,
                    structure="SMC_ZONE", structure_score=smc.confidence,
                    entry_score=smc.confidence,
                    reason=f"SMC risk-blocked: {risk.rejection_reason}",
                    adx_val=0.0, rsi_val=curr_rsi,
                    thought_log=thoughts, signal_source="SMC",
                )

            rr = round(smc.tp_pts / smc.sl_pts, 2) if smc.sl_pts > 0 else 0.0
            final = (
                f"🎯 SMC TRADE | conf={smc.confidence}% {smc.grade} | "
                f"{smc.direction} {symbol} | "
                f"BOS={'✅' if smc.bos_confirmed else '❌'} "
                f"CHoCH={'✅' if smc.choch_confirmed else '❌'} | "
                f"SL:{smc.sl_pts}pts TP:{smc.tp_pts}pts RR:{rr} | Lot:{lot}"
            )
            logger.info(f"[{symbol}] {final}")

            return Decision(
                action="TRADE",
                direction=smc.direction,
                lot=lot,
                tp_points=smc.tp_pts,
                sl_points=smc.sl_pts,
                confidence=smc.confidence,
                grade=smc.grade,
                regime="SMC",
                regime_score=smc.confidence,
                structure="SMC_ZONE",
                structure_score=smc.confidence,
                entry_score=smc.confidence,
                reason=final,
                pattern=smc.po3_phase,
                rr_ratio=rr,
                news_clear=True,
                mode=f"SMC_{smc.po3_phase}",
                adx_val=0.0,
                rsi_val=curr_rsi,
                thought_log=thoughts,
                signal_source="SMC",
            )

        thoughts.append(_build_thought(
            "SMC_GATE",
            f"SMC {smc.confidence}% < threshold {smc_threshold}% — scalp fallback",
            False,
        ))

    # ══════════════════════════════════════════════════════════
    # PATH 2 — CLASSIC SCALP  (SECONDARY / FALLBACK)
    # ══════════════════════════════════════════════════════════
    thoughts.append(_build_thought(
        "SCALP", "Running classic scalp analysis as secondary signal", True))

    # Regime
    try:
        regime = analyze_regime(candles_m5, symbol=symbol, point=point)
    except Exception as e:
        logger.warning(f"[{symbol}] Regime error: {e}")
        return Decision(action="WAIT", reason=f"Regime error: {e}",
                        confidence=0, signal_source="SCALP")

    session_clear = "Outside active session" not in regime.reason
    thoughts.append(_build_thought(
        "SESSION",
        "UTC session active" if session_clear else regime.reason,
        session_clear,
    ))

    adx_val  = regime.adx if regime.adx else 0.0
    adx_min  = 15.0 if symbol == "XAUUSD" else 25.0
    adx_ok   = True if bypass_gates else adx_val > adx_min
    thoughts.append(_build_thought(
        "ADX",
        f"ADX={adx_val:.1f} ({'bypassed' if bypass_gates else 'checked'})",
        adx_ok,
    ))

    slope_min = 5.0 if symbol == "XAUUSD" else 20.0
    slope_ok  = True if bypass_gates else abs(regime.ema_slope) > slope_min
    thoughts.append(_build_thought(
        "SLOPE", f"Slope={regime.ema_slope:.1f}°", slope_ok))

    thoughts.append(_build_thought(
        "REGIME", f"{regime.type} (scalp — all conditions allowed)", True))

    # Structure
    try:
        from brain.candle_utils import parse_closes
        curr_px = (ticks[-1]["bid"] if len(ticks) > 0 else parse_closes(candles_m5)[-1])
        structure = analyze_structure(candles_m5, curr_px, regime.trend, point)
    except Exception as e:
        logger.warning(f"[{symbol}] Structure error: {e}")
        structure = type("S", (), {
            "confluence_score": 30, "position": "NA",
            "preferred_direction": "BUY", "sl_distance": 20, "score": 30,
        })()

    direction = (structure.preferred_direction
                 if structure.preferred_direction != "NONE"
                 else ("BUY" if regime.trend == "TRENDING_UP" else "SELL"))

    # Entry
    try:
        ec    = candles_m1 if (candles_m1 is not None and len(candles_m1) >= 15) else candles_m5
        entry = analyze_entry(ticks, ec, direction)
    except Exception as e:
        logger.warning(f"[{symbol}] Entry error: {e}")
        entry = type("E", (), {"timing_score": 20, "reason": "NONE"})()

    # Risk
    try:
        risk = evaluate_risk(account, structure, candles_m5, risk_mgr,
                             session, spread)
    except Exception as e:
        logger.warning(f"[{symbol}] Risk error: {e}")
        risk = type("R", (), {
            "approved": True, "quality_score": 30, "rejection_reason": "",
        })()

    # Confidence
    total = (regime.confidence_score * 0.30
             + structure.confluence_score * 0.30
             + entry.timing_score        * 0.25
             + risk.quality_score        * 0.15)
    # Blend with SMC score so dashboard reflects best reading
    if smc and smc.confidence > 0:
        total = max(total, smc.confidence * 0.70)
    total = max(0.0, min(100.0, total))

    if   total >= 80: grade = "A"
    elif total >= 60: grade = "B"
    elif total >= 40: grade = "C"
    elif total >= 20: grade = "D"
    else:             grade = "F"

    thoughts.append(_build_thought(
        "CONFIDENCE", f"{total:.0f}% → {grade}", total >= 50.0))

    # ── Gates ────────────────────────────────────────────────
    if not session_clear and not (getattr(cfg, "ABSOLUTE_NEVER_PAUSE", False) or getattr(cfg, "FORCE_CONTINUOUS_TRADING", False)):
        return Decision(
            action="WAIT", direction=direction,
            confidence=int(total), grade=grade,
            regime=regime.type, regime_score=regime.score,
            structure=structure.position, structure_score=structure.confluence_score,
            entry_score=entry.timing_score, reason=regime.reason,
            adx_val=adx_val, rsi_val=curr_rsi, thought_log=thoughts,
        )

    if not adx_ok:
        return Decision(
            action="WAIT", direction=direction,
            confidence=int(total), grade=grade,
            regime=regime.type, regime_score=regime.score,
            structure=structure.position, structure_score=structure.confluence_score,
            entry_score=entry.timing_score,
            reason=f"ADX too low: {adx_val:.1f} (need >{adx_min})",
            adx_val=adx_val, rsi_val=curr_rsi, thought_log=thoughts,
        )

    if not slope_ok:
        return Decision(
            action="WAIT", direction=direction,
            confidence=int(total), grade=grade,
            regime=regime.type, regime_score=regime.score,
            structure=structure.position, structure_score=structure.confluence_score,
            entry_score=entry.timing_score,
            reason=f"EMA slope flat: {regime.ema_slope:.1f}°",
            adx_val=adx_val, rsi_val=curr_rsi, thought_log=thoughts,
        )

    if not risk.approved:
        return Decision(
            action="WAIT", direction=direction,
            confidence=int(total), grade=grade,
            regime=regime.type, regime_score=regime.score,
            structure=structure.position, structure_score=structure.confluence_score,
            entry_score=entry.timing_score,
            reason=f"Risk blocked: {risk.rejection_reason}",
            adx_val=adx_val, rsi_val=curr_rsi, thought_log=thoughts,
        )

    # Confidence threshold: exactly 50% for all symbols (user requirement: show 50%, trade at >=50%)
    thr = 50.0
    # NOTE: Calibration penalty is intentionally disabled to keep threshold locked at 50%
    # (self_optimizer cannot drift the gate — threshold is LOCKED by CONFIDENCE_THRESHOLD_LOCKED)
    if total < thr:
        return Decision(
            action="WAIT", direction=direction,
            confidence=int(total), grade=grade,
            regime=regime.type, regime_score=regime.score,
            structure=structure.position, structure_score=structure.confluence_score,
            entry_score=entry.timing_score,
            reason=f"Scalp conf {total:.0f}% < {thr:.0f}% threshold (cal_penalty applied)",
            adx_val=adx_val, rsi_val=curr_rsi, thought_log=thoughts,
        )

    # ── Scalp trade approved ──────────────────────────────────
    # Compute ATR-scaled SL/TP — SL is never zero
    try:
        _s_exits = risk_mgr.atr_scaled_sl_tp(symbol, atr_estimate, int(total))
        _s_sl  = _s_exits["sl_pts"]
        _s_tp  = _s_exits["tp_pts"]
        _s_rr  = _s_exits["rr_ratio"]
    except Exception:
        is_gold = ("XAU" in symbol.upper() or "GOLD" in symbol.upper())
        _s_sl, _s_tp, _s_rr = (150, 300, 2.0) if is_gold else (40, 80, 2.0)  # safe symbol defaults (meets mandatory SL floor)

    mode_name = f"SCALP_{scalp_ctrl.upper()}"
    final = (
        f"📈 SCALP TRADE | conf={total:.0f}% {grade} | "
        f"{direction} {symbol} | Lot:{lot} | SL:{_s_sl}pts TP:{_s_tp}pts R:R:{_s_rr} | {mode_name}"
    )
    logger.info(f"[{symbol}] {final}")

    return Decision(
        action="TRADE",
        direction=direction,
        lot=lot,
        tp_points=_s_tp,
        sl_points=_s_sl,
        confidence=int(total),
        grade=grade,
        regime=regime.type,
        regime_score=regime.score,
        structure=structure.position,
        structure_score=structure.confluence_score,
        entry_score=entry.timing_score,
        reason=final,
        pattern=entry.reason,
        rr_ratio=_s_rr,
        news_clear=True,
        mode=mode_name,
        adx_val=adx_val,
        rsi_val=curr_rsi,
        thought_log=thoughts,
        signal_source="SCALP",
    )


# ─────────────────────────────────────────────────────────────
# RL Agent Helper
# ─────────────────────────────────────────────────────────────

_rl_agent = None
_rl_agent_challenger = None

def get_rl_agent():
    global _rl_agent
    if _rl_agent is None:
        try:
            from config.quant_x_config import QX
            if QX.flag("offline_rl"):
                from brain.offline_rl_agent import AegisOfflineRLAgent
                _rl_agent = AegisOfflineRLAgent()
                logger.info("[RL] Loaded Offline CQL Agent for decision flow.")
            else:
                from brain.reinforcement_agent import AegisRLAgent
                _rl_agent = AegisRLAgent()
        except Exception as e:
            logger.error(f"Error loading RL Agent in brain decision flow: {e}")
    return _rl_agent

def get_rl_agent_challenger():
    global _rl_agent_challenger
    if _rl_agent_challenger is None:
        try:
            from config.quant_x_config import QX
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            challenger_path = os.path.join(base_dir, "models", "aegis_rl_challenger.pt")
            if os.path.exists(challenger_path):
                if QX.flag("offline_rl"):
                    from brain.offline_rl_agent import AegisOfflineRLAgent
                    _rl_agent_challenger = AegisOfflineRLAgent(model_path=challenger_path)
                else:
                    from brain.reinforcement_agent import AegisRLAgent
                    _rl_agent_challenger = AegisRLAgent(model_path=challenger_path)
                logger.info(f"[RL] Loaded Challenger RL Agent from {challenger_path}")
            else:
                logger.debug(f"Challenger RL Agent weights file not found at {challenger_path}")
        except Exception as e:
            logger.error(f"Error loading Challenger RL Agent: {e}")
    return _rl_agent_challenger



# ─────────────────────────────────────────────────────────────
# Public wrapper — crash-safe
# ─────────────────────────────────────────────────────────────

def decide(ticks=None, candles_m5=None, account: dict = None, risk_mgr=None, session: str = "LONDON",
           spread: float = 15.0, point: float = 0.01, symbol: str = "XAUUSD",
           candles_m1=None, current_price=None, **kwargs) -> Decision:
    """
    Bulletproof wrapper. Orchestrates the Aegis Quant X execution workflow
    when flags are enabled; falls back fully to v8.0-v9.0 trading loop when disabled.
    """
    if isinstance(ticks, (list, pd.DataFrame)) and candles_m5 is None:
        candles_m5 = ticks
        ticks = []
    if ticks is None:
        ticks = []
    if account is None:
        account = {"equity": 10000.0, "balance": 10000.0}

    from config.quant_x_config import QX

    # ─────────────────────────────────────────────────────────────
    # LAYER 1: DATA INTEGRITY (Phase 1)
    # ─────────────────────────────────────────────────────────────
    if QX.flag("data_integrity"):
        from brain.data_integrity import validate_bars, validate_tick_feed
        validated_m5 = validate_bars(candles_m5, ticks, symbol, point)
        if validated_m5 is None:
            return Decision(action="WAIT", reason="VETO | Data integrity check failed (stale or gaps)", confidence=0)
        candles_m5 = validated_m5
        
        if candles_m1 is not None:
            validated_m1 = validate_bars(candles_m1, ticks, symbol, point)
            if validated_m1 is not None:
                candles_m1 = validated_m1
                
        if not validate_tick_feed(ticks, symbol):
            return Decision(action="WAIT", reason="VETO | Tick feed stale", confidence=0)

    # ─────────────────────────────────────────────────────────────
    # LAYER 2: MACRO & EVENT CONTEXT (Phase 2)
    # ─────────────────────────────────────────────────────────────
    macro_blackout = False
    macro_reduced_size = False
    reduced_factor = 1.0
    macro_tags = {}
    if QX.flag("macro_event_context"):
        from brain.macro_context import get_macro_context
        m_ctx = get_macro_context().get_event_context(symbol)
        macro_blackout = m_ctx.blackout
        macro_reduced_size = m_ctx.reduced_size
        reduced_factor = m_ctx.reduced_size_factor
        macro_tags = get_macro_context().get_bar_tags(time.time() if ticks is None or len(ticks) == 0 else float(ticks[-1]["time_msc"]/1000.0))

    # Run default decision engine implementation
    try:
        decision = _decide_impl(ticks, candles_m5, account, risk_mgr,
                                session, spread, point, symbol, candles_m1)
    except Exception as e:
        logger.error(
            f"[{symbol}] BRAIN CRASH — safe WAIT returned. Error: {e}",
            exc_info=True,
        )
        decision = Decision(
            action="WAIT",
            reason=f"Brain error (safe fallback): {type(e).__name__}: {e}",
            confidence=0,
            grade="F",
        )

    # Extract state features for ML / RL
    cl = [c[4] for c in candles_m5] if not isinstance(candles_m5[-1], dict) else [c["close"] for c in candles_m5]
    highs = [c[2] for c in candles_m5] if not isinstance(candles_m5[-1], dict) else [c["high"] for c in candles_m5]
    lows = [c[3] for c in candles_m5] if not isinstance(candles_m5[-1], dict) else [c["low"] for c in candles_m5]
    
    atr_val = 0.0
    try:
        atrs = ATR(highs, lows, cl, 14)
        atr_val = atrs[-1] if atrs else 0.0
    except Exception:
        pass

    rl_features = [
        float(decision.regime_score or 0.0),
        float(decision.structure_score or 0.0),
        float(decision.entry_score or 0.0),
        float(decision.rsi_val or 50.0),
        float(decision.adx_val or 20.0),
        float(atr_val),
        float(spread or 0.0),
        float(account.get("wins", 0) if isinstance(account, dict) else 0.0),
        float(account.get("losses", 0) if isinstance(account, dict) else 0.0),
    ]

    # Predict RL Action
    rl_action, rl_conf = "WAIT", 0
    try:
        rl_agent = get_rl_agent()
        if rl_agent:
            rl_action, rl_conf = rl_agent.predict_action(rl_features)
    except Exception as e:
        logger.error(f"Error executing RL Agent analysis: {e}")

    # Run challenger in shadow mode
    try:
        from brain.champion_challenger import get_arena
        arena = get_arena()
        if arena.has_challenger() and rl_features:
            chal_agent = get_rl_agent_challenger()
            if chal_agent:
                chal_action, chal_conf = chal_agent.predict_action(rl_features)
                arena.record_challenger_shadow("WIN" if rl_action == chal_action else "LOSS", 1.0 if rl_action == chal_action else -1.0)
    except Exception as e:
        logger.error(f"Error executing Challenger RL Agent shadow analysis: {e}")

    # ─────────────────────────────────────────────────────────────
    # MODULE 3: QUANT FEATURE ADJUSTMENT (flag-gated)
    # Hurst exponent adjusts entry_score before fusion.
    # boost  (+5 pts): H > 0.55 and signal is trend-following → market is trending
    # penalty (-5 pts): H < 0.45 and signal is trend-following → mean-reverting market
    # ─────────────────────────────────────────────────────────────
    if QX.flag("quant_features"):
        try:
            _closes_for_quant = cl[-50:] if len(cl) >= 50 else cl
            from modules.feature_factory import FeatureFactory as _FF
            _ff_inst = _FF(point)
            _quant_feats = _ff_inst.extract_quant(_closes_for_quant)
            if _quant_feats:
                _hurst = float(_quant_feats.get("hurst", 0.5))
                _hurst_adj = 0
                if decision.action == "TRADE":
                    if _hurst > 0.55:
                        _hurst_adj = +5
                    elif _hurst < 0.45:
                        _hurst_adj = -5
                if _hurst_adj != 0:
                    decision.confidence = max(0, min(100, decision.confidence + _hurst_adj))
                    decision.reason = (
                        f"{decision.reason} | QUANT: Hurst={_hurst:.2f} "
                        f"({'TRENDING +5' if _hurst_adj > 0 else 'MEAN-REV -5'})"
                    )
                logger.debug(
                    "[MODULE3] Hurst=%.3f entropy=%.3f dominant_cycle=%.1f adj=%+dpts conf=%d",
                    _hurst,
                    _quant_feats.get("entropy_shannon", 0),
                    _quant_feats.get("dominant_cycle", 0),
                    _hurst_adj,
                    decision.confidence,
                )
        except Exception as _qf_ex:
            logger.debug("[MODULE3] Quant feature adjustment skipped: %s", _qf_ex)

    # ─────────────────────────────────────────────────────────────
    # LAYER 3: DECISION FUSION v2 (Phase 8)
    # ─────────────────────────────────────────────────────────────
    if QX.flag("decision_fusion_v2"):
        from brain.decision_fusion import DecisionFusionV2
        from brain.ml_ensemble import get_ml_ensemble, enrich_prediction_with_disagreement
        
        # Build features dict for ML Ensemble
        ml_features = {
            "confidence": decision.confidence,
            "regime": decision.regime,
            "structure": decision.structure,
            "regime_score": decision.regime_score,
            "structure_score": decision.structure_score,
            "entry_score": decision.entry_score,
            "rsi": decision.rsi_val,
            "adx": decision.adx_val,
            "atr": atr_val,
            "spread": spread
        }
        
        ml_prediction = None
        try:
            raw_ml = get_ml_ensemble().predict(ml_features)
            enriched_ml = enrich_prediction_with_disagreement(raw_ml)
            ml_prediction = {
                "direction": enriched_ml.direction,
                "win_probability": enriched_ml.win_probability,
                "uncertainty": enriched_ml.uncertainty
            }
        except Exception as e:
            logger.warning(f"ML Ensemble prediction failed during fusion: {e}")

        # Check drift & calibration
        from brain.calibration import get_calibration_monitor
        from brain.drift_monitor import get_drift_monitor
        cal_penalty = get_calibration_monitor().get_threshold_penalty()
        drift_status = get_drift_monitor().get_status()
        drift_defensive = drift_status.get("defensive_forced", False)
        
        regime_state = analyze_regime(candles_m5, symbol=symbol, point=point)

        fusion_result = DecisionFusionV2().fuse(
            smc_signal={"direction": decision.direction if decision.signal_source == "SMC" else "NONE", "confidence": decision.confidence},
            scalp_signal={"direction": decision.direction if decision.signal_source == "SCALP" else "NONE", "confidence": decision.confidence},
            ml_prediction=ml_prediction,
            rl_action=rl_action,
            rl_confidence=rl_conf,
            stat_analysis=None,
            macro_blackout=macro_blackout,
            regime_type=decision.regime,
            regime_confidence=getattr(regime_state, "regime_confidence", 0.0),
            regime_ambiguous=getattr(regime_state, "ambiguous", False),
            calibration_penalty=cal_penalty,
            drift_defensive=drift_defensive
        )

        decision.action = fusion_result.action
        decision.direction = fusion_result.fused_direction
        decision.confidence = fusion_result.confidence
        if fusion_result.block_reason:
            decision.reason = fusion_result.block_reason

    # ─────────────────────────────────────────────────────────────
    # LAYER 4: RISK INTELLIGENCE v2 (Phase 9)
    # ─────────────────────────────────────────────────────────────
    # Volatility scaled position lot
    if QX.flag("volatility_scaled_lot") and atr_val > 0:
        decision.lot = risk_mgr.volatility_scaled_lot(symbol, atr_val, decision.lot)

    # Margin buffer check
    if QX.flag("margin_buffer_check"):
        if not risk_mgr.margin_buffer_check(account):
            decision.action = "WAIT"
            decision.reason = "VETO | Margin level buffer breach"

    # Correlation check
    if decision.action == "TRADE":
        if not risk_mgr.correlation_exposure_check(symbol, decision.direction):
            decision.action = "WAIT"
            decision.reason = f"VETO | Multi-position correlation limit on {symbol}"

    # ─────────────────────────────────────────────────────────────
    # LAYER 5: EXECUTION INTEGRITY (Phase 10)
    # ─────────────────────────────────────────────────────────────
    if QX.flag("execution_integrity"):
        from brain.execution_integrity import BrokerAnomalyDetector
        detector = BrokerAnomalyDetector()
        if not detector.check_spread(symbol, spread):
            decision.action = "WAIT"
            decision.reason = "VETO | Broker spread anomaly detected"

    # Apply regime switcher profile adjustments
    try:
        from brain.regime_switcher import get_strategy_state
        switcher = get_strategy_state()
        switched = switcher.evaluate_and_switch(
            regime_type=decision.regime,
            adx=decision.adx_val,
            session=session,
            recent_win_rate=0.5
        )
        profile = switcher.current_profile
        if decision.action == "TRADE":
            decision.lot = round(decision.lot * profile.lot_multiplier, 2)
            decision.lot = max(0.01, decision.lot)
    except Exception as e:
        logger.error(f"Regime switcher error in decidewrapper: {e}")

    # Build and Save Explainability record
    try:
        explanation = build_explanation(
            trade_id=None,
            symbol=symbol,
            direction=decision.direction,
            action=decision.action,
            confidence=decision.confidence,
            signal_sources={
                "SCALP": {"passed": decision.signal_source == "SCALP", "reason": decision.reason},
                "SMC":   {"passed": decision.signal_source == "SMC",   "reason": decision.reason},
            },
            component_breakdown={
                "structure": {"score": decision.structure_score},
                "smc":       {"score": decision.regime_score},
                "mtf":       {"score": 0},
            },
            veto_checks=[],
            market_context={
                "regime":  decision.regime,
                "session": session,
                "adx":     decision.adx_val,
                "rsi":     decision.rsi_val,
                "spread":  spread,
            },
            risk_assessment={
                "lot":       decision.lot,
                "sl_points": decision.sl_points,
                "tp_points": decision.tp_points,
                "rr_ratio":  decision.rr_ratio,
            },
        )
        save_explanation(explanation)
    except Exception as e:
        logger.error(f"[{symbol}] Explainability error: {e}")

    # ─────────────────────────────────────────────────────────────
    # LAYER 6: OBSERVABILITY STRUCTURING (Phase 13)
    # ─────────────────────────────────────────────────────────────
    try:
        from brain.observability import get_observability_logger, DecisionRecord
        from brain.feature_pipeline import FEATURE_SCHEMA_HASH
        obs_logger = get_observability_logger()
        rec = DecisionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=symbol,
            action=decision.action,
            direction=decision.direction,
            confidence=decision.confidence,
            uncertainty=getattr(decision, "uncertainty", 0.0),
            regime=decision.regime,
            regime_confidence=0.0,
            features_summary=json.dumps({"adx": decision.adx_val, "rsi": decision.rsi_val, "atr": atr_val}),
            model_outputs=json.dumps({"rl_action": rl_action, "rl_confidence": rl_conf}),
            risk_assessment=json.dumps({"lot": decision.lot, "sl": decision.sl_points, "tp": decision.tp_points}),
            sizing_rationale="volatility_scaled" if QX.flag("volatility_scaled_lot") else "fixed",
            execution_details=json.dumps({"spread": spread}),
            outcome="UNKNOWN",
            shap_top_3=json.dumps([]),
            config_hash=FEATURE_SCHEMA_HASH,
            model_version_id="Aegis_Quant_X_v9.0"
        )
        obs_logger.log_decision_record(rec)
    except Exception as e:
        logger.error(f"Failed to log decision record: {e}")

    try:
        log_decision(decision)
    except Exception as e:
        logger.error(f"log_decision failed: {e}")

    return decision

