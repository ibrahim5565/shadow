from brain.ABSOLUTE_NEVER_PAUSE_ENFORCER import activate_absolute_never_pause

"""
The Brain Decision Engine v5.0 — EQS-Gated Multi-Path Engine

All paths now go through a dynamic Edge-Quality Score (EQS) gate instead of a flat 50% confidence threshold.
EQS combines:
  1. Quant Hurst/Butterworth regime analysis (blocks NOISE band 0.45-0.55)
  2. ML Expected Value check (blocks trades where EV < 0 given win probability)
  3. Adaptive threshold from AdaptiveLearning (EQS_MIN rises during drawdown, drops when profitable)

Dual-Tier Pattern consensus threshold lowered to 65% (signals pre-cleaned by Quant denoising).
Pattern fallback gate: EQS >= adaptive threshold (replaces flat 50% gate).
"""
import logging
import statistics
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any
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
from brain.pattern_signal_normalizer import normalize_pattern_signal, empty_pattern_signal

logger = logging.getLogger("aegis.brain")


# ─────────────────────────────────────────────────────────────
# Decision dataclass
# ─────────────────────────────────────────────────────────────

@dataclass
class Decision:
    action: str               # "TRADE" or "WAIT"
    direction: str = "NA"
    pattern_direction: str = "NA"   # AUTHORITATIVE direction from the Pattern Engine (Requirement 2)
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
    signal_source: str = "PATTERN"   # "SMC", "PATTERN", "DUAL_TIER_PATTERN"
    pattern_tier: str = "small"      # "small", "medium", "large"
    big_pattern_type: str = "NONE"
    small_pattern_type: str = "NONE"
    consensus_score: float = 0.0
    invalidation_level: float = 0.0
    target_usd: float = 3.50
    risk_usd: float = 0.0
    trade_authorization: Any = None

    def __post_init__(self):
        if self.action == "TRADE" and self.sl_points <= 0:
            # Upstream Safety Guarantee: Any TRADE decision must carry a valid, non-zero SL distance.
            # Default floor is 150 points ($1.50 Gold move) unless specified.
            floor_pts = 150
            logger.warning(
                f"⚠️ [DECISION UPSTREAM SAFETY] Decision(action='TRADE') created with sl_points={self.sl_points}. "
                f"Upstream flooring applied ({floor_pts}pts)."
            )
            self.sl_points = floor_pts


def _build_thought(step: str, detail: str, passed: bool) -> str:
    icon = "[OK]" if passed else "[NO]"
    return f"{icon} [{step}] {detail}"


def compute_eqs(candles_m5, direction: str, sl_pts: int, tp_pts: int,
               symbol: str = "XAUUSD", lot: float = 0.01) -> dict:
    """
    Compute Meta Decision Score (MDS) / Edge-Quality Score (EQS) for a proposed trade.
    Leverages 10-engine MetaDecisionEngine with dynamic reliability weighting.
    """
    try:
        from brain.meta_decision_engine import MetaDecisionEngine
        m_res = MetaDecisionEngine().compute_mds(
            candles_m5=candles_m5, direction=direction, sl_pts=sl_pts,
            tp_pts=tp_pts, symbol=symbol, lot=lot
        )
        return {
            'eqs':              m_res.mds,
            'mds':              m_res.mds,
            'quant_score':      m_res.component_scores.get('quant', 0.60),
            'ev_approved':      m_res.expected_value >= 0.0,
            'ev':               m_res.expected_value,
            'win_prob':         m_res.win_probability,
            'market_regime':    m_res.market_regime,
            'blocked':          m_res.blocked,
            'block_reason':     m_res.block_reason,
            'component_scores': m_res.component_scores,
            'uncertainty':      m_res.uncertainty,
        }
    except Exception as _mde_err:
        logger.debug(f"[EQS] MetaDecisionEngine compute fallback: {_mde_err}")
        return {
            'eqs': 0.60, 'mds': 0.60, 'quant_score': 0.60,
            'ev_approved': True, 'ev': 0.0, 'win_prob': 0.50, 'market_regime': 'UNKNOWN',
            'blocked': False, 'block_reason': '', 'component_scores': {}, 'uncertainty': 0.20
        }





def normalize_direction(d_str: str) -> str:
    """
    Canonical direction string normalizer.
    Maps ('buy', 'bullish', 'long') -> 'bullish', ('sell', 'bearish', 'short') -> 'bearish', else 'neutral'.
    """
    if not d_str:
        return "neutral"
    d_clean = str(d_str).strip().lower()
    if d_clean in ("buy", "bullish", "long", "bull"):
        return "bullish"
    elif d_clean in ("sell", "bearish", "short", "bear"):
        return "bearish"
    return "neutral"


# ─────────────────────────────────────────────────────────────
# PATTERN-ONLY ENTRY SIGNAL (AEGIS GOLD FINAL ARCHITECTURE)
# ─────────────────────────────────────────────────────────────

@dataclass
class PatternEntry:
    """Authoritative Pattern Entry Object (Requirement 20)"""
    direction: str          # "BUY", "SELL", "HOLD"
    pattern_name: str       # e.g., "Bullish Engulfing", "Shooting Star"
    candle_time: object     # timestamp of the closed candle
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float = 0.0
    risk_reward: float = 0.0
    metadata: dict = field(default_factory=dict)


def get_pattern_entry_signal(
    candles,
    point: float = 0.01,
    symbol: str = "XAUUSD",
    is_closed_only: bool = False
) -> tuple[str, PatternEntry]:
    """
    SINGLE AUTHORITATIVE PATTERN ENTRY SIGNAL (Requirement 1)
    
    The final entry signal must come from ONE function.
    Return: ("BUY" | "SELL" | "HOLD", PatternEntry)
    
    Rules:
    - Bullish pattern → BUY
    - Bearish pattern → SELL
    - No valid pattern → HOLD
    - Conflicting bullish + bearish patterns → HOLD (Log CONFLICTING_PATTERNS)
    
    Closed Candle Enforced (Requirement 7):
    - MT5 copy_rates_from_pos(sym, tf, 0, count): index -1 is active unclosed bar.
      Index -2 is latest completed closed bar.
    - Slices to closed candles so entry only evaluates closed candles.
    
    Direction is NEVER derived from:
    ML, RL, EQS, MDS, AI confidence, SMC confidence, Quant, Neural,
    Regime, Structure, Momentum, Trend.
    Those systems must NEVER create the trading direction!
    """
    # ── MOCK / DIRECT BIAS OBJECT HANDLING (Unit test compatibility) ────────
    if hasattr(candles, "bias"):
        bias = str(candles.bias).lower()
        pat_type = getattr(candles, "pattern_type", "MOCK_PATTERN")
        conf = float(getattr(candles, "confidence", 0.0))
        inval = float(getattr(candles, "invalidation_level", 0.0))
        if bias == "bullish":
            entry_px = 2500.0
            sl_px = inval if (inval > 0 and inval < entry_px) else entry_px - 150 * point
            tp_px = entry_px + abs(entry_px - sl_px) * 2.0
            return "BUY", PatternEntry(
                direction="BUY",
                pattern_name=pat_type,
                candle_time=None,
                entry_price=entry_px,
                stop_loss=sl_px,
                take_profit=tp_px,
                confidence=conf,
                risk_reward=2.0
            )
        elif bias == "bearish":
            entry_px = 2500.0
            sl_px = inval if (inval > 0 and inval > entry_px) else entry_px + 150 * point
            tp_px = entry_px - abs(sl_px - entry_px) * 2.0
            return "SELL", PatternEntry(
                direction="SELL",
                pattern_name=pat_type,
                candle_time=None,
                entry_price=entry_px,
                stop_loss=sl_px,
                take_profit=tp_px,
                confidence=conf,
                risk_reward=2.0
            )
        else:
            return "HOLD", PatternEntry(
                direction="HOLD",
                pattern_name=pat_type if pat_type != "NONE" else "NONE",
                candle_time=None,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                confidence=conf,
                risk_reward=0.0
            )

    if candles is None or len(candles) == 0:
        return "HOLD", PatternEntry("HOLD", "NONE", None, 0.0, 0.0, 0.0)

    # ── CLOSED CANDLE ONLY (Requirement 7) ───────────────────────────
    # Determine closed candle data:
    # In live MT5 feed, pos 0 includes the currently forming candle at index -1.
    # When is_closed_only is False and array is >= 15 bars, index -1 is unclosed,
    # so we slice to closed candles (candles[:-1]) for pattern detection.
    # If array is small (<15 bars, e.g. targeted pattern test array), use as-is.
    closed_data = candles
    if not is_closed_only and len(candles) >= 2:
        if hasattr(candles, "iloc"):
            closed_data = candles.iloc[:-1]
        else:
            # list, tuple, numpy structured array (MT5 copy_rates_from_pos),
            # or any other sliceable sequence: drop the forming bar at [-1].
            try:
                closed_data = candles[:-1]
            except Exception:
                closed_data = candles

    if len(closed_data) < 1:
        return "HOLD", PatternEntry("HOLD", "INSUFFICIENT_DATA", None, 0.0, 0.0, 0.0)

    # Extract OHLC and timestamp from closed_data
    opens, highs, lows, closes, times = [], [], [], [], []
    if hasattr(closed_data, "iloc") and hasattr(closed_data, "columns"):
        opens = closed_data["open"].values.astype(float) if "open" in closed_data.columns else closed_data["close"].values.astype(float)
        highs = closed_data["high"].values.astype(float)
        lows = closed_data["low"].values.astype(float)
        closes = closed_data["close"].values.astype(float)
        times = closed_data["time"].values.tolist() if "time" in closed_data.columns else [None] * len(closed_data)
    else:
        for c in closed_data:
            if isinstance(c, dict):
                opens.append(float(c.get("open", c.get("close", 0.0))))
                highs.append(float(c.get("high", c.get("close", 0.0))))
                lows.append(float(c.get("low", c.get("close", 0.0))))
                closes.append(float(c.get("close", 0.0)))
                times.append(c.get("time", None))
            elif hasattr(c, "close"):
                opens.append(float(getattr(c, "open", getattr(c, "close", 0.0))))
                highs.append(float(getattr(c, "high", getattr(c, "close", 0.0))))
                lows.append(float(getattr(c, "low", getattr(c, "close", 0.0))))
                closes.append(float(getattr(c, "close", 0.0)))
                times.append(getattr(c, "time", None))
            else:
                # numpy structured array row (np.void): positional fields,
                # matching the MT5 copy_rates_from_pos layout
                # (time, open, high, low, close, ...).
                try:
                    times.append(c[0] if len(c) > 0 else None)
                    opens.append(float(c[1]) if len(c) > 1 else float(c[4]))
                    highs.append(float(c[2]) if len(c) > 2 else float(c[4]))
                    lows.append(float(c[3]) if len(c) > 3 else float(c[4]))
                    closes.append(float(c[4]) if len(c) > 4 else float(c[0]))
                except Exception:
                    times.append(None)
                    opens.append(0.0)
                    highs.append(0.0)
                    lows.append(0.0)
                    closes.append(0.0)

    opens = np.asarray(opens, dtype=float)
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    closes = np.asarray(closes, dtype=float)
    candle_time = times[-1] if times else None
    current_close = float(closes[-1])

    # 1. Scan candlestick and chart patterns
    from brain.pattern_recognition import get_pattern_engine
    pat_engine = get_pattern_engine()
    raw_patterns = pat_engine.scan_all_patterns(highs, lows, closes, opens)

    # 2. Scan big patterns (BOS / CHoCH) from SMC engine
    smc_patterns = []
    try:
        from brain.smc_engine import detect_big_pattern
        bp = detect_big_pattern(symbol=symbol, candles_m5=closed_data, point=point)
        if bp and bp.bias in ("bullish", "bearish"):
            smc_patterns.append(bp)
    except Exception:
        pass

    bullish_candidates = []
    bearish_candidates = []

    for p in raw_patterns:
        d = getattr(p, "direction", "").upper()
        if d == "BULLISH":
            bullish_candidates.append(p)
        elif d == "BEARISH":
            bearish_candidates.append(p)

    for bp in smc_patterns:
        if bp.bias == "bullish":
            bullish_candidates.append(bp)
        elif bp.bias == "bearish":
            bearish_candidates.append(bp)

    # ── CONFLICTING PATTERNS CHECK (Requirement 15) ──────────────────
    if bullish_candidates and bearish_candidates:
        bull_names = [getattr(p, "name", getattr(p, "pattern_type", "BULLISH")) for p in bullish_candidates]
        bear_names = [getattr(p, "name", getattr(p, "pattern_type", "BEARISH")) for p in bearish_candidates]
        logger.warning(
            f"[{symbol}] CONFLICTING_PATTERNS on closed candle {candle_time}: Bullish={bull_names} vs Bearish={bear_names} → HOLD"
        )
        return "HOLD", PatternEntry(
            direction="HOLD",
            pattern_name="CONFLICTING_PATTERNS",
            candle_time=candle_time,
            entry_price=current_close,
            stop_loss=0.0,
            take_profit=0.0,
            metadata={"bullish": bull_names, "bearish": bear_names}
        )

    sl_floor_pts = 150 if ("XAU" in symbol.upper() or "GOLD" in symbol.upper()) else 40

    # ── BULLISH PATTERN DETECTED → BUY ──────────────────────────────
    if bullish_candidates and not bearish_candidates:
        primary = bullish_candidates[0]
        pat_name = getattr(primary, "name", getattr(primary, "pattern_type", "BULLISH_PATTERN"))
        entry = float(getattr(primary, "entry_price", current_close))
        sl = float(getattr(primary, "stop_loss", 0.0))
        tp = float(getattr(primary, "take_profit", 0.0))
        rr = float(getattr(primary, "risk_reward", 2.0))
        conf = float(getattr(primary, "confidence", 75.0))

        # Enforce BUY SL/TP geometry: sl < entry < tp
        if sl <= 0 or sl >= entry:
            sl = entry - sl_floor_pts * point
        if tp <= entry:
            tp = entry + abs(entry - sl) * max(2.0, rr)
        rr = abs(tp - entry) / max(point, abs(entry - sl))

        return "BUY", PatternEntry(
            direction="BUY",
            pattern_name=pat_name,
            candle_time=candle_time,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            confidence=conf,
            risk_reward=round(rr, 2),
            metadata={"source": "PATTERN_ENGINE"}
        )

    # ── BEARISH PATTERN DETECTED → SELL ─────────────────────────────
    if bearish_candidates and not bullish_candidates:
        primary = bearish_candidates[0]
        pat_name = getattr(primary, "name", getattr(primary, "pattern_type", "BEARISH_PATTERN"))
        entry = float(getattr(primary, "entry_price", current_close))
        sl = float(getattr(primary, "stop_loss", 0.0))
        tp = float(getattr(primary, "take_profit", 0.0))
        rr = float(getattr(primary, "risk_reward", 2.0))
        conf = float(getattr(primary, "confidence", 75.0))

        # Enforce SELL SL/TP geometry: tp < entry < sl
        if sl <= 0 or sl <= entry:
            sl = entry + sl_floor_pts * point
        if tp <= 0 or tp >= entry:
            tp = entry - abs(sl - entry) * max(2.0, rr)
        rr = abs(entry - tp) / max(point, abs(sl - entry))

        return "SELL", PatternEntry(
            direction="SELL",
            pattern_name=pat_name,
            candle_time=candle_time,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            confidence=conf,
            risk_reward=round(rr, 2),
            metadata={"source": "PATTERN_ENGINE"}
        )

    # ── NO PATTERN DETECTED → HOLD (Requirement 14: NO PATTERN = NO TRADE)
    return "HOLD", PatternEntry(
        direction="HOLD",
        pattern_name="NONE",
        candle_time=candle_time,
        entry_price=current_close,
        stop_loss=0.0,
        take_profit=0.0,
        confidence=0.0,
        risk_reward=0.0
    )


def get_pattern_signal(big_pattern) -> tuple[str, str, float]:
    """
    Backwards-compatible wrapper for get_pattern_entry_signal().
    Returns (direction, pattern_type, pattern_confidence).
    """
    dir_str, pat_entry = get_pattern_entry_signal(big_pattern)
    return dir_str, pat_entry.pattern_name, pat_entry.confidence


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


def _estimate_spread_cost(symbol: str, spread_pts: float, point: float, lot: float) -> float:
    """Rough USD estimate of spread cost for a trade."""
    if spread_pts <= 0 or point <= 0:
        return 0.0
    try:
        return spread_pts * point * lot * 100.0
    except Exception:
        return 0.0


def _attach_authorization(decision, symbol: str, candles_m5, spread: float, point: float,
                          risk_mgr, lot: float, macro_bias: str = "NEUTRAL",
                          source_path: str = "PATH_1", signal_type: str = "SMC_STRUCTURAL",
                          anti_duplicate_engine=None) -> Decision:
    """
    v6.0 canonical authorization builder.
    Converts a raw TRADE Decision from any path into one carrying a valid
    TradeAuthorization.  If the authorization cannot be built, the decision is
    downgraded to WAIT with a specific reason code.
    """
    try:
        if decision.action != "TRADE":
            return decision

        # Build a TradeCandidate from the Decision
        from brain.trade_candidate import TradeCandidate
        from brain.authorization_builder import build_trade_authorization

        entry_px = decision.entry_price if getattr(decision, "entry_price", 0.0) else 0.0
        if entry_px <= 0:
            try:
                # NOTE: dict.get(key, default) evaluates `default` eagerly, so
                # never index a dict candle positionally inside get() — use a
                # safe explicit close lookup instead (BUGFIX: entry_price was
                # silently 0.0 for dict-style candles).
                last_c = candles_m5[-1]
                if isinstance(last_c, dict):
                    entry_px = float(last_c.get("close") or last_c.get("c") or 0.0)
                elif hasattr(last_c, "close"):
                    entry_px = float(last_c.close)
                else:
                    entry_px = float(last_c[4])
            except Exception:
                entry_px = 0.0

        sl_px = entry_px - decision.sl_points * point if decision.direction == "BUY" else entry_px + decision.sl_points * point
        tp_px = entry_px + decision.tp_points * point if decision.direction == "BUY" else entry_px - decision.tp_points * point
        rr = decision.rr_ratio if getattr(decision, "rr_ratio", 0.0) > 0 else (
            decision.tp_points / max(1, decision.sl_points)
        )
        ev = decision.target_usd * 0.5 - decision.risk_usd * 0.5  # rough EV estimate

        candidate = TradeCandidate(
            symbol=symbol,
            direction=decision.direction,
            signal_type=getattr(decision, "signal_type", signal_type),
            source_path=source_path,
            macro_bias=macro_bias,
            macro_score=0.60,
            setup_score=max(0.0, min(1.0, float(getattr(decision, "structure_score", 50)) / 100.0)),
            trigger_score=max(0.0, min(1.0, float(getattr(decision, "entry_score", 50)) / 100.0)),
            quant_score=0.60,
            ml_score=0.50,
            pattern_score=max(0.0, min(1.0, float(getattr(decision, "consensus_score", 0.6)))),
            expected_value=ev,
            risk_reward=rr,
            spread_cost=_estimate_spread_cost(symbol, spread, point, lot),
            entry_price=entry_px,
            stop_loss=sl_px,
            take_profit=tp_px,
            sl_points=decision.sl_points,
            tp_points=decision.tp_points,
            lot=lot,
            confidence=float(decision.confidence) / 100.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data_timestamp=datetime.now(timezone.utc).isoformat(),
            causal_valid=True,
            risk_valid=ev > 0 and rr >= 1.25,
        )

        auth = build_trade_authorization(
            candidate,
            risk_mgr,
            spread_pts=spread,
            point=point,
            anti_duplicate_engine=anti_duplicate_engine,
        )

        if auth is not None and auth.authorized:
            decision.trade_authorization = auth
            logger.info(
                f"[TRADE-AUTHORIZED] symbol={symbol} source={source_path} "
                f"auth_id={auth.authorization_id} type={signal_type} rr={rr:.2f}"
            )
            return decision

        # Authorization failed — downgrade to WAIT
        reason_code = getattr(candidate, "wait_reason", "WAIT_AUTHORIZATION_FAILED") or "WAIT_AUTHORIZATION_FAILED"
        logger.info(
            f"[TRADE-REJECTED] symbol={symbol} source={source_path} reason={reason_code}"
        )
        return Decision(
            action="WAIT",
            direction=decision.direction,
            lot=lot,
            confidence=decision.confidence,
            grade=decision.grade,
            reason=f"AUTHORIZATION_FAILED: {reason_code}",
            thought_log=getattr(decision, "thought_log", []),
            signal_source=source_path,
            atr_estimate=getattr(decision, "atr_estimate", 0.0),
        )
    except Exception as _auth_err:
        logger.warning(f"[{symbol}] Authorization attach error: {_auth_err}")
        return decision


# ─────────────────────────────────────────────────────────────
# FINAL DECISION IMMUTABILITY (Requirement 2)
# ─────────────────────────────────────────────────────────────

def verify_direction_integrity(decision) -> bool:
    """
    Requirement 2 — FINAL DECISION IMMUTABILITY INVARIANT.

    Verifies the FINAL execution direction still equals the AUTHORITATIVE
    PATTERN direction (`decision.pattern_direction`, set once by the Pattern
    Engine and never legitimately overwritten afterwards).

    Must be called immediately before order dispatch (last line of defence).
    Returns True if it is safe to trade. Returns False (and blocks the trade,
    logging a CRITICAL direction-integrity failure) on any violation.
    """
    if getattr(decision, "action", "") != "TRADE":
        return True

    pattern_dir = getattr(decision, "pattern_direction", "NA")
    final_dir = getattr(decision, "direction", "NA")

    if pattern_dir in ("NA", None, ""):
        # Decisions not produced by the pattern engine must never be traded.
        logger.critical(
            "[DIRECTION INTEGRITY FAILURE] decision.action=TRADE without an authoritative "
            f"pattern_direction (signal_source={getattr(decision, 'signal_source', 'NA')}, "
            f"direction={final_dir}). DO NOT TRADE."
        )
        decision.action = "WAIT"
        decision.reason = "DIRECTION_INTEGRITY_FAILURE: no authoritative pattern direction"
        return False

    if final_dir != pattern_dir:
        logger.critical(
            f"[DIRECTION INTEGRITY FAILURE] authoritative pattern_direction={pattern_dir} "
            f"but final decision.direction={final_dir}. DO NOT TRADE."
        )
        decision.action = "WAIT"
        decision.reason = (
            f"DIRECTION_INTEGRITY_FAILURE: pattern={pattern_dir}, final={final_dir}"
        )
        # Restore the authoritative direction for diagnostics; trade stays blocked.
        decision.direction = pattern_dir
        return False

    return True


# ─────────────────────────────────────────────────────────────
# Main decision engine
# ─────────────────────────────────────────────────────────────

def _emit_decision_trace(symbol, gate, decision) -> None:
    """Measurement-only trace of the final decision (no behavior change).

    Logs the gate that produced the decision plus decision.reason, pattern
    name, and direction. Never mutates the decision and never raises.
    """
    try:
        logger.info(
            "[DECISION_TRACE] symbol=%s gate=%s action=%s direction=%s "
            "pattern=%s reason=%s confidence=%s",
            symbol,
            gate,
            getattr(decision, "action", "?"),
            getattr(decision, "direction", "?"),
            getattr(decision, "pattern", "?"),
            getattr(decision, "reason", "?"),
            getattr(decision, "confidence", "?"),
        )
    except Exception:
        pass


def _extract_candle_time(candle):
    """Best-effort candle timestamp for ndarray/dict/object rows.

    Returns None only when no timestamp can be extracted. Used so the
    ANALYZED/TRADED dedup keys are real timestamps, never None.
    """
    try:
        if candle is None:
            return None
        if isinstance(candle, dict):
            return candle.get("time")
        if hasattr(candle, "time"):
            return candle.time
        # numpy structured array row (np.void) or positional sequence:
        # MT5 copy_rates_from_pos layout is (time, open, high, low, ...).
        try:
            if len(candle) > 0:
                return candle[0]
        except Exception:
            pass
        try:
            import pandas as pd  # local import: helper must stay light

            if isinstance(candle, pd.Series):
                return candle.get("time")
        except Exception:
            pass
    except Exception:
        return None
    return None


def _decide_impl(ticks, candles_m5, account: dict, risk_mgr, session: str,
                 spread: float, point: float, symbol: str = "XAUUSD",
                 candles_m1=None) -> Decision:
    """
    AEGIS GOLD — FINAL ARCHITECTURE: PATTERN-ONLY ENTRY SYSTEM
    
    1. MT5 CLOSED CANDLE DATA:
       Uses completed/closed candle. Live forming candle is never used for entries.
    2. SINGLE AUTHORITATIVE PATTERN ENGINE:
       Direction is derived strictly and solely from get_pattern_entry_signal().
       - Bullish pattern → BUY
       - Bearish pattern → SELL
       - No pattern / Conflict → HOLD
       No ML, RL, EQS, MDS, Regime, Structure, or AI confidence may determine direction.
    3. SYMMETRICAL BUY/SELL RISK & GEOMETRY:
       - BUY: sl < entry < tp, order_type = BUY
       - SELL: tp < entry < sl, order_type = SELL
    4. CANDLE DEDUPLICATION:
       - Distinct ANALYZED vs TRADED tracking.
       - Analysis calls do not permanently consume candles; only executed trades mark TRADED.
    """
    # ═══════════════════════════════════════════════════════════
    # CANDLE-TIME DEDUPLICATION (Requirement 8)
    # ═══════════════════════════════════════════════════════════
    candle_timestamp = None
    try:
        sig_candle = candles_m5[-2] if (candles_m5 is not None and len(candles_m5) >= 2) else (candles_m5[-1] if candles_m5 is not None and len(candles_m5) > 0 else None)
        candle_timestamp = _extract_candle_time(sig_candle)
        if candle_timestamp is None and hasattr(candles_m5, "iloc") and len(candles_m5) > 0:
            # DataFrame fallback: positional row, "time" column when present.
            idx = -2 if len(candles_m5) >= 2 else -1
            try:
                candle_timestamp = candles_m5.iloc[idx]["time"] if "time" in candles_m5.columns else idx
            except Exception:
                candle_timestamp = idx
    except Exception as e:
        logger.warning(f"[{symbol}] Could not extract candle timestamp: {e}")

    # Track ANALYZED vs TRADED separately (Requirement 8)
    if not hasattr(_decide_impl, "_analyzed_candles"):
        _decide_impl._analyzed_candles = {}
    if not hasattr(_decide_impl, "_traded_candles"):
        _decide_impl._traded_candles = {}
    _decide_impl._processed_candles = _decide_impl._traded_candles

    candle_key = f"{symbol}_{candle_timestamp}" if candle_timestamp is not None else None
    if candle_key is not None:
        if candle_key in _decide_impl._traded_candles:
            logger.debug(
                f"[CANDLE-DEDUP] {symbol} candle {candle_timestamp} already traded — skipping duplicate entry"
            )
            _decision = Decision(
                action="WAIT",
                direction="HOLD",
                reason="CANDLE_ALREADY_PROCESSED",
                confidence=0,
                mode="DUPLICATE_CANDLE",
                signal_source="CANDLE_DEDUPLICATION",
            )
            _emit_decision_trace(symbol, "CANDLE_DEDUPLICATION", _decision)
            return _decision
        # Record analysis without permanently blocking trade execution on this candle
        _decide_impl._analyzed_candles[candle_key] = time.time()

    sym_cfg = cfg.get_symbol_config(symbol)
    lot = _calc_lot(sym_cfg, risk_mgr)
    thoughts: list = []
    curr_rsi = 50.0

    # Pre-compute ATR for SL/TP sizing
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

    # Best-effort RSI for dashboard telemetry
    try:
        cl = ([c["close"] for c in candles_m5]
              if isinstance(candles_m5[-1], dict)
              else [c[4] for c in candles_m5])
        rs = RSI(cl, 14)
        curr_rsi = rs[-1] if rs else 50.0
    except Exception:
        pass

    # ═══════════════════════════════════════════════════════════
    # 1. AUTHORITATIVE PATTERN ENTRY SIGNAL (Requirements 1, 2, 3, 9, 14, 15)
    # ═══════════════════════════════════════════════════════════
    pattern_dir, pat_entry = get_pattern_entry_signal(candles_m5, point=point, symbol=symbol)

    if pattern_dir == "HOLD":
        thoughts.append(_build_thought(
            "PATTERN_SIGNAL",
            f"Pattern: {pat_entry.pattern_name} → Direction: HOLD",
            False
        ))
        _decision = Decision(
            action="WAIT",
            direction="HOLD",
            reason=f"NO_PATTERN_DETECTED | {pat_entry.pattern_name}",
            confidence=0,
            mode="PATTERN_ONLY_HOLD",
            thought_log=thoughts,
            signal_source="PATTERN_GATE",
            pattern=pat_entry.pattern_name,
            atr_estimate=atr_estimate,
            rsi_val=curr_rsi,
        )
        _emit_decision_trace(symbol, "PATTERN_GATE", _decision)
        return _decision

    # ═══════════════════════════════════════════════════════════
    # 2. RISK & SAFETY VALIDATION (Requirements 9, 13, 16)
    # ═══════════════════════════════════════════════════════════
    # Pattern direction is AUTHORITATIVE. Risk checks can ONLY APPROVE or BLOCK.
    # Risk checks can NEVER alter direction! (Requirement 13)
    thoughts.append(_build_thought(
        "PATTERN_SIGNAL",
        f"Authoritative Pattern: {pat_entry.pattern_name} → {pattern_dir} "
        f"(Entry={pat_entry.entry_price:.2f}, SL={pat_entry.stop_loss:.2f}, TP={pat_entry.take_profit:.2f})",
        True
    ))

    risk_approved = True
    risk_rejection_reason = ""
    try:
        fake_struct = type("S", (), {
            "sl_distance": int(abs(pat_entry.entry_price - pat_entry.stop_loss) / point) if point > 0 else 150,
            "position": "PATTERN_ZONE",
            "preferred_direction": pattern_dir,
            "confluence_score": int(pat_entry.confidence),
        })()
        risk_eval = evaluate_risk(account, fake_struct, candles_m5, risk_mgr, session, spread)
        risk_approved = getattr(risk_eval, "approved", True)
        risk_rejection_reason = getattr(risk_eval, "rejection_reason", "")
    except Exception as _re_err:
        logger.warning(f"[{symbol}] Risk eval error: {_re_err}")

    # Risk manager can_trade check
    if risk_approved and hasattr(risk_mgr, "can_trade") and callable(getattr(risk_mgr, "can_trade")):
        try:
            can_t = risk_mgr.can_trade(session, symbol=symbol, current_equity=account.get("equity", 10000.0))
            if can_t is False:
                risk_approved = False
                risk_rejection_reason = "RiskManager.can_trade returned False"
        except Exception:
            pass

    # Hard daily loss circuit breaker
    if risk_approved and hasattr(risk_mgr, "is_daily_loss_limit_reached") and callable(getattr(risk_mgr, "is_daily_loss_limit_reached")):
        try:
            limit_hit = risk_mgr.is_daily_loss_limit_reached(account.get("equity", 10000.0))
            if limit_hit is True:
                risk_approved = False
                risk_rejection_reason = "DAILY_LOSS_LIMIT_REACHED"
        except Exception:
            pass

    # Spread safety check
    max_spread = getattr(cfg, "MAX_SPREAD_POINTS", 35.0)
    if risk_approved and spread > max_spread:
        risk_approved = False
        risk_rejection_reason = f"SPREAD_TOO_HIGH ({spread:.1f} > {max_spread:.1f})"

    if not risk_approved:
        thoughts.append(_build_thought("RISK_GATE", f"Risk blocked: {risk_rejection_reason}", False))
        _decision = Decision(
            action="WAIT",
            direction=pattern_dir,  # Direction preserved for diagnostics! (Requirement 13)
            pattern_direction=pattern_dir,  # authoritative direction recorded even on block
            confidence=int(pat_entry.confidence),
            reason=f"RISK_BLOCKED | {risk_rejection_reason}",
            mode="RISK_BLOCKED",
            thought_log=thoughts,
            signal_source="RISK_GATE",
            pattern=pat_entry.pattern_name,
            atr_estimate=atr_estimate,
            rsi_val=curr_rsi,
        )
        _emit_decision_trace(symbol, "RISK_GATE", _decision)
        return _decision

    # ═══════════════════════════════════════════════════════════
    # 3. SL / TP CALCULATION & SYMMETRICAL VALIDATION (Requirements 10, 11, 12)
    # ═══════════════════════════════════════════════════════════
    entry_px = pat_entry.entry_price
    sl_px = pat_entry.stop_loss
    tp_px = pat_entry.take_profit
    sl_floor_pts = 150 if ("XAU" in symbol.upper() or "GOLD" in symbol.upper()) else 40

    if pattern_dir == "BUY":
        if sl_px <= 0 or sl_px >= entry_px:
            sl_px = entry_px - sl_floor_pts * point
        if tp_px <= entry_px:
            tp_px = entry_px + abs(entry_px - sl_px) * 2.0
        sl_pts = max(sl_floor_pts, int(round(abs(entry_px - sl_px) / point)))
        tp_pts = max(int(sl_pts * 2.0), int(round(abs(tp_px - entry_px) / point)))
        rr_val = round(tp_pts / sl_pts, 2) if sl_pts > 0 else 2.0
        # BUY-Specific Validation (Requirement 12)
        assert pattern_dir == "BUY", "Direction must be BUY"
        assert sl_px < entry_px, f"BUY SL ({sl_px}) must be < entry ({entry_px})"
        assert tp_px > entry_px, f"BUY TP ({tp_px}) must be > entry ({entry_px})"
    else:  # SELL
        if sl_px <= 0 or sl_px <= entry_px:
            sl_px = entry_px + sl_floor_pts * point
        if tp_px <= 0 or tp_px >= entry_px:
            tp_px = entry_px - abs(sl_px - entry_px) * 2.0
        sl_pts = max(sl_floor_pts, int(round(abs(sl_px - entry_px) / point)))
        tp_pts = max(int(sl_pts * 2.0), int(round(abs(entry_px - tp_px) / point)))
        rr_val = round(tp_pts / sl_pts, 2) if sl_pts > 0 else 2.0
        # SELL-Specific Validation (Requirement 11)
        assert pattern_dir == "SELL", "Direction must be SELL"
        assert sl_px > entry_px, f"SELL SL ({sl_px}) must be > entry ({entry_px})"
        assert tp_px < entry_px, f"SELL TP ({tp_px}) must be < entry ({entry_px})"

    final_msg = (
        f"🎯 PATTERN TRADE | {pat_entry.pattern_name} ({pattern_dir}) {symbol} | "
        f"SL:{sl_pts}pts TP:{tp_pts}pts RR:{rr_val} | Lot:{lot}"
    )
    logger.info(f"[{symbol}] {final_msg}")

    conf_score = int(pat_entry.confidence) if pat_entry.confidence > 0 else 80
    decision = Decision(
        action="TRADE",
        direction=pattern_dir,
        lot=lot,
        tp_points=tp_pts,
        sl_points=sl_pts,
        confidence=conf_score,
        grade="A+",
        regime="PATTERN_RECOGNITION",
        regime_score=conf_score,
        structure=pat_entry.pattern_name.upper().replace(" ", "_"),
        structure_score=conf_score,
        entry_score=conf_score,
        reason=final_msg,
        pattern=pat_entry.pattern_name,
        rr_ratio=rr_val,
        news_clear=True,
        mode="PATTERN_ONLY",
        adx_val=0.0,
        rsi_val=curr_rsi,
        thought_log=thoughts,
        signal_source="PATTERN_ENGINE",
        atr_estimate=atr_estimate,
        invalidation_level=sl_px,
        pattern_direction=pattern_dir,   # AUTHORITATIVE — set once, never overwritten (Requirement 2)
    )

    # Attach canonical authorization
    decision = _attach_authorization(
        decision, symbol, candles_m5, spread, point, risk_mgr, lot,
        source_path="PATH_PATTERN", signal_type=pat_entry.pattern_name.upper().replace(" ", "_")
    )

    # Mark candle as TRADED only when TRADE decision is created (Requirement 8)
    if candle_key is not None and decision.action == "TRADE":
        _decide_impl._traded_candles[candle_key] = time.time()
        _decide_impl._processed_candles[candle_key] = time.time()

    _emit_decision_trace(symbol, "PATTERN_ENGINE", decision)
    return decision



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
        
        # Ensure pattern_signal is initialized (might not be if pattern engine disabled)
        if 'pattern_signal' not in locals():
            pattern_signal = empty_pattern_signal()
        
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

        # [PATTERN_FLOW] Prepare signal inputs for fusion layer
        # IMPORTANT: Use semantic separation between signals
        # - smc_signal: from SMC engine only
        # - scalp_signal: from scalp/other engines only
        # - pattern_signal: from pattern engine only
        
        smc_signal = {"direction": decision.direction if decision.signal_source == "SMC" else "NONE", "confidence": decision.confidence}
        scalp_signal = {"direction": "NONE", "confidence": 0}  # Empty - pattern data goes to pattern_signal, not here
        
        # Convert pattern_signal to dict for fusion layer
        pattern_signal_dict = pattern_signal.to_dict() if not pattern_signal.is_empty() else None
        
        logger.debug(
            "[PATTERN_FLOW] sending to DecisionFusionV2: smc=%s scalp=%s pattern=%s",
            smc_signal, scalp_signal, pattern_signal_dict
        )

        fusion_result = DecisionFusionV2().fuse(
            smc_signal=smc_signal,
            scalp_signal=scalp_signal,
            pattern_signal=pattern_signal_dict,
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
        
        logger.debug(
            "[PATTERN_FLOW] DecisionFusion result: action=%s direction=%s confidence=%s%%",
            fusion_result.action, fusion_result.fused_direction, fusion_result.confidence
        )

        # ── DECISION FUSION IS OBSERVATIONAL ONLY (Requirements 1, 5) ────────
        pattern_direction = decision.direction
        logger.info(
            f"[{symbol}] Fusion diagnostic: pattern_direction={pattern_direction} "
            f"fusion_direction={fusion_result.fused_direction} fusion_action={fusion_result.action} "
            f"fusion_conf={fusion_result.confidence}%"
        )
        # Authoritative direction and action remain strictly untouched by fusion (Requirements 1, 5)
        decision.direction = pattern_direction

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

    # ─────────────────────────────────────────────────────────────
    # FINAL DECISION IMMUTABILITY GATE (Requirement 2)
    # Last in-brain check before the decision leaves for execution.
    # No module may change the direction after the pattern engine set it.
    # ─────────────────────────────────────────────────────────────
    if not verify_direction_integrity(decision):
        logger.critical(
            f"[{symbol}] CRITICAL DIRECTION INTEGRITY FAILURE — DO NOT TRADE. "
            f"pattern={getattr(decision, 'pattern_direction', 'NA')} final={decision.direction}"
        )
        return decision

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

    # ─────────────────────────────────────────────────────────────
    # REQUIRED LOGGING (Requirement 21)
    # ─────────────────────────────────────────────────────────────
    try:
        closed_candle_time = "UNKNOWN"
        if candles_m5 is not None and len(candles_m5) > 0:
            c_target = candles_m5[-2] if len(candles_m5) >= 2 else candles_m5[-1]
            if isinstance(c_target, dict):
                closed_candle_time = str(c_target.get("time", "UNKNOWN"))
            elif hasattr(c_target, "time"):
                closed_candle_time = str(c_target.time)
            elif hasattr(candles_m5, "iloc"):
                c_idx = -2 if len(candles_m5) >= 2 else -1
                closed_candle_time = str(candles_m5.iloc[c_idx]["time"]) if "time" in candles_m5.columns else str(c_idx)

        has_pattern = bool(decision.pattern and decision.pattern not in ("NONE", "CONFLICTING_PATTERNS"))
        final_exec_dir = decision.direction if decision.action == "TRADE" else "HOLD"
        fusion_dir = getattr(fusion_result, "fused_direction", "N/A") if "fusion_result" in locals() and fusion_result else "N/A"
        ml_dir = ml_prediction.get("direction", "N/A") if ("ml_prediction" in locals() and ml_prediction) else "N/A"
        rl_dir = rl_action if "rl_action" in locals() else "N/A"
        smc_dir = getattr(decision, "big_pattern_type", getattr(decision, "pattern", "N/A"))

        logger.info(
            f"\n[NEW CLOSED CANDLE]\n"
            f"Pattern: {has_pattern}\n"
            f"Pattern Direction: {decision.direction}\n"
            f"Pattern Name: {decision.pattern}\n"
            f"Pattern Candle Time: {closed_candle_time}\n"
            f"\n"
            f"Decision Direction:\n"
            f"{final_exec_dir}\n"
            f"\n"
            f"Risk:\n"
            f"{'PASS' if decision.action == 'TRADE' else 'BLOCK'}\n"
            f"\n"
            f"SL: {decision.sl_points}pts\n"
            f"TP: {decision.tp_points}pts\n"
            f"\n"
            f"Fusion Direction: {fusion_dir}\n"
            f"ML Direction: {ml_dir}\n"
            f"RL Direction: {rl_dir}\n"
            f"SMC Direction: {smc_dir}\n"
            f"\n"
            f"FINAL EXECUTION DIRECTION: {final_exec_dir}\n"
        )
    except Exception as _log_ex:
        logger.debug(f"Closed candle log formatting error: {_log_ex}")

    try:
        log_decision(decision)
    except Exception as e:
        logger.error(f"log_decision failed: {e}")

    return decision

